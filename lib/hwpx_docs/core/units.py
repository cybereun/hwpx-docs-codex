"""Units, colours, lines and shared constants of the builder."""
import html
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))


TEMPLATE = os.path.join(HERE, 'template')


# ---- units -------------------------------------------------------------------------------
HU_PER = {'mm': 7200 / 25.4, 'cm': 72000 / 25.4, 'pt': 100.0, 'in': 7200.0, 'hu': 1.0, 'px': 75.0}


PAPER = {'A4': ('59528hu', '84186hu'),          # Hangul's own A4 (new document), not round(297 mm)
         'A3': (297, 420), 'A5': (148, 210), 'B4': (257, 364), 'B5': (182, 257),
         'LETTER': (215.9, 279.4), 'LEGAL': (215.9, 355.6)}


def hu(v, unit='mm'):
    """Length -> HWPUNIT. v is a number in `unit`, or a string with a unit: '12pt', '3.5mm', '1cm', '96px'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(v * HU_PER[unit])
    m = re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*(mm|cm|pt|in|hu|px)?\s*', str(v))
    if not m:
        raise ValueError(f'bad length: {v!r}')
    return round(float(m.group(1)) * HU_PER[m.group(2) or unit])


def quad(v, unit='mm'):
    """[left, right, top, bottom] from one value or a list of 1, 2 (horizontal, vertical) or 4 values."""
    if v is None:
        return None
    if not isinstance(v, (list, tuple)):
        v = [v]
    if len(v) == 1:
        v = v * 4
    elif len(v) == 2:
        v = [v[0], v[0], v[1], v[1]]
    return [hu(x, unit) for x in v]


def color(v, default='#000000'):
    if v is None:
        return default
    s = str(v).strip()
    if s.lower() in ('none', 'transparent'):
        return 'none'
    s = s.lstrip('#')
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    if not re.fullmatch(r'[0-9a-fA-F]{6}', s):
        raise ValueError(f'bad colour: {v!r}')
    return '#' + s.upper()


def esc(s):
    return html.escape(str(s), quote=True)


# ---- lines (borders) ---------------------------------------------------------------------
LINE_TYPES = {'none': 'NONE', 'solid': 'SOLID', 'dash': 'DASH', 'dot': 'DOT', 'dash_dot': 'DASH_DOT',
              'dash_dot_dot': 'DASH_DOT_DOT', 'long_dash': 'LONG_DASH', 'circle': 'CIRCLE', 'double': 'DOUBLE_SLIM',
              'double_slim': 'DOUBLE_SLIM', 'slim_thick': 'SLIM_THICK', 'thick_slim': 'THICK_SLIM',
              'slim_thick_slim': 'SLIM_THICK_SLIM',
              'wave': 'WAVE', 'doublewave': 'DOUBLEWAVE', 'thick3d': 'THICK3D', 'thickrev3d': 'THICKREV3D',
              '3d': '3D', 'rev3d': 'REV3D'}      # sampled: table S:cell_line_types, cell_line_types_more (TB01)


WIDTHS_MM = [0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]


NO_LINE = ('NONE', '0.12 mm', '#000000')


def width_str(mm):
    w = min(WIDTHS_MM, key=lambda x: abs(x - mm))   # Hangul accepts only these widths
    s = ('%.2f' % w).rstrip('0')
    return (s + '0' if s.endswith('.') else s) + ' mm'


def line(v):
    """'0.4mm solid #000000' | 'none' | {'type','width','color'} -> (TYPE, 'W mm', '#RRGGBB')."""
    if v is None or v is False:
        return NO_LINE
    if isinstance(v, (list, tuple)) and len(v) == 3 and str(v[1]).endswith(' mm'):
        return tuple(v)
    if isinstance(v, dict):
        t, w, c = v.get('type', 'solid'), v.get('width', '0.12mm'), v.get('color')
    else:
        t, w, c = 'solid', '0.12mm', None
        for tok in str(v).replace(',', ' ').split():
            low = tok.lower()
            if low.startswith('#'):
                c = tok
            elif re.fullmatch(r'-?\d+(\.\d+)?(mm|pt)?', low):
                w = tok
            elif low in LINE_TYPES:
                t = low
            else:
                raise ValueError(f'bad line token {tok!r} in {v!r}')
    t = LINE_TYPES[str(t).lower()]
    # a NONE side keeps its width and colour: Hangul uses them at the corners where the next
    # side is drawn (corpus paraborder round trip: the bottom rule ends moved without them)
    mm = hu(w, 'mm') / HU_PER['mm']
    return t, width_str(mm), color(c)


# ---- header (reference lists) ------------------------------------------------------------
LANGS = ['HANGUL', 'LATIN', 'HANJA', 'JAPANESE', 'OTHER', 'SYMBOL', 'USER']


LANG_ATTRS = ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']


TYPEINFO = ('<hh:typeInfo familyType="FCAT_GOTHIC" weight="6" proportion="4" contrast="0" strokeVariation="1" '
            'armStyle="1" letterform="1" midline="1" xHeight="1"/>')


ALIGNS = {'left': 'LEFT', 'right': 'RIGHT', 'center': 'CENTER', 'justify': 'JUSTIFY', 'distribute': 'DISTRIBUTE',
          'divide': 'DISTRIBUTE_SPACE'}


def langs(fmt, values):
    return ' '.join(f'{a}="{v}"' for a, v in zip(LANG_ATTRS, values))


def sides_of(border):
    """Paragraph or cell border spec -> dict side -> line tuple.
    border: one line spec for all sides, or {'left','right','top','bottom'} (missing sides: none)."""
    if not border:
        return {}
    if isinstance(border, dict) and set(border) & {'left', 'right', 'top', 'bottom'}:
        return {k: line(v) for k, v in border.items()}
    return {k: line(border) for k in ('left', 'right', 'top', 'bottom')}


# ---- style inheritance -------------------------------------------------------------------
CHAR_KEYS = {'font', 'font_latin', 'font_hanja', 'font_japanese', 'font_other', 'font_symbol', 'font_user',
             'size', 'bold', 'italic', 'underline', 'strike', 'color', 'shade', 'spacing',
             'ratio', 'sup', 'sub', 'rel_size', 'offset', 'outline', 'shadow', 'emboss', 'engrave', 'emphasis',
             'kerning', 'font_space', 'char_border', 'char_fill', 'highlight'}


PARA_KEYS = {'align', 'left', 'right', 'indent', 'before', 'after', 'line', 'keep_next', 'keep_lines',
             'page_break_before', 'widow', 'word_break', 'border', 'fill', 'border_offset', 'border_connect', 'bullet',
             'number', 'bullet_image', 'tabs', 'snap', 'line_valign', 'condense', 'latin_break', 'autospace', 'outline_level'}


INHERIT = CHAR_KEYS | PARA_KEYS - {'border', 'fill', 'border_offset', 'border_connect', 'bullet', 'bullet_image', 'number', 'outline_level',
                                   'page_break_before'}


# Hangul's default paragraph numbering (corpus/numbering, header numbering id 2)
DEFAULT_NUMBERING = [{'text': '^1.', 'format': 'DIGIT'}, {'text': '^2.', 'format': 'HANGUL_SYLLABLE'},
                     {'text': '^3)', 'format': 'DIGIT'}, {'text': '^4)', 'format': 'HANGUL_SYLLABLE'},
                     {'text': '(^5)', 'format': 'DIGIT'}, {'text': '(^6)', 'format': 'HANGUL_SYLLABLE'},
                     {'text': '^7', 'format': 'CIRCLED_DIGIT'}, {'text': '^8', 'format': 'CIRCLED_HANGUL_SYLLABLE'},
                     {'format': 'HANGUL_JAMO'}, {'format': 'ROMAN_SMALL'}]


def inherit(ctx, block):
    """Context for children: only text style keys flow down (not borders, fills, page breaks)."""
    out = dict(ctx)
    out.update({k: v for k, v in block.items() if k in INHERIT})
    return out


def read(path):
    return open(path, encoding='utf-8').read()


# picture file extension -> the media type Hangul writes in content.hpf (read from Hangul's own HWPX of real forms; "image/jpg" and
# "image/tif" are Hangul's spelling)
IMAGE_MEDIA = {'png': 'image/png', 'jpg': 'image/jpg', 'jpeg': 'image/jpg', 'bmp': 'image/bmp', 'gif': 'image/gif',
               'tif': 'image/tif', 'tiff': 'image/tif'}


def image_size(data):
    if data[:4] in (b'II*\x00', b'MM\x00*'):                       # TIFF: the width and length tags of the first directory
        end = '<' if data[:2] == b'II' else '>'
        pos = struct.unpack(end + 'I', data[4:8])[0]
        n = struct.unpack(end + 'H', data[pos:pos + 2])[0]
        size = {}
        for k in range(n):
            tag, typ = struct.unpack(end + 'HH', data[pos + 2 + 12 * k:pos + 6 + 12 * k])
            if tag in (256, 257):
                size[tag] = struct.unpack(end + ('H' if typ == 3 else 'I'), data[pos + 10 + 12 * k:pos + 10 + 12 * k + (2 if typ == 3 else 4)])[0]
        return size[256], size[257]
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:2] == b'BM':
        w, h = struct.unpack('<ii', data[18:26])
        return w, abs(h)
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return struct.unpack('<HH', data[6:10])
    if data[:2] == b'\xff\xd8':
        i = 2
        while i < len(data):
            marker, size = data[i + 1], struct.unpack('>H', data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            i += 2 + size
    raise ValueError('unknown image format')
