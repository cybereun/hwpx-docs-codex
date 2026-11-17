"""Tables: grid, merges, per-cell lines and fills, sizes."""
from ..core.units import CHAR_KEYS, PARA_KEYS, hu, inherit, line, quad, sides_of
from . import ext, fills


class TableMixin:
    """Tables: grid, merges, per-cell lines and fills, sizes. Mixed into core.build.Doc."""

    # ---- tables ----
    def table(self, t, ctx, inline=False):
        # cells take the char style of the anchor paragraph, but not its paragraph shape
        # (spacing, indents, align of the paragraph that holds the table are not the cells' own)
        ctx = dict({k: v for k, v in self.defaults.items() if k in PARA_KEYS},
                   **{k: v for k, v in ctx.items() if k in CHAR_KEYS})
        cols = [hu(w) for w in t['cols']]
        rows_spec = t['rows'] if 'rows' in t else t['cells']
        nrow = len(rows_spec)
        ncol = len(cols)
        # place cells (HTML-like flow): a cell takes the next free grid position in its row
        taken = {}
        cells = []
        for r, row in enumerate(rows_spec):
            if isinstance(row, dict):
                rstyle, row_cells = row.get('style', {}), row['cells']
            else:
                rstyle, row_cells = {}, row
            c = 0
            for cell in row_cells:
                if not isinstance(cell, dict):
                    cell = {'p': '' if cell is None else str(cell)}
                cell = dict(rstyle, **self.klass(cell))      # row style < class < the cell's own props
                while (r, c) in taken:
                    c += 1
                if c >= ncol:
                    raise ValueError(f'table row {r}: too many cells')
                rs, cs = int(cell.get('rs', 1)), int(cell.get('cs', 1))
                for dr in range(rs):
                    for dc in range(cs):
                        taken[(r + dr, c + dc)] = True
                cells.append((r, c, rs, cs, cell))
                c += cs
        for r in range(nrow):
            for c in range(ncol):
                if (r, c) not in taken:
                    cells.append((r, c, 1, 1, {'p': ''}))
        cells.sort(key=lambda x: (x[0], x[1]))
        heights = t.get('heights')
        heights = [hu(h) for h in heights] if heights else [None] * nrow
        pad = quad(t.get('pad', ['1.8mm', '1.8mm', '0.5mm', '0.5mm']))
        if t.get('pad') is None:
            pad = [510, 510, 141, 141]       # Hangul default cell margins
        defcell = t.get('cell', {})
        # line grid: H[(r, c)] = line above row r at column c; V[(r, c)] = line left of column c at row r
        inner = line(t.get('border', '0.12mm solid #000000'))
        outer = line(t['outline']) if 'outline' in t else inner
        H = {(r, c): (outer if r in (0, nrow) else inner) for r in range(nrow + 1) for c in range(ncol)}
        V = {(r, c): (outer if c in (0, ncol) else inner) for r in range(nrow) for c in range(ncol + 1)}
        for r, v in (t.get('hlines') or {}).items():
            for c in range(ncol):
                H[(int(r), c)] = line(v)
        for c, v in (t.get('vlines') or {}).items():
            for r in range(nrow):
                V[(r, int(c))] = line(v)
        for r, c, rs, cs, cell in cells:
            # a cell border sets the grid lines around the cell; a later cell wins on a shared line
            for side, lt in sides_of(cell.get('border')).items():
                if side == 'top':
                    for dc in range(cs):
                        H[(r, c + dc)] = lt
                elif side == 'bottom':
                    for dc in range(cs):
                        H[(r + rs, c + dc)] = lt
                elif side == 'left':
                    for dr in range(rs):
                        V[(r + dr, c)] = lt
                elif side == 'right':
                    for dr in range(rs):
                        V[(r + dr, c + cs)] = lt
        # row heights: given, or estimated from the text (Hangul grows a row to fit its text)
        for r in range(nrow):
            if heights[r] is None:
                est = 0
                for rr, c, rs, cs, cell in cells:
                    if rr == r and rs == 1:
                        cc = inherit(inherit(ctx, defcell), cell)
                        lines = max(1, len(str(cell.get('p', '')).split('\n')) if isinstance(cell.get('p', ''), str) else 1)
                        ln = cc.get('line', 160)
                        pct = ln if isinstance(ln, (int, float)) else 160
                        est = max(est, round(lines * hu(cc.get('size', 10), 'pt') * pct / 100))
                heights[r] = est + pad[2] + pad[3]
        tid = self.next_obj()
        trs = []
        for r in range(nrow):
            tcs = []
            for rr, c, rs, cs, cell in cells:
                if rr != r:
                    continue
                cc = inherit(inherit(ctx, defcell), cell)
                fill = cell.get('fill', defcell.get('fill'))
                diag = cell.get('diag', defcell.get('diag'))
                sides = {'left': V[(r, c)], 'right': V[(r, c + cs)], 'top': H[(r, c)], 'bottom': H[(r + rs, c)]}
                bf = self.head.border_fill(sides, fills.brush(self, fill),
                                           slash=diag in ('slash', 'both', 'cross'), back=diag in ('back', 'both', 'cross'),
                                           diag=line(cell.get('diag_line', '0.12mm solid')) if diag else None)
                cpad = quad(cell['pad']) if 'pad' in cell else (quad(defcell['pad']) if 'pad' in defcell else pad)
                has = 1 if ('pad' in cell or 'pad' in defcell) else 0
                valign = str(cell.get('valign', defcell.get('valign', 'center'))).upper()
                content = cell.get('blocks')
                if content is None:
                    text = cell.get('p', '')
                    content = [{'p': [{'xml': ext.formula_xml(self, cell['formula'], text)}]}] if cell.get('formula') \
                        else [{'p': text}]                  # a formula cell (계산식): field + shown result, rules TB09
                w = sum(cols[c:c + cs])
                h = sum(heights[r:r + rs])
                header = 1 if (r < int(t.get('header_rows', 0))) else 0
                prot, edit = (int(bool(cell.get(k, defcell.get(k)))) for k in ('protect', 'editable'))     # rules TB08
                tcs.append(f'<hp:tc name="" header="{header}" hasMargin="{has}" protect="{prot}" editable="{edit}" dirty="0" '
                           f'borderFillIDRef="{bf}">{self.sublist(content, cc, valign)}'
                           f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="{cs}" rowSpan="{rs}"/>'
                           f'<hp:cellSz width="{w}" height="{h}"/>'
                           f'<hp:cellMargin left="{cpad[0]}" right="{cpad[1]}" top="{cpad[2]}" bottom="{cpad[3]}"/></hp:tc>')
            trs.append('<hp:tr>' + ''.join(tcs) + '</hp:tr>')
        tbf = self.head.border_fill({k: inner for k in ('left', 'right', 'top', 'bottom')})
        om = quad(t.get('margin', ['1mm'] * 4)) if not inline else quad(t.get('margin', 0))
        halign = str(t.get('align', 'left')).upper()
        wrap = str(t.get('wrap', 'top_and_bottom')).upper()
        posxml = ext.pos_xml(t.get('pos'), halign, inline, t.get('hold'))      # floating table, hold: rules TB05
        capxml = ext.caption_xml(self, t['caption'], ctx, sum(cols)) if t.get('caption') else ''     # rules TB07
        pb = {'cell': 'CELL', 'table': 'TABLE', 'none': 'NONE'}[t.get('page_break', 'cell')]
        return (f'<hp:tbl id="{1000000000 + tid}" zOrder="{tid}" numberingType="TABLE" textWrap="{wrap}" '
                f'textFlow="{str(t.get("side", "both_sides")).upper()}" lock="0" dropcapstyle="None" pageBreak="{pb}" '
                f'repeatHeader="{int(t.get("repeat_header", True))}" rowCnt="{nrow}" '
                f'colCnt="{ncol}" cellSpacing="0" borderFillIDRef="{tbf}" noAdjust="0">'
                f'<hp:sz width="{sum(cols)}" widthRelTo="ABSOLUTE" height="{sum(heights)}" heightRelTo="ABSOLUTE" protect="0"/>'
                f'{posxml}<hp:outMargin left="{om[0]}" right="{om[1]}" top="{om[2]}" bottom="{om[3]}"/>{capxml}'
                f'<hp:inMargin left="{pad[0]}" right="{pad[1]}" top="{pad[2]}" bottom="{pad[3]}"/>{"".join(trs)}</hp:tbl>')
