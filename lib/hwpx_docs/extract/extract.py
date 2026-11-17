"""HWPX -> plain text or Markdown.

  hd text <in.hwpx> [--md] [-o out.md]
  hd text --selftest

Reads the file with core/read.py and writes the text in document order. --md: a big bold paragraph becomes a
heading (# for 4+ pt over the body size, ## for 2+ pt), a table becomes a Markdown table (a merged cell keeps its
text in its first position; the covered positions stay empty; line breaks in a cell become <br>), a footnote
becomes [^n] with the note text at the end, a picture becomes ![](file). Text boxes and headers/footers are left out.
"""
from ..core import tmpdir
import collections
import os
import sys

from ..core import read


class Out:
    def __init__(self, md):
        self.md, self.lines, self.notes = md, [], []

    def runs(self, p):
        if isinstance(p, str):
            return p
        out = []
        for r in p:
            if isinstance(r, str):
                out.append(r)
            elif 'footnote' in r or 'endnote' in r:
                note = r.get('footnote', r.get('endnote'))
                self.notes.append(note if isinstance(note, str) else ' '.join(self.block_text(b) for b in note))
                out.append(f'[^{len(self.notes)}]' if self.md else f'({len(self.notes)})')
            else:
                out.append(str(r.get('t', '')))
        return ''.join(out)

    def block_text(self, b):
        if isinstance(b, str):
            return b
        return self.runs(b.get('p', '')) if 'p' in b else ''

    def cell_text(self, c):
        if isinstance(c, str):
            return c
        if 'blocks' in c:
            return '\n'.join(self.block_text(b) for b in c['blocks'])
        return self.runs(c.get('p', ''))

    def table(self, t):
        rows = [r.get('cells', []) if isinstance(r, dict) else r for r in t.get('rows', [])]
        grid, taken = collections.defaultdict(dict), set()
        for r, row in enumerate(rows):
            c = 0
            for cell in row:
                while (r, c) in taken:
                    c += 1
                cs = cell.get('cs', 1) if isinstance(cell, dict) else 1
                rs = cell.get('rs', 1) if isinstance(cell, dict) else 1
                taken |= {(r + i, c + j) for i in range(rs) for j in range(cs)}
                grid[r][c] = self.cell_text(cell)
                c += cs
        ncol = max((c for _, c in taken), default=-1) + 1
        if not self.md:
            for r in range(len(rows)):
                self.lines.append('\t'.join(grid[r].get(c, '') for c in range(ncol)))
            return
        def esc(x):
            return x.replace('|', '\\|').replace('\n', '<br>').strip()
        for r in range(len(rows)):
            self.lines.append('| ' + ' | '.join(esc(grid[r].get(c, '')) for c in range(ncol)) + ' |')
            if r == 0:
                self.lines.append('|' + '---|' * ncol)
        self.lines.append('')

    def blocks(self, blocks, base):
        for b in blocks:
            if isinstance(b, str):
                b = {'p': b}
            if 'table' in b:
                self.table(b['table'])
            elif 'pic' in b:
                if self.md:
                    self.lines += [f'![]({b["pic"].get("src", "")})', '']
            elif 'p' in b:
                text = self.runs(b['p'])
                size = b.get('size', base)
                if self.md and text.strip() and (b.get('bold') or size >= base + 4) and size >= base + 2:
                    self.lines += ['#' * (1 if size >= base + 4 else 2) + ' ' + text.strip(), '']
                else:
                    self.lines += [text, ''] if self.md else [text]


def extract(path, md=False):
    spec = read.read(path, os.path.join(tmpdir.mkdtemp('hwpx_docs_x_'), 's.json'))
    out = Out(md)
    sizes = collections.Counter()
    for sec in spec.get('sections') or [spec]:
        for b in sec.get('body', []):
            if isinstance(b, dict) and 'p' in b:
                p = b['p']
                n = len(p) if isinstance(p, str) else sum(len(r) if isinstance(r, str) else len(str(r.get('t', '')))
                                                          for r in p)
                sizes[b.get('size', 10)] += n
    base = sizes.most_common(1)[0][0] if sizes else 10
    for sec in spec.get('sections') or [spec]:
        out.blocks(sec.get('body', []), base)
    lines = out.lines
    if out.notes:
        lines += [''] + [(f'[^{i}]: ' if md else f'({i}) ') + n for i, n in enumerate(out.notes, 1)]
    text = '\n'.join(lines)
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return text.strip() + '\n'


def selftest():
    from ..core import build
    d = tmpdir.mkdtemp('hwpx_docs_xt_')
    src = os.path.join(d, 'a.hwpx')
    build.write({'body': [{'p': '보고서 제목', 'size': 18, 'bold': True},
                          {'p': ['본문 문장', {'footnote': '각주 글'}, ' 끝']},
                          {'table': {'cols': [30, 30, 30], 'rows': [['구분', {'p': '내용', 'cs': 2}],
                                                                   ['가', '나|다', '줄1\n줄2']]}}]}, src)
    md = extract(src, md=True)
    assert md.startswith('# 보고서 제목'), md
    assert '본문 문장[^1] 끝' in md and '[^1]: 각주 글' in md, md
    assert '| 구분 | 내용 |  |' in md and '| 가 | 나\\|다 | 줄1<br>줄2 |' in md, md
    txt = extract(src)
    assert '보고서 제목' in txt and '가\t나|다' in txt, txt
    print('EXTRACT SELFTEST PASS')


def main(args):
    if args and args[0] == '--selftest':
        return selftest()
    text = extract(args[0], md='--md' in args)
    if '-o' in args:
        open(args[args.index('-o') + 1], 'w', encoding='utf-8').write(text)
        print('TEXT WRITTEN', args[args.index('-o') + 1])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
