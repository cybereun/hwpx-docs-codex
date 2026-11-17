"""verify.py: the checks behind the numbers of lib/hwpx_docs/hwp5/coverage.md (the pairs of hwp2hwpx and the round trip).

  HWP5_PAIRS=<folder of <name>/from.hwp + <name>/from.hwpx>  python -I tools/verify.py tohwpx   [names] [--detail] [--why] [--only REGEX] [--keep DIR]
  HWP5_PAIRS=<same>                                          python -I tools/verify.py fromhwpx [names] [--show N] [--out DIR]
                                                             python -I tools/verify.py roundtrip <folder | file.hwp | @list.json> ... [--pairs] [--show N] [--limit N]

tohwpx     our HWPX (`hd hwp tohwpx`) against the HWPX that Hangul saved of the same .hwp: every XML part equal after the NORMAL list, BinData and PrvText
           equal bytes, core.read equal. Last line `TOHWPX PAIRS <n>/<total> EQUAL`.
fromhwpx   our .hwp (`hd hwp fromhwpx`) against the .hwp that Hangul saved of the same HWPX: records of DocInfo and every section byte for byte after
           the NORMALISE list below (every value an HWPX cannot hold, each with its reason). Last line `FROMHWPX PAIRS <n>/<total> RECORDS-EQUAL`.
roundtrip  .hwp -> tohwpx -> fromhwpx -> .hwp against the ORIGINAL records (three values that change by themselves are set aside: the caret, the
           paragraph instance id, the object instance id). Last line `ROUNDTRIP <n>/<total> RECORDS-EQUAL`.

The pair folder is third-party data (the hwp2hwpx test pairs, Apache-2.0); it is read, never executed or committed. The 153 government forms and the page
images of Hangul 2024 were measured with a tool that is not part of this repository.
"""
import collections
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import traceback
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'lib'))
from hwpx_docs.core import read as rd                      # noqa: E402
from hwpx_docs.core.protect import ProtectedDocument      # noqa: E402
from hwpx_docs.hwp5 import fmt, fromowpml, owpml          # noqa: E402
from hwpx_docs.hwp5 import owpmlmap as om                 # noqa: E402


# ======================================================================================================================
# tohwpx: our HWPX against the HWPX Hangul saved of the same document
# ======================================================================================================================


# NORMAL: (element local name, attribute) pairs that are instance numbers Hangul draws at random or counts up in its own
# way; they do not change the document. Everything else is compared as it is.
NORMAL = {('p', 'id'), ('secPr', 'id'), ('colPr', 'id'), ('tbl', 'id'), ('pic', 'id'), ('rect', 'id'), ('ellipse', 'id'),
          ('arc', 'id'), ('polygon', 'id'), ('curve', 'id'), ('line', 'id'), ('container', 'id'), ('ole', 'id'),
          ('equation', 'id'), ('connectLine', 'id'), ('textart', 'id'), ('btn', 'id'), ('checkBtn', 'id'),
          ('radioBtn', 'id'), ('comboBox', 'id'), ('edit', 'id'), ('chart', 'id'), ('video', 'id'),
          ('pic', 'instid'), ('tbl', 'instid'), ('ole', 'instid'), ('hiddenComment', 'id'), ('footNote', 'instId'), ('endNote', 'instId'),
          ('paraPr', 'textDir'),    # Hangul 2024 writes it (measured, HW100); the builds that saved the 41 pairs (2014-2018) do not
          ('head', 'version'),      # head@version: 1.4 or 1.5 by the Hangul build that saved the pair, not by the document
          ('itemref', 'linear'),    # content.hpf spine: only some Hangul builds write it
          ('CaretPosition', 'listIDRef'), ('CaretPosition', 'paraIDRef'), ('CaretPosition', 'pos')}   # where the caret was when saved


# Parts that only say which Hangul build saved the pair or are the same text for every document: present or not, not compared.
PACKAGE_ONLY = {'version.xml', 'META-INF/container.xml', 'META-INF/container.rdf', 'META-INF/manifest.xml'}


# DROP_ELEMENTS: elements Hangul for Mac (19 of the 41 pairs) leaves out and Hangul for Windows writes: font typeInfo
DROP_ELEMENTS = {'typeInfo'}


SKIP_PARTS ={'Preview/PrvImage.png', 'Preview/PrvImage.gif', 'Preview/PrvImage.bmp', 'mimetype'}


def local(tag):
    return tag.rsplit('}', 1)[-1]


def parse(data):
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return ET.fromstring(data.decode('utf-8', 'replace').encode('utf-8'))


PREFIX = {'http://www.hancom.co.kr/hwpml/2011/paragraph': 'hp', 'http://www.hancom.co.kr/hwpml/2011/head': 'hh',
          'http://www.hancom.co.kr/hwpml/2011/core': 'hc', 'http://www.hancom.co.kr/hwpml/2011/section': 'hs',
          'http://www.hancom.co.kr/hwpml/2011/app': 'ha', 'http://www.idpf.org/2007/opf/': 'opf',
          'http://www.hancom.co.kr/hwpml/2011/master-page': 'hm'}


def qname(tag):
    """'{uri}name' -> 'prefix:name' with Hangul's usual prefixes: the prefix of an element matters (hp:startPt != hc:startPt)."""
    if tag.startswith('{'):
        uri, name = tag[1:].split('}', 1)
        return f'{PREFIX.get(uri, uri)}:{name}'
    return tag


def norm(el):
    """-> (tag, {attr: value}, text, [children]) of an element; instance ids dropped (see NORMAL)."""
    lt = local(el.tag)
    tag = qname(el.tag)
    at = {qname(k) if k.startswith('{') and 'xml' not in k else local(k): v for k, v in el.attrib.items()
          if (lt, local(k)) not in NORMAL}
    text = (el.text or '').strip()
    if lt == 'meta' and at.get('name') in ('ModifiedDate', 'lastsaveby'):
        text = ''                         # who / when the pair's .hwpx was saved (the Hangul user, not the document's author)
    if lt == 'style' and at.get('type') == 'CHAR':
        at.pop('paraPrIDRef', None)       # Hangul 9.1.1 writes memory garbage here for a character style (7 other values seen)
    return tag, at, text, [norm(c) for c in el if local(c.tag) not in DROP_ELEMENTS]


def ascii_only(s):
    return ''.join(c for c in s if c < '\x80' and c != '�')


FAITHFUL = [0]          # attribute values that differ only by digits Hangul rounds away (HW107); counted, not a difference


def rounds_to(mine, theirs):
    """True when `mine` is a float with more than 6 decimals (the original value, kept) that Hangul's way of writing it (6 decimals,
    trailing zeros dropped) turns into `theirs`: "faithful to the original" (the allowed difference of rule HW107)."""
    try:
        m = float(mine)
        float(theirs)
    except (TypeError, ValueError):
        return False
    if '.' not in mine or len(mine.split('.')[1].split('e')[0]) <= 6:
        return False
    s = ('%.6f' % m).rstrip('0').rstrip('.')
    return (s if s not in ('-0', '') else '0') == theirs


def diff(a, b, path='', out=None, limit=400):
    """Differences of two normalised trees: (path, reason). Children are paired by position."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    here = f'{path}/{a[0]}'
    if a[0] != b[0]:
        out.append((here, f'tag {a[0]} != {b[0]}'))
        return out
    for k in sorted(set(a[1]) | set(b[1])):
        if a[1].get(k) != b[1].get(k):
            if rounds_to(a[1].get(k), b[1].get(k)):
                FAITHFUL[0] += 1
                continue
            out.append((here, f'@{k}: mine {a[1].get(k)!r} != theirs {b[1].get(k)!r}'))
    ta, tb = a[2], b[2]
    if '�' in tb or any(('�' in v) for v in b[1].values()):     # Hangul 9 wrote cp949 bytes into UTF-8 here:
        ta, tb = ascii_only(ta), ascii_only(tb)                           # only the ASCII part can be compared
    if ta != tb:
        out.append((here, f'text: mine {a[2][:60]!r} != theirs {b[2][:60]!r}'))
    ca, cb = a[3], b[3]
    for i in range(max(len(ca), len(cb))):
        if i >= len(ca):
            out.append((f'{here}[{i}]', f'missing in mine: <{cb[i][0]}>'))
        elif i >= len(cb):
            out.append((f'{here}[{i}]', f'extra in mine: <{ca[i][0]}>'))
        else:
            diff(ca[i], cb[i], f'{here}[{i}]', out, limit)
    return out


def package(path):
    z = zipfile.ZipFile(path)
    return {i.filename: z.read(i.filename) for i in z.infolist() if not i.filename.endswith('/')}


def compare_packages(mine, theirs):
    """-> list of (part, path, reason)."""
    res = []
    for name in sorted(set(mine) | set(theirs)):
        if name in SKIP_PARTS or (name in PACKAGE_ONLY and name in mine):
            continue
        if name.startswith('Preview/PrvImage') and name in mine and name in theirs:
            continue
        if name not in mine:
            res.append((name, '', 'part missing in mine'))
        elif name not in theirs:
            res.append((name, '', 'part extra in mine'))
        elif name.endswith(('.xml', '.hpf')):
            for p, why in diff(norm(parse(mine[name])), norm(parse(theirs[name]))):
                res.append((name, p, why))
        elif mine[name] != theirs[name]:
            if name.endswith('.ole') and len(mine[name]) == len(theirs[name]) and \
                    sum(x != y for x, y in zip(mine[name], theirs[name])) <= 8:
                continue                  # Hangul rewrites a time stamp (4 bytes) in the OLE file's directory when it saves
            res.append((name, '', f'bytes differ ({len(mine[name])} vs {len(theirs[name])})'))
    return res


def run_pair(root, name, keep=None):
    """One pair; the files of the run live in a temp folder that is removed afterwards (kept with --keep DIR)."""
    tmp = keep or tempfile.mkdtemp(prefix='pair_')
    try:
        return _run_pair(root, name, tmp)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def _run_pair(root, name, tmp):
    hwp, ref = os.path.join(root, name, 'from.hwp'), os.path.join(root, name, 'from.hwpx')
    out = os.path.join(tmp, name + '.hwpx')
    try:
        owpml.convert(hwp, out)
    except owpml.Unsupported as e:
        return 'UNSUPPORTED', [(str(e), '', '')]
    except Exception as e:                          # a crash is a result too, with its place
        tb = traceback.extract_tb(e.__traceback__)[-1]
        return 'CRASH', [(f'{type(e).__name__}: {e}', f'{os.path.basename(tb.filename)}:{tb.lineno}', '')]
    diffs = compare_packages(package(out), package(ref))
    try:
        for sub in ('mine', 'ref'):
            os.makedirs(os.path.join(tmp, name + '_' + sub), exist_ok=True)     # each reads its pictures / OLE next to its json
        a = rd.read(out, os.path.join(tmp, name + '_mine', 'spec.json'))
        b = rd.read(ref, os.path.join(tmp, name + '_ref', 'spec.json'))
        dump = lambda x: re.sub(r'instid=\\"\d+\\"', 'instid=\\"0\\"', json.dumps(x, sort_keys=True, ensure_ascii=False))
        same = dump(a) == dump(b)         # instid: the OLE record keeps none (NORMAL)
    except Exception as e:
        same = f'read failed: {type(e).__name__}: {str(e)[:80]}'
    return ('EQUAL' if not diffs and same is True else 'DIFF'), diffs, same


def cmd_tohwpx(argv):
    root = os.environ.get('HWP5_PAIRS')
    if not root or not os.path.isdir(root):
        print('set HWP5_PAIRS to the folder with <name>/from.hwp and <name>/from.hwpx')
        return 2
    detail = '--detail' in argv
    only = None
    if '--only' in argv:                    # --only REGEX: compare one feature (Hangul 2024 pairs differ elsewhere: textDir ...)
        only = argv[argv.index('--only') + 1]
    keep = None
    if '--keep' in argv:
        keep = argv[argv.index('--keep') + 1]
        os.makedirs(keep, exist_ok=True)
    names = [a for a in argv if not a.startswith('--') and a != keep and a != only]
    allnames = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    total = [d for d in allnames if os.path.exists(os.path.join(root, d, 'from.hwp'))
             and os.path.exists(os.path.join(root, d, 'from.hwpx'))]
    left_out = [d for d in allnames if d not in total]
    ok = 0
    why_count = {}
    for d in names or total:
        r = run_pair(root, d, keep)
        state, diffs = r[0], r[1]
        if only and state in ('EQUAL', 'DIFF'):         # evidence for one feature: only the differences at matching places count
            diffs = [x for x in diffs if re.search(only, f'{x[0]} {x[1]}')]
            state = 'EQUAL' if not diffs else 'DIFF'
            r = (state, diffs, True)
        ok += state == 'EQUAL'
        for part, p, why in diffs:
            key = (part.split('/')[-1], re.sub(r'\[\d+\]', '', p), re.sub(r"'[^']*'", "'..'", why))
            why_count.setdefault(key, [0, d])[0] += 1
        kinds = {}
        for part, p, why in diffs:
            k = re.sub(r'\[\d+\]', '', p.rsplit('/', 1)[-1]) or part
            kinds[k] = kinds.get(k, 0) + 1
        top = ', '.join(f'{k} x{n}' for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:5])
        spec = '' if state in ('UNSUPPORTED', 'CRASH') else f' spec={"equal" if r[2] is True else r[2]}'
        print(f'{d:28} {state:11} xml-diffs={len(diffs)}{spec} {top}')
        if detail and state != 'EQUAL':
            for part, p, why in diffs[:60]:
                print(f'    {part} {p} :: {why}')
    for d in left_out:
        have = [f for f in ('from.hwp', 'from.hwpx') if os.path.exists(os.path.join(root, d, f))]
        print(f'{d:28} LEFT OUT (not a pair: only {", ".join(have) or "no from file"})')
    if '--why' in argv:
        print('--- differences by place and reason (count, first pair)')
        for (part, p, why), (n, first) in sorted(why_count.items(), key=lambda kv: -kv[1][0])[:40]:
            print(f'{n:5} {first:22} {part} {p.replace("/head", "").replace("/sec", "")[-90:]} :: {why[:110]}')
    print(f'(faithful to the original, not counted as a difference: {FAITHFUL[0]} attribute values with more than 6 decimals, HW107)')
    print(f'TOHWPX PAIRS {ok}/{len(total) if not names else len(names)} EQUAL')
    return 0


# ======================================================================================================================
# fromhwpx: our .hwp against the .hwp Hangul saved of the same HWPX
# ======================================================================================================================


NORMALISE = [
    'DocInfo FACE_NAME: the "default font name" (attribute bit 5) is not in the HWPX; dropped from the saved record',
    'DocInfo track change record (tag 0x20): only the flags (first 4 bytes) come from the HWPX; the rest is memory '
    'Hangul writes unchanged or at random',
    'BodyText `form` CTRL_HEADER: the z order and the instance id (the HWPX form elements have neither)',
    'BodyText `gso ` CTRL_HEADER: the 8 bytes of the outer margin; the .hwp of rect_no_fill holds values there that '
    'hwp2hwpx does not write to the HWPX (it shows 0)',
    'BodyText SHAPE_COMPONENT: the numbers of the matrices are compared rounded to 3 decimals (the HWPX '
    'writes them with 6 digits)',
    'BodyText caption LIST_HEADER (30 bytes): the caption attribute bits above bit 2 (side and full-size bits are kept); the '
    '.hwp holds bits there that the HWPX does not have',
    'DocInfo FORBIDDEN_CHAR record (tag 0x5e) level: table_numbering_bits has it at level 0, every other pair at level 1',
    'BodyText PAGE_BORDER_FILL: the attribute bits above bit 4 (the .hwp of `field` has bits 28-29 set; the HWPX has no '
    'attribute for them)',
    'BinData of an OLE object (BIN0001.OLE): up to 8 bytes may differ (a time stamp inside the OLE file: 4 bytes in the ole pair)',
    'DocInfo PARA_SHAPE: bit 3 of the second attribute word: Hangul 2024 sets it when it saves a HWPX as .hwp (all 4542 records of '
    '153 forms) and the originals have it clear (HW81)',
    'BodyText `tbl ` / `gso ` CTRL_HEADER: bit 28 of the attribute and 2 more bytes at the end: Hangul 2024 writes them when it saves a '
    'HWPX as .hwp (311 records of 153 forms), the originals do not have them (HW81)',
    'BodyText SHAPE_COMPONENT: bit 16 of the flag word at byte 36: Hangul 2024 sets it when it saves a HWPX as .hwp (12 shapes of 153 '
    'forms), the originals have it clear (HW81)',
    'DocInfo layout compatibility record (tag 0x1F): the bits that have no element name in the HWPX (owpmlmap.COMPAT_FLAGS entries None: bits 4, '
    '7, 10 of word 0 ...) cannot come from a HWPX; compat_msword has bit 7 set (HW85)',
    'DocInfo DOCUMENT_PROPERTIES: the caret (list, paragraph, position: the last 12 bytes); hwp2hwpx writes caret values '
    'in settings.xml that differ from the .hwp in 3 of 41 pairs (여러섹션, footnote_endnote, ...); the caret is cosmetic',
]


# ---- the comparison of the pair check ---------------------------------------------------------------------------------
def _face_without_default(d):
    attr = d[0]
    n = struct.unpack_from('<H', d, 1)[0]
    i = 3 + 2 * n
    if attr & 0x80:                                        # an alternative font: type and name
        i += 1 + 2 + 2 * struct.unpack_from('<H', d, i + 1)[0]
    if attr & 0x40:
        i += 10
    return bytes([attr & ~0x20]) + d[1:i]


def normalise(mine, saved, stream):
    """Both record lists with the NORMALISE fields made equal; returns (mine, saved)."""
    if stream != 'DocInfo':
        def fix_body(rs):
            out = []
            for tag, lvl, d in rs:
                if tag == fmt.T['CTRL_HEADER'] and d[:4] == b'mrof' and len(d) >= 40:     # `form`: z order and instance id
                    d = d[:24] + bytes(4) + d[28:36] + bytes(4) + d[40:]
                elif tag == fmt.T['CTRL_HEADER'] and d[:4] == b' osg' and len(d) >= 36:
                    d = d[:28] + bytes(8) + d[36:]                 # outer margin (HW20): see NORMALISE
                if tag == fmt.T['CTRL_HEADER'] and d[:4] in (b' lbt', b' osg') and len(d) >= 46:     # bit 28 and 2 more bytes: see NORMALISE
                    d = d[:4] + struct.pack('<I', struct.unpack_from('<I', d, 4)[0] & ~(1 << 28)) + d[8:]
                    if len(d) == 46 + 2 * struct.unpack_from('<H', d, 44)[0] + 2:
                        d = d[:-2]
                elif tag == fmt.T['PAGE_BORDER_FILL']:                 # bits 28-29 of the attribute: see NORMALISE
                    d = struct.pack('<I', struct.unpack_from('<I', d)[0] & 0x1F) + d[4:]
                elif tag == fmt.T['LIST_HEADER'] and len(d) == 30:       # a caption: bits above the side and size bits
                    d = d[:8] + struct.pack('<I', struct.unpack_from('<I', d, 8)[0] & 7) + d[12:]
                elif tag == fmt.T['SHAPE_COMPONENT'] and len(d) >= 52 + 8 * 18:
                    sh_ = 0 if d[:4] == d[4:8] else -4                # a grouped child writes its kind once
                    d = d[:36 + sh_] + struct.pack('<I', struct.unpack_from('<I', d, 36 + sh_)[0] & ~(1 << 16)) + d[40 + sh_:]   # bit 16: see NORMALISE
                    k = 6 * (1 + 2 * struct.unpack_from('<H', d, 50 + sh_)[0])      # the matrices: the HWPX keeps 6 decimals
                    m = struct.unpack_from('<%dd' % k, d, 52 + sh_)
                    d = d[:52 + sh_] + struct.pack('<%dd' % k, *[round(x, 3) + 0.0 for x in m]) + d[52 + sh_ + 8 * k:]
                out.append((tag, lvl, d))
            return out
        return fix_body(mine), fix_body(saved)

    def fix(rs):
        out = []
        for tag, lvl, d in rs:
            if tag == fmt.T['FACE_NAME']:
                d = _face_without_default(d)
            elif tag == 0x20:
                d = d[:4]
            elif tag == fmt.T['DOCUMENT_PROPERTIES']:
                d = d[:14]
            elif tag == 0x1F and len(d) == 20:                                  # bits without a name: see NORMALISE
                ws = list(struct.unpack('<5I', d))
                for w, names in enumerate(om.COMPAT_FLAGS):
                    for bit, name in enumerate(names):
                        if not name:
                            ws[w] &= ~(1 << bit)
                d = struct.pack('<5I', *ws)
            elif tag == fmt.T['PARA_SHAPE'] and len(d) >= 46:                     # bit 3 of the second attribute word: see NORMALISE
                d = d[:42] + struct.pack('<I', struct.unpack_from('<I', d, 42)[0] & ~8) + d[46:]
            elif tag == 0x5E:
                lvl = 1
            out.append((tag, lvl, d))
        return out
    return fix(mine), fix(saved)


T = {v: k for k, v in fmt.T.items()}


def norm_records(path_hwp, stream):
    pk = fmt.Package(path_hwp)
    return [tuple(r) for r in pk.records(stream)], pk


def describe(r):
    return f'{T.get(r[0], hex(r[0]))} L{r[1]} {len(r[2])}B {r[2][:48].hex()}'


def diff_streams(a, b, name, show):
    """First differences of two record lists; returns a short text or ''."""
    out = []
    n = min(len(a), len(b))
    k = 0
    while k < n and a[k] == b[k]:
        k += 1
    if k == n and len(a) == len(b):
        return ''
    out.append(f'{name}: record {k} of {len(a)}/{len(b)} (mine / saved)')
    for j in range(k, min(k + show, n)):
        if a[j] != b[j]:
            out.append(f'   mine  {describe(a[j])}')
            out.append(f'   saved {describe(b[j])}')
            x, y = a[j][2], b[j][2]
            at = len(os.path.commonprefix([x, y]))
            out.append(f'   first byte difference at {at}: mine {x[at:at + 12].hex()} saved {y[at:at + 12].hex()}')
    if len(a) != len(b) and k == n:
        longer, who = (a, 'mine') if len(a) > len(b) else (b, 'saved')
        out.append(f'   {who} has more: {describe(longer[k])}')
    return '\n'.join(out)


def cmd_fromhwpx(argv):
    root = os.environ.get('HWP5_PAIRS')
    if not root:
        print('set HWP5_PAIRS to the folder of <name>/from.hwp + from.hwpx pairs')
        return 2
    show, outdir, names = 1, None, []
    it = iter(argv)
    for a in it:
        if a == '--show':
            show = int(next(it))
        elif a == '--out':
            outdir = next(it)
        else:
            names.append(a)
    names = names or sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, 'from.hwp'))
                            and os.path.isfile(os.path.join(root, d, 'from.hwpx')))
    temp_out = outdir is None                                     # no --out: a temporary folder of its own, removed at the end (never the current folder)
    outdir = outdir or tempfile.mkdtemp(prefix='fromhwpx_pairs_')
    os.makedirs(outdir, exist_ok=True)
    equal = 0
    for name in names:
        src, ref = os.path.join(root, name, 'from.hwpx'), os.path.join(root, name, 'from.hwp')
        dst = os.path.join(outdir, name + '.hwp')
        t0 = time.time()
        try:
            fromowpml.convert(src, dst)
        except fromowpml.Unsupported as e:
            print(f'STOP  {name}: {e}')
            continue
        except Exception as e:                                       # a bug of the converter: show it
            print(f'ERROR {name}: {type(e).__name__}: {e}')
            traceback.print_exc(limit=3)
            continue
        text = []
        for stream in ['DocInfo'] + sorted(p for p in fmt.Package(ref).streams if p.startswith('BodyText/')):
            try:
                mine, _ = norm_records(dst, stream)
            except KeyError:
                text.append(f'{stream}: missing in mine')
                continue
            saved, _ = norm_records(ref, stream)
            mine, saved = normalise(mine, saved, stream)
            d = diff_streams(mine, saved, stream, show)
            if d:
                text.append(d)
        bm, bs = fmt.Package(dst), fmt.Package(ref)                  # BinData: the same files (compare after inflating)
        for path in sorted(p for p in bs.streams if p.startswith('BinData/')):
            if path not in bm.streams:
                text.append(f'{path}: missing in mine')
            else:
                x, y = fmt.inflate(bm.streams[path].data), fmt.inflate(bs.streams[path].data)
                few = len(x) == len(y) and path.endswith('.OLE') and sum(1 for i, j in zip(x, y) if i != j) <= 8
                if x != y and not few:        # an OLE file may differ in a time stamp (4 bytes in the ole pair): see NORMALISE
                    text.append(f'{path}: bytes differ after inflating')
        if not text:
            equal += 1
            print(f'EQUAL {name} ({time.time() - t0:.1f}s)')
        else:
            lines = [x for one in text for x in one.splitlines()]
            print(f'DIFF  {name}: ' + lines[0])
            for t in lines[1:]:                          # every stream that differs, not only the first
                print(t)
    print(f'FROMHWPX PAIRS {equal}/{len(names)} RECORDS-EQUAL')
    if temp_out:
        shutil.rmtree(outdir, ignore_errors=True)
    return 0


# ======================================================================================================================
# roundtrip: .hwp -> tohwpx -> fromhwpx -> .hwp against the original records
# ======================================================================================================================


TAGNAME = {v: k for k, v in fmt.T.items()}


def normalised(path):
    """{stream: [(tag, level, data)]} with N1-N3 applied; BinData as {name: bytes}."""
    pk = fmt.Package(path)
    out = {}
    for stream in ['DocInfo'] + list(pk.sections):
        recs = []
        for tag, lvl, d in pk.records(stream):
            if tag == fmt.T['DOCUMENT_PROPERTIES'] and stream == 'DocInfo':
                d = d[:14]
            elif tag == fmt.T['PARA_HEADER'] and len(d) >= 22:
                d = d[:18] + bytes(4) + d[22:]
            elif tag == fmt.T['CTRL_HEADER'] and d[:4] in (b' lbt', b' osg') and len(d) >= 40:
                d = d[:36] + bytes(4) + d[40:]
            recs.append((tag, lvl, d))
        out[stream] = recs
    bins = {}
    for name, s in pk.streams.items():
        if name.startswith('BinData/'):
            try:
                bins[name.lower()] = fmt.inflate(s.data) if pk.compressed else s.data
            except Exception:
                bins[name.lower()] = s.data
    return out, bins


def compare(a, b, show):
    """Returns (lines, Counter of tags that differ)."""
    (ra, ba), (rb, bb) = a, b
    lines, tags = [], collections.Counter()
    for stream in sorted(set(ra) | set(rb)):
        x, y = ra.get(stream), rb.get(stream)
        if x is None or y is None:
            lines.append(f'{stream}: only in {"original" if y is None else "round trip"}')
            continue
        if x == y:
            continue
        k = 0
        while k < min(len(x), len(y)) and x[k] == y[k]:
            k += 1
        cx = collections.Counter((t, d) for t, l, d in x)
        cy = collections.Counter((t, d) for t, l, d in y)
        lost = cx - cy                                        # in the original, not found in the round trip
        for (t, d), n in lost.items():
            tags[f'{stream.split("/")[0]}:{TAGNAME.get(t, hex(t))}'] += n
        for (t, d), n in (cy - cx).items():
            tags[f'{stream.split("/")[0]}:{TAGNAME.get(t, hex(t))} (new)'] += n
        first = f'{stream}: record {k} of {len(x)}/{len(y)}'
        if k < min(len(x), len(y)):
            first += f' {TAGNAME.get(x[k][0], hex(x[k][0]))} {len(x[k][2])}B/{len(y[k][2])}B'
        elif len(x) != len(y):
            first += ' (one list is longer)'
        lines.append(first)
        for j in range(k, min(k + show, min(len(x), len(y)))):
            if x[j] != y[j]:
                p, q = x[j][2], y[j][2]
                at = len(os.path.commonprefix([p, q]))
                lines.append(f'    {TAGNAME.get(x[j][0], hex(x[j][0]))}: byte {at}: original {p[at:at + 10].hex()} round trip {q[at:at + 10].hex()}')
    for name in sorted(set(ba) | set(bb)):
        if ba.get(name) != bb.get(name):
            lines.append(f'{name}: {"missing" if name not in bb else "extra" if name not in ba else "bytes differ"}')
            tags['BinData'] += 1
    return lines, tags


def files_of(arg, pairs):
    if arg.startswith('@'):
        with open(arg[1:], encoding='utf-8') as f:
            return json.load(f)
    if os.path.isfile(arg):
        return [arg]
    out = []
    for root, _, names in os.walk(arg):
        for n in sorted(names):
            if (pairs and n == 'from.hwp') or (not pairs and n.lower().endswith('.hwp')):
                out.append(os.path.join(root, n))
    return sorted(out)


def one(src, tmp, show):
    h, r = os.path.join(tmp, 'a.hwpx'), os.path.join(tmp, 'a.hwp')
    try:
        owpml.convert(src, h)
    except owpml.Unsupported as e:
        return 'UNSUPPORTED tohwpx ' + str(e)[:150], collections.Counter()
    except (fmt.Hwp5Error, ProtectedDocument) as e:                # a document the converter refuses on purpose (distribution / password)
        return 'SKIP not a plain .hwp: ' + str(e)[:100], collections.Counter()
    try:
        fromowpml.convert(h, r)
    except fromowpml.Unsupported as e:
        return 'UNSUPPORTED fromhwpx ' + str(e)[:150], collections.Counter()
    lines, tags = compare(normalised(src), normalised(r), show)
    return ('EQUAL' if not lines else 'DIFF ' + '; '.join(lines[:1 + show])[:400]), tags


def cmd_roundtrip(argv):
    args = [a for a in argv if not a.startswith('--')]
    pairs = '--pairs' in argv
    show = int(argv[argv.index('--show') + 1]) if '--show' in argv else 1
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else 0
    if '--show' in argv:
        args.remove(argv[argv.index('--show') + 1])
    if '--limit' in argv:
        args.remove(argv[argv.index('--limit') + 1])
    files = [f for a in args for f in files_of(a, pairs)]
    if limit:
        files = files[:limit]
    if not files:
        print(__doc__)
        return 2
    equal = skip = 0
    all_tags = collections.Counter()
    with tempfile.TemporaryDirectory(prefix='rt_') as tmp:
        for src in files:
            name = os.path.relpath(src, os.path.commonpath([os.path.dirname(f) for f in files]) if len(files) > 1 else os.path.dirname(src))
            try:
                res, tags = one(src, tmp, show)
            except Exception as e:                      # a crash is a bug: listed, never hidden
                res, tags = 'CRASH ' + type(e).__name__ + ' ' + str(e)[:150] + ' @' + traceback.format_exc().splitlines()[-3].strip()[:80], collections.Counter()
            skip += res.startswith('SKIP')
            equal += res == 'EQUAL'
            all_tags.update(tags)
            print(f'{name[:60]:60} {res}', flush=True)
    print(f'ROUNDTRIP {equal}/{len(files)} RECORDS-EQUAL (not a plain .hwp: {skip})')
    if all_tags:
        print('differing records by tag (original records not found in the round trip / new ones):')
        for k, n in all_tags.most_common(25):
            print(f'  {n:6} {k}')
    return 0 if equal == len(files) else 1


# ======================================================================================================================
def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8')          # pair names are Korean
    except (AttributeError, ValueError):
        pass
    cmds = {'tohwpx': cmd_tohwpx, 'fromhwpx': cmd_fromhwpx, 'roundtrip': cmd_roundtrip}
    if not argv or argv[0] not in cmds:
        print(__doc__)
        return 2
    return cmds[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
