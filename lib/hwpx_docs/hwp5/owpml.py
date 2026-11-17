"""HWP 5.0 -> HWPX, record by record (rules HW29-): the DocInfo and BodyText records become the OWPML elements they
stand for. No spec in between (that is `tospec`, the approximate route); nothing is guessed, nothing is dropped quietly:
a record or a control this converter has no mapping for stops the conversion with `Unsupported` (`UNSUPPORTED <tag>
<place>`).

  convert(src.hwp, dst.hwpx)     the whole package
  Unsupported                    raised for a record / control without a mapping

Files: owpmlmap.py (tables, XML writer), owpml.py (package, header.xml), owpmlsec.py (section*.xml: paragraphs, runs,
sections, columns), owpmlobj.py (controls and drawing objects).
"""
import re
import struct

from . import fmt
from . import owpmlmap as om
from .fmt import Unsupported
from .owpmlmap import (ALIGN, CHAR_SHADOW, COMPAT_FLAGS, COMPAT_TARGET, FAMILY, FONT_TYPE, HEADING, IMG_EFFECT, LANG_ATTR, LANGS, LINE, LINE_SPACING, NUMFMT, OUTLINE,
                       SLASH, SYMMARK, TAB_TYPE, UNDER_POS, UNDERLINE_SHAPE, VALIGN,
                       El, Reader, color, document, mm)

T = fmt.T


CONTROL_NAMES = {'tcmt': 'hidden comment', 'tdut': 'ruby text', 'tcps': 'overlapping letters', 'bokm': 'bookmark', 'idxm': 'index mark',
                 'secd': 'section definition', 'cold': 'columns', 'tbl ': 'table', 'gso ': 'drawing object', 'form': 'form object',
                 'eqed': 'equation', 'head': 'header', 'foot': 'footer', 'fn  ': 'footnote', 'en  ': 'endnote', 'atno': 'auto number',
                 'nwno': 'new number', 'pgnp': 'page number', 'pghd': 'page hiding'}
NEXT_STEP = 'Open the file in Hangul, save it again, then run the command again (or use `hd convert`).'


def short_record_text(e, what=''):
    """The words for a record that is shorter than its layout: how many bytes it has of how many, and what to do next.
    `e` is the struct / index error; `what` names the control, for example "control 'tcmt' (hidden comment)"."""
    import re
    m = re.search(r'at least (\d+) bytes.*actual buffer size is (\d+)', str(e))
    size = f'the record has {m.group(2)} of {m.group(1)} bytes' if m else 'the record is shorter than its layout'
    return f'{what + ": " if what else ""}{size}. {NEXT_STEP}'


def tag_name(tag):
    for k, v in T.items():
        if v == tag:
            return k
    return f'0x{tag:X}'


# ---- header.xml --------------------------------------------------------------------------------------------------------
class Head:
    """DocInfo -> header.xml. Ids: border fills count from 1 (as Hangul writes them), all the others from 0."""

    def __init__(self, pk):
        self.pk = pk
        # Hangul of the 2014 generation (files 5.0.5.x) writes HWPX a little differently from Hangul 2018+ (5.1.x, and the
        # 5.0.2.x file the 2020 build converted): runs and numbering levels. 12 of the 13 pairs with a 5.0.5.x file say so.
        self.legacy = 0x05000500 <= pk.version < 0x05010000
        self.by = {}
        for tag, lvl, d in pk.records('DocInfo'):
            self.by.setdefault(tag, []).append(d)
        self.known = {T[k] for k in ('DOCUMENT_PROPERTIES', 'ID_MAPPINGS', 'BIN_DATA', 'FACE_NAME', 'BORDER_FILL',
                                     'CHAR_SHAPE', 'TAB_DEF', 'NUMBERING', 'BULLET', 'PARA_SHAPE', 'STYLE', 'DOC_DATA',
                                     'COMPATIBLE_DOCUMENT', 'LAYOUT_COMPATIBILITY', 'TRACK_CHANGE_FLAGS', 'MEMO_SHAPE',
                                     'FORBIDDEN_CHAR', 'TRACK_CHANGE', 'TRACK_CHANGE_AUTHOR')}
        for tag in self.by:
            if tag not in self.known:
                raise Unsupported(tag_name(tag), 'DocInfo')
        ids = self.by.get(T['ID_MAPPINGS'], [b''])[0]
        self.counts = list(struct.unpack_from('<%di' % (len(ids) // 4), ids)) + [0] * 20
        self.bins = self.bin_items()

    def bin_items(self):
        out = []
        for d in self.by.get(T['BIN_DATA'], []):
            r = Reader(d)
            attr = r.u('H')
            kind = attr & 0xF
            if kind == 0:                                   # link: absolute path, relative path
                path = r.wstr()
                out.append(dict(kind='link', path=path, rel=r.wstr() if r.left() >= 2 else '', ext=path.rsplit('.', 1)[-1] if '.' in path else ''))
            else:
                bid = r.u('H')
                ext = r.wstr() if r.left() >= 2 else ''
                out.append(dict(kind='embed' if kind == 1 else 'storage', id=bid, ext=ext, attr=attr))
        return out

    # -- the pieces
    def fontfaces(self):
        faces = self.by.get(T['FACE_NAME'], [])
        root = El('hh:fontfaces', {'itemCnt': 7})
        k = 0
        for n, lang in enumerate(LANGS):
            cnt = self.counts[1 + n]
            ff = El('hh:fontface', {'lang': lang, 'fontCnt': cnt})
            for i in range(cnt):
                ff.add(self.font(i, faces[k]))
                k += 1
            root.add(ff)
        return root

    def font(self, i, d):
        r = Reader(d)
        attr = r.u('B')
        name = r.wstr()
        f = El('hh:font', {'id': i, 'face': name, 'type': FONT_TYPE[min(attr & 3, 2)], 'isEmbedded': 0})
        if attr & 0x80:
            alt_type = r.u('B')
            alt = r.wstr()
            f.add(El('hh:substFont', {'face': alt, 'type': FONT_TYPE[min(alt_type, 2)], 'isEmbedded': 0,
                                      'binaryItemIDRef': ''}))
        if attr & 0x40:
            fam, serif, weight, prop, contrast, stroke, arm, letter, mid, xh = r.u('10B')
            f.add(El('hh:typeInfo', {'familyType': FAMILY[fam] if fam < len(FAMILY) else 'FCAT_UNKNOWN', 'weight': weight,
                                     'proportion': prop, 'contrast': contrast, 'strokeVariation': stroke, 'armStyle': arm,
                                     'letterform': letter, 'midline': mid, 'xHeight': xh}))
        if attr & 0x20:
            r.wstr()                                       # base font name: OWPML keeps no such field in its output
        return f

    def fill(self, r):
        """The fill part of a border fill -> hc:fillBrush or None (the same record part as in a drawing object)."""
        from .owpmlshape import fill_brush
        return fill_brush(r, 'DocInfo', self) if r.left() >= 4 else None

    def bin_ref(self, binid, place):
        """The manifest id of the BIN_DATA item `binid` (from 1) that a fill or a picture refers to."""
        from .owpmlpkg import bin_name
        if not 1 <= binid <= len(self.bins) or bin_name(binid, self.bins[binid - 1]['ext']) is None:
            raise Unsupported(f'a fill or picture refers to BIN_DATA {binid}, which is not an image', place)
        return bin_name(binid, self.bins[binid - 1]['ext'])[0]

    def border_fills(self):
        root = El('hh:borderFills', {'itemCnt': len(self.by.get(T['BORDER_FILL'], []))})
        for i, d in enumerate(self.by.get(T['BORDER_FILL'], []), 1):
            r = Reader(d)
            attr = r.u('H')
            bf = El('hh:borderFill', {'id': i, 'threeD': attr & 1, 'shadow': attr >> 1 & 1,
                                      'centerLine': om.CENTER_LINE[attr >> 13 & 3],
                                      'breakCellSeparateLine': attr >> 10 & 1})
            # bits 2-4 slash / 5-7 backslash shape, 8-9 slash Crooked (0-3), 11 / 12 isCounter; bit 10 leaves no trace in Hangul's HWPX
            for name, sh, cr, ic in (('slash', 2, attr >> 8 & 3, 11), ('backSlash', 5, 0, 12)):
                if (attr >> sh & 7) not in SLASH:
                    raise Unsupported(f'border fill {name} shape {attr >> sh & 7}', f'DocInfo BORDER_FILL {i}')
                bf.add(El('hh:' + name, {'type': SLASH[attr >> sh & 7], 'Crooked': cr, 'isCounter': attr >> ic & 1}))
            sides = {}
            for k in ('left', 'right', 'top', 'bottom', 'diagonal'):
                t, w, c = r.u('BBI')
                sides[k] = El('hh:%sBorder' % k if k != 'diagonal' else 'hh:diagonal',
                              {'type': LINE[t] if t < len(LINE) else 'SOLID', 'width': mm(w), 'color': color(c)})
            bf.add(sides['left'], sides['right'], sides['top'], sides['bottom'], sides['diagonal'])
            bf.add(self.fill(r))
            root.add(bf)
        return root

    def char_props(self):
        root = El('hh:charProperties', {'itemCnt': len(self.by.get(T['CHAR_SHAPE'], []))})
        for i, d in enumerate(self.by.get(T['CHAR_SHAPE'], [])):
            r = Reader(d)
            face = r.u('7H')
            ratio, spacing, rel, offset = r.u('7B'), r.u('7b'), r.u('7B'), r.u('7b')
            base, attr = r.u('iI')
            gx, gy = r.u('bb')
            text, under, shade, shadow = r.u('IIII')
            bfid = r.u('H') if r.left() >= 2 else 0
            strike = r.u('I') if r.left() >= 4 else 0
            c = El('hh:charPr', {'id': i, 'height': base, 'textColor': color(text), 'shadeColor': color(shade),
                                 'useFontSpace': attr >> 25 & 1, 'useKerning': attr >> 30 & 1,
                                 'symMark': SYMMARK[min(attr >> 21 & 15, 12)], 'borderFillIDRef': bfid})
            seven = lambda v: {a: v[k] for k, a in enumerate(LANG_ATTR)}
            c.add(El('hh:fontRef', seven(face)), El('hh:ratio', seven(ratio)), El('hh:spacing', seven(spacing)),
                  El('hh:relSz', seven(rel)), El('hh:offset', seven(offset)))
            if attr & 1:
                c.add(El('hh:italic'))
            if attr & 2:
                c.add(El('hh:bold'))
            # bits 2-3 of the attribute: 0 none, 1 below, 3 above; 2 = a line through the text: Hangul 2024 writes it as a strikeout
            # whose shape is bits 4-7 (and no underline, shape SOLID); else bits 18-20 (strikeout) with the shape of bits 26-29 (HW100)
            ut = attr >> 2 & 3
            st = attr >> 18 & 7
            c.add(El('hh:underline', {'type': 'NONE' if ut == 2 else UNDER_POS[ut],
                                      'shape': 'SOLID' if ut == 2 else UNDERLINE_SHAPE[attr >> 4 & 15],
                                      'color': '#000000' if ut == 2 else color(under)}))     # (that colour is black: 3 forms)
            c.add(El('hh:strikeout', {'shape': UNDERLINE_SHAPE[attr >> 4 & 15] if ut == 2
                                      else 'NONE' if not st else UNDERLINE_SHAPE[attr >> 26 & 15], 'color': color(strike)}))
            c.add(El('hh:outline', {'type': OUTLINE[min(attr >> 8 & 7, 6)]}))
            sh = attr >> 11 & 3
            c.add(El('hh:shadow', {'type': CHAR_SHADOW[min(sh, 2)], 'color': color(shadow),
                                   'offsetX': gx, 'offsetY': gy}))
            if attr >> 13 & 1:
                c.add(El('hh:emboss'))
            if attr >> 14 & 1:
                c.add(El('hh:engrave'))
            if attr >> 15 & 1:
                c.add(El('hh:supscript'))
            if attr >> 16 & 1:
                c.add(El('hh:subscript'))
            root.add(c)
        return root

    def tab_props(self):
        root = El('hh:tabProperties', {'itemCnt': len(self.by.get(T['TAB_DEF'], []))})
        for i, d in enumerate(self.by.get(T['TAB_DEF'], [])):
            attr, n = struct.unpack_from('<Ii', d, 0)
            t = El('hh:tabPr', {'id': i, 'autoTabLeft': attr & 1, 'autoTabRight': attr >> 1 & 1})
            for k in range(n):
                pos, typ, lead = struct.unpack_from('<iBB', d, 8 + 8 * k)           # signed (a tab stop of -260288 in 2 forms)
                item = lambda p, unit: El('hh:tabItem', {'pos': p, 'type': TAB_TYPE[min(typ, 3)],
                                                         'leader': LINE_TAB[lead] if lead < len(LINE_TAB) else 'SOLID',
                                                         'unit': unit})
                t.add(self.unitswitch(item(pos // 2, 'HWPUNIT'), item(pos, None)))
            root.add(t)
        return root

    @staticmethod
    def unitswitch(case, default):
        """hp:switch with the HwpUnitChar case (half the stored value) and the default (the stored value)."""
        return El('hp:switch', None,
                  El('hp:case', {'hp:required-namespace': 'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar'}, case),
                  El('hp:default', None, default))

    def para_head(self, r):
        attr = r.u('I')
        adj, off = r.u('hH')
        cs = r.u('I')
        return attr, adj, off, cs

    def numberings(self):
        if not self.by.get(T['NUMBERING']):
            return None                                    # Hangul 2024 writes no hh:numberings without a numbering (14 of 14 files)
        root = El('hh:numberings', {'itemCnt': len(self.by.get(T['NUMBERING'], []))})
        for i, d in enumerate(self.by.get(T['NUMBERING'], []), 1):
            r = Reader(d)
            heads = []
            for lv in range(7):
                attr, adj, off, cs = self.para_head(r)
                heads.append((attr, adj, off, cs, r.wstr()))
            start = r.u('H')
            starts = [r.u('I') for _ in range(7)] if r.left() >= 28 else [1] * 7
            if r.left() >= 3 * 12:                         # 5.0.2.5 and later: levels 8-10 follow, then their start numbers
                for lv in range(3):
                    attr, adj, off, cs = self.para_head(r)
                    heads.append((attr, adj, off, cs, r.wstr()))
                starts += [r.u('I') for _ in range(3)] if r.left() >= 12 else [1] * 3
            elif not self.legacy:                          # an older record ends at level 7: Hangul 2018+ pads levels 8-10
                for _ in range(3):                         # Hangul pads with zeros (old_version_linespacing); arc has real ones
                    heads.append((0, 0, 0, 0, ''))
                    starts.append(1)
            n = El('hh:numbering', {'id': i, 'start': start})
            for lv, (attr, adj, off, cs, text) in enumerate(heads, 1):
                n.add(El('hh:paraHead', {'start': starts[lv - 1], 'level': lv, 'align': om.ALIGN3[min(attr & 3, 2)],
                                         'useInstWidth': attr >> 2 & 1, 'autoIndent': attr >> 3 & 1, 'widthAdjust': adj,
                                         'textOffsetType': 'HWPUNIT' if attr >> 4 & 1 else 'PERCENT', 'textOffset': off,
                                         'numFormat': NUMFMT[min(attr >> 5 & 15, 14)], 'charPrIDRef': cs,
                                         'checkable': attr >> 5 & 1}, text=text or None))   # Hangul: "checkable" = the low bit of the format number
            root.add(n)
        return root

    def bullets(self):
        data = self.by.get(T['BULLET'], [])
        if not data:
            return None
        root = El('hh:bullets', {'itemCnt': len(data)})
        for i, d in enumerate(data, 1):
            r = Reader(d)
            attr, adj, off, cs = self.para_head(r)
            ch = r.u('H')
            img = r.u('i') if r.left() >= 4 else 0              # the oldest record ends after the bullet character
            pic = r.u('bbBH') if r.left() >= 5 else None        # contrast, brightness, effect, BinData id (HW72)
            chk = r.u('H') if r.left() >= 2 else 0              # the check character, from 5.1
            b = El('hh:bullet', {'id': i, 'char': chr(ch), 'useImage': 1 if img else 0})
            if chk:
                b.at['checkedChar'] = chr(chk)
            if img and pic is not None:                          # picture bullet: hc:img before the paragraph head, as Hangul 2024
                contrast, bright, effect, binid = pic
                if effect >= len(IMG_EFFECT):
                    raise Unsupported(f'picture bullet {i}: picture effect {effect}', 'DocInfo BULLET')
                b.add(El('hc:img', {'binaryItemIDRef': self.bin_ref(binid, 'DocInfo BULLET'), 'bright': bright,
                                    'contrast': contrast, 'effect': IMG_EFFECT[effect], 'alpha': 0}))
            b.add(El('hh:paraHead', {'level': 0, 'align': om.ALIGN3[min(attr & 3, 2)], 'useInstWidth': attr >> 2 & 1,
                                     'autoIndent': attr >> 3 & 1, 'widthAdjust': adj,
                                     'textOffsetType': 'HWPUNIT' if attr >> 4 & 1 else 'PERCENT', 'textOffset': off,
                                     'numFormat': 'DIGIT', 'charPrIDRef': cs, 'checkable': attr >> 9 & 1}))
            root.add(b)
        return root

    def para_props(self):
        root = El('hh:paraProperties', {'itemCnt': len(self.by.get(T['PARA_SHAPE'], []))})
        for i, d in enumerate(self.by.get(T['PARA_SHAPE'], [])):
            r = Reader(d)
            a1, left, right, indent, prev, nxt, ls_old = r.u('Iiiiiii')
            tab_id, head_id, bf_id = r.u('HHH')
            offs = r.u('4h')
            a2 = r.u('I') if r.left() >= 4 else 0
            a3 = r.u('I') if r.left() >= 4 else None
            ls_new = r.u('I') if r.left() >= 4 else None
            level_x = r.u('I') if r.left() >= 4 else 0              # 5.0.3.x: the outline level 1-10 of a heading
            if a3 is not None:
                lt, lv = a3 & 31, ls_new
            else:
                lt, lv = a1 & 3, ls_old
            ltype = LINE_SPACING[min(lt, 3)]
            htype = a1 >> 23 & 3
            p = El('hh:paraPr', {'id': i, 'tabPrIDRef': tab_id, 'condense': a1 >> 9 & 127, 'fontLineHeight': a1 >> 22 & 1,
                                 'snapToGrid': a1 >> 8 & 1, 'suppressLineNumbers': a2 >> 6 & 1, 'checked': 0,
                                 'textDir': text_dir(a2, f'DocInfo PARA_SHAPE {i}')})
            p.add(El('hh:align', {'horizontal': ALIGN[min(a1 >> 2 & 7, 5)], 'vertical': VALIGN[a1 >> 20 & 3]}))
            heading = lambda t, ref, lv: El('hh:heading', {'type': t, 'idRef': ref, 'level': lv})
            if htype == 1 and level_x > 6:                   # outline level 7-10: Hangul 2016+ writes a switch (levels 1-6 plain)
                p.add(El('hp:switch', None,
                         El('hp:case', {'hp:required-namespace': 'http://www.hancom.co.kr/hwpml/2016/paragraph'},
                            heading('OUTLINE', head_id, level_x)),
                         El('hp:default', None, heading('NONE', 0, 0))))
            else:
                p.add(heading(HEADING[htype], head_id if htype else 0, a1 >> 25 & 7))
            p.add(El('hh:breakSetting', {'breakLatinWord': om.LATIN_BREAK[min(a1 >> 5 & 3, 2)],
                                         'breakNonLatinWord': 'KEEP_WORD' if a1 >> 7 & 1 else 'BREAK_WORD',
                                         'widowOrphan': a1 >> 16 & 1, 'keepWithNext': a1 >> 17 & 1, 'keepLines': a1 >> 18 & 1,
                                         'pageBreakBefore': a1 >> 19 & 1, 'lineWrap': 'BREAK'}))
            p.add(El('hh:autoSpacing', {'eAsianEng': a2 >> 4 & 1, 'eAsianNum': a2 >> 5 & 1}))

            def body(case):
                """case: the HwpUnitChar form (half the stored value; an odd value = a count of characters, value >> 1);
                default: the stored value as it is."""
                m = El('hh:margin', None)
                for tag, v in (('hc:intent', indent), ('hc:left', left), ('hc:right', right), ('hc:prev', prev),
                               ('hc:next', nxt)):
                    if case:
                        m.add(El(tag, {'value': v >> 1 if v & 1 else v // 2, 'unit': 'CHAR' if v & 1 else 'HWPUNIT'}))
                    else:
                        m.add(El(tag, {'value': v, 'unit': 'HWPUNIT'}))
                return [m, El('hh:lineSpacing', {'type': ltype, 'value': lv if ltype == 'PERCENT' else (lv // 2 if case else lv),
                                                 'unit': 'HWPUNIT'})]
            case, dflt = body(True), body(False)
            sw = El('hp:switch', None,
                    El('hp:case', {'hp:required-namespace': 'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar'}, *case),
                    El('hp:default', None, *dflt))
            p.add(sw)
            p.add(El('hh:border', {'borderFillIDRef': bf_id, 'offsetLeft': offs[0], 'offsetRight': offs[1],
                                   'offsetTop': offs[2], 'offsetBottom': offs[3], 'connect': a1 >> 28 & 1,
                                   'ignoreMargin': a1 >> 29 & 1}))
            root.add(p)
        return root

    def styles(self):
        root = El('hh:styles', {'itemCnt': len(self.by.get(T['STYLE'], []))})
        for i, d in enumerate(self.by.get(T['STYLE'], [])):
            r = Reader(d)
            name, eng = r.wstr(), r.wstr()
            kind, nxt = r.u('BB')
            lang = r.u('h')
            para, char = r.u('HH')
            lock = kind >> 2 & 1                              # attribute byte: bits 0-1 the type, bit 2 "lock" (HW81, HW100: 7600 styles)
            if kind & 3 > 1:
                raise Unsupported(f'style {i} type {kind & 3} (paragraph 0, character 1)', 'DocInfo STYLE')
            root.add(El('hh:style', {'id': i, 'type': 'CHAR' if kind & 3 else 'PARA', 'name': name, 'engName': eng,
                                     'paraPrIDRef': para, 'charPrIDRef': char, 'nextStyleIDRef': nxt, 'langID': lang,
                                     'lockForm': lock}))
        return root

    def element(self):
        props = self.by.get(T['DOCUMENT_PROPERTIES'], [b'\0' * 26])[0]
        nsec, page, foot, end, pic, tbl, eq = struct.unpack_from('<7H', props, 0)
        head = El('hh:head', {'version': '1.5' if self.pk.version >= 0x05000300 else '1.4', 'secCnt': nsec})
        head.add(El('hh:beginNum', {'page': page, 'footnote': foot, 'endnote': end, 'pic': pic, 'tbl': tbl, 'equation': eq}))
        ref = El('hh:refList', None, self.fontfaces(), self.border_fills(), self.char_props(), self.tab_props(),
                 self.numberings(), self.bullets(), self.para_props(), self.styles(), self.memo_props(), *self.track_changes())
        head.add(ref)
        head.add(self.compat(), self.doc_option(), self.track_config())
        return head

    def memo_props(self):
        """MEMO_SHAPE (22 bytes: width, line type, line width, line / fill / active colour, memo type) -> hh:memoPr; the line type
        0-7 and memo type 0-3 were measured one value at a time in Hangul 2024 (higher values write no attribute: they stop)."""
        recs = self.by.get(T['MEMO_SHAPE'], [])
        if not recs:
            return None
        lines, kinds = om.MEMO_LINE[:8], om.MEMO_TYPE                                  # (sic) Hangul spells NOMAL
        items = []
        for i, d in enumerate(recs, 1):
            r = Reader(d)
            width, ltype, lwidth, lc, fc, ac, kind = r.u('IBB3II')
            if ltype >= len(lines) or kind >= len(kinds) or r.left():
                raise Unsupported(f'memo shape line type {ltype} / memo type {kind}', 'DocInfo')
            items.append(El('hh:memoPr', {'id': i, 'width': width, 'lineWidth': lwidth, 'lineType': lines[ltype],
                                          'lineColor': color(lc), 'fillColor': color(fc), 'activeColor': color(ac),
                                          'memoType': kinds[kind]}))
        return El('hh:memoProperties', {'itemCnt': len(items)}, *items)

    def track_changes(self):
        """TRACK_CHANGE (26 bytes: type 0x10 Insert / 0x11 Delete, year month day hour minute as words, author, 6 bytes, hide; 30 bytes
        for 0x12 CharShape / 0x13 ParaShape with the shape id at offset 22) and TRACK_CHANGE_AUTHOR (name, mark, 4 bytes that Hangul
        leaves out) -> hh:trackChanges / hh:trackChangeAuthors (Hangul 2024, 2 files; the type word was measured 0-0x23: only these
        four are named). The date is written -9 hours (KST, as the memo date)."""
        import datetime
        out = []
        recs = self.by.get(T['TRACK_CHANGE'], [])
        if recs:
            items = []
            for i, d in enumerate(recs, 1):
                r = Reader(d)
                kind, y, mo, day, h, mi, author = r.u('I6H')
                names = {0x10: 'Insert', 0x11: 'Delete', 0x12: 'CharShape', 0x13: 'ParaShape'}
                if kind not in names or len(d) != (26 if kind < 0x12 else 30):
                    raise Unsupported(f'track change type {kind:#x} / length {len(d)}', 'DocInfo')
                t = datetime.datetime(y, mo, day, h, mi) - datetime.timedelta(hours=9)
                at = {'type': names[kind], 'date': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'authorID': author,
                      'hide': 1 if kind == 0x11 else 0, 'id': i}
                if kind >= 0x12:             # the shape id is at offset 22 (Hangul 2024 renumbers a paragraph shape: 73 -> 72 in 1 file)
                    at['charshapeID' if kind == 0x12 else 'parashapeID'] = struct.unpack_from('<I', d, 22)[0]
                items.append(El('hh:trackChange', at))
            out.append(El('hh:trackChanges', {'itemCnt': len(items)}, *items))
        auth = self.by.get(T['TRACK_CHANGE_AUTHOR'], [])
        if auth:
            items = []
            for i, d in enumerate(auth, 1):
                r = Reader(d)
                name = r.raw(2 * r.u('I')).decode('utf-16-le', 'replace')            # the length is a 4-byte number here
                mark = r.u('I')
                items.append(El('hh:trackChangeAuthor', {'name': name, 'mark': mark, 'id': i}))
            out.append(El('hh:trackChangeAuthors', {'itemCnt': len(items)}, *items))
        return out

    def compat(self):
        target = self.by.get(T['COMPATIBLE_DOCUMENT'], [b'\0\0\0\0'])[0]
        t = struct.unpack_from('<I', target, 0)[0]
        words = struct.unpack_from('<%dI' % (len(self.by.get(T['LAYOUT_COMPATIBILITY'], [b''])[0]) // 4),
                                   self.by.get(T['LAYOUT_COMPATIBILITY'], [b''])[0])
        if t >= len(COMPAT_TARGET):
            raise Unsupported(f'COMPATIBLE_DOCUMENT target program {t}', 'DocInfo')
        lc = El('hh:layoutCompatibility')
        for w, word in enumerate(words):                       # the children in bit order (HW53)
            for b in range(32):
                if word >> b & 1:
                    names = COMPAT_FLAGS[w] if w < len(COMPAT_FLAGS) else []
                    if b >= len(names):
                        raise Unsupported(f'LAYOUT_COMPATIBILITY flag word {w} bit {b} (Hangul 2024 knows no name for it)',
                                          'DocInfo')
                    if names[b]:
                        lc.add(El('hh:' + names[b]))
        return El('hh:compatibleDocument', {'targetProgram': COMPAT_TARGET[t]}, lc)

    def doc_option(self):
        # _LinkDoc = path (256 WCHAR), two DWORDs, then pageInherit (the last DWORD): 0 / 1 in all 280 Hangul 2024 reference files;
        # no stream (older files): Hangul writes 1 (HW100)
        link = self.pk.streams.get('DocOptions/_LinkDoc')
        page = struct.unpack_from('<I', link.data, 520)[0] & 1 if link is not None and len(link.data) >= 524 else 1
        return El('hh:docOption', None, El('hh:linkinfo', {'path': '', 'pageInherit': page, 'footnoteInherit': 0}))

    def track_config(self):
        # no record (5.0.0 - 5.0.3 files): Hangul 2024 writes 56 (56 files; HW58). The tracked-change display of a document depends on
        # it: with 0 the 5.0.1.7 form of 016 paginates to 94 pages instead of 92.
        d = self.by.get(T['TRACK_CHANGE_FLAGS'], [b'\x38\0\0\0'])[0]
        return El('hh:trackchageConfig', {'flags': struct.unpack_from('<I', d, 0)[0]})


def text_dir(attr2, place):
    """PARA_SHAPE attribute 2, bits 2-3 -> paraPr@textDir (measured one value at a time in Hangul 2024, HW100: 0 AUTO, 1 RTL, 2 LTR;
    3 makes Hangul write no attribute)."""
    v = attr2 >> 2 & 3
    if v == 3:
        raise Unsupported('paragraph text direction 3 (Hangul 2024 writes no textDir for it)', place)
    return om.TEXT_DIR[v]


LINE_TAB = LINE                      # one numbering for every line (HW82)


def convert(src, dst):
    """.hwp -> .hwpx. Raises fmt.Hwp5Error for a file that is not (or not plainly) an .hwp, Unsupported for a record
    without a mapping."""
    from . import owpmlsec, owpmlpkg
    from .owpmlmap import replaced
    pk = fmt.Package(src)
    sec = None
    replaced[0] = 0
    try:
        head = Head(pk)
        parts = {'Contents/header.xml': document(head.element())}
        sec = owpmlsec.Sections(pk, head)
        for i, xml in enumerate(sec.xml()):
            parts[f'Contents/section{i}.xml'] = xml
        notes = []
        owpmlpkg.write(pk, head, sec, parts, dst, notes)
    except (struct.error, IndexError) as e:                 # a record shorter than its layout: stop, say where
        raise Unsupported(short_record_text(e), f'(at {sec.place if sec else "DocInfo"})') from None
    if replaced[0]:
        notes.append(f'NOTE {replaced[0]} character(s) that XML cannot hold (a lone surrogate, a control code) became U+FFFD')
    return notes


def main(args):
    """`hd hwp tohwpx <in.hwp> <out.hwpx>` (cli.py passes the arguments after the sub-command)."""
    if args and args[0] == 'tohwpx':
        args = args[1:]
    if len(args) != 2:
        print('usage: hd hwp tohwpx <in.hwp> <out.hwpx>')
        return 2
    try:
        notes = convert(args[0], args[1])
    except Unsupported as e:
        print(e)
        return 5
    for n in notes:
        print(n)
    print(f'wrote {args[1]}')
    return 0
