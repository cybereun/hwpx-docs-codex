"""HWP 5.0 -> spec (the builder's input), with no Hangul (rules HW19-HW24).

  hd hwp tospec <in.hwp> <out.json>        pictures are saved next to the JSON
  (`hd hwp tohwpx` is owpml.py now: record by record, no spec in between)

The spec has the shape that core.read gives for an HWPX, so the preview, pagefit and the checks take it as they take
an HWPX. Covered: page (size, margins, landscape), page border, columns, header / footer, page number, paragraphs (char and
para shapes as core.read names them), tabs, line breaks, tables (columns, rows, spans, cell borders and fills, margins,
vertical alignment, nesting), pictures, rectangles / ellipses / lines and text boxes, equations, footnotes / endnotes,
click-here fields (누름틀), hyperlinks, bookmarks. Anything else is counted (UNSUPPORTED <kind> on stderr); with
placeholders=True (the renderer) an object of known size becomes a red dashed box "NOT DRAWN <kind>".
"""
import json
import os
import struct
import sys
from collections import Counter

from ..core import read as rd
from . import docinfo, fmt, owpmlmap

HU = 7200 / 25.4
unsupported = Counter()
V_REL, H_REL, VALIGN, HALIGN, FLOW = ([x.lower() for x in t] for t in (          # the spec's words are the OWPML names in lower case
    owpmlmap.V_REL, owpmlmap.H_REL, owpmlmap.POS_VALIGN, owpmlmap.POS_HALIGN, owpmlmap.OBJ_FLOW))


def mm(v):
    return round(v / HU, 3)


def whole(s):
    """A string built one UTF-16 code unit at a time -> proper characters (also inside a field or link dict)."""
    if isinstance(s, str):
        return s.encode('utf-16-le', 'surrogatepass').decode('utf-16-le', 'replace')
    if isinstance(s, dict) and isinstance(s.get('t'), str):
        s['t'] = whole(s['t'])
    return s


class Node:
    __slots__ = ('tag', 'level', 'data', 'children', 'index')

    def __init__(self, tag, level, data, index):
        self.tag, self.level, self.data, self.children, self.index = tag, level, data, [], index


def tree(recs):
    root = Node(-1, -1, b'', -1)
    stack = [root]
    for i, (t, lvl, d) in enumerate(recs):
        n = Node(t, lvl, d, i)
        while stack and stack[-1].level >= lvl:
            stack.pop()
        (stack[-1] if stack else root).children.append(n)
        stack.append(n)
    return root


def common(d):
    """Common object properties of a CTRL_HEADER (table, drawing object, equation): attr, x, y, w, h, margins."""
    if len(d) < 36:
        return None
    attr, y, x, w, h, z = struct.unpack_from('<IiiIIi', d, 4)
    om = struct.unpack_from('<4h', d, 28)
    return dict(attr=attr, x=x, y=y, w=w, h=h, margin=[mm(v) for v in om], inline=bool(attr & 1),
                vrel=V_REL[min(attr >> 3 & 3, 2)], hrel=H_REL[attr >> 8 & 3], halign=HALIGN[min(attr >> 10 & 7, 4)],
                vpos=VALIGN[min(attr >> 5 & 7, 4)],
                wrap=['square', 'top_and_bottom', 'behind_text', 'in_front_of_text', 'tight', 'through'][min(attr >> 21 & 7, 5)],
                side=FLOW[attr >> 24 & 3], flow=bool(attr >> 13 & 1))


class Conv:
    save = rd.Reader.save                 # same safe file names as core.read
    SAFE_EXT = rd.Reader.SAFE_EXT

    def __init__(self, pk, out_dir, placeholders=False):
        self.pk, self.out_dir, self.placeholders = pk, out_dir, placeholders
        self.di = docinfo.DocInfo(pk)
        self.saved = set()
        self.not_drawn = []

    # ---- helpers
    def char(self, i):
        return self.di.chars[i] if 0 <= i < len(self.di.chars) else dict(rd.DEF_CHAR)

    def para_props(self, i):
        return dict(self.di.paras[i]) if 0 <= i < len(self.di.paras) else dict(rd.DEF_PARA)

    def note(self, kind):
        unsupported[kind] += 1

    def placeholder(self, kind, c):
        """A red dashed box of the object's size where it is (renderer only)."""
        self.note(kind)
        if not self.placeholders or not c or not c['w'] or not c['h']:
            return None
        self.not_drawn.append(kind)
        box = {'type': 'rect', 'x': mm(c['x']), 'y': mm(c['y']), 'rel': c['vrel'], 'w': mm(c['w']), 'h': mm(c['h']),
               'line': '0.3mm dash #FF0000', 'wrap': c['wrap'],
               'text': [{'p': f'NOT DRAWN {kind}', 'color': '#FF0000', 'size': 8}], 'valign': 'center'}
        return box

    def picture(self, bin_id):
        info = self.di.bins.get(bin_id)
        if not info or info[0] not in self.pk.streams:
            return None
        data = self.pk.streams[info[0]].data
        try:                                        # a picture stream is raw-deflated when the document is (HW13)
            data = fmt.inflate(data) if self.pk.compressed else data
        except Exception:
            pass
        if not data:
            data = self.pk.streams[info[0]].data
        return self.save(os.path.basename(info[0]).lower(), data)

    # ---- paragraphs
    def paragraphs(self, nodes, base=rd.DEF_CHAR):
        out = []
        for n in nodes:
            if n.tag == fmt.T['PARA_HEADER']:
                out += self.paragraph(n, base)
        return out

    def paragraph(self, p, base=rd.DEF_CHAR):
        h = p.data
        ps_id, style_id, brk = struct.unpack_from('<HBB', h, 8)
        kids = p.children
        text = next((k.data for k in kids if k.tag == fmt.T['PARA_TEXT']), b'')
        shapes = next((k.data for k in kids if k.tag == fmt.T['PARA_CHAR_SHAPE']), b'')
        ctrls = [k for k in kids if k.tag == fmt.T['CTRL_HEADER']]
        u = fmt.Units(text, shapes)
        pp = self.para_props(ps_id)
        runs, extra, floats = [], [], []
        field = link = None
        ci = 0
        cu, cnt, at = 0, 0, {}            # code unit -> content units before it (preview rules P19)
        for raw, sid, _ in u.items:
            at[cu] = cnt
            cu += len(raw) // 2
            n_runs = len(runs)
            cp = self.char(sid)
            c = u.code(raw)
            if c >= 32 or c in (fmt.TAB, fmt.LINE_BREAK):
                cnt += 0 if 0xDC00 <= c <= 0xDFFF else 1
                s = fmt.Units.text_of([[raw, sid, 0]])
                if field is not None:
                    field['t'] = field.get('t', '') + s
                    field['_cp'] = cp
                elif link is not None:
                    if runs and isinstance(runs[-1][1], dict) and runs[-1][1].get('link') == link and runs[-1][0] is cp:
                        runs[-1][1]['t'] += s
                    else:
                        runs.append((cp, {'link': link, 't': s}))
                elif runs and isinstance(runs[-1][1], str) and runs[-1][0] is cp:
                    runs[-1] = (cp, runs[-1][1] + s)
                else:
                    runs.append((cp, s))
                continue
            if c == 4:                                     # field end
                field = link = None
                continue
            if c not in fmt.EXTENDED:
                continue
            node = ctrls[ci] if ci < len(ctrls) else None
            ci += 1
            if node is None:
                continue
            cid = fmt.ctrl_id(node.data)
            if cid in ('secd', 'cold', 'head', 'foot', 'pgnp', 'pghd'):
                continue                                   # section level (section())
            if cid == 'tbl ':
                t = self.table(node, cp)
                (runs if t.get('inline') else extra).append((cp, {'table': t}))
            elif cid == 'gso ':
                item = self.gso(node, cp)
                if item is None:
                    continue
                kind, val = item
                if kind == 'pic':
                    (runs if val.get('inline', True) else extra).append((cp, {'pic': val}))
                else:
                    floats.append(val)
            elif cid == 'eqed':
                eq = self.equation(node)
                if eq:
                    runs.append((cp, {'equation': eq}))
            elif cid == '%clk':
                field = {'field': self.field_name(node), 'memo': ''}
                runs.append((cp, field))
            elif cid == '%hlk':
                link = self.field_command(node).split(';')[0].replace('\\:', ':')
            elif cid in ('fn  ', 'en  '):
                blocks = self.paragraphs(self.list_paras(node), dict(cp, size=9))
                if blocks and isinstance(blocks[0].get('p'), str) and blocks[0]['p'].startswith(' '):
                    blocks[0]['p'] = blocks[0]['p'][1:]
                runs.append((cp, {'footnote' if cid == 'fn  ' else 'endnote': blocks}))
            elif cid == 'atno':
                kind = struct.unpack_from('<I', node.data, 4)[0] & 15 if len(node.data) >= 8 else -1
                if kind == 0:                              # page number
                    runs.append((cp, {'page_num': True}))
            elif cid == 'bokm':
                runs.append((cp, {'bookmark': self.bookmark_name(node)}))
            elif cid == 'nwno':
                if len(node.data) >= 10 and struct.unpack_from('<I', node.data, 4)[0] & 15 == 0:
                    runs.append((cp, {'new_page_num': struct.unpack_from('<H', node.data, 8)[0]}))
            elif cid.startswith('%'):
                continue                                   # other fields: their text stays as text
            else:
                box = self.placeholder('ctrl/' + cid.strip(), common(node.data))
                if box:
                    floats.append(box)
            if len(runs) > n_runs and not isinstance(runs[-1][1], str) and set(runs[-1][1]) & {
                    'table', 'pic', 'footnote', 'endnote', 'page_num', 'equation'}:
                eq = runs[-1][1].get('equation')
                cnt += 0 if eq is not None and not eq.get('script') else 1
        runs = [(c, whole(s)) for c, s in runs]               # join UTF-16 surrogate halves into one character
        first_cp = next((c for c, _ in runs), None) or (extra[0][0] if extra else self.char(u.items[0][1]))
        block = rd.diff(pp, rd.DEF_PARA)
        block.pop('outline_level', None)
        block.update(rd.rel(first_cp, base))
        if brk & 0x04:
            block['page_break'] = True
        if brk & 0x08:
            block['column_break'] = True
        out = []
        for cp, item in extra:
            b = rd.diff(pp, rd.DEF_PARA)
            b.pop('outline_level', None)
            b.update(rd.rel(cp, base))
            if not out and block.get('page_break'):
                b['page_break'] = True
            b.update(item)
            out.append(b)
        if floats:
            block['shapes'] = floats
        texts = [(c, s) for c, s in runs if not (s == '' and len(runs) > 1)]
        if extra and not any(s for _, s in texts) and not floats:
            return out
        for b in out:
            b['same_para'] = True
        at[cu] = cnt
        segs = next((k.data for k in kids if k.tag == fmt.T['PARA_LINE_SEG']), b'')
        starts = [struct.unpack_from('<I', segs, k)[0] for k in range(0, len(segs) - 35, 36)]
        hints = [at.get(x) for x in starts[1:]]
        if starts and None not in hints and hints == sorted(set(hints)) and (not hints or hints[0] > 0):
            block['hangul_lines'] = hints                  # Hangul's own line starts (preview rules P19); [] = one line
        items = []
        for cp, s in texts:
            if isinstance(s, dict) and '_cp' in s:
                s = dict(s)
                cp = s.pop('_cp')
            d = rd.rel(cp, first_cp)
            if isinstance(s, str):
                if items and isinstance(items[-1], dict) and 't' in items[-1] and set(items[-1]) - {'t'} == set(d) and \
                        all(items[-1][k] == v for k, v in d.items()):
                    items[-1]['t'] += s
                    continue
                items.append(dict(t=s, **d) if d else s)
            else:
                items.append(dict(s, **d) if d else s)
        if len(items) == 1 and isinstance(items[0], str):
            block['p'] = items[0]
        elif not items:
            block['p'] = ''
        else:
            block['p'] = [(i if isinstance(i, str) or set(i) != {'t'} else i['t']) for i in items]
        out.append(block)
        return out

    @staticmethod
    def list_paras(node):
        """Paragraph nodes of the (first) list under a control."""
        return [k for k in node.children if k.tag == fmt.T['PARA_HEADER']]

    @staticmethod
    def field_command(node):
        d = node.data
        if len(d) < 11:
            return ''
        n = struct.unpack_from('<H', d, 9)[0]
        return d[11:11 + 2 * n].decode('utf-16-le', 'replace')

    def field_name(self, node):
        d = node.data
        k = 11 + 2 * struct.unpack_from('<H', d, 9)[0] + 4
        if len(d) >= k + 2:
            n = struct.unpack_from('<H', d, k)[0]
            name = d[k + 2:k + 2 + 2 * n].decode('utf-16-le', 'replace')
            return name
        return ''

    @staticmethod
    def bookmark_name(node):
        for k in node.children:
            if k.tag == fmt.T['CTRL_DATA'] and len(k.data) >= 12:
                d = k.data
                n = struct.unpack_from('<H', d, 10)[0] if len(d) >= 12 else 0
                return d[12:12 + 2 * n].decode('utf-16-le', 'replace')
        return ''

    # ---- tables
    def table(self, node, base):
        c = common(node.data) or dict(inline=False, margin=[1.0] * 4, halign='left')
        kids = node.children
        ti = next((k for k in kids if k.tag == fmt.T['TABLE']), None)
        attr, nrow, ncol = struct.unpack_from('<IHH', ti.data, 0)
        pad = struct.unpack_from('<4H', ti.data, 10)
        cells, cur = [], None
        after = False
        cap_list, cap_paras = None, []
        for k in kids:
            if k is ti:
                after = True
            elif not after and k.tag == fmt.T['LIST_HEADER']:
                cap_list = k
            elif not after and k.tag == fmt.T['PARA_HEADER']:
                cap_paras.append(k)
            elif after and k.tag == fmt.T['LIST_HEADER']:
                d = k.data
                col, row, cs, rs = struct.unpack_from('<4H', d, 8)
                w, h = (max(v, 0) for v in struct.unpack_from('<ii', d, 16))    # a form can hold a negative cell size (4294964642 = -2654): none
                m = struct.unpack_from('<4H', d, 24)
                bf = struct.unpack_from('<H', d, 32)[0]
                la = struct.unpack_from('<I', d, 4)[0]
                # a span cannot go past the table (a hostile record has up to 65535 x 65535 cells in the loops below)
                cur = dict(r=row, c=col, rs=min(rs or 1, max(nrow - row, 1)), cs=min(cs or 1, max(ncol - col, 1)), w=w, h=h, pad=m, bf=bf,
                           attr=la, paras=[])
                cells.append(cur)
            elif after and k.tag == fmt.T['PARA_HEADER'] and cur is not None:
                cur['paras'].append(k)
        cols = rd.solve([(x['c'], x['cs'], x['w']) for x in cells], ncol)
        # a row is as high as its highest cell (Hangul writes the height in one cell only; form 111171267: the empty row of 30 mm)
        heights = rd.solve([(x['r'], x['rs'], x['h']) for x in cells], nrow, largest=True)
        H, V = {}, {}

        def put(store, key, val):
            if key not in store or rd.strength(val) > rd.strength(store[key]):
                store[key] = val
        bfs = self.di.border_fills
        nob = dict(sides={k: 'none' for k in ('left', 'right', 'top', 'bottom')}, fill=None, slash=False, back=False, diag='none')
        for x in cells:
            sides = bfs.get(x['bf'], nob)['sides']
            for dc in range(x['cs']):
                put(H, (x['r'], x['c'] + dc), sides['top'])
                put(H, (x['r'] + x['rs'], x['c'] + dc), sides['bottom'])
            for dr in range(x['rs']):
                put(V, (x['r'] + dr, x['c']), sides['left'])
                put(V, (x['r'] + dr, x['c'] + x['cs']), sides['right'])
        allv = list(H.values()) + list(V.values())
        common_line = Counter(allv).most_common(1)[0][0] if allv else 'none'
        grid = [[] for _ in range(nrow)]
        hdr_rows = 0
        for x in sorted(cells, key=lambda x: (x['r'], x['c'])):
            r, cc, rs, cs = x['r'], x['c'], x['rs'], x['cs']
            bf = bfs.get(x['bf'], nob)
            cell = {}
            if rs > 1:
                cell['rs'] = rs
            if cs > 1:
                cell['cs'] = cs
            own = {'top': H[(r, cc)], 'bottom': H[(r + rs, cc)], 'left': V[(r, cc)], 'right': V[(r, cc + cs)]}
            border = {k: v for k, v in own.items() if v != common_line}
            if border:
                cell['border'] = border
            if bf['fill']:
                cell['fill'] = bf['fill']
            if bf['slash'] or bf['back']:
                cell['diag'] = 'both' if bf['slash'] and bf['back'] else ('slash' if bf['slash'] else 'back')
                cell['diag_line'] = bf['diag']
            va = ['top', 'center', 'bottom'][min(x['attr'] >> 5 & 3, 2)]
            if va != 'center':
                cell['valign'] = va
            if x['attr'] >> 16 & 1:
                cell['pad'] = [mm(v) for v in x['pad']]
            if x['attr'] >> 18 & 1:
                cell['header'] = True
            blocks = self.paragraphs(x['paras'], base)
            simple = blocks and (len(blocks) == 1 or not any('hangul_lines' in b for b in blocks)) and \
                all(set(b) - {'p'} == set(blocks[0]) - {'p'} and all(b[k] == blocks[0][k] for k in b if k != 'p')
                    and isinstance(b.get('p'), str) for b in blocks)
            if simple:
                cell.update({k: v for k, v in blocks[0].items() if k != 'p'})
                cell['p'] = '\n'.join(b['p'] for b in blocks)
            else:
                cell['blocks'] = blocks
            if 0 <= r < nrow:
                grid[r].append(cell if set(cell) != {'p'} else cell['p'])
        t = dict(cols=[mm(v) for v in cols], heights=[mm(v) for v in heights], border=common_line, rows=grid)
        if list(pad) != [510, 510, 141, 141]:
            t['pad'] = [mm(v) for v in pad]
        if c['inline']:
            t['inline'] = True
            if any(c['margin']):
                t['margin'] = c['margin']
        else:
            t['inline'] = False          # a table that flows: written out, because a table without `inline` is a character (table/inline.py)
            if c['margin'] != [1.0, 1.0, 1.0, 1.0]:
                t['margin'] = c['margin']
            if c['halign'] != 'left':
                t['align'] = c['halign']
        if not c['inline']:
            p = self.flow_pos(c)
            if p and self.runs_with_text(c):     # Hangul flows it and cuts it at page ends: the preview turns pos into margins
                t['pos'] = dict(p, flow=True)
            elif p:
                t['pos'] = p
        if cap_list is not None:
            t['caption'] = self.caption(cap_list, cap_paras)
        pb = attr & 3
        if pb != 2:
            t['page_break'] = {0: 'none', 1: 'table', 2: 'cell'}.get(pb, 'cell')
        if not attr >> 2 & 1:
            t['repeat_header'] = False
        if not c['inline'] and c.get('wrap', 'top_and_bottom') != 'top_and_bottom':
            t['wrap'] = c['wrap']
        hdr = 0                     # Hangul repeats the title rows at the top of the table only (HW21)
        for row in grid:
            if not (row and all(isinstance(c, dict) and c.get('header') for c in row)):
                break
            hdr += 1
        for row in grid:
            for c in row:
                if isinstance(c, dict):
                    c.pop('header', None)
        if hdr:
            t['header_rows'] = hdr
        return t

    @staticmethod
    def runs_with_text(c):
        """A block table that takes its place in the text (자리 차지), anchored to its paragraph, moving with the text,
        at the left of its column: Hangul lays it out in the text flow and cuts it at page ends, whatever its
        offsets (HW21; a 138-row table of a 103-page document)."""
        return (c['wrap'] == 'top_and_bottom' and c['vrel'] == 'para' and c['hrel'] in ('column', 'para') and c['flow']
                and c['vpos'] == 'top' and c['halign'] == 'left' and c['x'] >= 0 and c['y'] >= 0)

    @staticmethod
    def flow_pos(c):
        """A block table's floating position (as table.ext.read_pos), or None for a plain flow table."""
        a = c['attr']
        flow, overlap, affect = bool(a >> 13 & 1), bool(a >> 14 & 1), bool(a >> 2 & 1)
        if (c['vrel'], c['hrel'], c['vpos'], flow, overlap, affect, c['x'], c['y']) == ('para', 'column', 'top', True, False,
                                                                                       False, 0, 0):
            return None
        d = {'x': mm(c['x']), 'y': mm(c['y'])}
        if c['vrel'] == c['hrel']:
            d['rel'] = c['vrel']
        else:
            d['vrel'], d['hrel'] = c['vrel'], c['hrel']
        if c['vpos'] != 'top':
            d['valign'] = c['vpos']
        if c['halign'] != 'left':
            d['halign'] = c['halign']
        for key, val, default in (('flow', flow, False), ('overlap', overlap, True), ('affect', affect, False)):
            if val != default:
                d[key] = val
        return d

    def caption(self, lst, paras):
        """Table caption (as table.ext.read_caption): side, label, number, text, gap, width."""
        d = lst.data
        attr = struct.unpack_from('<I', d, 8)[0] if len(d) >= 12 else 3
        width = struct.unpack_from('<I', d, 12)[0] if len(d) >= 16 else 8504
        gap = struct.unpack_from('<H', d, 16)[0] if len(d) >= 18 else 850
        out = {'side': ['left', 'right', 'top', 'bottom'][attr & 3]}
        before = after = ''
        number = False
        for p in paras:
            text = next((k.data for k in p.children if k.tag == fmt.T['PARA_TEXT']), b'')
            ctrls = [k for k in p.children if k.tag == fmt.T['CTRL_HEADER']]
            u, ci = fmt.Units(text, b''), 0
            for raw, _, _ in u.items:
                code = u.code(raw)
                if code in fmt.EXTENDED:
                    if ci < len(ctrls) and fmt.ctrl_id(ctrls[ci].data) == 'atno':
                        number = True
                    ci += 1
                elif code >= 32:
                    s = fmt.Units.text_of([[raw, 0, 0]])
                    if number:
                        after += s
                    else:
                        before += s
        if number:
            out.update(label=before.rstrip(), number=True, text=after[1:] if after.startswith(' ') else after)
        else:
            out.update(label='', number=False, text=before)
        if gap != 850:
            out['gap'] = mm(gap)
        if width != 8504:
            out['width'] = mm(width)
        return out

    # ---- drawing objects
    def gso(self, node, cp):
        c = common(node.data)
        sc = next((k for k in node.children if k.tag == fmt.T['SHAPE_COMPONENT']), None)
        if sc is None or c is None:
            return None
        kind = sc.data[:4][::-1].decode('latin-1')
        pic = next((k for k in sc.children if k.tag == fmt.T['SHAPE_COMPONENT_PICTURE']), None)
        if kind == '$pic' and pic is not None and len(pic.data) >= 73:
            bid = struct.unpack_from('<H', pic.data, 71)[0]
            name = self.picture(bid)
            if name is None:
                return ('shape', self.placeholder('picture without data', c))
            d = {'src': name, 'w': mm(c['w']), 'h': mm(c['h'])}
            bcol, bw, bprop = struct.unpack_from('<IiI', pic.data, 0)
            if bprop & 63:
                names = docinfo.LINE_TYPES
                d['border'] = f'{round(bw / HU, 3)}mm {names[bprop & 63] if (bprop & 63) < len(names) else "solid"} {docinfo.color(bcol)}'
            if not c['inline']:
                d['inline'] = False
                d['pos'] = {'x': mm(c['x']), 'y': mm(c['y']), 'rel': c['vrel']}
                if c['flow']:
                    d['pos']['flow'] = True
                d['wrap'] = c['wrap']
                if c['side'] != 'both_sides':
                    d['side'] = c['side']
            return ('pic', d)
        shape = {'$rec': 'rect', '$ell': 'ellipse', '$lin': 'line'}.get(kind)
        lst = next((k for k in sc.children if k.tag == fmt.T['LIST_HEADER']), None)
        if shape is None:
            box = self.placeholder('object ' + kind.strip('$'), c)
            return ('shape', box) if box else None
        d = {'type': shape, 'x': mm(c['x']), 'y': mm(c['y']), 'rel': c['vrel'], 'line': self.shape_line(sc),
             'wrap': c['wrap']}
        if c['side'] != 'both_sides':
            d['side'] = c['side']
        if shape == 'line':
            ln = next((k for k in sc.children if k.tag == fmt.T['SHAPE_COMPONENT_LINE']), None)
            sx, sy, ex, ey = struct.unpack_from('<4i', ln.data, 0) if ln is not None and len(ln.data) >= 16 else (0, 0, c['w'], c['h'])
            d.update(x=mm(c['x'] + sx), y=mm(c['y'] + sy), x2=mm(c['x'] + ex), y2=mm(c['y'] + ey))
            heads = self.shape_arrows(sc)
            if any(heads):
                d['arrow'] = 'both' if all(heads) else ('start' if heads[0] else 'end')
        else:
            d.update(w=mm(c['w']), h=mm(c['h']))
            fill = self.shape_fill(sc)
            if fill:
                d['fill'] = fill
            rc = next((k for k in sc.children if k.tag == fmt.T['SHAPE_COMPONENT_RECTANGLE']), None)
            if shape == 'rect' and rc is not None and rc.data[:1] not in (b'', b'\x00'):
                d['round'] = rc.data[0]
            if lst is not None:
                paras = [k for k in sc.children if k.tag == fmt.T['PARA_HEADER']]
                d['text'] = self.paragraphs(paras, cp)
                la = struct.unpack_from('<I', lst.data, 4)[0] if len(lst.data) >= 8 else 0
                d['valign'] = ['top', 'center', 'bottom'][min(la >> 5 & 3, 2)]
                if len(lst.data) >= 16:
                    d['pad'] = [mm(v) for v in struct.unpack_from('<4H', lst.data, 8)]
        return ('shape', d)

    @staticmethod
    def _after_matrices(d):
        """Offset of the line info in a SHAPE_COMPONENT (after the ids, sizes and the transform matrices)."""
        k = 8 if d[:4] == d[4:8] else 4
        k += 4 + 4 + 2 + 2 + 16 + 4 + 2 + 4 + 4
        if len(d) < k + 2:
            return None
        n = struct.unpack_from('<H', d, k)[0]
        return k + 2 + 48 + n * 96

    def shape_line(self, sc):
        k = self._after_matrices(sc.data)
        if k is None or len(sc.data) < k + 12:
            return '0.12mm solid #000000'
        col, width, prop = struct.unpack_from('<IiI', sc.data, k)
        style = prop & 63
        if style == 0:
            return 'none'
        names = docinfo.LINE_TYPES
        return f'{round(width / HU, 2)}mm {names[style] if style < len(names) else "solid"} {docinfo.color(col)}'

    def shape_arrows(self, sc):
        k = self._after_matrices(sc.data)
        if k is None or len(sc.data) < k + 12:
            return (False, False)
        prop = struct.unpack_from('<I', sc.data, k + 8)[0]
        return (bool(prop >> 10 & 63), bool(prop >> 16 & 63))

    def shape_fill(self, sc):
        k = self._after_matrices(sc.data)
        if k is None or len(sc.data) < k + 13 + 4:
            return None
        k += 13
        ft = struct.unpack_from('<I', sc.data, k)[0]
        if ft & 1 and len(sc.data) >= k + 8:
            v = docinfo.color(struct.unpack_from('<I', sc.data, k + 4)[0])
            return None if v == 'none' else v
        return None

    def equation(self, node):
        eq = next((k for k in node.children if k.tag == fmt.T['EQEDIT']), None)
        c = common(node.data)
        if eq is None:
            return None
        r = docinfo.Reader(eq.data)
        r.u('I')
        script = r.wstr()
        size = r.u('I') if r.left() >= 4 else 1000
        col = r.u('I') if r.left() >= 4 else 0
        base = r.u('h') if r.left() >= 2 else 66
        return {'script': script, 'size': round(size / 100, 2), 'color': docinfo.color(col), 'font': 'HancomEQN',
                'baseline': base, 'w': mm(c['w']) if c else 0, 'h': mm(c['h']) if c else 0}

    # ---- sections
    def section(self, recs):
        root = tree(recs)
        sec = {}
        paras = [n for n in root.children if n.tag == fmt.T['PARA_HEADER']]
        for p in paras:
            for k in p.children:
                if k.tag != fmt.T['CTRL_HEADER']:
                    continue
                cid = fmt.ctrl_id(k.data)
                if cid == 'secd' and 'page' not in sec:
                    self.section_def(k, sec)
                elif cid == 'cold' and 'columns' not in sec:
                    self.columns(k, sec)
                elif cid in ('head', 'foot'):
                    apply = struct.unpack_from('<I', k.data, 4)[0] & 3 if len(k.data) >= 8 else 0
                    blocks = self.paragraphs(self.list_paras(k))
                    key = 'header' if cid == 'head' else 'footer'
                    if apply == 0:
                        sec[key] = blocks
                    else:
                        sec[key + ('_even' if apply == 1 else '_odd')] = blocks
                elif cid == 'pgnp' and len(k.data) >= 12:
                    attr = struct.unpack_from('<I', k.data, 4)[0]
                    pos = ['none', 'top_left', 'top_center', 'top_right', 'bottom_left', 'bottom_center', 'bottom_right',
                           'outside_top', 'outside_bottom', 'inside_top', 'inside_bottom']
                    side = k.data[16:18].decode('utf-16-le', 'replace') if len(k.data) >= 18 else '-'
                    sec['page_number'] = {'pos': pos[min(attr >> 8 & 15, 10)],
                                          'format': ['digit', 'circled_digit', 'roman_capital', 'roman_small',
                                                     'latin_capital', 'latin_small'][min(attr & 255, 5)],
                                          'side': side.strip('\x00') or '-'}
        sec['body'] = self.paragraphs(paras)
        return sec

    def section_def(self, k, sec):
        pd = next((x for x in k.children if x.tag == fmt.T['PAGE_DEF']), None)
        if pd is not None and len(pd.data) >= 40:
            w, h, ml, mr, mt, mb, mh, mf, mg, attr = struct.unpack_from('<10I', pd.data, 0)
            page = {'size': 'A4'} if (w, h) == (59528, 84186) else {'size': [mm(w), mm(h)]}
            if attr & 1:
                page['landscape'] = True
            page['margin'] = {'left': mm(ml), 'right': mm(mr), 'top': mm(mt), 'bottom': mm(mb), 'header': mm(mh),
                              'footer': mm(mf)}
            if mg:
                page['margin']['gutter'] = mm(mg)
            if struct.unpack_from('<I', k.data, 4)[0] >> 19 & 1:
                page['hide_empty_line'] = True
            if len(k.data) >= 22:
                start = struct.unpack_from('<H', k.data, 20)[0]
                if start:
                    page['start_page'] = start
            sec['page'] = page
        pbf = [x for x in k.children if x.tag == fmt.T['PAGE_BORDER_FILL']]
        if pbf and len(pbf[0].data) >= 14:
            attr = struct.unpack_from('<I', pbf[0].data, 0)[0]
            off = struct.unpack_from('<4h', pbf[0].data, 4)
            bf_id = struct.unpack_from('<H', pbf[0].data, 12)[0]
            bf = self.di.border_fills.get(bf_id)
            if bf and bf_id != 1 and (any(v != 'none' for v in bf['sides'].values()) or bf['fill']):
                sec['page_border'] = {'border': {s: v for s, v in bf['sides'].items() if v != 'none'}, 'fill': bf['fill'],
                                      'offset': [mm(v) for v in off],
                                      'text_border': 'paper' if attr & 1 else 'content',
                                      'fill_area': ['paper', 'page', 'border'][min(attr >> 3 & 3, 2)],
                                      'header_inside': bool(attr >> 1 & 1), 'footer_inside': bool(attr >> 2 & 1)}

    def columns(self, k, sec):
        d = k.data
        if len(d) < 8:
            return
        attr, gap = struct.unpack_from('<HH', d, 4)
        count = attr >> 2 & 255 or 1
        kind = attr & 3
        if count > 1 or kind:
            c = {'count': count, 'gap': mm(gap)}
            if kind:
                c['type'] = {1: 'balanced', 2: 'parallel'}.get(kind, 'newspaper')
            sec['columns'] = c


def read(path, out_json=None, placeholders=False):
    """HWP file -> spec dict (pictures saved next to out_json, or in a temp folder)."""
    from ..core import tmpdir
    pk = fmt.Package(path)
    out_dir = os.path.dirname(os.path.abspath(out_json)) if out_json else tmpdir.mkdtemp('hwp5_spec_')
    conv = Conv(pk, out_dir, placeholders)
    secs = [conv.section(pk.records(s)) for s in pk.sections]
    spec = {'sections': secs} if len(secs) > 1 else secs[0]
    spec['_not_drawn'] = conv.not_drawn
    return spec


def main(args):
    if len(args) < 3:
        print(__doc__)
        return 2
    cmd, src, dst = args[0], args[1], args[2]
    if cmd != 'tospec':
        print(__doc__)
        return 2
    spec = read(src, dst)
    spec.pop('_not_drawn', None)
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print('SPEC WRITTEN', dst)
    for k, v in unsupported.items():
        print('UNSUPPORTED', k, v, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
