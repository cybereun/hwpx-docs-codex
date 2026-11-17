"""수식 (hp:equation, spec run {"equation": {script, size, color}}): drawn by preview/equation/ as vector shapes.
A script that fails (a safety net: every command of the Hangul help is drawn) is written as plain text and prints one
`WARN preview: equation drawn as text` line."""
from .. import equation
from ..equation import layout as eq_layout
from ..measure import BASE, PT
from ..svg import f3
from . import register


def draw_equation(item, style):
    script = item.get('script', '')
    size = item.get('size') or style['size']
    color = item.get('color') or '#000000'
    eq = equation.render(script, size, color)
    if eq.ok:
        w, a, d, svg = eq.w, eq.a, eq.d, eq.svg
    else:
        print('WARN preview: equation drawn as text (%s): %s' % ('; '.join(eq.warns), script[:60]))
        box = eq_layout.text_box(script.replace('\n', ' '), size * equation.PT_MM, {'rm': True, 'bold': False}, color)
        w, a, d = box.w, box.a, box.d
        svg = eq_layout.to_svg(eq_layout.shift(box.p, 0.0, box.a), 0.265)
    # Hangul puts the top of the equation TOP_GAP em below the top of its line, whatever the height (rules E18)
    off = equation.TOP_GAP * size * equation.PT_MM
    h = off + a + d
    base = BASE * max(style['size'] * PT, h) - off      # the line puts the object at y + BASE * line height - base = y + off

    def draw(x, y):
        return ['<g transform="translate(%s,%s)">%s</g>' % (f3(x), f3(y), svg)]
    return {'w': w, 'h': h, 'base': base, 'draw': draw}


register('equation', draw_equation)
