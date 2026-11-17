"""OWPML section*.xml -> BodyText records of an HWP 5.0 file (the writing half of rules HW04-HW06, HW20-HW23).

  BinTable(source)                    the embedded files (BinData/*) with their HWP ids and stream names
  section_records(source, name, bins) -> [[tag, level, bytes], ...]

A paragraph is written as Hangul writes it: PARA_HEADER (level L), PARA_TEXT, PARA_CHAR_SHAPE, PARA_LINE_SEG at L+1, then
the CTRL_HEADER of every control of the text in order (L+1) with their own records below. The k-th extended control
character of PARA_TEXT is the k-th CTRL_HEADER (HW05). The layouts are the ones tospec.py reads (HW20-HW23).
"""
import os
import re
import struct
import xml.etree.ElementTree as ET

from . import fo_dedupe
from . import owpmlmap as om
from .fmt import T
from .fo_head import HALIGN, LINE, NUM_FORMAT, WIDTH, Unsupported, color, first, kids, ln, num, pick, snum, warn, wstr

(NUM_TYPE, APPLY_PAGE, OBJ_WRAP, OBJ_FLOW, V_REL, H_REL, POS_VALIGN, POS_HALIGN, W_REL, H_REL_SZ, NOTE_NUMBERING, GUTTER, BORDER_AREA, COL_TYPE, COL_LAYOUT,
 LINE_WRAP, SUB_VALIGN, CAPTION_SIDE, TBL_BREAK, COMPOSE) = map(om.inverse, (
    om.NUM_TYPE, om.APPLY_PAGE, om.OBJ_WRAP, om.OBJ_FLOW, om.V_REL, om.H_REL, om.POS_VALIGN, om.POS_HALIGN, om.W_REL, om.H_REL_SZ, om.NOTE_NUMBERING,
    om.GUTTER, om.BORDER_AREA, om.COL_TYPE, om.COL_LAYOUT, om.LINE_WRAP, om.SUB_VALIGN, om.CAPTION_SIDE, om.TBL_BREAK, om.COMPOSE))
NUMBERING = {**om.inverse(om.NUMBERING), 'FIGURE': 1}                      # a figure is numbered like a picture


def cid(name):
    """Control id as the 4 bytes Hangul stores (the characters reversed)."""
    return name.encode('latin-1')[::-1]


def rec(tag, level, data):
    return [T[tag] if isinstance(tag, str) else tag, level, data]


def crlf(text):
    """XML gives line breaks as LF; Hangul stores CR LF in object descriptions."""
    return text.replace(chr(13) + chr(10), chr(10)).replace(chr(10), chr(13) + chr(10))


def b(v):
    """0/1 attribute -> int ('true' too)."""
    return 1 if v in ('1', 'true', 'TRUE') else 0


class BinTable:
    """BinData of the package: the items of content.hpf in order get the ids 1, 2, ... (`BIN0001.png`)."""

    def __init__(self, source):
        self.source = source
        self.by_ref = {}
        self.items = []                           # (extension, type)
        self.data = []
        for iid, (href, media) in source.items.items():
            if iid in source.linked:                           # a linked picture (isEmbeded="0"): no stream, only the paths (HW91)
                self.by_ref[iid] = len(self.items) + 1
                self.items.append((self.link_record(href or ''), 'LINK'))
                self.data.append(None)
            elif href.startswith('BinData/') and source.has(href):
                ext = href.rsplit('.', 1)[-1].lower() if '.' in href else ''
                if not re.fullmatch(r'[a-z0-9]{0,16}', ext):         # the extension names a stream (BIN0001.<ext>): short, plain letters
                    raise Unsupported(f'BinData file name {href[:60]!r}: the extension is not 16 letters or digits at most')
                ole = ext == 'ole'                                # an OLE file is a storage item, written as BIN0001.OLE
                self.by_ref[iid] = len(self.items) + 1
                # Hangul 2024 writes the extension in capitals when it saves a HWPX as .hwp (tif, png, bmp: 8 files of 153 forms; HW81)
                self.items.append((ext.upper() if ole or source.ver >= (5, 1, 1, 0) else ext, 'STORAGE' if ole else 'EMBEDDING'))
                self.data.append(source.read(href))

    def link_record(self, path):
        """The BIN_DATA record of a linked picture (without its record header): attribute 0, the absolute path, the path
        from the folder of the .hwp. Hangul works the second path out again at every save. Same drive: up to the common
        folder; another drive: one `..` for each folder of the .hwp, then the path without its first folder (as Hangul 2024
        wrote it in the one file measured, HW91)."""
        from .safecopy import remote_note, remote_path
        if remote_path(path):
            warn(remote_note(path))                                            # the author's network path goes into the file
        comps = lambda p: [x for x in p.replace('/', chr(92)).split(chr(92)) if x]
        out = os.path.dirname(os.path.abspath(self.source.dst))
        out_drive, out_dirs = os.path.splitdrive(out)
        drive, tail = os.path.splitdrive(path)
        out_dirs, tgt = comps(out_dirs), comps(tail)
        if drive.lower() == out_drive.lower() and drive:
            k = 0
            while k < min(len(out_dirs), len(tgt) - 1) and out_dirs[k].lower() == tgt[k].lower():
                k += 1
            rel = chr(92).join(['..'] * (len(out_dirs) - k) + tgt[k:])
        else:
            rel = chr(92).join(['..'] * len(out_dirs) + (tgt[1:] if drive else tgt))
        return struct.pack('<H', 0) + wstr(path) + wstr(rel)

    def streams(self):
        for k, ((ext, typ), d) in enumerate(zip(self.items, self.data), 1):
            if typ != 'LINK':
                yield 'BIN%04X.%s' % (k, ext), d


# ---- paragraphs ----------------------------------------------------------------------------------------------------------
class Para:
    """One paragraph under construction."""

    def __init__(self):
        self.units = bytearray()
        self.pairs = []                  # (position, char shape id)
        self.ctrls = []                  # one record list per extended control, in order
        self.tail = []                   # records after all the controls (a memo's list: 0x5d, LIST_HEADER and its paragraphs, all at the control's level)
        self.codes = set()
        self.tracked = False             # a tracked change in the paragraph (the document gets ViewText, HW88)
        self.has_col = False             # a column definition in the paragraph (bit 1 of the break byte, HW81)
        self.ranges = []                 # (start, end, tag) of the range tags (highlights); the open ones wait in self.open
        self.open = []

    def pos(self):
        return len(self.units) // 2

    def ext(self, code, name):
        """An 8-unit control (extended or inline): code, 4-byte id, 8 zero bytes, code."""
        self.units += struct.pack('<H', code) + cid(name) + bytes(8) + struct.pack('<H', code)
        self.codes.add(code)


class Writer:
    def __init__(self, source, bins):
        self.src, self.bins, self.ver = source, bins, source.ver
        self.where = 'a section'
        self.fields = []                 # the fields begun and not yet ended

    # -- a list of paragraphs (the body, a cell, a text box, a header ...) -----------------------------------------------
    def paras(self, plist, level):
        out = []
        for k, p in enumerate(plist):
            out += self.paragraph(p, level, k == len(plist) - 1)
        return out

    def paragraph(self, p, level, last):
        pa = Para()
        has_sec = False
        for run in kids(p, 'run'):
            sid = num(run.get('charPrIDRef'))
            if not pa.pairs or pa.pairs[-1][1] != sid:
                pa.pairs.append((pa.pos(), sid))
            for el in run:
                tag = ln(el)
                if tag == 't':
                    self.text(pa, el)
                elif tag == 'secPr':
                    has_sec = True
                    pa.ext(2, 'secd')
                    pa.ctrls.append(self.sec_def(el, level + 1))
                elif tag == 'ctrl':
                    for c in el:
                        self.ctrl(pa, c, level + 1, p)
                elif tag in ('dutmal', 'compose'):                   # these two sit directly in the run
                    self.ctrl(pa, el, level + 1, p)
                elif tag == 'tbl':
                    pa.ext(11, 'tbl ')
                    pa.ctrls.append(self.table(el, level + 1))
                elif tag in ('btn', 'checkBtn', 'radioBtn', 'comboBox', 'edit'):
                    from . import fo_form
                    pa.ext(11, 'form')
                    pa.ctrls.append(fo_form.form(self, el, level + 1))
                elif tag == 'equation':
                    pa.ext(11, 'eqed')
                    pa.ctrls.append(self.equation(el, level + 1))
                elif tag in ('pic', 'rect', 'ellipse', 'line', 'arc', 'polygon', 'curve', 'container', 'ole', 'textart',
                             'connectLine'):
                    from . import fo_shape
                    pa.ext(11, 'gso ')
                    pa.ctrls.append(fo_shape.gso(self, el, level + 1))
                else:
                    raise Unsupported(f'element hp:{tag} in paragraph id={p.get("id")}')
        if not pa.pairs:
            pa.pairs = [(0, 0)]
        pa.units += struct.pack('<H', 13)
        n = pa.pos()
        seg = first(p, 'linesegarray')
        segs, nseg = b'', 0
        if seg is not None:
            for s in kids(seg, 'lineseg'):
                segs += struct.pack('<IiiiiiiiI', num(s.get('textpos')), snum(s.get('vertpos')), snum(s.get('vertsize')),
                                    snum(s.get('textheight')), snum(s.get('baseline')), snum(s.get('spacing')),
                                    snum(s.get('horzpos')), snum(s.get('horzsize')), num(s.get('flags')))
                nseg += 1
        brk = (4 if num(p.get('pageBreak')) else 0) | (8 if num(p.get('columnBreak')) else 0) | (3 if has_sec else 2 if pa.has_col and self.ver >= (5, 0, 3, 0) else 0)
        mask = 0
        for c in pa.codes:
            mask |= 1 << c
        head = struct.pack('<IIHBBHHHIH', (n & 0x7FFFFFFF) | (0x80000000 if last else 0), mask, num(p.get('paraPrIDRef')),
                           num(p.get('styleIDRef')), brk, len(pa.pairs), len(pa.ranges), nseg, num(p.get('id')) & 0xFFFFFFFF,
                           num(p.get('merged')))
        out = [rec('PARA_HEADER', level, head)]
        if n > 1:
            out.append(rec('PARA_TEXT', level + 1, bytes(pa.units)))
        out.append(rec('PARA_CHAR_SHAPE', level + 1, b''.join(struct.pack('<II', *x) for x in pa.pairs)))
        if nseg:
            out.append(rec('PARA_LINE_SEG', level + 1, segs))
        if pa.open:
            raise Unsupported(f'a begin without its end (highlight or tracked change) in paragraph id={p.get("id")}')
        if pa.tracked:
            self.src.tracked = True
        if pa.ranges:
            out.append(rec('PARA_RANGE_TAG', level + 1, b''.join(struct.pack('<III', *x) for x in sorted(pa.ranges))))
        for c in pa.ctrls:
            out += c
        out += pa.tail
        return out

    def text(self, pa, t):
        """<hp:t>: its text and the inline children (tab, lineBreak, nbSpace, fwSpace) in order."""
        if t.text:
            pa.units += t.text.encode('utf-16-le', 'surrogatepass')
        for c in t:
            tag = ln(c)
            if tag == 'tab':
                pa.units += (struct.pack('<H', 9) + struct.pack('<IBB', num(c.get('width')), num(c.get('leader')),
                                                                 num(c.get('type'))) + struct.pack('<3H', 32, 32, 32)
                             + struct.pack('<H', 9))
                pa.codes.add(9)
            elif tag == 'lineBreak':
                pa.units += struct.pack('<H', 10)
                pa.codes.add(10)
            elif tag == 'nbSpace':
                pa.units += struct.pack('<H', 30)
                pa.codes.add(30)
            elif tag == 'fwSpace':
                pa.units += struct.pack('<H', 31)
                pa.codes.add(31)
            elif tag == 'hypen':                               # a hyphen (24), as Hangul spells the element (HW88)
                pa.units += struct.pack('<H', 24)
                pa.codes.add(24)
            elif tag == 'titleMark':                           # a title mark for the table of contents: inline control 8, 'titM' / 'ngiM' (HW88)
                pa.units += struct.pack('<H', 8) + (b'titM' if num(c.get('ignore')) else b'ngiM') + bytes(8) + struct.pack('<H', 8)
                pa.codes.add(8)
            elif tag in ('insertBegin', 'deleteBegin'):         # a tracked change: a range tag of type 16 / 17, the number in the low 24 bits (HW88)
                pa.open.append((pa.pos(), (16 if tag == 'insertBegin' else 17) << 24 | num(c.get('TcId')) & 0xFFFFFF))
                pa.tracked = True
            elif tag in ('insertEnd', 'deleteEnd'):
                if not pa.open:
                    raise Unsupported(f'hp:{tag} without its begin')
                start, tg = pa.open.pop()
                # paraend="1": the range takes in the paragraph end mark too. An empty paragraph then has the range 0..1; with 0..0
                # Hangul shows no mark (5 of 80 marks of form 156757920, HW93)
                pa.ranges.append((start, pa.pos() + (1 if c.get('paraend') == '1' else 0), tg))
            elif tag == 'markpenBegin':                        # a highlight: one range tag, type 2, the colour in the low 24 bits (HW76)
                pa.open.append((pa.pos(), color(c.get('color'), 0) & 0xFFFFFF))
            elif tag == 'markpenEnd':
                if not pa.open:
                    raise Unsupported('hp:markpenEnd without its hp:markpenBegin')
                start, col = pa.open.pop()
                pa.ranges.append((start, pa.pos(), 2 << 24 | col))
            else:
                raise Unsupported(f'text element hp:{tag}')
            if c.tail:
                pa.units += c.tail.encode('utf-16-le', 'surrogatepass')

    def ctrl(self, pa, c, level, p):
        tag = ln(c)
        if tag == 'colPr':
            pa.ext(2, 'cold')
            pa.has_col = True
            pa.ctrls.append(self.col_def(c, level))
        elif tag == 'pageNum':                                   # page number position (21)
            pos = {'NONE': 0, 'TOP_LEFT': 1, 'TOP_CENTER': 2, 'TOP_RIGHT': 3, 'BOTTOM_LEFT': 4, 'BOTTOM_CENTER': 5,
                   'BOTTOM_RIGHT': 6, 'OUTSIDE_TOP': 7, 'OUTSIDE_BOTTOM': 8, 'INSIDE_TOP': 9, 'INSIDE_BOTTOM': 10}
            ch = lambda v: ord(v) if v else 0
            pa.ext(21, 'pgnp')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('pgnp') + struct.pack(
                '<IHHHH', pick(NUM_FORMAT, c.get('formatType', 'DIGIT'), 'page number format')
                | pick(pos, c.get('pos', 'BOTTOM_CENTER'), 'page number position') << 8,
                ch(c.get('userChar')), ch(c.get('prefixChar')), ch(c.get('suffixChar')), ch(c.get('sideChar'))))])
        elif tag == 'newNum':                                    # new number (21)
            kind = NUM_TYPE
            pa.ext(21, 'nwno')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('nwno') + struct.pack(
                '<IH', pick(kind, c.get('numType', 'PAGE'), 'number type'), num(c.get('num'))))])
        elif tag == 'pageHiding':                                # hide header, footer ... on this page (21)
            bits = ('hideHeader', 'hideFooter', 'hideMasterPage', 'hideBorder', 'hideFill', 'hidePageNum')
            pa.ext(21, 'pghd')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('pghd') + struct.pack(
                '<I', sum(b(c.get(k)) << i for i, k in enumerate(bits))))])
        elif tag == 'indexmark':                                 # index mark (22): the two keys as wide strings (HW88)
            pa.ext(22, 'idxm')
            fk, sk = first(c, 'firstKey'), first(c, 'secondKey')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('idxm') + wstr((fk.text or '') if fk is not None else '')
                                 + wstr((sk.text or '') if sk is not None else '') + wstr(''))])
        elif tag == 'bookmark':                                  # bookmark (22) with its name in a parameter set
            pa.ext(22, 'bokm')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('bokm')),
                             rec('CTRL_DATA', level + 1, struct.pack('<HHHHH', 0x021B, 1, 0, 0x4000, 1)
                                 + wstr(c.get('name', '')))])
        elif tag in ('header', 'footer'):                         # header / footer (16): applies to both, even or odd pages
            name = 'head' if tag == 'header' else 'foot'
            sl = first(c, 'subList')
            plist = kids(sl, 'p')
            pa.ext(16, name)
            apply = APPLY_PAGE.get(c.get('applyPageType', 'BOTH'), 0)
            pa.ctrls.append([rec('CTRL_HEADER', level, cid(name) + struct.pack('<II', apply, num(c.get('id'))))]
                            + [rec('LIST_HEADER', level + 1, struct.pack('<III', len(plist), self.list_attr(sl),
                                                                         num(sl.get('textWidth')))
                                   + struct.pack('<I', num(sl.get('textHeight'))) + bytes(18))]
                            + self.paras(plist, level + 1))
        elif tag in ('footNote', 'endNote'):                      # note (17): number, decoration characters, instance id
            name = 'fn  ' if tag == 'footNote' else 'en  '
            sl = first(c, 'subList')
            plist = kids(sl, 'p')
            pa.ext(17, name)
            ch = lambda v: (int(v) if str(v).isdigit() else ord(v)) if v else 0
            pa.ctrls.append([rec('CTRL_HEADER', level, cid(name) + struct.pack(
                '<IHHHHI', num(c.get('number')), ch(c.get('prefixChar')), ch(c.get('suffixChar')), ch(c.get('userChar')), 0,
                num(c.get('instId')) & 0xFFFFFFFF))]
                + [rec('LIST_HEADER', level + 1, struct.pack('<II', len(plist), self.list_attr(sl)) + bytes(8))]
                + self.paras(plist, level + 1))
        elif tag == 'hiddenComment':                              # hidden comment (15): a list of paragraphs
            sl = first(c, 'subList')
            plist = kids(sl, 'p')
            pa.ext(15, 'tcmt')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('tcmt'))]
                            + [rec('LIST_HEADER', level + 1, struct.pack('<II', len(plist), self.list_attr(sl)) + bytes(8))]
                            + self.paras(plist, level + 1))
        elif tag == 'fieldBegin':                                 # a field: begin (3), end (4) comes with fieldEnd
            ids = {'CLICK_HERE': '%clk', 'HYPERLINK': '%hlk', 'BOOKMARK': '%bmk', 'MEMO': '%%me', 'DATE': '%dte',
                   'DOC_DATE': '%ddt', 'PATH': '%pat', 'FORMULA': '%fmu', 'SUMMERY': '%smr', 'USER_INFO': '%usr',
                   'MAILMERGE': '%mmg', 'CROSSREF': '%crf', 'PROOFREADING_MARKS_SIMPLECHANGE': '%unk',
                   'PROOFREADING_MARKS_SIGN': '%unk'}       # the proofreading marks are the unknown field with a command (HW88)
            name = pick(ids, c.get('type', 'CLICK_HERE'), 'field type')
            params = {x.get('name'): (x.text or '') for x in c.iter() if ln(x) in ('integerParam', 'stringParam')}
            prop = num(params.get('Prop'))
            command = params.get('Command', '')
            self.fields.append([name, prop, len(self.fields), b(c.get('editable'))])
            pa.ext(3, name)
            attr = b(c.get('editable')) | b(c.get('dirty')) << 15
            hid = '%unk' if name == '%%me' else name                  # a memo field: the header says unknown (measured)
            head = rec('CTRL_HEADER', level, cid(hid) + struct.pack('<IB', attr, prop & 0xFF) + wstr(crlf(command))
                       + struct.pack('<II', num(c.get('id')) & 0xFFFFFFFF, num(params.get('Number'))))
            if name == '%%me':                       # a memo: no name record; its number, then its list at the control's level
                sl = first(c, 'subList')
                if sl is None:
                    raise Unsupported(f'memo field without its list in paragraph id={p.get("id")}')
                plist = kids(sl, 'p')
                pa.ctrls.append([head])
                pa.tail += ([rec(0x5D, level, struct.pack('<I', num(params.get('Number'))))]
                            + [rec('LIST_HEADER', level, struct.pack('<II', len(plist), self.list_attr(sl)) + bytes(8))]
                            + self.paras(plist, level))
            else:
                pa.ctrls.append([head] + ([rec('CTRL_DATA', level + 1, struct.pack('<HHHHH', 0x021B, 1, 0, 0x4000, 1)
                                                                   + wstr(c.get('name', '')))] if c.get('name') or c.get('type', 'CLICK_HERE') == 'CLICK_HERE' else []))      # a hyperlink without a name: no record (HW87)
        elif tag == 'fieldEnd':
            name, prop, depth, editable = self.fields.pop()
            # the end marker: the id with the property in its last byte, then the editable bit (+2 inside another field)
            data = struct.pack('<4sII', cid(name)[:3] + bytes([prop & 0xFF]), editable | (2 if depth else 0),
                               1 if name == '%%me' else 0)
            pa.units += struct.pack('<H', 4) + data + struct.pack('<H', 4)
            pa.codes.add(4)
        elif tag == 'dutmal':                                     # ruby text (덧말, 23): main text, sub text, position
            mt, st = first(c, 'mainText'), first(c, 'subText')
            pa.ext(23, 'tdut')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('tdut') + wstr((mt.text or '') if mt is not None else '')
                                 + wstr((st.text or '') if st is not None else '')
                                 + struct.pack('<5I', {'TOP': 0, 'BOTTOM': 1, 'SIDE': 2}.get(c.get('posType', 'TOP'), 0),
                                               num(c.get('szRatio')), num(c.get('option')), num(c.get('styleIDRef')),
                                               HALIGN.get(c.get('align', 'CENTER'), 3)))])
        elif tag == 'compose':                                    # overlapping characters (글자 겹침, 23)
            # circle type -> (number, the character Hangul puts before the text: measured on the compose pair)
            circle = {'CHAR': (0, '　'), 'SHAPE_CIRCLE': (1, '◯'), 'SHAPE_REVERSAL_CIRCLE': (2, '●'),
                      'SHAPE_RECTANGLE': (3, '□'), 'SHAPE_REVERSAL_RECTANGLE': (4, '■'),
                      'SHAPE_TRIANGLE': (5, '△'), 'SHAPE_REVERSAL_TIRANGLE': (6, '▲'),      # (sic) in OWPML
                      'SHAPE_LIGHT': (7, '☼'), 'SHAPE_RHOMBUS': (8, '◇'), 'SHAPE_REVERSAL_RHOMBUS': (9, '◆'),
                      'SHAPE_ROUNDED_RECTANGLE': (10, '▢'), 'SHAPE_EMPTY_CIRCULATE_TRIANGLE': (11, '♲'),
                      'SHAPE_THIN_CIRCULATE_TRIANGLE': (12, '♺'), 'SHAPE_THICK_CIRCULATE_TRIANGLE': (13, '♻')}
            kind, lead = pick(circle, c.get('circleType', 'CHAR'), 'compose circle type')
            if kind == 0 and c.get('composeType') == 'OVERLAP':
                lead = ''                                      # plain overlapped characters have no leading space
            prs = kids(c, 'charPr')
            pa.ext(23, 'tcps')
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('tcps') + wstr(lead + c.get('composeText', ''))
                                 + struct.pack('<BbBB', kind, num(c.get('charSz')),
                                               COMPOSE.get(c.get('composeType'), 0), len(prs))
                                 + b''.join(struct.pack('<I', num(x.get('prIDRef')) & 0xFFFFFFFF) for x in prs))])
        elif tag == 'autoNum':                                    # an automatic number inside a note or caption (18)
            kind = NUM_TYPE
            nf = first(c, 'autoNumFormat')
            ch = lambda v: (int(v) if str(v).isdigit() else ord(v)) if v else 0
            pa.ext(18, 'atno')
            attr = pick(kind, c.get('numType', 'PAGE'), 'auto number type')
            if nf is not None:
                attr |= pick(NUM_FORMAT, nf.get('type', 'DIGIT'), 'number format') << 4 | b(nf.get('supscript')) << 12
            pa.ctrls.append([rec('CTRL_HEADER', level, cid('atno') + struct.pack(
                '<IHHHH', attr, num(c.get('num')), ch(nf.get('userChar')) if nf is not None else 0,
                ch(nf.get('prefixChar')) if nf is not None else 0, ch(nf.get('suffixChar')) if nf is not None else 0))])
        else:
            raise Unsupported(f'control hp:{tag} in paragraph id={p.get("id")}')

    # -- section definition ----------------------------------------------------------------------------------------------
    def sec_def(self, sp, level):
        vis = first(sp, 'visibility')
        attr = 0
        if vis is not None:
            attr |= b(vis.get('hideFirstHeader')) | b(vis.get('hideFirstFooter')) << 1 | b(vis.get('hideFirstMasterPage')) << 2
            attr |= b(vis.get('hideFirstPageNum')) << 5 | b(vis.get('hideFirstEmptyLine')) << 19
            # the page border and fill: the words Hangul writes for bits 3 / 8 (border) and 4 / 9 (fill), measured by setting
            # each bit in an .hwp and saving it as HWPX; line numbers are bit 24
            for key, hide, show in (('border', 3, 8), ('fill', 4, 9)):
                word = vis.get(key, 'SHOW_ALL')
                if word not in ('SHOW_ALL', 'HIDE_FIRST', 'SHOW_FIRST'):
                    raise Unsupported(f'page {key} visibility "{word}" (hp:visibility) in {self.where}')
                attr |= {'SHOW_ALL': 0, 'HIDE_FIRST': 1 << hide, 'SHOW_FIRST': 1 << show}[word]
            attr |= b(vis.get('showLineNumber')) << 24
        # what the section record has no field for yet is refused, never dropped
        memo_ids = [m.get('id') for m in self.src.head.iter() if isinstance(m.tag, str) and ln(m) == 'memoPr']
        memo_ref = num(sp.get('memoShapeIDRef'))
        if memo_ref and str(memo_ref) not in memo_ids:
            raise Unsupported(f'memo shape {memo_ref} of {self.where} is not in the header (hp:secPr memoShapeIDRef)')
        if num(sp.get('textVerticalWidthHead')) not in (0, 1):
            raise Unsupported(f'section setting "vertical text width head {sp.get("textVerticalWidthHead")}" (hp:secPr) in {self.where}')
        if sp.get('textDirection', 'HORIZONTAL') not in ('HORIZONTAL', 'VERTICAL'):
            raise Unsupported(f'text direction "{sp.get("textDirection")}" (hp:secPr) in {self.where}')
        masters = []                                           # (kind, LIST_HEADER + paragraphs) of the master pages, in file order
        kinds = {'BOTH': 29, 'EVEN': 30, 'ODD': 31}
        for mp in kids(sp, 'masterPage'):
            href = self.src.items.get(mp.get('idRef'), (None,))[0]
            if href is None or not self.src.has(href):
                raise Unsupported(f'master page {mp.get("idRef")} is not in the package ({self.where})')
            root = ET.fromstring(self.src.read(href))
            fo_dedupe.remap(root, self.src.idmaps)
            if num(root.get('pageNumber')) or num(root.get('pageDuplicate')) or num(root.get('pageFront')):
                raise Unsupported(f'master page {mp.get("idRef")}: page number / duplicate / front settings')
            kind = pick(kinds, root.get('type', 'BOTH'), 'master page type')
            if masters and kind <= masters[-1][0]:
                raise Unsupported(f'master pages of {self.where} are not in the order both, even, odd')
            sl = first(root, 'subList')
            plist = kids(sl, 'p')
            masters.append((kind, [rec('LIST_HEADER', level + 1, struct.pack('<III', len(plist), self.list_attr(sl),
                                                                            num(sl.get('textWidth')))
                                       + struct.pack('<I', num(sl.get('textHeight'))) + bytes(18))]
                            + self.paras(plist, level + 1)))
        for kind, _ in masters:
            attr |= 1 << kind
        sn = first(sp, 'startNum')
        grid = first(sp, 'grid')
        if grid is not None and num(grid.get('wonggojiFormat')):
            attr |= 1 << 22                                            # manuscript paper (원고지) format
        # where the page number starts (both, even, odd pages); hwp2hwpx leaves the attribute out for the value 3
        attr |= {'BOTH': 0, 'EVEN': 1, 'ODD': 2, None: 3}.get(sn.get('pageStartsOn') if sn is not None else 'BOTH', 3) << 20
        d = (cid('secd') + struct.pack('<IHhhI', attr, num(sp.get('spaceColumns')),
                                       num(grid.get('lineGrid')) if grid is not None else 0,
                                       num(grid.get('charGrid')) if grid is not None else 0, num(sp.get('tabStop')))
             + struct.pack('<HHHHHH', num(sp.get('outlineShapeIDRef')), num(sn.get('page')) if sn is not None else 0,
                           num(sn.get('pic')) if sn is not None else 0, num(sn.get('tbl')) if sn is not None else 0,
                           num(sn.get('equation')) if sn is not None else 0, 0))
        d = bytearray(d.ljust(47, b'\x00'))
        if memo_ref:                                                   # the memo shape: its place in the MEMO_SHAPE list, 1-based (HW73)
            struct.pack_into('<H', d, 34, memo_ids.index(str(memo_ref)) + 1)
        if sp.get('textDirection') == 'VERTICAL':
            d[36] = 2                                                  # measured in Hangul
        d[36] |= 16 * num(sp.get('textVerticalWidthHead'))             # the vertical text width head: bit 4 of that byte (HW73)
        lns = first(sp, 'lineNumberShape')                             # line numbers: restart type, count by, distance, start
        if lns is not None:
            d[38] = num(lns.get('restartType'))
            struct.pack_into('<HH', d, 39, num(lns.get('countBy')), num(lns.get('distance')))
            struct.pack_into('<H', d, 45, num(lns.get('startNumber')))
        out = [rec('CTRL_HEADER', level, bytes(d))]
        pres = first(sp, 'presentation')
        if pres is not None:
            out.append(rec('CTRL_DATA', level + 1, presentation(pres, self.bins)))      # the page effects (쪽 연출): a parameter set (HW87)
        pp = first(sp, 'pagePr')
        m = first(pp, 'margin')
        out.append(rec('PAGE_DEF', level + 1, struct.pack(
            '<IIIIIIIIII', num(pp.get('width')), num(pp.get('height')), num(m.get('left')), num(m.get('right')),
            num(m.get('top')), num(m.get('bottom')), num(m.get('header')), num(m.get('footer')), num(m.get('gutter')),
            (1 if pp.get('landscape') == 'NARROWLY' else 0)
            | GUTTER.get(pp.get('gutterType'), 0) << 1)))
        for name in ('footNotePr', 'endNotePr'):
            out.append(rec('FOOTNOTE_SHAPE', level + 1, note_shape(first(sp, name))))
        for pb in kids(sp, 'pageBorderFill'):
            o = first(pb, 'offset')
            attr = {'PAPER': 1, 'CONTENT': 0}.get(pb.get('textBorder', 'PAPER'), 1) | b(pb.get('headerInside')) << 1 \
                | b(pb.get('footerInside')) << 2 | BORDER_AREA.get(pb.get('fillArea', 'PAPER'), 0) << 3
            out.append(rec('PAGE_BORDER_FILL', level + 1, struct.pack(
                '<IHHHHH', attr, num(o.get('left')), num(o.get('right')), num(o.get('top')), num(o.get('bottom')),
                num(pb.get('borderFillIDRef')))))
        for _, recs in masters:
            out += recs
        return out

    def col_def(self, c, level):
        """The column definition control (`cold`): attribute (type, count, direction, same size), gap, widths, line."""
        n = num(c.get('colCount'), 1)
        same = num(c.get('sameSz'), 1)
        attr = COL_TYPE.get(c.get('type', 'NEWSPAPER'), 0) | n << 2
        attr |= COL_LAYOUT.get(c.get('layout', 'LEFT'), 0) << 10 | same << 12
        body = struct.pack('<HH', attr, num(c.get('sameGap')))
        if not same:
            for cs in kids(c, 'colSz'):
                body += struct.pack('<HH', num(cs.get('width')), num(cs.get('gap')))
        cl = first(c, 'colLine')
        t = w = col = 0
        if cl is not None:
            t = pick({x: i for i, x in enumerate(LINE)}, cl.get('type', 'SOLID'), 'column line')
            wd = (cl.get('width') or '0.1 mm').replace('mm', '').strip()
            w = WIDTH.index(wd) if wd in WIDTH else 0
            col = color(cl.get('color'), 0)
        body += struct.pack('<HBBI', 0, t, w, col)
        return [rec('CTRL_HEADER', level, cid('cold') + body)]

    # -- objects -----------------------------------------------------------------------------------------------------------
    def common(self, el, name, desc=''):
        """CTRL_HEADER payload of an object: id, attribute, offsets, size, z order, outer margins, instance id, text."""
        sz, pos, om = first(el, 'sz'), first(el, 'pos'), first(el, 'outMargin')
        a = 0
        if pos is not None:
            a |= b(pos.get('treatAsChar')) | b(pos.get('affectLSpacing')) << 2
            a |= V_REL.get(pos.get('vertRelTo', 'PARA'), 2) << 3
            a |= POS_VALIGN.get(pos.get('vertAlign', 'TOP'), 0) << 5
            a |= H_REL.get(pos.get('horzRelTo', 'PARA'), 3) << 8
            a |= POS_HALIGN.get(pos.get('horzAlign', 'LEFT'), 0) << 10
            a |= b(pos.get('flowWithText')) << 13 | b(pos.get('allowOverlap')) << 14
        if sz is not None:
            a |= W_REL.get(sz.get('widthRelTo', 'ABSOLUTE'), 4) << 15
            a |= H_REL_SZ.get(sz.get('heightRelTo', 'ABSOLUTE'), 2) << 18
            a |= b(sz.get('protect')) << 20
        a |= OBJ_WRAP.get(el.get('textWrap', 'TOP_AND_BOTTOM'), 1) << 21
        a |= OBJ_FLOW.get(el.get('textFlow', 'BOTH_SIDES'), 0) << 24
        a |= NUMBERING.get(el.get('numberingType', 'NONE'), 0) << 26
        # holdAnchorAndSO has no bit of its own in the .hwp (Hangul saves the same attribute for 0 and 1); bit 29 = the object
        # has a caption (measured in Hangul: removing the caption clears it, and a file with a caption but no bit is refused)
        if first(el, 'caption') is not None:
            a |= 1 << 29
        a |= b(el.get('lock')) << 30                       # the object is locked (a table of 153 forms: bit 30; HW81)
        if self.ver >= (5, 1, 1, 0) and name in ('tbl ', 'gso '):       # what Hangul 2024 writes when it saves a HWPX: bit 28 and 2 more bytes (HW81)
            a |= 1 << 28
        om = om if om is not None else ET.Element('x')
        return (cid(name) + struct.pack('<IiiIIi', a & 0xFFFFFFFF, snum(pos.get('vertOffset')) if pos is not None else 0,
                                        snum(pos.get('horzOffset')) if pos is not None else 0, num(sz.get('width')),
                                        num(sz.get('height')), snum(el.get('zOrder')))
                + struct.pack('<4HI', num(om.get('left')), num(om.get('right')), num(om.get('top')), num(om.get('bottom')),
                              num(el.get('id')) & 0xFFFFFFFF)
                + struct.pack('<I', b(pos.get('holdAnchorAndSO')) if pos is not None and name == 'tbl ' else 0)      # a table: holdAnchorAndSO (HW87)
                + struct.pack('<H', len(crlf(desc))) + crlf(desc).encode('utf-16-le')
                + (bytes(2) if self.ver >= (5, 1, 1, 0) and name in ('tbl ', 'gso ') else b''))

    @staticmethod
    def list_attr(sl):
        """The attribute word of a LIST_HEADER: text direction, line wrap, vertical alignment."""
        attr = {'HORIZONTAL': 0, 'VERTICAL': 1}.get(sl.get('textDirection', 'HORIZONTAL'), 0)
        attr |= LINE_WRAP.get(sl.get('lineWrap', 'BREAK'), 0) << 3
        attr |= SUB_VALIGN.get(sl.get('vertAlign', 'TOP'), 0) << 5
        return attr

    def equation(self, eq, level):
        """`eqed` control: common properties and the EQEDIT record (script, size, colour, baseline, version, font)."""
        desc = first(eq, 'shapeComment')
        script = first(eq, 'script')
        return [rec('CTRL_HEADER', level, self.common(eq, 'eqed', (desc.text or '') if desc is not None else '')),
                rec('EQEDIT', level + 1, struct.pack('<I', {'CHAR': 0, 'LINE': 1}.get(eq.get('lineMode', 'CHAR'), 0))
                    + wstr((script.text or '') if script is not None else '')
                    + struct.pack('<IIhH', num(eq.get('baseUnit')), color(eq.get('textColor'), 0), num(eq.get('baseLine')), 0)
                    + wstr(eq.get('version', '')) + wstr(eq.get('font', '')))]

    def caption(self, cap, level):
        """A caption: LIST_HEADER (count, attribute, side and size of the caption) then its paragraphs."""
        sl = first(cap, 'subList')
        plist = kids(sl, 'p')
        side = CAPTION_SIDE.get(cap.get('side', 'BOTTOM'), 3) | b(cap.get('fullSz')) << 2
        data = (struct.pack('<II', len(plist), self.list_attr(sl)) + struct.pack('<IIhI', side, num(cap.get('width')),
                                                                                  num(cap.get('gap')), num(cap.get('lastWidth')))
                + bytes(8))
        return [rec('LIST_HEADER', level, data)] + self.paras(plist, level)

    @staticmethod
    def column_widths(rows):
        """The grid lines of a table, as Hangul works them out from the cells (HW81): the line after column j is the furthest right
        edge of the cells that end in column j (their start line plus their width). The cell header holds the distance of its
        two lines (288 of 304 tables of 153 forms equal; the width of the cell itself is never larger)."""
        cells = []
        for r in rows:
            for tc in kids(r, 'tc'):
                ca, cs, sz = (first(tc, x) for x in ('cellAddr', 'cellSpan', 'cellSz'))
                cells.append((num(ca.get('colAddr')), max(num(cs.get('colSpan')), 1), num(sz.get('width'))))
        n = max((c + k for c, k, _ in cells), default=0)
        by_end = {}                                          # cells grouped by their last column: one pass, not columns x cells
        for c, k, w in cells:
            by_end.setdefault(c + k - 1, []).append((c, w))
        x = [0] * (n + 1)
        for j in range(n):
            ends = [x[c] + w for c, w in by_end.get(j, ())]
            x[j + 1] = max(ends) if ends else x[j]
        return x

    def table(self, tbl, level):
        """`tbl ` control: common properties, [caption], TABLE, then the cells (LIST_HEADER + paragraphs each)."""
        out = [rec('CTRL_HEADER', level, self.common(tbl, 'tbl '))]
        lab = first(tbl, 'label')
        if lab is not None:                                  # a label sheet (라벨): a parameter set before TABLE (HW87)
            names = ('topmargin', 'leftmargin', 'boxwidth', 'boxlength', 'boxmarginhor', 'boxmarginver', 'labelcols', 'labelrows',
                     'landscape', 'pagewidth', 'pageheight')
            vals = [{'WIDELY': 0, 'NARROWLY': 1}.get(lab.get(n), 0) if n == 'landscape' else num(lab.get(n)) for n in names]
            items = b''.join(struct.pack('<HHi', 0x4000 + k, 4, vals[k]) for k in reversed(range(11)))     # item 0x4000 = topmargin ... 0x400A = pageheight, written from the last
            out.append(rec('CTRL_DATA', level + 1, struct.pack('<HhHHHHhH', 0x021B, 1, 0, 0x0242, 0x8000, 0x0242, 11, 0) + items))
        cap = first(tbl, 'caption')
        if cap is not None:
            out += self.caption(cap, level + 1)
        im = first(tbl, 'inMargin')
        rows = kids(tbl, 'tr')
        zones = kids(first(tbl, 'cellzoneList'), 'cellzone') if first(tbl, 'cellzoneList') is not None else []
        attr = TBL_BREAK.get(tbl.get('pageBreak', 'CELL'), 2) | b(tbl.get('repeatHeader')) << 2
        attr |= b(tbl.get('noAdjust')) << 3                # bit 3 = noAdjust (210 tables of 153 forms: 95 with it, all with the bit; HW81)
        out.append(rec('TABLE', level + 1, struct.pack('<IHHH4H', attr, num(tbl.get('rowCnt')), num(tbl.get('colCnt')),
                                                       num(tbl.get('cellSpacing')), num(im.get('left')), num(im.get('right')),
                                                       num(im.get('top')), num(im.get('bottom')))
                       + struct.pack('<%dH' % len(rows), *[len(kids(r, 'tc')) for r in rows])
                       + struct.pack('<HH', num(tbl.get('borderFillIDRef')), len(zones))
                       + b''.join(struct.pack('<5H', num(z.get('startRowAddr')), num(z.get('startColAddr')), num(z.get('endRowAddr')),
                                              num(z.get('endColAddr')), num(z.get('borderFillIDRef'))) for z in zones)))      # HW81
        cols = self.column_widths(rows)
        for r in rows:
            for tc in kids(r, 'tc'):
                sl = first(tc, 'subList')
                plist = kids(sl, 'p')
                ca, cs, sz, cm = (first(tc, x) for x in ('cellAddr', 'cellSpan', 'cellSz', 'cellMargin'))
                cattr = self.list_attr(sl) | b(tc.get('hasMargin')) << 16 | b(tc.get('header')) << 18 \
                    | b(tc.get('protect')) << 17 | b(tc.get('editable')) << 19      # bits 16-19: margin, protect, header, editable (12475 cells; HW81)
                data = (struct.pack('<II', len(plist), cattr) + struct.pack('<4H', num(ca.get('colAddr')), num(ca.get('rowAddr')),
                                                                        num(cs.get('colSpan')), num(cs.get('rowSpan')))
                        + struct.pack('<II4HH', num(sz.get('width')), num(sz.get('height')), snum(cm.get('left')) & 0xFFFF,
                                      snum(cm.get('right')) & 0xFFFF, snum(cm.get('top')) & 0xFFFF, snum(cm.get('bottom')) & 0xFFFF,
                                      num(tc.get('borderFillIDRef')))
                        + struct.pack('<I', cols[num(ca.get('colAddr')) + max(num(cs.get('colSpan')), 1)] - cols[num(ca.get('colAddr'))])
                        + (bytes.fromhex('ff1b02010000000040') + struct.pack('<H', 1) + wstr(tc.get('name')) + bytes(8) if tc.get('name') else bytes(9)))       # a cell with a name (HW81)
                out.append(rec('LIST_HEADER', level + 1, data))
                out += self.paras(plist, level + 1)
        return out




def presentation(el, bins=None):
    """`hp:presentation` -> the parameter set of CTRL_DATA after the section definition (HW87, HW89). Every item was found by changing
    one attribute of the HWPX and saving it in Hangul 2024 (offsets of the values in the 298 bytes of form 156953763); the constants
    are what Hangul writes whatever the attributes are. The fill is a gradation, one colour, a picture or none; the sound is the
    BinData id of the sound file."""
    def item(iid, typ, v):
        return struct.pack('<HHi', iid, typ, v)

    def bindata(iid, v):
        return struct.pack('<HHH', iid, 0x8002, v)

    def array(iid, vals):
        return struct.pack('<HHi', iid, 0x8001, len(vals)) + b''.join(struct.pack('<Hi', 5, v if v < 1 << 31 else v - (1 << 32)) for v in vals)

    def pset(pid, count, body):
        return struct.pack('<HhH', pid, count, 0) + body
    ref = (bins.by_ref if bins is not None else {})
    sound = None
    if el.get('soundIDRef'):
        sound = ref.get(el.get('soundIDRef'))
        if sound is None:                         # the file is not in the package: write id 0, as Hangul does, and say so (HW92)
            sound = 0
            warn(f'presentation sound {el.get("soundIDRef")} is not in the package; written as BinData id 0')
    fb = first(el, 'fillBrush')
    gr = first(fb, 'gradation') if fb is not None else None
    wb = first(fb, 'winBrush') if fb is not None else None
    ib = first(fb, 'imgBrush') if fb is not None else None
    fill = b''
    if gr is not None:
        cols = [color(c.get('value'), 0) for c in kids(gr, 'color')]
        if len(cols) > 10:
            raise Unsupported('presentation gradient with more than 10 colours')
        grad = (item(0x400B, 6, num(gr.get('alpha'))) + item(0x400A, 6, num(gr.get('stepCenter'), 50)) + array(0x4009, [0] * 10)
                + array(0x4008, (cols + [0] * 10)[:10]) + item(0x4007, 5, num(gr.get('colorNum'), len(cols))) + item(0x4006, 5, num(gr.get('step'), 100))
                + item(0x4005, 5, num(gr.get('centerY'))) + item(0x4004, 5, num(gr.get('centerX'), 50)) + item(0x4003, 5, num(gr.get('angle')))
                + item(0x4002, 5, pick(om.GRADIENT_NUM, gr.get('type', 'LINEAR'), 'gradation type')) + item(0x4001, 9, 4) + item(0x402F, 6, 0)
                + item(0x4031, 6, 0) + item(0x4030, 6, 1))
        fill = struct.pack('<HH', 0x0266, 0x8000) + pset(0x0266, 14, grad)
    elif wb is not None:
        win = (item(0x4001, 9, 1) + item(0x4018, 6, num(wb.get('alpha'))) + item(0x4016, 5, -1) + item(0x4015, 9, color(wb.get('hatchColor'), 0) & 0xFFFFFF)
               + item(0x4014, 9, color(wb.get('faceColor'), 0) & 0xFFFFFF) + item(0x402F, 6, 1) + item(0x4031, 6, 0) + item(0x4030, 6, 0))
        fill = struct.pack('<HH', 0x0266, 0x8000) + pset(0x0266, 8, win)
    elif ib is not None:
        im = first(ib, 'img')
        bid = ref.get(im.get('binaryItemIDRef')) if im is not None else None
        if bid is None:
            raise Unsupported('presentation picture is not in the package')
        pic = (item(0x4001, 9, 2) + item(0x401F, 6, 1) + bindata(0x401E, bid) + item(0x4024, 5, pick(om.inverse(om.IMG_MODES), ib.get('mode', 'TILE'), 'presentation picture mode'))
               + item(0x4022, 2, snum(im.get('contrast'))) + item(0x4021, 2, snum(im.get('bright')))
               + item(0x4020, 6, pick(om.inverse(om.IMG_EFFECT), im.get('effect', 'REAL_PIC'), 'picture effect'))
               + item(0x402F, 6, 0) + item(0x4031, 6, 1) + item(0x4033, 6, num(im.get('alpha'))) + item(0x4030, 6, 0))
        fill = struct.pack('<HH', 0x0266, 0x8000) + pset(0x0266, 11, pic)
    elif fb is not None and len(fb):
        raise Unsupported('presentation fill that is not a gradation, a colour or a picture')
    applyto = pick({'WholeDoc': 0, 'NewSection': 1}, el.get('applyto', 'WholeDoc'), 'presentation applyto')
    inner = (item(0x4004, 9, applyto) + item(0x4005, 9, num(el.get('showtime'))) + item(0x4003, 5, num(el.get('autoshow')))
             + item(0x4002, 5, num(el.get('invertText'))) + (bindata(0x4001, sound) if sound is not None else b'')
             + item(0x4000, 9, pick(om.inverse(om.PRESENT_EFFECT), el.get('effect', 'none'), 'presentation effect')) + fill)
    count = 5 + (1 if sound is not None else 0) + (1 if fill else 0)
    return pset(0x021B, 1, struct.pack('<HH', 0x0219, 0x8000) + pset(0x0219, count, inner))


def note_shape(n):
    """FOOTNOTE_SHAPE of a section: number format, user and surrounding characters, start number, separator line, spacing."""
    nf = first(n, 'autoNumFormat')
    nl, sp, nu, pl = (first(n, x) for x in ('noteLine', 'noteSpacing', 'numbering', 'placement'))
    attr = pick(NUM_FORMAT, nf.get('type', 'DIGIT'), 'note number format')
    attr |= {'EACH_COLUMN': 0, 'MERGED_COLUMN': 1, 'RIGHT_MOST_COLUMN': 2, 'END_OF_DOCUMENT': 0, 'END_OF_SECTION': 1
             }.get(pl.get('place', 'EACH_COLUMN'), 0) << 8
    attr |= NOTE_NUMBERING.get(nu.get('type', 'CONTINUOUS'), 0) << 10
    attr |= b(nf.get('supscript')) << 12 | b(pl.get('beneathText')) << 13
    ch = lambda v: ord(v) if v else 0
    w = (nl.get('width') or '0.12 mm').replace('mm', '').strip()
    return (struct.pack('<IHHHH', attr, ch(nf.get('userChar')), ch(nf.get('prefixChar')), ch(nf.get('suffixChar')),
                        num(nu.get('newNum'), 1))
            + struct.pack('<iHHH', snum(nl.get('length')), num(sp.get('aboveLine')), num(sp.get('belowLine')),
                          num(sp.get('betweenNotes')))
            + struct.pack('<BBI', pick({x: i for i, x in enumerate(LINE)}, nl.get('type', 'SOLID'), 'note line'),
                          WIDTH.index(w) if w in WIDTH else 1, color(nl.get('color'), 0)))


def section_records(source, name, bins):
    root = ET.fromstring(source.read(name))
    fo_dedupe.remap(root, source.idmaps)
    w = Writer(source, bins)
    w.where = name
    return w.paras(kids(root, 'p'), 0)
