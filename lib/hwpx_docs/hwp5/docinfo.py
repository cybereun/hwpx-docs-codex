"""DocInfo of an HWP 5.0 file: fonts, border fills, char shapes, para shapes, styles, pictures (rules HW11-HW14).

  DocInfo(package)   .faces[lang] = [names], .border_fills[id] = {sides, fill, slash, back, diag},
                     .chars[id] = spec char props (as core.read gives them), .paras[id] = spec para props,
                     .styles[id] = name, .bins[id] = (stream path, extension)
Ids: border fills count from 1 (as Hangul refers to them), the others from 0.
"""
import struct

from . import fmt
from . import owpmlmap
from .owpmlmap import LANG_ATTR, LINE, OUTLINE, WIDTH

# One numbering for every line (HW82): 2 = dot, 3 = dash. Measured in Hangul 2024's own .hwp of a variant HWPX: border sides DOT / DASH /
# LONG_DASH / DASH_DOT -> 2 / 3 / 6 / 4 in BORDER_FILL, underline shapes DOT / DASH -> 1 / 2 in CHAR_SHAPE (the number minus 1).
LINE_TYPES = [x.lower() for x in LINE]
ALIGN = ['justify', 'left', 'right', 'center', 'distribute', 'divide']
UNDER_SHAPES = LINE_TYPES[1:]          # underline / strike shapes: 0 = solid ...


def color(v):
    """COLORREF (0x00BBGGRR) -> '#RRGGBB'; 0xFFFFFFFF -> 'none'."""
    if v == 0xFFFFFFFF:
        return 'none'
    return '#%02X%02X%02X' % (v & 255, (v >> 8) & 255, (v >> 16) & 255)


def line(t, w, c):
    """A border side as core.read writes it: '<width>mm <type> #RRGGBB', 'none' or 'none <w> <colour>'."""
    width = WIDTH[w] if w < len(WIDTH) else '0.12'
    col = color(c)
    if t == 0:
        return 'none' if (width, col) in (('0.12', '#000000'), ('0.1', '#000000')) else f'none {width}mm {col}'
    return f'{width}mm {LINE_TYPES[t] if t < len(LINE_TYPES) else "solid"} {col}'


class Reader(owpmlmap.Reader):
    def wstr(self):                    # a lone surrogate becomes U+FFFD here: the spec is text (the other reader keeps it)
        n = self.u('H')
        s = self.d[self.i:self.i + 2 * n].decode('utf-16-le', 'replace')
        self.i += 2 * n
        return s


class DocInfo:
    def __init__(self, pk):
        self.version = pk.version
        recs = pk.records('DocInfo')
        by = {}
        for tag, lvl, d in recs:
            by.setdefault(tag, []).append(d)
        T = fmt.T
        ids = struct.unpack_from('<%di' % (len(by.get(T['ID_MAPPINGS'], [b''])[0]) // 4), by.get(T['ID_MAPPINGS'], [b''])[0])
        counts = list(ids) + [0] * 18
        self.faces, k = {}, 0
        names = [self.face(d) for d in by.get(T['FACE_NAME'], [])]
        for n, lang in enumerate(LANG_ATTR):
            self.faces[lang] = names[k:k + counts[1 + n]]
            k += counts[1 + n]
        self.border_fills = {i + 1: self.border_fill(d) for i, d in enumerate(by.get(T['BORDER_FILL'], []))}
        self.tabs = [self.tab_def(d) for d in by.get(T['TAB_DEF'], [])]
        self.chars = [self.char_shape(d) for d in by.get(T['CHAR_SHAPE'], [])]
        self.paras = [self.para_shape(d) for d in by.get(T['PARA_SHAPE'], [])]
        self.styles = {}
        for i, d in enumerate(by.get(T['STYLE'], [])):
            r = Reader(d)
            self.styles[i] = r.wstr()
        self.bins = {}
        for i, d in enumerate(by.get(T['BIN_DATA'], [])):
            r = Reader(d)
            attr = r.u('H')
            if attr & 0xF in (1, 2) and r.left() >= 2:
                bid = r.u('H')
                ext = r.wstr() if r.left() >= 2 else ''
                self.bins[i + 1] = ('BinData/BIN%04X.%s' % (bid, ext), ext.lower())

    @staticmethod
    def face(d):
        r = Reader(d)
        r.u('B')
        return r.wstr()

    def face_name(self, lang, i):
        lst = self.faces.get(lang, [])
        return lst[i] if i < len(lst) else (lst[0] if lst else '함초롬바탕')

    @staticmethod
    def border_fill(d):
        r = Reader(d)
        attr = r.u('H')
        sides = {}
        for k in ('left', 'right', 'top', 'bottom'):
            t, w, c = r.u('BBI')
            sides[k] = line(t, w, c)
        dt, dw, dc = r.u('BBI')
        fill = None
        if r.left() >= 4:
            ft = r.u('I')
            if ft & 1 and r.left() >= 12:
                bg, _, _ = r.u('IIi')
                fill = None if color(bg) == 'none' else color(bg)
        slash = bool(attr >> 2 & 7)
        back = bool(attr >> 5 & 7)
        return dict(sides=sides, fill=fill, slash=slash, back=back, diag=line(dt or 1, dw, dc))

    @staticmethod
    def tab_def(d):
        """TAB_DEF -> spec `tabs` (None when it has no stops); positions are stored at twice HWPUNIT (HW12)."""
        if len(d) < 8:
            return None
        attr, n = struct.unpack_from('<II', d, 0)
        leaders = LINE_TYPES
        stops = []
        for k in range(min(n, (len(d) - 8) // 8)):
            pos, typ, fill = struct.unpack_from('<IBB', d, 8 + 8 * k)
            stops.append({'pos': round(pos / 2 / 7200 * 25.4, 3), 'type': ['left', 'right', 'center', 'decimal'][min(typ, 3)],
                          'leader': leaders[fill] if fill < len(leaders) else 'none'})
        if not stops:
            return None
        auto = {'auto_left': bool(attr & 1), 'auto_right': bool(attr & 2)}
        return dict(stops=stops, **auto) if any(auto.values()) else stops

    def char_shape(self, d):
        r = Reader(d)
        face = r.u('7H')
        ratio, spacing, rel, offset = r.u('7B'), r.u('7b'), r.u('7B'), r.u('7b')
        base, attr = r.u('iI')
        r.u('bb')
        text, under, shade, shadow = r.u('IIII')
        bfid = r.u('H') if r.left() >= 2 else 0
        strike_c = r.u('I') if r.left() >= 4 else text

        def seven(v):
            return v[0] if len(set(v)) == 1 else list(v)
        c = color(text)
        out = dict(font=self.face_name('hangul', face[0]), size=round(base / 100, 2), bold=bool(attr & 2),
                   italic=bool(attr & 1), color=c, shade=color(shade), spacing=seven(spacing), ratio=seven(ratio),
                   rel_size=seven(rel), offset=seven(offset), sup=bool(attr >> 15 & 1), sub=bool(attr >> 16 & 1),
                   emboss=bool(attr >> 13 & 1), engrave=bool(attr >> 14 & 1), kerning=bool(attr >> 30 & 1),
                   font_space=bool(attr >> 25 & 1))
        em = attr >> 21 & 15
        out['emphasis'] = None if not em else ['dot_above', 'ring_above', 'tilde', 'caron', 'side', 'colon',
                                               'grave_accent', 'acute_accent', 'circumflex', 'macron', 'hook_above',
                                               'dot_below'][min(em - 1, 11)]
        for n, lang in enumerate(LANG_ATTR[1:], 1):
            f = self.face_name(lang, face[n])
            if f != out['font']:
                out['font_' + lang] = f
        ut, us = attr >> 2 & 3, attr >> 4 & 15
        if ut == 0:
            out['underline'] = False
        elif ut == 1 and us == 0:
            out['underline'] = True if color(under) == c else color(under)
        else:
            out['underline'] = {'pos': {1: 'bottom', 2: 'center', 3: 'top'}.get(ut, 'bottom'),
                                'shape': UNDER_SHAPES[us] if us < len(UNDER_SHAPES) else 'solid', 'color': color(under)}
        st, ss = attr >> 18 & 7, attr >> 26 & 15
        if not st:
            out['strike'] = False
        else:
            shape = UNDER_SHAPES[ss] if ss < len(UNDER_SHAPES) else 'solid'
            out['strike'] = True if shape == 'solid' and color(strike_c) == c else {'shape': shape, 'color': color(strike_c)}
        ol = attr >> 8 & 7
        out['outline'] = False if not ol else (True if ol == 1 else OUTLINE[min(ol, len(OUTLINE) - 1)].lower())   # as core.read
        sh = attr >> 11 & 3
        out['shadow'] = False if not sh else {'type': 'drop' if sh == 1 else 'continuous', 'color': color(shadow)}
        bf = self.border_fills.get(bfid)
        if bfid not in (0, 2) and bf:
            out['char_border'] = {k: v for k, v in bf['sides'].items() if v != 'none'} or None
            out['char_fill'] = bf['fill']
        return out

    def para_shape(self, d):
        r = Reader(d)
        a1, left, right, indent, prev, nxt, ls_old = r.u('Iiiiiii')
        tab_id, head_id, bf_id = r.u('HHH')
        offs = r.u('4h')
        a2 = r.u('I') if r.left() >= 4 else 0
        a3, ls_new = (r.u('II') if r.left() >= 8 else (None, None))
        # values are stored at twice Hangul's HWPUNIT (core.read reads the HwpUnitChar case, which holds half)
        half = lambda v: round(v / 200, 2)
        if a3 is not None:
            lt, lv = a3 & 31, ls_new
        else:
            lt, lv = a1 & 3, ls_old
        line = lv if lt == 0 else {1: 'fixed', 2: 'between', 3: 'at_least'}.get(lt, 'fixed')
        if lt:
            line = {line: half(lv)}
        out = dict(align=ALIGN[a1 >> 2 & 7] if (a1 >> 2 & 7) < len(ALIGN) else 'justify', indent=half(indent),
                   left=half(left), right=half(right), before=half(prev), after=half(nxt), line=line,
                   keep_next=bool(a1 >> 17 & 1), keep_lines=bool(a1 >> 18 & 1), page_break_before=bool(a1 >> 19 & 1),
                   widow=bool(a1 >> 16 & 1), word_break='char' if a1 >> 7 & 1 else 'word', snap=bool(a1 >> 8 & 1),
                   line_valign=['baseline', 'top', 'center', 'bottom'][a1 >> 20 & 3], condense=a1 >> 9 & 127,
                   latin_break={0: 'word', 1: 'hyphen', 2: 'char'}.get(a1 >> 5 & 3, 'word'),
                   autospace=bool(a2 >> 4 & 1))
        if tab_id < len(self.tabs) and self.tabs[tab_id]:
            out['tabs'] = self.tabs[tab_id]
        heading = a1 >> 23 & 3
        if heading == 1:
            out['outline_level'] = a1 >> 25 & 7
        bf = self.border_fills.get(bf_id)
        if bf and (any(v != 'none' for v in bf['sides'].values()) or bf['fill']):
            out['border'] = {k: v for k, v in bf['sides'].items() if v != 'none'}
            if bf['fill']:
                out['fill'] = bf['fill']
            out['border_offset'] = [round(v / 7200 * 25.4, 3) for v in offs]
            if a1 >> 28 & 1:
                out['border_connect'] = True
        return out
