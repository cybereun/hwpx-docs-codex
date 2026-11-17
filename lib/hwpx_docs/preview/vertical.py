"""세로쓰기 (a section with text_direction "vertical" or "vertical_all", hp:secPr textDirection): Hangul lays the text
out as on the page turned a quarter turn clockwise (rules P14, measured on the page session's samples vertical_B,
vertical_head_B and vt_*): lines run top to bottom and stack from the right to the left; Hangul letters stand upright.

  render(ctx, sec, first_no)      the one call of flow.render_pages for a vertical section
  virtual_section(sec)            -> (section on the turned page, paper geometry)
  to_paper(ctx, pages, sec, paper) the turned pages back onto the paper

Margins: the first line touches the paper's right side at the top margin; a line runs from left margin + header to
paper height - right margin - footer. With vertical_head (textVerticalWidthHead=1) the header and the footer take room
on the right and the left instead. Latin letters, digits, ASCII punctuation and CJK brackets lie on their side in
"vertical"; in "vertical_all" letters and digits stand upright, each in a full cell. Tables and pictures are NOT turned:
they stand as on a normal page and take their width across the lines. Header, footer, page number and page border are
drawn as on a normal page (horizontal, at the paper's top and bottom).
"""
import html
import re

from ..core import read as rd
from ..core import textfit
from . import drawers
from .measure import PT, lang
from .svg import Page, f3

TURN = 'matrix(0 1 -1 0 %s 0)'          # turned page (x, y) -> paper (W - y, x)
UPRIGHT = '<g data-upright="1">'         # SVG already in paper coordinates (tables, pictures)
BRACKETS = set('「」『』〈〉《》【】〔〕（）［］｛｝')
STOPS = {'.': '。', ',': '、'}
_ctx = [None]


def render(ctx, sec, first_no):
    from .flow import render_section
    n0 = len(ctx.pages)
    vsec, paper = virtual_section(sec)
    _ctx[0], ctx.vertical = ctx, paper
    try:
        render_section(ctx, vsec, first_no)
    finally:
        ctx.vertical = None
    to_paper(ctx, ctx.pages[n0:], sec, paper)


def _upright_pics(blocks):
    """Pictures of the body (blocks and runs, not inside tables) as upright objects: on the turned page they take their
    height along the line and their width across the lines."""
    def one(x):
        if isinstance(x, dict) and isinstance(x.get('pic'), dict):
            p = x['pic']
            up = {'w': p['h'], 'h': p['w'], 'pic': p}
            if p.get('inline', True) is False:      # floating: upright too; its offsets are taken on the turned page
                up.update(inline=False, pos=p['pos'], wrap=p.get('wrap', 'top_and_bottom'), side=p.get('side', 'both_sides'))
            return dict({k: v for k, v in x.items() if k != 'pic'}, upright_pic=up)
        return x
    out = []
    for b in blocks:
        b = one(b)
        if isinstance(b, dict) and isinstance(b.get('p'), list):
            b = dict(b, p=[one(r) for r in b['p']])
        out.append(b)
    return out


def virtual_section(sec):
    from .flow import geometry
    g = geometry(sec)
    head = bool(sec.get('vertical_head'))
    m = {k: g[k] for k in ('left', 'right', 'top', 'bottom', 'header', 'footer')}
    vm = dict(left=m['left'] + (0 if head else m['header']), right=m['right'] + (0 if head else m['footer']),
              top=m['top'], bottom=m['bottom'], header=m['header'] if head else 0, footer=m['footer'] if head else 0,
              gutter=0)
    page = dict(sec.get('page') or {}, size=[g['h'], g['w']], landscape=False, margin=vm)
    # vertical_head: header, footer and page number are written down the page like the text (vt2_head_hf): laid out
    # on the turned page, the footer and page number at the bottom of the footer room (one 100 % line)
    drop = ('page_border', 'body') if head else ('header', 'footer', 'page_number', 'page_border', 'body')
    vsec = {k: v for k, v in sec.items() if k not in drop}
    vsec.update(page=page, body=_upright_pics(sec.get('body', [])), _upright=sec.get('text_direction') == 'vertical_all',
                _frame_low=head, _vcell=True)
    return vsec, g


def _place(x, y, vw, vh):
    """Top-left corner on the paper of an upright object whose box on the turned page is (x, y, vw along the line,
    vh across the lines)."""
    W = _ctx[0].vertical['w']
    return W - (y + vh), x


def upright_pic(item, st):
    def draw(x, y):
        from .layout import emit_pic
        px, py = _place(x, y, item['w'], item['h'])
        pg = Page(0, 0, {})
        emit_pic(_ctx[0], item['pic'], px, py, pg)
        return [UPRIGHT + ''.join(pg.svg) + '</g>']
    return {'w': item['w'], 'h': item['h'], 'base': None, 'draw': draw}


def upright_table(ctx, b, st, w, layout_table, layout_para):
    """A table in a vertical section: laid out as on a normal page, one atom as thick as the table is wide. A table
    with `pos` floats upright like a picture: offsets on the turned page, its edge one outer margin in (vt2_table_para)."""
    if not getattr(ctx, 'vertical', None):
        return None
    from .layout import A
    t = b['table']
    if t.get('pos'):
        plain = {k: v for k, v in t.items() if k not in ('caption', 'pos')}
        tw, rows = layout_table(ctx, dict(plain, margin=t.get('margin') or [1.0, 1.0, 1.0, 1.0]), st, 1e9, inline=True)
        th = sum(a.h for a in rows)

        def draw(x, y):
            px, py = _place(x, y, th, tw)
            pg = Page(0, 0, {})
            for a in rows:
                if a.emit:
                    a.emit(px, py, pg)
                py += a.h
            return [UPRIGHT + ''.join(pg.svg) + '</g>']
        pos = t['pos']
        obj = {'w': th, 'h': tw, 'draw': draw, 'base': None, 'kind': 'drawn', 'name': 'table'}
        shape = dict(type='object', obj=obj, x=pos.get('x', 0), y=pos.get('y', 0), rel=pos.get('vrel', pos.get('rel', 'para')),
                     w=th, h=tw, wrap=t.get('wrap', 'top_and_bottom'), side=t.get('side', 'both_sides'))
        return layout_para(ctx, {'p': '', 'shapes': [shape]}, st, w)
    tw, atoms = layout_table(ctx, t, st, 1e9)
    th = sum(a.h for a in atoms)

    def emit(x, y, page):
        px, py = _place(x, y, th, tw)
        pg = Page(0, page.no, page.g)
        for a in atoms:
            a.emit(px, py, pg)
            py += a.h
        page.svg.append(UPRIGHT + ''.join(pg.svg) + '</g>')
    return [A(tw, emit)]


drawers.register('upright_pic', upright_pic)
drawers.register_table_wrap(upright_table, first=True)      # before the floating-table wrapper of the table package


def _family(attrs):
    return (attrs.get('font-family', '') or 'serif').split(',')[0].strip("'\" ") or 'serif'


def _turned(ch, mode):
    return ch in BRACKETS or (mode == 'vertical' and lang(ch) == 1)


def _text(e, W, mode):
    """One <text> of the turned page -> letters on the paper (one <text> per letter, centred on its cell)."""
    m = re.match(r'<text ([^>]*)>(.*)</text>$', e, re.S)
    if not m:
        return '<g transform="%s">%s</g>' % (TURN % f3(W), e)
    attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1)))
    chars = html.unescape(m.group(2))
    xs = [float(v) for v in attrs.get('x', '0').split()]
    y, size = float(attrs.get('y', 0)), float(attrs.get('font-size', 3.5))
    keep = ' '.join('%s="%s"' % (k, v) for k, v in attrs.items()
                    if k not in ('x', 'y', 'text-anchor', 'dominant-baseline', 'transform'))
    if len(xs) == 1 and len(chars) > 1:     # a label with one anchor (chart, placeholder): upright at the turned anchor
        return '<text x="%s" y="%s" %s text-anchor="%s" dominant-baseline="central">%s</text>' % (
            f3(W - y), f3(xs[0]), keep, attrs.get('text-anchor', 'start'), html.escape(chars, quote=False))
    out, fam = [], _family(attrs)
    bold = attrs.get('font-weight') == 'bold'
    for i, ch in enumerate(chars):
        if ch == ' ' or i >= len(xs):
            continue
        if ch in STOPS:                     # Hangul writes . , as 。、 upright at the top right of a full cell (vt_punct)
            px, py = W - (y - 0.35 * size) + 0.5 * size, xs[i] + 0.5 * size - 0.5 * size
            out.append('<text x="%s" y="%s" %s text-anchor="middle" dominant-baseline="central">%s</text>' % (
                f3(px), f3(py), keep, STOPS[ch]))
            continue
        cell = size if lang(ch) == 0 or mode == 'vertical_all' and lang(ch) != 0 else textfit.gdi().em(ch, fam, bold) * size
        px, py = W - (y - 0.35 * size), xs[i] + cell / 2
        out.append('<text x="%s" y="%s" %s text-anchor="middle" dominant-baseline="central"%s>%s</text>' % (
            f3(px), f3(py), keep, ' transform="rotate(90 %s %s)"' % (f3(px), f3(py)) if _turned(ch, mode) else '',
            html.escape(ch, quote=False)))
    return '<g>%s</g>' % ''.join(out)


def to_paper(ctx, pages, sec, paper):
    """Turn the pages that the flow laid out on the turned page back onto the paper, in place (one element for one,
    so page layer positions stay), then add the page border, header, footer and page number as on a normal page."""
    from .flow import page_border, page_frame
    W, mode = paper['w'], sec.get('text_direction', 'vertical')
    for pg in pages:
        vg = pg.g
        pg.svg[:] = [e if e.startswith(UPRIGHT) else _text(e, W, mode) if e.startswith('<text')
                     else '<g transform="%s">%s</g>' % (TURN % f3(W), e) for e in pg.svg]
        pg.g, pg.lines = paper, []
        under = Page(pg.n, pg.no, paper)
        page_border(ctx, under, sec, paper)
        pg.svg[0:0] = under.svg
        pg.under_at = getattr(pg, 'under_at', 0) + len(under.svg)
        # header, footer, page number stay horizontal; on the turned page's sides (P14, measured on vt_pages): x from the
        # bottom margin to paper width - top margin; header at the left margin from the top; footer and page number
        # end at paper height - right margin
        cs = dict(rd.DEF_CHAR)
        frame = dict(paper, x0=paper['bottom'], x1=W - paper['top'])
        low = paper['h'] - paper['right'] - cs['size'] * PT
        if not sec.get('vertical_head'):                # vertical_head: written down the turned page (virtual_section)
            page_frame(ctx, pg, sec, frame, cs, zones=(paper['left'], low, low))
        x0, y0, x1, y1 = vg['x0'], vg['y0'], vg['x1'], vg['y1']
        pg.info.update(vertical=mode, size=(paper['w'], paper['h']), body=(W - y1, x0, W - y0, x1),
                       margin={k: paper[k] for k in ('left', 'right', 'top', 'bottom', 'header', 'footer', 'gutter')})
