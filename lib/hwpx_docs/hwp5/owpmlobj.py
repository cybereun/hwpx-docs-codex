"""Controls of a paragraph (CTRL_HEADER and what hangs below it) -> OWPML elements (rules HW29-).

  control(sections, ctrl_node) -> [El]          one extended control character of a paragraph
  inline(sections, code) -> [El]                an inline control (field end ...) with no CTRL_HEADER
  special_char(code, place) -> El               hyphen, no-break space, fixed-width space

The table `CONTROLS` maps the control id ('secd', 'tbl ', ...) to its converter. A control that is not in it stops the
conversion: `UNSUPPORTED <id> <place>`.
"""
import re
import struct

from . import fmt
from . import owpmlmap as om
from .fmt import Unsupported
from .owpmlmap import GRADIENT, LINE, NUMFMT, El, Reader, color, mm

T = fmt.T


def enum(table, v, what, place):
    if not 0 <= v < len(table):
        raise Unsupported(f'{what} value {v}', place)
    return table[v]


def special_char(code, place):
    names = {24: 'hp:hypen', 30: 'hp:nbSpace', 31: 'hp:fwSpace'}          # (sic) Hangul spells the hyphen element `hypen`
    if code not in names:
        raise Unsupported(f'character code {code}', place)
    return El(names[code])


def inline(sec, code):
    if code == 4 and sec.fields:                        # the end of the innermost open field
        begin, fid = sec.fields.pop()
        return [El('hp:ctrl', None, El('hp:fieldEnd', {'beginIDRef': begin, 'fieldid': fid}))]
    raise Unsupported(f'inline control {code}', sec.place)


def control(sec, node):
    cid = fmt.ctrl_id(node.d)
    fn = CONTROLS.get(cid)
    if fn is None:
        raise Unsupported(f'control {cid!r}', sec.place)
    try:
        return fn(sec, node)
    except (struct.error, IndexError, ValueError) as e:      # a record shorter than its layout, or a number out of range
        from .owpml import CONTROL_NAMES, short_record_text
        name = f'control {cid!r}' + (f' ({CONTROL_NAMES[cid]})' if cid in CONTROL_NAMES else '')
        raise Unsupported(short_record_text(e, name), f'(at {sec.place})') from None


# ---- section definition and columns ------------------------------------------------------------------------------------
def note_shape(sec, node, kind):
    """FOOTNOTE_SHAPE -> footNotePr / endNotePr."""
    d = node.d
    attr, user, prefix, suffix, start, length, above, below, between, ltype, lwidth, lcolor = struct.unpack_from('<IHHHHiHHHBBI', d, 0)
    fmt_no = attr & 0xFF
    ch = lambda c: chr(c) if c else ''
    # attribute bits (format document order; a file with garbage in bits 14-15 gives the same as Hangul's own HWPX):
    # 0-7 number shape, 8-9 placement, 10-11 numbering, 12 superscript, 13 beneath the text
    num_type = om.NOTE_NUMBERING[min(attr >> 10 & 3, 2)]
    place_n = attr >> 8 & 3
    if kind == 'foot':
        place = ['EACH_COLUMN', 'MERGED_COLUMN', 'RIGHT_MOST_COLUMN'][min(place_n, 2)]
    else:
        place = ['END_OF_DOCUMENT', 'END_OF_SECTION'][min(place_n, 1)]
    el = El('hp:footNotePr' if kind == 'foot' else 'hp:endNotePr')
    el.add(El('hp:autoNumFormat', {'type': NUMFMT[fmt_no] if fmt_no < len(NUMFMT) else 'DIGIT', 'userChar': ch(user),
                                   'prefixChar': ch(prefix), 'suffixChar': ch(suffix), 'supscript': attr >> 12 & 1}))
    el.add(El('hp:noteLine', {'length': length, 'type': LINE[ltype] if ltype < len(LINE) else 'SOLID', 'width': mm(lwidth),
                              'color': color(lcolor)}))
    el.add(El('hp:noteSpacing', {'betweenNotes': between, 'belowLine': below, 'aboveLine': above}))
    el.add(El('hp:numbering', {'type': num_type, 'newNum': start}))
    el.add(El('hp:placement', {'place': place, 'beneathText': attr >> 13 & 1}))
    return el


def param_set(d, pos=0):
    """A parameter set (the CTRL_DATA records): set id WORD, item count DWORD, then items of id WORD, type WORD and the value: type
    0x8000 a set inside, 0x8001 an array (count DWORD, then type WORD + DWORD each), 0x8002 a string (length WORD, UTF-16), any other a
    DWORD. -> ((set id, {item id: (type, value)}), end position)."""
    sid, cnt = struct.unpack_from('<HI', d, pos)
    pos += 6
    items = {}
    for _ in range(cnt):
        iid, typ = struct.unpack_from('<HH', d, pos)
        pos += 4
        if typ == 0x8000:
            val, pos = param_set(d, pos)
        elif typ == 0x8001:
            n = struct.unpack_from('<I', d, pos)[0]
            val = [struct.unpack_from('<I', d, pos + 4 + 6 * k + 2)[0] for k in range(n)]
            pos += 4 + 6 * n
        elif typ == 0x8002:
            n = struct.unpack_from('<H', d, pos)[0]
            val = d[pos + 2:pos + 2 + 2 * n].decode('utf-16-le')
            pos += 2 + 2 * n
        else:
            val = struct.unpack_from('<I', d, pos)[0]
            pos += 4
        items[iid] = (typ, val)
    return (sid, items), pos


def presentation(sec, d):
    """The slide show settings of a presentation document: the set 0x021b > 0x0219 below the section definition (form 156953763, 280
    bytes) -> `hp:presentation`. Item 0x4000 the effect (`PRESENT_EFFECT`), 0x4002 = 1 invert text, the set 0x0266 the background
    (item 0x4001 = 4 a gradient: 0x4002 type 1 LINEAR / 2 RADIAL / 3 CONICAL / 4 SQUARE, 0x4003 angle, 0x4004 / 0x4005 centre, 0x4006
    step, 0x4007 colour count (2 only), 0x400a step centre, 0x4008 the colours). Measured one item at a time in Hangul 2024 (HW104);
    the other items change nothing in its HWPX. Any other set: None (HW47: Hangul 2024 writes nothing for it)."""
    try:
        (sid, top), end = param_set(d)
    except (struct.error, UnicodeDecodeError):
        return None
    if sid != 0x21B or 0x219 not in top or top[0x219][0] != 0x8000:
        return None
    pres = top[0x219][1][1]
    from .owpmlmap import PRESENT_EFFECT
    eff = pres.get(0x4000, (9, 0))[1]
    if eff >= len(PRESENT_EFFECT):
        raise Unsupported(f'slide show effect {eff}', sec.place)
    el = El('hp:presentation', {'effect': PRESENT_EFFECT[eff], 'soundIDRef': '', 'invertText': 1 if pres.get(0x4002, (9, 0))[1] == 1 else 0,
                                'autoshow': 0, 'showtime': 0, 'applyto': 'WholeDoc'})
    fill = pres.get(0x266, (0x8000, (0, {})))[1][1]
    kind = fill.get(0x4001, (9, 0))[1]
    if kind & 4:
        ncol = fill.get(0x4007, (5, 0))[1]
        gtype = fill.get(0x4002, (5, 1))[1]
        cols = fill.get(0x4008, (0x8001, []))[1]
        if ncol != 2 or gtype not in (1, 2, 3, 4) or len(cols) < 2:
            raise Unsupported(f'slide show background gradient (colours {ncol}, type {gtype})', sec.place)
        g = El('hc:gradation', {'type': GRADIENT[gtype], 'angle': fill.get(0x4003, (5, 0))[1],
                                'centerX': fill.get(0x4004, (5, 0))[1], 'centerY': fill.get(0x4005, (5, 0))[1],
                                'step': fill.get(0x4006, (5, 0))[1], 'colorNum': 2, 'stepCenter': fill.get(0x400A, (6, 0))[1], 'alpha': 0})
        g.add(*[El('hc:color', {'value': color(c)}) for c in cols[:2]])
        el.add(El('hc:fillBrush', None, g))
    elif kind not in (0, 1, 2, 3, 5, 7, 8):
        raise Unsupported(f'slide show background kind {kind}', sec.place)
    return el


def sec_def(sec, node):
    d = node.d
    attr, gap, line_grid, char_grid, tab, outline, page, pic, tbl, eq = struct.unpack_from('<IHHHIHHHHH', d, 4)
    kids = {k.tag: [] for k in node.kids}
    for k in node.kids:
        kids[k.tag].append(k)
    for tag in kids:
        if tag not in (T['PAGE_DEF'], T['FOOTNOTE_SHAPE'], T['PAGE_BORDER_FILL'], T['LIST_HEADER'], T['PARA_HEADER'],
                       T['CTRL_DATA']):                # CTRL_DATA: Hangul's own parameter set of the section; Hangul 2024 writes no HWPX for it
            from .owpml import tag_name
            raise Unsupported(tag_name(tag), f'section definition, {sec.place}')
    masters = lists_of(node)
    kinds = [k for bit, k in ((29, 'BOTH'), (30, 'EVEN'), (31, 'ODD')) if attr >> bit & 1]   # the master pages that exist, in file order
    if len(kinds) != len(masters):
        raise Unsupported(f'{len(masters)} master pages for the flags {attr >> 29:03b}', sec.place)
    # the memo shape of the section: a WORD at byte 34, the place in the MEMO_SHAPE list (1-based, 0 none; rule HW73 and 45 files of
    # Hangul 2024); the vertical text width head: bit 4 of byte 36. A number the list does not hold: Hangul writes 0.
    memo = struct.unpack_from('<H', d, 34)[0] if len(d) >= 36 else 0
    if memo > len(sec.head.by.get(T['MEMO_SHAPE'], [])):
        memo = 0
    textdir = attr >> 16 & 7
    if textdir not in (0, 1):
        raise Unsupported(f'text direction {textdir}', sec.place)
    el = El('hp:secPr', {'id': '', 'textDirection': 'VERTICAL' if textdir else 'HORIZONTAL', 'spaceColumns': gap,
                         'tabStop': tab, 'tabStopVal': tab // 2, 'tabStopUnit': 'HWPUNIT', 'outlineShapeIDRef': outline,
                         'memoShapeIDRef': memo, 'textVerticalWidthHead': d[36] >> 4 & 1 if len(d) > 36 else 0,
                         'masterPageCnt': len(masters)})
    el.add(El('hp:grid', {'lineGrid': line_grid, 'charGrid': char_grid, 'wonggojiFormat': attr >> 22 & 1}))
    starts = ['BOTH', 'EVEN', 'ODD', None][attr >> 20 & 3]            # both bits set: Hangul writes no attribute
    el.add(El('hp:startNum', {'pageStartsOn': starts, 'page': page, 'pic': pic, 'tbl': tbl, 'equation': eq}))
    if attr & 0x118:                       # hide the border / the fill, or the border on the first page only: no file shows the words
        raise Unsupported('section flags hide border / fill / border on the first page only', sec.place)
    el.add(El('hp:visibility', {'hideFirstHeader': attr & 1, 'hideFirstFooter': attr >> 1 & 1, 'hideFirstMasterPage': attr >> 2 & 1,
                                'border': 'SHOW_ALL', 'fill': 'SHOW_FIRST' if attr & 0x200 else 'SHOW_ALL',   # bit 9 seen in 5 files
                                'hideFirstPageNum': attr >> 5 & 1,
                                'hideFirstEmptyLine': attr >> 19 & 1, 'showLineNumber': 0}))
    el.add(El('hp:lineNumberShape', {'restartType': 0, 'countBy': 0, 'distance': 0, 'startNumber': 0}))
    pd = kids.get(T['PAGE_DEF'])
    if pd:
        w, h, ml, mr, mt, mb, mh, mf, mg, pattr = struct.unpack_from('<10I', pd[0].d, 0)
        el.add(El('hp:pagePr', {'landscape': 'NARROWLY' if pattr & 1 else 'WIDELY', 'width': w, 'height': h,
                                'gutterType': om.GUTTER[min(pattr >> 1 & 3, 2)]},
                  El('hp:margin', {'header': mh, 'footer': mf, 'gutter': mg, 'left': ml, 'right': mr, 'top': mt, 'bottom': mb})))
    notes = kids.get(T['FOOTNOTE_SHAPE'], [])
    if notes:
        el.add(note_shape(sec, notes[0], 'foot'))
        if len(notes) > 1:
            el.add(note_shape(sec, notes[1], 'end'))
    for typ, k in zip(('BOTH', 'EVEN', 'ODD'), kids.get(T['PAGE_BORDER_FILL'], [])):
        battr, ol, orr, ot, ob, bf = struct.unpack_from('<I4hH', k.d, 0)
        el.add(El('hp:pageBorderFill', {'type': typ, 'borderFillIDRef': bf, 'textBorder': 'PAPER' if battr & 1 else 'CONTENT',
                                        'headerInside': battr >> 1 & 1, 'footerInside': battr >> 2 & 1,
                                        'fillArea': om.BORDER_AREA[min(battr >> 3 & 3, 2)]},
                  El('hp:offset', {'left': ol, 'right': orr, 'top': ot, 'bottom': ob})))
    for k in kids.get(T['CTRL_DATA'], []):
        pr = presentation(sec, k.d)
        if pr is not None:
            el.add(pr)
    for kind, (lh, paras) in zip(kinds, masters):
        name = f'masterpage{len(sec.masters)}'
        la, tw, th = struct.unpack_from('<III', lh.d, 4)
        root = El('masterPage', {'id': name, 'type': kind, 'pageNumber': 0, 'pageDuplicate': 0, 'pageFront': 0},
                  sub_list(sec, la, paras, textWidth=tw, textHeight=th))
        sec.masters.append((name, sec.section_no))
        sec.master_docs.append((name, root))
        el.add(El('hp:masterPage', {'idRef': name}))
    return [el]


def col_def(sec, node):
    r = Reader(node.d, 4)
    attr, gap = r.u('Hh')
    count = attr >> 2 & 0xFF
    same = attr >> 12 & 1
    sizes = []
    if not same:
        for _ in range(count):
            sizes.append(r.u('HH'))
    ltype = 0                                  # the oldest records stop after the column sizes: no line
    if r.left() >= 8:
        _, ltype, lwidth, lcolor = r.u('HBBI')
    el = El('hp:colPr', {'id': '', 'type': om.COL_TYPE[min(attr & 3, 2)], 'layout': om.COL_LAYOUT[min(attr >> 10 & 3, 2)],
                         'colCount': count, 'sameSz': same, 'sameGap': gap})
    for w, g in sizes:
        el.add(El('hp:colSz', {'width': w, 'gap': g}))
    if ltype:
        el.add(El('hp:colLine', {'type': LINE[ltype] if ltype < len(LINE) else 'SOLID', 'width': mm(lwidth),
                                 'color': color(lcolor)}))       # 3 = DASH as in drawing lines (a column line of Hangul 2024)
    return [El('hp:ctrl', None, el)]


# ---- objects: the common part, lists, tables -----------------------------------------------------------------------------


class Common:
    """The part every object control (table, drawing object, equation, form) starts with (HW20)."""

    def __init__(self, sec, d):
        self.attr, self.y, self.x, self.w, self.h, self.z = struct.unpack_from('<IiiIIi', d, 4)
        self.margins = struct.unpack_from('<4H', d, 28)
        self.inst = struct.unpack_from('<I', d, 36)[0]
        n = struct.unpack_from('<H', d, 44)[0] if len(d) >= 46 else 0
        self.desc = d[46:46 + 2 * n].decode('utf-16-le', 'replace') if n else ''
        self.end = 46 + 2 * n
        a = self.attr
        place = sec.place
        self.wrap = enum(om.OBJ_WRAP, a >> 21 & 7, 'text wrap', place)
        self.flow = enum(om.OBJ_FLOW, a >> 24 & 3, 'text flow', place)

    def sz(self):
        a = self.attr
        return El('hp:sz', {'width': self.w, 'widthRelTo': om.W_REL[min(a >> 15 & 7, 4)], 'height': self.h,
                            'heightRelTo': om.H_REL_SZ[min(a >> 18 & 3, 2)], 'protect': a >> 20 & 1})

    def pos(self):
        a = self.attr
        return El('hp:pos', {'treatAsChar': a & 1, 'affectLSpacing': a >> 2 & 1, 'flowWithText': a >> 13 & 1,
                             'allowOverlap': a >> 14 & 1, 'holdAnchorAndSO': 0, 'vertRelTo': om.V_REL[min(a >> 3 & 3, 2)],
                             'horzRelTo': om.H_REL[a >> 8 & 3], 'vertAlign': om.POS_VALIGN[min(a >> 5 & 7, 4)],
                             'horzAlign': om.POS_HALIGN[min(a >> 10 & 7, 4)], 'vertOffset': self.y & 0xFFFFFFFF,
                             'horzOffset': self.x & 0xFFFFFFFF})

    def out_margin(self):
        l, r, t, b = self.margins
        return El('hp:outMargin', {'left': l, 'right': r, 'top': t, 'bottom': b})

    def tail(self, sec):
        """size, position, outer margin, the caption (a list before the shape record), the comment: the end of an object element."""
        out = [self.sz(), self.pos(), self.out_margin()]
        if self.desc:                                   # the comment comes before the caption (Hangul 2024, an ellipse with both)
            out.append(El('hp:shapeComment', None, text=self.desc))
        if getattr(self, 'caption', None):
            out.append(caption(sec, *self.caption))
        return out


def sub_list(sec, attr, paras, **extra):
    """An hp:subList of paragraph nodes, from the attribute word of a LIST_HEADER (bits 0-2 text direction, 3-4 line wrap, 5-6 vertical align)."""
    at = {'id': '', 'textDirection': 'VERTICAL' if attr & 7 else 'HORIZONTAL',
          'lineWrap': om.LINE_WRAP[min(attr >> 3 & 3, 2)], 'vertAlign': om.SUB_VALIGN[min(attr >> 5 & 3, 2)],
          'linkListIDRef': 0, 'linkListNextIDRef': 0, 'textWidth': 0, 'textHeight': 0, 'hasTextRef': 0, 'hasNumRef': 0}
    at.update(extra)
    return El('hp:subList', at, *[sec.paragraph(p, sec.place) for p in paras])


def lists_of(node):
    """[(LIST_HEADER, [paragraph nodes])] of a control; the first count paragraphs after each LIST_HEADER belong to it."""
    out, kids, i = [], node.kids, 0
    while i < len(kids):
        n = kids[i]
        if n.tag == T['LIST_HEADER']:
            cnt = struct.unpack_from('<i', n.d, 0)[0]
            paras = [k for k in kids[i + 1:i + 1 + cnt] if k.tag == T['PARA_HEADER']]
            out.append((n, paras))
            i += 1 + len(paras)
        else:
            i += 1
    return out


def caption(sec, lh, paras):
    attr, width, gap, last = struct.unpack_from('<IIHI', lh.d, 8)
    return El('hp:caption', {'side': om.CAPTION_SIDE[attr & 3], 'fullSz': attr >> 2 & 1, 'width': width,
                             'gap': gap, 'lastWidth': last},
              sub_list(sec, struct.unpack_from('<I', lh.d, 4)[0], paras))


def table(sec, node):
    c = Common(sec, node.d)
    lists = lists_of(node)
    tb = node.first(T['TABLE'])
    if tb is None:
        raise Unsupported('table without TABLE record', sec.place)
    attr, rows, cols, spacing, ml, mr, mt, mb = struct.unpack_from('<IHHH4H', tb.d, 0)
    row_sizes = struct.unpack_from('<%dH' % rows, tb.d, 18)
    bf = struct.unpack_from('<H', tb.d, 18 + 2 * rows)[0]
    cap = None
    body = []
    for lh, paras in lists:
        if lh.at < tb.at:
            cap = (lh, paras)
        else:
            body.append((lh, paras))
    # read from 589 tables of Hangul's own HWPX: numbering type = object bits 26-27 (0 NONE, 1 PICTURE, 2 TABLE), lock = bit 30,
    # page break = TABLE attribute bits 0-1 (0 NONE, 1 TABLE, 2 CELL), noAdjust = TABLE attribute bit 3
    el = El('hp:tbl', {'id': c.inst, 'zOrder': c.z, 'numberingType': om.NUMBERING[c.attr >> 26 & 3],
                       'textWrap': c.wrap, 'textFlow': c.flow, 'lock': c.attr >> 30 & 1,
                       'dropcapstyle': 'None', 'pageBreak': om.TBL_BREAK[min(attr & 3, 2)],
                       'repeatHeader': attr >> 2 & 1, 'rowCnt': rows, 'colCnt': cols, 'cellSpacing': spacing,
                       'borderFillIDRef': bf, 'noAdjust': attr >> 3 & 1})
    el.add(c.sz(), c.pos(), c.out_margin())
    if cap:
        el.add(caption(sec, *cap))
    el.add(El('hp:inMargin', {'left': ml, 'right': mr, 'top': mt, 'bottom': mb}))
    end = 20 + 2 * rows                                  # the cell zones (5.0.1.0 and later): count, then row / column of the first and
    if len(tb.d) >= end + 2:                             # the last cell and the border fill (5 WORDs each; HW100: 1 table of 141716763)
        nz = struct.unpack_from('<H', tb.d, end)[0]
        if nz and len(tb.d) >= end + 2 + 10 * nz:
            zl = El('hp:cellzoneList')
            for k in range(nz):
                sr, sc, er, ec, zbf = struct.unpack_from('<5H', tb.d, end + 2 + 10 * k)
                zl.add(El('hp:cellzone', {'startRowAddr': sr, 'startColAddr': sc, 'endRowAddr': er, 'endColAddr': ec,
                                          'borderFillIDRef': zbf}))
            el.add(zl)
    trs = {}
    for lh, paras in body:
        d = lh.d
        lattr = struct.unpack_from('<I', d, 4)[0]
        col, row, cspan, rspan, w, h, cl, cr, ct, cb, cbf = struct.unpack_from('<4H2I4hH', d, 8)
        cl, cr, ct, cb = (v & 0xFFFFFFFF for v in (cl, cr, ct, cb))       # a negative margin: Hangul writes it as an unsigned 32-bit number
        # a named cell (a field name): after the 47 bytes comes a parameter set `1b02 0100 0000 0040 0100 <len> <chars>`
        # the set starts after 47 bytes, or after 39 when one byte 0xFF follows the width (5.0.3 forms: 4 files, HW100)
        name = ''
        for at in (47, 39):
            if len(d) >= at + 12 and d[at:at + 2] == b'\x1b\x02' and (at == 47 or d[38] == 0xFF):
                n_chars = struct.unpack_from('<H', d, at + 10)[0]
                name = d[at + 12:at + 12 + 2 * n_chars].decode('utf-16-le', 'replace')
                break
        tc = El('hp:tc', {'name': name, 'header': lattr >> 18 & 1, 'hasMargin': lattr >> 16 & 1, 'protect': lattr >> 17 & 1,
                          'editable': lattr >> 19 & 1, 'dirty': 0, 'borderFillIDRef': cbf})
        tc.add(sub_list(sec, lattr, paras))
        tc.add(El('hp:cellAddr', {'colAddr': col, 'rowAddr': row}), El('hp:cellSpan', {'colSpan': cspan, 'rowSpan': rspan}),
               El('hp:cellSz', {'width': w, 'height': h}), El('hp:cellMargin', {'left': cl, 'right': cr, 'top': ct, 'bottom': cb}))
        trs.setdefault(row, El('hp:tr')).add(tc)
    for r in sorted(trs):
        el.add(trs[r])
    return [el]


# ---- header / footer, notes, numbers, small controls -----------------------------------------------------------------------
PAGE_POS = ['NONE', 'TOP_LEFT', 'TOP_CENTER', 'TOP_RIGHT', 'BOTTOM_LEFT', 'BOTTOM_CENTER', 'BOTTOM_RIGHT', 'OUTSIDE_TOP',
            'OUTSIDE_BOTTOM', 'INSIDE_TOP', 'INSIDE_BOTTOM']


def one_list(sec, node, what):
    lists = lists_of(node)
    if len(lists) != 1:
        raise Unsupported(f'{what} with {len(lists)} lists', sec.place)
    return lists[0]


def ch(c):
    return chr(c) if c else ''


def head_foot(sec, node):
    cid = fmt.ctrl_id(node.d)
    attr, idn = struct.unpack_from('<II', node.d, 4) if len(node.d) >= 12 else (struct.unpack_from('<I', node.d, 4)[0], 0)
    lh, paras = one_list(sec, node, 'header / footer')
    la, tw, th = struct.unpack_from('<III', lh.d, 4)
    el = El('hp:header' if cid == 'head' else 'hp:footer', {'id': idn, 'applyPageType': enum(om.APPLY_PAGE, attr & 3, 'apply page', sec.place)},
            sub_list(sec, la, paras, textWidth=tw, textHeight=th))
    return [El('hp:ctrl', None, el)]


def note(sec, node):
    cid = fmt.ctrl_id(node.d)
    number, prefix, suffix = struct.unpack_from('<IHH', node.d, 4)
    inst = struct.unpack_from('<I', node.d, 16)[0] if len(node.d) >= 20 else 0       # the oldest record has no instance id
    lh, paras = one_list(sec, node, 'note')
    at = {'number': number}
    if prefix:
        at['prefixChar'] = prefix
    at.update({'suffixChar': suffix, 'instId': inst})
    el = El('hp:footNote' if cid == 'fn  ' else 'hp:endNote', at,
            sub_list(sec, struct.unpack_from('<I', lh.d, 4)[0], paras))
    return [El('hp:ctrl', None, el)]


def auto_num(sec, node):
    attr, num, user, prefix, suffix = struct.unpack_from('<IH3H', node.d, 4)
    fmt_no = attr >> 4 & 0xFF
    el = El('hp:autoNum', {'num': num, 'numType': enum(om.NUM_TYPE, attr & 15, 'auto number type', sec.place)},
            El('hp:autoNumFormat', {'type': enum(NUMFMT, fmt_no, 'number format', sec.place), 'userChar': ch(user),
                                    'prefixChar': ch(prefix), 'suffixChar': ch(suffix), 'supscript': attr >> 12 & 1}))
    return [El('hp:ctrl', None, el)]


def new_num(sec, node):
    attr, num = struct.unpack_from('<IH', node.d, 4)
    return [El('hp:ctrl', None, El('hp:newNum', {'num': num, 'numType': enum(om.NUM_TYPE, attr & 15, 'number type', sec.place)}))]


def page_num(sec, node):
    attr, user, prefix, suffix, side = struct.unpack_from('<I4H', node.d, 4)
    at = {'pos': enum(PAGE_POS, attr >> 8 & 15, 'page number position', sec.place),
          'formatType': enum(NUMFMT, attr & 0xFF, 'number format', sec.place), 'sideChar': ch(side)}
    for k, v in (('userChar', user), ('prefixChar', prefix), ('suffixChar', suffix)):
        if v:
            at[k] = ch(v)
    return [El('hp:ctrl', None, El('hp:pageNum', at))]


def index_mark(sec, node):
    """An index mark: the first and the second key (two wide strings), as in Hangul 2024's HWPX of one file."""
    r = Reader(node.d, 4)
    first = r.wstr()
    second = r.wstr() if r.left() >= 2 else ''
    third = r.wstr() if r.left() >= 2 else ''
    if third or any(r.raw(r.left())) or not first:         # a third key, or data after the keys: not seen in any file
        raise Unsupported('index mark with a third key or data after the keys', sec.place)
    keys = [El('hp:firstKey', None, text=first)] + ([El('hp:secondKey', None, text=second)] if second else [])
    return [El('hp:ctrl', None, El('hp:indexmark', None, *keys))]


def page_hiding(sec, node):
    a = struct.unpack_from('<I', node.d, 4)[0]
    return [El('hp:ctrl', None, El('hp:pageHiding', {'hideHeader': a & 1, 'hideFooter': a >> 1 & 1, 'hideMasterPage': a >> 2 & 1,
                                                       'hideBorder': a >> 3 & 1, 'hideFill': a >> 4 & 1, 'hidePageNum': a >> 5 & 1}))]


def ctrl_data_name(node):
    """The name of a bookmark / field in its CTRL_DATA parameter set (id, count, 2 bytes, then item id, type 1 = string, text)."""
    cd = node.first(T['CTRL_DATA'])
    if cd is None or len(cd.d) < 12:
        return ''
    n = struct.unpack_from('<H', cd.d, 10)[0]
    return cd.d[12:12 + 2 * n].decode('utf-16-le', 'replace')


def bookmark(sec, node):
    return [El('hp:ctrl', None, El('hp:bookmark', {'name': ctrl_data_name(node)}))]


def hidden_comment(sec, node):
    lh, paras = one_list(sec, node, 'hidden comment')
    return [El('hp:ctrl', None, El('hp:hiddenComment', None,
                                   sub_list(sec, struct.unpack_from('<I', lh.d, 4)[0], paras)))]


def dutmal(sec, node):
    r = Reader(node.d, 4)
    main, sub = r.wstr(), r.wstr()
    pos, ratio, option, style, align = r.u('5I')
    el = El('hp:dutmal', {'posType': enum(['TOP', 'BOTTOM', 'CENTER'], pos, 'dutmal position', sec.place), 'szRatio': ratio,
                          'option': option, 'styleIDRef': style,
                          'align': enum(om.ALIGN, align, 'dutmal align', sec.place)})
    el.add(El('hp:mainText', None, text=main or None), El('hp:subText', None, text=sub or None))
    return [el]


# as Hangul spells them (SHAPE_REVERSAL_TIRANGLE with the typo, read from the 15 compose samples)
COMPOSE_SHAPES = ['CHAR', 'SHAPE_CIRCLE', 'SHAPE_REVERSAL_CIRCLE', 'SHAPE_RECTANGLE', 'SHAPE_REVERSAL_RECTANGLE',
                  'SHAPE_TRIANGLE', 'SHAPE_REVERSAL_TIRANGLE', 'SHAPE_LIGHT', 'SHAPE_RHOMBUS', 'SHAPE_REVERSAL_RHOMBUS',
                  'SHAPE_ROUNDED_RECTANGLE', 'SHAPE_EMPTY_CIRCULATE_TRIANGLE', 'SHAPE_THIN_CIRCULATE_TRIANGLE',
                  'SHAPE_THICK_CIRCULATE_TRIANGLE']


def compose(sec, node):
    r = Reader(node.d, 4)
    text = r.wstr()
    if r.left() < 4:        # the oldest record is the text only: Hangul 2024 fills in overlapped characters, size -4, ten default shapes
        circle, size, ctype, cnt, ids = 0, -4, 1, 10, [0xFFFFFFFF] * 10
    else:
        circle, size, ctype, cnt = r.u('BbBB')
        ids = [r.u('I') for _ in range(cnt)]
    if ctype == 0:                              # spread: the HWP text starts with the frame glyph (or a blank), OWPML keeps the letters
        text = text[1:]
    el = El('hp:compose', {'circleType': enum(COMPOSE_SHAPES, circle, 'compose circle type', sec.place),
                           'charSz': size, 'composeType': enum(om.COMPOSE, ctype, 'compose type', sec.place),
                           'charPrCnt': cnt, 'composeText': text})
    el.add(*[El('hp:charPr', {'prIDRef': i}) for i in ids])
    return [el]


# ---- fields -------------------------------------------------------------------------------------------------------------
FIELD_TYPES = {'%clk': 'CLICK_HERE', '%bmk': 'BOOKMARK', '%hlk': 'HYPERLINK', '%fmu': 'FORMULA', '%xrf': 'CROSSREF',
               '%usr': 'USER_INFO', '%smr': 'SUMMERY'}      # seen in pairs / Hangul 2024 files (SUMMERY is Hangul's spelling)


def hyperlink_params(cmd, place):
    """`<target>;<kind>;0;0;` (kind 0 = a Hangul document, 1 = an address) -> the 4-5 string parameters (read from Hangul 2024's
    HWPX of 6 files: Command as it is, Path = the target with its backslash escapes undone, a fixed target and open type)."""
    import re
    # `<target>;<kind>;<target type>;<open>;` (the last `;` may be missing): kind 0 document / 1 address / 2 mail, target type 0
    # bookmark / 1 outline, open 0 this tab / 1 a new tab; a target that starts with `?` (a place in a document) has no Path;
    # Path = the target without the backslash before `:` and `;` (`.\\a.hwp` keeps both backslashes). 9 hyperlinks of Hangul 2024.
    m = re.fullmatch(r'(.*);([012]);([012]);([01]);?', cmd, re.S)
    if not m:
        raise Unsupported(f'hyperlink command {cmd[:40]!r}', place)
    target, kind, ttype, opn = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    out = [El('hp:stringParam', {'name': 'Command'}, text=cmd)]
    if not target.startswith('?'):
        out.append(El('hp:stringParam', {'name': 'Path'}, text=re.sub(r'\\([:;])', r'\1', target)))
    out += [El('hp:stringParam', {'name': 'Category'}, text=['HWPHYPERLINK_TYPE_HWP', 'HWPHYPERLINK_TYPE_URL', 'HWPHYPERLINK_TYPE_EMAIL'][kind]),
            El('hp:stringParam', {'name': 'TargetType'},
               text=['HWPHYPERLINK_TARGET_BOOKMARK', 'HWPHYPERLINK_TARGET_OUTLINE', 'HWPHYPERLINK_TARGET_TABLE'][ttype]),
            El('hp:stringParam', {'name': 'DocOpenType'}, text=['HWPHYPERLINK_JUMP_CURRENTTAB', 'HWPHYPERLINK_JUMP_NEWTAB'][opn])]
    return out


def crossref_params(cmd, place):
    """`?#<id>;0;0;1;0;` -> the 8 parameters of Hangul 2024's cross reference (one command form seen in 2 files)."""
    import re
    # `<?target>;<type>;<content>;<link>;<open>;`: every value measured one at a time in Hangul 2024 (HW53); a value that Hangul
    # writes no parameter for (type 7-9, content 4-5, open 3-4) stops
    m = re.fullmatch(r'(\?.*);(\d);(\d);(\d);(\d);', cmd, re.S)
    types = ['TARGET_TABLE', 'TARGET_PICTURE', 'TARGET_EQUATION', 'TARGET_FOOTNOTE', 'TARGET_ENDNOTE', 'TARGET_OUTLINE',
             'TARGET_BOOKMARK']
    contents = ['OBJECT_TYPE_PAGE', 'OBJECT_TYPE_NUMBER', 'OBJECT_TYPE_CONTENTS', 'OBJECT_TYPE_UPDOWNPOS']
    opens = ['HWPHYPERLINK_JUMP_CURRENTTAB', 'HWPHYPERLINK_JUMP_NEWTAB', 'HWPHYPERLINK_JUMP_NEWWINDOW']
    if not m or int(m.group(2)) >= len(types) or int(m.group(3)) >= len(contents) or int(m.group(4)) > 2 or int(m.group(5)) >= len(opens):
        raise Unsupported(f'cross reference command {cmd[:40]!r}', place)
    return [El('hp:stringParam', {'name': 'Command'}, text=cmd), El('hp:stringParam', {'name': 'RefPath'}, text=m.group(1) + ';'),
            El('hp:stringParam', {'name': 'RefType'}, text=types[int(m.group(2))]),
            El('hp:stringParam', {'name': 'RefContentType'}, text=contents[int(m.group(3))]),
            El('hp:booleanParam', {'name': 'RefHyperLink'}, text='false' if m.group(4) == '0' else 'true'),
            El('hp:stringParam', {'name': 'RefOpenType'}, text=opens[int(m.group(5))])]


def formula_params(cmd, place):
    """`<formula>??<result format>;;<last result>` -> Command, Formula, ResultFormat, LastResult (read from 3 files of Hangul 2024)."""
    if '??' not in cmd or ';;' not in cmd.split('??', 1)[1]:
        raise Unsupported(f'formula command {cmd[:40]!r}', place)
    formula, rest = cmd.split('??', 1)
    fmt_, last = rest.split(';;', 1)
    return [El('hp:stringParam', {'name': 'Command'}, text=cmd), El('hp:stringParam', {'name': 'Formula'}, text=formula),
            El('hp:stringParam', {'name': 'ResultFormat'}, text=fmt_), El('hp:stringParam', {'name': 'LastResult'}, text=last)]


def field(sec, node):
    """A field start ('%clk', '%bmk', and the memo '%unk'): hp:fieldBegin; the end is an inline control (4)."""
    d = node.d
    cid = fmt.ctrl_id(d)
    attr, etc = struct.unpack_from('<IB', d, 4)
    n = struct.unpack_from('<H', d, 9)[0]
    cmd = d[11:11 + 2 * n].decode('utf-16-le', 'replace')
    # the oldest field records end after the command: no instance id, no z order (Hangul 2024 writes a new id and zorder -1; 1 file)
    inst, zo = struct.unpack_from('<II', d, 11 + 2 * n) if len(d) >= 19 + 2 * n else (0, 0)
    fid = struct.unpack_from('<I', d, 0)[0]
    memo = cid == '%unk' and cmd.startswith('MEMO/')
    rev = None                                           # a proofreading mark: field type and Hangul's field id (2 files of Hangul 2024)
    if cid == '%unk' and cmd == '$RevisionSimpleChange;':
        rev = ('PROOFREADING_MARKS_SIMPLECHANGE', b'%%*c')
    elif cid == '%unk' and re.fullmatch(r'\$RevisionSign;\d+;', cmd):
        rev = ('PROOFREADING_MARKS_SIGN', b'%sig')
    if memo:
        fid = struct.unpack('>I', b'%%me')[0]            # Hangul's field id for a memo
    elif rev:
        fid = struct.unpack('>I', rev[1])[0]
    if not memo and not rev and cid not in FIELD_TYPES:
        raise Unsupported(f'field {cid!r} {cmd[:30]!r}' if cid == '%unk' else f'field {cid!r}', sec.place)
    at = {'id': inst, 'type': 'MEMO' if memo else rev[0] if rev else FIELD_TYPES[cid], 'name': ctrl_data_name(node), 'editable': attr & 1,
          'dirty': attr >> 15 & 1, 'zorder': zo if zo else -1, 'fieldid': fid}
    el = El('hp:fieldBegin', at)
    params = [El('hp:integerParam', {'name': 'Prop'}, text=str(etc))]
    if cid == '%hlk':
        params += hyperlink_params(cmd, sec.place)
    elif cid == '%fmu':
        params += formula_params(cmd, sec.place)
    elif cid == '%xrf':
        params = [El('hp:booleanParam', {'name': 'Fiexde'}, text='1')] + params + crossref_params(cmd, sec.place)   # (sic) Hangul's spelling
    elif cid in ('%usr', '%smr'):          # the command is a name like $Company / $author, repeated as Category / Property
        params += [El('hp:stringParam', {'name': 'Command'}, text=cmd),
                   El('hp:stringParam', {'name': 'Category' if cid == '%usr' else 'Property'}, text=cmd)]
    elif cmd:
        params.append(El('hp:stringParam', {'name': 'Command', **({'xml:space': 'preserve'} if cmd != cmd.strip() else {})}, text=cmd))   # as Hangul: only around spaces (HW100)
        if cid == '%clk' and not sec.head.legacy:     # Hangul 2018+ repeats the guide text as its own parameter (38 fields of one file)
            try:
                guide = parse_set(cmd, 0, len(cmd)).get('Clickhere', {}).get('Direction')
            except ValueError:
                guide = None
            if guide is not None:
                params.append(El('hp:stringParam', {'name': 'Direction', **({'xml:space': 'preserve'} if guide != guide.strip() else {})},
                                 text=guide))
    if memo:
        parts = cmd.split('/')
        if len(parts) < 7:
            raise Unsupported('memo command', sec.place)
        low, high = int(parts[3]), int(parts[4])
        import datetime
        t = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=((high << 32) | low) // 10, hours=9)
        # the command holds UTC; Hangul writes the author's local time (KST in the pair) with a Z
        params += [El('hp:stringParam', {'name': 'ID'}, text=f'memo{parts[2]}'),
                   El('hp:integerParam', {'name': 'Number'}, text=parts[2]),
                   El('hp:stringParam', {'name': 'Author'}, text=parts[5]),
                   El('hp:stringParam', {'name': 'MemoShapeIDRef'}, text=parts[1]),
                   El('hp:stringParam', {'name': 'CreateDateTime'}, text=t.strftime('%Y-%m-%dT%H:%M:%SZ'))]
    el.add(El('hp:parameters', {'cnt': len(params), 'name': ''}, *params))
    if memo:
        # the list of memo N is the one that follows the MEMO_LIST record of number N, in some paragraph of the section
        # (below the last one, below the same one: 014_english) or below the field itself (older files)
        lists = [sec.memos[int(parts[2])]] if int(parts[2]) in getattr(sec, 'memos', {}) else lists_of(sec.cur.node)
        if len(lists) != 1:
            raise Unsupported('memo without its list', sec.place)
        lh, paras = lists[0]
        el.add(sub_list(sec, struct.unpack_from('<I', lh.d, 4)[0], paras))
    sec.fields.append((inst, fid))
    return [El('hp:ctrl', None, el)]


# ---- form objects ---------------------------------------------------------------------------------------------------------
def parse_set(s, i, end):
    """The text property set of a form object: `Key:type:value` items separated by spaces; `set:N:` nests N characters,
    `wstring:N:` is N characters long (it may hold spaces)."""
    out = {}
    while i < end:
        while i < end and s[i] == ' ':
            i += 1
        if i >= end:
            break
        j = s.index(':', i)
        key = s[i:j]
        i = j + 1
        j = s.index(':', i)
        typ = s[i:j]
        i = j + 1
        if typ in ('set', 'wstring'):
            j = s.index(':', i)
            n = int(s[i:j])
            i = j + 1
            out[key] = parse_set(s, i, i + n) if typ == 'set' else s[i:i + n]
            i += n
        else:
            j = s.find(' ', i)
            j = end if j < 0 or j > end else j
            out[key] = int(s[i:j]) if typ == 'int' else s[i:j] == '1' if typ == 'bool' else s[i:j]
            i = j
    return out


def form(sec, node):
    c = Common(sec, node.d)
    fo = node.first(0x5B)
    if fo is None:
        raise Unsupported('form control without its property record', sec.place)
    kind = fo.d[:4][::-1].decode('latin-1')
    n = struct.unpack_from('<H', fo.d, 12)[0]
    text = fo.d[14:14 + 2 * n].decode('utf-16-le')
    props = parse_set(text, 0, len(text))
    cs, com = props.get('CharShapeSet', {}), props.get('CommonSet', {})
    b = lambda v: 1 if v else 0
    common = {'name': com.get('Name', ''), 'foreColor': color(com.get('ForeColor', 0)), 'backColor': color(com.get('BackColor', 0)),
              'groupName': com.get('GroupName', ''), 'tabStop': b(com.get('TabStop')), 'editable': b(com.get('Editable')),
              'tabOrder': com.get('TabOrder', 0), 'enabled': b(com.get('Enabled')), 'borderTypeIDRef': com.get('BorderType', 0),
              'drawFrame': b(com.get('DrawFrame')), 'printable': b(com.get('Printable')), 'command': com.get('Command', '')}
    fcp = El('hp:formCharPr', {'charPrIDRef': cs.get('CharShapeID', 0), 'followContext': b(cs.get('FollowContext')),
                               'autoSz': b(cs.get('AutoSize')), 'wordWrap': b(cs.get('WordWrap'))})
    extra = []
    if kind == '+pbt':
        bs = props.get('ButtonSet', {})
        tag, at = 'hp:btn', {'caption': bs.get('Caption', ''), 'radioGroupName': bs.get('RadioGroupName', ''),
                             'triState': b(bs.get('TriState')), **common}
    elif kind in ('+cbt', '+rbt'):
        bs = props.get('ButtonSet', {})
        tag = 'hp:checkBtn' if kind == '+cbt' else 'hp:radioBtn'
        val = bs.get('Value', 0)
        if val not in (0, 1):
            raise Unsupported(f'button value {val}', sec.place)
        at = {'caption': bs.get('Caption', ''), 'value': om.FORM_VALUE[val], 'radioGroupName': bs.get('RadioGroupName', ''),
              'triState': b(bs.get('TriState')), 'backStyle': om.FORM_BACK[min(bs.get('BackStyle', 0), 1)], **common}
    elif kind == '+cob':
        cb = props.get('ComboBoxSet', {})
        tag, at = 'hp:comboBox', {'listBoxRows': cb.get('ListBoxRows', 0), 'listBoxWidth': cb.get('ListBoxWidth', 0),
                                  'editEnable': b(cb.get('EditEnable')), 'selectedValue': '', **common}
        if cb.get('Text'):
            extra.append(El('hp:listItem', {'displayText': '', 'value': cb['Text']}))
    elif kind == '+edt':
        ed = props.get('EditSet', {})
        scroll, tabkey, align = ed.get('ScrollBars', 0), ed.get('TabKeyBehavior', 0), ed.get('AlignText', 0)
        tag = 'hp:edit'
        at = {'multiLine': b(ed.get('MultiLine')), 'passwordChar': ed.get('PasswordChar', ''), 'maxLength': ed.get('MaxLength', 0),
              'scrollBars': enum(om.FORM_SCROLL, scroll, 'edit scroll bars', sec.place),
              'tabKeyBehavior': enum(om.FORM_TAB, tabkey, 'edit tab key', sec.place),
              'numOnly': b(ed.get('Number')), 'readOnly': b(ed.get('ReadOnly')),
              'alignText': enum(om.ALIGN3, align, 'edit align', sec.place), **common}
        extra.append(El('hp:text', None, text=ed.get('Text') or None))
    else:
        raise Unsupported(f'form object {kind!r}', sec.place)
    el = El(tag, at, fcp, *extra, c.sz(), c.pos(), c.out_margin())
    if c.desc:
        el.add(El('hp:shapeComment', None, text=c.desc))
    return [el]


def equation(sec, node):
    c = Common(sec, node.d)
    eq = node.first(T['EQEDIT'])
    if eq is None:
        raise Unsupported('equation without EQEDIT', sec.place)
    r = Reader(eq.d)
    attr = r.u('I')
    script = r.wstr()
    size, col, base = r.u('IIi')
    # older records stop after the version, or before it: Hangul 2024 writes its defaults (read from 4 files)
    version = r.wstr() if r.left() >= 2 else 'Equation Version 60'
    font = r.wstr() if r.left() >= 2 else 'HYhwpEQ'
    el = El('hp:equation', {'id': c.inst, 'zOrder': c.z, 'numberingType': 'EQUATION', 'textWrap': c.wrap, 'textFlow': c.flow,
                            'lock': 0, 'dropcapstyle': 'None', 'version': version, 'baseLine': base, 'textColor': color(col),
                            'baseUnit': size, 'lineMode': 'LINE' if attr & 1 else 'CHAR', 'font': font})
    el.add(c.sz(), c.pos(), c.out_margin())
    if c.desc:
        el.add(El('hp:shapeComment', None, text=c.desc))
    el.add(El('hp:script', {'xml:space': 'preserve'} if script != script.strip() else None, text=script))
    return [el]


def gso(sec, node):
    from . import owpmlshape
    return owpmlshape.gso(sec, node)


CONTROLS = {'idxm': index_mark, '%hlk': field, '%fmu': field, '%xrf': field, '%usr': field, '%smr': field, 'form': form, 'eqed': equation, '%clk': field, '%bmk': field, '%unk': field, 'gso ': gso, 'secd': sec_def, 'cold': col_def, 'tbl ': table, 'head': head_foot, 'foot': head_foot, 'fn  ': note, 'en  ': note,
            'atno': auto_num, 'nwno': new_num, 'pgnp': page_num, 'pghd': page_hiding, 'bokm': bookmark,
            'tcmt': hidden_comment, 'tdut': dutmal, 'tcps': compose}
