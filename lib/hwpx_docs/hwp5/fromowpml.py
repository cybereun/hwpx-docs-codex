"""HWPX -> HWP 5.0 (the reverse converter; rules HW37-HW43 in rules.md).

  convert(src.hwpx, dst.hwp)      OWPML -> records -> compound file; raises Unsupported (`UNSUPPORTED <what> <where>`) when an
                                  element has no record yet: the conversion stops, nothing is dropped silently

Parts: fo_head.py (header.xml -> DocInfo), fo_body.py (section*.xml -> BodyText records), this file (the package: FileHeader,
BinData, Preview, summary, compound file). `hd hwp fromhwpx in.hwpx out.hwp` and `hd hwp build spec.json out.hwp`
(spec -> core.build -> convert) are in hwp5/build.py.
"""
import os
import re
import struct
import time
import xml.etree.ElementTree as ET
import zipfile

from ..core import tmpdir
from . import cfb, fmt
from . import fo_head
from .fo_head import Unsupported, head_records, ln, first

VERSION = 0x05000500                      # 5.0.5.0, the version of the files Hangul 2020-2024 writes


class Source:
    """The parts of an HWPX package this converter reads (nothing else is touched)."""

    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        self.names = self.zip.namelist()
        self.head = ET.fromstring(self.read('Contents/header.xml'))
        hpf = ET.fromstring(self.read('Contents/content.hpf'))
        self.items = {}                                     # manifest id -> (href, media type)
        self.linked = set()                                 # ids of the linked pictures (isEmbeded="0"; their href is the path, HW91)
        self.dst = ''                                       # where the .hwp goes: a linked picture gets its relative path from it
        self.spine = []
        for el in hpf.iter():
            if ln(el) == 'item':
                self.items[el.get('id')] = (el.get('href'), el.get('media-type'))
                if el.get('isEmbeded') == '0' and not (el.get('href', '').startswith('BinData/') and el.get('href') in self.names):
                    self.linked.add(el.get('id'))                 # (hwp2hwpx also writes isEmbeded="0" for an OLE file that is in the package)
            elif ln(el) == 'itemref':
                self.spine.append(el.get('idref'))
        self.meta = {}
        for el in hpf.iter():
            if ln(el) == 'meta' and el.get('name'):
                self.meta[el.get('name')] = (el.text or '')
            elif ln(el) in ('title', 'language'):
                self.meta[ln(el)] = el.text or ''
        self.sections = [self.items[i][0] for i in self.spine if self.items[i][0].startswith('Contents/section')]
        if not self.sections:
            self.sections = sorted((n for n in self.names if re.fullmatch(r'Contents/section\d+\.xml', n)),
                                   key=lambda n: int(re.findall(r'\d+', n)[0]))
        self.ver = (5, 1, 1, 0)
        if 'version.xml' in self.names:
            vx = ET.fromstring(self.read('version.xml'))
            self.ver = tuple(int(vx.get(k, d)) for k, d in (('major', 5), ('minor', 1), ('micro', 1), ('buildNumber', 0)))
        self.tracked = False                                 # the body has tracked changes: ViewText and flag 0x4000 (HW88)
        self.idmaps = {}                                     # old -> new numbers of the dropped list entries (fo_dedupe)
        self.settings = {}
        if 'settings.xml' in self.names:
            for el in ET.fromstring(self.read('settings.xml')).iter():
                if ln(el) == 'CaretPosition':
                    self.settings = {'listIDRef': int(el.get('listIDRef', 0)), 'paraIDRef': int(el.get('paraIDRef', 0)),
                                     'pos': int(el.get('pos', 0))}
                elif ln(el) == 'config-item-set' and el.get('name') == 'PrintInfo':          # the print settings: record 0x1b (HW81)
                    self.settings['print'] = {c.get('name'): (c.text or '').strip() for c in el if ln(c) == 'config-item'}

    def read(self, name):
        if self.zip.getinfo(name).file_size > fmt.MAX_INFLATE:            # a zip bomb: the size is in the directory
            raise Unsupported(f'package part {name} is larger than {fmt.MAX_INFLATE >> 20} MB')
        return self.zip.read(name)

    def has(self, name):
        return name in self.names


def summary_information(meta):
    """`\\x05HwpSummaryInformation`: an OLE property set (title, subject, author, keywords, comments, last author,
    created, saved). Values come from the opf:meta of content.hpf; a missing one is empty."""
    def lpwstr(s):
        b = s.encode('utf-16-le') + b'\x00\x00'
        n = len(b) // 2
        return struct.pack('<II', 0x1F, n) + b + bytes((-len(b)) % 4)

    def filetime(s):
        m = re.match(r'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)', s or '')
        if not m:
            return struct.pack('<IQ', 0x40, 0)
        t = time.mktime(time.struct_time(tuple(map(int, m.groups())) + (0, 0, 0))) - time.timezone
        return struct.pack('<IQ', 0x40, int((t + 11644473600) * 10_000_000))
    props = [(2, lpwstr(meta.get('title', ''))), (3, lpwstr(meta.get('subject', ''))),
             (4, lpwstr(meta.get('creator', ''))), (5, lpwstr(meta.get('keyword', ''))),
             (6, lpwstr(meta.get('description', ''))), (8, lpwstr(meta.get('lastsaveby', ''))),
             (12, filetime(meta.get('CreatedDate'))), (13, filetime(meta.get('ModifiedDate')))]
    fmtid = bytes.fromhex('60b6a29f6110d411b4c6006097c09d8c')       # the format id Hangul uses (also as the class id)
    head = struct.pack('<HHI', 0xFFFE, 0, 0x00020206) + fmtid + struct.pack('<I', 1) + fmtid + struct.pack('<I', 48)
    base = 8 + 8 * len(props)
    table, body = b'', b''
    for pid, val in props:
        table += struct.pack('<II', pid, base + len(body))
        body += val
    return head + struct.pack('<II', base + len(body), len(props)) + table + body


def strip_tracks(recs):
    """BodyText of a document with tracked changes = the records without the range tags of the changes (types 16 and 17)."""
    out, drop = [], 0
    for tag, lvl, d in recs:
        if tag == fmt.T['PARA_RANGE_TAG']:
            keep = b''.join(d[k:k + 12] for k in range(0, len(d), 12) if struct.unpack_from('<I', d, k + 8)[0] >> 24 not in (16, 17))
            if len(keep) != len(d):
                if keep:
                    out.append((tag, lvl, keep))
                continue
        out.append((tag, lvl, d))
    # the range count of each paragraph header follows the records that are left
    res, i = [], 0
    for k, (tag, lvl, d) in enumerate(out):
        if tag == fmt.T['PARA_HEADER'] and len(d) >= 18:
            n = 0
            for tag2, lvl2, d2 in out[k + 1:]:
                if tag2 == fmt.T['PARA_HEADER'] and lvl2 <= lvl:
                    break
                if tag2 == fmt.T['PARA_RANGE_TAG'] and lvl2 == lvl + 1:
                    n += len(d2) // 12
            d = d[:14] + struct.pack('<H', n) + d[16:]
        res.append((tag, lvl, d))
    return res


def convert(src, dst):
    from . import fo_body, fo_dedupe
    del fo_head.WARNINGS[:]
    s = Source(src)
    s.dst = dst
    bins = fo_body.BinTable(s)
    s.idmaps = fo_dedupe.dedupe(s.head, s.ver, bins.by_ref)           # equal list entries are written once (HW83)
    head = head_records(s.head, s.settings, bins.items, s.ver, bins.by_ref)
    recs_by_section = [fo_body.section_records(s, name, bins) for name in s.sections]
    root = cfb.Entry('Root Entry', cfb.ROOT)
    stamp = 133389797792510000
    root.mtime = stamp
    fh = bytearray(256)
    fh[:17] = b'HWP Document File'
    tracked = s.tracked or first(first(s.head, 'refList'), 'trackChanges') is not None
    struct.pack_into('<II', fh, 32, s.ver[0] << 24 | s.ver[1] << 16 | s.ver[2] << 8 | s.ver[3], 1 | (0x4000 if tracked else 0))   # version, bit 0 compressed, bit 14 tracked changes
    root.add(cfb.Entry('FileHeader', cfb.STREAM, bytes(fh)))
    root.add(cfb.Entry('DocInfo', cfb.STREAM, fmt.deflate(fmt.unrecords(head))))
    body = root.add(cfb.Entry('BodyText', cfb.STORAGE, ctime=stamp, mtime=stamp))
    for k, recs in enumerate(recs_by_section):
        body.add(cfb.Entry(f'Section{k}', cfb.STREAM, fmt.deflate(fmt.unrecords(strip_tracks(recs) if tracked else recs))))
    if tracked:                                               # a document with tracked changes keeps the marks in ViewText (HW88)
        view = root.add(cfb.Entry('ViewText', cfb.STORAGE, ctime=stamp, mtime=stamp))
        for k, recs in enumerate(recs_by_section):
            view.add(cfb.Entry(f'Section{k}', cfb.STREAM, fmt.deflate(fmt.unrecords(recs))))
    root.add(cfb.Entry('\x05HwpSummaryInformation', cfb.STREAM, summary_information(s.meta)))
    if s.has('Preview/PrvText.txt'):
        root.add(cfb.Entry('PrvText', cfb.STREAM, s.read('Preview/PrvText.txt').decode('utf-8', 'replace').encode('utf-16-le')))
    if s.has('Preview/PrvImage.png'):
        root.add(cfb.Entry('PrvImage', cfb.STREAM, s.read('Preview/PrvImage.png')))
    # no `Scripts` storage: the HWPX has no script, and a document with a script part makes Hangul show its security-level window
    if bins.items:
        bd = root.add(cfb.Entry('BinData', cfb.STORAGE, ctime=stamp, mtime=stamp))
        for name, data in bins.streams():
            bd.add(cfb.Entry(name, cfb.STREAM, fmt.deflate(data)))     # raw-deflated like the other streams (HW13)
    data = cfb.build(root)
    with fmt.atomic(dst) as tmp, open(tmp, 'wb') as f:
        f.write(data)
    return dst





def selftest():
    """Spec -> HWPX (core.build) -> .hwp: the records read back, the sibling trees are valid, an unknown element stops."""
    import zipfile
    from ..core import build as core_build
    from . import edit
    d = tmpdir.mkdtemp('hwp5_fo_')
    spec = {'title': '시험', 'body': ['제목 문단', {'table': {'cols': [30, 40], 'rows': [['가', {'p': '나', 'rs': 2}], ['다']]}},
                                      '끝 문단']}
    hx, hw = os.path.join(d, 's.hwpx'), os.path.join(d, 's.hwp')
    core_build.write(spec, hx, d)
    convert(hx, hw)
    pk = fmt.Package(hw)
    assert pk.version_text() == '5.1.1.0' and pk.compressed and pk.sections == ['BodyText/Section0'], pk.version_text()
    text = edit.Doc(hw).text()
    assert '제목 문단' in text and '끝 문단' in text and '가' in text and '나' in text and '다' in text, text
    recs = pk.records('BodyText/Section0')
    assert [r[0] for r in recs].count(fmt.T['LIST_HEADER']) == 3 and fmt.T['TABLE'] in [r[0] for r in recs]
    paras = fmt.paragraphs(recs)
    assert sum(1 for p in paras if p.kind == 'cell') == 3 and paras[-1].kind == 'body'
    n_last = struct.unpack_from('<I', recs[paras[-1].head][2])[0]
    assert n_last >> 31 == 1, 'the last paragraph of the body carries bit 31'
    root = cfb.read(open(hw, 'rb').read())
    assert {c.name for c in root.children} >= {'FileHeader', 'DocInfo', 'BodyText', 'PrvText'}
    assert pk.streams['PrvText'].data.decode('utf-16-le').startswith('제목 문단')
    # the DocInfo counts are the HWPX header's counts, less the entries equal to an earlier one (HW83)
    di = [r for r in pk.records('DocInfo') if r[0] == fmt.T['ID_MAPPINGS']][0][2]
    counts = struct.unpack('<18i', di)
    hdr = zipfile.ZipFile(hx).read('Contents/header.xml').decode('utf-8')
    assert 0 < counts[9] <= hdr.count('<hh:charPr ') and 0 < counts[13] <= hdr.count('<hh:paraPr '), counts
    # an element with no record stops the conversion (nothing dropped silently)
    bad = os.path.join(d, 'bad.hwpx')
    with zipfile.ZipFile(hx) as zi, zipfile.ZipFile(bad, 'w') as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == 'Contents/section0.xml':
                data = data.replace(b'<hp:t>', b'<hp:zzz/><hp:t>', 1)
            zo.writestr(it, data)
    try:
        convert(bad, os.path.join(d, 'bad.hwp'))
        raise AssertionError('an unknown element must stop the conversion')
    except Unsupported as e:
        assert 'zzz' in str(e), e
    assert not os.path.exists(os.path.join(d, 'bad.hwp'))
    # the column type is the schema's name both ways: BALANCED_NEWSPAPER -> value 1 -> BALANCED_NEWSPAPER (it was written as NEWSPAPER)
    from . import owpml
    for kind, want in (('BALANCED_NEWSPAPER', 1), ('PARALLEL', 2)):
        col_x, col_hw, col_back = (os.path.join(d, 'col.hwpx'), os.path.join(d, 'col.hwp'), os.path.join(d, 'col_back.hwpx'))
        with zipfile.ZipFile(hx) as zi, zipfile.ZipFile(col_x, 'w') as zo:
            for it in zi.infolist():
                data = zi.read(it.filename)
                if it.filename == 'Contents/section0.xml':
                    assert data.count(b'type="NEWSPAPER"') == 1
                    data = data.replace(b'type="NEWSPAPER"', f'type="{kind}"'.encode())
                zo.writestr(it, data)
        convert(col_x, col_hw)
        cold = [r for r in fmt.Package(col_hw).records('BodyText/Section0') if r[0] == fmt.T['CTRL_HEADER'] and r[2][:4] == b'dloc']
        assert cold and struct.unpack_from('<H', cold[0][2], 4)[0] & 3 == want, (kind, cold[:1])
        owpml.convert(col_hw, col_back)
        assert f'type="{kind}"'.encode() in zipfile.ZipFile(col_back).read('Contents/section0.xml'), kind
    print('FROMOWPML SELFTEST PASS')
