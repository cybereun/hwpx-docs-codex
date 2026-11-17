"""Readability check of a document (user 2026-11-14: "한글문서 만들때 가독성도 신경써야할거 같은데").

  python readability.py <file.hwpx | spec.json> [--fix out.json]
  python readability.py --selftest

Each finding is one line "RDnn <where>: <problem> -> <fix>". Line layout comes from textfit.py (real font widths).
A reproduction (image, HTML, an existing form) must look like its target: report the findings to the user and change
nothing. A new document (Markdown, a description) gets the safe fixes (marked "fix"): md2hwpx.py applies them unless
--keep; --fix here writes a fixed spec. Other findings are advice: they change the design, so the user decides.

| id | problem | threshold | fix |
|---|---|---|---|
| RD01 | a line break inside a Korean word | word_break char and a break between two Hangul syllables | word_break word |
| RD02 | wide gaps in a justified line | each gap > 1.8 x a normal space | advice: left align, condense, or reword |
| RD03 | dense lines | 2+ lines and line spacing < 140 % (table cell < 120 %) | 160 % (cell 130 %) |
| RD04 | small text | < 9 pt | advice |
| RD05 | long lines | > 50 Korean characters per line | advice: wider margins, 2 columns |
| RD06 | low contrast on its fill | contrast ratio < 4.5 | black or white text |
| RD07 | text near the cell lines | cell margin left/right < 1.0 mm or top/bottom < 0.3 mm | Hangul default 1.8 / 0.5 mm |
| RD08 | heading far from its text | space above <= space below | advice; keep_next on (fix) |
| RD09 | many font families | > 3 | advice |
| RD10 | table header not marked, long table | 3+ rows, row 1 not bold and no fill; 15+ rows and no repeat | advice; repeat_header (fix) |
| RD11 | empty paragraphs for space | 2+ empty paragraphs in a row | advice: use before/after |
| RD12 | long centred text | 3+ lines centred | advice: left or justify |
| RD13 | space next to a block table that Hangul drops | `before` on the paragraph after a table or on the table block (rules W05) | move it to the table margin |
"""
from ..core import tmpdir
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from ..core import read as hwpx2spec
from ..core import textfit
from ..core.layout import Layout, mm, text_of

HANGUL = re.compile('[가-힣]')


def luminance(c):
    c = (c or '#000000').lstrip('#')
    rgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)] if len(c) == 6 else [0, 0, 0]
    rgb = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def visible(line):
    return bool(line) and not str(line).startswith('none')


def marked(cell):
    """A cell that looks like a header or label: fill, or bold text."""
    return isinstance(cell, dict) and bool(cell.get('fill') or cell.get('bold') or any(
        isinstance(x, dict) and (x.get('bold') or any(isinstance(r, dict) and r.get('bold') for r in
                                                      (x['p'] if isinstance(x.get('p'), list) else [])))
        for x in cell.get('blocks', [])))


class Check(Layout):
    """The rules RD01-RD13 on the layout of a spec (core/layout.py)."""

    def __init__(self, spec):
        super().__init__(spec)
        self.findings = []

    def add(self, rid, where, msg, fix=None):
        self.findings.append((rid, where, msg, fix))

    def run(self):
        sizes = {}
        for p in self.paras:
            sizes[p.props['size']] = sizes.get(p.props['size'], 0) + len(p.text)
        body = max(sizes, key=sizes.get) if sizes else 10
        fonts = set()
        empty = 0
        for i, p in enumerate(self.paras):
            pr, text = p.props, p.text
            short = text.strip()[:24]
            fonts.add(pr.get('font'))
            if not text.strip():
                # a small empty paragraph (< 8 pt) is an exact spacer; full-size blank lines give uneven space
                empty = empty + 1 if not p.cell and pr['size'] >= 8 else 0
                if empty == 2:
                    self.add('RD11', p.where, '2+ empty paragraphs used as space', None)
                continue
            empty = 0
            nl = len(p.lines)
            # RD01 break inside a Korean word
            if pr.get('word_break', 'char') == 'char' and any(
                    e < len(p.cs) and HANGUL.match(p.cs[e - 1][0]) and HANGUL.match(p.cs[e][0]) for _, e in p.lines[:-1]):
                self.add('RD01', p.where, f'line break inside a word "{short}"',
                         lambda b=p.block: b.update(word_break='word'))
            # RD02 gaps in justified lines
            if pr.get('align') == 'justify' and nl > 1:
                first, other = textfit.widths(pr, p.width)
                for k, (s, e) in enumerate(p.lines[:-1]):
                    seg = p.cs[s:e]
                    while seg and seg[-1][0] == ' ':
                        seg = seg[:-1]
                    gaps = [w for ch, w in seg if ch == ' ']
                    if gaps:
                        extra = ((first if k == 0 else other) - sum(w for _, w in seg)) / len(gaps)
                        if extra > 0.8 * sum(gaps) / len(gaps):     # each gap at least 1.8 x a normal space
                            self.add('RD02', p.where, f'justified line {k + 1}: each gap {extra / pr["size"]:.1f} em '
                                                      f'wider than a space "{short}"', None)
                            break
            # RD03 dense lines
            line = pr.get('line', 160)
            low = 120 if p.cell else 140
            if nl > 1 and isinstance(line, (int, float)) and line < low:
                self.add('RD03', p.where, f'{nl} lines at {line} % spacing "{short}"',
                         lambda b=p.block, v=130 if p.cell else 160: b.update(line=v))
            # RD04 small text, RD05 long lines
            if pr['size'] < 9:
                self.add('RD04', p.where, f'{pr["size"]} pt text "{short}"', None)
            if not p.cell and nl > 1 and pr['size'] == body and textfit.widths(pr, p.width)[1] / pr['size'] > 50:
                self.add('RD05', p.where, f'about {textfit.widths(pr, p.width)[1] / pr["size"]:.0f} characters per line',
                         None)
            # RD06 contrast
            bg = p.fill or '#FFFFFF'
            fg = pr.get('color', '#000000')
            if contrast(fg, bg) < 4.5:
                to = '#000000' if contrast('#000000', bg) >= contrast('#FFFFFF', bg) else '#FFFFFF'
                self.add('RD06', p.where, f'text {fg} on {bg}: contrast {contrast(fg, bg):.1f}',
                         lambda b=p.block, v=to: b.update(color=v))
            # RD08 heading spacing and keep_next (neighbours in the same list; a table gives its outer margin)
            nxt = self.paras[i + 1] if i + 1 < len(self.paras) else None
            if (not p.cell and nl == 1 and len(text) < 40 and (pr.get('bold') or pr['size'] >= body + 2)
                    and nxt is not None and nxt.block is p.next and nxt.text.strip()
                    and nxt.props['size'] < pr['size'] + 0.1
                    and not (nxt.props.get('bold') and nxt.props['size'] == pr['size'])):
                def space(b, side):         # side 'after' of the block above, 'before' of the block below
                    if not isinstance(b, dict):
                        return 0
                    b = self.eff(b)
                    if 'table' in b:
                        m = b['table'].get('margin', 1)
                        m = m if isinstance(m, list) else [m] * 4
                        return mm(m[3 if side == 'after' else 2]) / textfit.PT_MM
                    return b.get(side, 0) or 0
                above = round(space(p.prev, 'after') + pr.get('before', 0), 1)
                below = round(pr.get('after', 0) + space(p.next, 'before'), 1)
                if p.prev is not None and above <= below and above + below > 0:      # not the first block
                    self.add('RD08', p.where, f'heading "{short}": {above} pt above <= {below} pt below', None)
                if not pr.get('keep_next'):
                    self.add('RD08', p.where, f'heading "{short}" can end a page alone',
                             lambda b=p.block: b.update(keep_next=True))
            # RD12 long centred text
            if pr.get('align') == 'center' and nl >= 3:
                self.add('RD12', p.where, f'{nl} centred lines "{short}"', None)
        if len(fonts - {None}) > 3:
            self.add('RD09', 'document', f'{len(fonts)} font families: {", ".join(sorted(f for f in fonts if f))}', None)
        for cell, pad, where, has_text, tline in self.cells:
            b = cell.get('border', tline)
            side = {k: (b.get(k, tline) if isinstance(b, dict) else b) for k in ('left', 'right', 'top', 'bottom')}
            near = [(side['left'], pad[0], 1.0), (side['right'], pad[1], 1.0), (side['top'], pad[2], 0.3),
                    (side['bottom'], pad[3], 0.3)]
            if has_text and any(visible(line) and v < limit for line, v, limit in near):  # only sides with a line
                self.add('RD07', where, 'cell margins ' + '/'.join(f'{x:.1f}' for x in pad) + ' mm',
                         lambda c=cell: c.update(pad=[1.8, 1.8, 0.5, 0.5]))
        for where, t, b, side, pt in self.lost:          # rules W05: Hangul drops this space
            def move(t=t, b=b, side=side, pt=pt):
                m = t.get('margin', 1)
                m = list(m) if isinstance(m, list) else [m] * 4
                k = 3 if side == 'bottom' else 2
                m[k] = round(max(m[k], pt * textfit.PT_MM), 2)
                t['margin'] = m
                b['before'] = 0
            self.add('RD13', where, f'{pt} pt before {"the paragraph after a table" if side == "bottom" else "a table"}'
                                    f' is not shown by Hangul; use the table {side} margin', move)
        for t, where in self.tables:
            rows = t.get('rows', [])
            if len(rows) >= 3:
                cells = [[self.eff(c) for c in (r.get('cells', []) if isinstance(r, dict) else r)] for r in rows]
                head_row = any(marked(c) for c in cells[0]) or (isinstance(rows[0], dict) and
                                                                rows[0].get('style', {}).get('bold'))
                label_col = all(r and marked(r[0]) for r in cells)       # key-value table: labels in column 1
                if not head_row and not label_col:
                    self.add('RD10', where, 'row 1 of the table is not marked as a header (bold or fill)', None)
            # Hangul repeats the rows marked as header rows; repeat_header is on unless set to false
            if len(rows) >= 15 and (not t.get('header_rows') or t.get('repeat_header') is False):
                self.add('RD10', where, f'{len(rows)} rows: header not repeated on the next page',
                         lambda t=t: t.update(repeat_header=True, header_rows=t.get('header_rows') or 1))
        return self.findings


def check(spec):
    """Findings [(id, where, message, fix or None)]; a fix changes `spec` in place when fix() runs."""
    return Check(spec).run()


def report_only(spec, out=print):
    """For a reproduction: list the findings, change nothing."""
    import copy
    report(check(copy.deepcopy(spec)), out)


def fix(findings):
    """Apply the safe fixes; returns the number applied."""
    n = 0
    for _, _, _, f in findings:
        if f:
            f()
            n += 1
    return n


def report(findings, out=print):
    for rid, where, msg, f in findings:
        out(f'{rid} {where}: {msg}' + (' -> fix' if f else ''))
    ids = {}
    for rid, *_ in findings:
        ids[rid] = ids.get(rid, 0) + 1
    out('READABILITY ' + (' '.join(f'{k}x{v}' for k, v in sorted(ids.items())) or 'OK'))


def selftest():
    spec = {'body': [
        {'p': '제목', 'size': 14, 'bold': True, 'before': 0, 'after': 10},
        {'p': '가나다라마바사아자차카타파하' * 6, 'size': 10, 'line': 110, 'word_break': 'char'},
        {'p': '흐린 글자', 'color': '#BBBBBB'},
        '', '',
        {'table': {'cols': [40, 40], 'pad': [0.2, 0.2, 0.1, 0.1], 'rows': [['가', '나'], ['1', '2'], ['3', '4']]}},
        {'p': '표 다음 문단', 'class': 'spaced'}], 'styles': {'spaced': {'before': 10}}}
    f = check(spec)
    ids = sorted({x[0] for x in f})
    assert ids == ['RD01', 'RD03', 'RD06', 'RD07', 'RD08', 'RD10', 'RD11', 'RD13'], (ids, f)
    assert fix(f) >= 6
    b = spec['body']
    assert b[1]['word_break'] == 'word' and b[1]['line'] == 160 and b[2]['color'] == '#000000' and b[0]['keep_next']
    assert b[5]['table']['rows'][0][0]['pad'] == [1.8, 1.8, 0.5, 0.5]
    assert b[6]['before'] == 0 and b[5]['table']['margin'] == [1, 1, 1, 3.53], (b[6], b[5]['table'].get('margin'))
    print('READABILITY SELFTEST PASS')


def main(args):
    if args and args[0] == '--selftest':
        return selftest()
    src = args[0]
    if src.lower().endswith('.hwpx'):
        spec = hwpx2spec.read(src, os.path.join(tmpdir.mkdtemp('rd_'), 'spec.json'))
    else:
        spec = json.load(open(src, encoding='utf-8'))
    found = check(spec)
    report(found)
    if '--fix' in args:
        out = args[args.index('--fix') + 1]
        print('FIXED', fix(found))
        json.dump(spec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('SPEC WRITTEN', out)


if __name__ == '__main__':
    main(sys.argv[1:])
