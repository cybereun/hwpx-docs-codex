"""Layout of the preview: paragraphs (lines), tables, shapes and pictures as atoms (a text line or a table row, height in mm)."""
from ..core import read as rd
from ..core import textfit
import base64
import html
import math
import os
from .measure import BASE, PT, TAB, char_style, cwidth, eff_size, face, fam, fmt_num, lang, para_style, parse_line, strength, sv
from .svg import TEXT_STROKE, f3, rect, stroke, thin
import re
from . import drawers

OBJECTS = ('pic', 'table', 'drawn', 'missing')      # inline objects that sit on a line like a character
HU_MM = 283.465
INVISIBLE = ('hp:ctrl', 'hp:fieldBegin', 'hp:fieldEnd', 'hp:bookmark', 'hp:markpenBegin', 'hp:markpenEnd',
             'hp:titleMark', 'hp:indexmark', 'hp:hiddenComment', 'hp:lineBreak', 'hp:hyphen', 'hp:nbSpace', 'hp:fwSpace')


def object_of(d, st):
    """A spec item (block or run) that is an object -> the obj of a line ('drawn' by a drawer, or 'missing' = dashed
    placeholder), or None when `d` is not an object. Drawers: preview/drawers/ (register, register_inline)."""
    k = drawers.key_of(d)
    if k:
        got = drawers.block(k)(d[k], st)
        if got:
            return dict(got, kind='drawn', name=k)
        return dict(kind='missing', name=k, w=d[k].get('w', 5), h=d[k].get('h', 5)) if isinstance(d[k], dict) else None
    if isinstance(d.get('xml'), str):
        tag = (re.match(r'\s*<([\w:]+)', d['xml']) or [None, '?'])[1]
        fn = drawers.inline(tag)
        got = fn(d['xml'], st) if fn else None
        if got:
            return dict(got, kind='drawn', name=tag)
        sz = re.search(r'<hp:sz\b[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"', d['xml'])
        if sz and tag not in INVISIBLE:         # it takes room on the page, and nothing draws it
            return dict(kind='missing', name=tag, w=int(sz.group(1)) / HU_MM, h=int(sz.group(2)) / HU_MM)
        return None
    k = next((k for k, v in d.items() if isinstance(v, dict) and 'w' in v and 'h' in v and k not in KNOWN), None)
    return dict(kind='missing', name=k, w=d[k]['w'], h=d[k]['h']) if k else None     # an object of an unknown type


KNOWN = ('pic', 'table', 'equation')     # objects that layout.py draws itself (equation: script text until a drawer exists)


def emit_object(page, obj, x, y):
    page.marks.update(obj.get('marks') or ())          # a drawer can mark its page (drawers.register_inline)
    out = obj['draw'](x, y) if obj['kind'] == 'drawn' and obj.get('draw') else ([] if obj.get('marks') else None)
    if out is None:
        placeholder(page, x, y, obj['w'], obj['h'], obj['name'])
    else:
        page.svg.extend(out)


def placeholder(page, x, y, w, h, name):
    """Something the preview cannot draw: a dashed box with its type name, and one warning line (never a silent blank)."""
    page.svg.append('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#C00000" stroke-width="0.3" '
                    'stroke-dasharray="1.5 1"/>' % (f3(x), f3(y), f3(max(w, 2)), f3(max(h, 2))))
    page.svg.append('<text x="%s" y="%s" font-family="\'Malgun Gothic\',sans-serif" font-size="%s" fill="#C00000" '
                    'text-anchor="middle" dominant-baseline="central">%s</text>' % (
                        f3(x + max(w, 2) / 2), f3(y + max(h, 2) / 2), f3(min(3.0, max(h, 2) * 0.6)), html.escape(name)))
    print('PREVIEW NOT DRAWN %s %.1f x %.1f mm on page %s' % (name, w, h, page.no))


# 주석 모양: Hangul's template values (hp:footNotePr / hp:endNotePr); a section's note_shape changes some of them
NOTE_DEFAULTS = {
    'footnote': dict(format='digit', prefix='', suffix=')', user_char='', superscript=False, line='0.12mm solid #000000',
                     line_length='column', between=1.0, below=2.0, above=3.0, numbering='continuous', start=1,
                     place='each_column', beneath_text=False),
    'endnote': dict(format='digit', prefix='', suffix=')', user_char='', superscript=False, line='0.12mm solid #000000',
                    line_length=51831.0, between=0.0, below=2.0, above=3.0, numbering='continuous', start=1,
                    place='end_of_document', beneath_text=False)}


def note_shape(ctx, end):
    kind = 'endnote' if end else 'footnote'
    return dict(NOTE_DEFAULTS[kind], **((getattr(ctx, 'note_shapes', None) or {}).get(kind) or {}))


def note_mark(ctx, n, end):
    """The number of a note as Hangul writes it: prefix + number in its format (or the user character) + suffix."""
    s = note_shape(ctx, end)
    num = s['user_char'] if s['format'] == 'user_char' and s['user_char'] else fmt_num(n, str(s['format']).upper())
    return '%s%s%s' % (s['prefix'] or '', num, s['suffix'] if s['suffix'] is not None else '')


def note_line_length(v, width):
    """noteLine length -> mm. -1 ("column" in the spec) is drawn 5 cm long by Hangul (footnote_doc page: 50.27 mm);
    a length wider than the column (the endnote template has 14692344 HWPUNIT) takes the column width."""
    if v in (None, 'column', -1, '-1'):
        return 50.0
    return min(float(v), width)


class A:
    """One unit of the flow: a text line or a table row. emit(x, y, page) draws it with its top-left at (x, y)."""
    __slots__ = ('h', 'emit', 'trail', 'keep', 'absorb', 'base', 'para', 'start', 'at', 'notes', 'tbl', 'row', 'cut', 'shut')

    def __init__(self, h, emit=None, trail=0.0, keep=False, absorb=0.0, base=None):
        self.h, self.emit, self.trail, self.keep = h, emit, trail, keep
        self.absorb = absorb            # room under a floating object: the next paragraph's `before` falls into it (P11)
        self.base = base                # a text line: its baseline below the atom top (mm); flow records it in page.lines
        self.para, self.start = None, 0  # a paragraph row: its Para and its first item (the flow wraps rows again, P16)
        self.at = None                  # where the flow wrapped this row for: (page, x, y)
        self.notes = ()                 # the footnotes this row refers to (the flow keeps room for them, rules P15)
        self.tbl, self.row = None, 0    # a table row: its table (page_break, header rows, merged groups) and row index
        self.cut = None                 # a row that may be cut inside its cells: cut(avail, top, plan) -> (first, rest) (P18)
        self.shut = None                # a row whose bottom edge the next row draws: shut(x, y, page) closes it at a page end


class Ctx:
    def __init__(self, spec, pic_dir):
        self.spec, self.dir = spec, pic_dir
        self.pageno = 1
        self.count = {}                  # numbering counters {(list, level): n}
        self.notes = 0                   # footnote number
        self.endnote_n, self.endnotes = 0, []    # endnote number, endnotes waiting for the end of the section/document
        self.note_shapes = {}            # section note_shape {"footnote": {...}, "endnote": {...}}
        self.pages = []

    def image(self, src):
        p = os.path.join(self.dir, src)
        if not os.path.exists(p):
            return None
        ext = os.path.splitext(p)[1].lower().lstrip('.')
        mime = {'jpg': 'jpeg', 'svg': 'svg+xml'}.get(ext, ext)
        return 'data:image/%s;base64,%s' % (mime, base64.b64encode(open(p, 'rb').read()).decode())

    def prefix(self, pp):
        if pp.get('bullet'):
            return pp['bullet']
        n = pp.get('number')
        if n is None:
            return ''
        lst, lv = (n['list'], n['level']) if isinstance(n, dict) else (0, n)
        levels = (self.spec.get('numberings') or [{'levels': []}] * (lst + 1))[lst]['levels']
        for k in [k for k in self.count if k[0] == lst and k[1] > lv]:
            del self.count[k]
        self.count[(lst, lv)] = self.count.get((lst, lv), (levels[lv].get('start', 1) if lv < len(levels) else 1) - 1) + 1
        text = levels[lv].get('text', '^%d.' % (lv + 1)) if lv < len(levels) else '^%d.' % (lv + 1)
        for i in range(lv + 1):
            f = levels[i]['format'] if i < len(levels) else 'DIGIT'
            text = text.replace('^%d' % (i + 1), fmt_num(self.count.get((lst, i), 1), f))
        return text


def items_of(ctx, b, cst, pp, units=None):
    """Paragraph -> list of (char, width pt, style, obj). obj: None, or a dict for an inline object / note.
    units: a list that gets, per item, its content unit (rules P19: one per text character, one per inline object,
    note, page number or equation; -1 for a bullet or number in front)."""
    items = []
    unit = [0]

    def text(t, st, one=False):
        for k, ch in enumerate(t):
            items.append((ch, 0.0 if ch == '\n' else cwidth(ch, st), st, None))
            if units is not None:
                units.append(unit[0])
                if not one:
                    unit[0] += 1
        if one and t:
            unit[0] += 1

    def object_unit(n_items):              # an object or note: one unit for all its items
        if units is not None:
            units.extend([unit[0]] * n_items)
            unit[0] += 1 if n_items else 0
    pre = ctx.prefix(pp)
    if pre:
        text(pre + ' ', cst)
        if pp['indent'] < 0:       # hanging indent: the text starts where the wrapped lines start
            w = sum(i[1] for i in items)
            items[-1] = (' ', max(0.0, -pp['indent'] - (w - items[-1][1])), cst, None)
        if units is not None:
            units[:] = [-1] * len(items)
            unit[0] = 0
    p = b.get('p', '')
    for r in ([p] if isinstance(p, str) else (p or [])):
        if isinstance(r, str):
            text(r, cst)
            continue
        before = len(items)
        st = char_style(cst, r)
        obj = None if ('pic' in r or 'table' in r) else object_of(r, st)
        if 'pic' in r:
            items.append(('￼', r['pic']['w'] / PT, st, dict(kind='pic', **r['pic'])))
        elif obj:                          # drawn by preview/drawers (chart, 글자 겹치기 ...) or a dashed placeholder
            items.append(('￼', obj['w'] / PT, st, obj))
        elif 'table' in r:
            w, atoms = layout_table(ctx, r['table'], st, 1e9, inline=True)
            items.append(('￼', w / PT, st, dict(kind='table', w=w, h=sum(a.h for a in atoms), atoms=atoms)))
        elif 'footnote' in r or 'endnote' in r:
            end = 'endnote' in r and 'footnote' not in r
            if end:
                ctx.endnote_n += 1
            else:
                ctx.notes += 1
            n = ctx.endnote_n if end else ctx.notes
            mark = note_mark(ctx, n, end)              # 주석 모양 (section note_shape, rules P15)
            s2 = dict(st, sup=True)
            on_page = not end and note_shape(ctx, end)['numbering'] == 'on_page'     # numbered again when drawn
            for k, ch in enumerate(mark):
                items.append((ch, cwidth(ch, s2), s2, dict(kind='note', n=n, end=end, mark=mark, on_page=on_page,
                                                           blocks=r.get('footnote') or r.get('endnote')) if k == 0 else None))
        elif 'page_num' in r:
            text(str(ctx.pageno), st, one=True)
            continue
        elif 'equation' in r:
            e = r['equation']
            text(e.get('script', ''), dict(st, italic=True), one=True)
            continue
        elif 'new_page_num' in r:
            ctx.pageno = r['new_page_num'] - 1       # takes effect on the next page
        elif any(k in r for k in ('xml', 'bookmark')):
            pass
        else:
            text(r.get('t', ''), st)
            continue
        object_unit(len(items) - before)
    return items


def hinted_lines(b, items, units, pp, width_mm):
    """Hangul's own line starts (spec `hangul_lines`, rules P19) as item ranges, or None when they do not fit the
    paragraph (a unit past the end, not increasing, or a line over 2.5 times its box: then the preview wraps)."""
    hints = b.get('hangul_lines')
    if hints is None or units is None or not items:
        return None
    starts = [0]
    for u in hints:
        k = next((i for i, x in enumerate(units) if x >= u), None)
        if k is None or k <= starts[-1]:
            return None
        starts.append(k)
    lines = list(zip(starts, starts[1:] + [len(items)]))
    first, other = textfit.widths(pp, width_mm)
    for n, (s, e) in enumerate(lines):
        seg = items[s:e]
        while seg and seg[-1][0] in ' \n':
            seg = seg[:-1]
        if sum(i[1] for i in seg) > 2.5 * (first if n == 0 else other) + 1:
            return None
        if any(it[0] == '\n' for it in items[s:e - 1]):
            return None                    # a forced line break inside a line: the hints are not this text
    return lines


def layout_para(ctx, b, cs, width_mm, no_before=False):
    pp = para_style(b)
    cst = char_style(cs, b)
    units = [] if b.get('hangul_lines') is not None else None
    items = items_of(ctx, b, cst, pp, units)
    forced = hinted_lines(b, items, units, pp, width_mm)
    segs, cur = [], []
    for it in items:                       # a forced line break splits the paragraph for wrapping
        if it[0] == '\n':
            segs.append(cur + [it])
            cur = []
        else:
            cur.append(it)
    segs.append(cur)
    lines, off = [], 0
    for seg in segs:
        _, ls = textfit.wrap_chars(seg, pp, width_mm)
        lines += [(off + s, off + e) for s, e in ls]
        off += len(seg)
    if forced:
        lines = forced
    # items without the '\n' items positions: rebuild a flat list that wrap indexes refer to
    flat = [i for seg in segs for i in seg]
    # no_before: True after a block table (W05), or the mm of room under the objects of the paragraph before (P11)
    before = 0 if no_before is True else max(0.0, pp['before'] * PT - (no_before or 0))
    para = Para(ctx, b, pp, cst, flat, width_mm, before, pp['after'] * PT)
    para.forced = bool(forced)
    atoms = [para.row([para.line(s, e, k == 0, k == len(lines) - 1)], s) for k, (s, e) in enumerate(lines)]
    shapes = para.shapes
    if pp.get('border') or pp.get('fill'):                 # one block: border/fill around the whole paragraph
        atoms = [box_para(atoms, pp, width_mm, ctx)]
        atoms[0].para, para.boxed = para, True             # its objects still wrap the text after it; its own rows stay
    if shapes:
        extra = max([(sh['y'] + sh['h'] - sum(a.h for a in atoms)) for sh in shapes
                     if sh.get('wrap') == 'top_and_bottom' and sh.get('rel') == 'para' and sh.get('h')] or [0])
        if extra > 0:
            atoms.append(A(extra, absorb=extra))
            atoms[-1].para = para               # the flow makes it what is left under the objects (rules P16)
    if pp['page_break_before'] or b.get('page_break'):
        atoms[0].keep = 'break'
    return atoms


class Para:
    """A paragraph laid out in rows, with what it takes to wrap its rows again in other widths (the body flow does it
    beside objects with square wrap, rules P16). origin: the paragraph's top-left on the page, where its anchored
    objects are measured from; pin: the place the flow gave it before it moved any row."""

    def __init__(self, ctx, b, pp, cst, flat, width, before, after):
        self.ctx, self.pp, self.cst, self.flat, self.width = ctx, pp, cst, flat, width
        self.before, self.after = before, after
        self.shapes = b.get('shapes') or []
        self.tabs = pp.get('tabs') or b.get('tabs')
        self.ends = [i + 1 for i, it in enumerate(flat) if it[0] == '\n'] + [len(flat)]     # forced line breaks
        self.zero = dict(pp, left=0, right=0, indent=0)
        self.origin = self.pin = None
        self.boxed = False
        self.forced = False      # lines from Hangul's own layout (P19): a line wider than its box is fitted into it

    def line(self, s, e, first, last, dx=None, avail=None):
        """Line of items s..e: text height, pitch, and where it sits (dx, avail mm from the column left; default: the
        paragraph's indents)."""
        pp, seg = self.pp, self.flat[s:e]
        sizes = [eff_size(i[2], lang(i[0])) for i in seg if i[3] is None and i[0] not in ' \n'] or [self.cst['size']]
        S = max(sizes)
        objh = max([i[3]['h'] / PT for i in seg if i[3] and i[3]['kind'] in OBJECTS] or [0])
        vs = max(S, objh)
        if isinstance(pp['line'], dict):
            kind, v = next(iter(pp['line'].items()))
            pitch = {'fixed': v, 'at_least': max(v, vs), 'between': vs + v}[kind]
        else:
            pitch = vs + S * (pp['line'] - 100) / 100
        if dx is None:
            ind = max(pp['indent'], 0) if first else max(-pp['indent'], 0)
            dx, avail = (pp['left'] + ind) * PT, self.width - (pp['left'] + pp['right'] + ind) * PT
        return dict(seg=seg, vs=vs, base=BASE * vs, pitch=pitch, first=first, last=last, dx=dx, avail=avail,
                    align=pp['align'], origin=pp['left'] * PT, tabs=self.tabs, fit=self.forced)

    def row(self, parts, start):
        """The atom of one row: its lines side by side (more than one when an object splits the row), first item `start`."""
        first, last = start == 0, parts[-1]['last']
        vs, pitch = max(p['vs'] for p in parts), max(p['pitch'] for p in parts)
        for p in parts:                         # one baseline for the row
            p['vs'], p['base'] = vs, BASE * vs
        pre, post = (self.before if first else 0), (self.after if last else 0)

        def emit(x, y, page):
            if first:
                self.origin = self.pin or (x, y)
            o = self.origin or (x, y)
            for sh in (self.shapes if first else ()):
                if sh.get('wrap') == 'behind_text':
                    emit_shape(self.ctx, sh, self.cst, o[0], o[1], page, self.width, self.pp)
            for p in parts:
                emit_line(self.ctx, p, x, y + pre, page)
            for sh in (self.shapes if last else ()):
                if sh.get('wrap') != 'behind_text':
                    emit_shape(self.ctx, sh, self.cst, o[0], o[1], page, self.width, self.pp)
        a = A(pitch * PT + pre + post, emit, trail=max(0.0, pitch - vs) * PT + post, base=pre + BASE * vs * PT)
        a.para, a.start = self, start
        a.notes = tuple(i[3] for p in parts for i in p['seg'] if i[3] and i[3].get('kind') == 'note' and not i[3].get('end'))
        return a

    def fit(self, s, w):
        """End of the line that starts at item s in w mm (a forced line break ends it)."""
        hard = next(e for e in self.ends if e > s) if s < len(self.flat) else s
        return s if hard <= s else s + textfit.wrap_chars(self.flat[s:hard], self.zero, w)[1][0][1]

    def wrap(self, start, free):
        """Rows from item `start` on, wrapped again. free(top, bottom) -> ([(x0, x1)] free mm of the column, or the
        full column; y where the objects that cover the row end, or None), top and bottom from the first row's top. A row
        fills the free ranges inside its indents from left to right; a range narrower than one character is left empty;
        a row with no range moves down below the objects (its `before` falls into that room, as P11). An empty paragraph
        keeps its place."""
        pp, n = self.pp, len(self.flat)
        out, y, s = [], 0.0, start
        while True:
            first = s == 0
            pre = self.before if first else 0
            ind = (max(pp['indent'], 0) if first else max(-pp['indent'], 0)) * PT
            lo, hi = (pp['left'] * PT) + ind, self.width - pp['right'] * PT
            probe = self.line(s, self.fit(s, hi - lo), first, False)
            iv, below = free(y + pre, y + pre + probe['pitch'] * PT)
            # ponytail: the narrowest usable range is one character of the paragraph's size (not measured in Hangul)
            ranges = [(max(a, lo), min(b, hi)) for a, b in iv if min(b, hi) - max(a, lo) >= self.cst['size'] * PT]
            if not ranges and below is not None and s < n:
                gap = max(below - pre - y, 1e-3)
                skip = A(gap, keep='skip')
                skip.para, skip.start = self, s
                out.append(skip)
                y += gap
                continue
            parts, row_start = [], s
            for a, b in ranges or [(lo, hi)]:
                e = self.fit(s, b - a)
                parts.append(self.line(s, e, first, e >= n, a, b - a))
                s = e
                if s >= n or self.flat[s - 1][0] == '\n':
                    break
            out.append(self.row(parts, row_start))
            y += out[-1].h
            if s >= n:
                return out


def shape_at(sh, page, ax, ay, width=0.0, pp=None):
    """Top-left (mm on the page) of a floating object whose anchor paragraph starts at (ax, ay) in a column `width` wide.
    Its `rel` is the vertical reference and, unless `hrel` is given, the horizontal one: paper, page (the body area, as
    rules TB05), para (the paragraph: horizontally its text between the indents), column; x, y are offsets from it, and
    `halign` (left, center, right; outside as right) places it in the horizontal reference first (rules P16)."""
    g = page.g
    rel = sh.get('rel', 'para')
    hrel = sh.get('hrel', rel)
    pl, pr = (pp['left'] * PT, pp['right'] * PT) if pp else (0.0, 0.0)
    span = ((0.0, g['w']) if hrel == 'paper' else (g['x0'], g['x1']) if hrel == 'page' else
            (ax + pl, ax + width - pr) if hrel == 'para' else (ax, ax + width))
    w, ha = sh.get('w', 0), sh.get('halign', 'left')
    x = sh['x'] + ((span[0] + span[1] - w) / 2 if ha == 'center' else span[1] - w if ha in ('right', 'outside') else span[0])
    if rel not in ('paper', 'page'):
        return x, sh['y'] + ay
    top, bottom = (0.0, g['h']) if rel == 'paper' else (g['y0'], g['y1'])     # vpos on the paper / the body area
    va, h = sh.get('vpos', 'top'), sh.get('h', 0)       # not `valign`: in a text box that is the text inside
    return x, sh['y'] + ((top + bottom - h) / 2 if va == 'center' else bottom - h if va in ('bottom', 'outside') else top)


def box_para(atoms, pp, width_mm, ctx=None):
    """Paragraph border/fill: the box runs from the top of the paragraph (spacing before included) minus the top offset
    to its bottom (spacing after included) plus the bottom offset; the offsets take no room in the flow (measured)."""
    off = pp.get('border_offset')
    off = off if isinstance(off, list) else [0, 0, 0, 0]
    h = sum(a.h for a in atoms)

    def emit(x, y, page):
        bd = pp.get('border')
        sides = {k: parse_line(v) for k, v in bd.items()} if isinstance(bd, dict) else {}
        x0, x1 = x + pp['left'] * PT - off[0], x + width_mm - pp['right'] * PT + off[1]
        y0, y1 = y - off[2], y + h + off[3]
        if pp.get('fill'):
            rect(page, x0, y0, x1 - x0, y1 - y0, drawers.paint(ctx, page, pp['fill'], x1 - x0, y1 - y0))
        yy = y
        for a in atoms:
            a.emit(x, yy, page)
            yy += a.h
        for side, (ax, ay, bx, by) in (('top', (x0, y0, x1, y0)), ('bottom', (x0, y1, x1, y1)),
                                       ('left', (x0, y0, x0, y1)), ('right', (x1, y0, x1, y1))):
            if sides.get(side):
                stroke(page, ax, ay, bx, by, sides[side])
    return A(h, emit, atoms[-1].trail, atoms[0].keep)


def renumber(ctx, seg, page):
    """Footnote marks of a line whose numbers start again on every page (numbering on_page, rules P15): numbered after
    the footnotes already on the page."""
    out, k, n = [], 0, len(page.notes)
    while k < len(seg):
        ch, w, st, obj = seg[k]
        if obj and obj.get('kind') == 'note' and obj.get('on_page'):
            n += 1
            mark = note_mark(ctx, n, False)
            o = dict(obj, n=n, mark=mark)
            out += [(c, cwidth(c, st), st, o if j == 0 else None) for j, c in enumerate(mark)]
            k += len(obj['mark'])
            continue
        out.append(seg[k])
        k += 1
    return out


def emit_line(ctx, line, x, y, page):
    seg, base = line['seg'], y + line['base'] * PT
    if any(i[3] and i[3].get('on_page') for i in seg):
        seg = renumber(ctx, seg, page)
    x0 = x + line['dx']
    n = len(seg)
    te = n
    while te > 0 and seg[te - 1][0] in ' \n':
        te -= 1
    natural = sum(i[1] for i in seg[:te]) * PT
    avail = line['avail']
    al = line['align']
    scale = 1.0
    if line.get('fit') and natural > avail > 0 and not any(i[0] == '\t' for i in seg):
        scale, natural = avail / natural, avail      # Hangul put these characters on one line: our widths are too wide
    extra, per_space, per_char = 0.0, 0.0, 0.0
    shift = 0.0
    if al == 'center':
        shift = (avail - natural) / 2
    elif al == 'right':
        shift = avail - natural
    elif al in ('justify', 'distribute', 'divide') and (not line['last'] or al != 'justify') and avail > natural:
        extra = avail - natural
        sp = sum(1 for i in seg[:te] if i[0] == ' ')
        if al == 'justify' and sp:
            per_space = extra / sp
        elif te > 1:
            per_char = extra / (te - 1)
    xs, cx = [], x0 + shift
    stops, leaders = tab_stops(line), []
    for k, (ch, w, st, obj) in enumerate(seg):
        if ch == '\t':
            start = cx
            stop = next((s for s in stops if x + line['origin'] + s[0] > cx + 0.01), None)
            if stop is None:                    # no stop of the paragraph after here: the default stops (P08)
                rel = cx - x
                cx = x + (math.floor((rel + 0.01) / TAB) + 1) * TAB
            else:                               # 사용자 탭 (rules P12): the text after it ends / centres / aligns there
                at = x + line['origin'] + stop[0]
                rest = seg[k + 1:next((m for m in range(k + 1, n) if seg[m][0] == '\t'), n)]
                while rest and rest[-1][0] in ' \n':
                    rest = rest[:-1]
                if stop[1] == 'decimal':
                    rest = rest[:next((m for m, it in enumerate(rest) if it[0] == '.'), len(rest))]
                width = sum(it[1] for it in rest) * PT * {'right': 1, 'decimal': 1, 'center': 0.5}.get(stop[1], 0)
                cx = max(cx, at - width)
                if stop[2] not in (None, 'none', 'NONE'):
                    leaders.append((start, cx, stop[2], st))
            xs.append(cx)
            continue
        xs.append(cx)
        cx += w * PT * scale
        if k < te - 1:
            cx += per_char + (per_space if ch == ' ' else 0)
        if obj and obj.get('kind') == 'note':
            # endnotes go after the text (flow); a footnote keeps its column (page.col: set by the flow) for its place
            (ctx.endnotes if obj.get('end') else page.notes).append(dict(obj, col=getattr(page, 'col', 0)))
    # objects and text groups
    i = 0
    while i < n:
        ch, w, st, obj = seg[i]
        if obj and obj['kind'] in OBJECTS:
            oy = y + (0 if obj['h'] / PT >= line['vs'] - 1e-6 else line['base'] * PT - obj['h'])
            if obj.get('base') is not None:     # a drawer that knows its baseline
                oy = y + line['base'] * PT - obj['base']
            if obj['kind'] == 'pic':
                emit_pic(ctx, obj, xs[i], oy, page)
            elif obj['kind'] in ('drawn', 'missing'):
                emit_object(page, obj, xs[i], oy)
            else:
                yy = oy
                for a in obj['atoms']:
                    a.emit(xs[i], yy, page)
                    yy += a.h
            i += 1
            continue
        j = i
        while j < n and seg[j][2] is st and not (seg[j][3] and seg[j][3]['kind'] in OBJECTS):
            j += 1
        emit_run(page, seg[i:j], xs[i:j], base, line, st, cx if j >= n else xs[j])
        i = j
    for a, b, kind, st in leaders:              # tab leaders (채울 모양) on the baseline, a little in from both ends
        if b - a > 1.0:
            stroke(page, a + 0.4, base - 0.05 * st['size'] * PT, b - 0.4, base - 0.05 * st['size'] * PT,
                   (0.3 if kind.lower() in ('dot', 'circle') else 0.12, kind.lower(), st['color']), ext=False)


def tab_stops(line):
    """The paragraph's tab stops (spec `tabs`: a list of {pos mm, type, leader}, or {"stops": [...], "auto_right": true})
    -> sorted [(pos mm from the text left, type, leader)]. auto_right adds a right stop at the end of the line."""
    t = line.get('tabs')
    if not t:
        return []
    stops = t.get('stops', []) if isinstance(t, dict) else t
    out = sorted((float(s.get('pos', 0)), str(s.get('type', 'left')).lower(), s.get('leader') or 'none')
                 for s in stops if isinstance(s, dict))
    if isinstance(t, dict) and t.get('auto_right'):
        out.append((line['dx'] - line['origin'] + line['avail'], 'right', 'none'))
    return out


def emit_run(page, seg, xs, base, line, st, xend):
    lg = lang(seg[0][0])
    S = eff_size(st, 0 if lg == 5 else lg)
    # per-character size and baseline shift are the same inside one style
    top = base - BASE * line['vs'] * PT
    shade = st.get('hl') or (st.get('shade') if st.get('shade') not in (None, 'none') else None)
    fill = st.get('char_fill')
    if fill not in (None, 'none') and not shade:     # 글자 배경 (char border fill)
        rect(page, xs[0], top, xend - xs[0], line['vs'] * PT, fill)
    if shade:
        rect(page, xs[0], top, xend - xs[0], line['vs'] * PT, shade)
    cb = st.get('char_border')
    if cb:                                  # 글자 테두리: lines around the run, one line high (reader: {side: line})
        x0, x1, y0, y1 = xs[0], xend, top, top + line['vs'] * PT
        edge = {'left': (x0, y0, x0, y1), 'right': (x1, y0, x1, y1), 'top': (x0, y0, x1, y0), 'bottom': (x0, y1, x1, y1)}
        for side, v in (cb if isinstance(cb, dict) else dict.fromkeys(edge, cb)).items():
            ln = parse_line(v) if isinstance(v, str) else None
            if ln and side in edge:
                stroke(page, *edge[side], ln, ext=False)
    dy = 0.0
    if st.get('sup'):
        dy = -0.32 * st['size'] * PT
    elif st.get('sub'):
        dy = 0.12 * st['size'] * PT
    off = sv(st['offset'], lg)
    if off:
        dy -= off / 100 * st['size'] * PT
    keep = [(c[0], x) for c, x in zip(seg, xs) if c[0] not in ' \t\n￼']
    if keep:
        # each character may use another font (Latin, symbol): group by face
        k = 0
        while k < len(keep):
            lgk = lang(keep[k][0])
            e = k
            while e < len(keep) and lang(keep[e][0]) == lgk:
                e += 1
            sz = eff_size(st, lgk) * PT
            page.svg.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" stroke="%s" stroke-width="%s"%s%s>%s</text>' % (
                ' '.join(f3(x) for _, x in keep[k:e]), f3(base + dy), html.escape(fam(face(st, lgk)), quote=True),
                f3(sz), st['color'], st['color'], f3(TEXT_STROKE), ' font-weight="bold"' if st['bold'] else '', ' font-style="italic"' if st['italic'] else '',
                html.escape(''.join(c for c, _ in keep[k:e]), quote=False)))
            k = e
    ul, so = st.get('underline'), st.get('strike')
    if ul:
        col = ul if isinstance(ul, str) else (ul.get('color') if isinstance(ul, dict) else st['color'])
        pos = ul.get('pos', 'bottom') if isinstance(ul, dict) else 'bottom'
        yy = base + 0.13 * S * PT if pos == 'bottom' else (base - 0.85 * S * PT if pos == 'top' else base - 0.35 * S * PT)
        stroke(page, xs[0], yy, xend, yy, (max(0.04, S * PT * 0.05), 'solid', col), ext=False)
    if so:
        col = so.get('color') if isinstance(so, dict) else st['color']
        yy = base - 0.3 * S * PT
        stroke(page, xs[0], yy, xend, yy, (max(0.04, S * PT * 0.05), 'solid', col), ext=False)


def emit_pic(ctx, p, x, y, page):
    data = ctx.image(p['src'])
    if data:
        page.svg.append('<image x="%s" y="%s" width="%s" height="%s" preserveAspectRatio="none" href="%s"/>' % (
            f3(x), f3(y), f3(p['w']), f3(p['h']), data))
    else:
        placeholder(page, x, y, p['w'], p['h'], 'picture %s' % os.path.basename(str(p.get('src', ''))))


def layout_blocks(ctx, blocks, cs, width_mm):
    """Public (page layers and drawers may call it): spec blocks -> atoms (a.h mm, a.emit(x, y, page)) for a column
    `width_mm` wide, with the char style `cs` (dict(core.read.DEF_CHAR) or the style around)."""
    atoms, after_table, carry, pend = [], False, [], []
    for b in blocks:
        if carry and isinstance(b, dict) and 'p' in b:       # the text of their paragraph: they are anchored to it
            b, carry = dict(b, shapes=list(b.get('shapes') or []) + carry), []
        elif carry:
            atoms += layout_para(ctx, {'p': '', 'shapes': carry}, cs, width_mm, after_table)
            carry = []
        if isinstance(b, dict) and b.get('same_para') and flow_table(b, width_mm) is not None:
            pend.append(b)                      # a table that flows (Hangul cuts it at page ends): under the text of its paragraph
            continue
        got = floating(ctx, b, cs, width_mm) if isinstance(b, dict) and b.get('same_para') else None
        if got:                                 # a floating object in the same paragraph as the next block (rules S26)
            carry += got
            continue
        new = layout_block(ctx, b, cs, width_mm, after_table)
        atoms += new
        after_table = isinstance(b, dict) and 'table' in b       # Hangul drops the 'before' of the paragraph after a table (rules W05)
        if not after_table and new and new[-1].absorb:
            after_table = new[-1].absorb                          # the next 'before' falls into the room under objects (P11)
        if pend and isinstance(b, dict) and 'p' in b:
            for tb in pend:                     # its offset from the top of the paragraph counts from there, down to the text's end
                atoms += layout_block(ctx, flow_table(tb, width_mm, sum(a.h for a in new)), cs, width_mm, False)
            pend, after_table = [], True
    for tb in pend:
        atoms += layout_block(ctx, flow_table(tb, width_mm), cs, width_mm, after_table)
    if carry:
        atoms += layout_para(ctx, {'p': '', 'shapes': carry}, cs, width_mm, after_table)
    return atoms


def flow_table(b, w, drop=0.0):
    """A table block anchored to its paragraph that flows with the text (hwp5 `pos.flow`, top_and_bottom wrap) is an ordinary table
    that Hangul cuts at page ends: its offsets become margins (the y offset less `drop`, the height of the text above it) and
    halign its alignment (kps-ai: a table of contents over two pages, a heading with its table). The block with that done, or
    None when the table floats as an object (table/draw.py)."""
    t = b.get('table') if isinstance(b, dict) else None
    pos = t.get('pos') if isinstance(t, dict) else None
    if not (pos and pos.get('flow') and pos.get('vrel', pos.get('rel')) == 'para' and pos.get('hrel', pos.get('rel')) in ('column', 'para')
            and t.get('wrap', 'top_and_bottom') == 'top_and_bottom' and pos.get('valign', 'top') == 'top'
            and -5 <= pos.get('x', 0) <= w / 2 and pos.get('y', 0) >= -5):
        return None                 # a table put aside (negative offset, far to the right) is a floating object
    m = list(t.get('margin') or [1.0, 1.0, 1.0, 1.0])
    off = max(0.0, pos.get('y', 0) - drop)
    t = dict({k: v for k, v in t.items() if k != 'pos'}, margin=[max(0.0, m[0] + pos.get('x', 0)), m[1], m[2] + off, m[3]],
             align=pos.get('halign', 'left'), margin_cont=t.get('margin_cont', m[2]))
    return dict({k: v for k, v in b.items() if k not in ('same_para', 'page_break')}, table=t)     # the text starts the page, not the table


def floating_pic(p):
    """A floating picture (`inline` false) as a shape of its paragraph."""
    pos = p['pos']
    sh = dict(type='pic', pic=p, x=pos['x'], y=pos['y'], rel=pos['rel'], w=p['w'], h=p['h'],
              wrap=p.get('wrap', 'top_and_bottom'), side=p.get('side', 'both_sides'))
    for k, v in (('hrel', pos.get('hrel', p.get('hrel'))), ('halign', pos.get('halign', p.get('halign'))),
                 ('vpos', pos.get('valign', p.get('valign')))):      # a picture's valign is its place (objects2 reader)
        if v:
            sh[k] = v
    return sh


def object_key(b):
    """The key of the object a block holds (drawn by a drawer, or of an unknown type with w and h), or None."""
    return None if 'p' in b else (drawers.key_of(b) or next(
        (x for x, v in b.items() if isinstance(v, dict) and 'w' in v and 'h' in v and x not in KNOWN), None))


def floating_object(b, k, cs):
    """A floating object block (chart, an upright picture of 세로쓰기 ...) as a shape of its paragraph."""
    obj = object_of({k: b[k]}, char_style(cs, b))
    pos = b[k].get('pos') or {}
    return dict(type='object', obj=obj, x=pos.get('x', 0), y=pos.get('y', 0), rel=pos.get('rel', 'para'),
                w=obj['w'], h=obj['h'], wrap=b[k].get('wrap', 'square'), side=b[k].get('side', 'both_sides'))


def floating(ctx, b, cs, w):
    """The shapes of a block that floats (a picture with `inline` false, a table with `pos`, an object with `inline`
    false), or None."""
    if 'pic' in b and 'p' not in b and b['pic'].get('inline', True) is False:
        return [floating_pic(b['pic'])]
    k = object_key(b)
    if k and isinstance(b[k], dict) and b[k].get('inline', True) is False:
        return [floating_object(b, k, cs)]
    if 'table' in b and b['table'].get('pos'):
        got = []

        def grab(ctx, blk, cst, width, no_before=False):          # the table wrapper hands its shape to layout_para
            got.extend(blk.get('shapes') or [])
            return []
        drawers.table_wrap(ctx, b, char_style(cs, b), w, layout_table, grab)
        return got or None
    return None


def layout_block(ctx, b, cs, w, after_table=False):
    if isinstance(b, str):
        b = {'p': b}
    if 'gap' in b:
        return [A(b['gap'] * PT)]
    if 'table' in b:
        pp = para_style(b)
        cst = char_style(cs, b)
        atoms = drawers.table_wrap(ctx, b, cst, w, layout_table, layout_para)      # captions, tables with pos (drawers/)
        if atoms is None:
            tw, atoms = layout_table(ctx, b['table'], cst, w, b['table'].get('align', 'left'))
        if atoms:
            atoms[0].keep = 'break' if (b.get('page_break') or pp['page_break_before']) else atoms[0].keep
            T = next((a.tbl for a in atoms if a.tbl is not None), None)
            if T is not None:
                T['keep_next'] = bool(pp.get('keep_next'))  # the table goes on with the next paragraph (pagefit PF25)
                if T['pb'] == 'none' and not T['hold'] and b['table'].get('inline') is not True and 'defer' not in T:
                    # kept whole without hold: one that does not fit waits for the next page, the text goes on here (P18, kh_none)
                    T['defer'] = sum(a.h for a in layout_para(ctx, {'p': ''}, cst, w))
        return atoms
    if 'pic' in b and 'p' not in b:
        p = b['pic']
        cst = char_style(cs, b)
        if p.get('inline', True):
            return layout_para(ctx, dict(b, p=[{'pic': p}]), cs, w, after_table)
        return layout_para(ctx, {'p': '', 'shapes': [floating_pic(p)]}, cst, w, after_table)
    k = object_key(b)
    if k and b[k].get('inline', True) is False:      # a floating object (chart ...): placed like a floating picture
        return layout_para(ctx, {'p': '', 'shapes': [floating_object(b, k, cs)]}, char_style(cs, b), w, after_table)
    if k or ('p' not in b and isinstance(b.get('xml'), str)):    # an object in its own paragraph, on the line
        run = {k: b[k]} if k else {'xml': b['xml']}
        return layout_para(ctx, dict({x: v for x, v in b.items() if x not in (k, 'xml')}, p=[run]), cs, w, after_table)
    return layout_para(ctx, b, cs, w, after_table)


def layout_table(ctx, t, cs, avail, align='left', inline=False):
    cols = t['cols']
    W = sum(cols)
    cx = [0.0]
    for c in cols:
        cx.append(cx[-1] + c)
    margin = t.get('margin') or ([0, 0, 0, 0] if inline else [1.0, 1.0, 1.0, 1.0])
    pad_t = t.get('pad') or [1.8, 1.8, 0.5, 0.5]
    common = parse_line(t.get('border', 'none'))
    # place cells on the grid (like HTML)
    cells, used = [], set()
    nrow = len(t['rows'])
    for r, row in enumerate(t['rows']):
        if isinstance(row, dict):
            row = row['cells']
        c = 0
        for cell in row:
            while (r, c) in used:
                c += 1
            cd = cell if isinstance(cell, dict) else {'p': cell}
            rs, cs_ = cd.get('rs', 1), cd.get('cs', 1)
            for dr in range(rs):
                for dc in range(cs_):
                    used.add((r + dr, c + dc))
            cells.append(dict(r=r, c=c, rs=rs, cs=cs_, d=cd))
            c += cs_
    heights = list(t.get('heights') or []) + [0.0] * nrow
    heights = heights[:nrow]
    given = heights[:]                                  # the rows' own heights (cellSz): a cut row's first part keeps it
    H, V = {}, {}

    def edge(store, key, ln):
        if key not in store or strength(ln) > strength(store[key]):
            store[key] = ln
    for ce in cells:
        d, r, c = ce['d'], ce['r'], ce['c']
        bd = d.get('border')
        sides = {k: common for k in ('top', 'bottom', 'left', 'right')}
        if isinstance(bd, dict):
            sides.update({k: parse_line(v) for k, v in bd.items()})
        elif isinstance(bd, str):
            sides = {k: parse_line(bd) for k in sides}
        ce['sides'] = sides
        for dc in range(ce['cs']):
            edge(H, (r, c + dc), sides['top'])
            edge(H, (r + ce['rs'], c + dc), sides['bottom'])
        for dr in range(ce['rs']):
            edge(V, (r + dr, c), sides['left'])
            edge(V, (r + dr, c + ce['cs']), sides['right'])
        # content
        cs2 = char_style(cs, d)
        pad = d.get('pad') or pad_t
        inner = cx[c + ce['cs']] - cx[c] - pad[0] - pad[1]
        if 'blocks' in d:
            blocks = d['blocks']
        else:
            base = {k: v for k, v in d.items() if (k in rd.CHAR_KEYS or k in rd.PARA_KEYS) and k not in ('border', 'fill')}
            # the hwp5 reader (`hangul_lines`): one paragraph, its '\n' are line breaks, not paragraph ends
            blocks = [dict(base, p=s) for s in str(d.get('p', '')).split('\n')] if isinstance(d.get('p', ''), str) \
                and 'hangul_lines' not in d else [dict(base, p=d['p'])]
        at = layout_blocks(ctx, blocks, cs2, inner)
        ce['atoms'], ce['pad'] = at, pad
        ce['ch'] = sum(a.h for a in at) - (at[-1].trail if at else 0) + pad[2] + pad[3]
    for ce in cells:
        if ce['rs'] == 1:
            heights[ce['r']] = max(heights[ce['r']], ce['ch'])
    for ce in cells:
        if ce['rs'] > 1:
            lack = ce['ch'] - sum(heights[ce['r']:ce['r'] + ce['rs']])
            if lack > 0:
                heights[ce['r'] + ce['rs'] - 1] += lack
    ry = [0.0]
    for h in heights:
        ry.append(ry[-1] + h)
    off = margin[0]
    if not inline:
        if align == 'center':
            off = (avail - W) / 2
        elif align == 'right':
            off = avail - W - margin[1]
    def hline(page, key, tx, yy):
        """The horizontal edge above row `key` (key nrow: the table bottom) at yy."""
        c = 0
        while c < len(cols):
            ln = H.get((key, c))
            e = c + 1
            while e < len(cols) and H.get((key, e)) == ln:
                e += 1
            if ln:
                stroke(page, tx + cx[c], yy, tx + cx[e], yy, ln)
            c = e

    def paint(x, y, page, r, mine, top_m, rh, keys, body):
        """Row r at x, y, rh mm high, or a part of it (body: each cell's atoms on the part, rules P18); keys: its
        horizontal edges as (edge row, mm below the row top)."""
        tx, ty = x + off, y + top_m
        for ce in mine:
            fill = ce['d'].get('fill')
            if fill:
                fw, fh = cx[ce['c'] + ce['cs']] - cx[ce['c']], ry[r + ce['rs']] - ry[r] if body is None else rh
                rect(page, tx + cx[ce['c']], ty, fw, fh, drawers.paint(ctx, page, fill, fw, fh))
        for key, dy in keys:
            hline(page, key, tx, ty + dy)
        for c in range(len(cols) + 1):
            ln = V.get((r, c))
            if ln:
                stroke(page, tx + cx[c], ty, tx + cx[c], ty + rh, ln)
        for ce in mine:
            d = ce['d']
            x0, y0 = tx + cx[ce['c']], ty
            w, h = cx[ce['c'] + ce['cs']] - cx[ce['c']], ry[r + ce['rs']] - ry[r] if body is None else rh
            dl = parse_line(d.get('diag_line', 'none'))
            if d.get('diag') and dl:
                if d['diag'] in ('slash', 'both'):
                    stroke(page, x0, y0 + h, x0 + w, y0, dl, ext=False)
                if d['diag'] in ('back', 'both'):
                    stroke(page, x0, y0, x0 + w, y0 + h, dl, ext=False)
            pad = ce['pad']
            ats = ce['atoms'] if body is None else body[id(ce)]
            va = d.get('valign', 'center')
            yy = y0 + pad[2] + (0 if va == 'top' else (h - pad[2] - pad[3] - inner(ats)) / (2 if va == 'center' else 1))
            for a in ats:
                if a.emit:
                    a.emit(x0 + pad[0], yy, page)
                yy += a.h

    def inner(ats):
        return sum(a.h for a in ats) - (ats[-1].trail if ats else 0)

    def row(r, top_m, bot_m, body=None):
        """The atom of row r, or of the rest of it after a cut at a page end (body: each cell's atoms left, P18)."""
        mine = [ce for ce in cells if ce['r'] == r]
        rh = heights[r] if body is None else max(inner(body[id(ce)]) + ce['pad'][2] + ce['pad'][3] for ce in mine)
        keys = [(r, 0.0)] + ([(nrow, rh)] if r == nrow - 1 else [])
        a = A(rh + top_m + bot_m, lambda x, y, page: paint(x, y, page, r, mine, top_m, rh, keys, body))
        a.tbl, a.row = T, uid[r]
        if r < nrow - 1:                                # the next row draws the edge below; at a page end the flow does
            a.shut = lambda x, y, page: hline(page, r + 1, x + off, y + a.h)
        if T['pb'] == 'cell' and r >= hdr_rows and r not in merged and mine:
            a.cut = lambda avail, top, plan: cut(r, mine, top_m, bot_m, body, avail, top, plan)
        return a

    def cut(r, mine, top_m, bot_m, body, avail, top, plan):
        """Cut row r at a page end avail mm below its top (rules P18) -> (first part, rest): the first part has the lines
        of each cell that fit (plan: how many of a cell's atoms go, with the keep rules of P17); None when no cell has a
        line there or every cell fits whole."""
        given_h = [min(given[r], avail - top_m)] if body is None else []      # kc_w1: one line, the row's height kept
        body = body or {id(ce): ce['atoms'] for ce in mine}
        n = {id(ce): plan(body[id(ce)], avail - top_m - ce['pad'][2] - ce['pad'][3], top) for ce in mine}
        if not any(n.values()) or all(n[k] == len(v) for k, v in body.items()):
            return None
        one = {k: v[:n[k]] for k, v in body.items()}
        ph = max([inner(one[id(ce)]) + ce['pad'][2] + ce['pad'][3] for ce in mine] + given_h)
        p = A(top_m + ph, lambda x, y, page: paint(x, y, page, r, mine, top_m, ph, [(r, 0.0)], one))
        p.tbl, p.row = T, uid[r]
        p.shut = lambda x, y, page: hline(page, r + 1, x + off, y + p.h)
        return p, row(r, 0.0, bot_m, {k: v[n[k]:] for k, v in body.items()})

    # ---- rows tied by row spans (rs): in a `page_break` cell table Hangul cuts them like any rows (rules P18), so such a group
    # of rows is one atom whose cut may fall between its rows or inside one; a cell that crosses the cut goes on in the rest
    def hline_all(page, key, tx, yy, side):
        """The edge at row boundary `key`: the table edges H, and where a cell crosses it (no edge there) the `side` ('top' /
        'bottom') line of that cell, as Hangul draws a cell cut at a page end."""
        lns = []
        for c in range(len(cols)):
            if (key, c) in H:
                lns.append(H[(key, c)])
                continue
            ce = next((e for e in cells if e['c'] <= c < e['c'] + e['cs'] and
                       e['r'] <= (key if side == 'top' else key - 1) < e['r'] + e['rs']), None)
            lns.append(ce['sides'][side] if ce else None)
        c = 0
        while c < len(cols):
            e = c + 1
            while e < len(cols) and lns[e] == lns[c]:
                e += 1
            if lns[c]:
                stroke(page, tx + cx[c], yy, tx + cx[e], yy, lns[c])
            c = e

    def rowh(R, body, rest0, cap=None):
        """Heights of the rows R (consecutive) of a group, each cell's atoms from `body` (id -> atoms, else all): the rows' own
        heights (a rest part has none), the cells of one row, then a cell over rows that end in R takes what it lacks in its
        last row (the preview's natural heights when R is the whole group). cap: the room the last row's own height may take."""
        hs = [0.0 if (k == 0 and rest0) else given[r] for k, r in enumerate(R)]
        if cap is not None:
            hs[-1] = min(hs[-1], cap)
        for ce in cells:
            if ce['rs'] == 1 and R[0] <= ce['r'] <= R[-1]:
                k = ce['r'] - R[0]
                hs[k] = max(hs[k], inner(body.get(id(ce), ce['atoms'])) + ce['pad'][2] + ce['pad'][3])
        for ce in cells:
            if ce['rs'] > 1 and R[0] < ce['r'] + ce['rs'] <= R[-1] + 1 and ce['r'] <= R[-1]:
                a, b = max(ce['r'], R[0]) - R[0], ce['r'] + ce['rs'] - R[0]
                ats = body.get(id(ce), ce['atoms'])
                lack = (inner(ats) + ce['pad'][2] + ce['pad'][3] if ats else 0.0) - sum(hs[a:b])
                if lack > 0:
                    hs[b - 1] += lack
        return hs

    def upaint(x, y, page, R, hs, body, cont, top_m):
        tx, ty = x + off, y + top_m
        yk = [ty]
        for h in hs:
            yk.append(yk[-1] + h)
        span = []
        for ce in cells:
            t0, t1 = max(ce['r'], R[0]) - R[0], min(ce['r'] + ce['rs'], R[-1] + 1) - R[0]
            if t0 < t1:
                span.append((ce, t0, t1))
        for ce, t0, t1 in span:
            fill = ce['d'].get('fill')
            if fill:
                fw, fh = cx[ce['c'] + ce['cs']] - cx[ce['c']], yk[t1] - yk[t0]
                rect(page, tx + cx[ce['c']], yk[t0], fw, fh, drawers.paint(ctx, page, fill, fw, fh))
        for k, r in enumerate(R):
            if k == 0 and cont:
                hline_all(page, r, tx, yk[0], 'top')
            else:
                hline(page, r, tx, yk[k])
        if R[-1] == nrow - 1:
            hline(page, nrow, tx, yk[-1])
        for k, r in enumerate(R):
            for c in range(len(cols) + 1):
                ln = V.get((r, c))
                if ln:
                    stroke(page, tx + cx[c], yk[k], tx + cx[c], yk[k + 1], ln)
        for ce, t0, t1 in span:
            d, pad = ce['d'], ce['pad']
            x0, y0 = tx + cx[ce['c']], yk[t0]
            w, h = cx[ce['c'] + ce['cs']] - cx[ce['c']], yk[t1] - yk[t0]
            dl = parse_line(d.get('diag_line', 'none'))
            if d.get('diag') and dl:
                if d['diag'] in ('slash', 'both'):
                    stroke(page, x0, y0 + h, x0 + w, y0, dl, ext=False)
                if d['diag'] in ('back', 'both'):
                    stroke(page, x0, y0, x0 + w, y0 + h, dl, ext=False)
            ats = body.get(id(ce), ce['atoms'])
            va = d.get('valign', 'center')
            yy = y0 + pad[2] + (0 if va == 'top' else (h - pad[2] - pad[3] - inner(ats)) / (2 if va == 'center' else 1))
            for a in ats:
                if a.emit:
                    a.emit(x0 + pad[0], yy, page)
                yy += a.h

    def unit(R, body, cont, rest0, top_m, bot_m, last=None, cap=None):
        """The atom of the rows R of a group (body: the atoms left of the cells a cut left; cont: cells that come from above
        R; rest0: the first row is the rest of a cut row; last: the height of the last row when a cut stretches it)."""
        hs = rowh(R, body, rest0, cap)
        if last is not None:
            hs[-1] = last
        a = A(top_m + sum(hs) + bot_m, lambda x, y, page: upaint(x, y, page, R, hs, body, cont, top_m))
        a.tbl, a.row = T, uid[R[0]]
        a.trail = 0.0 if R[-1] == nrow - 1 else -margin[3]      # a part of the table keeps the table's outer margin below it at a
        #                                                         page end (tallcell_table_k32: need() = h + margin; P18)
        if R[-1] < nrow - 1:
            a.shut = lambda x, y, page: hline_all(page, R[-1] + 1, x + off, y + a.h, 'bottom')
        if T['pb'] == 'cell' and R[0] >= hdr_rows:
            a.cut = lambda avail, top, plan: ucut(R, body, cont, rest0, top_m, bot_m, avail, top, plan)
        return a

    def ucut(R, body, cont, rest0, top_m, bot_m, avail, top, plan):
        """Cut the group's rows R at a page end `avail` mm below their top -> (first part, rest), or None (rules P18). The
        table keeps its outer margin below at the page end (end = avail - margin). The row that does not fit is cut inside
        its cells when a cell of its own has a line that fits (the cells that cross it too); else the rows before it are the
        first part, stretched to `end` (a cell over several rows crosses the cut)."""
        end = avail - margin[3]
        hs = rowh(R, body, rest0)
        ys = [top_m]
        for h in hs:
            ys.append(ys[-1] + h)
        k = next((i for i in range(len(R)) if ys[i + 1] > end + 0.05), None)
        if k is None:
            return None
        act = []
        for ce in cells:
            t0, t1 = max(ce['r'], R[0]) - R[0], min(ce['r'] + ce['rs'], R[-1] + 1) - R[0]
            if t0 < t1:
                act.append((ce, t0, t1))
        ats = {id(ce): body.get(id(ce), ce['atoms']) for ce, _, _ in act}
        n = {}
        for ce, t0, t1 in act:
            if t1 <= k:
                n[id(ce)] = len(ats[id(ce)])                # above the cut: whole
            elif t0 > k:
                n[id(ce)] = 0                               # starts after row k: whole in the rest
            else:
                n[id(ce)] = plan(ats[id(ce)], end - ys[t0] - ce['pad'][2] - ce['pad'][3] - 0.12, top and t0 == 0)   # 0.12: the bottom border
        here = [(ce, t0, t1) for ce, t0, t1 in act if t0 <= k < t1]
        inside = any(n[id(ce)] > 0 for ce, t0, t1 in here if t0 == k)
        whole = all(n[id(ce)] == len(ats[id(ce)]) for ce, t0, t1 in here)
        if k == 0 and not inside:
            return None
        # 'in': row k is cut inside its cells; 'fit': row k stays whole, its own height cut short to the page end (Hangul
        # keeps a row whose text fits, plain_cell_k28); 'before': the rows before row k are the first part
        mode = 'before' if not inside else 'in' if not whole else 'fit'
        one, left = {}, {}
        for ce, t0, t1 in here:
            if mode != 'before' or t0 < k:
                one[id(ce)], left[id(ce)] = ats[id(ce)][:n[id(ce)]], ats[id(ce)][n[id(ce)]:]
        Rf = R[:k] if mode == 'before' else R[:k + 1]
        Rr = R[k + 1:] if mode == 'fit' else R[k:]
        fb, nb = {**body, **one}, {**body, **left}
        crossing = bool(Rr) and any(ce['r'] < Rr[0] < ce['r'] + ce['rs'] for ce, t0, t1 in here)
        if mode == 'before':
            first = unit(Rf, fb, cont, rest0, top_m, 0.0, last=end - ys[k - 1])
        else:
            first = unit(Rf, fb, cont, rest0, top_m, 0.0, last=end - ys[k] if mode == 'fit' and crossing else None, cap=end - ys[k])
        first.cut, first.trail = None, 0.0                  # it ends at the page end: nothing more has to fit
        if not Rr:
            return first, A(0.0)
        more = {id(ce) for ce in cells if ce['r'] < Rr[0] < ce['r'] + ce['rs']}
        return first, unit(Rr, nb, more, mode == 'in', 0.0, bot_m)

    # for the page flow (rules P17, P18, pagefit PF02): how the table may be cut; the header rows come again on the next page,
    # under the table's outer margin (mt)
    merged = {r for ce in cells if ce['rs'] > 1 for r in range(ce['r'], ce['r'] + ce['rs'])}
    # a table that holds its paragraph on its page (hold, holdAnchorAndSO) or sits as a character (inline) is not cut (P18)
    pb = 'none' if t.get('hold') or t.get('inline') is True else str(t.get('page_break', 'cell')).lower()
    hdr_rows = int(t.get('header_rows', 0) or 0) if t.get('repeat_header', True) else 0
    groups, r0 = [], 0
    while r0 < nrow:
        e, i = r0 + 1, r0
        while i < e:
            e = max([e] + [ce['r'] + ce['rs'] for ce in cells if ce['r'] == i and ce['rs'] > 1])
            i += 1
        groups.append((r0, e))
        r0 = e
    packed = pb == 'cell' and any(e - s > 1 for s, e in groups)     # a group of rows is one atom (it may be cut inside)
    uid = {r: (i if packed else r) for i, (s, e) in enumerate(groups) for r in range(s, e)}
    # the gap above a table that goes on at the top of a page or column (mc): the outer margin it has without the offset that
    # Hangul puts it down from its paragraph (the hwp5 reader keeps it as `margin_cont`); delegation pages 8-31: 0.5 mm, not 4.5
    mc = float(t['margin_cont']) if t.get('margin_cont') is not None else min(margin[2], 1.0)
    T = dict(pb=pb, hold=bool(t.get('hold')), rep=set(), mt=margin[2], mc=mc,
             hdr=sum(1 for s, e in groups if s < hdr_rows) if packed else hdr_rows,
             bad=set() if packed else {r for ce in cells if ce['rs'] > 1 for r in range(ce['r'] + 1, ce['r'] + ce['rs'])})
    if packed:
        T['atoms'] = [unit(list(range(s, e)), {}, (), False, margin[2] if s == 0 else 0, margin[3] if e == nrow else 0)
                      if e - s > 1 else row(s, margin[2] if s == 0 else 0, margin[3] if s == nrow - 1 else 0)
                      for s, e in groups]
        for a, (s, e) in zip(T['atoms'], groups):
            a.row = uid[s]
    else:
        T['atoms'] = [row(r, margin[2] if r == 0 else 0, margin[3] if r == nrow - 1 else 0) for r in range(nrow)]
        T['gneed'] = {s0: sum(a.h for a in T['atoms'][s0:e0]) + (margin[3] if e0 < nrow else 0.0)
                      for s0, e0 in groups if e0 - s0 > 1}  # the rows of a group and the table's outer margin below (table_plan)
    return W + margin[0] + margin[1], T['atoms']


def emit_shape(ctx, sh, cs, ax, ay, page, width=0.0, pp=None):
    x, y = shape_at(sh, page, ax, ay, width, pp)
    ox, oy = x - sh['x'], y - sh['y']
    t = sh['type']
    ln = parse_line(sh.get('line', 'none'))
    if t == 'pic':
        emit_pic(ctx, sh['pic'], x, y, page)
        return
    if t == 'object':
        emit_object(page, sh['obj'], x, y)
        return
    if t == 'line':
        x2, y2 = ox + sh['x2'], oy + sh['y2']
        if ln:
            stroke(page, x, y, x2, y2, ln, ext=False)
            arrow = sh.get('arrow')
            ang = math.atan2(y2 - y, x2 - x)
            for tip, a, on in ((( x2, y2), ang, arrow in ('end', 'both')), ((x, y), ang + math.pi, arrow in ('start', 'both'))):
                if on:
                    s = max(ln[0] * 4, 2.0)
                    pts = [tip, (tip[0] - s * math.cos(a - 0.4), tip[1] - s * math.sin(a - 0.4)),
                           (tip[0] - s * math.cos(a + 0.4), tip[1] - s * math.sin(a + 0.4))]
                    page.svg.append('<polygon points="%s" fill="%s"/>' % (' '.join('%s,%s' % (f3(p), f3(q)) for p, q in pts), ln[2]))
        return
    w, h = sh['w'], sh['h']
    fill = drawers.paint(ctx, page, sh.get('fill'), w, h)
    if t == 'ellipse':
        page.svg.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s"%s/>' % (
            f3(x + w / 2), f3(y + h / 2), f3(w / 2), f3(h / 2), fill or 'none',
            ' stroke="%s" stroke-width="%s"' % (ln[2], f3(thin(ln[0]))) if ln else ''))
    else:
        rect(page, x, y, w, h, fill, ln, rx=min(w, h) / 2 * sh.get('round', 0) / 100)
    if sh.get('text'):
        pad = sh.get('pad') or [1.0, 1.0, 1.0, 1.0]
        pad = pad if isinstance(pad, list) else [pad] * 4
        blocks = sh['text'] if isinstance(sh['text'], list) else [sh['text']]
        at = layout_blocks(ctx, blocks, cs, w - pad[0] - pad[1])
        th = sum(a.h for a in at)
        va = sh.get('valign', 'center')
        yy = y + pad[2] + (0 if va == 'top' else (h - pad[2] - pad[3] - th) / (2 if va == 'center' else 1))
        for a in at:
            a.emit(x + pad[0], yy, page)
            yy += a.h
