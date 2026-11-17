"""Preview drawing of the table extras (no Hangul): gradient and picture cell fills, caption, floating table.

The preview (`preview/layout.py`) calls these through two hooks that the preview owner adds (`drawers.paint`,
`drawers.table_wrap`; registered in `preview/drawers/table.py`):
  paint(ctx, page, fill, w, h) -> paint string for an SVG `fill` (a colour string comes back as it is)
  wrap(ctx, b, cst, w, layout_table, layout_para) -> atoms for a table block that has `caption` or `pos`, else None
Limits (written, not drawn): conical and square gradients are drawn as radial ones; the linear angle is the Hangul one for
0 (top to bottom) and 90 (left to right), 180 and 270 draw like 0 and 90, other angles are only close (S:cell_fill_gradient_angles);
`step` and `step_center` are not drawn; a 3-colour gradient is drawn with 3 stops (Hangul draws it black); a picture fill
without the picture file is a grey box; the horizontal and vertical alignment of a floating
table (`halign`, `valign`) is not applied (the table sits at its x and y offset); a floating table does not break across pages.
"""
import base64
import itertools
import math

_ids = itertools.count(1)
PT = 25.4 / 72
CAP_WIDTH_MM = 8504 * 25.4 / 7200        # Hangul's default caption width: 30 mm
IMG_MM = 25.4 / 96          # one picture pixel at 96 dpi (the builder's 75 hu per pixel)


def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def _png_size(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    return None


def _gradient(page, g):
    n = next(_ids)
    gid = f'tbg{n}'
    cols = g.get('colors') or ['#FFFFFF', '#000000']
    stops = ''.join('<stop offset="%s" stop-color="%s"/>' % (f3(i / max(len(cols) - 1, 1)), c) for i, c in enumerate(cols))
    kind = str(g.get('kind', 'linear')).lower()
    cx, cy = g.get('center', [0, 0])
    if kind == 'linear':
        a = math.radians(g.get('angle', 90) % 180)      # Hangul: 180 draws like 0 and 270 like 90 (S:cell_fill_gradient_angles)
        dx, dy = math.sin(a), math.cos(a)        # Hangul render (TB03): angle 90 = first colour left, last colour right
        x1, y1, x2, y2 = 0.5 - dx / 2, 0.5 - dy / 2, 0.5 + dx / 2, 0.5 + dy / 2
        page.svg.append('<defs><linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient></defs>' % (
            gid, f3(x1), f3(y1), f3(x2), f3(y2), stops))
    else:                      # radial; conical and square are drawn as radial (limit)
        page.svg.append('<defs><radialGradient id="%s" cx="%s" cy="%s" r="0.75">%s</radialGradient></defs>' % (
            gid, f3(cx / 100), f3(cy / 100), stops))
    return f'url(#{gid})'


def _image(ctx, page, im, w, h):
    uri = ctx.image(im['src'])
    if not uri:
        return '#D9D9D9'                       # no picture file: a grey box
    mode = str(im.get('mode', 'tile')).lower()
    data = base64.b64decode(uri.split(',', 1)[1]) if uri.startswith('data:image/png') else b''
    size = _png_size(data)
    tw, th = (size[0] * IMG_MM, size[1] * IMG_MM) if size else (w, h)
    if mode == 'total':
        tw, th, par = w, h, 'none'
    elif mode == 'zoom':
        tw, th, par = w, h, 'xMidYMid slice'
    else:                                      # tile and the placed modes: natural size (placed modes are tiled: limit)
        par = 'none'
    n = next(_ids)
    pid = f'tbi{n}'
    page.svg.append('<defs><pattern id="%s" patternUnits="objectBoundingBox" patternContentUnits="userSpaceOnUse" '
                    'width="%s" height="%s"><image width="%s" height="%s" preserveAspectRatio="%s" href="%s"/></pattern></defs>' % (
                        pid, f3(tw / w), f3(th / h), f3(tw), f3(th), par, uri))
    return f'url(#{pid})'


def paint_gradient(ctx, page, fill, w, h):
    return _gradient(page, fill)


def paint_image(ctx, page, fill, w, h):
    if 'src' not in fill:                      # nothing to paint with: the colour (if any) and the registry's warning line
        print('PREVIEW NOT DRAWN fill image %.1f x %.1f mm on page %s' % (w, h, getattr(page, 'no', '?')))
        return fill.get('color')
    return _image(ctx, page, fill, w, h)


def paint(ctx, page, fill, w, h):
    """The two painters by fill["type"] (what preview/drawers/table.py registers); a colour string comes back as it is."""
    if not isinstance(fill, dict):
        return fill
    fn = {'gradient': paint_gradient, 'image': paint_image}.get(fill.get('type'))
    return fn(ctx, page, fill, w, h) if fn else '#D9D9D9'


# ---- caption and floating table -----------------------------------------------------------------------------------------
def caption_text(ctx, cap):
    if isinstance(cap, str):
        cap = {'text': cap}
    label, text = cap.get('label', '표' if cap.get('number', True) else ''), cap.get('text', '')
    if not cap.get('number', True):
        return (label + ' ' if label else '') + text
    ctx.table_caps = getattr(ctx, 'table_caps', 0) + 1
    return (label + ' ' if label else '') + str(ctx.table_caps) + (' ' + text if text else '')


def _section(ctx):
    spec = getattr(ctx, 'spec', None) or {}
    secs = spec.get('sections')
    return secs[getattr(ctx, 'section', 0)] if secs else spec


class _Sub:
    """Stand-in for the page while a floating table draws itself: it only collects SVG."""

    def __init__(self, page_geometry=None):
        self.svg, self.notes, self.no, self.n, self.g = [], [], 0, 0, page_geometry or {}


# ---- wave and 3D line types (rules TB01; Hangul 300 dpi render of 1 mm lines, S:lines_wide) -------------------------------
def _zigzag_path(x1, y1, x2, y2, amp, period, shift=0.0):
    """Hangul's wave is a zigzag (a triangle wave), not a sine: vertices every half period, alternately +amp and -amp."""
    n = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    half = period / 2
    ts = sorted({0.0, n} | {j * half - shift for j in range(math.ceil(shift / half), math.floor((n + shift) / half) + 1)
                          if 0 < j * half - shift < n})
    pts = []
    for t in ts:
        ph = (t + shift) / half
        k = math.floor(ph)
        f = ph - k
        d = amp * ((1 - 2 * f) if k % 2 == 0 else (2 * f - 1))      # triangle between +amp and -amp
        pts.append('%s %s' % (f3(x1 + ux * t - uy * d), f3(y1 + uy * t + ux * d)))
    return 'M' + ' L'.join(pts)


def stroke_wave(page, x1, y1, x2, y2, w, col, double=False):
    """WAVE and DOUBLEWAVE. Measured on Hangul's 1 mm and 0.4 mm lines: WAVE = zigzag, period 1.2 + 0.8 w mm, half height
    0.18 + 0.16 w, stroke 0.1 + 0.15 w; DOUBLEWAVE = two zigzags half a period apart, so they cross in a chain of diamonds
    (diamond width about 2.5 mm, i.e. period 5 mm), half height 0.45 + 0.35 w, stroke 0.12 + 0.1 w."""
    if double:
        period, amp, lw, shifts = 5.0, 0.45 + 0.35 * w, 0.12 + 0.1 * w, (0.0, 2.5)
    else:
        period, amp, lw, shifts = 1.2 + 0.8 * w, 0.18 + 0.16 * w, 0.1 + 0.15 * w, (0.0,)
    for sh in shifts:
        page.svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="miter"/>' % (
            _zigzag_path(x1, y1, x2, y2, amp, period, sh), col, f3(lw)))


def stroke_doublewave(page, x1, y1, x2, y2, w, col):
    stroke_wave(page, x1, y1, x2, y2, w, col, double=True)


def stroke_none(page, x1, y1, x2, y2, w, col):
    """THICK3D, THICKREV3D, 3D, REV3D: Hangul draws nothing for these in a table cell border (300 dpi render, S:lines_wide)."""
    return None


def _beside(ctx, spec, side, cst, plain, atoms, layout_para, layout_table, text):
    """Atoms of a table with a caption on its left or right: the caption (its own width, default 30 mm) is drawn from the first
    row's top, the table is moved aside. Hangul: table edge = 1 mm + caption width + gap (3 mm) from the area's left edge."""
    cw = spec.get('width', CAP_WIDTH_MM)
    gap = spec.get('gap', 3.0) if isinstance(spec.get('gap', 3.0), (int, float)) else 3.0
    table_w = sum(plain['cols'])
    cap_atoms = layout_para(ctx, {'p': text, 'align': 'left', 'line': 100}, cst, cw, True)
    tx = cw + gap if side == 'left' else 0.0                # how far the table moves right (it keeps its own 1 mm margin)
    cx = 1.0 if side == 'left' else 1.0 + table_w + gap     # where the caption starts (from the left edge of the area)

    def emit(x, y, page):
        yy = y + 1.0                                        # the outer margin above the table
        for ca in cap_atoms:
            if ca.emit:
                ca.emit(x + cx, yy, page)
            yy += ca.h
        for a in atoms:
            if a.emit:
                a.emit(x + tx, y, page)
            y += a.h
    # Hangul (preview rules P18, kc_capl / kc_capr / kc_capm): a table with its caption beside it is never cut; one that does
    # not fit goes to the next page whole (one higher than a page runs past its bottom) and the text after it goes on under
    # the empty line of its paragraph: the preview flow reads `defer` (that line's height) on the row data `tbl`
    one = type(atoms[0])(sum(a.h for a in atoms), emit, atoms[-1].trail, atoms[0].keep, atoms[-1].absorb)
    T = getattr(atoms[0], 'tbl', None)
    if T is not None:
        one.tbl = dict(T, pb='none', atoms=[one], hdr=0, bad=set(), rep=set(),      # hold: it goes with its paragraph
                       defer=None if T.get('hold') else sum(a.h for a in layout_para(ctx, {'p': ''}, cst, cw)))
    return [one]


def wrap(ctx, b, cst, w, layout_table, layout_para, geometry=None):
    t = b['table']
    cap, pos = t.get('caption'), t.get('pos')
    if not cap and not pos:
        return None
    plain = {k: v for k, v in t.items() if k not in ('caption', 'pos')}
    if pos:                                    # a floating table: an object at its x, y like a floating picture
        # Hangul puts the outer margin (default 1 mm) between the offset and the table edge (S:table_pos_resaved_paper)
        tw, atoms = layout_table(ctx, dict(plain, margin=t.get('margin') or [1.0, 1.0, 1.0, 1.0]), cst, 1e9, inline=True)
        h = sum(a.h for a in atoms)

        def draw(x, y):
            sub = _Sub()
            for a in atoms:
                if a.emit:
                    a.emit(x, y, sub)
                y += a.h
            return sub.svg
        rel = pos.get('vrel', pos.get('rel', 'paper'))
        x, y = pos.get('x', 0), pos.get('y', 0)
        hrel = pos.get('hrel', pos.get('rel', 'paper'))
        if geometry and rel != 'para' and hrel != 'para':    # alignment and different references need the page: absolute x, y
            g = geometry(_section(ctx))
            bx = (0, g['w']) if hrel == 'paper' else (g['x0'], g['x1'])
            by = (0, g['h']) if rel == 'paper' else (g['y0'], g['y1'])    # page = the body area (S:table_pos_resaved_page_right_bottom)
            ha, va = pos.get('halign', 'left'), pos.get('valign', 'top')
            x += {'center': (bx[0] + bx[1] - tw) / 2, 'right': bx[1] - tw}.get(ha, bx[0])
            y += {'center': (by[0] + by[1] - h) / 2, 'bottom': by[1] - h}.get(va, by[0])
            rel = 'paper'
        shape = dict(type='object', obj={'w': tw, 'h': h, 'draw': draw, 'base': None, 'kind': 'drawn', 'name': 'table'}, x=x, y=y,
                     rel=rel, w=tw, h=h, wrap=t.get('wrap', 'top_and_bottom'), side=t.get('side', 'both_sides'))
        if rel == 'para' or hrel == 'para':    # placed from the anchor paragraph by the preview flow (preview rules P16)
            shape.update(hrel=hrel, halign=pos.get('halign', 'left'))
        return layout_para(ctx, {'p': '', 'shapes': [shape]}, cst, w)
    tw, atoms = layout_table(ctx, plain, cst, w, t.get('align', 'left'))
    if atoms and b.get('page_break'):
        atoms[0].keep = 'break'
    spec = cap if isinstance(cap, dict) else {'text': cap}
    gap_pt = (spec.get('gap', 3.0) if isinstance(spec.get('gap', 3.0), (int, float)) else 3.0) / PT
    side = str(spec.get('side', 'bottom')).lower()
    if side in ('left', 'right'):              # beside the table, level with its top row (S:table_caption_left)
        return _beside(ctx, spec, side, cst, plain, atoms, layout_para, layout_table, caption_text(ctx, cap))
    top = side == 'top'
    # Hangul (S:table_caption_top, S:table_caption): the caption starts at the table's outer margin (1 mm in and, on top, 1 mm down),
    # the line has no extra line spacing, and the bottom gap overlaps the table's own 1 mm outer margin
    mm_pt = 1 / PT
    para = {'p': caption_text(ctx, cap), 'align': 'left', 'line': 100, 'left': mm_pt}
    para.update({'before': mm_pt, 'after': max(gap_pt - mm_pt, 0)} if top else {'before': max(gap_pt - mm_pt, 0)})
    cap_atoms = layout_para(ctx, para, cst, sum(plain['cols']), False)
    T = getattr(atoms[0], 'tbl', None) if atoms else None
    if T is not None and not top:          # cut over pages, each part keeps room for the caption below it (preview P18, kc_capb*)
        T['foot'] = sum(a.h for a in cap_atoms) + (plain.get('margin') or [1.0] * 4)[3]
    return cap_atoms + atoms if top else atoms + cap_atoms
