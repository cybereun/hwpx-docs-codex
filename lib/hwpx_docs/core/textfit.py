"""Width of text in the real font (Windows GDI through ctypes; no package) and the line count of a wrapped paragraph.

  python textfit.py            self-test (prints "TEXTFIT OK")

md2hwpx.css_layout uses count_lines() to give table rows the browser's height: a wrong line count makes a row too
high or too low, and the error adds up down the page. Break rules follow the browser (UAX #14, simplified):
word_break "word" (CSS keep-all) breaks at spaces and before an opening bracket after a CJK letter; "char" (CSS
normal) also breaks between CJK letters, never before closing punctuation or after an opening bracket;
latin_break "char" (CSS break-all) breaks anywhere.
"""
import ctypes
import re
import sys
try:
    from ctypes import wintypes
except (ImportError, ValueError):          # not Windows: no GDI; gdi() then gives estimated widths
    wintypes = None

EM = 1000                       # measuring size in device units; widths scale linearly with the font size
OPEN = set('([{「『〈《【"\'‘“')
CLOSE = set(')]}」』〉》】,.;:!?·、。，．％%\'"’”')
PT_MM = 25.4 / 72


def cjk(ch):
    return ord(ch) >= 0x2E80


class _GDI:
    def __init__(self):
        g = ctypes.windll.gdi32
        g.CreateCompatibleDC.restype = ctypes.c_void_p
        g.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        g.CreateFontW.restype = ctypes.c_void_p
        g.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [ctypes.c_wchar_p]
        g.SelectObject.restype = ctypes.c_void_p
        g.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        g.GetTextExtentPoint32W.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int,
                                            ctypes.POINTER(wintypes.SIZE)]
        self.g, self.dc, self.fonts, self.cache = g, g.CreateCompatibleDC(None), {}, {}

    def em(self, ch, face, bold):
        """Advance width of one character in em."""
        key = (ch, face, bold)
        if key not in self.cache:
            f = self.fonts.get((face, bold))
            if f is None:
                # DEFAULT_CHARSET (1), ANTIALIASED_QUALITY (4)
                f = self.fonts[(face, bold)] = self.g.CreateFontW(-EM, 0, 0, 0, 700 if bold else 400, 0, 0, 0, 1,
                                                                   0, 0, 4, 0, face)
            self.g.SelectObject(self.dc, f)
            sz = wintypes.SIZE()
            self.g.GetTextExtentPoint32W(self.dc, ch, 1, ctypes.byref(sz))
            self.cache[key] = sz.cx / EM
        return self.cache[key]


class _Estimate:
    """Without Windows GDI: a CJK character 1 em, a space 0.3 em, other characters 0.55 em (rough). Symbols that
    Korean fonts draw full width (East Asian width W, F or A: ① ○ □ ※ “ ” ․ …; not the Latin-1 letters) are 1 em
    too: at 0.55 em the next character was drawn over them."""
    def em(self, ch, face, bold):
        if cjk(ch):
            return 1.0
        if ch == ' ':
            return 0.3
        o = ord(ch)
        if o >= 0x2000 or (0xA1 <= o < 0xC0 and o not in (0xAA, 0xBA)) or o in (0xD7, 0xF7):
            import unicodedata
            if unicodedata.east_asian_width(ch) in ('W', 'F', 'A'):
                return 1.0
        return 0.55


_gdi = None


def gdi():
    global _gdi
    if _gdi is None:
        try:
            _gdi = _GDI()
        except (AttributeError, OSError, TypeError):
            _gdi = _Estimate()
    return _gdi


def chars(b):
    """Paragraph spec -> list of (char, width pt)."""
    base = dict(font=b.get('font', '함초롬바탕'), font_latin=b.get('font_latin'), size=b.get('size', 10),
                bold=b.get('bold', False), spacing=b.get('spacing', 0))
    p = b.get('p', '')
    runs = [p] if isinstance(p, str) else p
    out = []
    for r in runs:
        st = dict(base, **{k: v for k, v in r.items() if k in base}) if isinstance(r, dict) else base
        t = r if isinstance(r, str) else r.get('t', '')
        for ch in t or '':
            face = st['font'] if cjk(ch) else (st['font_latin'] or st['font'])
            w = gdi().em(ch, face, bool(st['bold'])) * st['size'] + (st['spacing'] or 0) / 100 * st['size']
            out.append((ch, w))
    return out


def widths(b, width_mm):
    """(first line width, other lines width) in pt of paragraph spec `b` (Hangul left/indent/right semantics)."""
    left, ind, right = b.get('left', 0), b.get('indent', 0), b.get('right', 0)
    full = width_mm / PT_MM - left - right
    return full - max(ind, 0), full - max(-ind, 0)


def wrap(b, width_mm):
    """Lay out paragraph spec `b` in a box `width_mm` wide. Returns (chars, lines): chars = [(char, width pt)],
    lines = [(start, end)] indexes into chars (a line keeps its trailing spaces)."""
    return wrap_chars(chars(b), b, width_mm)


def wrap_chars(cs, b, width_mm):
    """wrap() for a char list `cs` that the caller made (items start with (char, width pt); more fields are kept
    by index). `b` gives left, indent, right, word_break, latin_break."""
    if not cs:
        return cs, [(0, 0)]
    first, other = widths(b, width_mm)
    keep = b.get('word_break') == 'word'
    anywhere = b.get('latin_break') == 'char'

    def opening(i):             # a line may start at chars[i]
        ch, prev = cs[i][0], cs[i - 1][0]
        if prev == ' ':
            return ch != ' '
        if ch == ' ':
            return False
        if anywhere:
            return ch not in CLOSE and prev not in OPEN
        if keep:
            return ch in OPEN and cjk(prev)
        return (cjk(prev) or cjk(ch)) and ch not in CLOSE and prev not in OPEN
    starts = [0] + [i for i in range(1, len(cs)) if opening(i)] + [len(cs)]
    lines, ls, used, avail = [], 0, 0.0, first
    for s, e in zip(starts, starts[1:]):
        te = e
        while te > s and cs[te - 1][0] == ' ':
            te -= 1             # trailing spaces count only when more text follows on the line
        w = sum(c[1] for c in cs[s:te])
        if used and used + w > avail + 0.01:
            lines.append((ls, s))
            ls, used, avail = s, 0.0, other
        k = s
        while used + w > avail + 0.01 and avail > 0:  # a unit longer than the line breaks anywhere (Hangul does)
            j, acc = k, used
            while j < te and acc + cs[j][1] <= avail + 0.01:
                acc += cs[j][1]
                j += 1
            j = max(j, k + 1)
            lines.append((ls, j))
            ls, k, used, avail = j, j, 0.0, other
            w = sum(c[1] for c in cs[k:te])
        used += w + sum(c[1] for c in cs[te:e])
    lines.append((ls, len(cs)))
    return cs, lines


def count_lines(b, width_mm):
    """Line count of paragraph spec `b` in a box `width_mm` wide."""
    return len(wrap(b, width_mm)[1])


def selftest():
    w_ga = gdi().em('가', '함초롬바탕', False)
    w_a = gdi().em('a', '함초롬바탕', False)
    assert 0.9 < w_ga <= 1.05, w_ga                   # a Hangul syllable is about 1 em
    assert 0.3 < w_a < 0.7, w_a
    b = dict(p='가' * 20, size=10, font='함초롬바탕')
    assert count_lines(b, 20 * 10 * PT_MM * 1.0 + 0.5) == 1
    assert count_lines(b, 10 * 10 * PT_MM + 0.5) == 2
    word = dict(b, p='가나다 라마바 사아자', word_break='word')
    assert count_lines(word, 5 * 10 * PT_MM) == 3      # breaks only at the two spaces
    print('TEXTFIT OK', round(w_ga, 3), round(w_a, 3))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == '--selftest':
        selftest()
    else:                       # hd textwidth "<text>" [--font <face>] [--size <pt>] -> width in pt
        face = a[a.index('--font') + 1] if '--font' in a else '함초롬바탕'
        size = float(a[a.index('--size') + 1]) if '--size' in a else 10
        print('WIDTH_PT', round(sum(w for _, w in chars({'p': a[0], 'font': face, 'size': size})), 2))
