"""Styles and text metrics of the preview: language of a character, char/para style merge, advance width (GDI), line types, numbering."""
from ..core import read as rd
from ..core import textfit


PT = 25.4 / 72                         # mm per pt


BASE = 0.85                            # baseline = 0.85 x line text height (linesegarray baseline / vertsize, 99 % of lines)


TAB = 14.11                            # default tab stop, mm (secPr tabStopVal 4000 hu)


LANGS = ('hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user')


SYMBOLS = set('○●◎□■☐◇◆△▲▽▼※★☆·•')


BLACK = '#000000'


PAPER_MM = {'A4': (209.998, 297.0)}


def lang(ch):
    o = ord(ch)
    if ch in SYMBOLS:
        return 5
    if o < 0x250:
        return 1
    if 0x4E00 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF:
        return 2
    if 0x3040 <= o <= 0x30FF:
        return 3
    return 0


def sv(v, i):
    """One value of a 7-language list (or the number itself)."""
    return v[i] if isinstance(v, list) else v


def char_style(parent, node):
    s = dict(parent)
    for k, v in node.items():
        if k in rd.CHAR_KEYS:
            s[k] = v
    if 'highlight' in node:
        s['hl'] = node['highlight']
    return s


def para_style(node):
    p = dict(rd.DEF_PARA)
    p.update({k: v for k, v in node.items() if k in rd.PARA_KEYS})
    return p


def face(st, lg):
    return st['font'] if lg == 0 else st.get('font_' + LANGS[lg], st['font'])


def eff_size(st, lg):
    s = st['size'] * sv(st['rel_size'], lg) / 100
    return s * 0.58 if st.get('sup') or st.get('sub') else s


SPACE_EM = 0.5      # Hangul's own space (useFontSpace 0, the default): half an em in any font (rules P08)


def cwidth(ch, st):
    """Advance of one character in pt: font width x size x 장평 + 자간."""
    lg = lang(ch)
    sz = eff_size(st, lg)
    if (st.get('upright') and lg != 0 or st.get('vcell') and (lg == 0 or ch in '.,')) and ch != ' ':
        return sz + sv(st['spacing'], lg) / 100 * sz    # 세로쓰기: a letter (and . ,) stands in a full cell (P14)
    em = SPACE_EM if ch == ' ' and not st.get('font_space') else textfit.gdi().em(ch, face(st, lg), bool(st['bold']))
    w = em * sz * sv(st['ratio'], lg) / 100
    return w + sv(st['spacing'], lg) / 100 * sz


def fam(name):
    fb = 'serif' if ('바탕' in name or '명조' in name or 'Batang' in name) else 'sans-serif'
    return "'%s','Malgun Gothic',%s" % (name, fb)


def parse_line(s):
    """"0.4mm solid #000000" -> (width mm, type, colour) or None for none."""
    if not s or s == 'none' or s.startswith('none'):
        return None
    p = s.split()
    return float(p[0].rstrip('m')), (p[1] if len(p) > 1 else 'solid'), (p[2] if len(p) > 2 else BLACK)


def strength(ln):
    return (0, 0) if ln is None else (1, ln[0])


def fmt_num(n, f):
    if f == 'HANGUL_SYLLABLE':
        return '가나다라마바사아자차카타파하'[(n - 1) % 14]
    if f == 'CIRCLED_DIGIT':
        return chr(0x2460 + n - 1) if 1 <= n <= 20 else str(n)
    if f in ('LATIN_SMALL', 'LATIN_CAPITAL'):
        c = chr(ord('a') + (n - 1) % 26)
        return c.upper() if f == 'LATIN_CAPITAL' else c
    if f in ('ROMAN_SMALL', 'ROMAN_CAPITAL'):
        r, out = n, ''
        for v, sym in ((10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')):
            while r >= v:
                out += sym
                r -= v
        return out.upper() if f == 'ROMAN_CAPITAL' else out
    return str(n)
