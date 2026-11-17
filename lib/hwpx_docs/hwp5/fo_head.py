"""OWPML header.xml -> DocInfo records of an HWP 5.0 file (the writing half of rules HW11, HW12, HW14).

  head_records(head_el, settings, bins) -> [[tag, level, bytes], ...]   in Hangul's order, ID_MAPPINGS counted
  Maps (the correspondence tables): LINE, WIDTH, LANGS, UNDER_POS, ... below; they are the inverse of owpmlmap.py.

Written from the public format document (see the notice in __init__.py); the field layouts are the ones docinfo.py reads.
Everything the HWPX has is written; a value this module has no code for raises `Unsupported` (the caller stops).
"""
import re
import struct

from . import owpmlmap as om
from .fmt import T
from .fontnames import DEFAULT_FONT_NAME, SERIF_STYLE


class Unsupported(ValueError):
    """An element or value with no record in this converter: reported as `UNSUPPORTED <what> <where>`; nothing is dropped."""


WARNINGS = []                                        # one line for each thing that was written in the way Hangul does it, not as the HWPX says


def warn(msg):
    """A converted value that is not what the HWPX says (a missing file written as id 0, ...): one `warning:` line on stderr for each message."""
    if msg not in WARNINGS:
        WARNINGS.append(msg)
        import sys
        print('warning: ' + msg, file=sys.stderr)


def ln(el):
    """Local name of an element (the namespace stripped)."""
    t = el.tag
    return t.rsplit('}', 1)[-1] if isinstance(t, str) else ''


def kids(el, name=None):
    return [c for c in el if ln(c) == name] if name else [c for c in el if isinstance(c.tag, str)]


def first(el, name):
    for c in el:
        if ln(c) == name:
            return c
    return None


def num(v, default=0):
    """An attribute value as an int ('-5', '0.1' truncates, '' and None give the default)."""
    if v is None or v == '':
        return default
    try:
        return int(v)
    except ValueError:
        return int(float(v))


def snum(v, default=0):
    """A signed 32-bit number: the HWPX writes a negative INT32 as its unsigned value (-100 as 4294967196)."""
    n = num(v, default)
    return n - (1 << 32) if n >= 1 << 31 else n


def color(v, none=0xFFFFFFFF):
    """'#RRGGBB' -> COLORREF 0x00BBGGRR ('none' -> 0xFFFFFFFF); '#AARRGGBB' keeps the alpha in the high byte."""
    if v is None or v == '' or v.lower() == 'none':
        return none
    v = v.lstrip('#')
    a = 0
    if len(v) == 8:
        a, v = int(v[:2], 16), v[2:]
    elif len(v) == 7:                                          # Hangul writes a one-digit alpha at times: #ARRGGBB (HW81)
        a, v = int(v[0], 16), v[1:]
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    return a << 24 | r | g << 8 | b << 16


def wstr(s):
    b = s.encode('utf-16-le')
    return struct.pack('<H', len(b) // 2) + b


# ---- the correspondence tables: one copy in owpmlmap.py (number -> name, the reading side); here name -> number --------
LINE, WIDTH, LANGS, LANG_ATTR = om.LINE, om.WIDTH, om.LANGS, om.LANG_ATTR          # HW14: types 0..17, widths 0..15
FONT_TYPE, HALIGN, VALIGN, UNDER_POS = map(om.inverse, (om.FONT_TYPE, om.ALIGN, om.VALIGN, om.UNDER_POS))
SYM_MARK, OUTLINE, SHADOW, TAB_TYPE = map(om.inverse, (om.SYMMARK, om.OUTLINE, om.CHAR_SHADOW, om.TAB_TYPE))
HEADING, LINE_SPACING, NUM_FORMAT, HATCH = map(om.inverse, (om.HEADING, om.LINE_SPACING, om.NUMFMT, om.HATCH))
SLASH = BACKSLASH = om.inverse(om.SLASH)                                              # bits 2-4 of BORDER_FILL attr




def pick(table, v, what):
    try:
        return table[v]
    except KeyError:
        raise Unsupported(f'{what} "{v}"') from None


def line_side(el):
    """<hh:leftBorder type= width="0.12 mm" color=/> -> (type, width index, COLORREF)."""
    t = pick({n: i for i, n in enumerate(LINE)}, el.get('type', 'NONE'), 'line type')
    w = (el.get('width') or '0.1 mm').replace('mm', '').strip()
    try:
        wi = WIDTH.index(w)
    except ValueError:
        wi = min(range(len(WIDTH)), key=lambda i: abs(float(WIDTH[i]) - float(w)))
    return t, wi, color(el.get('color'), 0)


ALLOWED = {                                     # children each header element may have: any other one is refused (not dropped)
    'charPr': {'fontRef', 'ratio', 'spacing', 'relSz', 'offset', 'italic', 'bold', 'underline', 'strikeout', 'outline',
               'shadow', 'emboss', 'engrave', 'supscript', 'subscript'},
    'paraPr': {'align', 'heading', 'breakSetting', 'autoSpacing', 'switch', 'margin', 'lineSpacing', 'border'},
    'borderFill': {'slash', 'backSlash', 'leftBorder', 'rightBorder', 'topBorder', 'bottomBorder', 'diagonal', 'fillBrush'},
    'fillBrush': {'winBrush', 'gradation', 'imgBrush'},
    'bullet': {'paraHead', 'img'}, 'memoPr': set(), 'style': set(), 'tabPr': {'switch', 'tabItem'}, 'numbering': {'paraHead'}, 'font': {'typeInfo', 'substFont'},
}


def only(el, what=None):
    """Raise Unsupported for a child of `el` that the record writer has no field for."""
    ok = ALLOWED.get(what or ln(el), None)
    if ok is None:
        return
    for c in el:
        if isinstance(c.tag, str) and ln(c) not in ok:
            raise Unsupported(f'element hh:{ln(c)} in hh:{ln(el)} id={el.get("id")} (header.xml)')


# ---- the records ---------------------------------------------------------------------------------------------------------
def face_name(font):
    """FACE_NAME: attribute, name, [substitute font], [type info (10 bytes)], [default font name: bit 5, fontnames.py, rule HW80]."""
    only(font, 'font')
    name = font.get('face', '')
    ti = first(font, 'typeInfo')
    attr = FONT_TYPE.get(font.get('type', 'TTF'), 1)
    body = wstr(name)
    sf = first(font, 'substFont')
    if sf is not None:                                     # a substitute font: type and name, before the type info
        if num(sf.get('isEmbedded')) or sf.get('binaryItemIDRef'):
            raise Unsupported(f'embedded substitute font "{sf.get("face")}" of font "{name}" (header.xml)')
        attr |= 0x80
        body += bytes([FONT_TYPE.get(sf.get('type', 'TTF'), 1)]) + wstr(sf.get('face', ''))
    if ti is not None:
        attr |= 0x40
        # PANOSE of the HWPX typeInfo: family kind 2 (text), serif style, weight, proportion, contrast, stroke, arm,
        # letterform, midline, x height. The HWPX has no serif style byte (hwp2hwpx writes FCAT_GOTHIC for every font):
        # Hangul's own values by font name, else 11 (sans serif) for gothic and 3 (modern serif) for myungjo.
        serif = 11 if (num(ti.get('proportion')), num(ti.get('letterform'))) == (4, 2) else SERIF_STYLE.get(name)       # HW80
        if serif is None:                                  # a font Hangul's table does not show: a guess by the kind of font
            serif = 0 if attr & 3 == 2 else 3 if ti.get('familyType') == 'FCAT_MYUNGJO' else 11 if ti.get('familyType') == 'FCAT_GOTHIC' else 0
        body += bytes([om.inverse(om.FAMILY).get(ti.get('familyType'), 0), serif, num(ti.get('weight')), num(ti.get('proportion')), num(ti.get('contrast')),
                       num(ti.get('strokeVariation')), num(ti.get('armStyle')), num(ti.get('letterform')),
                       num(ti.get('midline')), num(ti.get('xHeight'))])
    default = DEFAULT_FONT_NAME.get(name) if sf is None else None        # Hangul gives it to a font without a substitute font (HW80)
    if default:
        attr |= 0x20
        body += wstr(default)
    return bytes([attr]) + body


def fill_info(fb, bin_ref=None, ver=(5, 1, 0, 0)):
    """The <hc:fillBrush> of a borderFill (or None) -> FillInfo bytes (type + the parts) and the trailing bytes."""
    brush = first(fb, 'fillBrush') if fb is not None else None
    if brush is None:
        return struct.pack('<I', 0) + struct.pack('<I', 0)
    kinds, out, ftype = [ln(c) for c in brush], b'', 0
    if 'winBrush' in kinds:
        w = first(brush, 'winBrush')
        if w.get('faceColor', 'none').lower() == 'none' and w.get('hatchStyle') is None and kinds == ['winBrush']:
            pass
        ftype |= 1
        hs = w.get('hatchStyle')
        out += struct.pack('<IIi', color(w.get('faceColor')), color(w.get('hatchColor'), 0),
                           HATCH[hs] if hs in HATCH else -1)
    if 'gradation' in kinds:
        g = first(brush, 'gradation')
        ftype |= 4
        cols = kids(g, 'color')
        gtype = om.GRADIENT_NUM.get(g.get('type', 'LINEAR'), 1)
        out += struct.pack('<bIiiiI', gtype, num(g.get('angle')) & 0xFFFFFFFF, snum(g.get('centerX')),
                           snum(g.get('centerY')), snum(g.get('step')), len(cols))
        if len(cols) > 2:
            out += struct.pack('<%di' % len(cols), *[round(i * 100 / max(len(cols) - 1, 1)) for i in range(len(cols))])
        out += struct.pack('<%dI' % len(cols), *[color(c.get('value'), 0) for c in cols])
    if 'imgBrush' in kinds:
        ib = first(brush, 'imgBrush')
        img = first(ib, 'img')
        ftype |= 2
        mode = pick(om.inverse(om.IMG_MODES),
                    ib.get('mode', 'TILE'), 'image fill mode')                       # numbers measured in Hangul (16 modes)
        bid = (bin_ref or {}).get(img.get('binaryItemIDRef'))
        if bid is None:
            raise Unsupported(f'image fill picture "{img.get("binaryItemIDRef")}" is not in the package (header.xml)')
        # measured in Hangul: the mode, then the CONTRAST byte, then the brightness byte, the effect, the picture id
        out += struct.pack('<BbbBH', mode, snum(img.get('contrast')), snum(img.get('bright')),
                           pick(om.inverse(om.IMG_EFFECT), img.get('effect', 'REAL_PIC'), 'picture effect'), bid)
    # after the parts: a size and that many bytes (a gradient has its step centre there), then the transparency byte
    if ftype & 4:
        g = first(brush, 'gradation')
        tail = struct.pack('<I', 1) + bytes([num(g.get('stepCenter'), 50), num(g.get('alpha'))])
    elif ftype & 1:
        tail = struct.pack('<I', 0) + bytes([num(first(brush, 'winBrush').get('alpha'))])
    elif ftype & 2:
        tail = struct.pack('<I', 0) + bytes([num(first(first(brush, 'imgBrush'), 'img').get('alpha'))])
    else:
        tail = struct.pack('<I', 0)
    if ver < (5, 0, 2, 0) and ftype & 7:                     # files before 5.0.2.0 have no transparency byte (52 bytes, not 53; HW77)
        tail = tail[:-1]
    return struct.pack('<I', ftype) + out + tail


def border_fill(el, bin_ref=None, ver=(5, 1, 0, 0)):
    only(el)
    attr = 0
    if num(el.get('threeD')):
        attr |= 1
    if num(el.get('shadow')):
        attr |= 2
    sl, bs = first(el, 'slash'), first(el, 'backSlash')
    if sl is not None:
        attr |= pick(SLASH, sl.get('type', 'NONE'), 'slash') << 2
        attr |= (num(sl.get('Crooked')) & 3) << 8 | num(sl.get('isCounter')) << 11     # bits as Hangul wrote them (HW53)
    if bs is not None:
        attr |= pick(BACKSLASH, bs.get('type', 'NONE'), 'backslash') << 5
        attr |= num(bs.get('isCounter')) << 12
    attr |= num(el.get('breakCellSeparateLine')) << 10                              # bit 10, measured in both directions (HW86)
    cl = om.inverse(om.CENTER_LINE).get(el.get('centerLine', 'NONE'), 0)       # bit 13 = VERTICAL measured (HW86)
    attr |= cl << 13
    sides = b''
    for name in ('leftBorder', 'rightBorder', 'topBorder', 'bottomBorder', 'diagonal'):
        s = first(el, name)
        t, w, c = line_side(s) if s is not None else (0, 1, 0) if name == 'diagonal' else (0, 0, 0)    # no diagonal: width 1 (HW81)
        sides += struct.pack('<BBI', t, w, c)
    return struct.pack('<H', attr) + sides + fill_info(el, bin_ref, ver)


def seven(el, default=0):
    return [num(el.get(a), default) if el is not None else default for a in LANG_ATTR]


def char_shape(el, ver=(5, 1, 0, 0)):
    """CHAR_SHAPE (74 bytes; 70 before 5.0.3.0 without the strike-through colour, 68 before 5.0.2.0 without the border fill id; HW77). The char property flags of attr: HW12 / docinfo.char_shape read the same bits."""
    only(el)
    fr, ra, sp, rs, of = (first(el, n) for n in ('fontRef', 'ratio', 'spacing', 'relSz', 'offset'))
    attr = 0
    if first(el, 'italic') is not None:
        attr |= 1
    if first(el, 'bold') is not None:
        attr |= 2
    ul, st, ou, sh = (first(el, n) for n in ('underline', 'strikeout', 'outline', 'shadow'))
    under_color = 0
    if ul is not None:
        attr |= pick(UNDER_POS, ul.get('type', 'NONE'), 'underline') << 2
        attr |= pick(om.inverse(om.UNDERLINE_SHAPE), ul.get('shape', 'SOLID'), 'underline shape') << 4
        under_color = color(ul.get('color'), 0)
    if ou is not None:
        attr |= pick(OUTLINE, ou.get('type', 'NONE'), 'outline') << 8
    shadow_color, sx, sy = 0xB2B2B2, 10, 10
    if sh is not None:
        attr |= pick(SHADOW, sh.get('type', 'NONE'), 'shadow') << 11
        shadow_color, sx, sy = color(sh.get('color'), 0), num(sh.get('offsetX'), 10), num(sh.get('offsetY'), 10)
    if first(el, 'emboss') is not None:
        attr |= 1 << 13
    if first(el, 'engrave') is not None:
        attr |= 1 << 14
    if first(el, 'supscript') is not None:
        attr |= 1 << 15
    if first(el, 'subscript') is not None:
        attr |= 1 << 16
    strike_color = 0
    if st is not None and st.get('shape', 'NONE') != 'NONE':
        attr |= 1 << 18                                        # strike through (3 = the single line)
        attr |= pick(om.inverse(om.UNDERLINE_SHAPE), st.get('shape'), 'strikeout shape') << 26
        if ul is None or ul.get('type', 'NONE') == 'NONE':      # a strike through also sets the underline type "center" and the shape (HW81)
            attr = attr & ~0xFC | 2 << 2 | pick(om.inverse(om.UNDERLINE_SHAPE), st.get('shape'), 'strikeout shape') << 4
            under_color = color(st.get('color'), 0)              # the underline colour slot holds the strike colour then (HW81)
        strike_color = color(st.get('color'), 0)
    elif st is not None:
        strike_color = color(st.get('color'), 0)
    attr |= pick(SYM_MARK, el.get('symMark', 'NONE'), 'symMark') << 21
    if num(el.get('useFontSpace')):
        attr |= 1 << 25
    if num(el.get('useKerning')):
        attr |= 1 << 30
    return (struct.pack('<7H', *seven(fr)) + bytes(seven(ra, default=100)) + struct.pack('<7b', *seven(sp))
            + bytes(seven(rs, default=100)) + struct.pack('<7b', *seven(of))
            + struct.pack('<iIbb', snum(el.get('height'), 1000), attr, sx, sy)
            + struct.pack('<IIII', color(el.get('textColor'), 0), under_color, color(el.get('shadeColor')), shadow_color)
            + (struct.pack('<H', num(el.get('borderFillIDRef'))) if ver >= (5, 0, 2, 0) else b'')
            + (struct.pack('<I', strike_color) if ver >= (5, 0, 3, 0) else b''))


def tab_def(el):
    """TAB_DEF: attribute, count, then (position, type, leader) per stop. Each stop is in its own <hp:switch>: the
    <hp:default> branch holds Hangul's own units (twice the HwpUnitChar ones) and is what the record stores."""
    only(el)
    items = []
    for c in el:
        if ln(c) == 'switch':
            d = first(c, 'default') if first(c, 'default') is not None else first(c, 'case')
            items += kids(d, 'tabItem')
        elif ln(c) == 'tabItem':
            items.append(c)
    attr = num(el.get('autoTabLeft')) | num(el.get('autoTabRight')) << 1
    out = struct.pack('<Ii', attr, len(items))
    for it in items:
        leader = pick({n: i for i, n in enumerate(LINE)}, it.get('leader', 'NONE'), 'tab leader')
        out += struct.pack('<IBBH', snum(it.get('pos')) & 0xFFFFFFFF, pick(TAB_TYPE, it.get('type', 'LEFT'), 'tab type'), leader, 0)
    return out


def numbering(el, ver=(5, 1, 0, 0)):
    """NUMBERING: 7 levels of (attr, width adjust, text offset, char shape id, format string), start number, then the
    levels 8-10 (newer files)."""
    only(el)
    heads = {num(h.get('level')): h for h in kids(el, 'paraHead')}
    out = b''
    for lv in range(1, 8):
        out += head_record(heads.get(lv))
    out += struct.pack('<H', num(el.get('start')))
    for lv in range(1, 8 if ver >= (5, 0, 3, 0) else 1):          # the start numbers of the levels: from 5.0.3.0 (172 bytes; 144 before, HW77)
        h = heads.get(lv)
        out += struct.pack('<I', num(h.get('start'), 1) if h is not None else 1)
    if ver >= (5, 1, 0, 0) and any(lv > 7 for lv in heads):                        # levels 8-10 (files of Hangul 2010 and later)
        for lv in range(8, 11):
            out += head_record(heads.get(lv))
        for lv in range(8, 11):
            h = heads.get(lv)
            out += struct.pack('<I', num(h.get('start'), 1) if h is not None else 1)
    return out


def head_record(h):
    if h is None:
        return struct.pack('<IhhI', 0, 0, 0, 0xFFFFFFFF) + wstr('')
    attr = om.inverse(om.ALIGN3).get(h.get('align', 'LEFT'), 0)
    attr |= num(h.get('useInstWidth')) << 2 | num(h.get('autoIndent')) << 3
    attr |= {'PERCENT': 0, 'HWPUNIT': 1}.get(h.get('textOffsetType', 'PERCENT'), 0) << 4
    attr |= pick(NUM_FORMAT, h.get('numFormat', 'DIGIT'), 'number format') << 5
    return (struct.pack('<IhhI', attr, num(h.get('widthAdjust')), num(h.get('textOffset')), num(h.get('charPrIDRef'), 0xFFFFFFFF) & 0xFFFFFFFF)
            + wstr(h.text or ''))


def bullet(el, ver, bin_ref=None):
    """BULLET: the paragraph head (as a numbering level), the bullet character, the picture flag (INT32), the picture
    (contrast, brightness, effect, BinData id WORD), [the check mark character, from 5.1]. Measured in Hangul 2024: 23 bytes in
    5.0.3.0 files, 25 in 5.1.1.0; three bullets with three different pictures gave the ids 1, 2, 3 in the order of use (rule HW72)."""
    only(el, 'bullet')
    ph = first(el, 'paraHead')
    img = first(el, 'img')
    flag, info = 0, bytes(5)
    if num(el.get('useImage')):
        if img is None:
            raise Unsupported(f'picture bullet id={el.get("id")} without its picture (header.xml)')
        bid = (bin_ref or {}).get(img.get('binaryItemIDRef'))
        if bid is None:
            raise Unsupported(f'picture bullet id={el.get("id")}: picture "{img.get("binaryItemIDRef")}" is not in the package (header.xml)')
        flag = 1
        info = struct.pack('<bbBH', snum(img.get('contrast')), snum(img.get('bright')),
                           pick(om.inverse(om.IMG_EFFECT), img.get('effect', 'REAL_PIC'), 'picture effect'), bid)
    attr = om.inverse(om.ALIGN3).get(ph.get('align', 'LEFT'), 0) | num(ph.get('useInstWidth')) << 2         | num(ph.get('autoIndent')) << 3 | {'PERCENT': 0, 'HWPUNIT': 1}.get(ph.get('textOffsetType', 'PERCENT'), 0) << 4         | num(ph.get('checkable')) << 9
    ch = lambda v: ord(v) if v else 0
    return (struct.pack('<IhhI', attr, snum(ph.get('widthAdjust')), snum(ph.get('textOffset')),
                        num(ph.get('charPrIDRef'), 0xFFFFFFFF) & 0xFFFFFFFF)
            + struct.pack('<H', ch(el.get('char')))
            + (struct.pack('<i', flag) + info if ver >= (5, 0, 3, 0) else b'')              # 14 bytes before 5.0.3.0 (HW77)
            + (struct.pack('<H', ch(el.get('checkedChar'))) if ver >= (5, 1, 0, 0) else b''))


def memo_shape(el):
    """MEMO_SHAPE (rule HW73): width, line type, line width (a whole number), line / fill / active colours, memo type."""
    only(el, 'memoPr')
    lw = re.match(r'\s*(\d+(?:\.\d+)?)', el.get('lineWidth') or '0')
    mt = pick(om.inverse(om.MEMO_TYPE), el.get('memoType', 'NOMAL'), 'memo type')
    return (struct.pack('<IBB', num(el.get('width')), pick(om.inverse(om.MEMO_LINE), el.get('lineType', 'SOLID'), 'memo line type'),
                        int(float(lw.group(1))) if lw else 0)
            + b''.join(struct.pack('<I', color(el.get(k), 0) & 0xFFFFFF) for k in ('lineColor', 'fillColor', 'activeColor'))
            + struct.pack('<I', mt | (0x80000000 if mt else 0)))


# The print settings of settings.xml (`PrintInfo`) are the document data record 0x1B of Hangul: a parameter set header and seven
# items (id, type, value), measured by changing each setting (rule HW81). name -> (item id, item type, default)
PRINT_ITEMS = [('PrintMethod', 0x4006, 6), ('PrintAutoHeadNote', 0x400E, 6), ('PrintAutoFootNote', 0x400A, 6),
               ('ZoomX', 0x401F, 7), ('BinderHoleType', 0x401D, 6), ('PrintCropMark', 0x401A, 6), ('OverlapSize', 0x4010, 7),
               ('ZoomY', 0x4020, 7)]


def print_info(cfg):
    for k in cfg:
        if k not in {n for n, _, _ in PRINT_ITEMS}:
            raise Unsupported(f'print setting "{k}" (settings.xml)')
    items = [(iid, typ, cfg[name]) for name, iid, typ in PRINT_ITEMS if name in cfg]      # the items the file has, in Hangul's order
    out = struct.pack('<HHHHHHHH', 0x021C, 1, 0, 0x0207, 0x8000, 0x0207, len(items), 0)
    for iid, typ, v in items:
        out += struct.pack('<HHi', iid, typ, 1 if v == 'true' else 0 if v == 'false' else int(v))
    return out


TRACK_KINDS = {'Insert': 0x10, 'Delete': 0x11, 'CharShape': 0x12, 'ParaShape': 0x13}


def track_change(el):
    """TRACK_CHANGE (HW88; layout from the files of Hangul 2024 that were read): the type, the local time as five words (the HWPX
    has it as UTC minus 9 hours), the author, 6 bytes, [the shape id for a shape change] and the hidden flag."""
    import datetime
    kind = pick(TRACK_KINDS, el.get('type'), 'track change type')
    m = re.match(r'(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)', el.get('date') or '')
    t = (datetime.datetime(*map(int, m.groups())) + datetime.timedelta(hours=9)) if m else datetime.datetime(1980, 1, 1)
    out = struct.pack('<I6H', kind, t.year, t.month, t.day, t.hour, t.minute, num(el.get('authorID'))) + bytes(6)
    if kind >= 0x12:
        out += struct.pack('<I', num(el.get('charshapeID' if kind == 0x12 else 'parashapeID')))
    return out + struct.pack('<I', num(el.get('hide')))


def track_author(el):
    """TRACK_CHANGE_AUTHOR (HW88): the name (a 4-byte length, UTF-16), the mark and 4 bytes Hangul fills with noise (0 here)."""
    name = el.get('name', '')
    return struct.pack('<I', len(name)) + name.encode('utf-16-le') + struct.pack('<I', num(el.get('mark'))) + bytes(4)


def para_shape(el, ver=(5, 0, 5, 0)):
    a1 = 0
    al = first(el, 'align')
    a1 |= pick(HALIGN, al.get('horizontal', 'JUSTIFY') if al is not None else 'JUSTIFY', 'alignment') << 2
    a1 |= pick(VALIGN, al.get('vertical', 'BASELINE') if al is not None else 'BASELINE', 'vertical alignment') << 20
    bs = first(el, 'breakSetting')
    if bs is not None:
        a1 |= om.inverse(om.LATIN_BREAK).get(bs.get('breakLatinWord'), 0) << 5
        a1 |= (1 if bs.get('breakNonLatinWord') == 'KEEP_WORD' else 0) << 7      # saved: BREAK_WORD = bit clear
        a1 |= num(bs.get('widowOrphan')) << 16 | num(bs.get('keepWithNext')) << 17 | num(bs.get('keepLines')) << 18
        a1 |= num(bs.get('pageBreakBefore')) << 19
    a1 |= num(el.get('snapToGrid')) << 8 | num(el.get('condense')) << 9 | num(el.get('fontLineHeight')) << 22
    hd = first(el, 'heading')
    for sw in kids(el, 'switch'):                           # the heading may sit in a switch: the <hp:case> branch (new
        for br in ('case', 'default'):                      # namespace) holds the outline level, <hp:default> only NONE
            h = first(first(sw, br), 'heading') if first(sw, br) is not None else None
            if h is not None:
                hd = hd if hd is not None else h
                break
    hdn = pick(HEADING, hd.get('type', 'NONE') if hd is not None else 'NONE', 'heading type')
    level = num(hd.get('level')) if hd is not None else 0
    a1 |= hdn << 23 | min(level, 6) << 25               # the level is kept for the heading type NONE too (Hangul's HWPX has level="1" there; HW81)
    bd = first(el, 'border')
    if bd is not None:
        a1 |= num(bd.get('connect')) << 28 | num(bd.get('ignoreMargin')) << 29
    a2 = 0
    au = first(el, 'autoSpacing')
    if au is not None:
        a2 |= num(au.get('eAsianEng')) << 4 | num(au.get('eAsianNum')) << 5
    a2 |= num(el.get('suppressLineNumbers')) << 6
    a2 |= om.inverse(om.TEXT_DIR).get(el.get('textDir', 'AUTO'), 0) << 2         # measured in Hangul 2024 (rule HW100)
    # the margins and the line spacing: the <hp:default> branch holds Hangul's own units (twice the HwpUnitChar ones)
    holder = el
    for sw in kids(el, 'switch'):                          # the switch that holds the margin (another one holds the heading)
        h = first(sw, 'default') if first(sw, 'default') is not None else first(sw, 'case')
        if h is not None and first(h, 'margin') is not None:
            holder = h
            break
    mg = first(holder, 'margin')
    v = {k: snum(first(mg, k).get('value')) if mg is not None and first(mg, k) is not None else 0
         for k in ('intent', 'left', 'right', 'prev', 'next')}
    ls = first(holder, 'lineSpacing')
    lt = pick(LINE_SPACING, ls.get('type', 'PERCENT') if ls is not None else 'PERCENT', 'line spacing type')
    lv = num(ls.get('value'), 160) if ls is not None else 160
    a1 |= lt & 3
    bf = num(bd.get('borderFillIDRef')) if bd is not None else 0
    offs = [num(bd.get(k)) for k in ('offsetLeft', 'offsetRight', 'offsetTop', 'offsetBottom')] if bd is not None else [0] * 4
    out = (struct.pack('<Iiiiiii', a1, v['left'], v['right'], v['intent'], v['prev'], v['next'], lv)
           + struct.pack('<HHH', num(el.get('tabPrIDRef')), num(hd.get('idRef')) if hd is not None else 0, bf)
           + struct.pack('<4h', *offs))
    if ver >= (5, 1, 1, 0):
        a2 |= 8                                             # Hangul 2024 sets bit 3 whenever it saves a HWPX as .hwp (HW81)
    if ver >= (5, 0, 1, 7):
        out += struct.pack('<I', a2)
    if ver >= (5, 0, 2, 5):
        out += struct.pack('<II', lt, lv)
    if ver >= (5, 1, 0, 0):
        out += struct.pack('<I', level)                    # the outline level of files of version 5.1 and later (1-10)
    return out


def style(el):
    only(el)
    char = el.get('type') == 'CHAR'
    # a character style has no paragraph shape (hwp2hwpx writes an unrelated number there): 0, as Hangul stores it
    # the lock bit is bit 2 of the property byte (a locked style: 4 or 5) and the last word stays 0 (Hangul 2024, HW81, HW100)
    return (wstr(el.get('name', '')) + wstr(el.get('engName', '')) + struct.pack('<BB', (1 if char else 0) | num(el.get('lockForm')) << 2,
            num(el.get('nextStyleIDRef'))) + struct.pack('<hHHH', num(el.get('langID'), 1042),
                                                      0 if char else num(el.get('paraPrIDRef')),
                                                      num(el.get('charPrIDRef')), 0))


# ---- the whole header ---------------------------------------------------------------------------------------------------
def head_records(head, settings, bin_items, ver=(5, 0, 5, 0), bin_ref=None):
    """`head` = the <hh:head> element; `settings` = {'listIDRef', 'paraIDRef', 'pos'} of the caret; `bin_items` = a list
    of (ext, type) of the embedded pictures in id order (BIN_DATA records). Returns the DocInfo records."""
    ref = first(head, 'refList')
    # what has no record writer yet is refused, never dropped (the counts of ID_MAPPINGS must match the records written)
    for c in head:
        if isinstance(c.tag, str) and ln(c) not in ('beginNum', 'refList', 'compatibleDocument', 'docOption', 'trackchageConfig', 'metaTag'):
            raise Unsupported(f'element hh:{ln(c)} in hh:head (header.xml)')
        if ln(c) == 'metaTag' and (c.text or '').strip() not in ('', '{"name":""}'):
            raise Unsupported('document meta tag with content (hh:metaTag, header.xml)')
    for c in ref:
        if isinstance(c.tag, str) and ln(c) not in ('fontfaces', 'borderFills', 'charProperties', 'tabProperties', 'numberings',
                                                    'bullets', 'paraProperties', 'styles', 'memoProperties', 'trackChanges', 'trackChangeAuthors'):
            if len(c):
                raise Unsupported(f'{len(c)} x hh:{ln(c)[:-1] if ln(c).endswith("s") else ln(c)} in hh:{ln(c)} (header.xml): no record writer yet')
    recs = []
    faces = {}
    for ff in kids(first(ref, 'fontfaces'), 'fontface'):
        faces[ff.get('lang')] = kids(ff, 'font')
    border_fills = kids(first(ref, 'borderFills'), 'borderFill') if first(ref, 'borderFills') is not None else []
    chars = kids(first(ref, 'charProperties'), 'charPr') if first(ref, 'charProperties') is not None else []
    tabs = kids(first(ref, 'tabProperties'), 'tabPr') if first(ref, 'tabProperties') is not None else []
    nums = kids(first(ref, 'numberings'), 'numbering') if first(ref, 'numberings') is not None else []
    buls = kids(first(ref, 'bullets'), 'bullet') if first(ref, 'bullets') is not None else []
    paras = kids(first(ref, 'paraProperties'), 'paraPr') if first(ref, 'paraProperties') is not None else []
    styles = kids(first(ref, 'styles'), 'style') if first(ref, 'styles') is not None else []
    memos = kids(first(ref, 'memoProperties'), 'memoPr') if first(ref, 'memoProperties') is not None else []
    tcs = kids(first(ref, 'trackChanges'), 'trackChange') if first(ref, 'trackChanges') is not None else []
    tauth = kids(first(ref, 'trackChangeAuthors'), 'trackChangeAuthor') if first(ref, 'trackChangeAuthors') is not None else []
    bn = first(head, 'beginNum')
    bnv = [num(bn.get(k), 1) for k in ('page', 'footnote', 'endnote', 'pic', 'tbl', 'equation')] if bn is not None else [1] * 6
    recs.append([T['DOCUMENT_PROPERTIES'], 0, struct.pack('<H6HIII', num(head.get('secCnt'), 1), *bnv,
                                                         settings.get('listIDRef', 0), settings.get('paraIDRef', 0),
                                                         settings.get('pos', 0))])
    face_counts = [len(faces.get(L, [])) for L in LANGS]
    counts = [len(bin_items)] + face_counts + [len(border_fills), len(chars), len(tabs), len(nums), len(buls), len(paras),
                                               len(styles), len(memos), len(tcs), len(tauth)]
    n_ids = 18 if ver >= (5, 0, 3, 0) else 16 if ver >= (5, 0, 1, 0) else 15     # 72 / 64 / 60 bytes in 5.0.3+ / 5.0.1.7, 5.0.2.4 / 5.0.0.6 files (HW77)
    recs.append([T['ID_MAPPINGS'], 0, struct.pack('<%di' % n_ids, *counts[:n_ids])])
    for k, (ext, typ) in enumerate(bin_items, 1):
        if typ == 'LINK':                                     # `ext` is the finished record data of a linked picture (HW91)
            recs.append([T['BIN_DATA'], 1, ext])
            continue
        recs.append([T['BIN_DATA'], 1, struct.pack('<HH', {'LINK': 0, 'EMBEDDING': 1, 'STORAGE': 2}.get(typ, 1), k) + wstr(ext)])
    for L in LANGS:
        for f in faces.get(L, []):
            recs.append([T['FACE_NAME'], 1, face_name(f)])
    for b in border_fills:
        recs.append([T['BORDER_FILL'], 1, border_fill(b, bin_ref, ver)])
    for c in chars:
        recs.append([T['CHAR_SHAPE'], 1, char_shape(c, ver)])
    for t in tabs:
        recs.append([T['TAB_DEF'], 1, tab_def(t)])
    for n in nums:
        recs.append([T['NUMBERING'], 1, numbering(n, ver)])
    for bl in buls:
        recs.append([T['BULLET'], 1, bullet(bl, ver, bin_ref)])
    for p in paras:
        recs.append([T['PARA_SHAPE'], 1, para_shape(p, ver)])
    for s in styles:
        recs.append([T['STYLE'], 1, style(s)])
    for m in memos:
        recs.append([T['MEMO_SHAPE'], 1, memo_shape(m)])
    for a in tauth:
        recs.append([T['TRACK_CHANGE_AUTHOR'], 1, track_author(a)])
    for c in tcs:
        recs.append([T['TRACK_CHANGE'], 1, track_change(c)])
    if 'print' in settings:
        recs.append([T['DOC_DATA'], 0, print_info(settings['print'])])
    if ver >= (5, 0, 2, 0):                                 # the closing records by version (HW77, from 160 forms): 5.0.0.6 and 5.0.1.7 have none,
        recs.append([T['FORBIDDEN_CHAR'], 1, bytes(16)])                   # 5.0.2.4 has this one, 5.0.3.x and later have all four
        # forbidden characters: Hangul's default (nothing set)
    comp = first(head, 'compatibleDocument')
    lc = first(comp, 'layoutCompatibility') if comp is not None else None
    flag_bit = {name: (w, bit) for w, names in enumerate(om.COMPAT_FLAGS) for bit, name in enumerate(names) if name}
    words = [0] * 5
    for c in (lc if lc is not None else []):          # a flag element = its bit set (160 bits measured in Hangul 2024; HW85)
        if not isinstance(c.tag, str):
            continue
        if ln(c) not in flag_bit:
            raise Unsupported(f'layout compatibility flag hh:{ln(c)} (header.xml): not a flag Hangul 2024 writes')
        w, bit = flag_bit[ln(c)]
        words[w] |= 1 << bit
    target = pick(om.inverse(om.COMPAT_TARGET), comp.get('targetProgram', 'HWP201X') if comp is not None else 'HWP201X', 'compatible document target')
    if ver >= (5, 0, 3, 0):
        recs.append([T['COMPATIBLE_DOCUMENT'], 0, struct.pack('<I', target)])
        recs.append([T['LAYOUT_COMPATIBILITY'], 1, struct.pack('<5I', *words)])   # layout compatibility flags
        tc = first(head, 'trackchageConfig')
        recs.append([T['TRACK_CHANGE_FLAGS'], 1, struct.pack('<I', num(tc.get('flags'), 56) if tc is not None else 56) + bytes(1028)])
    return recs
