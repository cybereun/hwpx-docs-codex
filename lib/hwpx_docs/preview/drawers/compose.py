"""글자 겹치기 (hp:compose, kept raw by the reader): the text in a circle, box or rhombus one character wide;
SHAPE_REVERSAL_* = filled shape with white text; CHAR = the characters only."""
import html
import re

from ..measure import PT, eff_size, face, fam
from ..svg import f3
from . import register_inline

SHAPES = {'CIRCLE': 'circle', 'RECTANGLE': 'rect', 'ROUNDED_RECTANGLE': 'rect', 'RHOMBUS': 'rhombus'}


def compose(xml, st):
    m = re.search(r'composeText="([^"]*)"', xml)
    sh = re.search(r'circleType="([^"]*)"', xml)
    text = html.unescape(m.group(1) if m else '')
    shape = sh.group(1) if sh else 'SHAPE_CIRCLE'
    s = eff_size(st, 0) * PT

    def draw(x, y):
        kind = shape.replace('SHAPE_', '').replace('REVERSAL_', '')
        rev = 'REVERSAL' in shape
        ink = st['color']
        cx, cy = x + s / 2, y + s / 2
        form = SHAPES.get(kind, None if kind == 'CHAR' else 'circle')
        attrs = 'fill="%s" stroke="%s" stroke-width="%s"' % (ink if rev else 'none', ink, f3(s * 0.06))
        out = []
        if form == 'circle':
            out.append('<circle cx="%s" cy="%s" r="%s" %s/>' % (f3(cx), f3(cy), f3(s * 0.46), attrs))
        elif form == 'rect':
            out.append('<rect x="%s" y="%s" width="%s" height="%s" %s/>' % (f3(x + s * 0.06), f3(y + s * 0.06), f3(s * 0.88),
                                                                          f3(s * 0.88), attrs))
        elif form == 'rhombus':
            out.append('<polygon points="%s,%s %s,%s %s,%s %s,%s" %s/>' % (
                f3(cx), f3(y), f3(x + s), f3(cy), f3(cx), f3(y + s), f3(x), f3(cy), attrs))
        size = s * (0.62 if len(text) == 1 else 0.5 if len(text) == 2 else 0.4)
        out.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="middle" '
                   'dominant-baseline="central">%s</text>' % (f3(cx), f3(cy), html.escape(fam(face(st, 1)), quote=True),
                                                              f3(size), '#FFFFFF' if rev else ink, html.escape(text)))
        return out
    return {'w': s, 'h': s, 'draw': draw, 'base': None}


register_inline('hp:compose', compose)
