"""Self-test of privacy.py (called by tests.py): synthetic parts that look like what Hangul writes on a PC."""
from ..core import tmpdir
import os
import zipfile

from . import privacy

FAKE = '홍길동'          # a made-up name: author slots hold any name, the PC user name is set from the environment


def run():
    d = tmpdir.mkdtemp('hwpx_docs_pv_')
    os.environ['HWPX_DOCS_PRIVATE'] = 'zzsecretzz'
    bs = chr(92)
    path_a = 'C:' + bs + 'Users' + bs + 'zzsecretzz' + bs + 'Desktop' + bs + 'book1.xls'
    ole = b'head' + path_a.encode('utf-16-le') + b'\x00\x00mid' + path_a.encode('latin-1') + b'\x00tail zzsecretzz'
    header = ('<hh:refList><hh:trackChangeAuthors itemCnt="1"><hh:trackChangeAuthor name="' + FAKE + '" mark="1" id="1"/>'
              '</hh:trackChangeAuthors></hh:refList>')
    section = ('<hp:p><hp:stringParam name="Command">MEMO/65535/1/2948717776/31290369/' + FAKE + '/;;</hp:stringParam>'
               '<hp:stringParam name="Author">' + FAKE + '</hp:stringParam><hp:t>note ' + path_a + ' zzsecretzz</hp:t></hp:p>')
    hpf = '<x name="creator" content="text">zzsecretzz</x><x name="lastsaveby" content="text">zzsecretzz</x>'
    f = os.path.join(d, 't.hwpx')
    with zipfile.ZipFile(f, 'w') as z:
        z.writestr('Contents/header.xml', header)
        z.writestr('Contents/section0.xml', section)
        z.writestr('Contents/content.hpf', hpf)
        z.writestr('BinData/ole1.ole', ole)
        z.writestr('Preview/PrvImage.png', b'png')
    before = privacy.scan(f)
    assert {n for n, _ in before} >= {'Contents/header.xml', 'Contents/section0.xml', 'Contents/content.hpf', 'BinData/ole1.ole'}, before
    assert privacy.scan(f, fix=True) == [], privacy.scan(f)
    with zipfile.ZipFile(f) as z:
        assert 'Preview/PrvImage.png' not in z.namelist()
        h, s, b = (z.read(n).decode('utf-8', 'replace') if n != 'BinData/ole1.ole' else z.read(n)
                   for n in ('Contents/header.xml', 'Contents/section0.xml', 'BinData/ole1.ole'))
    assert 'name="hwpx-docs"' in h and FAKE not in h + s and 'zzsecretzz' not in s, (h, s)
    assert '/hwpx-docs/' in s and 'note book1.xls hwpx-docs' in s, s                  # path -> file name only; the name -> hwpx-docs
    assert len(b) == len(ole) and b'zzsecretzz' not in b and 'zzsecretzz'.encode('utf-16-le') not in b, 'binary: same length, no name'
    assert b'book1.xls' in b and 'book1.xls'.encode('utf-16-le') in b and b'Desktop' not in b, b      # the file name stays
    # the repository scan reads PNG text chunks and finds names, generic paths and real e-mail addresses (not example.*)
    import zlib
    chunk = b'tEXt' + b'Author\x00zzsecretzz'
    png = b'\x89PNG\r\n\x1a\n' + len(chunk[4:]).to_bytes(4, 'big') + chunk + zlib.crc32(chunk).to_bytes(4, 'big')
    assert b'zzsecretzz' in privacy._png_text(png)
    at = chr(64).encode()                                     # not written as one address: the repository scan reads this file too
    hits = {lab for lab, _ in privacy._hits(b'by zzsecretzz at a' + at + b'b.kr, see c' + at + b'example.com and app' + b'data', ['zzsecretzz'])}
    assert hits == {'private', 'e-mail', 'generic'}, hits
    assert not privacy._hits(b'write to c@example.com', []), 'example.* addresses are fictional'
    print('SELFTEST privacy OK')
