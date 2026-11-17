"""The package around header.xml and the sections: mimetype, version, content.hpf, container, settings, Preview, BinData.

The summary (title, author, dates) is read from `\\x05HwpSummaryInformation` (an OLE property set, [MS-OLEPS]); the files
that Hangul writes the same way for every document (version.xml, container.rdf, manifest.xml) come from core/template, whose
copies Hangul opens.
"""
import datetime
import os
import re
import struct
import zipfile

from . import fmt
from .fmt import Unsupported
from .owpmlmap import NS, El, document

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'core', 'template')
IMAGE_TYPES = {'png': 'image/png', 'jpg': 'image/jpg', 'jpeg': 'image/jpg', 'gif': 'image/gif', 'bmp': 'image/bmp',
               'tif': 'image/tif', 'tiff': 'image/tif', 'wmf': 'image/x-wmf', 'emf': 'image/x-emf'}


def template(name):
    with open(os.path.join(TEMPLATE, *name.split('/')), 'rb') as f:
        return f.read()


def summary(pk):
    """\\x05HwpSummaryInformation -> {property id: value} (strings, FILETIME as datetime). Not there: {}."""
    s = pk.streams.get('\x05HwpSummaryInformation')
    if s is None:
        return {}
    d = s.data
    out = {}
    try:
        nsec = struct.unpack_from('<I', d, 24)[0]
        for i in range(nsec):
            off = struct.unpack_from('<I', d, 44 + 20 * i)[0]
            cnt = struct.unpack_from('<I', d, off + 4)[0]
            for k in range(cnt):
                pid, po = struct.unpack_from('<II', d, off + 8 + 8 * k)
                t = struct.unpack_from('<I', d, off + po)[0] & 0xFFFF
                if t == 0x1F:
                    n = struct.unpack_from('<I', d, off + po + 4)[0]
                    out[pid] = d[off + po + 8:off + po + 8 + 2 * n].decode('utf-16-le', 'replace').split('\0')[0]
                elif t == 0x1E:
                    n = struct.unpack_from('<I', d, off + po + 4)[0]
                    out[pid] = d[off + po + 8:off + po + 8 + n].decode('cp949', 'replace').split('\0')[0]
                elif t == 0x40:
                    ft = struct.unpack_from('<Q', d, off + po + 4)[0]
                    out[pid] = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft // 10)
    except (struct.error, OverflowError):
        return out
    return out


def iso(v):
    return v.strftime('%Y-%m-%dT%H:%M:%SZ') if isinstance(v, datetime.datetime) and v.year > 1601 else ''


def bin_name(k, ext):
    """(name in the manifest, media type, isEmbeded) of the k-th BIN_DATA item (k from 1); None for an unknown kind."""
    ext = ext.lower()
    if ext in IMAGE_TYPES:
        return f'image{k}', IMAGE_TYPES[ext], 1
    if ext == 'ole':
        return f'ole{k}', 'application/ole', 0
    if ext.isalnum():                       # any other embedded item: Hangul 2024 names it image<k> with media type image/<ext> (tmp, pcx)
        return f'image{k}', f'image/{ext}', 1
    return None


def bin_items(pk, head):
    """-> [(id in the manifest, file name in the package, media type, isEmbeded, bytes)] for every embedded item, in the
    order of BIN_DATA; k counts from 1 over all BIN_DATA records (as Hangul names them: image1.png, ole1.ole)."""
    out = []
    for k, b in enumerate(head.bins, 1):
        if b['kind'] == 'link':          # a linked image: a manifest item with the path and isEmbeded 0, no file (an image fill, 1 file)
            named = bin_name(k, b['ext'])
            if named is not None:
                out.append((named[0], b['path'], named[1], 0, None))
            continue
        ext = b['ext']                     # the case of the extension stays as it is (image1.BMP); the media type is lower case
        path = 'BinData/BIN%04X.%s' % (b['id'], b['ext'])
        stream = pk.streams.get(path) or next((v for n, v in pk.streams.items() if n.lower() == path.lower()), None)
        if stream is None:
            raise_missing(path)
        data = stream.data
        compress = b['attr'] >> 4 & 3
        if compress == 1 or (compress == 0 and pk.compressed):
            data = fmt.inflate(data)
        named = bin_name(k, ext)
        if named is None:
            raise Unsupported(f'BIN_DATA extension {ext!r}', f'bin item {k}')
        name, mt, emb = named
        if name.startswith('ole'):
            ext = 'ole'                    # an OLE item is always `.ole`; an image keeps the case of its extension
        out.append((name, f'BinData/{name}.{ext}', mt, emb, data))
    return out


def raise_missing(path):
    raise Unsupported('BinData stream missing', path)


def content_hpf(pk, sec, bins, n_sections):
    s = summary(pk)
    pkg = El('opf:package', {'version': '', 'unique-identifier': '', 'id': ''})
    def sp(v):                                     # Hangul writes xml:space="preserve" when the text has white space at an end (HW100)
        return {'xml:space': 'preserve'} if v and v != v.strip() else None
    meta = El('opf:metadata', None, El('opf:title', sp(s.get(2)), text=s.get(2) or None), El('opf:language', None, text='ko'))
    for name, val in (('creator', s.get(4, '')), ('subject', s.get(3, '')), ('description', s.get(6, '')),
                      ('lastsaveby', s.get(8, '')), ('CreatedDate', iso(s.get(12))), ('ModifiedDate', iso(s.get(13))),
                      ('date', s.get(20, '')), ('keyword', s.get(5, ''))):
        meta.add(El('opf:meta', {'name': name, 'content': 'text', **(sp(val) or {})}, text=val or None))
    man = El('opf:manifest', None, El('opf:item', {'id': 'header', 'href': 'Contents/header.xml', 'media-type': 'application/xml'}))
    for name, path, mt, emb, _ in bins:
        man.add(El('opf:item', {'id': name, 'href': path, 'media-type': mt, 'isEmbeded': emb}))
    master_at = {}
    for nm, sec_no in sec.masters:
        master_at.setdefault(sec_no, []).append(nm)
    for n in range(n_sections):
        for nm in master_at.get(n, []):
            man.add(El('opf:item', {'id': nm, 'href': f'Contents/{nm}.xml', 'media-type': 'application/xml'}))
        man.add(El('opf:item', {'id': f'section{n}', 'href': f'Contents/section{n}.xml', 'media-type': 'application/xml'}))
    man.add(El('opf:item', {'id': 'settings', 'href': 'settings.xml', 'media-type': 'application/xml'}))
    spine = El('opf:spine', None, El('opf:itemref', {'idref': 'header', 'linear': 'yes'}),
               *[El('opf:itemref', {'idref': f'section{n}', 'linear': 'yes'}) for n in range(n_sections)])
    pkg.add(meta, man, spine)
    return document(pkg)


def container_rdf(n):
    """The template's container.rdf names Contents/section0.xml; one more pair of descriptions per further section."""
    rdf = template('META-INF/container.rdf').decode('utf-8')
    one = rdf[rdf.index('<rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" '
                        'rdf:resource="Contents/section0.xml"/>'):rdf.index('<rdf:Description rdf:about=""><rdf:type')]
    more = ''.join(one.replace('section0', f'section{i}') for i in range(1, n))
    return rdf.replace(one, one + more).encode('utf-8')


# DocInfo record 0x1b (the print settings; a parameter set `1c02 0100 0000 0702 0080 0702 0700 0000`, 16 bytes, then items of id WORD,
# type WORD, value DWORD) -> the config items of settings.xml, in the order Hangul 2024 writes them. Measured one item at a time in
# Hangul 2024 (the measuring tool outside this repository, 7 + 1 items, values 1 and 7), rule HW104: id -> (name, boolean?)
PRINT_ITEMS = [(0x400A, 'PrintAutoFootNote', True), (0x400E, 'PrintAutoHeadNote', True), (0x4006, 'PrintMethod', False),
               (0x4010, 'OverlapSize', False), (0x401A, 'PrintCropMark', False), (0x401D, 'BinderHoleType', False),
               (0x401F, 'ZoomX', False), (0x4020, 'ZoomY', False)]


def print_info(d):
    """`config:config-item-set PrintInfo` of the record `d` (None when the document has no such record)."""
    if d is None or len(d) < 16:
        return None
    vals = {}
    for pos in range(16, len(d) - 7, 8):
        iid, typ, val = struct.unpack_from('<HHI', d, pos)
        vals[iid] = val
    if len(d) != 16 + 8 * len(vals) or set(vals) - {i for i, _, _ in PRINT_ITEMS}:
        raise Unsupported(f'print settings record with items {sorted(hex(i) for i in set(vals) - {i for i, _, _ in PRINT_ITEMS})} (DocInfo 0x1b)',
                          'DocInfo')
    st = El('config:config-item-set', {'name': 'PrintInfo'})
    for iid, name, boolean in PRINT_ITEMS:
        if iid in vals:
            st.add(El('config:config-item', {'name': name, 'type': 'boolean' if boolean else 'short'},
                      text=('true' if vals[iid] else 'false') if boolean else str(vals[iid])))
    return st


def settings_xml(head):
    props = head.by.get(fmt.T['DOCUMENT_PROPERTIES'], [b'\0' * 26])[0]
    lst, para, pos = struct.unpack_from('<III', props, 14) if len(props) >= 26 else (0, 0, 0)
    root = El('ha:HWPApplicationSetting', None, El('ha:CaretPosition', {'listIDRef': lst, 'paraIDRef': para, 'pos': pos}))
    info = print_info(head.by.get(fmt.T['DOC_DATA'], [None])[0])
    if info is not None:
        root.add(info)
    root.at = {'xmlns:ha': NS['ha'], 'xmlns:config': NS['config']}
    out = []
    root.xml(out)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + ''.join(out)).encode('utf-8')


def version_xml(pk):
    """version.xml of the template with the file version of the original (FileHeader) in major / minor / micro / buildNumber: the
    record layouts of the old forms come back with it (fromhwpx reads the version here, HW77). Hangul 2024 writes 5.1.1.0 for every
    file but opens the others (rule HW101)."""
    v = pk.version
    xml = template('version.xml').decode('utf-8')
    for name, val in (('major', v >> 24 & 255), ('minor', v >> 16 & 255), ('micro', v >> 8 & 255), ('buildNumber', v & 255)):
        xml = re.sub(r'(\b%s=")\d+"' % name, r'\g<1>%d"' % val, xml, count=1)
    return xml.encode('utf-8')


def write(pk, head, sec, parts, dst, notes):
    bins = bin_items(pk, head)
    from .safecopy import link_notes
    notes.extend(link_notes(head.bins))                                    # a network path is named
    n = len(pk.sections)
    with fmt.atomic(dst) as tmp, zipfile.ZipFile(tmp, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/hwp+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('version.xml', version_xml(pk), compress_type=zipfile.ZIP_STORED)
        z.writestr('Contents/header.xml', parts.pop('Contents/header.xml'), compress_type=zipfile.ZIP_DEFLATED)
        for name, path, _, _, data in bins:
            if data is not None:
                z.writestr(path, data, compress_type=zipfile.ZIP_DEFLATED)
        for name, xml in sec.masters_xml():
            z.writestr(f'Contents/{name}.xml', xml, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in parts.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        prv = pk.streams.get('PrvText')
        text = prv.data.decode('utf-16-le', 'replace') if prv else sec.preview_text()
        z.writestr('Preview/PrvText.txt', text.encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('settings.xml', settings_xml(head), compress_type=zipfile.ZIP_DEFLATED)
        img = pk.streams.get('PrvImage')
        if img is not None:
            if img.data[:4] == b'\x89PNG':
                z.writestr('Preview/PrvImage.png', img.data, compress_type=zipfile.ZIP_STORED)
            else:
                notes.append(f'NOTE PrvImage is {img.data[:3]!r}, not PNG: the preview picture is left out')
        z.writestr('META-INF/container.xml', template('META-INF/container.xml'), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('META-INF/container.rdf', container_rdf(n), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('Contents/content.hpf', content_hpf(pk, sec, bins, n), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('META-INF/manifest.xml', template('META-INF/manifest.xml'), compress_type=zipfile.ZIP_DEFLATED)
