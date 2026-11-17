"""Detect a protected HWPX (opened with a password, or saved as a distribution document). Detection only.

This module never decrypts and never implements any cipher. It looks at the package marks that Hangul leaves:
  META-INF/manifest.xml  lists a `file-entry` with an `encryption-data` child for every encrypted part
                         (an unprotected file has an empty manifest); the parts' bytes are then not XML.
A protected file cannot be read, checked or drawn without Hangul. The reader raises `ProtectedDocument` with a clear
message; `hd` prints it and exits with code 4; the preview draws a placeholder page instead of failing.
"""
from . import tmpdir
import zipfile
from xml.etree import ElementTree as ET

EXIT_CODE = 4


class ProtectedDocument(RuntimeError):
    pass


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def detect(path):
    """None for an unprotected HWPX (or a file that is not a zip), else {'kind': 'encrypted', 'parts': [...],
    'algorithm': name or ''} (the part paths come from the manifest; no key data is read)."""
    if not zipfile.is_zipfile(path):
        return None
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        parts, algo = [], ''
        if 'META-INF/manifest.xml' in names:
            try:
                root = ET.fromstring(z.read('META-INF/manifest.xml'))
            except ET.ParseError:
                root = None
            for entry in (root if root is not None else []):
                enc = [e for e in entry.iter() if _local(e.tag) == 'encryption-data']
                if enc:
                    attrs = [e.attrib for e in enc[0].iter() if _local(e.tag) == 'algorithm']
                    algo = algo or (attrs[0].get('algorithm-name', '') if attrs else '')
                    parts.append(next((v for k, v in entry.attrib.items() if _local(k) == 'full-path'), ''))
        if not parts and 'Contents/header.xml' in names:      # no manifest mark, but the header is not XML text
            head = z.read('Contents/header.xml')[:5].lstrip(b'\xef\xbb\xbf')
            if not head.startswith(b'<'):
                parts = ['Contents/header.xml']
    return {'kind': 'encrypted', 'parts': parts, 'algorithm': algo} if parts else None


def message(path, info):
    return (f'PROTECTED: {path} is a password-protected or distribution (배포용) document '
            f'({len(info["parts"])} encrypted part(s)). hwpx-docs does not decrypt. Open it in Hangul and save an '
            f'unprotected copy, then run the command again.')


def guard(path):
    """Raise ProtectedDocument if `path` is a protected HWPX."""
    info = detect(path)
    if info:
        raise ProtectedDocument(message(path, info))


def fake_protected(src, dst):
    """TEST HELPER: copy the HWPX `src` to `dst` with the package marks of a protected file (an `encryption-data` entry
    for each of the XML parts) and random bytes in place of those parts. No cipher is involved: this only gives the
    detector, the reader and the preview something that looks protected."""
    import os
    marks = ''.join('<odf:file-entry full-path="%s" media-type="application/xml" size="1"><odf:encryption-data '
                    'checksum-type="x" checksum="AAAA"><odf:algorithm algorithm-name="test-only" '
                    'initialisation-vector="AAAA"/></odf:encryption-data></odf:file-entry>' % n
                    for n in ('Contents/header.xml', 'Contents/section0.xml'))
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:'
                'manifest:1.0">%s</odf:manifest>' % marks)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == 'META-INF/manifest.xml':
                data = manifest.encode()
            elif info.filename in ('Contents/header.xml', 'Contents/section0.xml'):
                data = os.urandom(64)
            zout.writestr(info.filename, data)


def _selftest():
    import os
    from . import build, read
    d = tmpdir.mkdtemp('hwpx_docs_pr_')
    plain, prot = os.path.join(d, 'plain.hwpx'), os.path.join(d, 'prot.hwpx')
    build.write({'body': [{'p': '보호 시험'}]}, plain)
    assert detect(plain) is None and detect(os.path.join(d, 'none.txt')) is None
    fake_protected(plain, prot)
    info = detect(prot)
    assert info and info['kind'] == 'encrypted' and info['parts'] == ['Contents/header.xml', 'Contents/section0.xml'], info
    assert info['algorithm'] == 'test-only'
    try:
        read.read(prot, os.path.join(d, 'x.json'))
        raise AssertionError('a protected file must not be read')
    except ProtectedDocument as e:
        assert str(e).startswith('PROTECTED:') and 'does not decrypt' in str(e)
    assert read.read(plain, os.path.join(d, 'y.json'))['body'][0]['p'] == '보호 시험'
    print('protect self-check ok')
