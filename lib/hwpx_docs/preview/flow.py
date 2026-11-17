"""Page flow of the preview: sections, pages, columns, header/footer, page numbers, footnotes. `render_pages(path)` is the entry."""
from ..core import tmpdir
from ..core import read as rd
import os
import re
import shutil
from . import drawers
from .layout import A, Ctx, emit_line, layout_blocks, note_line_length, note_shape, shape_at
from .measure import BASE, BLACK, PAPER_MM, PT, cwidth, fmt_num, parse_line
from .svg import Page, page_svg, rect, set_min_line, stroke


def geometry(sec):
    pg = sec.get('page', {})
    size = pg.get('size', 'A4')
    w, h = PAPER_MM['A4'] if size == 'A4' else tuple(size)
    if pg.get('landscape'):
        w, h = h, w
    m = dict(left=20, right=20, top=20, bottom=15, header=15, footer=15, gutter=0)
    m.update(pg.get('margin', {}))
    g = dict(w=w, h=h, **m)
    g['x0'], g['x1'] = m['left'] + m['gutter'], w - m['right']
    g['y0'], g['y1'] = m['top'] + m['header'], h - m['bottom'] - m['footer']
    return g


def hf_blocks(v, no):
    if v is None:
        return None
    if isinstance(v, list):
        return v
    ap = v.get('apply', 'both')
    if ap == 'both' or (ap == 'even') == (no % 2 == 0):
        return v['blocks']
    return None


def fmt_page(n, f, side):
    s = fmt_num(n, {'DIGIT': 'DIGIT', 'ROMAN_CAPITAL': 'ROMAN_CAPITAL', 'ROMAN_SMALL': 'ROMAN_SMALL',
                    'HANGUL_SYLLABLE': 'HANGUL_SYLLABLE', 'CIRCLED_DIGIT': 'CIRCLED_DIGIT'}.get(f.upper(), 'DIGIT'))
    return '%s %s %s' % (side, s, side) if side else s


def page_border(ctx, pg, sec, g):
    """쪽 테두리/배경 of a page (geometry g)."""
    pb = sec.get('page_border')
    if not pb:
        return
    ln = {k: parse_line(v) for k, v in (pb.get('border') or {}).items()}
    o = pb.get('offset', 5)
    o = o if isinstance(o, list) else [o] * 4
    base = (0, 0, g['w'], g['h']) if pb.get('text_border', 'paper') == 'paper' else (g['left'], g['top'], g['w'] - g['right'], g['h'] - g['bottom'])
    x0, y0, x1, y1 = base[0] + o[0], base[1] + o[2], base[2] - o[1], base[3] - o[3]
    if pb.get('fill'):
        rect(pg, x0, y0, x1 - x0, y1 - y0, drawers.paint(ctx, pg, pb['fill'], x1 - x0, y1 - y0))
    for k, (a, b, c, d) in (('top', (x0, y0, x1, y0)), ('bottom', (x0, y1, x1, y1)), ('left', (x0, y0, x0, y1)), ('right', (x1, y0, x1, y1))):
        if ln.get(k):
            stroke(pg, a, b, c, d, ln[k])


def page_frame(ctx, pg, sec, g, base_cs, zones=None):
    """Header, footer and page number of a page (geometry g; x from g['x0'] to g['x1']). zones = (header top, footer
    top, bottom page number top) in mm to place them elsewhere (a vertical section, rules P14)."""
    hz, fz, nz = zones or (g['top'], g['h'] - g['bottom'] - g['footer'], g['h'] - g['bottom'] - base_cs['size'] * 1.6 * PT)
    for key, zone in (('header', hz), ('footer', fz)):
        bl = hf_blocks(sec.get(key), pg.no)
        if bl:
            ats = layout_blocks(ctx, bl, base_cs, g['x1'] - g['x0'])
            yy = zone
            if key == 'footer' and not zones and ats:   # the footer ends at the bottom margin (tabs_fields, vt2_head_hf)
                yy = g['h'] - g['bottom'] - (sum(a.h for a in ats) - ats[-1].trail)
            for a in ats:
                if a.emit:
                    a.emit(g['x0'], yy, pg)
                yy += a.h
    pn = sec.get('page_number')
    if pn:
        pos = pn.get('pos', 'bottom_center')
        txt = fmt_page(pg.no, pn.get('format', 'digit'), pn.get('side', ''))
        wtxt = sum(cwidth(ch, base_cs) for ch in txt) * PT
        xx = g['x0'] if pos.endswith('left') else (g['x1'] - wtxt if pos.endswith('right') else (g['x0'] + g['x1'] - wtxt) / 2)
        yy = hz if pos.startswith('top') else nz        # bottom of the footer zone (measured)
        emit_line(ctx, dict(seg=[(c, cwidth(c, base_cs), base_cs, None) for c in txt], vs=base_cs['size'], base=BASE * base_cs['size'],
                            dx=xx - g['x0'], avail=wtxt, align='left', last=True, origin=0), g['x0'], yy, pg)


def free_ranges(zones, cx0, cx1, top, bottom, skip=None):
    """Free x ranges of the column [cx0, cx1] beside the zones (square / top_and_bottom objects) that cover [top, bottom]
    -> ([(x0, x1)] mm from the column left, the lowest bottom of those zones or None). Zones of `skip` (a Para) are
    left out. side (textFlow): both_sides, left_only, right_only, largest_only (rules P16)."""
    hit = [z for z in zones if (skip is None or z['para'] is not skip) and z['y0'] < bottom - 1e-6 and z['y1'] > top + 1e-6
           and z['x0'] < cx1 - 1e-6 and z['x1'] > cx0 + 1e-6]
    if not hit:
        return [(0.0, cx1 - cx0)], None
    iv = [(cx0, cx1)]
    for z in hit:
        if z['wrap'] == 'top_and_bottom':
            iv = []
            continue
        left = [(a, min(b, z['x0'])) for a, b in iv if a < z['x0']]
        right = [(max(a, z['x1']), b) for a, b in iv if b > z['x1']]
        side = z['side']
        if side == 'largest_only':
            side = 'left_only' if sum(b - a for a, b in left) >= sum(b - a for a, b in right) else 'right_only'
        iv = (left if side != 'right_only' else []) + (right if side != 'left_only' else [])
    return [(a - cx0, b - cx0) for a, b in iv if b > a], min(z['y1'] for z in hit)


def snapshot(ctx):
    """The ctx state to lay a section out again (lists and dicts copied one level)."""
    return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in vars(ctx).items()}


def render_section(ctx, sec, first_no):
    """A section; laid out twice when objects placed on the page or paper move text (the second time those objects
    are on their page before any text of it, rules P16), or when footnotes of a later column make the block under all
    columns taller (the second time the columns before keep room for it, rules P15)."""
    saved = snapshot(ctx)
    fixed = lay_section(ctx, sec, first_no)
    if fixed:
        vars(ctx).clear()
        vars(ctx).update(saved)
        lay_section(ctx, sec, first_no, fixed)


def lay_section(ctx, sec, first_no, fixed=None):
    if getattr(ctx, 'trace', None) is not None:
        ctx.trace.append(('section', getattr(ctx, 'section', 0)))
    g = geometry(sec)
    cols = sec.get('columns') or {}
    ncol = cols.get('count', 1)
    gap = cols.get('gap', 0)
    cw = (g['x1'] - g['x0'] - (ncol - 1) * gap) / ncol
    base_cs = dict(rd.DEF_CHAR)
    if sec.get('_upright'):                             # 세로쓰기 vertical_all: every letter in a full cell (P14)
        base_cs['upright'] = True
    if sec.get('_vcell'):                               # 세로쓰기: Hangul letters in full cells (vt2_* line breaks)
        base_cs['vcell'] = True
    st = {'no': first_no, 'page': None, 'col': 0, 'y': g['y0'], 'n': 0, 'k': 0, 'nroom': {}, 'ends': {}, 'cont': {},
          'shut': None, 'top': None, 'defer': []}
    fixed = fixed or {}
    zones = []                      # objects on this page that text goes around (rules P16)
    placed = []                     # (n, page index, zone) of the objects placed on the page or paper
    merged = {}                     # page index -> room of the footnote block under all columns (rules P15)
    ctx.note_shapes = sec.get('note_shape') or {}       # 주석 모양 of this section (pagex reader; rules P15)
    for end, attr in ((False, 'notes'), (True, 'endnote_n')):
        shape = note_shape(ctx, end)
        if shape['numbering'] == 'on_section' or getattr(ctx, 'section', 0) == 0 and not ctx.pages:
            setattr(ctx, attr, int(shape['start']) - 1)
        if end and shape['numbering'] == 'on_page':     # footnotes: numbered again when drawn (layout.renumber)
            print('PREVIEW NOT DRAWN endnote numbering on_page (numbers run on) on page %s' % first_no)

    def info(pg):
        """What a page layer (drawers.register_page_layer) gets to know about the page."""
        return dict(no=pg.no, index=pg.n, section=getattr(ctx, 'section', 0), first=st['n'] == 1, odd=pg.no % 2 == 1,
                    size=(g['w'], g['h']), margin={k: g[k] for k in ('left', 'right', 'top', 'bottom', 'header', 'footer', 'gutter')},
                    body=(g['x0'], g['y0'], g['x1'], g['y1']), columns=dict(count=ncol, gap=gap, width=cw), spec=sec)

    def new_page():
        finish()
        ctx.pageno = st['no'] if st['page'] is None else ctx.pageno + 1
        pg = Page(len(ctx.pages) + 1, ctx.pageno, g)
        ctx.pages.append(pg)
        st['page'], st['col'], st['y'] = pg, 0, g['y0']
        st['n'] += 1
        st['nroom'], st['ends'] = {}, {}
        zones[:] = [z for _, n, z in fixed.get('zones', ()) if n == st['n']]     # second time: there before the text
        page_border(ctx, pg, sec, g)
        pg.info, pg.under_at = info(pg), len(pg.svg)   # page layers are drawn after all pages are laid out (layers())
        low = g['h'] - g['bottom'] - base_cs['size'] * PT       # 세로쓰기 vertical_head (vertical.virtual_section)
        page_frame(ctx, pg, sec, g, base_cs, (g['top'], low, low) if sec.get('_frame_low') else None)

    def finish():
        """Footnotes of the page at the bottom of the page or column, or right under the text (rules P15). A block
        that does not fit under the text goes on at the bottom of the next page (nt_room: Hangul splits a long note)."""
        pg = st['page']
        if not pg or getattr(pg, 'done', False):
            return
        pg.done = True
        shape = note_shape(ctx, False)
        cont, st['cont'] = st['cont'], {}
        for col in sorted({note_col(nt) for nt in pg.notes} | set(cont)):
            x = g['x0'] + max(col, 0) * (cw + gap)
            width = g['x1'] - g['x0'] if col < 0 else cw
            ats = block_atoms(cont.get(col, []), [nt for nt in pg.notes if note_col(nt) == col], width)
            end = max(list(st['ends'].values()) or [g['y0']]) if col < 0 else st['ends'].get(col, g['y0'])
            free = g['y1'] - end - shape['above'] - shape['below']
            if ats and col < 0 and ncol > 1 and note_place() == 'merged_column' and any(nt.get('col', 0) for nt in pg.notes):
                merged[st['n']] = sum(a.h for a in ats) - ats[-1].trail + shape['above'] + shape['below']
            k, h = 0, 0.0
            while k < len(ats) and h + ats[k].h - ats[k].trail <= free + 0.05:
                h += ats[k].h
                k += 1
            rest = ats[k:]
            while rest and not rest[0].emit:            # the space between two notes does not start a page
                rest = rest[1:]
            if rest:
                st['cont'][col] = rest
                if getattr(ctx, 'trace', None) is not None:      # a footnote goes on at the next page
                    ctx.trace.append(('notes_cont', pg.n, col))
            if not k:
                continue
            h -= ats[k - 1].trail                       # the last line's spacing below is not kept
            if getattr(ctx, 'trace', None) is not None:
                ctx.trace.append(('notes', pg.n, col, h))
            top = end + shape['above'] + shape['below'] if shape.get('beneath_text') else g['y1'] - h
            ln = parse_line(shape['line'])
            if ln:
                ly = top - shape['below']
                stroke(pg, x, ly, x + note_line_length(shape['line_length'], width), ly, ln, ext=False)
            for a in ats[:k]:
                if a.emit:
                    a.emit(x, top, pg)
                top += a.h
        pg.notes = []

    def endnotes():
        """Endnotes after the text: at the end of the document, or of the section (place end_of_section) (P15)."""
        shape = note_shape(ctx, True)
        if not ctx.endnotes or not (shape['place'] == 'end_of_section' or getattr(ctx, 'last_section', True)):
            return
        w = cw
        ln, length = parse_line(shape['line']), note_line_length(shape['line_length'], w)
        sep = A(shape['above'] + shape['below'], lambda x, y, pg: ln and stroke(pg, x, y + shape['above'], x + length,
                                                                              y + shape['above'], ln, ext=False))
        for a in [sep] + notes_atoms(ctx, ctx.endnotes, shape, dict(base_cs, size=9), w):
            put(a)
        ctx.endnotes = []

    def put(a):
        room(a)
        draw(a)

    def need(a):
        """How far down `a` must fit: its text (not the spacing below), and under a table row that is not the table's end
        the room for the table's caption below it (P18, kc_capb*)."""
        return a.h - a.trail + (a.tbl.get('foot', 0.0) if a.tbl is not None and a.shut else 0.0)

    def at_top():
        """Nothing in this column yet, or only a table's outer margin and header rows above the row that goes on (P18)."""
        return st['y'] <= g['y0'] + 1e-6 or st['top'] == (st['page'], st['col'], st['y'])

    def room(a):
        """A new column or page when `a` must start one or does not fit (above the footnotes of its column, with its own)."""
        top_of_col = at_top()
        if a.keep == 'break' and not top_of_col:
            nxt(True)
        elif a.keep == 'next' and not top_of_col:      # where the keep rules split a paragraph (keeps)
            nxt(False)
        elif st['y'] + need(a) > g['y1'] - notes_need(a.notes) + 0.05 and not top_of_col:
            nxt(False)              # the spacing below a row may run into the room above the notes (nt_room, nt_col_each)

    def note_place():
        """Where the footnotes of a page go: 'merged_column' (one block under all columns; also with one column),
        'each_column' (under the column of the reference) or 'right_most_column' (rules P15)."""
        return note_shape(ctx, False)['place'] if ncol > 1 else 'merged_column'

    def note_col(nt):
        return {'each_column': nt.get('col', 0), 'right_most_column': ncol - 1}.get(note_place(), -1)

    def block_atoms(cont, notes, width):
        """Atoms of a footnote block: the lines that go on from the page before, then the notes of this page."""
        shape = note_shape(ctx, False)
        ats = notes_atoms(ctx, notes, shape, dict(base_cs, size=9), width) if notes else []
        if cont and ats:
            cont = cont + [A(float(shape['between']) - cont[-1].trail)]
        return list(cont) + ats

    def notes_need(more=()):
        """Room at the bottom of the current column for its footnotes (the whole block of the notes it holds) and
        for the first line of `more` (a row's own footnotes: the rest may go on at the next page, nt_room)."""
        place, col = note_place(), st['col']
        mine = [nt for nt in st['page'].notes if note_col(nt) in (-1, col)]
        cont = st['cont'].get(-1, []) + st['cont'].get(col, [])
        own = bool(more) and (place != 'right_most_column' or col == ncol - 1)
        if not (mine or cont or own):
            return 0.0
        shape = note_shape(ctx, False)
        width = g['x1'] - g['x0'] if place == 'merged_column' else cw
        key = (st['page'].n, col, len(mine), len(cont))     # ponytail: the block is laid out again only when it grows
        if key not in st['nroom']:
            ats = block_atoms(cont, mine, width)
            st['nroom'][key] = sum(a.h for a in ats) - ats[-1].trail if ats else 0.0
        h = st['nroom'][key]
        if own:
            first = notes_atoms(ctx, list(more)[:1], shape, dict(base_cs, size=9), width)[0]
            h += (float(shape['between']) if h else 0.0) + first.h - first.trail
        if place == 'merged_column' and ncol > 1:           # second time: the block as tall as it ends up
            h = max(h, fixed.get('notes', {}).get(st['n'], 0.0) - shape['above'] - shape['below'])
        return h + shape['above'] + shape['below']

    def draw(a):
        pg, x = st['page'], g['x0'] + st['col'] * (cw + gap)
        pg.col = st['col']                              # a footnote keeps its column (layout.emit_line)
        if a.emit:
            a.emit(x, st['y'], pg)
            st['ends'][st['col']] = st['y'] + a.h - a.trail     # where the text of the column ends (beneath_text)
            st['shut'] = (a.shut, x, st['y'], pg) if a.shut else None
        if getattr(ctx, 'trace', None) is not None:       # a tool that plans pages asks for what went where (blocks.page_report)
            ctx.trace.append(('atom', pg.n, st['col'], st['y'], a))
        if a.base is not None:                          # a body text line: for line numbers (page.lines)
            pg.lines.append([st['y'] + a.base, x, st['col']])
        st['y'] += a.h

    def anchor(P, x, y):
        """The objects of paragraph P (placed at x, y) that text goes around become zones of the page (rules P16)."""
        P.pin = (x, y)
        for sh in P.shapes:
            if sh.get('wrap') not in ('square', 'top_and_bottom') or not sh.get('w') or not sh.get('h'):
                continue
            sx, sy = shape_at(sh, st['page'], x, y, P.width, P.pp)
            z = dict(x0=sx, y0=sy, x1=sx + sh['w'], y1=sy + sh['h'], wrap=sh['wrap'], side=sh.get('side', 'both_sides'), para=P)
            if sh.get('rel') in ('page', 'paper'):      # on its page before the text the second time (render_section)
                st['k'] += 1
                if any(k == st['k'] and n == st['n'] for k, n, _ in fixed.get('zones', ())):
                    continue
                placed.append((st['k'], st['n'], dict(z, para=None)))
            zones.append(z)

    def around(a):
        """`a` beside the zones of the page: None (draw it as it is), or the atoms that take the place of `a` and of the
        rest of its paragraph (rows wrapped in the free ranges, or room to go below the objects)."""
        x, y, P = g['x0'] + st['col'] * (cw + gap), st['y'], a.para
        if P is not None and P.pin is None and a.start == 0 and P.shapes and not a.absorb:
            anchor(P, x, y)
        if a.absorb and P is not None and P.pin is not None:    # room under the paragraph's objects (P11): only what
            own = [z for z in zones if z['para'] is P and z['wrap'] == 'top_and_bottom']
            if own and min(z['y0'] for z in own) > y + 1e-6:     # a gap before the object: text goes on into it and
                return []                                        # moves below the object where it meets it (vt2_pic_para)
            bottom = max([z['y1'] for z in own] or [y])
            if abs(bottom - y - a.h) > 1e-6:                    # its rows left (rows that moved below them use it up)
                return [A(bottom - y, absorb=a.absorb)] if bottom - y > 1e-6 else []
        if a.absorb or (a.keep == 'skip' and a.at is None):     # room under objects (P11, or put in by around)
            return None
        here = (st['page'].n, round(x, 3), round(y, 3))
        if a.at is not None and a.at == here:
            return None
        rows = P is not None and not P.boxed
        if a.at is None:
            iv, below = free_ranges(zones, x, x + cw, y, y + a.h, None if rows else P)
            if below is None:
                return None
            if not rows:                                # a table row, a boxed paragraph ...: below the objects
                return [A(below - y, keep='skip'), a]

        def free(top, bottom):
            iv, below = free_ranges(zones, x, x + cw, y + top, y + bottom)
            return iv, None if below is None else below - y
        new, yy = P.wrap(a.start, free), y
        for b in new:
            b.at = (st['page'].n, round(x, 3), round(yy, 3))
            yy += b.h
        return new

    def group(q, i):
        """(start, end) in q of the rows of the paragraph that q[i] belongs to; one atom for a table row or a box."""
        P = q[i].para
        if P is None or P.boxed or q[i].absorb:
            return i, i + 1
        s, e = i, i + 1
        while s > 0 and q[s - 1].para is P and not q[s - 1].absorb:
            s -= 1
        while e < len(q) and q[e].para is P and not q[e].absorb:
            e += 1
        return s, e

    def keeps(q, i):
        """The keep rules in the body flow before q[i] is drawn: True when it moved to the next column or page; a split
        is marked on its row (keep 'next')."""
        top = at_top()
        r = keep_plan(q, i, top, lambda used, row: st['y'] + used + row.h - row.trail <= g['y1'] - notes_need(row.notes) + 0.05,
                      g['y1'] - g['y0'], g['y1'] - st['y'])
        if r == 'move':
            nxt(False)
            return True
        if r is not None:
            q[r].keep = 'next'
        return False

    def table_plan(a, full, ahead):
        """Hangul's table cuts at row a, not at a page top (pagefit PF02): a table with page_break none that fits on a page
        is not cut; no cut inside a group of merged rows (rs) when the group fits on a page. 'move' or None."""
        T, r = a.tbl, a.row
        if r == 0 and T['pb'] == 'none' and ahead + 0.05 < sum(x.h for x in T['atoms']) <= full:
            return 'move'
        if r not in T['bad'] and r + 1 in T['bad']:
            e = r + 1
            while e in T['bad']:
                e += 1
            need = T.get('gneed', {}).get(r) or sum(x.h for x in T['atoms'][r:e])
            if ahead + 0.05 < need <= full:
                return 'move'
        return None

    def block(q, j):
        """(start, end) in q of the block that q[j] starts: a paragraph's rows, or a table's rows (its row data tbl)."""
        if q[j].para is None and q[j].tbl is not None:
            e = j + 1
            while e < len(q) and q[e].tbl is q[j].tbl:
                e += 1
            return j, e
        return group(q, j)

    def keeps_next(a):
        """`a` starts a block with 다음 문단과 함께 (keep_next): a paragraph, or a table whose paragraph has it (PF25)."""
        if a.para is not None:
            return bool(a.para.pp.get('keep_next'))
        return a.tbl is not None and bool(a.tbl.get('keep_next')) and a is a.tbl['atoms'][0]

    def with_next(q, s, full, ahead):
        """'move' when the block at q[s] (and the next blocks that keep with the next) must go on with the next PARAGRAPH
        (pagefit PF02, PF25): it fits whole here but the first part of the next paragraph does not (one line; two with
        widow when it has 4 lines or more; all of it with fewer or with keep_lines). A block already cut on this page has
        its last line with the next one, and toward a table or an object keep_next does nothing. A table with keep_next
        (a heading box) is such a block: Hangul moves the whole table (2 x 2 table, canary 6 of pagefit)."""
        total, j = 0.0, s
        while True:
            js, je = block(q, j)
            total += sum(x.h for x in q[js:je])
            if total - q[je - 1].trail > ahead + 0.05:
                return None
            j = je
            if j >= len(q) or not keeps_next(q[j]):
                break
        T = q[j].tbl if j < len(q) and q[j].para is None else None
        if T is not None and T.get('hold') and q[j] is T['atoms'][0]:
            je = block(q, j)[1]                             # a table that holds its paragraph on its page: the paragraph comes
            nxt_h = sum(x.h for x in q[j:je]) - q[je - 1].trail     # with the whole table (P18, kh_hold)
            return 'move' if total + nxt_h > ahead + 0.05 and total <= full else None
        if j >= len(q) or q[j].base is None:
            return None
        ns, ne = group(q, j)
        nx, P2 = q[ns:ne], q[ns].para
        if P2 is not None and P2.pp.get('keep_lines') and sum(x.h for x in nx) <= full:
            k = len(nx)                                     # the next paragraph may not be cut either
        elif P2 is not None and P2.pp.get('widow') and len(nx) >= 2:
            k = 2 if len(nx) >= 4 else len(nx)              # its first cut leaves two lines at least on each page
        else:
            k = 1
        if total + sum(x.h for x in nx[:k]) - nx[k - 1].trail > ahead + 0.05 and total <= full:
            return 'move'
        return None

    def keep_plan(q, i, top, fits, full, ahead):
        """Hangul's keep rules for q[i] (pagefit rules PF02, P17) at the start of a paragraph or of a page / column: 다음
        문단과 함께 (keep_next: the block and the next ones that keep, with the first line of the block after them, or two
        with widow), 문단 보호 (keep_lines: whole on one page when it fits on one), 외톨이 줄 보호 (widow: no single line at
        the bottom, none at the top: the page before gives one line more). -> 'move' (q[i] goes on to the next column or
        page), the index in q of the row where the paragraph splits, or None. fits(height placed so far, row): the row
        still fits; full: mm of an empty page / column; ahead: mm from here down to its bottom."""
        a, P = q[i], q[i].para
        if a.tbl is not None and P is None:
            if top:
                return None
            return (with_next(q, i, full, ahead) if keeps_next(a) else None) or table_plan(a, full, ahead)
        if P is None or a.absorb or a.keep == 'skip':
            return None
        s, e = group(q, i)
        rows, k0, pp = q[s:e], i - s, P.pp
        if k0 == 0 and pp.get('keep_next') and not top and with_next(q, s, full, ahead):
            return 'move'
        if k0 and not top:                                  # a paragraph is planned at its start and at a page top
            return None
        n, m, used = len(rows), 0, 0.0
        while k0 + m < n and (fits(used, rows[k0 + m]) or top and m == 0):
            used += rows[k0 + m].h
            m += 1
        if k0 + m >= n:
            return None
        if pp.get('keep_lines') and k0 == 0 and not top and sum(x.h for x in rows) <= full:
            m = 0
        elif pp.get('widow') and n >= 2 and not P.boxed:
            if k0 == 0 and m < 2:
                m = 0                                   # one line at the bottom of the page: the whole paragraph goes on
            elif n - (k0 + m) == 1:                     # one line left for the next page: it takes one more
                m = m - 1 if (k0 + m - 1 >= 2 or k0 > 0) else 0
        if m == 0 and not top:
            return 'move'
        return s + k0 + max(m, 1)

    def cell_cut(q, room, top):
        """How many of a cell's atoms go on the first part of a row cut at a page end, room mm for them (rules P18): the
        keep rules of P17 hold inside the cell, but its first paragraph stays even with one line (kc_w1)."""
        y, i = 0.0, 0
        while i < len(q):
            a = q[i]
            if (i or not top) and y + a.h - a.trail > room + 0.05:
                return i
            y0 = y
            r = keep_plan(q, i, i == 0, lambda used, row: y0 + used + row.h - row.trail <= room + 0.05, g['y1'] - g['y0'],
                          room - y0)
            if r is not None:
                return i if r == 'move' else r
            y += a.h
            i += 1
        return i

    def adopt(a, first):
        """Row atom `a` becomes the first part of its cut (P18): the trace keeps its atom (report.page_report)."""
        a.h, a.emit, a.shut, a.cut, a.trail = first.h, first.emit, first.shut, None, first.trail
        return a

    def goes_on(a):
        """`a` is a table row after the table's first one, at the top of a column the table has not been on yet."""
        T = a.tbl
        return T is not None and a.para is None and a is not T['atoms'][0] and st['y'] <= g['y0'] + 1e-6 \
            and (st['page'].n, st['col']) not in T['rep']

    def body(atoms):
        """Atoms of the body in the flow, rows wrapped beside the objects that text goes around (rules P16)."""
        q, i = list(atoms), 0
        while i < len(q):
            a = q[i]
            if a.keep == 'skip' and st['y'] + a.h > g['y1'] + 0.05:     # room under objects past the page end: dropped
                nxt(False)
                i += 1
                continue
            if a.tbl is not None and a.tbl.get('defer') is not None and a is a.tbl['atoms'][0] and a.keep != 'break' \
                    and not at_top():
                j = block(q, i)[1]
                if st['y'] + sum(x.h for x in q[i:j]) - q[j - 1].trail > g['y1'] - notes_need(a.notes) + 0.05:
                    st['defer'] += q[i:j]               # a table kept whole without hold, or with a side caption (P18, kh_none,
                    q[i:j] = [A(a.tbl['defer'], trail=a.tbl['defer'])]  # kc_capl): the next page takes it whole, the
                    # text goes on here (the empty line is room, not text: pagefit's used height leaves it out)
                    if getattr(ctx, 'trace', None) is not None:     # under its paragraph's empty line (pagefit: reading order)
                        ctx.trace.append(('defer', st['page'].n, st['col'], st['y'], a))
                    continue
            if a.cut is not None and (not a.keep or at_top()) and not goes_on(a):
                avail = g['y1'] - notes_need(a.notes) - st['y']
                got = a.cut(avail - a.tbl.get('foot', 0.0), at_top(), cell_cut) if need(a) > avail + 0.05 else None
                if got:                                 # a row cut inside its cells (P18): the rest on the next page
                    adopt(a, got[0])
                    got[1].keep = 'next'
                    q.insert(i + 1, got[1])
            room(a)
            T = a.tbl
            if goes_on(a):                              # a table going on at the top of a column: the header rows again (PF02)
                T['rep'].add((st['page'].n, st['col']))     # or its outer margin (kc_table: 1 mm; the first row has it)
                if 0 < T['hdr'] <= a.row and (a.cut is not None or
                                              sum(x.h for x in T['atoms'][:T['hdr']]) + a.h <= g['y1'] - g['y0']):
                    x = g['x0'] + st['col'] * (cw + gap)
                    st['y'] += T['mc'] - T['mt']        # the header rows again: their first row has the table's top margin in it
                    for hr in T['atoms'][:T['hdr']]:
                        if hr.emit:
                            hr.emit(x, st['y'], st['page'])
                        st['y'] += hr.h
                else:
                    st['y'] += T['mc']
                st['top'] = (st['page'], st['col'], st['y'])
                continue
            new = around(a)
            if new is not None:
                j = i + 1
                while a.para is not None and not a.para.boxed and j < len(q) and q[j].para is a.para and not q[j].absorb:
                    j += 1
                q[i:j] = new
                continue
            if keeps(q, i):
                continue
            draw(a)
            i += 1
        if st['defer']:                                 # a table still waiting: on a page of its own after the text
            nxt(False)

    def nxt(force_page):
        if st['shut']:                                  # a table cut at this page end: its last row gets its bottom edge
            st['shut'][0](*st['shut'][1:])
            st['shut'] = None
        if not force_page and st['col'] + 1 < ncol:
            st['col'] += 1
            st['y'] = g['y0']
        else:
            new_page()
        defer, st['defer'] = st['defer'], []
        for a in defer:                                 # tables that waited for this column or page (P18)
            draw(a)
    def fill(atoms, n, h, fresh, place_at=None, w=0.0, gp=0.0):
        """Greedy fill of `n` columns `h` mm high from the region top: the atoms left over (and the height used). With
        place_at (top y) it also draws them. A page break atom stops the fill unless it is first on a fresh page. A row
        fits when its text does (the spacing below may run past the bottom), and the keep rules of P17 hold here too
        (kp_region_* samples: Hangul applies them after a column change); a table row is cut inside its cells as in the
        body (P18, kc_r* samples)."""
        q, col, y, ctop, used, cut, c, last, rep = list(atoms), 0, 0.0, None, 0.0, set(), 0, None, set()

        def shut():                                     # the bottom edge of a table cut at this column end
            if last:
                last[0](*last[1:])

        while c < len(q):
            a = q[c]
            if a.keep == 'break' and not (col == 0 and y == 0 and fresh):
                shut()
                return q[c:], used
            top = y <= 1e-6 or y == ctop
            T = a.tbl
            if T is not None and a.para is None and a is not T['atoms'][0] and y <= 1e-6 and col not in rep:
                rep.add(col)                            # a table going on at a column top: header rows or outer margin
                hdr = T['atoms'][:T['hdr']] if 0 < T['hdr'] <= a.row and (
                    a.cut is not None or sum(x.h for x in T['atoms'][:T['hdr']]) + a.h <= h) else []
                y += T['mc'] - T['mt'] if hdr else 0.0
                for hr in hdr:
                    if place_at is not None and hr.emit:
                        hr.emit(g['x0'] + col * (w + gp), place_at + y, st['page'])
                    y += hr.h
                y = ctop = y if hdr else T['mc']
                continue
            if a.cut is not None and (top or c not in cut) and y + need(a) > h + 0.05:
                got = a.cut(h - y - a.tbl.get('foot', 0.0), top, cell_cut)
                if got:
                    first = adopt(a, got[0]) if place_at is not None else got[0]
                    q[c:c + 1] = [first, got[1]]
                    cut = {k + (k > c) for k in cut} | {c + 1}  # the rest starts the next column
                    a = first
            if not top and (c in cut or y + need(a) > h + 0.05):
                r = 'move'
            else:
                y0 = y
                r = keep_plan(q, c, top, lambda done, row: y0 + done + row.h - row.trail <= h + 0.05, h, h - y0)
            if r == 'move':
                if place_at is not None:
                    shut()
                col, y, ctop, last = col + 1, 0.0, None, None
                if col == n:
                    return q[c:], used
                continue
            if r is not None:
                cut.add(r)
            if place_at is not None:
                pg, x = st['page'], g['x0'] + col * (w + gp)
                if a.emit:
                    a.emit(x, place_at + y, pg)
                    last = (a.shut, x, place_at + y, pg) if a.shut else None
                if getattr(ctx, 'trace', None) is not None:
                    ctx.trace.append(('atom', pg.n, col, place_at + y, a))
                if a.base is not None:
                    pg.lines.append([place_at + y + a.base, x, col])
            y += a.h
            used = max(used, y)
            c += 1
        return [], used

    def region(cdef, blocks, balance, first=True):
        """One column setting (단 설정) from here: its blocks laid out at its column width and placed under what is on
        the page. balance: a later setting follows, so the columns of its last page are made even (pagex rules PX10)."""
        n = max(1, int(cdef.get('count', 1) or 1))
        gp = cdef.get('gap', 0) if n > 1 else 0
        w = (g['x1'] - g['x0'] - (n - 1) * gp) / n
        atoms = layout_blocks(ctx, blocks, base_cs, w)
        ln = parse_line(cdef['line']) if cdef.get('line') and n > 1 else None
        if not first and blocks and st['y'] > g['y0'] + 1e-6:
            st['y'] += 1.8                      # a new setting starts 1.8 mm lower (P13, measured on cols_mid_S)
        rest, top = atoms, st['y']
        while rest:
            room, fresh = g['y1'] - top, top <= g['y0'] + 1e-6
            h = room
            if balance and n > 1 and not fill(rest, n, room, fresh)[0]:
                lo, hi = 0.0, room                     # the lowest column height that still takes every atom
                for _ in range(24):
                    mid = (lo + hi) / 2
                    lo, hi = (lo, mid) if not fill(rest, n, mid, fresh)[0] else (mid, hi)
                h = hi
            left, used = fill(rest, n, h, fresh, top, w, gp)
            if left and left[0] is rest[0]:             # a page break first, below other content: a new page
                new_page()
                top = st['y']
                continue
            for k in range(1, n if ln else 1):
                xx = g['x0'] + k * (w + gp) - gp / 2
                stroke(st['page'], xx, top, xx, top + (room if left else used), ln, ext=False)
            rest = left
            if rest:
                new_page()
                top = st['y']
            else:
                st['y'] = top + used

    new_page()
    regions = column_regions(sec.get('body', []), cols)
    if len(regions) > 1:                                # 단 설정 나누기 inside the section (C10.03)
        for k, (cdef, blocks) in enumerate(regions):
            region(cdef, blocks, k < len(regions) - 1, k == 0)
    else:
        body(layout_blocks(ctx, sec.get('body', []), base_cs, cw))
    endnotes()
    finish()
    while st['cont']:                                   # a footnote that goes on after the last page of text
        new_page()
        finish()
    st['page'].info['is_last'] = True                   # last page of this section
    if cols.get('line') and ncol > 1 and len(regions) == 1:
        ln = parse_line(cols['line'])
        pgs = [p for p in ctx.pages if p.g is g]
        for pg in pgs:
            for k in range(1, ncol):
                xx = g['x0'] + k * (cw + gap) - gap / 2
                stroke(pg, xx, g['y0'], xx, g['y1'], ln, ext=False)
    if fixed or not (placed or merged):
        return None
    return {'zones': placed, 'notes': merged}


def notes_atoms(ctx, notes, shape, cs, width):
    """Atoms of notes, each starting with its number as Hangul writes it (superscript when the shape says so), with the
    shape's space between notes."""
    ats = []
    for i, nt in enumerate(notes):
        bl = nt['blocks'] if isinstance(nt['blocks'], list) else [nt['blocks']]
        bl = [b if isinstance(b, dict) else {'p': b} for b in bl]
        p = bl[0].get('p', '')
        mark = {'t': nt.get('mark', '%d)' % nt['n']), 'sup': True} if shape['superscript'] else nt.get('mark', '%d)' % nt['n'])
        first = dict(bl[0], p=[mark, ' '] + (p if isinstance(p, list) else [p]))
        ats += layout_blocks(ctx, [first] + bl[1:], cs, width)
        if i < len(notes) - 1 and ats:                  # between notes: `between` instead of the last line's spacing
            ats.append(A(float(shape['between']) - ats[-1].trail))
    return ats


def colpr(xml):
    """A raw `hp:colPr` (in `hp:ctrl`) -> the spec column dict {count, gap mm, type, line}."""
    def attr(tag, name, default=None):
        m = re.search(r'<hp:%s\b[^>]*\b%s="([^"]*)"' % (tag, name), xml)
        return m.group(1) if m else default
    c = {'count': int(attr('colPr', 'colCount', 1)), 'gap': int(attr('colPr', 'sameGap', 0)) / 283.465,
         'type': str(attr('colPr', 'type', 'NEWSPAPER')).lower()}
    kind = attr('colLine', 'type', 'NONE')
    if kind != 'NONE':
        c['line'] = '%s %s %s' % (str(attr('colLine', 'width', '0.12 mm')).replace(' ', ''), kind.lower(),
                                  attr('colLine', 'color', '#000000'))
    return c


def column_change(b):
    """(column dict, the block without it) when a new column setting starts at block `b` (spec `columns_here`, or a
    raw `hp:ctrl/hp:colPr` run that the reader keeps; pagex rules PX10), else None."""
    if not isinstance(b, dict):
        return None
    if isinstance(b.get('columns_here'), dict):
        return b['columns_here'], {k: v for k, v in b.items() if k != 'columns_here'}
    p = b.get('p')
    for i, r in enumerate(p if isinstance(p, list) else []):
        if isinstance(r, dict) and isinstance(r.get('xml'), str) and '<hp:colPr' in r['xml']:
            return colpr(r['xml']), dict(b, p=p[:i] + p[i + 1:])
    return None


def column_regions(body, cols):
    """The body split where the column setting changes: [(column dict, blocks)], the section's own setting first."""
    out = [(cols, [])]
    for b in body:
        ch = column_change(b)
        if ch:
            out.append((ch[0], [ch[1]]))
        else:
            out[-1][1].append(b)
    return out


def render_pages(path, dpi=96):
    """HWPX -> list of (width mm, height mm, svg text), one per page."""
    from .protected import placeholder_pages
    pages = placeholder_pages(path)          # a password / distribution document: one placeholder page
    if pages:
        return pages
    set_min_line(25.4 / dpi)
    tmp = tmpdir.mkdtemp('hwpx_preview_')
    try:                                       # the pictures go into the SVG as data: the folder is not needed after
        spec = rd.read(path, os.path.join(tmp, 'spec.json'))
        drawers.prepare(spec, tmp)             # spec rewrites of drawers (picture bullets: drawers/bullet_image.py)
        ctx = lay_out(spec, tmp)
        return [(p.g['w'], p.g['h'], page_svg(p)) for p in ctx.pages]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_spec(spec, pic_dir, dpi=96):
    """A spec (pictures in pic_dir) -> list of (width mm, height mm, svg text): the pages of a document that was not
    read from an HWPX (hwp5: a .hwp read as a spec, with Hangul's own line starts `hangul_lines`)."""
    set_min_line(25.4 / dpi)
    drawers.prepare(spec, pic_dir)
    ctx = lay_out(spec, pic_dir)
    return [(p.g['w'], p.g['h'], page_svg(p)) for p in ctx.pages]


class Trace:
    """Where lay_out writes what it placed (a plain object, so that the section snapshot does not copy it)."""

    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)


def lay_out(spec, pic_dir, trace=None):
    """The laid out pages of a spec (Ctx with .pages). trace: a Trace that gets ('section', i) when a section is laid out (again: the
    events of its first layout are void), ('atom', page n, column, y mm, atom) for every atom the flow places and
    ('notes', page n, column, height mm) for every footnote block and ('defer', page n, column, y mm, first atom) for a table
    that waits for the next page while the text after it goes on (blocks.page_report reads them)."""
    ctx = Ctx(spec, pic_dir)
    if trace is not None:
        ctx.trace = trace
    first = 1
    secs = spec.get('sections') or [spec]
    for i, sec in enumerate(secs):
        ctx.spec, ctx.section, ctx.last_section = spec, i, i == len(secs) - 1
        start = (sec.get('page') or {}).get('start_page') or (ctx.pageno + 1 if ctx.pages else first)
        if sec.get('text_direction') in ('vertical', 'vertical_all'):     # 세로쓰기 (preview/vertical.py, rules P14)
            from . import vertical
            vertical.render(ctx, sec, start)
        else:
            render_section(ctx, sec, start)
    layers(ctx)
    return ctx


def layers(ctx):
    """Page layers (drawers.register_page_layer), after all pages are laid out: `under` goes below the header and the
    body (above the page border fill), `over` on top of everything; info['is_last'] / ['is_last_doc'] are known now."""
    under, over = drawers.page_layers('under'), drawers.page_layers('over')
    for pg in ctx.pages:
        pg.info.setdefault('is_last', False)
        pg.info['is_last_doc'] = pg is ctx.pages[-1]
        below = [e for fn in under for e in (fn(ctx, pg, pg.info) or [])]
        pg.svg[pg.under_at:pg.under_at] = below
        for fn in over:
            pg.svg.extend(fn(ctx, pg, pg.info) or [])
