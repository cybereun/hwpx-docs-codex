"""Hide personal data in the text of an HWPX (C11.04 without Hangul): resident / foreigner registration numbers,
phone numbers, e-mail addresses and card numbers in the section text are replaced by a mask character.

  mask.apply(src, dst, char='*') -> number of items hidden (0 = the output is a plain copy)

This is a plain text replacement, not encryption: the hidden text is gone from the new file. The input is never
changed. A protected input is refused (core.protect). Only text between tags is touched, never an attribute value.
"""
import re
import zipfile

from ..core import protect

# (name, pattern, how many leading characters stay visible): the pattern never crosses a tag
PATTERNS = (
    ('resident', re.compile(r'(?<![\d-])\d{6}-[1-8]\d{6}(?![\d-])'), 6),
    ('card', re.compile(r'(?<![\d-])\d{4}-\d{4}-\d{4}-\d{4}(?![\d-])'), 0),
    ('phone', re.compile(r'(?<![\d-])0\d{1,2}-\d{3,4}-\d{4}(?![\d-])'), 0),
    ('email', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'), 0),
)
TEXT = re.compile(r'>([^<>]+)<')


def mask_text(text, char='*'):
    """Return (new text, number of items hidden)."""
    n = 0
    for _, rx, keep in PATTERNS:
        def hide(m):
            s = m.group(0)
            return s[:keep] + re.sub(r'[^\W_]', char, s[keep:])           # letters and digits only: '-', '@', '.' stay
        text, k = rx.subn(hide, text)
        n += k
    return text, n


def _white_png():
    """A 1 x 1 white PNG: the page-1 preview picture of the file (`Preview/PrvImage.png`) would still show the hidden text."""
    import struct
    import zlib

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff')) + chunk(b'IEND', b''))


def apply(src, dst, char='*'):
    """Mask the section text and the preview text (`Preview/PrvText.txt`, the first characters of the document in plain text);
    when anything was hidden the preview picture becomes white. A number split over two runs (two `hp:t`) is not found."""
    protect.guard(src)
    total = prev = 0                          # items hidden in the sections / in the preview text (the same items again)
    with zipfile.ZipFile(src) as zi:
        items = [(it, zi.read(it.filename)) for it in zi.infolist()]
    out = []
    for it, data in items:
        if re.fullmatch(r'Contents/section\d+\.xml', it.filename):
            parts, last = [], 0
            xml = data.decode('utf-8')
            for m in TEXT.finditer(xml):
                t, k = mask_text(m.group(1), char)
                if k:
                    parts.append(xml[last:m.start(1)] + t)
                    last, total = m.end(1), total + k
            data = (''.join(parts) + xml[last:]).encode('utf-8')
        elif it.filename == 'Preview/PrvText.txt':
            enc = 'utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'
            try:
                t, k = mask_text(data.decode(enc), char)
                data, prev = t.encode(enc), prev + k
            except UnicodeDecodeError:
                data = b''
        out.append((it, data))
    with zipfile.ZipFile(dst, 'w') as zo:
        for it, data in out:
            if it.filename == 'Preview/PrvImage.png' and (total or prev):
                data = _white_png()
            zo.writestr(it, data, compress_type=it.compress_type)
    return total
