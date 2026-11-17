"""Layout of a spec: every paragraph with its box width and its wrapped lines (real font widths, core/textfit.py),
every table cell, and the space that Hangul drops next to a block table (rules W05).

  Layout(spec).paras   [Para]: .block, .props (inherited + own), .width (mm), .fill, .where ("p3", "p2 table r1c2 p1"),
                       .cell (in a table cell), .prev/.next (neighbour blocks), .text, .cs (chars), .lines [(start, end)]
  Layout(spec).cells   [(cell, pad mm [l, r, t, b], where, has text, table border)]
  Layout(spec).tables  [(table, where)]
  Layout(spec).lost    [(where, table, block, 'top'|'bottom', pt)]

Used by checks that need to know where text goes (readability, edit guard). Styles ("class") resolve as in the
builder (core/build.py Doc.klass).
"""
from . import build, read, textfit

HU_MM = 283.465
CELL_ONLY = {'p', 'blocks', 'cs', 'rs', 'fill', 'border', 'pad', 'valign', 'diag', 'diag_line', 'protect', 'editable', 'formula'}


def mm(v):
    return build.hu(v) / HU_MM


def text_of(p):
    return p if isinstance(p, str) else ''.join(x if isinstance(x, str) else str(x.get('t', '')) for x in p or [])


class Para:
    def __init__(self, block, props, width_mm, fill, where, in_cell, prev=None, nxt=None):
        self.block, self.props, self.width, self.fill, self.where, self.cell = block, props, width_mm, fill, where, in_cell
        self.prev, self.next = prev, nxt          # neighbour blocks in the same list (body or cell)
        self.text = text_of(props.get('p', ''))
        self.cs, self.lines = textfit.wrap(props, width_mm) if self.text.strip() else ([], [(0, 0)])


class Layout:
    eff = build.Doc.klass       # props of a spec item with its "class" styles applied, exactly as the builder does

    def __init__(self, spec):
        self.spec = spec
        self.paras, self.cells, self.tables = [], [], []
        self.lost = []              # (where, table, block, side, pt): space that Hangul ignores next to a table
        self.styles = spec.get('styles', {})
        self.named = spec.get('named_styles') or {}      # Doc.klass puts a named style's props under the item's own
        secs = spec.get('sections') or [spec]
        base = {**read.DEF_CHAR, **read.DEF_PARA, **(spec.get('defaults') or {})}
        # table cells: the document's paragraph defaults + the char props around the table (core/build Doc.table)
        self.cell_para = {k: v for k, v in base.items() if k in build.PARA_KEYS}
        for i, sec in enumerate(secs):
            pg = dict(spec.get('page', {}), **sec.get('page', {}))
            size = pg.get('size', 'A4')
            w, h = build.PAPER[size.upper()] if isinstance(size, str) else size
            w, h = mm(w), mm(h)
            if pg.get('landscape'):
                w = max(w, h)
            m = {'left': 20, 'right': 20, **pg.get('margin', {})}
            self.walk(sec.get('body', []), {**base, **(sec.get('defaults') or {})}, w - mm(m['left']) - mm(m['right']),
                      None, f's{i + 1}' if len(secs) > 1 else '', False)

    def walk(self, blocks, inh, width, fill, where, in_cell):
        for n, b in enumerate(blocks, 1):
            if isinstance(b, str):
                b = {'p': b}
            here = f'{where} p{n}'.strip()
            e = self.eff(b)
            prev = blocks[n - 2] if n > 1 else None
            if isinstance(prev, dict) and 'table' in prev and not prev['table'].get('inline') and e.get('before'):
                self.lost.append((here, prev['table'], b, 'bottom', e['before']))   # rules W05
            if 'table' in b and not b['table'].get('inline') and e.get('before'):
                self.lost.append((here, b['table'], b, 'top', e['before']))
            if 'table' in b:
                t = b['table']
                self.tables.append((t, here))
                chars = {k: v for k, v in {**inh, **e}.items() if k in read.CHAR_KEYS}
                base = {**self.cell_para, **chars, **t.get('cell', {})}
                tpad = t.get('pad', [1.8, 1.8, 0.5, 0.5])
                for r, row in enumerate(t.get('rows', []), 1):
                    cells = row.get('cells', []) if isinstance(row, dict) else row
                    rs = dict(base, **(row.get('style', {}) if isinstance(row, dict) else {}))
                    c = 0
                    for k, cell in enumerate(cells, 1):
                        if isinstance(cell, str):
                            cell = cells[k - 1] = {'p': cell}   # in the spec, so that a fix changes it
                        ce = self.eff(cell)
                        span = ce.get('cs', 1)
                        cw = sum(t['cols'][c:c + span]) if c < len(t['cols']) else 0
                        c += span
                        pad = ce.get('pad', tpad)
                        pad = [mm(x) for x in (pad if isinstance(pad, list) else [pad] * 4)]
                        cfill = ce.get('fill') or fill
                        cwhere = f'{here} table r{r}c{k}'
                        props = dict(rs, **{x: v for x, v in ce.items() if x not in CELL_ONLY})
                        inner = cell.get('blocks') or [{'p': x} for x in str(cell.get('p', '')).split('\n')]
                        self.cells.append((cell, pad, cwhere, any(text_of(x.get('p', '') if isinstance(x, dict)
                                                                          else x).strip() for x in inner),
                                           t.get('border', '0.12mm solid')))
                        if 'blocks' in cell:
                            self.walk(cell['blocks'], props, cw - pad[0] - pad[1], cfill, cwhere, True)
                        else:                           # text cell: a fix goes on the cell (its props reach its text)
                            for m, x in enumerate(inner, 1):
                                self.paras.append(Para(cell, dict(props, p=x['p']), cw - pad[0] - pad[1], cfill,
                                                       f'{cwhere} p{m}', True))
            elif 'p' in b:
                if isinstance(b['p'], str) and '\n' in b['p']:
                    continue                            # several paragraphs in one string: skipped (rare)
                self.paras.append(Para(b, dict(inh, **e), width, e.get('fill') or fill, here, in_cell,
                                       prev, blocks[n] if n < len(blocks) else None))
