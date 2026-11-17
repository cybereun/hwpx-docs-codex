"""OLE object that embeds a file (C8.03): `{"ole": {"src": "file.txt", "w", "h", ...}}` <-> `hp:ole` + `BinData/oleN.ole`.

Hangul's "OLE 개체 > 파일로 만들기" stores the file in an OLE "Package" object: `BinData/ole1.ole` = 4 bytes (length of the compound
file, little endian) + a compound file (CFB v3) with the streams `\\x01CompObj` (constant) and `\\x01Ole10Native` (label, source path,
temp path, the file's bytes, and the same three names in UTF-16). `cfb()` writes such a file, `read_cfb()` reads it; both handle only
what this needs (version 3, 512-byte sectors, a flat list of streams, one FAT with up to 109 sectors). Spec keys as for the object
block (shapes.py): `inline`, `pos`, `wrap`, `side`, `caption`; `w`, `h` default 26.72 x 21.96 mm (Hangul's size). Rules OB19, OB20.
"""
import os
import re
import struct

from ..core.units import esc, hu, inherit
from . import pos as P
from . import shapes as S

NS = P.NS
SS, MS, CUT = 512, 64, 4096                       # sector size, mini sector size, mini stream cut-off
ENDC, FREE, FATSECT = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD
PACKAGE_CLSID = bytes.fromhex('0c00030000000000c000000000000046')      # {0003000C-0000-0000-C000-000000000046}
COMPOBJ = (b'\x01\x00\xfe\xff\x03\n\x00\x00\xff\xff\xff\xff\x0c\x00\x03\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00F'
           b'\x0c\x00\x00\x00OLE Package\x00\x00\x00\x00\x00\x08\x00\x00\x00Package\x00\xf49\xb2q' + b'\x00' * 12)    # as Hangul writes it (76 bytes)
W0, H0 = 7574, 6225                                # Hangul's default size of the object (hu)


# ---- compound file -----------------------------------------------------------------------------------------------------
def cfb(streams, root_clsid=PACKAGE_CLSID):
    """[(name, bytes)] -> compound file bytes (a flat list of streams under the root)."""
    mini, big = [(n, d) for n, d in streams if len(d) < CUT], [(n, d) for n, d in streams if len(d) >= CUT]
    sectors, fat = [], []

    def alloc(data, fill=b'\x00'):
        """Append `data` as a chain of sectors; returns the first sector index."""
        k = max(1, -(-len(data) // SS)) if data else 0
        first = len(sectors) if k else ENDC
        for i in range(k):
            sectors.append(data[i * SS:(i + 1) * SS].ljust(SS, fill))
            fat.append(len(sectors) if i < k - 1 else ENDC)
        return first
    ministream, minifat, start = bytearray(), [], {}
    for n, d in mini:
        k = -(-len(d) // MS)
        start[n] = len(ministream) // MS if k else ENDC
        ministream += d.ljust(k * MS, b'\x00')
        minifat += [start[n] + i + 1 for i in range(k - 1)] + ([ENDC] if k else [])
    for n, d in big:
        start[n] = alloc(d)
    mf_first = alloc(b''.join(struct.pack('<I', v) for v in minifat).ljust(-(-len(minifat) // 128) * 512, b'\xff')) if minifat else ENDC
    ms_first = alloc(bytes(ministream))

    def entry(name, typ, left, right, child, first, size, clsid=b'\x00' * 16):
        nm = name.encode('utf-16-le')
        return (nm.ljust(64, b'\x00') + struct.pack('<HBB', len(nm) + 2 if name else 0, typ, 1) + struct.pack('<III', left, right, child)
                + clsid + b'\x00' * 4 + b'\x00' * 16 + struct.pack('<IQ', first, size))      # state bits, create / modify time
    names = [n for n, _ in streams]
    ents = [entry('Root Entry', 5, FREE, FREE, 1 if names else FREE, ms_first, len(ministream), root_clsid)]
    for i, (n, d) in enumerate(streams):
        ents.append(entry(n, 2, FREE, i + 2 if i + 1 < len(streams) else FREE, FREE, start[n], len(d)))
    while len(ents) % 4:
        ents.append(b'\x00' * 64 + b'\x00\x00\x00\x00' + struct.pack('<III', FREE, FREE, FREE) + b'\x00' * 36 + struct.pack('<IQ', 0, 0))
    dir_first = alloc(b''.join(ents))
    nfat = 1
    while nfat * 128 < len(sectors) + nfat:
        nfat += 1
    fat_first = len(sectors)
    fat += [FATSECT] * nfat
    fat += [FREE] * (nfat * 128 - len(fat))
    fat_bytes = b''.join(struct.pack('<I', v) for v in fat)
    sectors += [fat_bytes[i * SS:(i + 1) * SS] for i in range(nfat)]
    hdr = (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 16 + struct.pack('<HHHHH', 0x3e, 3, 0xfffe, 9, 6) + b'\x00' * 6
           + struct.pack('<IIIIIIIII', 0, nfat, dir_first, 0, CUT, mf_first, -(-len(minifat) // 128), ENDC, 0)
           + b''.join(struct.pack('<I', fat_first + i) for i in range(nfat)) + b'\xff' * (4 * (109 - nfat)))
    return hdr + b''.join(sectors)


def read_cfb(data):
    """compound file bytes -> {stream name: bytes}; ValueError when it is not a CFB v3 file this module can read."""
    if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' or struct.unpack_from('<H', data, 26)[0] != 3:
        raise ValueError('not a compound file (version 3)')
    nfat, dir_first, cut, mf_first = struct.unpack_from('<I', data, 44)[0], struct.unpack_from('<I', data, 48)[0], \
        struct.unpack_from('<I', data, 56)[0], struct.unpack_from('<I', data, 60)[0]
    fat_secs = struct.unpack_from('<%dI' % nfat, data, 76)
    sec = lambda n: data[512 + n * SS:512 + (n + 1) * SS]
    fat = [v for s in fat_secs for v in struct.unpack('<128I', sec(s))]

    def chain(first):
        out, n = [], first
        while n < FATSECT and len(out) < len(fat):
            out.append(n)
            n = fat[n]
        return out
    d = b''.join(sec(n) for n in chain(dir_first))
    ents = []
    for i in range(0, len(d), 128):
        e = d[i:i + 128]
        ln = struct.unpack_from('<H', e, 64)[0]
        if ln and e[66] in (2, 5):
            ents.append((e[:ln - 2].decode('utf-16-le'), e[66], struct.unpack_from('<I', e, 116)[0], struct.unpack_from('<Q', e, 120)[0]))
    root = next(e for e in ents if e[1] == 5)
    ministream = b''.join(sec(n) for n in chain(root[2]))[:root[3]]
    minifat = [v for n in chain(mf_first) for v in struct.unpack('<128I', sec(n))]
    out = {}
    for name, typ, first, size in ents:
        if typ != 2:
            continue
        if size < cut:
            n, parts = first, []
            while n < FATSECT and len(parts) < len(minifat):
                parts.append(ministream[n * MS:(n + 1) * MS])
                n = minifat[n]
            out[name] = b''.join(parts)[:size]
        else:
            out[name] = b''.join(sec(n) for n in chain(first))[:size]
    return out


# ---- the OLE "Package" object -------------------------------------------------------------------------------------------
def package(name, payload):
    """The `\\x01Ole10Native` stream of a file `name` with the bytes `payload`."""
    lab = name.encode('cp949', 'replace')
    src = tmp = ('C:\\temp\\' + name).encode('cp949', 'replace')
    body = (b'\x02\x00' + lab + b'\x00' + src + b'\x00' + b'\x00\x00\x03\x00' + struct.pack('<I', len(tmp) + 1) + tmp + b'\x00'
            + struct.pack('<I', len(payload)) + payload)
    for s in (tmp, lab, src):                              # the three names again in UTF-16 (counted in characters)
        u = s.decode('cp949')
        body += struct.pack('<I', len(u)) + u.encode('utf-16-le')
    return struct.pack('<I', len(body)) + body


def unpackage(stream):
    """`\\x01Ole10Native` stream -> (file name, bytes)."""
    if struct.unpack_from('<I', stream, 0)[0] != len(stream) - 4 or stream[4:6] != b'\x02\x00':
        raise ValueError('not an OLE package stream')
    i = stream.index(b'\x00', 6)
    label = stream[6:i].decode('cp949', 'replace')
    j = stream.index(b'\x00', i + 1)
    m = re.compile(rb'\x00\x00\x03\x00').search(stream, j)
    if not m:
        raise ValueError('no temp path in the OLE package stream')
    p = m.end()
    p += 4 + struct.unpack_from('<I', stream, p)[0]
    n = struct.unpack_from('<I', stream, p)[0]
    return label, stream[p + 4:p + 4 + n]


def ole_bytes(name, payload):
    """`BinData/oleN.ole`: the length of the compound file, then the file."""
    c = cfb([('\x01CompObj', COMPOBJ), ('\x01Ole10Native', package(name, payload))])
    return struct.pack('<I', len(c)) + c


# ---- other OLE objects: the name of the object and its cached picture ---------------------------------------------------------
def compobj_names(stream):
    """`\\x01CompObj` -> (user type, ProgID), '' when a field is missing."""
    try:
        n = struct.unpack_from('<I', stream, 28)[0]
        user = stream[32:32 + n].rstrip(b'\x00').decode('cp949', 'replace')
        p = 32 + n + 4                                  # the clipboard format (DWORD) follows
        m = struct.unpack_from('<I', stream, p)[0]
        return user, stream[p + 4:p + 4 + m].rstrip(b'\x00').decode('cp949', 'replace')
    except (struct.error, IndexError):
        return '', ''


def dib_png(dib):
    """A device independent bitmap (BITMAPINFOHEADER + colours + bits, 8 / 24 / 32 bit, uncompressed) -> PNG bytes, or None."""
    import zlib
    try:
        size, w, h, planes, bits, comp, _, _, _, ncol = struct.unpack_from('<IiiHHIIiiI', dib, 0)
    except struct.error:
        return None
    if size < 40 or comp not in (0, 3) or bits not in (8, 24, 32) or w <= 0 or h == 0:
        return None
    top_down, h = h < 0, abs(h)
    pal_n = (ncol or 256) if bits == 8 else 0
    pal = [tuple(dib[size + 4 * i + 2::-1][:3]) for i in range(pal_n)]            # BGRA -> RGB
    off = size + 4 * pal_n + (12 if comp == 3 and size == 40 else 0)
    stride = (w * bits + 31) // 32 * 4
    rows = []
    for r in range(h):
        row = dib[off + r * stride:off + r * stride + stride]
        if len(row) < stride:
            return None
        px = bytearray()
        for x in range(w):
            if bits == 8:
                px += bytes(pal[row[x]] if row[x] < len(pal) else (0, 0, 0))
            else:
                b = row[x * bits // 8:x * bits // 8 + 3]
                px += bytes((b[2], b[1], b[0]))
        rows.append(b'\x00' + bytes(px))
    if not top_down:
        rows.reverse()

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(rows)))
            + chunk(b'IEND', b''))


def presentation_png(streams):
    """The cached picture of an OLE object (`\\x02OlePres000`) as PNG bytes when it is a device independent bitmap; None for a
    metafile (Excel, Word ...) or when there is none."""
    try:
        s = streams['\x02OlePres000']
        marker, fmt = struct.unpack_from('<II', s, 0)
        if marker != 0xFFFFFFFF or fmt != 8:
            return None
        td = struct.unpack_from('<I', s, 8)[0]
        p = 8 + max(td, 4)
        n = struct.unpack_from('<I', s, p + 4 * 6)[0]
        return dib_png(s[p + 4 * 7:p + 4 * 7 + n])
    except (KeyError, struct.error, IndexError):
        return None


# ---- builder and reader ------------------------------------------------------------------------------------------------
def element(doc, o, ctx):
    if 'raw' in o:                                         # an OLE object of another program: the part and the element as read
        n = 1 + sum(1 for b in doc.bins if b[0].startswith('ole'))
        item = f'ole{n}'
        doc.bins.append((item, f'BinData/{item}.ole', open(os.path.join(doc.base, o['raw']), 'rb').read(), 'application/ole'))
        return re.sub(r'binaryItemIDRef="[^"]*"', f'binaryItemIDRef="{item}"', o['xml'], count=1)
    path = os.path.join(doc.base, o['src'])
    name = os.path.basename(o['src'])
    n = 1 + sum(1 for b in doc.bins if b[0].startswith('ole'))
    item = f'ole{n}'
    doc.bins.append((item, f'BinData/{item}.ole', ole_bytes(name, open(path, 'rb').read()), 'application/ole'))
    w, h = (hu(o['w']), hu(o['h'])) if 'w' in o else (W0, H0)
    o = dict(o, w=w / S.MM, h=h / S.MM)
    stem = os.path.splitext(name)[0]
    xml = (S.head(doc, o, 'ole', w, h, None, f' objectType="EMBEDDED" binaryItemIDRef="{item}" hasMoniker="0" drawAspect="CONTENT" eqBaseLine="0"')
           .replace('numberingType="NONE"', 'numberingType="PICTURE"') + f'<hc:extent x="{w}" y="{h}"/>'
           + S.line_xml(dict(o, line='none')) + S.tail(o, w, h, None)
           + f'<hp:shapeComment>OLE 개체입니다.\n원본 파일의 이름은 {esc(stem)}입니다.</hp:shapeComment>')
    return S.finish(doc, o, ctx, xml, 'ole', w)


def block(doc, b, ctx, extra, pending_break):
    """Builder handler of the spec key `ole`: the run of the object (core makes the paragraph, same_para)."""
    o = b['ole']
    if not isinstance(o, dict) or not ('src' in o or 'raw' in o):
        return None
    return f'<hp:run charPrIDRef="{doc.head.char_pr(inherit(ctx, b))}">{element(doc, o, ctx)}<hp:t/></hp:run>'


def other(reader, el, d, data):
    """An embedded OLE object that is not a file package: keep the part and the element, find its name and cached picture."""
    from ..core.read import raw
    stem = reader.save(reader.bins[el.get('binaryItemIDRef')], data)
    d.pop('kind')
    d.update(raw=stem, xml=raw(el))
    try:
        streams = read_cfb(data[4:4 + struct.unpack_from('<I', data, 0)[0]])
    except (ValueError, struct.error, IndexError, StopIteration):
        streams = {}
    user, prog = compobj_names(streams.get('\x01CompObj', b''))
    if user or prog:
        d['label'] = user or prog
    png = presentation_png(streams)
    if png:
        d['view'] = reader.save(stem + '.png', png)
    return {'ole': d}


def read(reader, el):
    """Reader handler (READS): `hp:ole` that embeds a file -> `{"ole": {...}}`, the file saved next to the spec. Any other embedded OLE
    object (Excel, ...): `{"ole": {"raw": <the part, saved>, "xml": <the element>, "label": <object type>, "view": <cached picture>}}`
    (written back as read); a linked object: None (core keeps the element as raw OWPML)."""
    try:
        if el.get('objectType') != 'EMBEDDED':
            return None
        data = reader.z.read(reader.bins[el.get('binaryItemIDRef')])
        d = S.read_common(el, 'ole', False)
    except (KeyError, ValueError, struct.error, AttributeError):
        return None
    try:
        size = struct.unpack_from('<I', data, 0)[0]
        streams = read_cfb(data[4:4 + size])
        label, payload = unpackage(streams['\x01Ole10Native'])
        name = os.path.basename(label.replace('\\', '/'))
    except (KeyError, ValueError, struct.error, IndexError):
        return other(reader, el, d, data)
    d.pop('kind')
    d['src'] = reader.save(name, payload)     # the label comes from the received file: core.read.Reader.save checks it
    if (round(d['w'] * S.MM), round(d['h'] * S.MM)) == (W0, H0):
        d.pop('w'), d.pop('h')
    cap = P.read_caption(el)
    if cap:
        d['caption'] = cap
    return {'ole': d}
