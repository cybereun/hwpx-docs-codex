"""Pretty-print and diff the XML parts of HWPX files (standard library only).

  python hwpx_diff.py dump <a.hwpx> <out_dir>           unzip and pretty-print every XML part
  python hwpx_diff.py diff <a.hwpx> <b.hwpx> [out.txt]  unified diff of header.xml + section*.xml
  python hwpx_diff.py sdiff <a.hwpx> <b.hwpx>           section diff with style ids replaced by content
                                                        hashes (compare files made by different tools)

The diff ignores data that Hangul writes again on each save: paragraph ids (hp:p id),
the layout cache (hp:linesegarray) and dates in content.hpf.
"""
import difflib
import os
import re
import sys
import zipfile
from xml.dom import minidom

VOLATILE = [
    (re.compile(r'<hp:linesegarray>.*?</hp:linesegarray>', re.S), ''),
    (re.compile(r'(<hp:p id=")\d+(")'), r'\g<1>*\2'),
    (re.compile(r'(<hp:(?:tbl|pic|rect|ellipse|line|container|ole|equation|textart|compose|footNote|endNote) id=")\d+(")'), r'\g<1>*\2'),
    (re.compile(r'(instid=")\d+(")'), r'\g<1>*\2'),
    (re.compile(r'(zOrder=")\d+(")'), r'\g<1>*\2'),
]


def pretty(data, clean=True):
    text = data.decode('utf-8') if isinstance(data, bytes) else data
    if clean:
        for rx, rep in VOLATILE:
            text = rx.sub(rep, text)
    try:
        out = minidom.parseString(text.encode('utf-8')).toprettyxml(indent=' ')
    except Exception:
        out = text.replace('><', '>\n<')
    return [line for line in out.splitlines() if line.strip()]


def parts(path):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.startswith('Contents/') and n.endswith('.xml')]
        return {n: z.read(n) for n in sorted(names)}


def safe_entry_path(out_dir, name):
    """Where a ZIP entry may be written under `out_dir`, or None: no absolute name, drive, `..`, backslash or empty part (a
    received file can carry such names to write outside the folder)."""
    parts = name.split('/')
    if not name or name.endswith('/') or '\\' in name or any(p in ('', '.', '..') or ':' in p for p in parts):
        return None
    root = os.path.realpath(out_dir)
    dst = os.path.realpath(os.path.join(root, *parts))
    return dst if dst.startswith(root + os.sep) else None


def dump(path, out_dir):
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            dst = safe_entry_path(out_dir, n)
            if dst is None:
                if not n.endswith('/'):
                    print('SKIP unsafe entry name', repr(n))
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data = z.read(n)
            if n.endswith(('.xml', '.hpf', '.rdf')):
                open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(pretty(data, clean=False)) + '\n')
            else:
                open(dst, 'wb').write(data)


def semantic_lines(path):
    """Section XML with every charPr/paraPr/borderFill id replaced by a hash of its content
    (font ids replaced by face names), so two files made by different tools can be compared."""
    import hashlib
    with zipfile.ZipFile(path) as z:
        h = z.read('Contents/header.xml').decode('utf-8')
        secs = [z.read(n).decode('utf-8') for n in sorted(z.namelist()) if n.startswith('Contents/section')]
    fonts = {lang: dict(re.findall(r'<hh:font id="(\d+)" face="([^"]*)"', body))
             for lang, body in re.findall(r'<hh:fontface lang="(\w+)"[^>]*>(.*?)</hh:fontface>', h, re.S)}

    def faces(m):
        return '<FONTS ' + ' '.join(f'{k}={fonts[k.upper()][v]}' for k, v in re.findall(r'(\w+)="(\d+)"', m.group(1))) + '/>'
    maps = {}
    for tag, ref in (('borderFill', 'borderFillIDRef'), ('charPr', 'charPrIDRef'), ('paraPr', 'paraPrIDRef')):
        for i, body in re.findall(r'<hh:%s id="(\d+)"(.*?)</hh:%s>' % (tag, tag), h, re.S):
            body = re.sub(r'<hh:fontRef ([^/]*)/>', faces, body)
            body = re.sub(r'borderFillIDRef="(\d+)"', lambda m: 'BF=' + maps.get(('borderFillIDRef', m.group(1)), '?'), body)
            maps[(ref, i)] = tag[:2] + hashlib.md5(body.encode('utf-8')).hexdigest()[:6]
    out = []
    for s in secs:
        s = re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', s, flags=re.S)
        s = re.sub(r'(charPrIDRef|paraPrIDRef|borderFillIDRef)="(\d+)"',
                   lambda m: f'{m.group(1)}="{maps.get((m.group(1), m.group(2)), "?" + m.group(2))}"', s)
        s = re.sub(r' (id|instid|instId|zOrder|fieldid|beginIDRef)="\d+"', '', s)
        out += s.replace('><', '>\n<').splitlines()
    return out


def diff(a, b):
    pa, pb = parts(a), parts(b)
    out = []
    for n in sorted(set(pa) | set(pb)):
        la = pretty(pa.get(n, b''))
        lb = pretty(pb.get(n, b''))
        out += difflib.unified_diff(la, lb, f'A/{n}', f'B/{n}', n=2, lineterm='')
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'dump':
        dump(sys.argv[2], sys.argv[3])
        print('DUMP OK', sys.argv[3])
    elif cmd == 'sdiff':
        lines = [x for x in difflib.unified_diff(semantic_lines(sys.argv[2]), semantic_lines(sys.argv[3]), lineterm='', n=1)]
        sys.stdout.buffer.write(('\n'.join(lines) + '\n').encode('utf-8'))
    elif cmd == 'diff':
        lines = diff(sys.argv[2], sys.argv[3])
        text = '\n'.join(lines) + '\n'
        if len(sys.argv) > 4:
            open(sys.argv[4], 'w', encoding='utf-8', newline='\n').write(text)
            print('DIFF LINES', len(lines), sys.argv[4])
        else:
            sys.stdout.buffer.write(text.encode('utf-8'))
