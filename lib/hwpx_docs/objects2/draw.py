"""The new object kinds as a viewer draws them (DRAWS['object'], used by the preview): polygon, curve, connector, group, and
textart (글맵시) as a placeholder: its text is drawn straight in the box, the shape warp is not (limit, rules OB15).
Lengths in mm; `svg(item, x, y)` -> [SVG elements] with the object's top-left corner at (x, y); None for an unknown kind.
"""
import re

PT = 25.4 / 72


def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def pen(o, fill_default=None):
    """stroke / fill attributes of the object spec (`line`, `fill`)."""
    ln = o.get('line', '0.12mm solid #000000')
    attrs = ''
    if ln and ln != 'none':
        m = re.match(r'\s*([\d.]+)mm\s+(\w+)\s+(#\w+)', str(ln))
        w, kind, col = (float(m.group(1)), m.group(2), m.group(3)) if m else (0.12, 'solid', '#000000')
        dash = {'dot': f' stroke-dasharray="{f3(w)} {f3(w * 2)}"', 'dash': f' stroke-dasharray="{f3(w * 4)} {f3(w * 2)}"',
                'long_dash': f' stroke-dasharray="{f3(w * 8)} {f3(w * 3)}"',
                'dash_dot': f' stroke-dasharray="{f3(w * 4)} {f3(w * 2)} {f3(w)} {f3(w * 2)}"'}.get(kind, '')
        attrs += f' stroke="{col}" stroke-width="{f3(w)}"{dash}'
    fill = o.get('fill') or fill_default
    return f' fill="{fill}"' + attrs if fill else ' fill="none"' + attrs


def pts(points, x, y):
    return ' '.join(f'{f3(x + px)},{f3(y + py)}' for px, py in points)


def path_of(segs, x, y):
    """Hangul's segments: LINE; a run of three CURVE segments = one cubic Bezier (start -> control 1 -> control 2 -> end)."""
    d, i, cur = [], 0, None
    while i < len(segs):
        t, x1, y1, x2, y2 = segs[i]
        if cur != (x1, y1):
            d.append(f'M{f3(x + x1)},{f3(y + y1)}')
        if t == 'curve' and i + 2 < len(segs) and segs[i + 1][0] == 'curve' and segs[i + 2][0] == 'curve':
            c1, c2, end = (x2, y2), (segs[i + 1][3], segs[i + 1][4]), (segs[i + 2][3], segs[i + 2][4])
            d.append('C' + ' '.join(f'{f3(x + a)},{f3(y + b)}' for a, b in (c1, c2, end)))
            cur, i = end, i + 3
        else:
            d.append(f'L{f3(x + x2)},{f3(y + y2)}')
            cur, i = (x2, y2), i + 1
    return ' '.join(d)


def arrow_head(x1, y1, x2, y2, w):
    """Small filled triangle at (x2, y2) pointing away from (x1, y1)."""
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    n = max(1.6, w * 6)
    a, b = ang + math.pi - 0.45, ang + math.pi + 0.45
    return (f'<polygon points="{f3(x2)},{f3(y2)} {f3(x2 + n * math.cos(a))},{f3(y2 + n * math.sin(a))} '
            f'{f3(x2 + n * math.cos(b))},{f3(y2 + n * math.sin(b))}" fill="context-stroke"/>')


def connector(o, x, y):
    (x1, y1), (x2, y2) = o.get('from', [0, 0]), o.get('to', [o['w'], o['h']])
    kind = o.get('type', 'straight')
    ax, ay, bx, by = x + x1, y + y1, x + x2, y + y2
    mx = (ax + bx) / 2
    if kind == 'elbow':                               # Hangul: along the start side, across in the middle, along the end side
        d = f'M{f3(ax)},{f3(ay)} H{f3(mx)} V{f3(by)} H{f3(bx)}'
    elif kind == 'arc':
        d = f'M{f3(ax)},{f3(ay)} C{f3(mx)},{f3(ay)} {f3(mx)},{f3(by)} {f3(bx)},{f3(by)}'
    else:
        d = f'M{f3(ax)},{f3(ay)} L{f3(bx)},{f3(by)}'
    # the point next to each end, for the direction of the arrow head
    near_a, near_b = ((bx, by), (ax, ay)) if kind == 'straight' else ((mx, ay), (mx, by))
    out = [f'<path d="{d}"{pen(dict(o, fill="none"))}/>']
    w = float((re.match(r'\s*([\d.]+)mm', str(o.get('line', '0.12mm'))) or [0, 0.12])[1])
    col = (re.search(r'#\w+', str(o.get('line', ''))) or ['#000000'])[0]
    if o.get('arrow') in ('end', 'both'):
        out.append(arrow_head(*near_b, bx, by, w).replace('context-stroke', col))
    if o.get('arrow') == 'both':
        out.append(arrow_head(*near_a, ax, ay, w).replace('context-stroke', col))
    return out


def textart(o, x, y):
    """Straight text in the box (the shape of the 글맵시 is not warped: placeholder, rules OB15)."""
    w, h = o['w'], o['h']
    size = h * 0.72
    anchor = {'left': ('start', x), 'center': ('middle', x + w / 2), 'right': ('end', x + w)}[o.get('align', 'left')]
    font = o.get('font', '함초롬바탕')
    base = y + h * 0.78
    txt = o.get('text', '').replace('&', '&amp;').replace('<', '&lt;')
    out = []
    sh = o.get('shadow')
    if sh:
        dx, dy = sh.get('x', 5) * h / 100 * (-1 if sh['type'] == 'left_top' else 1) * 0.3, sh.get('y', 5) * h / 100 * 0.3
        out.append(f'<text x="{f3(anchor[1] + dx)}" y="{f3(base + dy)}" font-family="\'{font}\',\'Malgun Gothic\',sans-serif" '
                   f'font-size="{f3(size)}" text-anchor="{anchor[0]}" fill="#808080" textLength="{f3(w)}" lengthAdjust="spacingAndGlyphs">{txt}</text>')
    out.append(f'<text x="{f3(anchor[1])}" y="{f3(base)}" font-family="\'{font}\',\'Malgun Gothic\',sans-serif" font-size="{f3(size)}" '
               f'text-anchor="{anchor[0]}" fill="{o.get("fill", "#0000FF")}" textLength="{f3(w)}" lengthAdjust="spacingAndGlyphs">{txt}</text>')
    return out


def svg(o, x, y):
    k = o.get('kind')
    if k == 'polygon':
        tag = 'polygon' if o.get('closed', True) else 'polyline'
        return [f'<{tag} points="{pts(o["points"], x, y)}"{pen(o)}/>']
    if k == 'curve':
        return [f'<path d="{path_of(o["segs"], x, y)}"{pen(o)}/>']
    if k == 'connector':
        return connector(o, x, y)
    if k == 'textart':
        from . import textart_warp
        return textart_warp.svg(o, x, y) or textart(o, x, y)        # the shape of the 글맵시; straight text if it cannot
    if k == 'label':                                   # a caption of a core shape (pdraw.shape_captions)
        t = str(o.get('text', '')).replace('&', '&amp;').replace('<', '&lt;')
        return [f'<text x="{f3(x + o["w"] / 2)}" y="{f3(y + o["h"] * 0.72)}" text-anchor="middle" font-size="{f3(9 * PT)}" '
                f'font-family="\'함초롬돋움\',\'Malgun Gothic\',sans-serif" fill="#000000">{t}</text>']
    if k == 'rect':
        return [f'<rect x="{f3(x)}" y="{f3(y)}" width="{f3(o["w"])}" height="{f3(o["h"])}"{pen(o)}/>']
    if k == 'ellipse':
        return [f'<ellipse cx="{f3(x + o["w"] / 2)}" cy="{f3(y + o["h"] / 2)}" rx="{f3(o["w"] / 2)}" ry="{f3(o["h"] / 2)}"{pen(o)}/>']
    if k == 'line':
        return [f'<line x1="{f3(x)}" y1="{f3(y)}" x2="{f3(x + o.get("x2", o["w"]))}" y2="{f3(y + o.get("y2", o["h"]))}"{pen(o)}/>']
    if k == 'group':
        out = []
        for c in o['items']:
            out += svg(c, x + c.get('x', 0), y + c.get('y', 0)) or []
        return out
    return None
