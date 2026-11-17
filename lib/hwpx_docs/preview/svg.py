"""SVG writer of the preview: page elements (lines, rectangles) and the page document. Knows nothing about HWPX."""
import math


_min = [0.0]                           # thinnest stroke in mm: one pixel of the output dpi (set by flow.render_pages)


def set_min_line(v):
    _min[0] = v


def thin(w):
    return max(w, _min[0])


TEXT_STROKE = 0.05                     # mm outline: Hangul's 96 dpi glyphs are heavier than the plain glyph (ink difference 22.6 -> 21.7)


class Page:
    def __init__(self, n, no, g):
        self.n, self.no, self.g = n, no, g          # index, printed page number, geometry
        self.svg, self.notes = [], []
        self.lines = []        # body text lines placed on the page: [baseline y mm, x mm, column index] (line numbers)
        self.marks = set()     # marks that inline drawers left on the page (for example a page-hiding mark)


def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


EXTRA_STROKES = {}                  # {line type: fn(page, x1, y1, x2, y2, width mm, colour)}


def stroke(page, x1, y1, x2, y2, ln, ext=True):
    """A line with Hangul line type `ln` = (width mm, type, colour)."""
    w, t, col = ln
    w = thin(w)
    if t in EXTRA_STROKES:           # line types drawn by a feature package (wave, 3D: table/draw.py via drawers/table.py)
        return EXTRA_STROKES[t](page, x1, y1, x2, y2, w, col)
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    if ext and t not in ('dash', 'dot', 'dash_dot', 'dash_dot_dot', 'long_dash', 'circle'):
        x1, y1, x2, y2 = x1 - ux * w / 2, y1 - uy * w / 2, x2 + ux * w / 2, y2 + uy * w / 2
    dash = {'dash': (2, 2), 'dot': (1, 1.5), 'dash_dot': (4, 1.5, 1, 1.5), 'dash_dot_dot': (4, 1.5, 1, 1.5, 1, 1.5),
            'long_dash': (8, 3), 'circle': (0.1, 2)}.get(t)
    if t in ('double', 'double_slim', 'slim_thick', 'thick_slim', 'slim_thick_slim'):
        k = {'double': (1, 1), 'double_slim': (1, 1), 'slim_thick': (1, 2), 'thick_slim': (2, 1),
             'slim_thick_slim': (1, 2, 1)}[t]
        total = sum(k) + len(k) - 1
        unit = w / total
        off = -w / 2
        for part in k:
            wd = unit * part
            c = off + wd / 2
            page.svg.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
                f3(x1 - uy * c), f3(y1 + ux * c), f3(x2 - uy * c), f3(y2 + ux * c), col, f3(max(wd, _min[0] / 2))))
            off += wd + unit
        return
    d = ' stroke-dasharray="%s"' % ' '.join(f3(v * w) for v in dash) if dash else ''
    page.svg.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s/>' % (
        f3(x1), f3(y1), f3(x2), f3(y2), col, f3(w), d))


def rect(page, x, y, w, h, fill=None, ln=None, rx=0):
    a = ' rx="%s"' % f3(rx) if rx else ''
    page.svg.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"%s%s/>' % (
        f3(x), f3(y), f3(w), f3(h), fill or 'none',
        ' stroke="%s" stroke-width="%s"' % (ln[2], f3(thin(ln[0]))) if ln else '', a))


def page_svg(pg):
    g = pg.g
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%smm" height="%smm" '
            'style="background:#fff;white-space:pre;display:block">\n<rect width="%s" height="%s" fill="#fff"/>\n%s\n</svg>' % (
                f3(g['w']), f3(g['h']), f3(g['w']), f3(g['h']), f3(g['w']), f3(g['h']), '\n'.join(pg.svg)))
