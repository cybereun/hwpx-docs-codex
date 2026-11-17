"""The default of `inline` for a table (rules TB11): a table is treated as a character (`hp:pos treatAsChar="1"`) unless the spec says otherwise.

A table that the spec gives `inline` keeps that value. A table with `pos`, `wrap`, `side` or `hold`, or in a block with `same_para`, is a
flow table (`inline` false). A table with `header_rows` or `page_break: cell` (the spec asks for repeated header rows or for rows cut between pages) and a table that
is about as high as a page are flow tables too: Hangul does not cut a table that is treated as a character, so these must flow.
The height is estimated from the text, the wrapped lines of every cell (`core/textfit.py`), the row `heights` and the cell margins.

`resolve(spec)` writes the answer into every table of the spec that has no `inline` (the spec is changed in place, so the builder, the
layout checks and pagefit all see the same value); a table read from an .hwp / HWPX always has it (core/read.py, hwp5/tospec.py).
"""
FLOW_KEYS = ('pos', 'wrap', 'side', 'hold')
FIT = 0.95                                  # a table higher than this part of the page body flows
MM_PT = 25.4 / 72
HU_MM = 283.465


def _mm(v):
    from ..core.units import hu
    return hu(v) / HU_MM


def _text(p):
    return p if isinstance(p, str) else ''.join(x if isinstance(x, str) else str(x.get('t', '')) for x in p or [])


def _lines_height(props, text, width_mm):
    from ..core import textfit
    cs, lines = textfit.wrap(dict(props, p=text), width_mm) if text.strip() else ([], [(0, 0)])
    pct = props.get('line', 160)
    pct = pct if isinstance(pct, (int, float)) else 160
    return max(1, len(lines)) * float(props.get('size', 10)) * pct / 100 * MM_PT


def _blocks_height(blocks, props, width_mm, body_h):
    h = 0.0
    for b in blocks:
        b = {'p': b} if isinstance(b, str) else b
        if 'table' in b:
            h += _table_height(b['table'], props, width_mm, body_h)
        elif 'pic' in b:
            h += _mm(b['pic'].get('h', 0))
        elif 'p' in b:
            h += _lines_height({**props, **{k: v for k, v in b.items() if k != 'p'}}, _text(b['p']), width_mm)
    return h


def _table_height(t, props, width_mm, body_h):
    """Estimated height (mm) of table `t` in a box `width_mm` wide: the highest row content or the given height of every row."""
    cols = [_mm(w) for w in t['cols']]
    rows = t.get('rows') or t.get('cells') or []
    given = [_mm(h) for h in t['heights']] if t.get('heights') else []
    pad = t.get('pad', [1.8, 1.8, 0.5, 0.5])
    pad = [_mm(x) for x in (pad if isinstance(pad, list) else [pad] * 4)]
    base = {**props, **(t.get('cell') or {})}
    taken, total = set(), 0.0
    for r, row in enumerate(rows):
        style, cells = (row.get('style', {}), row['cells']) if isinstance(row, dict) else ({}, row)
        h, c = given[r] if r < len(given) else 0.0, 0
        for cell in cells:
            cell = {'p': '' if cell is None else str(cell)} if not isinstance(cell, dict) else cell
            while (r, c) in taken:
                c += 1
            rs, cs = int(cell.get('rs', 1)), int(cell.get('cs', 1))
            for dr in range(rs):
                for dc in range(cs):
                    taken.add((r + dr, c + dc))
            if rs == 1:
                cp = cell.get('pad', t.get('pad', [1.8, 1.8, 0.5, 0.5]))
                cp = [_mm(x) for x in (cp if isinstance(cp, list) else [cp] * 4)]
                w = max(sum(cols[c:c + cs]) - cp[0] - cp[1], 5.0)
                p = {**base, **style, **{k: v for k, v in cell.items() if k not in ('p', 'blocks', 'rs', 'cs', 'fill', 'border', 'pad')}}
                if 'blocks' in cell:
                    inner = _blocks_height(cell['blocks'], p, w, body_h)
                else:
                    inner = sum(_lines_height(p, x, w) for x in str(cell.get('p', '')).split('\n'))
                h = max(h, inner + cp[2] + cp[3])
            c += cs
        total += h
    return total


def default_inline(t, props, width_mm, body_h, same_para=False):
    """True when a table without `inline` is treated as a character."""
    if same_para or any(k in t for k in FLOW_KEYS) or t.get('header_rows') or t.get('page_break') == 'cell':
        return False
    try:
        return _table_height(t, props, width_mm, body_h) < FIT * body_h
    except Exception:                       # an estimate that fails (an odd spec) keeps the old default: a flow table
        return False


def _walk(blocks, props, width_mm, body_h):
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if isinstance(b.get('table'), dict):
            t = b['table']
            if 'inline' not in t:
                t['inline'] = default_inline(t, {**props, **{k: v for k, v in b.items() if k not in ('table',)}}, width_mm, body_h,
                                             bool(b.get('same_para')))
            cell_props = {**props, **(t.get('cell') or {})}
            cols = t.get('cols') or []
            for row in t.get('rows') or t.get('cells') or []:
                cells = row.get('cells', []) if isinstance(row, dict) else row
                c = 0
                for cell in cells:
                    cs = int(cell.get('cs', 1)) if isinstance(cell, dict) else 1
                    if isinstance(cell, dict) and 'blocks' in cell:
                        w = sum(_mm(x) for x in cols[c:c + cs]) or width_mm
                        _walk(cell['blocks'], cell_props, w, body_h)
                    c += cs


def resolve(spec):
    """Set `inline` on every table of `spec` (body of every section, and the tables in their cells) that has none."""
    from ..core import read
    from ..core.units import PAPER
    base = {**read.DEF_CHAR, **read.DEF_PARA, **(spec.get('defaults') or {})}
    for sec in spec.get('sections') or [spec]:
        pg = dict(spec.get('page', {}), **sec.get('page', {}))
        size = pg.get('size', 'A4')
        w, h = PAPER[size.upper()] if isinstance(size, str) else size
        w, h = _mm(pg.get('width', w)), _mm(pg.get('height', h))
        land = bool(pg.get('landscape')) or w > h                # the paper turned: the long side is the width
        if w > h:
            w, h = h, w
        mg = dict(left=20, right=20, top=20, bottom=15, header=15, footer=15)
        mg.update(pg.get('margin', {}))
        mg = {k: _mm(v) for k, v in mg.items() if k in ('left', 'right', 'top', 'bottom', 'header', 'footer')}
        across, down = (h, w) if land else (w, h)
        body_h = down - mg['top'] - mg['bottom'] - mg['header'] - mg['footer']
        width = across - mg['left'] - mg['right']
        _walk(sec.get('body'), {**base, **(sec.get('defaults') or {})}, width, body_h)
