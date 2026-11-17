"""BodyText sections -> section<N>.xml: paragraphs, runs, text, the section definition and columns (rules HW29-).

A paragraph = PARA_HEADER + PARA_TEXT / PARA_CHAR_SHAPE / PARA_LINE_SEG + its controls. Every PARA_CHAR_SHAPE pair opens one
`hp:run`; text goes into `hp:t` (a tab, a line break and the fixed spaces are elements inside it), every extended control
character takes the next CTRL_HEADER of the paragraph (owpmlobj.control).
"""
import struct

from . import fmt
from .fmt import Unsupported
from .owpmlmap import El, document

T = fmt.T


class Node:
    """A record with its children (the records one level deeper that follow it)."""
    __slots__ = ('tag', 'lvl', 'd', 'kids', 'at')

    def __init__(self, tag, lvl, d, at):
        self.tag, self.lvl, self.d, self.kids, self.at = tag, lvl, d, [], at

    def find(self, tag):
        return [k for k in self.kids if k.tag == tag]

    def first(self, tag):
        for k in self.kids:
            if k.tag == tag:
                return k
        return None


def tree(recs):
    """[[tag, level, payload]] -> top-level Nodes (`at` = index of the record in the stream)."""
    root = Node(0, -1, b'', -1)
    stack = [root]
    for i, (tag, lvl, d) in enumerate(recs):
        n = Node(tag, lvl, d, i)
        while stack[-1].lvl >= lvl:
            stack.pop()
        stack[-1].kids.append(n)
        stack.append(n)
    return root.kids


class Para:
    """A PARA_HEADER node, decoded."""

    def __init__(self, node):
        d = node.d
        self.node = node
        self.nchars = struct.unpack_from('<I', d, 0)[0] & 0x7FFFFFFF
        self.last = bool(struct.unpack_from('<I', d, 0)[0] >> 31)
        self.mask = struct.unpack_from('<I', d, 4)[0]
        self.shape, self.style, self.brk = struct.unpack_from('<HBB', d, 8)
        self.ncs, self.nrt, self.nls = struct.unpack_from('<HHH', d, 12)
        self.inst = struct.unpack_from('<I', d, 18)[0] if len(d) >= 22 else 0
        self.merged = struct.unpack_from('<H', d, 22)[0] if len(d) >= 24 else 0
        text = node.first(T['PARA_TEXT'])
        self.text = text.d if text else b''
        cs = node.first(T['PARA_CHAR_SHAPE'])
        self.cs = [struct.unpack_from('<II', cs.d, k) for k in range(0, len(cs.d) - 7, 8)] if cs else [(0, 0)]
        ls = node.first(T['PARA_LINE_SEG'])
        self.ls = [struct.unpack_from('<IiiiiiiiI', ls.d, k) for k in range(0, len(ls.d) - 35, 36)] if ls else []   # spacing may be negative
        self.ctrls = [k for k in node.kids if k.tag == T['CTRL_HEADER']]
        rt = node.first(T['PARA_RANGE_TAG'])
        self.ranges = [struct.unpack_from('<III', rt.d, k) for k in range(0, len(rt.d) - 11, 12)] if rt else []
        # a tracked change of a character / paragraph shape (range type 18 / 19): Hangul 2024 writes it as `charTcId` on the runs
        # the range touches and `paraTcId` on the paragraph (68 / 113 in the one file that has them)
        self.char_tc = [(s, e, tag & 0xFFFFFF) for s, e, tag in self.ranges if tag >> 24 == 18]
        self.para_tc = [tag & 0xFFFFFF for s, e, tag in self.ranges if tag >> 24 == 19]
        self.extra = (T['MEMO_LIST'], T['LIST_HEADER'], T['PARA_HEADER'])      # a memo: its number, its list and the list's paragraphs
        for k in node.kids:
            if k.tag not in (T['PARA_TEXT'], T['PARA_CHAR_SHAPE'], T['PARA_LINE_SEG'], T['CTRL_HEADER'], T['PARA_RANGE_TAG']) + self.extra:
                from .owpml import tag_name
                raise Unsupported(tag_name(k.tag), f'paragraph, record {k.at}')

    def marks(self, sec):
        """The range tags as [(position, order, element)] sorted: type 2 = a highlight (markpenBegin colour ... markpenEnd); 16 / 17 =
        a tracked insert / delete (`insertBegin Id TcId` ... `insertEnd Id TcId paraend`: the number of the track change is the low
        24 bits, Id counts these ranges in the order of the file, paraend = the range reaches the paragraph end); types 0, 1, 18
        and 19 leave no mark in Hangul's own HWPX (checked on 4 files: 192 ranges of 18 / 19 in one); any other type stops."""
        from .owpmlmap import color
        out = []
        for s, e, tag in self.ranges:
            typ = tag >> 24
            if typ == 2:
                out.append((s, 1, El('hp:markpenBegin', {'color': color(tag & 0xFFFFFF)})))
                out.append((e, 0, El('hp:markpenEnd')))
            elif typ in (16, 17):
                sec.tc_id += 1
                kind = 'insert' if typ == 16 else 'delete'
                at = {'Id': sec.tc_id, 'TcId': tag & 0xFFFFFF}
                out.append((s, 1, El(f'hp:{kind}Begin', at)))
                # paraend: the range reaches the paragraph end and it is the only tracked insert / delete of the paragraph
                # (510 markers of the one file with track changes: 510 equal to Hangul 2024's HWPX; HW105)
                alone = sum(1 for _, _, t in self.ranges if t >> 24 in (16, 17)) == 1
                out.append((e, 0, El(f'hp:{kind}End', {**at, 'paraend': 1 if e >= self.nchars and alone else 0})))
            elif typ in (18, 19):
                sec.tc_id += 1                      # a char / paragraph shape change takes a number too, and leaves no mark
            elif typ not in (0, 1):
                raise Unsupported(f'PARA_RANGE_TAG type {typ}', f'paragraph, record {self.node.at}')
        out.sort(key=lambda m: (m[0], m[1]))
        return out

    def items(self):
        """[(position, kind, value)]: kind 'c' = a character (str), 'x' = an extended control (code), 'i' = an inline
        control (code, 12 data bytes), 'n' = a line break, 'e' = the end of the paragraph."""
        out, i, n = [], 0, len(self.text) // 2
        t = self.text
        while i < n:
            c = struct.unpack_from('<H', t, i * 2)[0]
            if c >= 32:
                if 0xD800 <= c < 0xDC00 and i + 1 < n:
                    lo = struct.unpack_from('<H', t, i * 2 + 2)[0]
                    out.append((i, 'c', chr(0x10000 + ((c - 0xD800) << 10) + (lo - 0xDC00))))
                    i += 2
                    continue
                out.append((i, 'c', chr(c)))
            elif c in fmt.EXTENDED:
                out.append((i, 'x', c))
                i += 8
                continue
            elif c in fmt.INLINE:
                out.append((i, 'i', (c, t[i * 2 + 2:i * 2 + 14])))
                i += 8
                continue
            elif c == fmt.LINE_BREAK:
                out.append((i, 'n', c))
            elif c == fmt.PARA_END:
                out.append((i, 'e', c))
            else:
                out.append((i, 'k', c))                    # 24 hyphen, 30 / 31 fixed spaces, others
            i += 1
        return out


class Sections:
    def __init__(self, pk, head):
        self.pk, self.head = pk, head
        self.masters = []            # (name, xml bytes) of master pages
        self.bin_used = []           # bin data ids in the order the body refers to them
        self.section_no = 0
        self.place = ''
        self.fields = []             # the open fields: (begin id, field id)
        self.tc_id = 0               # the track change ranges seen so far (the `Id` of insertBegin / deleteBegin)
        self.masters = []            # (master page name, section number) in the order of the file
        self.master_docs = []        # (name, root El) of each master page

    def xml(self):
        for n, path in enumerate(self.pk.sections):
            self.section_no = n
            nodes = tree(self.pk.records(path))
            sec = El('hs:sec')
            self.memos = {}              # memo number -> (LIST_HEADER, paragraphs): kept below the last paragraph of the section (HW53)
            todo = list(nodes)
            while todo:
                kids = todo.pop().kids
                todo += kids
                for i, k in enumerate(kids):
                    if k.tag == T['MEMO_LIST'] and i + 1 < len(kids) and kids[i + 1].tag == T['LIST_HEADER']:
                        cnt = struct.unpack_from('<i', kids[i + 1].d, 0)[0]
                        paras = [p for p in kids[i + 2:i + 2 + cnt] if p.tag == T['PARA_HEADER']]
                        self.memos[struct.unpack_from('<I', k.d, 0)[0]] = (kids[i + 1], paras)
            for node in nodes:
                if node.tag != T['PARA_HEADER']:
                    from .owpml import tag_name
                    raise Unsupported(tag_name(node.tag), f'{path}, record {node.at}')
                sec.add(self.paragraph(node, path))
            yield document(sec)

    def bin_ref(self, binid, place):
        """The manifest id of the embedded item a picture / OLE object refers to (BIN_DATA number, from 1)."""
        from . import owpmlpkg
        if not 1 <= binid <= len(self.head.bins):      # a picture whose data is not there: Hangul 2024 writes an empty reference
            return ''
        if self.head.bins[binid - 1]['kind'] == 'link':
            raise Unsupported(f'picture / object refers to BIN_DATA {binid}, which is not an embedded item', place)
        named = owpmlpkg.bin_name(binid, self.head.bins[binid - 1]['ext'])
        if named is None:
            raise Unsupported(f'BIN_DATA extension {self.head.bins[binid - 1]["ext"]!r}', place)
        return named[0]

    def masters_xml(self):
        from .owpmlmap import document
        return [(name, document(root)) for name, root in self.master_docs]

    def preview_text(self):
        """PrvText for a file that has none (HW09): the text of the body paragraphs, a table as <cell cell ...>, each
        paragraph ended by CR LF; the first 1024 characters."""
        def ptext(node):
            p = Para(node)
            out, ci = [], 0
            for _, kind, val in p.items():
                if kind == 'c':
                    out.append(val)
                elif kind == 'x':
                    c = p.ctrls[ci] if ci < len(p.ctrls) else None
                    ci += 1
                    if c is not None and fmt.ctrl_id(c.d) == 'tbl ':
                        cells, seen = [], False
                        for lh in c.kids:
                            seen = seen or lh.tag == T['TABLE']          # the caption comes before the TABLE record
                            if seen and lh.tag == T['PARA_HEADER']:
                                cells.append(ptext(lh))
                        out.append('<' + ' '.join(t for t in cells if t) + '>')
                elif kind == 'n':
                    out.append('\n')
            return ''.join(out)
        text = ''
        for path in self.pk.sections:
            for node in tree(self.pk.records(path)):
                if node.tag == T['PARA_HEADER']:
                    text += ptext(node) + '\r\n'
        return text[:1024]

    # -- paragraphs
    def paragraph(self, node, where):
        from . import owpmlobj
        p = Para(node)
        # the same character shape in two ranges in a row is one run in Hangul 2024's HWPX (HW100: 24 forms)
        p.cs = [c for i, c in enumerate(p.cs) if i == 0 or c[1] != p.cs[i - 1][1]]
        self.cur = p
        self.place = f'{where} record {node.at}'
        at = {'id': p.inst, 'paraPrIDRef': p.shape, 'styleIDRef': p.style, 'pageBreak': p.brk >> 2 & 1,
              'columnBreak': p.brk >> 3 & 1, 'merged': p.merged & 1}
        if p.para_tc:
            at['paraTcId'] = p.para_tc[0]
        el = El('hp:p', at)
        items = p.items()
        ctrl_at = 0
        after_cold = False
        marks = p.marks(self)
        bounds = [pos for pos, _ in p.cs] + [1 << 30]

        def new_run(k, shape):
            tc = [t for s, e, t in p.char_tc if s < bounds[k + 1] and e > bounds[k]]
            return El('hp:run', {'charPrIDRef': shape, **({'charTcId': tc[-1]} if tc else {})})
        for k, (pos, shape) in enumerate(p.cs):
            run = new_run(k, shape)
            cur = None
            for ipos, kind, val in items:
                if not bounds[k] <= ipos < bounds[k + 1]:
                    continue
                while marks and marks[0][0] <= ipos:       # a highlight starts / ends before the character at this position
                    if cur is None:
                        cur = El('hp:t')
                    cur.add(marks.pop(0)[2])
                if kind == 'e':
                    continue
                if after_cold and kind == 'x' and ctrl_at < len(p.ctrls) and fmt.ctrl_id(p.ctrls[ctrl_at].d) in ('secd', 'cold'):
                    pass                            # the section definition and the columns in either order share one run (3 forms)
                elif after_cold:                    # Hangul 2018+: the run of the section controls ends after the columns
                    after_cold = False
                    if cur is not None:
                        run.add(cur)
                        cur = None
                    el.add(run)
                    run = new_run(k, shape)
                if kind == 'c' or kind == 'n' or kind == 'k' or (kind == 'i' and val[0] in (fmt.TAB, 8)):
                    if cur is None:
                        cur = El('hp:t')
                    if kind == 'c':
                        if cur.kids and isinstance(cur.kids[-1], str):
                            cur.kids[-1] += val
                        else:
                            cur.kids.append(val)
                    elif kind == 'n':
                        cur.add(El('hp:lineBreak'))
                    elif kind == 'k':
                        cur.add(owpmlobj.special_char(val, self.place))
                    elif val[0] == 8:                  # a title mark (for the table of contents); `ignore` as Hangul 2024 writes it
                        marks_ = {b'tit\x4d': 1, b'ngi\x4d': 0}     # 'titM' -> ignore 1, 'ngiM' -> ignore 0 (129 marks of Hangul 2024)
                        if val[1][:4] not in marks_:
                            raise Unsupported(f'title mark data {val[1].hex()}', self.place)
                        cur.add(El('hp:titleMark', {'ignore': marks_[val[1][:4]]}))
                    else:
                        d = val[1]
                        cur.add(El('hp:tab', {'width': struct.unpack_from('<I', d, 0)[0], 'leader': d[4], 'type': d[5]}))
                    continue
                if cur is not None:
                    run.add(cur)
                    cur = None
                if kind == 'x':
                    if ctrl_at >= len(p.ctrls):
                        raise Unsupported(f'control character {val} without CTRL_HEADER', self.place)
                    node_c = p.ctrls[ctrl_at]
                    run.add(*owpmlobj.control(self, node_c))
                    after_cold = (fmt.ctrl_id(node_c.d) == 'cold' or after_cold and fmt.ctrl_id(node_c.d) == 'secd') and not self.head.legacy
                    ctrl_at += 1
                else:
                    run.add(*owpmlobj.inline(self, val[0]))
            if after_cold:                          # nothing follows the columns in this range: the empty run stays (HW100, 7 forms)
                el.add(run)
                run = new_run(k, shape)
            after_cold = False
            # a mark on the boundary of two runs ends the first one, but the start of a tracked change opens the next one (HW53)
            while marks and marks[0][0] <= bounds[k + 1] and not (marks[0][0] == bounds[k + 1] and marks[0][2].tag in
                                                                  ('hp:insertBegin', 'hp:deleteBegin')):
                if cur is None:
                    cur = El('hp:t')
                cur.add(marks.pop(0)[2])
            if cur is not None:
                run.add(cur)
            elif ctrl_at and k == len(p.cs) - 1:       # the paragraph has controls and ends after one: an empty hp:t
                run.add(El('hp:t'))
            el.add(run)
        if p.ls:
            el.add(El('hp:linesegarray', None, *[El('hp:lineseg', dict(zip(
                ('textpos', 'vertpos', 'vertsize', 'textheight', 'baseline', 'spacing', 'horzpos', 'horzsize', 'flags'), s)))
                for s in p.ls]))
        return el
