"""Page model of pagefit: a document -> pages, the way Hangul lays them out when keep rules are on.

`load(path)` gives a spec (HWPX -> `core.read`, JSON -> as written; `class` and named styles resolved for the layout only) and the
directory of its pictures. `pages(spec, pic_dir)` runs the block atoms of the preview (`registry.backend('blocks', 'preview')`: heights
of lines and table rows, the same numbers as the preview's pages) through a paginator that applies the paragraph rules of the
blocks: `page_break` / `page_break_before`, `keep_next`, `keep_lines`, `widow` (no single line at the bottom or the top of a page).
The preview itself ignores these rules (it breaks at the first line that does not fit), so with every rule off the pages are
the preview's pages.

A section that has more than one column, a column change, footnotes or objects that text goes around is laid out by the preview's own
flow instead (`registry.backend('pagereport', 'preview')`, preview/report.py: the pages as the preview draws them, items per page,
fill = text and footnotes over the capacity of the columns). The flow applies the keep rules since preview rule P17 (`page_report.keep_rules`
is True); every section is read from it when it gives the pages of this paginator on the canary documents (`renderer_matches`: the
cases measured against Hangul), else only the sections that need it. A vertical-writing section is skipped (`Page.skipped`).
"""
from ..core import tmpdir
import json
import os
import re
from collections import Counter

from ..core import read, registry
from ..core.layout import Layout

EPS = 0.05


class Page:
    def __init__(self, section, no, y0, y1, why, columns=1):
        self.section, self.no, self.y0, self.y1, self.why, self.columns = section, no, y0, y1, why, columns
        self.items = []          # (block index, first row, end row)  end exclusive
        self.hs = []             # the height (mm) of each item
        self.used = 0.0          # mm of text (and footnotes) summed over the columns, spacing under the last line not counted
        self.skipped = False
        self.renderer = False    # the page comes from the preview's flow (columns, footnotes, objects)
        self.notes_cont = False  # a footnote goes on at the next page (preview flow pages only)
        self.deferred = []       # blocks (tables kept whole) that wait for a later page while the text after them stays here

    @property
    def y_end(self):
        return self.y0 + self.used / self.columns

    @property
    def fill(self):
        return self.used / (self.columns * (self.y1 - self.y0))

    @property
    def free(self):
        return (self.columns * (self.y1 - self.y0) - self.used) / self.columns


def load(path):
    """(spec, pic_dir) of a .hwpx or a .json spec; the spec's `body` blocks are what findings and fixes address."""
    tmp = tmpdir.mkdtemp('hwpx_pagefit_')
    if path.lower().endswith('.json'):
        spec = json.load(open(path, encoding='utf-8'))
        from ..table import inline
        inline.resolve(spec)                      # a table without `inline` is a character unless it flows (TB11): the layout sees what the builder writes
        return spec, os.path.dirname(os.path.abspath(path))
    return read.read(path, os.path.join(tmp, 'spec.json')), tmp


def _heights(b, size0):
    """Row heights (mm) of a table block that has none: what the builder writes (lines x size x line spacing + cell margins; Hangul
    then grows a row for wrapped text, the preview does too). A spec that went through Hangul or `core.read` has them."""
    t = b['table']
    pad = t.get('pad')
    top_bottom = (141 * 2 / 283.465) if pad is None else sum(quad_mm(pad)[2:4])
    dflt = t.get('cell') or {}
    out = []
    for row in t.get('rows', []):
        est = 0.0
        for c in row:
            cell = c if isinstance(c, dict) else {'p': c}
            if int(cell.get('rs', 1)) != 1:
                continue
            p = cell.get('p', '')
            lines = max(1, len(p.split(chr(10)))) if isinstance(p, str) else 1
            ln = cell.get('line', dflt.get('line', b.get('line', 160)))
            est = max(est, lines * float(cell.get('size', dflt.get('size', b.get('size', size0)))) * 25.4 / 72 * (ln if isinstance(ln, (int, float)) else 160) / 100)
        out.append(round(est + top_bottom, 3))
    return out


def quad_mm(v):
    v = v if isinstance(v, (list, tuple)) else [v]
    v = list(v) * 4 if len(v) == 1 else [v[0], v[0], v[1], v[1]] if len(v) == 2 else list(v)
    return [float(str(x).rstrip('mm')) for x in v]


def resolved(spec):
    """A copy of the spec whose body blocks have their `class` and `style` props in place and whose tables have row heights (for the
    layout only; the caller's spec is not changed)."""
    lay = Layout(spec)
    size0 = float((spec.get('defaults') or {}).get('size', 10))

    def one(b):
        if not isinstance(b, dict):
            return {'p': b} if isinstance(b, str) else b
        b = lay.eff(b)
        t = b.get('table')
        if isinstance(t, dict) and not t.get('heights') and t.get('rows'):
            b = dict(b, table=dict(t, heights=_heights(b, size0)))
        return b
    out = dict(spec)
    secs = spec.get('sections')
    if secs:
        out['sections'] = [dict(s, body=[one(b) for b in s.get('body', [])]) for s in secs]
    else:
        out['body'] = [one(b) for b in spec.get('body', [])]
    return out


def row_groups(block):
    """Row indexes where a table may NOT be cut: before row k when a cell with `rs` > 1 spans the rows above and below the cut."""
    t = block.get('table') if isinstance(block, dict) else None
    if not isinstance(t, dict):
        return set()
    iv = [(r, r + int(c['rs']) - 1) for r, row in enumerate(t.get('rows', [])) for c in row if isinstance(c, dict) and int(c.get('rs', 1)) > 1]
    bad = set()
    for a, b in iv:
        bad.update(range(a + 1, b + 1))
    return bad


def sections_of(spec):
    return spec.get('sections') or [spec]


def flags(b):
    b = b if isinstance(b, dict) else {}
    return dict(keep_next=bool(b.get('keep_next')), keep_lines=bool(b.get('keep_lines')), widow=bool(b.get('widow')))


def text_of(b, n=24):
    p = b.get('p', '') if isinstance(b, dict) else b
    if isinstance(p, list):
        p = ''.join(x if isinstance(x, str) else x.get('t', '') if isinstance(x, dict) else '' for x in p)
    if not p and isinstance(b, dict) and 'table' in b:
        p = '[표]'
    p = re.sub(r'\s+', ' ', str(p)).strip()
    return p[:n] + ('…' if len(p) > n else '')


def body_size(spec):
    c = Counter()
    for s in sections_of(spec):
        for b in s.get('body', []):
            if isinstance(b, dict) and isinstance(b.get('p'), (str, list)) and text_of(b, 80):
                c[float(b.get('size', spec.get('defaults', {}).get('size', 10)))] += len(text_of(b, 400))
    return c.most_common(1)[0][0] if c else 10.0


def is_heading(b, size):
    """A heading: an outline level, a style called 개요/제목, or short bold text bigger than the body text (keep_next is NOT a sign: fix sets it)."""
    t = b.get('table') if isinstance(b, dict) else None
    if isinstance(t, dict):                      # a heading box: a table of one cell that holds a heading
        rows = t.get('rows') or []
        c = rows[0][0] if len(rows) == 1 and len(rows[0]) == 1 else None
        blocks = (c.get('blocks') or [c]) if isinstance(c, dict) else []
        f = blocks[0] if blocks and isinstance(blocks[0], dict) else {}
        if not text_of(f, 80) or len(text_of(f, 200)) > 60:
            return False
        runs = f['p'] if isinstance(f.get('p'), list) else [f.get('p')]
        bold = bool(f.get('bold')) or all(isinstance(r, dict) and r.get('bold') for r in runs if not (isinstance(r, str) and not r.strip()))
        return is_heading(f, size) or (bold and float(f.get('size', size)) >= size + 0.5)
    if not isinstance(b, dict) or 'p' not in b or not text_of(b, 80):
        return False
    if b.get('outline_level') is not None or re.match(r'(개요|제목|heading|title)', str(b.get('style', '')), re.I):
        return True
    runs = b['p'] if isinstance(b['p'], list) else [b['p']]
    bold = bool(b.get('bold')) or all(isinstance(r, dict) and r.get('bold') for r in runs if not (isinstance(r, str) and not r.strip()))
    return bold and float(b.get('size', size)) >= size + 1.5 and len(text_of(b, 200)) <= 60


def section_info(spec, pic_dir='.'):
    """Per section: the resolved body blocks, the height of each block (mm) and the body height of a page, as the preview lays them out
    (the units of units.py are measured with them)."""
    res = resolved(spec)
    secs = sections_of(res)
    out = []
    for sec in registry.backend('blocks', 'preview')(res, pic_dir):
        out.append(dict(index=sec['index'], body=secs[sec['index']].get('body', []),
                        heights=[sum(a['h'] for a in b['atoms']) for b in sec['blocks']], cap=sec['geom']['y1'] - sec['geom']['y0']))
    return out


FLOW_KEYS = {'columns_here', 'footnote', 'endnote', 'shapes', 'shape', 'same_para'}


def uses_flow(sec):
    """True when the section needs the preview's own flow: columns, a column change, footnotes or endnotes, floating objects
    (shapes, a picture or object that is not `inline`, a table with `pos`, `same_para`)."""
    if (sec.get('columns') or {}).get('count', 1) > 1:
        return True

    def walk(o):
        if isinstance(o, dict):
            if FLOW_KEYS & set(o) or o.get('inline') is False or isinstance(o.get('pos'), dict)                     or ('xml' in o and isinstance(o['xml'], str) and '<hp:colPr' in o['xml']):
                return True
            return any(walk(v) for v in o.values())
        if isinstance(o, list):
            return any(walk(v) for v in o)
        return False
    return walk(sec.get('body', []))


def renderer_keeps():
    """True when the preview's flow applies the keep rules itself (`page_report.keep_rules`)."""
    fn = registry.backend('pagereport', 'preview')
    return bool(fn and getattr(fn, 'keep_rules', False))


_CANARY = '본문 줄입니다. '


def _canaries():
    """Small documents on which Hangul's behaviour was measured (rules PF02): a keep_next that Hangul leaves alone, a table that is not
    cut, merged rows, a repeated header, a paragraph that keeps with a table (no effect)."""
    def para(n, **k):
        return dict({'p': _CANARY * n, 'after': 6}, **k)

    def tbl(n, **k):
        t = {'cols': [40, 60, 60], 'rows': [['열0', '열1', '열2']] + [[f'가{i}', f'나{i}', f'다{i}'] for i in range(n)],
             'header_rows': 1, 'repeat_header': True, 'page_break': 'table', 'border': '0.4mm solid #000000'}
        t.update(k)
        return {'table': t}
    box = {'table': {'cols': [85, 85], 'rows': [['가', '나'], ['다', '라']], 'border': '0.4mm solid #000000'}, 'keep_next': True}
    merged = tbl(0, rows=[['열0', '열1', '열2']] + [[{'p': f'병합{i}', 'rs': 4}, f'나{i}', f'다{i}'] if i % 4 == 0 else [f'나{i}', f'다{i}']
                                                      for i in range(72)])
    return [
        {'body': [{'p': _CANARY * 12, 'after': 6} for _ in range(17)] + [{'p': _CANARY * 8, 'after': 4, 'keep_next': True},
                                                                         {'p': _CANARY * 12, 'after': 6}]},
        {'body': [para(12) for _ in range(3)] + [tbl(70)]},
        {'body': [para(12) for _ in range(3)] + [merged]},
        {'body': [para(12) for _ in range(14)] + [tbl(14, page_break='none')]},
        {'body': [para(12) for _ in range(13)] + [para(12, keep_next=True), tbl(14, page_break='none')]},
        {'body': [para(12) for _ in range(16)] + [box, para(12), para(12)]},       # a table with keep_next at the page end goes with the next paragraph (E3)
    ]


_match = {}


def renderer_matches():
    """True when the preview's flow gives the pages of this module's paginator (within 1.5 mm) on the canary documents: then every
    section is read from the flow; otherwise only the sections that need it (columns, footnotes, objects). Checked once per run."""
    if 'ok' not in _match:
        ok = renderer_keeps()
        for sp in (_canaries() if ok else []):
            try:
                a, b = pages(sp, '.', 'own'), pages(sp, '.', 'renderer')
            except Exception:
                ok = False
                break
            if len(a) != len(b) or any(abs(x.used - y.used) > 1.5 for x, y in zip(a, b)):
                ok = False
                break
        _match['ok'] = ok
    return _match['ok']


def _table_carry_ok():
    """True when the preview's flow carries a table that keeps with the next paragraph (`keep_next`, at the page end) to the next page,
    as Hangul does (measured with a 2 x 2 table: the whole table goes; a heading box is such a table). Checked once per run."""
    if 'carry' not in _match:
        sp = _canaries()[5]
        a, b = pages(sp, '.', 'own'), pages(sp, '.', 'renderer', carry=False)
        _match['carry'] = len(a) == len(b) and all(abs(x.used - y.used) <= 1.5 for x, y in zip(a, b))
    return _match['carry']


def _carried(secs, report, need):
    """[(section, block)]: a whole table with keep_next that ends a page of the flow while the next block is a paragraph on the next
    page. Hangul would carry it over; the flow does not (see _table_carry_ok)."""
    hits = []
    for s, sec in enumerate(secs):
        if not need[s]:
            continue
        pgs = [r for r in report if r['section'] == s]
        body = sec.get('body', [])
        for r, nxt in zip(pgs, pgs[1:]):
            if len(r['items']) < 2 or not nxt['items']:
                continue
            it = r['items'][-1]
            b, first = body[it['block']], nxt['items'][0]
            if isinstance(b, dict) and isinstance(b.get('table'), dict) and b.get('keep_next') and it['k0'] == 0 \
                    and it['k1'] == len(b['table'].get('rows', [])) and first['block'] == it['block'] + 1 and first['k0'] == 0 \
                    and first['block'] < len(body) and isinstance(body[first['block']], dict) and 'p' in body[first['block']] \
                    and 'table' not in body[first['block']]:
                hits.append((s, it['block']))
    return hits


def pages(spec, pic_dir='.', source=None, carry=True):
    """All pages of the document (every section): the paginator of this module for a plain section, the preview's flow for one that
    uses columns, footnotes or floating objects (see the module text), and for every section when the flow applies Hangul's keep rules
    the way this module's paginator does (`renderer_matches`). source 'renderer' forces the flow for all, 'own' this module's paginator
    wherever it can (a flow section still comes from the flow). A flow that does not carry a table with keep_next to the next page is
    run again with a page break before such a table, so that its pages are Hangul's (`carry` False: no such correction)."""
    fn = registry.backend('blocks', 'preview')
    rep_fn = registry.backend('pagereport', 'preview')
    if fn is None:
        raise RuntimeError('the preview package gives no block atoms (backend blocks/preview)')
    res = resolved(spec)
    secs = sections_of(res)
    use_all = rep_fn is not None and (source == 'renderer' or (source is None and renderer_matches()))
    need = [use_all or uses_flow(s) for s in secs]
    report = [p for p in rep_fn(res, pic_dir)] if rep_fn and any(need) else []
    injected = set()
    if report and carry and not _table_carry_ok():
        for _ in range(8):
            hits = [h for h in _carried(secs, report, need) if h not in injected]
            if not hits:
                break
            for s, bi in hits:
                secs[s]['body'][bi] = dict(secs[s]['body'][bi], page_break_before=True)
                injected.add((s, bi))
            report = [p for p in rep_fn(res, pic_dir)]
    out = []
    for sec in fn(res, pic_dir):
        i = sec['index']
        if secs[i].get('text_direction') in ('vertical', 'vertical_all'):
            pg = Page(i, len(out) + 1, sec['geom']['y0'], sec['geom']['y1'], 'start')
            pg.skipped = True
            out.append(pg)
        elif need[i] and rep_fn:
            for r in [r for r in report if r['section'] == i]:
                pg = Page(i, len(out) + 1, r['y0'], r['y1'], r['why'], r['columns'])
                if r['items'] and (i, r['items'][0]['block']) in injected and r['why'] == 'forced_break':
                    pg.why = 'keep_next'                      # the break is the model's own (a carried table), not the document's
                pg.items = [(it['block'], it['k0'], it['k1']) for it in r['items']]
                pg.hs = [it['h'] for it in r['items']]
                pg.used, pg.renderer, pg.notes_cont = r['used'], True, r.get('notes_cont', False)
                pg.deferred = [b for b in r.get('deferred', []) if b is not None]
                out.append(pg)
        else:
            out += paginate(sec, len(out) + 1)
    return out


def paginate(sec, first_no=1):
    """One section -> pages. The atoms (text lines, table rows) of the blocks are cut into pages greedily; a cut that Hangul would not
    make is moved up, atom by atom, until it is allowed (measured against Hangul pages, rules PF02):
      keep_next   the LAST line of a block stays with the first line of the next block (a one-line block moves as a whole, and then the
                  block before it, when it keeps with next too, gives up its last line as well);
      keep_lines  a paragraph that fits on a page is not cut;   widow   no single line of a paragraph at the bottom or the top;
      tables      cut between rows only, not inside merged rows (`rs`), not at all when `page_break` is `none` and the table fits on
                  a page; the header rows (`header_rows`, `repeat_header`) come again on the next page;
      a forced break (`page_break`, `page_break_before`) starts a page unless the block is first on one."""
    g = sec['geom']
    y0, y1 = g['y0'], g['y1']
    cap = y1 - y0
    flat, info = [], {}
    for b in sec['blocks']:
        if not b['atoms']:
            continue
        blk = b['block'] if isinstance(b['block'], dict) else {}
        f = flags(blk)
        t = blk.get('table') if isinstance(blk.get('table'), dict) else {}
        n = len(b['atoms'])
        height = sum(a['h'] for a in b['atoms'])
        lines = sum(a['line'] for a in b['atoms'])
        rows_ok = bool(t) and len(b['atoms']) == len(t.get('rows', []))
        info[b['index']] = dict(
            start=len(flat), n=n, lines=lines, keep_next=f['keep_next'], widow=f['widow'] and lines >= 2 and b['atoms'][0]['line'],
            keep_lines=(f['keep_lines'] or t.get('page_break') == 'none') and height <= cap, bad=row_groups(blk) if rows_ok else set(),
            hdr=(sum(a['h'] for a in b['atoms'][:int(t.get('header_rows', 0) or 0)])
                 if t and t.get('repeat_header', True) else 0.0))
        for k, a in enumerate(b['atoms']):
            flat.append(dict(a, bi=b['index'], k=k))
    pages_out = []

    def new(why):
        pg = Page(sec['index'], first_no + len(pages_out), y0, y1, why)
        pages_out.append(pg)
        return pg

    def allowed(s, c):
        """Why a page that holds atoms s..c may NOT end there, or None."""
        if c + 1 >= len(flat):
            return None
        a, b = flat[c], flat[c + 1]
        if a['bi'] == b['bi']:
            i = info[a['bi']]
            if i['keep_lines']:
                return 'keep_lines'
            if i['bad'] and b['k'] in i['bad']:
                return 'table_group'
            if i['widow']:
                before = c - max(i['start'], s) + 1 if i['start'] >= s else None
                after = i['start'] + i['n'] - 1 - c
                if after == 1 or (before == 1 and i['start'] >= s):
                    return 'widow'
            return None
        if info[a['bi']]['keep_next'] and a['k'] == info[a['bi']]['n'] - 1 and b['line']:      # not toward a table or an object (measured)
            return 'keep_next'
        return None
    s, n = 0, len(flat)
    while s < n:
        cur = new('start' if not pages_out else 'overflow')
        y = y0 + (info[flat[s]['bi']]['hdr'] if flat[s]['k'] > 0 and flat[s]['bi'] == flat[s - 1]['bi'] else 0.0) if s else y0
        top = y
        e = s - 1                                  # last atom that fits (at least one)
        while e + 1 < n:
            a = flat[e + 1]
            if e + 1 > s and a['keep'] == 'break':
                break
            if y + a['h'] - a['trail'] > y1 + EPS and e >= s:
                break
            y += a['h']
            e += 1
        c, why = e, None
        if e + 1 < n and not (flat[e + 1]['keep'] == 'break'):
            while c >= s:
                bad = allowed(s, c)
                if bad is None:
                    break
                why = why or bad
                # keep_next: the whole part of the block that is on this page goes on (measured: Hangul does not leave one line)
                c = max(info[flat[c]['bi']]['start'], s) - 1 if bad == 'keep_next' else c - 1
            if c < s:                              # nothing can be cut: Hangul gives up the rule
                c, why = e, None
        if c < s:
            c = s
        for bi in dict.fromkeys(f['bi'] for f in flat[s:c + 1]):
            ks = [f['k'] for f in flat[s:c + 1] if f['bi'] == bi]
            cur.items.append((bi, ks[0], ks[-1] + 1))
            cur.hs.append(sum(f['h'] for f in flat[s:c + 1] if f['bi'] == bi))
        used_end = top + sum(f['h'] for f in flat[s:c + 1])
        cur.used = used_end - flat[c]['trail'] - y0
        s = c + 1
        if s < n:                                  # why the NEXT page starts: the rule that moved the cut, a forced break, a split
            cur._why_next = why or ('forced_break' if flat[s]['keep'] == 'break' else
                                    'split' if flat[s]['bi'] == flat[c]['bi'] else 'overflow')
    # the reason a page started is the reason the page before it ended
    for i in range(1, len(pages_out)):
        pages_out[i].why = getattr(pages_out[i - 1], '_why_next', 'overflow')
    return pages_out
