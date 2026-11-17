"""문단 첫 글자 장식 (run item `{"dropcap": {"char", "lines", "font", "color", "frame", "fill"}}`): the character, as big as 2 or 3
lines, in a frame when it has one. Approximation (textstyle/rules.md TS21): the object is an inline one, so the first line is as
tall as the character and the text does not wrap around it (the preview has no square wrap)."""
import html

from ..measure import BASE, PT, cwidth, eff_size, face, fam, parse_line
from ..svg import f3
from . import register

LINES = {2: 2, 3: 3, 'margin': 3}


def dropcap(item, st):
    d = item.get('dropcap', item)
    n = LINES.get(d.get('lines', 2), 2)
    size = eff_size(st, 0)
    box = ((n - 1) * size * (st.get('line', 160) if not isinstance(st.get('line', 160), dict) else 160) / 100 + size) * PT
    ch = str(d.get('char', ''))
    big = dict(st, size=box / PT)
    w = max(sum(cwidth(c, big) for c in ch) * PT, box * 0.6)

    def draw(x, y):
        out = []
        if d.get('fill') or d.get('frame'):
            fill = d.get('fill') or 'none'
            ln = parse_line(d['frame']) if d.get('frame') else None
            stroke = 'stroke="%s" stroke-width="%s"' % (ln[2], f3(ln[0])) if ln else ''
            out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" %s/>' % (f3(x), f3(y), f3(w), f3(box), fill, stroke))
        out.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="middle">%s</text>' % (
            f3(x + w / 2), f3(y + box * BASE), html.escape(fam(d.get('font') or face(st, 0)), quote=True), f3(box),
            d.get('color') or st['color'], html.escape(ch)))
        return out
    return {'w': w, 'h': box, 'base': box * BASE, 'draw': draw}


register('dropcap', dropcap)
