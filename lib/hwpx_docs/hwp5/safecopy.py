"""A copy of a received document that is safe to open in Hangul (rule HW108).

Hangul runs the macros of a document ("Scripts") and fetches the pictures that a document links (a UNC path makes Windows send
the user's credentials to a remote server). Every tool that opens a document of someone else in Hangul opens THIS copy:

  copy(src, dst)    .hwp -> hwp_copy, .hwpx -> hwpx_copy (by the first bytes, not by the name); returns a report dict

  .hwp   every stream under a storage named SCRIPTS (any case, any depth) is blanked: `DefaultJScript` becomes the empty script
         Hangul itself writes (16 bytes), every other one keeps its length and becomes zero bytes; two entries with the same name
         (any case) are refused; every LINK picture (BIN_DATA type 0, absolute and relative path) keeps its record (the picture
         numbers stay) but its paths become `removed_link.<ext>`.
  .hwpx  every entry under `Scripts/` (any case) is left out, with its manifest item; two entries with the same name (any case)
         are refused; every linked picture (`opf:item isEmbeded="0"`) gets the href `removed_link.<ext>`.

The report: {'scripts': [names], 'links': n, 'changed': bool}. An unreadable or hostile file raises `UnsafeFile` (a ValueError) and
no copy is written. The source is only read."""
import io
import os
import re
import struct
import zipfile

from . import cfb, fmt

EMPTY_SCRIPT = bytes.fromhex('63604005ff8100006ebb6ed114000000')      # the script Hangul writes into every document without macros
REMOVED = 'removed_link'


class UnsafeFile(ValueError):
    """The file cannot be copied safely (duplicate names, damaged structure)."""


def _is_scripts(path):
    return 'SCRIPTS' in [p.upper() for p in path.split('/')[:-1]]


def _wstr(s):
    b = s.encode('utf-16-le')
    return struct.pack('<H', len(b) // 2) + b


def _ext(path):
    m = re.search(r'\.([A-Za-z0-9]{1,5})$', path or '')
    return m.group(1).lower() if m else 'png'


def scripts_in(pk):
    """Names of the script streams of a `fmt.Package` that hold a macro (any case, any depth; the empty script Hangul writes into
    every document does not count)."""
    out = []
    for path, s in pk.streams.items():
        if _is_scripts(path):
            last = path.split('/')[-1].upper()
            if (last == 'DEFAULTJSCRIPT' and s.data != EMPTY_SCRIPT) or (last not in ('DEFAULTJSCRIPT', 'JSCRIPTVERSION') and any(s.data)):
                out.append(path)
    return out


def remote_path(path):
    """True for a path that leaves this PC: a UNC path (`\\\\server\\share`, also `//server/share`), a mapped network drive, or a URL.
    Windows sends the user's credentials (NTLM) to such a server when a program opens the path."""
    p = (path or '').strip()
    if p.startswith(('\\\\', '//')) or re.match(r'^[A-Za-z][A-Za-z0-9+.-]{1,}:(//|\\\\)', p):
        return True
    m = re.match(r'^([A-Za-z]):[\\/]', p)
    if m and os.name == 'nt':
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(m.group(1) + ':\\') == 4          # DRIVE_REMOTE
        except Exception:
            return False
    return False


def remote_note(path):
    return (f'NOTE the linked picture "{path}" points to a network location: Windows may send your credentials to that server when a '
            f'program opens it. hwpx-docs never opens it (Hangul gets a copy without the link)')


def link_notes(bins):
    """NOTE lines for the linked pictures of `owpml.Head.bins` (dicts with kind / path) that point to a network location."""
    return [remote_note(b['path']) for b in bins if b.get('kind') == 'link' and remote_path(b.get('path'))]


def blank_scripts(pk):
    """Blank every script stream of a `fmt.Package` (not saved yet); returns the names changed."""
    names = []
    for path, s in pk.streams.items():
        if _is_scripts(path):
            data = EMPTY_SCRIPT if path.split('/')[-1].upper() == 'DEFAULTJSCRIPT' else bytes(len(s.data))
            if s.data != data:
                pk.put(path, data)
                names.append(path)
    return names


def hwp_copy(src, dst):
    """.hwp -> `dst` with the scripts blanked and the picture links removed (see the module text)."""
    try:
        pk = fmt.Package(src)
    except ValueError:
        raise
    except Exception as e:                                           # a damaged compound file
        raise UnsafeFile(f'{os.path.basename(src)} cannot be read as an HWP file ({type(e).__name__}); '
                         f'open it in Hangul and save it again') from None
    seen = {}
    for path, _ in pk.root.walk():
        k = path.upper()
        if k in seen:
            raise UnsafeFile(f'{os.path.basename(src)} has two entries with the name "{path}" (any case): refused')
        seen[k] = path
    report = {'scripts': blank_scripts(pk), 'links': 0, 'changed': False}
    recs, changed = [], False
    for tag, lvl, d in pk.records('DocInfo'):
        if tag == fmt.T['BIN_DATA'] and len(d) >= 2 and struct.unpack_from('<H', d, 0)[0] & 0xF == 0:
            path = ''
            try:
                n = struct.unpack_from('<H', d, 2)[0]
                path = d[4:4 + 2 * n].decode('utf-16-le', 'replace')
            except struct.error:
                pass
            name = f'{REMOVED}.{_ext(path)}'
            new = d[:2] + _wstr(name) + _wstr(name)
            if new != d:
                d, changed = new, True
                report['links'] += 1
        recs.append((tag, lvl, d))
    if changed:
        pk.put_records('DocInfo', recs)
    report['changed'] = bool(report['scripts'] or report['links'])
    pk.save(dst)
    return report


def _norm(name):
    """A package path as Windows / Hangul would resolve it: percent-decoded, backslashes as slashes, `.` and `..` folded, no leading
    slash. Returns the list of its parts (case kept). Two spellings of one place give one list."""
    import posixpath
    import urllib.parse
    s = urllib.parse.unquote(name or '').replace('\\', '/')
    s = posixpath.normpath(s) if s.strip('/') else ''
    return [p for p in s.split('/') if p not in ('', '.')]


def _is_scripts_path(name):
    return any(p.strip().upper() == 'SCRIPTS' for p in _norm(name))


def _outside(href):
    """True for a target that is not a place inside the package: nothing, a URL (`scheme:`, also a drive letter), a UNC or absolute
    path, or a path that climbs out with `..`."""
    import urllib.parse
    h = urllib.parse.unquote(href or '').strip().replace(chr(92), '/')
    return (not h) or h.startswith('/') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', h) is not None or '..' in _norm(h)


def hwpx_copy(src, dst):
    """.hwpx -> `dst` without any `scripts` part and without every manifest item that points outside the package (see the module text)."""
    try:
        z = zipfile.ZipFile(src)
        infos = z.infolist()
    except (zipfile.BadZipFile, OSError) as e:
        raise UnsafeFile(f'{os.path.basename(src)} cannot be read as an HWPX file ({type(e).__name__}); '
                         f'open it in Hangul and save it again') from None
    seen = set()
    for i in infos:
        k = '/'.join(p.upper() for p in _norm(i.filename)) or i.filename.upper()
        if k in seen:
            raise UnsafeFile(f'{os.path.basename(src)} has two entries with the name "{i.filename}" (any spelling, any case): refused')
        seen.add(k)
    report = {'scripts': [], 'links': 0, 'items': 0, 'changed': False}
    names = {'/'.join(p.upper() for p in _norm(i.filename)) for i in infos}
    drop = set()
    for i in infos:
        if _is_scripts_path(i.filename):
            report['scripts'].append(i.filename)
            drop.add(i.filename)
    manifests = {i.filename: _fix_manifest(z.read(i.filename), names, report, drop, infos)
                 for i in infos if i.filename.lower().endswith('.hpf') and i.filename not in drop}
    report['scripts'] = sorted(set(report['scripts']))
    tmp = dst + '.part'
    try:
        with zipfile.ZipFile(tmp, 'w') as out:
            for i in infos:
                if i.filename in drop or i.filename.endswith('/'):
                    continue
                data = manifests.get(i.filename)
                if data is None:
                    data = z.read(i.filename)
                zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                zi.compress_type = zipfile.ZIP_STORED if i.filename == 'mimetype' else zipfile.ZIP_DEFLATED
                out.writestr(zi, data)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    report['changed'] = bool(report['scripts'] or report['links'] or report['items'])
    return report


SCRIPT_TYPES = ('javascript', 'ecmascript', 'jscript', 'vbscript')


def _fix_manifest(data, names, report, drop, infos):
    """content.hpf read as XML (not with a pattern: any spelling of an item is one element): an item is kept only when its href is a
    place inside the package that exists and is not a `scripts` part and its media type is no script type; every other item goes
    (a linked picture, an external path, a UNC path, a URL, a script). The files of dropped script items are dropped too."""
    import xml.etree.ElementTree as ET
    ns = {}
    try:
        for _, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=('start-ns',)):
            ns.setdefault(prefix, uri)
        for prefix, uri in ns.items():
            try:
                ET.register_namespace(prefix, uri)
            except ValueError:
                pass
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise UnsafeFile(f'content.hpf is not well-formed XML ({e}); open the file in Hangul and save it again') from None
    by_norm = {'/'.join(p.upper() for p in _norm(i.filename)): i.filename for i in infos}
    removed = 0
    for parent in root.iter():
        for el in list(parent):
            if el.tag.rsplit('}', 1)[-1] != 'item':
                continue
            href = el.get('href', '')
            mt = (el.get('media-type') or '').lower()
            key = '/'.join(p.upper() for p in _norm(href))
            if any(t in mt for t in SCRIPT_TYPES) or _is_scripts_path(href):
                if key in by_norm:
                    drop.add(by_norm[key])
                    report['scripts'].append(by_norm[key])
            elif not _outside(href) and key in names:
                continue                                   # a part of the package: stays
            elif el.get('isEmbeded') == '0' or _outside(href):
                report['links'] += 1                       # a linked picture / a target outside the package
            else:
                report['items'] += 1                       # an item whose file is not in the package
            parent.remove(el)
            removed += 1
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def copy(src, dst):
    """Safe copy of an .hwp or an .hwpx (by the first bytes). Returns the report; see the module text."""
    with open(src, 'rb') as f:
        head = f.read(8)
    if head[:2] == b'PK':
        return hwpx_copy(src, dst)
    return hwp_copy(src, dst)


def selftest(d):
    """Hostile files built here: scripts in any case and depth, duplicate names, linked pictures (UNC) in .hwp and .hwpx."""
    import warnings
    from .owpml import short_record_text as owpml_text
    from .tests import build as build_hwp
    bs = chr(92)
    src = os.path.join(d, 'safe_src.hwp')
    build_hwp(src)
    pk = fmt.Package(src)
    root = cfb.read(open(src, 'rb').read())
    sc = cfb.Entry('sCrIpTs', cfb.STORAGE)                     # a storage in a strange case with a macro text
    sc.add(cfb.Entry('DefaultJScript', cfb.STREAM, b'EVIL macro text that Hangul would run'))
    sc.add(cfb.Entry('JScriptVersion', cfb.STREAM, bytes(range(1, 9))))
    root.add(sc)
    deep = cfb.Entry('Deep', cfb.STORAGE)                      # a second one, deeper
    deep.add(cfb.Entry('x', cfb.STORAGE)).add(cfb.Entry('SCRIPTS', cfb.STORAGE)).add(cfb.Entry('m', cfb.STREAM, b'second macro'))
    root.add(deep)
    recs = list(pk.records('DocInfo'))                         # a UNC link picture
    link = struct.pack('<H', 0) + _wstr(bs * 2 + 'evil.example' + bs + 'share' + bs + 'pic.png') + _wstr('..' + bs + 'pic.png')
    recs.insert(1, (fmt.T['BIN_DATA'], 1, link))
    body = fmt.unrecords(recs)
    cfb.streams(root)['DocInfo'].data = fmt.deflate(body) if pk.compressed else body
    hostile = os.path.join(d, 'safe_hostile.hwp')
    with open(hostile, 'wb') as f:
        f.write(cfb.build(root))
    out = os.path.join(d, 'safe_out.hwp')
    rep = copy(hostile, out)
    assert rep['changed'] and len(rep['scripts']) == 3 and rep['links'] == 1, rep
    q = fmt.Package(out)
    for p, s in q.streams.items():
        if _is_scripts(p):
            assert s.data == EMPTY_SCRIPT or not any(s.data), (p, s.data[:20])
    info = [x for t, l, x in q.records('DocInfo') if t == fmt.T['BIN_DATA']]
    assert info and all('evil'.encode('utf-16-le') not in x for x in info), 'the UNC path is still in DocInfo'
    assert 'removed_link'.encode('utf-16-le') in info[0]
    r2 = cfb.read(open(hostile, 'rb').read())                  # two storages with the same name in any case
    r2.add(cfb.Entry('SCRIPTS', cfb.STORAGE)).add(cfb.Entry('DEFAULTJSCRIPT', cfb.STREAM, b'x'))
    dupf = os.path.join(d, 'safe_dup.hwp')
    with open(dupf, 'wb') as f:
        f.write(cfb.build(r2))
    try:
        copy(dupf, os.path.join(d, 'safe_dup_out.hwp'))
    except UnsafeFile:
        pass
    else:
        raise AssertionError('two SCRIPTS storages were not refused')
    hx = os.path.join(d, 'safe_hostile.hwpx')                  # HWPX: every spelling of a script, a link, a URL
    hpf = ('<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"><opf:manifest>'
           '<opf:item id="a" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="s1" href="Scripts/macro.js" media-type="text/js"/>'
           "<opf:item" + chr(10) + " id='s2'" + chr(10) + " href='./scripts/second.js' media-type='text/plain'></opf:item>"
           '<opf:item id="s3" href="X/sCRIPTs/deep.js" media-type="text/plain"/>'
           '<opf:item id="s4" href="Scripts%2Fpercent.js" media-type="text/plain"/>'
           '<opf:item id="s5" href="Contents/..' + bs + 'Scripts' + bs + 'dots.js" media-type="text/plain"/>'
           '<opf:item id="j" href="Contents/code.txt" media-type="application/javascript"/>'
           '<opf:item id="u1" href="' + bs * 2 + 'evil' + bs + 'share' + bs + 'a.png" media-type="image/png" isEmbeded="0"/>'
           '<opf:item id="u2" href="http://evil.example/a.png" media-type="image/png"/>'
           '<opf:item id="u3" href="C:' + bs + 'Users' + bs + 'x' + bs + 'a.png" media-type="image/png" isEmbeded="0"/>'
           '<opf:item id="u4" href="file:///etc/passwd" media-type="image/png"/>'
           '<opf:item id="u5" href="BinData/missing.png" media-type="image/png"/>'
           '</opf:manifest></opf:package>')
    with zipfile.ZipFile(hx, 'w') as z:
        z.writestr('mimetype', 'application/hwp+zip')
        z.writestr('Contents/content.hpf', hpf)
        z.writestr('Contents/header.xml', '<h/>')
        z.writestr('Contents/code.txt', 'EVIL()')
        for n in ('sCrIpTs/macro.js', 'Scripts/headerScripts', 'scripts/second.js', 'X/sCRIPTs/deep.js', 'Scripts/percent.js'):
            z.writestr(n, 'EVIL')
        z.writestr('Contents/..' + bs + 'Scripts' + bs + 'dots.js', 'EVIL')
    ox = os.path.join(d, 'safe_out.hwpx')
    rep = copy(hx, ox)
    assert len(rep['scripts']) == 7 and rep['links'] == 4 and rep['items'] == 1, rep
    with zipfile.ZipFile(ox) as z:
        left = [n for n in z.namelist()]
        assert sorted(left) == ['Contents/content.hpf', 'Contents/header.xml', 'mimetype'], left        # code.txt (javascript type) went too
        out = z.read('Contents/content.hpf').decode()
        assert 'xmlns:opf=' in out and out.count('<opf:item ') == 1, out
        for bad in ('evil', 'Scripts', 'scripts', 'javascript', 'passwd', 'missing', 'Users'):
            assert bad not in out, (bad, out)
    hostile_xml = os.path.join(d, 'safe_badxml.hwpx')
    with zipfile.ZipFile(hostile_xml, 'w') as z:
        z.writestr('Contents/content.hpf', '<opf:package><opf:item')
    try:
        copy(hostile_xml, os.path.join(d, 'safe_badxml_out.hwpx'))
    except UnsafeFile:
        pass
    else:
        raise AssertionError('a manifest that is not XML was not refused')
    hd = os.path.join(d, 'safe_dup.hwpx')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        with zipfile.ZipFile(hd, 'w') as z:
            z.writestr('a/B.xml', '1')
            z.writestr('A/b.XML', '2')
    try:
        copy(hd, os.path.join(d, 'safe_dup_out.hwpx'))
    except UnsafeFile:
        pass
    else:
        raise AssertionError('two entries with the same name were not refused')
    try:                                                       # a short record says how short, and what to do next
        struct.unpack_from('<II', b'123456', 0)
    except struct.error as e:
        words = owpml_text(e)
    assert '6 of 8 bytes' in words and 'save it again' in words and 'unpack' not in words, words
    assert remote_path(bs * 2 + 'evil' + bs + 'share' + bs + 'a.png') and remote_path('//evil/share/a.png')    # a network path
    assert remote_path('http://x/y.png') and not remote_path('relative/b.png') and not remote_path('')
    from . import owpml
    heads = owpml.Head(fmt.Package(hostile))                    # the head of the hostile file: its UNC link is named in a NOTE
    notes = link_notes(heads.bins)
    assert any(n.startswith('NOTE the linked picture') and 'evil.example' in n for n in notes), notes
    from . import edit, render                                 # Hangul never starts by itself; the macro of an edit
    assert render.pick('auto') == 'preview'
    od = os.path.join(d, 'render_out')                          # an output folder is required; nothing is overwritten
    assert render.main(['render', src]) == 2
    assert render.main(['render', src, od, '--backend', 'preview']) == 0
    assert render.main(['render', src, od, '--backend', 'preview']) == 2
    keep, drop = os.path.join(d, 'safe_edit_keep.hwp'), os.path.join(d, 'safe_edit_drop.hwp')
    assert edit.main(['edit', hostile, keep]) == 0
    assert fmt.Package(keep).streams['sCrIpTs/DefaultJScript'].data.startswith(b'EVIL'), 'the original macro must stay'
    assert edit.main(['edit', hostile, drop, '--drop-scripts']) == 0
    assert fmt.Package(drop).streams['sCrIpTs/DefaultJScript'].data == EMPTY_SCRIPT
    print('SAFECOPY SELFTEST PASS')
