"""Dev tool (needs Hangul 2024 and PIL): measures the warp of the 36 글맵시 shapes and writes `textart_data.py`. Not run by `hd selftest`.

    python -m hwpx_docs.objects2.textart_measure render <work dir>     Hangul draws a row of 20 blocks in every shape (200 dpi PNG)
    python -m hwpx_docs.objects2.textart_measure data <work dir>       corners of every block -> textart_data.py

Set HWPX_DOCS_SECURITY_MODULE for the file-access module. Steps of `data`: connected blocks of the PNG; their four corners (convex hull
cut down to 4 corners by the smallest exterior angle, or the two ends of a thin curved stripe); the corners ordered TL, TR, BR, BL by
the text direction; per block the candidate that joins its neighbours best; a block that still does not join is replaced by the
average of its neighbours. Rules OB21.
"""
import json
import math
import os
import sys

DPI = 200
K = DPI / 25.4
MARGIN = 8 * K                                  # the box sits 8 mm inside the crop
BW, BH = 60 * K, 20 * K                         # box size in pixels (60 x 20 mm)
BLOCKS = '■' * 20


def render(work):
    from ..core import build
    from ..render.hwpcom import Hwp
    from . import shapes
    from PIL import Image
    os.makedirs(work, exist_ok=True)
    with Hwp(visible=False) as h:
        for name in shapes.SHAPES:
            spec = {'body': [{'object': {'kind': 'textart', 'w': 60, 'h': 20, 'text': BLOCKS, 'shape': name, 'fill': '#000000',
                                         'inline': False, 'pos': {'x': 30, 'y': 30, 'rel': 'paper'}, 'wrap': 'in_front_of_text'}}]}
            src = os.path.join(work, f'src_{name}.hwpx')
            build.write(spec, src, base=work)
            h.hwp.Clear(1)
            assert h.open(src), name
            stem = os.path.join(work, f'b20_{name}')
            p = h.page_images(stem, dpi=DPI, fmt='bmp')[0]
            x0, m = round(30 * K), round(8 * K)
            Image.open(p).convert('L').crop((x0 - m, x0 - m, x0 + round(60 * K) + m, x0 + round(20 * K) + m)).save(stem + '.png')
            os.remove(p)
            print('rendered', name, flush=True)


def components(im):
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    comps = []
    for y0 in range(h):
        for x0 in range(w):
            if px[x0, y0] < 128 and not seen[y0 * w + x0]:
                stack, pts = [(x0, y0)], []
                seen[y0 * w + x0] = 1
                while stack:
                    x, y = stack.pop()
                    pts.append((x, y))
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] < 128 and not seen[ny * w + nx]:
                            seen[ny * w + nx] = 1
                            stack.append((nx, ny))
                if len(pts) > 200:
                    comps.append(pts)
    return comps


def hull(pts):
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def simplify(poly, n=4):
    """Drop the vertex that turns least until n are left: the corners of a curved stripe stay."""
    poly = list(poly)
    while len(poly) > n:
        best, bi = None, 0
        for i in range(len(poly)):
            a, b, c = poly[i - 1], poly[i], poly[(i + 1) % len(poly)]
            v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            ang = abs(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1]))
            if best is None or ang < best:
                best, bi = ang, i
        poly.pop(bi)
    return poly


def sliver(pts):
    """A thin curved stripe (long side / width > 4): the two extreme points across each end; else None."""
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts) / n
    syy = sum((p[1] - my) ** 2 for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts) / n
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ax, ay = math.cos(ang), math.sin(ang)
    along = [(p[0] - mx) * ax + (p[1] - my) * ay for p in pts]
    across = [-(p[0] - mx) * ay + (p[1] - my) * ax for p in pts]
    length, width = max(along) - min(along), max(across) - min(across)
    if width * 4 > length:
        return None
    cut = length * 0.04
    lo = [(pts[i], across[i]) for i in range(n) if along[i] < min(along) + cut]
    hi = [(pts[i], across[i]) for i in range(n) if along[i] > max(along) - cut]
    return [min(lo, key=lambda t: t[1])[0], max(lo, key=lambda t: t[1])[0], max(hi, key=lambda t: t[1])[0], min(hi, key=lambda t: t[1])[0]]


def orient(q, d):
    """4 corners in cyclic order -> [TL, TR, BR, BL] in box units. Edge i joins vertices i and i + 1; the SIDES are the opposite pair of
    edges whose midpoints lie apart along the text direction d (a slanted stripe has long sides and a tiny top)."""
    mid = [((q[k][0] + q[(k + 1) % 4][0]) / 2, (q[k][1] + q[(k + 1) % 4][1]) / 2) for k in range(4)]
    dn = (d[0] ** 2 + d[1] ** 2) ** 0.5 or 1.0

    def along(a, b):
        v = (mid[b][0] - mid[a][0], mid[b][1] - mid[a][1])
        return abs(v[0] * d[0] + v[1] * d[1]) / ((v[0] ** 2 + v[1] ** 2) ** 0.5 * dn or 1.0)
    sides, ends = ((0, 2), (1, 3)) if along(0, 2) >= along(1, 3) else ((1, 3), (0, 2))
    left = min(sides, key=lambda k: mid[k][0] * d[0] + mid[k][1] * d[1])
    right = sides[0] if left == sides[1] else sides[1]
    top = max(ends, key=lambda k: mid[k][0] * d[1] - mid[k][1] * d[0])
    bottom = ends[0] if top == ends[1] else ends[1]

    def shared(a, b):
        return q[({a, (a + 1) % 4} & {b, (b + 1) % 4}).pop()]
    return [[round((p[0] - MARGIN) / BW, 4), round((p[1] - MARGIN) / BH, 4)]
            for p in (shared(left, top), shared(right, top), shared(right, bottom), shared(left, bottom))]


def candidates(path):
    """Per block (left to right): the candidate corner sets."""
    from PIL import Image
    cs = components(Image.open(path).convert('L'))
    cs.sort(key=lambda c: sum(p[0] for p in c) / len(c))
    cen = [(sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)) for c in cs]
    out = []
    for i, c in enumerate(cs):
        a, b = (cen[i], cen[i + 1]) if i + 1 < len(cs) else (cen[i - 1], cen[i])
        d = (b[0] - a[0], b[1] - a[1])
        sl = sliver(c)
        out.append([orient(q, d) for q in [simplify(hull(c))] + ([sl] if sl else [])])
    return out


def gap(a, b):
    return max(math.hypot(a[1][0] - b[0][0], a[1][1] - b[0][1]), math.hypot(a[2][0] - b[3][0], a[2][1] - b[3][1]))


def choose(blocks):
    chosen = [min(blocks[0], key=lambda a: min(gap(a, b) for b in blocks[1]))]
    for j in range(1, len(blocks)):
        nxt = blocks[j + 1] if j + 1 < len(blocks) else None
        chosen.append(min(blocks[j], key=lambda a: gap(chosen[-1], a) + (min(gap(a, b) for b in nxt) if nxt else 0)))
    for _ in range(3):                                         # a pair that does not join: the block whose other side is worse is wrong
        bad = set()
        for k in range(19):
            if gap(chosen[k], chosen[k + 1]) > 0.12:
                gl = gap(chosen[k - 1], chosen[k]) if k > 0 else 0
                gr = gap(chosen[k + 1], chosen[k + 2]) if k + 2 < 20 else 0
                bad.add(k if gl > gr else k + 1)
        if not bad:
            break
        for j in sorted(bad):
            if 0 < j < 19:
                chosen[j] = [[(a + b) / 2 for a, b in zip(p, r)] for p, r in zip(chosen[j - 1], chosen[j + 1])]
            else:
                n1, n2 = (1, 2) if j == 0 else (18, 17)
                chosen[j] = [[2 * a - b for a, b in zip(p, r)] for p, r in zip(chosen[n1], chosen[n2])]
    return chosen


def data(work):
    from . import shapes
    out = ['"""Measured warp of the 36 글맵시 shapes (generated by textart_measure.py from Hangul renders: edit the tool, not this file).',
           '',
           'Hangul 2024 drew a row of 20 blocks in every shape (a 60 x 20 mm box, 200 dpi). Each block is a quadrilateral: its corners',
           'top-left, top-right, bottom-right, bottom-left, as (x / box width, y / box height) from the box corner. A block is R of its',
           'pitch wide and the 20 of them cover the unwarped text box from 0 to 1 (rules OB21).', '"""', 'R = 0.7573', 'QUADS = {']
    for name in shapes.SHAPES:
        out.append(f"    '{name}': [")
        for b in choose(candidates(os.path.join(work, f'b20_{name}.png'))):
            out.append('        ' + repr([[round(v, 3) for v in p] for p in b]) + ',')
        out.append('    ],')
        print('measured', name, flush=True)
    out.append('}')
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textart_data.py')
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print('wrote', path)


if __name__ == '__main__':
    {'render': render, 'data': data}[sys.argv[1]](sys.argv[2])
