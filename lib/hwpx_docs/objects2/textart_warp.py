"""글맵시 text warped into the shape (preview). Hangul fits the ink box of the text to the shape: a point of the unwarped box
(u, v in 0 ... 1) goes to F(u, v) = (1 - v) T(u) + v B(u), where the top curve T and the bottom curve B come from the measured blocks
of `textart_data` (every shape: 20 quadrilaterals; between two blocks the corners are interpolated). The viewer cuts the straight
text into N strips and puts each strip on the parallelogram of its corners (SVG clip + matrix): the error stays below the width of
a strip. Rules OB21.
"""
import itertools

from . import textart_data as TD

N = 64                                       # strips across the box
_ids = itertools.count(1)
# Hangul syllables, capitals, digits and the like: ink from this far above the baseline to this far below it (em; GDI of 함초롬바탕,
# estimated) and the same for letters with a descender; used to find the ink box of a text.
TOP, BOTTOM, DESC, ASC = 0.80, 0.09, 0.22, 0.82
DESCENDERS = set('gjpqy,;()[]{}Qµ')
LOWER_ONLY = set('acemnorsuvwxz')            # no ascender: the ink starts lower
X_TOP = 0.56


def ink_box(text):
    """(top, bottom) of the ink of a one-line text in em from the baseline: top is above (positive), bottom below."""
    top, bot = 0.0, 0.0
    for ch in text:
        if ch.isspace():
            continue
        t = X_TOP if ch in LOWER_ONLY else TOP
        b = DESC if ch in DESCENDERS else BOTTOM
        top, bot = max(top, t), max(bot, b)
    return (top or TOP), (bot or BOTTOM)


def nodes(shape):
    """[(u, (top x, top y), (bottom x, bottom y))] along the text, from the quads of the shape."""
    quads = TD.QUADS[shape]
    n = len(quads)
    span = n - 1 + TD.R
    out = []
    for k, (tl, tr, br, bl) in enumerate(quads):
        out.append((k / span, tl, bl))
        out.append(((k + TD.R) / span, tr, br))
    return out


def at(nds, u):
    """F(u, 0) and F(u, 1): the top and bottom point at u (linear between the nodes, kept at the ends)."""
    if u <= nds[0][0]:
        return nds[0][1], nds[0][2]
    for (ua, ta, ba), (ub, tb, bb) in zip(nds, nds[1:]):
        if u <= ub:
            f = (u - ua) / (ub - ua) if ub > ua else 0.0
            return ([ta[i] + f * (tb[i] - ta[i]) for i in (0, 1)], [ba[i] + f * (bb[i] - ba[i]) for i in (0, 1)])
    return nds[-1][1], nds[-1][2]


def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def svg(o, x, y):
    """The textart `o` (spec dict: text, shape, font, align, fill, shadow; w, h in mm) with the top-left corner of its box at (x, y)."""
    shape = str(o.get('shape', 'WAVE2')).upper()
    if shape not in TD.QUADS:
        return None
    w, h = o['w'], o['h']
    text = str(o.get('text', ''))
    if not text.strip():
        return []
    top, bot = ink_box(text)
    size = h / (top + bot)                                   # the ink box is as high as the shape
    base = top * size                                        # baseline below the top of the box
    font = str(o.get('font', '함초롬바탕'))
    fam = "'%s','Malgun Gothic',%s" % (font, 'serif' if ('바탕' in font or '명조' in font) else 'sans-serif')
    tid = next(_ids)
    txt = text.replace('&', '&amp;').replace('<', '&lt;')
    fill = o.get('fill', '#0000FF')
    body = (f'<text id="ta{tid}" x="0" y="{f3(base)}" font-family="{fam}" font-size="{f3(size)}" textLength="{f3(w)}" '
            f'lengthAdjust="spacingAndGlyphs">{txt}</text>')                 # the colour comes from the group around the strips
    nds = nodes(shape)
    out = [f'<defs>{body}']
    uses = []
    for j in range(N):
        ua, ub = j / N, (j + 1) / N
        (tax, tay), (bax, bay) = at(nds, ua)
        (tbx, tby), _ = at(nds, ub)
        du = (ub - ua) * w
        a, b = (tbx - tax) * w / du, (tby - tay) * h / du          # x axis of the strip: from the top-left to the top-right
        c, d = (bax - tax) * w / h, (bay - tay) * h / h            # y axis: from the top-left to the bottom-left
        # unwarped (px, py) in the box -> x + (tax*w) + a*(px - ua*w) + c*py, y + (tay*h) + b*(px - ua*w) + d*py
        e, f = x + tax * w - a * ua * w, y + tay * h - b * ua * w
        out.append(f'<clipPath id="tc{tid}_{j}"><rect x="{f3(ua * w - 0.02)}" y="{f3(-size)}" width="{f3(du + 0.06)}" height="{f3(h + 2 * size)}"/></clipPath>')
        uses.append(f'<g transform="matrix({a:.5f} {b:.5f} {c:.5f} {d:.5f} {f3(e)} {f3(f)})"><use href="#ta{tid}" clip-path="url(#tc{tid}_{j})"/></g>')
    out.append('</defs>')
    strips = ''.join(uses)
    res = [''.join(out)]
    sh = o.get('shadow')
    if sh:                                                    # the shadow: the same warped text in black, behind: LEFTTOP = the text is at
        dx = sh.get('x', 5) * h / 100 * (1 if sh.get('type') == 'left_top' else -1)      # the left top of its shadow (render: 20 % of the
        dy = sh.get('y', 5) * h / 100                                                    # height right and down)
        res.append(f'<g transform="translate({f3(dx)} {f3(dy)})" fill="#000000" stroke="#000000" stroke-width="{f3(size * 0.012)}">{strips}</g>')
    res.append(f'<g fill="{fill}" stroke="{fill}" stroke-width="{f3(size * 0.012)}">{strips}</g>')
    return res
