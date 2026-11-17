"""Measure the ruled lines of a form image in mm (standard library only).

  python measure.py <image.png> [--page-mm 210] [--min-mm 6] [--dpi-work 150]

The image must show the whole page width (a scan or a page render); --page-mm is the paper width it shows
(A4 portrait 210, landscape 297). JPG and other formats: convert first (render.py topng).
Prints:
  PAGE <w_mm> x <h_mm>  scale <px per mm>
  H y=<mm> x=<x1>..<x2> t=<thickness mm>       horizontal line segments, top to bottom
  V x=<mm> y=<y1>..<y2> t=<thickness mm>       vertical line segments, left to right
  GRID x: <x positions>  y: <y positions>       distinct line positions (merge 0.8 mm)
  COLS <widths mm>  ROWS <heights mm>           differences of GRID (candidate table cols/heights)
  INK x=<mm>..<mm> y=<mm>..<mm>                  bounding box of all dark pixels
  T y=<y1>..<y2> h=<mm> x=<x1>..<x2>             text line bands (ink rows outside the long lines):
                                                 band pitch = line spacing, x extent / characters = size
Use the numbers in the spec (cols, heights, margins, shape x/y). Text is not read: read it from the image.
"""
import sys

from ..render import img


def dark_rows(im, thr):
    w, h, rows = im
    t3 = thr * 3
    return [[r[x] + r[x + 1] + r[x + 2] < t3 for x in range(0, w * 3, 3)] for r in rows]


def runs(bits, min_len):
    out, start = [], None
    for i, b in enumerate(bits + [False]):
        if b and start is None:
            start = i
        elif not b and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return out


def segments(grid, min_len, transpose=False):
    """Long runs per row (or per column), merged over neighbouring rows into lines with a thickness."""
    if transpose:
        grid = [list(col) for col in zip(*grid)]
    found = []      # [pos_start, pos_end, a, b]
    for y, row in enumerate(grid):
        for a, b in runs(row, min_len):
            for f in found:
                if f[1] == y - 1 and min(b, f[3]) - max(a, f[2]) > 0.8 * min(b - a, f[3] - f[2]):
                    f[1], f[2], f[3] = y, min(a, f[2]), max(b, f[3])
                    break
            else:
                found.append([y, y, a, b])
    return found


def cluster(values, tol):
    out = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def main(path, page_mm=210.0, min_mm=6.0, dpi_work=150, thr=128):
    im = img.load(path)
    s = dpi_work / 25.4 / (im[0] / page_mm)
    if s < 1:
        im = img.scale(im, s)
    w, h, _ = im
    pxmm = w / page_mm
    g = dark_rows(im, thr)
    min_len = max(3, round(min_mm * pxmm))
    hs = segments(g, min_len)
    vs = segments(g, min_len, transpose=True)
    f = lambda v: round(v / pxmm, 1)        # noqa: E731
    print(f'PAGE {page_mm} x {f(h)}  scale {pxmm:.3f} px/mm')
    for y0, y1, a, b in sorted(hs):
        print(f'H y={f((y0 + y1) / 2)} x={f(a)}..{f(b + 1)} t={round((y1 - y0 + 1) / pxmm, 2)}')
    for x0, x1, a, b in sorted(vs):
        print(f'V x={f((x0 + x1) / 2)} y={f(a)}..{f(b + 1)} t={round((x1 - x0 + 1) / pxmm, 2)}')
    gx = cluster([(x0 + x1) / 2 / pxmm for x0, x1, _, _ in vs], 0.8)
    gy = cluster([(y0 + y1) / 2 / pxmm for y0, y1, _, _ in hs], 0.8)
    print('GRID x:', ' '.join(f'{v:.1f}' for v in gx), ' y:', ' '.join(f'{v:.1f}' for v in gy))
    print('COLS', ' '.join(f'{b - a:.1f}' for a, b in zip(gx, gx[1:])),
          ' ROWS', ' '.join(f'{b - a:.1f}' for a, b in zip(gy, gy[1:])))
    xs = [x for row in g for x, b in enumerate(row) if b]
    ys = [y for y, row in enumerate(g) if any(row)]
    if xs:
        print(f'INK x={f(min(xs))}..{f(max(xs) + 1)} y={f(min(ys))}..{f(max(ys) + 1)}')
    # text lines: bands of rows with ink after the long lines are removed
    line_px = set()
    for y0, y1, a, b in hs:
        for y in range(y0, y1 + 1):
            line_px.update((y, x) for x in range(a, b + 1))
    for x0, x1, a, b in vs:
        for x in range(x0, x1 + 1):
            line_px.update((y, x) for y in range(a, b + 1))
    band = None
    for y, row in enumerate(g + [[]]):
        ink = [x for x, b in enumerate(row) if b and (y, x) not in line_px]
        if ink and band is None:
            band = [y, y, min(ink), max(ink)]
        elif ink:
            band[1], band[2], band[3] = y, min(band[2], min(ink)), max(band[3], max(ink))
        elif band is not None:
            if band[1] - band[0] >= 2:
                print(f'T y={f(band[0])}..{f(band[1] + 1)} h={round((band[1] - band[0] + 1) / pxmm, 1)} '
                      f'x={f(band[2])}..{f(band[3] + 1)}')
            band = None


def _selftest():
    w, h = 210, 100                       # 1 px = 1 mm
    rows = [bytearray(b'\xff' * (w * 3)) for _ in range(h)]
    for x in range(20, 190):
        rows[10][x * 3:x * 3 + 3] = b'\x00\x00\x00'
        rows[50][x * 3:x * 3 + 3] = b'\x00\x00\x00'
    for y in range(10, 51):
        for x in (20, 80, 189):
            rows[y][x * 3:x * 3 + 3] = b'\x00\x00\x00'
    im = (w, h, [bytes(r) for r in rows])
    g = dark_rows(im, 128)
    hs, vs = segments(g, 6), segments(g, 6, transpose=True)
    assert [(a, b) for a, b, _, _ in sorted(hs)] == [(10, 10), (50, 50)], hs
    assert [a for a, _, _, _ in sorted(vs)] == [20, 80, 189], vs
    assert cluster([20, 20.5, 80], 0.8) == [20.25, 80]
    print('MEASURE SELFTEST PASS')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'selftest':
        _selftest()
    else:
        opts = {'--page-mm': 210.0, '--min-mm': 6.0, '--dpi-work': 150}
        for k in list(opts):
            if k in a:
                i = a.index(k)
                opts[k] = float(a[i + 1])
                del a[i:i + 2]
        main(a[0], opts['--page-mm'], opts['--min-mm'], int(opts['--dpi-work']))
