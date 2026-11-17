"""Small image tools, standard library only: BMP/PNG read, PNG write, side by side, compare.

An image is (width, height, rows); rows is a list of bytes, 3 bytes (R, G, B) per pixel.

  hd img topng <in.bmp|png> <out.png>
  hd img side <out.png> <left> <right> [...]     images next to each other, tops aligned
  hd img overlay <out.png> <target> <yours>      black = both, red = only target, blue = only yours
  hd img compare <a> <b>                         prints "INK_DIFF <percent>" (see compare())
"""
from ..core import tmpdir
import struct
import sys
import zlib


def load(path):
    data = open(path, 'rb').read()
    if data[:2] == b'BM':
        return _bmp(data)
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return _png(data)
    raise ValueError('only BMP and PNG are supported (convert JPG with render.py topng): ' + path)


def _bmp(data):
    off, = struct.unpack_from('<I', data, 10)
    w, h, _, bpp, comp = struct.unpack_from('<iiHHI', data, 18)
    if bpp not in (24, 32) or comp not in (0, 3):
        raise ValueError('BMP must be 24 or 32 bit, not compressed')
    step = bpp // 8
    stride = (w * step + 3) & ~3
    rows = []
    for y in range(abs(h)):
        src = y if h < 0 else abs(h) - 1 - y
        line = data[off + src * stride: off + src * stride + w * step]
        if step == 3:
            px = bytearray(line)
            px[0::3], px[2::3] = line[2::3], line[0::3]   # BGR -> RGB
        else:
            px = bytearray(w * 3)
            px[0::3], px[1::3], px[2::3] = line[2::4], line[1::4], line[0::4]
        rows.append(bytes(px))
    return w, abs(h), rows


def _png(data):
    pos, idat, plte = 8, [], None
    while pos < len(data):
        n, t = struct.unpack_from('>I4s', data, pos)
        body = data[pos + 8: pos + 8 + n]
        if t == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif t == b'PLTE':
            plte = body
        elif t == b'IDAT':
            idat.append(body)
        pos += 12 + n
    if depth != 8 or interlace:
        raise ValueError('PNG must be 8 bit per channel and not interlaced')
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * ch
    prev = bytearray(stride)
    rows = []
    i = 0
    for _ in range(h):
        f = raw[i]
        cur = bytearray(raw[i + 1: i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(ch, stride):
                cur[x] = (cur[x] + cur[x - ch]) & 255
        elif f == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = cur[x - ch] if x >= ch else 0
                cur[x] = (cur[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = cur[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = cur
        if ch == 3:
            rows.append(bytes(cur))
        elif ch == 4:
            px = bytearray(w * 3)
            px[0::3], px[1::3], px[2::3] = cur[0::4], cur[1::4], cur[2::4]
            rows.append(bytes(px))
        elif ctype == 3:
            rows.append(b''.join(plte[v * 3: v * 3 + 3] for v in cur))
        else:
            g = cur[0::ch]
            px = bytearray(w * 3)
            px[0::3] = px[1::3] = px[2::3] = g
            rows.append(bytes(px))
    return w, h, rows


def save_png(path, img):
    w, h, rows = img

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + r for r in rows)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def scale(img, factor):
    """Nearest-neighbour scale (factor < 1 makes it smaller)."""
    w, h, rows = img
    nw, nh = max(1, round(w * factor)), max(1, round(h * factor))
    xs = [min(w - 1, int(x / factor)) for x in range(nw)]
    out = []
    for y in range(nh):
        r = rows[min(h - 1, int(y / factor))]
        out.append(b''.join(r[x * 3: x * 3 + 3] for x in xs))
    return nw, nh, out


def fit_height(img, height):
    return img if img[1] == height else scale(img, height / img[1])


def side_by_side(images, gap=16, bg=(160, 160, 160)):
    """Images next to each other, scaled to the height of the first one."""
    height = images[0][1]
    images = [fit_height(im, height) for im in images]
    sep = bytes(bg) * gap
    width = sum(im[0] for im in images) + gap * (len(images) - 1)
    rows = []
    for y in range(height):
        rows.append(sep.join(im[2][y] if y < im[1] else bytes(bg) * im[0] for im in images))
    return width, height, rows


def grid(images, cols, gap=16, bg=(160, 160, 160)):
    """Rows of `cols` images (side_by_side), stacked top to bottom."""
    rows_img = [side_by_side(images[i:i + cols], gap, bg) for i in range(0, len(images), cols)]
    width = max(r[0] for r in rows_img)
    out = []
    for n, (w, h, rows) in enumerate(rows_img):
        if n:
            out += [bytes(bg) * width] * gap
        out += [r + bytes(bg) * (width - w) for r in rows]
    return width, len(out), out


def overlay(a, b, threshold=160):
    """One picture of two pages: ink in both = black, only in a = red, only in b = blue."""
    b = scale(b, a[0] / b[0]) if a[0] != b[0] else b
    w, h = a[0], min(a[1], b[1])
    rows = []
    t3 = threshold * 3
    for y in range(h):
        ra, rb = a[2][y], b[2][y]
        out = bytearray(b'\xff' * (w * 3))
        for x in range(0, w * 3, 3):
            da = ra[x] + ra[x + 1] + ra[x + 2] < t3
            db = rb[x] + rb[x + 1] + rb[x + 2] < t3
            if da and db:
                out[x:x + 3] = b'\x00\x00\x00'
            elif da:
                out[x:x + 3] = b'\xe0\x20\x20'
            elif db:
                out[x:x + 3] = b'\x20\x40\xe0'
        rows.append(bytes(out))
    return w, h, rows


def ink(img, threshold=160, cell=4):
    """Set of (x, y) blocks of size `cell` px that hold dark pixels."""
    w, h, rows = img
    out = set()
    for y in range(h):
        r = rows[y]
        for x in range(0, w * 3, 3):
            if r[x] + r[x + 1] + r[x + 2] < threshold * 3:
                out.add((x // 3 // cell, y // cell))
    return out


def compare(a, b, cell=4):
    """Percent of ink blocks that are in one image only (0 = same ink layout). Sizes are matched first."""
    b = scale(b, a[0] / b[0]) if a[0] != b[0] else b
    ia, ib = ink(a, cell=cell), ink(b, cell=cell)
    if not ia and not ib:
        return 0.0
    return 100.0 * len(ia ^ ib) / max(1, len(ia | ib))


def _selftest():
    img = (3, 2, [bytes([255, 0, 0, 0, 255, 0, 0, 0, 255]), bytes([0, 0, 0] * 3)])
    import os
    p = os.path.join(tmpdir.mkdtemp(), 't.png')
    save_png(p, img)
    assert load(p) == img
    s = side_by_side([img, img], gap=1)
    assert s[0] == 7 and s[2][0][9:12] == bytes([160] * 3)
    assert compare(img, img) == 0.0
    print('IMG SELFTEST PASS')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'selftest':
        _selftest()
    elif cmd == 'topng':
        save_png(sys.argv[3], load(sys.argv[2]))
    elif cmd == 'side':
        save_png(sys.argv[2], side_by_side([load(p) for p in sys.argv[3:]]))
    elif cmd == 'overlay':
        save_png(sys.argv[2], overlay(load(sys.argv[3]), load(sys.argv[4])))
    elif cmd == 'compare':
        print('INK_DIFF %.2f' % compare(load(sys.argv[2]), load(sys.argv[3])))
