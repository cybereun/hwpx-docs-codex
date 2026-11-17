"""Page layout features of the package `pagex` (rules PX01-PX11): odd/even header and footer, 바탕쪽, line numbers,
hiding header/footer/page number/border/fill on one page. Page layers (register_page_layer) and the page-hiding mark
(register_inline for the raw `hp:ctrl` that holds `hp:pageHiding`).

Not drawn (written limits, PX05, PX07, PX10): vertical writing, text in manuscript cells (원고지 grid), the column change
inside a page: they change how lines are placed, which a layer cannot do.
"""
import re

from ...core import read as rd
from ..layout import layout_blocks
from ..measure import PT
from ..svg import f3
from . import register_inline, register_page_layer, _INLINE

HIDE = {'hideHeader': 'hide_header', 'hideFooter': 'hide_footer', 'hideMasterPage': 'hide_master', 'hideBorder': 'hide_border',
        'hideFill': 'hide_fill', 'hidePageNum': 'hide_pagenum'}


def captured(page, atoms, x, y):
    """Elements that the atoms draw at (x, y), without adding them to the page (a layer returns its elements)."""
    saved, page.svg = page.svg, []
    try:
        for a in atoms:
            if a.emit:
                a.emit(x, y, page)
            y += a.h
        return page.svg
    finally:
        page.svg = saved


def white(x, y, w, h):
    return '<rect x="%s" y="%s" width="%s" height="%s" fill="#FFFFFF"/>' % (f3(x), f3(y), f3(w), f3(h))


# ---- master pages (바탕쪽) ----------------------------------------------------------------------------------------------
def masters_of(info):
    """The master pages of the section that apply to this page, most specific first (a specific kind replaces BOTH;
    a master with `duplicate` also shows the one under it)."""
    ms = info['spec'].get('master_pages') or []
    by = {}
    for m in ms:
        by[m.get('type', 'both')] = m
    order = [('optional', lambda m: m.get('page') == info['no']), ('last', lambda m: info['is_last']),
             ('odd' if info['odd'] else 'even', lambda m: True), ('both', lambda m: True)]
    chosen = [by[t] for t, ok in order if t in by and ok(by[t])]
    out = []
    for m in chosen:
        out.append(m)
        if not m.get('duplicate'):
            break
    return out


def master_layer(front):
    def layer(ctx, page, info):
        if 'hide_master' in page.marks:
            return []
        x0, y0, x1, _ = info['body']
        out = []
        for m in reversed(masters_of(info)):
            if bool(m.get('front')) == front:
                out += captured(page, layout_blocks(ctx, m.get('body') or [], dict(rd.DEF_CHAR), x1 - x0), x0, y0)
        return out
    return layer


# ---- odd/even header and footer -----------------------------------------------------------------------------------------
def hf_layer(ctx, page, info):
    sec, m = info['spec'], info['margin']
    x0, _, x1, _ = info['body']
    out = []
    for kind, zone in (('header', m['top']), ('footer', info['size'][1] - m['bottom'] - m['footer'])):
        if 'hide_' + kind in page.marks:
            continue
        blocks = sec.get('%s_%s' % (kind, 'odd' if info['odd'] else 'even'))
        if blocks:
            atoms = layout_blocks(ctx, blocks, dict(rd.DEF_CHAR), x1 - x0)
            if kind == 'footer':                       # a footer sits at the bottom of its zone (vertAlign BOTTOM, PX01)
                zone += m['footer'] - sum(a.h for a in atoms)
            out += captured(page, atoms, x0, zone)
    return out


def hide_layer(ctx, page, info):
    """Cover what the page hides: the header, footer and page number that the flow already drew (a white box)."""
    hid = page.marks
    if not hid & {'hide_header', 'hide_footer', 'hide_pagenum', 'hide_border', 'hide_fill'}:
        return []
    sec, m = info['spec'], info['margin']
    w, h = info['size']
    out = []
    pn = sec.get('page_number')
    pn_h = rd.DEF_CHAR['size'] * 1.6 * PT                      # the page number line (flow.py)
    pn_top = pn and (pn.get('pos', 'bottom_center').startswith('top'))
    ztop, zbot = m['top'], h - m['bottom'] - m['footer']
    if 'hide_header' in hid:
        y = ztop + (pn_h if pn_top else 0)
        out.append(white(0, y, w, m['header'] - (pn_h if pn_top else 0)))
    if 'hide_footer' in hid:
        out.append(white(0, zbot, w, m['footer'] - (0 if pn_top or not pn else pn_h)))
    if 'hide_pagenum' in hid and pn:
        y = ztop if pn_top else h - m['bottom'] - pn_h
        out.append(white(0, y, w, pn_h))
    pb = sec.get('page_border')
    if pb and hid & {'hide_border', 'hide_fill'}:              # the border box is drawn under the page: white over it
        o = pb.get('offset', 5)
        o = o if isinstance(o, list) else [o] * 4
        base = (0, 0, w, h) if pb.get('text_border', 'paper') == 'paper' else (m['left'], m['top'], w - m['right'], h - m['bottom'])
        x0, y0, x1, y1 = base[0] + o[0], base[1] + o[2], base[2] - o[1], base[3] - o[3]
        if 'hide_fill' in hid and pb.get('fill'):
            out.append(white(x0, y0, x1 - x0, y1 - y0))
        if 'hide_border' in hid:
            for a, b, c, d in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
                out.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="#FFFFFF" stroke-width="1.2"/>' % (f3(a), f3(b), f3(c), f3(d)))
    return out


# ---- line numbers ---------------------------------------------------------------------------------------------------------
def line_number_layer(ctx, page, info):
    """A number left of every body line; `distance` is from the text to the right edge of the number (PX06).
    restart: 0 = every page, 1 = every section, 2 = continuous (an assumption until a two-page sample shows it)."""
    ln = info['spec'].get('line_numbers')
    if not ln:
        return []
    start, by = int(ln.get('start', 1)), max(1, int(ln.get('count_by', 1)))
    restart = int(ln.get('restart', 0))
    st = ctx.__dict__.setdefault('pagex_lines', {'next': start})
    if restart == 0 or (restart == 1 and info['first']):
        st['next'] = start
    out = []
    for y, x, _col in page.lines:
        n = st['next']
        st['next'] += 1
        if n % by == 0:
            out.append('<text x="%s" y="%s" font-family="\'Malgun Gothic\',sans-serif" font-size="%s" fill="#000000" '
                       'text-anchor="end">%d</text>' % (f3(x - ln.get('distance', 0)), f3(y), f3(8 * PT), n))
    return out


# ---- manuscript paper (원고지) -------------------------------------------------------------------------------------------
def manuscript_note(ctx, page, info):
    """Hangul puts each character into a grid cell (charGrid x lineGrid, PX07) and draws no grid line in its page image;
    the preview does not place text in cells, so say so once per section (never a silent difference)."""
    sec = info['spec']
    if (sec.get('manuscript') or sec.get('char_grid') or sec.get('line_grid')) and info['first']:
        print('PREVIEW NOT DRAWN manuscript grid (text is not placed in cells) on page %s' % page.no)
    return []


# ---- page hiding mark ---------------------------------------------------------------------------------------------------
def hiding_mark(xml, st):
    """`hp:ctrl` with `hp:pageHiding` (kept raw by the reader): no room, only marks for the page layers."""
    m = re.search(r'<hp:pageHiding\b([^>]*)>', xml)
    if not m:
        return _PREVIOUS(xml, st) if _PREVIOUS else None
    return {'w': 0, 'h': 0, 'draw': None, 'marks': {v for k, v in HIDE.items() if re.search(r'\b%s="1"' % k, m.group(1))}}


_PREVIOUS = _INLINE.get('hp:ctrl')           # another module may draw other `hp:ctrl` items: ask it for those
register_inline('hp:ctrl', hiding_mark)
register_page_layer(master_layer(False), 'under')
register_page_layer(hf_layer, 'under')
register_page_layer(master_layer(True), 'over')
register_page_layer(hide_layer, 'over')
register_page_layer(line_number_layer, 'over')
register_page_layer(manuscript_note, 'over')
