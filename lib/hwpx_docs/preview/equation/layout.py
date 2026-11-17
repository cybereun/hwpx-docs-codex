"""Layout of a parsed equation: boxes in mm and SVG primitives. A box has a width `w`, an ascent `a` (above the baseline), a
descent `d` and primitives with coordinates relative to its left edge and baseline (y down). The numbers in `M` are the
measured metrics of the Hangul equation editor (rules.md E09-E20); sizes are fractions of the current font size.
"""
import math
from ...core import textfit
from . import symbols as sy

FONT = 'HancomEQN'
FALLBACK = "'Cambria Math','Times New Roman','함초롬바탕',serif"
M = dict(
    script=0.65,         # sub and superscript size
    sup_up=0.42,         # minimum rise of a superscript
    sub_dn=0.20,         # minimum drop of a subscript
    axis=0.25,           # height of the fraction bar and of operator centres above the baseline
    frac_gap=0.27,       # bar to numerator / denominator
    frac_pad=0.10,       # bar overhang on each side
    bar=0.04,            # fraction bar and root bar thickness
    big=1.5,             # sum and product glyph size
    bigset=1.25,         # union and intersection glyph size
    bigint=2.15,         # integral glyph size
    limit_gap=0.10,      # big operator to its limits
    col_gap=0.30,        # matrix column gap
    row_gap=0.30,        # matrix row gap
    bracket_w=0.30,      # bracket width (small)
    space=0.5,           # tilde: width of a blank
    op_pad=0.15,         # room added on each side of a relation (= < > arrows ...)
    op_pad_bin=0.10,     # ... and of a binary operator (+ - times ...)
    int_lsb=0.21,        # left room of the integral sign, in sign sizes
    row_a=0.78,          # a stacked row is at least this high above the baseline ...
    row_d=0.27,          # ... and this deep below it
    limit_scale=0.65,    # size of the limits of a big operator
    lim_scale=1.2,       # size of the word lim
    sladder=0.92,        # size of the sladder text
    radical=0.55,        # width of the radical sign
    pile_gap=0.10,       # pile: extra room between rows
    ladder_gap=0.20,     # ladder: column gap
    ladder_row=0.50,     # ladder: extra room between rows (the rungs)
    div_row=1.12,        # longdiv: row pitch
)


class Box:
    __slots__ = ('w', 'a', 'd', 'p')

    def __init__(self, w=0.0, a=0.0, d=0.0, p=None):
        self.w, self.a, self.d, self.p = w, a, d, p if p is not None else []


def shift(prims, dx, dy):
    out = []
    for q in prims:
        t = q[0]
        if t == 't':
            out.append(('t', q[1] + dx, q[2] + dy) + q[3:])
        elif t == 'l':
            out.append(('l', q[1] + dx, q[2] + dy, q[3] + dx, q[4] + dy) + q[5:])
        elif t == 'p':
            out.append(('p', [(c, [(x + dx, y + dy) for x, y in pts]) for c, pts in q[1]]) + q[2:])
        elif t == 'r':
            out.append(('r', q[1] + dx, q[2] + dy) + q[3:])
    return out


def place(box, dx, dy):
    """Primitives of `box` moved by (dx, dy)."""
    return shift(box.p, dx, dy)


# ---- glyph metrics -------------------------------------------------------------------------------------------------
LOWER_ASC = set('bdfhklt')
DESC = set('gjpqy')
TALL = set('()[]{}|/\\⟨⟩⌈⌉⌊⌋')


def is_cjk(ch):
    return ord(ch) >= 0x2E80


def adv(ch, size):
    """Advance width of a character in mm."""
    if is_cjk(ch):
        return size
    return textfit.gdi().em(ch, FONT, False) * size


def extent(ch):
    """(ascent, descent) of a glyph in em."""
    if ch in 'xzaceimnorsuvw':
        return 0.47, 0.0
    if ch in DESC:
        return 0.47, 0.22
    if ch in LOWER_ASC or ch.isupper() or ch.isdigit():
        return 0.72, 0.0
    if ch in TALL:
        return 0.78, 0.22
    if ch in 'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ':
        return 0.72, 0.0
    if ch in 'αεικνοπστυω':
        return 0.47, 0.0
    if ch in 'βγδζηθλξρφχψϑϕ':
        return 0.72, 0.22
    if ch in ',;':
        return 0.1, 0.18
    if ch in '.':
        return 0.1, 0.0
    if ch in '+−=±∓×÷<>≤≥≠≈≡→←↔⇒⇐⇔':
        return 0.55, 0.0
    if is_cjk(ch):
        return 0.8, 0.12
    return 0.72, 0.1


def text_box(s, size, st, color, italic_ok=True):
    """One text prim for a run of characters with the same style."""
    xs, x = [], 0.0
    for ch in s:
        xs.append(x)
        x += adv(ch, size)
    a = max((extent(c)[0] for c in s), default=0.5) * size
    d = max((extent(c)[1] for c in s), default=0.0) * size
    italic = italic_ok and not st['rm'] and all(c.isascii() and c.isalpha() for c in s)
    return Box(x, a, d, [('t', 0.0, 0.0, s, xs, size, italic, st['bold'], color)])


def hcat(boxes):
    out, x, a, d = [], 0.0, 0.0, 0.0
    for b in boxes:
        out += shift(b.p, x, 0.0)
        x += b.w
        a, d = max(a, b.a), max(d, b.d)
    return Box(x, a, d, out)


def vline(x, y1, y2, wd, color):
    return ('l', x, y1, x, y2, wd, color)


def hline(x1, x2, y, wd, color):
    return ('l', x1, y, x2, y, wd, color)


# ---- layout of nodes -----------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, color):
        self.color = color
        self.warns = []


def lay(node, size, cx, dim=1.0):
    """Node -> Box. `size` is the current font size in mm (before the style's own scale)."""
    t = node[0]
    fn = LAYOUT.get(t)
    if fn is None:
        cx.warns.append('not drawn: %s' % t)
        return Box()
    return fn(node, size, cx)


def l_row(node, size, cx):
    items = node[1]
    if any(n[0] == 'br' for n in items):                 # lines: left aligned stack
        rows, cur = [], []
        for n in items:
            if n[0] == 'br':
                rows.append(('row', cur))
                cur = []
            else:
                cur.append(n)
        rows.append(('row', cur))
        return stack([lay(r, size, cx) for r in rows], size, 'left', 0.2)
    return hcat([lay(n, size, cx) for n in items if n[0] != 'tab'])


def l_txt(node, size, cx):
    _, s, st = node
    sz = size * st['scale'] / 100
    b = text_box(s, sz, st, cx.color)
    if len(s) == 1 and (s in sy.RELATIONS or s in sy.BINARY):          # room around an operator (E16)
        pad = M['op_pad' if s in sy.RELATIONS else 'op_pad_bin'] * sz
        return Box(b.w + 2 * pad, b.a, b.d, shift(b.p, pad, 0.0))
    return b


def l_sp(node, size, cx):
    return Box(node[1] * M['space'] * size)


def l_frac(node, size, cx):
    _, n, dn, bar = node
    nb, db = lay(n, size, cx), lay(dn, size, cx)
    ax, gap = M['axis'] * size, M['frac_gap'] * size
    w = max(nb.w, db.w) + 2 * M['frac_pad'] * size
    ny, dy = -ax - gap - nb.d, -ax + gap + db.a
    prims = shift(nb.p, (w - nb.w) / 2, ny) + shift(db.p, (w - db.w) / 2, dy)
    if bar:
        prims.append(hline(0.0, w, -ax, max(M['bar'] * size, 0.0), cx.color))
    return Box(w, -ny + nb.a, dy + db.d, prims)


def l_sqrt(node, size, cx):
    _, body, idx = node
    b = lay(body, size, cx)
    top = -(b.a + 0.15 * size)
    bot = b.d + 0.05 * size
    rw = M['radical'] * size
    h = bot - top
    ib = lay(idx, size * 0.6, cx) if idx is not None else Box()
    x0 = max(0.0, ib.w - 0.25 * size)
    pts = [(x0, top + 0.58 * h), (x0 + 0.12 * size, top + 0.52 * h), (x0 + 0.26 * size, bot), (x0 + rw - 0.02 * size, top)]
    prims = [('p', [('M', [pts[0]]), ('L', pts[1:]), ('L', [(x0 + rw + b.w + 0.1 * size, top)])], max(M['bar'] * size, 0.0), cx.color, 'none')]
    prims += shift(ib.p, x0 + 0.02 * size - ib.w * 0.0, top + 0.35 * h - ib.d) if idx is not None else []
    prims += shift(b.p, x0 + rw, 0.0)
    return Box(x0 + rw + b.w + 0.1 * size, -top, b.d, prims)


def l_script(node, size, cx):
    _, base, sub, sup = node
    bb = lay(base, size, cx)
    big = base[0] == 'big'
    ss = size * (M['limit_scale'] if big and base[2] else M['script'])
    sb = lay(sub, ss, cx) if sub is not None else None
    pb = lay(sup, ss, cx) if sup is not None else None
    if big and base[2]:                                  # limits above and below
        w = max(bb.w, sb.w if sb else 0, pb.w if pb else 0)
        prims = shift(bb.p, (w - bb.w) / 2, 0.0)
        a, d = bb.a, bb.d
        gap = M['limit_gap'] * size
        if pb:
            y = -(bb.a + gap + pb.d)
            prims += shift(pb.p, (w - pb.w) / 2, y)
            a = -y + pb.a
        if sb:
            y = bb.d + gap + sb.a
            prims += shift(sb.p, (w - sb.w) / 2, y)
            d = y + sb.d
        return Box(w, a, d, prims)
    if big:                                              # integral: limits at the side
        x = bb.w * 0.6
        prims = list(bb.p)
        w, a, d = x, bb.a, bb.d
        if pb:
            y = -(bb.a - 0.35 * size)
            prims += shift(pb.p, x + 0.35 * size, y)
            w, a = max(w, x + 0.35 * size + pb.w), max(a, -y + pb.a)
        if sb:
            y = bb.d - 0.15 * size
            prims += shift(sb.p, x, y)
            w, d = max(w, x + sb.w), max(d, y + sb.d)
        return Box(w, a, d, prims)
    prims = list(bb.p)
    x = bb.w
    w, a, d = x, bb.a, bb.d
    up = max(M['sup_up'] * size, bb.a - 0.25 * size) if pb else 0
    dn = max(M['sub_dn'] * size, bb.d + 0.10 * size) if sb else 0
    if pb and sb and (up - pb.d) - (-dn + sb.a) < 0.15 * size:         # keep the two apart
        dn = up - pb.d + sb.a - 0.15 * size + 0.0
        dn = max(dn, M['sub_dn'] * size)
    if pb:
        prims += shift(pb.p, x, -up)
        w, a = max(w, x + pb.w), max(a, up + pb.a)
    if sb:
        prims += shift(sb.p, x, dn)
        w, d = max(w, x + sb.w), max(d, dn + sb.d)
    return Box(w, a, d, prims)


def l_lscript(node, size, cx):
    _, base, sub, sup = node
    bb = lay(base, size, cx)
    ss = size * M['script']
    sb = lay(sub, ss, cx) if sub is not None else Box()
    pb = lay(sup, ss, cx) if sup is not None else Box()
    lw = max(sb.w, pb.w)
    prims = shift(bb.p, lw, 0.0)
    a, d = bb.a, bb.d
    if sup is not None:
        up = max(M['sup_up'] * size, bb.a - 0.25 * size)
        prims += shift(pb.p, lw - pb.w, -up)
        a = max(a, up + pb.a)
    if sub is not None:
        dn = max(M['sub_dn'] * size, bb.d + 0.10 * size)
        prims += shift(sb.p, lw - sb.w, dn)
        d = max(d, dn + sb.d)
    return Box(lw + bb.w, a, d, prims)


def l_big(node, size, cx):
    _, g, limits, is_text = node
    if is_text:
        return text_box(g, size * M['lim_scale'], {'rm': True, 'bold': False}, cx.color)
    k = M['bigint'] if g in '∫∮∬∭∯∰' else (M['bigset'] if g in '⋃⋂' else M['big'])
    sz = size * k
    ax = M['axis'] * size
    wd = adv(g, sz) if g not in '∬∭∯∰' else adv('∫', sz) * (2 if g in '∬∯' else 3)
    half = 0.5 * sz * 0.95
    b = Box(wd, ax + half, half - ax)
    if g in '∬∯':
        gl = '∫∫'
    elif g in '∭∰':
        gl = '∫∫∫'
    else:
        gl = g
    xs = [i * adv('∫', sz) * 0.8 for i in range(len(gl))] if len(gl) > 1 else [0.0]
    b.w = (xs[-1] + adv(gl[-1], sz)) if len(gl) > 1 else wd
    lsb = M['int_lsb'] * sz if g in '∫∮∬∭∯∰' else 0.0           # the integral sign has room on its left (E12)
    b.w -= lsb
    b.p = [('t', -lsb, -ax + 0.36 * sz, gl, xs, sz, False, False, cx.color)]
    return b


def l_not(node, size, cx):
    b = lay(node[1], size, cx)
    p = list(b.p) + [('l', 0.1 * b.w, b.d, b.w * 0.9 + 0.05 * size, -b.a, 0.04 * size, cx.color)]
    return Box(b.w, b.a, b.d, p)


def l_bigg(node, size, cx):
    return lay(node[1], size * 1.6, cx)


def l_acc(node, size, cx):
    _, kind, body = node
    b = lay(body, size, cx)
    w = max(b.w, 0.3 * size)
    prims = shift(b.p, (w - b.w) / 2, 0.0)
    wd = max(0.04 * size, 0.0)
    top = -(b.a + 0.10 * size)
    a, d = b.a, b.d
    cxm = w / 2 + (0.06 * size if kind in ('bar', 'dot', 'ddot', 'acute', 'grave') else 0)
    if kind == 'bar':
        prims.append(hline(0.05 * size, w, top, wd, cx.color))
        a += 0.14 * size
    elif kind == 'under':
        prims.append(hline(0.0, w, b.d + 0.10 * size, wd, cx.color))
        d += 0.14 * size
    elif kind in ('vec', 'dyad'):
        y = top
        prims.append(hline(0.0, w, y, wd, cx.color))
        h = 0.07 * size
        prims.append(('p', [('M', [(w - 0.14 * size, y - h)]), ('L', [(w, y), (w - 0.14 * size, y + h)])], wd, cx.color, 'none'))
        if kind == 'dyad':
            prims.append(('p', [('M', [(0.14 * size, y - h)]), ('L', [(0.0, y), (0.14 * size, y + h)])], wd, cx.color, 'none'))
        a += 0.2 * size
    elif kind in ('dot', 'ddot'):
        r = 0.035 * size
        pts = [cxm] if kind == 'dot' else [cxm - 0.1 * size, cxm + 0.1 * size]
        for x in pts:
            prims.append(('r', x - r, top - r, 2 * r, 2 * r, cx.color))
        a += 0.2 * size
    elif kind in ('acute', 'grave'):
        s = 1 if kind == 'acute' else -1
        prims.append(('l', cxm - s * 0.04 * size, top, cxm + s * 0.06 * size, top - 0.12 * size, wd, cx.color))
        a += 0.2 * size
    elif kind in ('hat', 'check', 'arch', 'tilde'):
        y = top
        h = 0.09 * size
        hw = max(w, 0.3 * size) / 2
        mid = w / 2
        if kind == 'hat':
            pts = [('M', [(mid - hw * 0.8, y + h)]), ('L', [(mid, y - h * 0.4), (mid + hw * 0.8, y + h)])]
        elif kind == 'check':
            pts = [('M', [(mid - hw * 0.8, y - h * 0.4)]), ('L', [(mid, y + h), (mid + hw * 0.8, y - h * 0.4)])]
        elif kind == 'arch':
            pts = [('M', [(mid - hw, y + h)]), ('Q', [(mid, y - h * 1.6), (mid + hw, y + h)])]
        else:
            pts = [('M', [(mid - hw, y + h * 0.4)]), ('C', [(mid - hw * 0.4, y - h * 1.2), (mid + hw * 0.4, y + h * 1.4), (mid + hw, y - h * 0.2)])]
        prims.append(('p', pts, wd, cx.color, 'none'))
        a += 0.22 * size
    return Box(w, a, d, prims)


def l_color(node, size, cx):
    _, rgb, body = node
    nums = [int(x) for x in ''.join(c if c.isdigit() or c == ',' else '' for c in _flat_text(rgb)).split(',') if x.isdigit()]
    old = cx.color
    if len(nums) == 3:
        cx.color = '#%02X%02X%02X' % tuple(min(255, v) for v in nums)
    b = lay(body, size, cx)
    cx.color = old
    return b


def _flat_text(node):
    if node[0] == 'row':
        return ''.join(_flat_text(n) for n in node[1])
    if node[0] == 'txt':
        return node[1]
    return ''


def l_rel(node, size, cx):
    _, arrow, top, bot = node
    tb = lay(top, size * 0.65, cx)
    bb = lay(bot, size * 0.65, cx) if bot is not None else Box()
    w = max(tb.w, bb.w, 0.8 * size) + 0.5 * size
    ax = M['axis'] * size
    prims = [hline(0.0, w, -ax, max(0.04 * size, 0.0), cx.color)]
    h = 0.08 * size
    prims.append(('p', [('M', [(w - 0.16 * size, -ax - h)]), ('L', [(w, -ax), (w - 0.16 * size, -ax + h)])], 0.04 * size, cx.color, 'none'))
    if '←' in _flat_text(arrow) or '↔' in _flat_text(arrow):
        prims.append(('p', [('M', [(0.16 * size, -ax - h)]), ('L', [(0.0, -ax), (0.16 * size, -ax + h)])], 0.04 * size, cx.color, 'none'))
    gap = 0.08 * size
    prims += shift(tb.p, (w - tb.w) / 2, -ax - gap - tb.d)
    a = ax + gap + tb.d + tb.a
    d = 0.0
    if bot is not None:
        prims += shift(bb.p, (w - bb.w) / 2, -ax + gap + bb.a)
        d = -ax + gap + bb.a + bb.d
    return Box(w, a, max(d, 0.0), prims)


def stack(rows, size, align, gap_em):
    """Rows (boxes) one under another; returns a box whose middle sits on the axis."""
    w = max((r.w for r in rows), default=0.0)
    gap = gap_em * size
    ra = [max(r.a, M['row_a'] * size) for r in rows]          # a row is at least one line high (E15)
    rd = [max(r.d, M['row_d'] * size) for r in rows]
    total = sum(ra) + sum(rd) + gap * max(len(rows) - 1, 0)
    ax = M['axis'] * size
    y = -ax - total / 2
    prims = []
    for k, r in enumerate(rows):
        y += ra[k]
        x = {'left': 0.0, 'right': w - r.w}.get(align, (w - r.w) / 2)
        prims += shift(r.p, x, y)
        y += rd[k] + gap
    return Box(w, total / 2 + ax, total / 2 - ax, prims)


def surround(body, op, cl, size, cx, extra=0.0):
    """Body with stretched brackets."""
    ax = M['axis'] * size
    hh = max(body.a - ax, body.d + ax, 0.45 * size) + 0.05 * size + extra
    y1, y2 = -(ax + hh), -ax + hh
    wd = max(0.04 * size, 0.0)
    bw = M['bracket_w'] * size
    lp, lw = _br(op, 0.0, y1, y2, wd, cx.color, 'l', bw)
    pad = 0.08 * size
    prims = lp + shift(body.p, lw + pad, 0.0)
    x = lw + pad + body.w + pad
    rp, rw = _br(cl, x, y1, y2, wd, cx.color, 'r', bw)
    return Box(x + rw, ax + hh, hh - ax, prims + rp)


def _br(ch, x, y1, y2, wd, color, side, bw):
    h = y2 - y1
    w = min(bw, 0.10 * h + 0.2 * bw) if ch in '([{)]}⟨⟩' else bw
    w = max(w, 0.5 * bw)
    return _bracket_paths(ch, x, y1, y2, wd, color, side, w)


def _bracket_paths(ch, x, y1, y2, wd, color, side, bw):
    def mx(v):
        return x + v if side == 'l' else x + bw - v
    h = y2 - y1
    m = (y1 + y2) / 2
    if not ch:
        return [], 0.0
    if ch in '()':
        return [('p', [('M', [(mx(bw), y1)]), ('Q', [(mx(0.0), m), (mx(bw), y2)])], wd, color, 'none')], bw
    if ch in '[]':
        return [('p', [('M', [(mx(bw), y1)]), ('L', [(mx(0.0), y1), (mx(0.0), y2), (mx(bw), y2)])], wd, color, 'none')], bw
    if ch in '⌈⌉':
        return [('p', [('M', [(mx(bw), y1)]), ('L', [(mx(0.0), y1), (mx(0.0), y2)])], wd, color, 'none')], bw
    if ch in '⌊⌋':
        return [('p', [('M', [(mx(0.0), y1)]), ('L', [(mx(0.0), y2), (mx(bw), y2)])], wd, color, 'none')], bw
    if ch in '{}':
        q = bw / 2
        pts = [('M', [(mx(bw), y1)]), ('Q', [(mx(q), y1), (mx(q), y1 + h * 0.12)]), ('L', [(mx(q), m - h * 0.08)]),
               ('Q', [(mx(q), m), (mx(0.0), m)]), ('Q', [(mx(q), m), (mx(q), m + h * 0.08)]), ('L', [(mx(q), y2 - h * 0.12)]),
               ('Q', [(mx(q), y2), (mx(bw), y2)])]
        return [('p', pts, wd, color, 'none')], bw
    if ch in '|‖':
        k = 1 if ch == '|' else 2
        gap = wd * 3
        prims = [vline(mx(gap * i + wd), y1, y2, wd, color) for i in range(k)]
        return prims, gap * (k - 1) + 2 * wd
    if ch in '⟨⟩':
        return [('p', [('M', [(mx(bw), y1)]), ('L', [(mx(0.0), m), (mx(bw), y2)])], wd, color, 'none')], bw
    return [], 0.0


def l_lr(node, size, cx):
    _, op, cl, body = node
    return surround(lay(body, size, cx), op, cl, size, cx)


def l_binom(node, size, cx):
    _, a, b = node
    return surround(l_frac(('frac', a, b, False), size, cx), '(', ')', size, cx)


def l_grid(node, size, cx):
    _, kind, rows, aligns = node
    if kind in ('ladder', 'sladder'):
        return l_ladder(kind, rows, size, cx)
    cells = [[lay(c, size, cx) for c in r] for r in rows]
    ncol = max((len(r) for r in cells), default=0)
    if kind in ('pile', 'lpile', 'rpile'):
        al = {'pile': 'center', 'lpile': 'left', 'rpile': 'right'}[kind]
        return stack([r[0] if r else Box() for r in cells], size, al, M['pile_gap'])
    colw = [max((r[c].w for r in cells if c < len(r)), default=0.0) for c in range(ncol)]
    rowa = [max((c.a for c in r), default=0.0) for r in cells]
    rowd = [max((c.d for c in r), default=0.0) for r in cells]
    gap = M['row_gap'] * size
    cg = 0.0 if kind == 'eqalign' else M['col_gap'] * size
    total = sum(rowa) + sum(rowd) + gap * max(len(cells) - 1, 0)
    ax = M['axis'] * size
    y = -ax - total / 2
    prims, ys = [], []
    for ri, r in enumerate(cells):
        y += rowa[ri]
        x = 0.0
        for ci, c in enumerate(r):
            if kind == 'eqalign':
                dx = colw[ci] - c.w if ci == 0 else 0.0
            elif kind == 'cases':
                dx = 0.0
            else:
                al = aligns[ci] if aligns and ci < len(aligns) else 'center'
                dx = {'left': 0.0, 'right': colw[ci] - c.w}.get(al, (colw[ci] - c.w) / 2)
            prims += shift(c.p, x + dx, y)
            x += colw[ci] + cg
        y += rowd[ri] + gap
    w = sum(colw) + cg * max(ncol - 1, 0)
    box = Box(w, total / 2 + ax, total / 2 - ax, prims)
    if kind == 'cases':
        return surround(box, '{', '', size, cx)
    br = {'pmatrix': ('(', ')'), 'bmatrix': ('[', ']'), 'dmatrix': ('|', '|')}.get(kind)
    return surround(box, br[0], br[1], size, cx) if br else box


def l_ladder(kind, rows, size, cx):
    """ladder{2&12&28 # 2&6&14 # 3&7&}: a divisor column, then numbers; every row but the last has an L-shaped rung (a vertical
    line left of the numbers and a line under them). The last row has no divisor. sladder: the third column is the remainder
    (after a row of dots) and the rungs run under the first number column only (rules E21)."""
    sz = size * (M['sladder'] if kind == 'sladder' else 1.0)
    n = len(rows)
    grid = []
    for k, r in enumerate(rows):
        cs = [lay(c, sz, cx) for c in r]
        grid.append([Box()] + cs if k == n - 1 and n > 1 else cs)
    if kind == 'sladder':
        dots = lay(('txt', '⋯', {'rm': True, 'bold': False, 'scale': 100}), sz, cx)
        for r in grid:
            for ci in range(2, len(r)):
                if r[ci].w > 0:
                    r[ci] = hcat([dots, r[ci]])
    ncol = max((len(r) for r in grid), default=0)
    colw = [max((r[c].w for r in grid if c < len(r)), default=0.0) for c in range(ncol)]
    gap = M['ladder_gap'] * sz
    rowa = [max((c.a for c in r), default=0.6 * sz) for r in grid]
    rowd = [max((c.d for c in r), default=0.0) for r in grid]
    pitch = M['ladder_row'] * sz
    total = sum(rowa) + sum(rowd) + pitch * max(n - 1, 0)
    ax = M['axis'] * size
    y = -ax - total / 2
    wd = max(0.04 * sz, 0.0)
    xs, x = [], 0.0
    for c in range(ncol):
        xs.append(x)
        x += colw[c] + (gap if c < ncol - 1 else 0.0)
    prims = []
    vtop = vbot = None
    xv = colw[0] + gap / 2 if ncol > 1 else 0.0
    xend = x if kind == 'ladder' else (xs[1] + colw[1] if ncol > 1 else x)
    for ri, r in enumerate(grid):
        y += rowa[ri]
        for ci, c in enumerate(r):
            dx = colw[ci] - c.w if ci < 2 or kind == 'ladder' else 0.0
            prims += shift(c.p, xs[ci] + dx, y)
        if ri < n - 1:
            ybot = y + rowd[ri] + 0.10 * sz
            if vtop is None:
                vtop = y - rowa[ri] - 0.04 * sz
            vbot = ybot
            prims.append(hline(xv, xend + gap / 2, ybot, wd, cx.color))
        y += rowd[ri] + pitch
    if vtop is not None:                                  # one vertical line through all rungs
        prims.append(vline(xv, vtop, vbot, wd, cx.color))
    return Box(x, total / 2 + ax, total / 2 - ax, prims)


def cell_text(node):
    """Text of a cell with one character per column; a blank (`~`) is a space."""
    if node[0] == 'row':
        return ''.join(cell_text(n) for n in node[1])
    if node[0] == 'txt':
        return node[1]
    if node[0] == 'sp':
        return ' ' * max(1, int(round(node[1])))
    return ''


def l_longdiv(node, size, cx):
    """longdiv{divisor}{quotient}{dividend # row # row ...}: `6)2532` with the quotient on the bar and the steps below. Rows
    with no blank are placed by the long-division rule (a subtrahend ends where the digit was brought down); a row with a
    leading `~` is placed as written, one blank = one digit (rules E22)."""
    _, dvn, qn, rows = node
    sz = size
    dv = lay(dvn, sz, cx)
    texts = [cell_text(r[0]) if r else '' for r in rows]
    dividend = texts[0].strip() if texts else ''
    body = texts[1:]
    quot = cell_text(qn).strip()
    ncols = max(len(dividend), 1)
    dw = adv('0', sz)
    manual = any(t != t.lstrip() for t in body)
    placed, end = [], None
    for k, t in enumerate(body):
        s = t.strip()
        if manual:
            start = len(t) - len(t.lstrip())
        else:
            if k % 2 == 0:
                e = len(s) - 1 if k == 0 else end
            else:
                e = min(end + 1, ncols - 1)
            end = e
            start = e - len(s) + 1
        placed.append((s, max(start, 0), k % 2 == 0))
    lh = M['div_row'] * sz
    x0 = dv.w + 0.45 * sz
    wd = max(0.04 * sz, 0.0)
    ytop = -0.82 * sz
    xp = x0 - 0.08 * sz
    prims = list(dv.p)
    prims.append(('p', [('M', [(xp + 0.02 * sz, ytop)]), ('Q', [(xp - 0.12 * sz, ytop + 0.55 * sz), (xp + 0.02 * sz, 0.25 * sz)])],
                  wd, cx.color, 'none'))
    prims.append(hline(xp + 0.02 * sz, x0 + ncols * dw + 0.05 * sz, ytop, wd, cx.color))

    def row(s, col, y):
        return ('t', x0 + col * dw, y, s, [i * dw for i in range(len(s))], sz, False, False, cx.color)
    if quot:
        prims.append(row(quot, max(ncols - len(quot), 0), ytop - 0.12 * sz))
    prims.append(row(dividend, 0, 0.0))
    for k, (s, col, sub) in enumerate(placed):
        y = (k + 1) * lh
        prims.append(row(s, col, y))
        if sub:
            prims.append(hline(x0 + col * dw, x0 + (col + len(s)) * dw, y + 0.12 * sz, wd, cx.color))
    d = len(placed) * lh + 0.25 * sz
    a = 0.82 * sz + (0.12 + 0.72) * sz if quot else 0.82 * sz
    return Box(x0 + ncols * dw + 0.1 * sz, a, max(d, dv.d), prims)


def l_phantom(node, size, cx):
    b = lay(node[1], size, cx)
    return Box(b.w, b.a, b.d, [])


def l_unsup(node, size, cx):
    cx.warns.append('not drawn: ' + node[1])
    b = text_box(node[1], size * 0.6, {'rm': True, 'bold': False}, cx.color)
    return b


LAYOUT = {'row': l_row, 'txt': l_txt, 'sp': l_sp, 'frac': l_frac, 'sqrt': l_sqrt, 'script': l_script, 'lscript': l_lscript,
          'big': l_big, 'not': l_not, 'bigg': l_bigg, 'acc': l_acc, 'color': l_color, 'rel': l_rel, 'lr': l_lr,
          'binom': l_binom, 'grid': l_grid, 'longdiv': l_longdiv, 'phantom': l_phantom, 'unsup': l_unsup, 'tab': lambda n, s, c: Box()}


# ---- SVG -----------------------------------------------------------------------------------------------------------
def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.') or '0'


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def to_svg(prims, min_line):
    """Primitives (origin at the left edge and top of the drawing) -> SVG text."""
    out = []
    fam = "%s,%s" % (FONT, FALLBACK)
    for q in prims:
        t = q[0]
        if t == 't':
            _, x, y, s, xs, size, italic, bold, color = q
            out.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s"%s%s>%s</text>' % (
                ' '.join(f3(x + v) for v in xs), f3(y), fam.replace('"', "'"), f3(size), color,
                ' font-style="italic"' if italic else '', ' font-weight="bold"' if bold else '', esc(s)))
        elif t == 'l':
            _, x1, y1, x2, y2, wd, color = q
            out.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
                f3(x1), f3(y1), f3(x2), f3(y2), color, f3(max(wd, min_line))))
        elif t == 'p':
            segs, wd, color, fill = q[1], q[2], q[3], q[4]
            d = ''.join(c + ' '.join('%s,%s' % (f3(x), f3(y)) for x, y in pts) + ' ' for c, pts in segs)
            out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="miter"/>' % (
                d.strip(), fill, color, f3(max(wd, min_line))))
        elif t == 'r':
            _, x, y, w, h, color = q
            out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (f3(x), f3(y), f3(w), f3(h), color))
    return ''.join(out)
