"""Track changes (변경 추적, run item `{"change": {"type", "t", ...}}`): inserted text in red with an underline, deleted text in
red with a strike line, text with a format change as plain text (fields/rules.md T03). Limits: the piece is one object, so a
long tracked passage does not wrap; the change bar in the left margin that Hangul draws is not drawn."""
import html

from ..measure import BASE, PT, cwidth, eff_size, face, fam
from ..svg import f3
from . import register

RED = '#FF0000'


def change(item, st):
    d = item.get('change', item)
    text, kind = str(d.get('t', '')), d.get('type', 'insert')
    s = eff_size(st, 0) * PT
    w = sum(cwidth(c, st) for c in text) * PT
    ink = RED if kind in ('insert', 'delete') else st['color']

    def draw(x, y):
        out = ['<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s"%s xml:space="preserve">%s</text>' % (
            f3(x), f3(y + s * BASE), html.escape(fam(face(st, 0)), quote=True), f3(s), ink,
            ' font-weight="bold"' if st.get('bold') else '', html.escape(text))]
        ly = y + s * (BASE + 0.12) if kind == 'insert' else y + s * 0.55
        if kind in ('insert', 'delete'):
            out.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
                f3(x), f3(ly), f3(x + w), f3(ly), ink, f3(s * 0.05)))
        return out
    return {'w': w, 'h': s, 'base': s * BASE, 'draw': draw}


register('change', change)
