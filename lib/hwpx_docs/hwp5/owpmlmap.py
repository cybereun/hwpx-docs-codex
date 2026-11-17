"""Tables shared by the HWP -> OWPML converter (owpml*.py) and, inverted, the OWPML -> HWP writer (fo_*.py): enum names,
colours, units, the XML writer.

Every table was read from pairs of one document saved by Hangul as .hwp and as .hwpx (the test pairs of hwp2hwpx), so the
OWPML spelling is Hangul's own. Where no pair uses a value the entry is marked `# unseen` (spelling from core/units.py,
which Hangul opens).
"""
import re
import struct

# border / line types: number in HWP -> OWPML. One numbering for every line (borders, drawing objects, picture borders, tab leaders):
# 2 DOT, 3 DASH, in Hangul's own HWPX of 153 forms (HW14, HW82)
LINE = ['NONE', 'SOLID', 'DOT', 'DASH', 'DASH_DOT', 'DASH_DOT_DOT', 'LONG_DASH', 'CIRCLE', 'DOUBLE_SLIM', 'SLIM_THICK',
        'THICK_SLIM', 'SLIM_THICK_SLIM', 'WAVE', 'DOUBLEWAVE', 'THICK3D', 'THICKREV3D', '3D', 'REV3D']
WIDTH = ['0.1', '0.12', '0.15', '0.2', '0.25', '0.3', '0.4', '0.5', '0.6', '0.7', '1.0', '1.5', '2.0', '3.0', '4.0', '5.0']
LANGS = ['HANGUL', 'LATIN', 'HANJA', 'JAPANESE', 'OTHER', 'SYMBOL', 'USER']
LANG_ATTR = ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']
ALIGN = ['JUSTIFY', 'LEFT', 'RIGHT', 'CENTER', 'DISTRIBUTE', 'DISTRIBUTE_SPACE']
VALIGN = ['BASELINE', 'TOP', 'CENTER', 'BOTTOM']
NUMFMT = ['DIGIT', 'CIRCLED_DIGIT', 'ROMAN_CAPITAL', 'ROMAN_SMALL', 'LATIN_CAPITAL', 'LATIN_SMALL', 'CIRCLED_LATIN_CAPITAL',
          'CIRCLED_LATIN_SMALL', 'HANGUL_SYLLABLE', 'CIRCLED_HANGUL_SYLLABLE', 'HANGUL_JAMO', 'CIRCLED_HANGUL_JAMO',
          'HANGUL_PHONETIC', 'IDEOGRAPH', 'CIRCLED_IDEOGRAPH', 'DECAGON_CIRCLE', 'DECAGON_CIRCLE_HANJA']   # 15, 16 unseen
SYMMARK = ['NONE', 'DOT_ABOVE', 'RING_ABOVE', 'TILDE', 'CARON', 'SIDE', 'COLON', 'GRAVE_ACCENT', 'ACUTE_ACCENT',
           'CIRCUMFLEX', 'MACRON', 'HOOK_ABOVE', 'DOT_BELOW']
# underline shape (CHAR_SHAPE bits 4-7) and strikeout shape (bits 26-29): all 16 values measured in Hangul 2024 (HW100)
UNDERLINE_SHAPE = ['SOLID', 'DOT', 'DASH', 'DASH_DOT', 'DASH_DOT_DOT', 'LONG_DASH', 'CIRCLE', 'DOUBLE_SLIM', 'SLIM_THICK',
                   'THICK_SLIM', 'SLIM_THICK_SLIM', 'WAVE', 'DOUBLEWAVE', 'THICK3D', 'THICKREV3D', '3D']
OUTLINE = ['NONE', 'SOLID', 'DOT', 'THICK', 'DASH', 'DASH_DOT', 'DASH_DOT_DOT']   # char outline: bits 8-10, not the line types
FONT_TYPE = ['UNKNOWN', 'TTF', 'HFT']
FAMILY = ['FCAT_UNKNOWN', 'FCAT_MYUNGJO', 'FCAT_GOTHIC', 'FCAT_SSERIF', 'FCAT_BRUSHSCRIPT', 'FCAT_DECORATIVE',
          'FCAT_NONRECTMJ', 'FCAT_NONRECTGT']
UNDER_POS = ['NONE', 'BOTTOM', 'CENTER', 'TOP']
# slide show effect of a presentation document (the parameter set below the section definition, item 0x4000), measured in Hangul
# 2024 for 0-69: 20 names, 20 and above make Hangul write no attribute (HW104)
PRESENT_EFFECT = ['none', 'overLeft', 'overRight', 'overUp', 'overDown', 'rectOut', 'rectIn', 'blindLeft', 'blindRight', 'blindUp',
                  'blindDown', 'cuttonHorzOut', 'cuttonHorzIn', 'cuttonVertOut', 'cuttonVertIn', 'moveLeft', 'moveRight', 'moveUp',
                  'moveDown', 'random']
CHAR_SHADOW = ['NONE', 'DROP', 'CONTINUOUS']
TAB_TYPE = ['LEFT', 'RIGHT', 'CENTER', 'DECIMAL']
HEADING = ['NONE', 'OUTLINE', 'NUMBER', 'BULLET']
LINE_SPACING = ['PERCENT', 'FIXED', 'BETWEEN_LINES', 'AT_LEAST']
SLASH = {0: 'NONE', 2: 'CENTER', 3: 'CENTER_BELOW', 6: 'CENTER_ABOVE', 7: 'ALL'}   # BORDER_FILL attr bits 2-4; unseen but NONE
ARROWS = ['NORMAL', 'ARROW', 'SPEAR', 'CONCAVE_ARROW', 'EMPTY_DIAMOND', 'EMPTY_CIRCLE', 'EMPTY_BOX', 'DIAMOND', 'CIRCLE', 'BOX']
ARROW_SIZE = ['SMALL_SMALL', 'SMALL_MEDIUM', 'SMALL_LARGE', 'MEDIUM_SMALL', 'MEDIUM_MEDIUM', 'MEDIUM_LARGE', 'LARGE_SMALL',
              'LARGE_MEDIUM', 'LARGE_LARGE']
# shadow of a drawing object: number in HWP -> OWPML. Measured in Hangul (variants of rect_no_fill saved as .hwp, 2026-11-16):
# the parallel kinds are spelt PARELLEL_* by Hangul (typo kept); a spelling Hangul does not know reads as 0, so only these 9 exist
SHADOW = ['NONE', 'PARELLEL_LEFTTOP', 'PARELLEL_RIGHTTOP', 'PARELLEL_LEFTBOTTOM', 'PARELLEL_RIGHTBOTTOM', 'SHEAR_LEFTTOP',
          'SHEAR_RIGHTTOP', 'SHEAR_LEFTBOTTOM', 'SHEAR_RIGHTBOTTOM']
# WordArt (글맵시) properties, measured in Hangul 2026-11-16 (the shape dword of a 0x5A record patched to 0..63, opened, saved as HWPX):
# 0..54 are the 55 shapes, 55..63 read as no shape. Alignment 0..4 (5..7 are dropped), shadow kinds are SHADOW above, font 1 TTF and
# 2 HTF (Hangul's spelling; 0, 3 and 4 do not open).
TEXT_SHAPE = [
    'PARALLELOGRAM', 'INVERTED_PARALLELOGRAM', 'INVERTED_UPWARD_CASCADE', 'INVERTED_DOWNWARD_CASCADE', 'UPWARD_CASCADE',
    'DOWNWARD_CASCADE', 'REDUCE_RIGHT', 'REDUCE_LEFT', 'ISOSCELES_TRAPEZOID', 'INVERTED_ISOSCELES_TRAPEZOID',
    'TOP_RIBBON_RECTANGLE', 'BOTTOM_RIBBON_RECTANGLE', 'CHEVRON_DOWN', 'CHEVRON', 'BOW_TIE', 'HEXAGON', 'WAVE1', 'WAVE2', 'WAVE3',
    'WAVE4', 'LEFT_TILT_CYLINDER', 'RIGHT_TILT_CYLINDER', 'BOTTOM_WIDE_CYLINDER', 'TOP_WIDE_CYLINDER', 'THIN_CURVE_UP1',
    'THIN_CURVE_UP2', 'THIN_CURVE_DOWN1', 'THIN_CURVE_DOWN2', 'INVERSED_FINGERNAIL', 'FINGERNAIL', 'GINKO_LEAF1', 'GINKO_LEAF2',
    'INFLATE_RIGHT', 'INFLATE_LEFT', 'INFLATE_UP_CONVEX', 'INFLATE_BOTTOM_CONVEX', 'DEFLATE_TOP', 'DEFLATE_BOTTOM', 'DEFLATE',
    'INFLATE', 'INFLATE_TOP', 'INFLATE_BOTTOM', 'RECTANGLE', 'LEFT_CYLINDER', 'CYLINDER', 'RIGHT_CYLINDER', 'CIRCLE', 'CURVE_DOWN',
    'ARCH_UP', 'ARCH_DOWN', 'SINGLE_LINE_CIRCLE1', 'SINGLE_LINE_CIRCLE2', 'TRIPLE_LINE_CIRCLE1', 'TRIPLE_LINE_CIRCLE2',
    'DOUBLE_LINE_CIRCLE']
TEXT_ALIGN = ['LEFT', 'RIGHT', 'CENTER', 'FULL', 'TABLE']
TEXT_FONT = {1: 'TTF', 2: 'HTF'}
# colour effects of a picture / effects colour: id in HWP -> OWPML name (patched into a written picture, opened, saved as HWPX).
# The other names of the schema (ALPHA*, RED*, GREEN*, BLUE*, GAMMA, INV_GAMMA, COMP, GRAY, INV) got no id in 0x000..0x2ff.
COLOR_EFFECT = {0x200: 'HUE', 0x201: 'HUE_MOD', 0x202: 'HUE_OFF', 0x203: 'SAT', 0x204: 'SAT_MOD', 0x205: 'SAT_OFF', 0x206: 'LUM',
                0x207: 'LUM_MOD', 0x208: 'LUM_OFF', 0x209: 'SHADE', 0x20a: 'TINT'}
# memo shape (MEMO_SHAPE, tag 0x5C), measured in Hangul 2026-11-16 in both directions: width DWORD, line type BYTE, line width BYTE
# (a whole number: Hangul reads "0.6mm" as 0 and writes the number as it is), three COLORREFs (line, fill, active), memo type DWORD
# (Hangul 2024 sets bit 31 for the types other than NOMAL when it saves a HWPX). The line type order differs from LINE above.
MEMO_LINE = ['NONE', 'SOLID', 'DOT', 'DASH', 'DASH_DOT', 'DASH_DOT_DOT', 'LONG_DASH', 'CIRCLE', 'DOUBLE_SLIM', 'SLIM_THICK',
             'THICK_SLIM', 'SLIM_THICK_SLIM', 'WAVE', 'DOUBLEWAVE', 'THICK3D', 'THICKREV3D']
MEMO_TYPE = ['NOMAL', 'USER_INSERT', 'USER_DELETE', 'USER_UPDATE']
# OLE object attribute (record 0x54, DWORD), measured in Hangul 2026-11-16 (HWPX -> .hwp): bits 0-7 drawing aspect (a bit each),
# bit 8 has moniker, bits 9-15 the equation base line, bits 16-21 the object type
OLE_ASPECT = {1: 'CONTENT', 2: 'THUMB_NAIL', 4: 'ICON', 8: 'DOC_PRINT'}
OLE_TYPE = ['UNKNOWN', 'EMBEDDED', 'LINK', 'STATIC', 'EQUATION']
HATCH = ['HORIZONTAL', 'VERTICAL', 'BACK_SLASH', 'SLASH', 'CROSS', 'CROSS_DIAGONAL']
# image fill mode (BORDER_FILL / shape fill, the mode byte) -> hc:imgBrush@mode, measured one value at a time in Hangul 2024 (HW53)
IMG_EFFECT = ['REAL_PIC', 'GRAY_SCALE', 'BLACK_WHITE']                     # picture effect (the record byte -> hc:img@effect)
GRADIENT = ['', 'LINEAR', 'RADIAL', 'CONICAL', 'SQUARE']                  # gradient type 1-4 -> hc:gradation@type
GRADIENT_NUM = {n: i for i, n in enumerate(GRADIENT) if n}
# ---- enums of the objects, notes, pages and forms: owpmlobj.py (reading) and fo_body.py / fo_form.py (writing) share one copy ----
OBJ_WRAP = ['SQUARE', 'TOP_AND_BOTTOM', 'BEHIND_TEXT', 'IN_FRONT_OF_TEXT']
OBJ_FLOW = ['BOTH_SIDES', 'LEFT_ONLY', 'RIGHT_ONLY', 'LARGEST_ONLY']
V_REL = ['PAPER', 'PAGE', 'PARA']
H_REL = ['PAPER', 'PAGE', 'COLUMN', 'PARA']
POS_VALIGN = ['TOP', 'CENTER', 'BOTTOM', 'INSIDE', 'OUTSIDE']
POS_HALIGN = ['LEFT', 'CENTER', 'RIGHT', 'INSIDE', 'OUTSIDE']
W_REL = ['PAPER', 'PAGE', 'COLUMN', 'PARA', 'ABSOLUTE']
H_REL_SZ = ['PAPER', 'PAGE', 'ABSOLUTE']
NUMBERING = ['NONE', 'PICTURE', 'TABLE', 'EQUATION']
APPLY_PAGE = ['BOTH', 'EVEN', 'ODD']
NUM_TYPE = ['PAGE', 'FOOTNOTE', 'ENDNOTE', 'PICTURE', 'TABLE', 'EQUATION', 'TOTAL_PAGE']      # 6: the page count (Hangul 2024)
NOTE_NUMBERING = ['CONTINUOUS', 'ON_SECTION', 'ON_PAGE']
GUTTER = ['LEFT_ONLY', 'LEFT_RIGHT', 'TOP_BOTTOM']
BORDER_AREA = ['PAPER', 'PAGE', 'BORDER']
COL_TYPE = ['NEWSPAPER', 'BALANCED_NEWSPAPER', 'PARALLEL']          # the schema's names (docs/rules.md S18); the writer once took `BALANCED`
COL_LAYOUT = ['LEFT', 'RIGHT', 'MIRROR']
LINE_WRAP = ['BREAK', 'SQUEEZE', 'KEEP']
SUB_VALIGN = ['TOP', 'CENTER', 'BOTTOM']
CAPTION_SIDE = ['LEFT', 'RIGHT', 'TOP', 'BOTTOM']
TBL_BREAK = ['NONE', 'TABLE', 'CELL']
COMPOSE = ['SPREAD', 'OVERLAP']
ALIGN3 = ['LEFT', 'CENTER', 'RIGHT']
CENTER_LINE = ['NONE', 'VERTICAL', 'HORIZONTAL', 'CROSS']
LATIN_BREAK = ['KEEP_WORD', 'HYPHENATION', 'BREAK_WORD']
TEXT_DIR = ['AUTO', 'RTL', 'LTR']
OUTLINE_STYLE = ['NORMAL', 'OUTER', 'INNER']
SHADOW_STYLE = ['OUTSIDE', 'INSIDE']
ARC_TYPE = ['NORMAL', 'PIE', 'CHORD']
FORM_VALUE = ['UNCHECKED', 'CHECKED']
FORM_BACK = ['TRANSPARENT', 'OPAQUE']
FORM_SCROLL = ['NONE', 'VERTICAL', 'HORIZONTAL', 'BOTH']
FORM_TAB = ['NEXT_OBJECT', 'INSERT_TAB']
EFFECT_ALIGN = ['TOP_LEFT', 'TOP', 'TOP_RIGHT', 'LEFT', 'CENTER', 'RIGHT', 'BOTTOM_LEFT', 'BOTTOM', 'BOTTOM_RIGHT']
CONNECT_TYPES = ['STRAIGHT_NOARROW', 'STRAIGHT_ONEWAY', 'STRAIGHT_BOTH', 'STROKE_NOARROW', 'STROKE_ONEWAY', 'STROKE_BOTH',
                 'ARC_NOARROW', 'ARC_ONEWAY', 'ARC_BOTH']
IMG_MODES = ['TILE', 'TILE_HORZ_TOP', 'TILE_HORZ_BOTTOM', 'TILE_VERT_LEFT', 'TILE_VERT_RIGHT', 'TOTAL', 'CENTER', 'CENTER_TOP',
             'CENTER_BOTTOM', 'LEFT_CENTER', 'LEFT_TOP', 'LEFT_BOTTOM', 'RIGHT_CENTER', 'RIGHT_TOP', 'RIGHT_BOTTOM', 'ZOOM']
# COMPATIBLE_DOCUMENT target program -> compatibleDocument@targetProgram (Hangul 2024 writes `Hunmin` for 3).
COMPAT_TARGET = ['HWP201X', 'HWP200X', 'MS_WORD', 'Hunmin']
# LAYOUT_COMPATIBILITY: five words; COMPAT_FLAGS[word][bit] = the `hh:layoutCompatibility` child Hangul 2024 writes for that bit
# (None = a bit that writes no child), the children in bit order. Measured one bit at a time (the measuring tool outside this repository:
# a patched .hwp opened in Hangul 2024, saved as HWPX); the bits that Hangul does not know are not listed (rule HW53).
COMPAT_FLAGS = [
    ['applyFontWeightToBold', 'useInnerUnderline', 'fixedUnderlineWidth', 'doNotApplyStrikeoutWithUnderline', None,
     'useLowercaseStrikeout', 'extendLineheightToOffset', None, 'treatQuotationAsLatin', 'doNotApplyDiacSymMarkOfNoneAndSix',
     None, 'adjustSpaceKerningMinus50'],
    ['doNotAlignWhitespaceOnRight', 'doNotAdjustWordInJustify', 'baseCharUnitOnEAsian', 'baseCharUnitOfIndentOnFirstChar',
     'adjustLineheightToFont', 'adjustBaselineInFixedLinespacing', 'applyPrevspacingBeneathObject',
     'applyNextspacingOfLastPara', 'applyAtLeastToPercent100Pct', 'doNotApplyAutoSpaceEAsianEng',
     'doNotApplyAutoSpaceEAsianNum', 'adjustParaBorderfillToSpacing', 'connectParaBorderfillOfEqualBorder',
     'adjustParaBorderOffsetWithBorder', 'extendLineheightToParaBorderOffset', 'applyParaBorderToOutside',
     'applyMinColumnWidthTo1mm', 'applyTabPosBasedOnSegment', 'breakTabOverLine', 'adjustVertPosOfLine',
     'doNotApplyWhiteSpaceHeight', 'doNotAlignLastPeriod', 'doNotAlignLastForbidden', 'adjustMarginFromAdjustLineheight'],
    ['baseLineSpacingOnLineGrid', 'applyCharSpacingToCharGrid', 'doNotApplyGridInHeaderFooter',
     'applyExtendHeaderFooterEachSection', 'doNotApplyHeaderFooterAtNoSpace', 'doNotApplyColSeparatorAtNoGap',
     'doNotApplyLinegridAtNoLinespacing'],
    ['doNotApplyImageEffect', 'doNotApplyShapeComment', 'doNotAdjustEmptyAnchorLine', 'overlapBothAllowOverlap',
     'doNotApplyVertOffsetOfForward', 'extendVertLimitToPageMargins', 'doNotHoldAnchorOfTable',
     'doNotFormattingAtBeneathAnchor', 'adjustBaselineOfObjectToBottom', 'adjustObjectHorizontally',
     'doNotAdjustGroupingCtrlCodePos'],
    ['doNotApplyExtensionCharCompose'],      # word 4 bit 0: the only bit left in the HWP200X preset, the only name left (not measured alone)
]


def inverse(table):
    """A number -> name table (list or dict) as name -> number: the writing side (fo_*.py) uses the same copy."""
    return {n: i for i, n in (table.items() if isinstance(table, dict) else enumerate(table))}


def color(v):
    """COLORREF 0x00BBGGRR -> '#RRGGBB'; 0xFFFFFFFF -> 'none'."""
    if v == 0xFFFFFFFF:
        return 'none'
    if v >> 24:                                    # a value with a high byte (alpha): Hangul prints '#%X' of alpha, red, green, blue
        return '#%X' % ((v & 0xFF000000) | (v & 255) << 16 | (v >> 8 & 255) << 8 | v >> 16 & 255)   # (no padding; HW100, 44 forms)
    return '#%02X%02X%02X' % (v & 255, (v >> 8) & 255, (v >> 16) & 255)


def mm(w):
    return (WIDTH[w] if w < len(WIDTH) else WIDTH[1]) + ' mm'


INVALID_XML = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]')
replaced = [0]               # characters XML cannot hold that were replaced by U+FFFD (convert() reports the count)


def esc(s, attr=False):
    s = str(s)
    if INVALID_XML.search(s):
        s, n = INVALID_XML.subn('�', s)
        replaced[0] += n
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s.replace('"', '&quot;') if attr else s


class El:
    """An XML element that serialises the way Hangul writes it (no white space between elements)."""
    __slots__ = ('tag', 'at', 'kids', 'text')

    def __init__(self, tag, at=None, *kids, text=None):
        self.tag, self.at, self.text = tag, dict(at or {}), text
        self.kids = [k for k in kids if k is not None]

    def add(self, *kids):
        self.kids += [k for k in kids if k is not None]
        return self

    def xml(self, out):
        out.append('<' + self.tag)
        for k, v in self.at.items():
            if v is not None:
                out.append(f' {k}="{esc(v, True)}"')
        if not self.kids and self.text is None:
            out.append('/>')
            return
        out.append('>')
        if self.text is not None:
            out.append(esc(self.text))
        for k in self.kids:
            if isinstance(k, str):                     # mixed content (hp:t: text between hp:tab, hp:lineBreak ...)
                out.append(esc(k))
            else:
                k.xml(out)
        out.append('</' + self.tag + '>')


NS = {'ha': 'http://www.hancom.co.kr/hwpml/2011/app', 'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
      'hp10': 'http://www.hancom.co.kr/hwpml/2016/paragraph', 'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
      'hc': 'http://www.hancom.co.kr/hwpml/2011/core', 'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
      'hhs': 'http://www.hancom.co.kr/hwpml/2011/history', 'hm': 'http://www.hancom.co.kr/hwpml/2011/master-page',
      'hpf': 'http://www.hancom.co.kr/schema/2011/hpf', 'dc': 'http://purl.org/dc/elements/1.1/',
      'opf': 'http://www.idpf.org/2007/opf/', 'ooxmlchart': 'http://www.hancom.co.kr/hwpml/2016/ooxmlchart',
      'hwpunitchar': 'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar', 'epub': 'http://www.idpf.org/2007/ops',
      'config': 'urn:oasis:names:tc:opendocument:xmlns:config:1.0'}
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


def document(root):
    """Serialise `root` with the namespace declarations Hangul puts on every part's root element."""
    root.at = {**{f'xmlns:{k}': v for k, v in NS.items()}, **root.at}
    out = [DECL]
    root.xml(out)
    return ''.join(out).encode('utf-8')


class Reader:
    """Little-endian reader over a record payload."""

    def __init__(self, data, i=0):
        self.d, self.i = data, i

    def u(self, f):
        v = struct.unpack_from('<' + f, self.d, self.i)
        self.i += struct.calcsize('<' + f)
        return v if len(v) > 1 else v[0]

    def left(self):
        return len(self.d) - self.i

    def wstr(self):
        n = self.u('H')
        s = self.d[self.i:self.i + 2 * n].decode('utf-16-le', 'surrogatepass')
        self.i += 2 * n
        return s

    def raw(self, n):
        b = self.d[self.i:self.i + n]
        self.i += n
        return b
