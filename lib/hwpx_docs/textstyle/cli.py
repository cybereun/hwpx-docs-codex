"""hd textstyle: samples and a dump of the style features of a file.

  hd textstyle samples <phase> <out_dir> [name ...]   Hangul COM sample maker (phase explore|fixtures|templates); see samples.py
  hd textstyle dump <in.hwpx>                         named styles and the paragraphs that use tab stops, as JSON lines
  hd textstyle scan [--fix] <in.hwpx> [...]            privacy scan of every zip entry (user name, e-mail, paths, author slots;
                                                      --fix rewrites the file in place: run it on a copy);
                                                      --fix first sets authors/paths to hwpx-docs and drops the preview (privacy.py)
  hd textstyle styles <in.hwpx> [...]                 the styles of each file as a Markdown table (what a 스타일마당 template applies)
"""
from ..core import tmpdir
import json
import os
import sys


def main(argv):
    if argv and argv[0] == 'samples':
        from . import samples
        return samples.main(argv[1:])
    if len(argv) >= 2 and argv[0] == 'dump':
        from ..core import read
        spec = read.read(argv[1], os.path.join(tmpdir.mkdtemp('hd_textstyle_'), 'dump.json'))
        print(json.dumps({'named_styles': spec.get('named_styles', {})}, ensure_ascii=False))
        for s in spec.get('sections') or [spec]:
            for b in s.get('body', []):
                if isinstance(b, dict) and ('tabs' in b or 'style' in b):
                    print(json.dumps({k: b[k] for k in ('style', 'tabs', 'p') if k in b}, ensure_ascii=False))
        return 0
    if argv[:2] == ['scan', '--repo']:
        from . import privacy
        root = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
        found = privacy.scan_repo(root)
        for rel, where, label, pat in found:
            print('FOUND', rel, '|', where, '|', label, '|', pat)
        print('SCAN REPO', 'clean (allowed: ' + '; '.join(f'{p} {lab}' for p, lab in privacy.ALLOWED) + '; example.* e-mail)' if not found
              else f'{len(found)} finding(s)')
        return 1 if found else 0
    if len(argv) >= 2 and argv[0] == 'scan':
        from . import privacy as samples
        fix = '--fix' in argv
        bad = 0
        for path in [a for a in argv[1:] if a != '--fix']:
            found = samples.scan(path, fix)
            bad += bool(found)
            print('SCAN', os.path.basename(path), 'FOUND ' + str(found) if found else 'clean')
        return 1 if bad else 0
    if len(argv) >= 2 and argv[0] == 'styles':
        return styles(argv[1:])
    print(__doc__)
    return 2


def styles(paths):
    import zipfile
    from xml.etree import ElementTree as ET
    from ..core import read
    for path in paths:
        head = zipfile.ZipFile(path).read('Contents/header.xml')
        refs = read.Refs(head)
        print(f'### {os.path.splitext(os.path.basename(path))[0]}')
        print()
        print('| id | style | type | font | pt | bold | colour | align | left | indent | before | after | line |')
        print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for st in ET.fromstring(head).iter('{%s}style' % read.NS['hh']):
            c, p = refs.char.get(st.get('charPrIDRef'), {}), refs.para.get(st.get('paraPrIDRef'), {})
            line = p.get('line', '')
            print('| ' + ' | '.join(str(x) for x in (
                st.get('id'), st.get('name'), st.get('type').lower(), c.get('font', ''), c.get('size', ''), 'B' if c.get('bold') else '',
                c.get('color', ''), p.get('align', ''), p.get('left', ''), p.get('indent', ''), p.get('before', ''), p.get('after', ''),
                line if not isinstance(line, dict) else line)) + ' |')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
