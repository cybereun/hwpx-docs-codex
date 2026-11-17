"""Page report of the preview: what the preview's own flow made of the pages, for tools that plan pages (pagefit).

`page_report(spec, pic_dir='.')` -> [page]; unlike blocks.section_atoms it runs the real flow, so columns, footnote blocks, objects
that text goes around and column changes are in the result. A page is
  {'no': page number in the document (1 = first), 'section': i, 'y0', 'y1': body top / bottom (mm), 'columns': n,
   'items': [{'block': k (body index of its section), 'k0', 'k1': the rows of that block on this page, counted over the document, 'h': mm}],
   'used': mm of text and footnotes summed over the columns, 'capacity': columns x body height,
   'why': what started the page: 'start' | 'forced_break' | 'split' | 'overflow', 'notes_cont': True when a footnote goes on at the
   next page}.
The keep rules (keep_next, keep_lines, widow, page_break_before) are applied by the preview's flow (rules P17):
`page_report.keep_rules` is True, so a tool that plans pages can take the pages as they are. Registered as the backend `pagereport` / `preview` (core/registry.py).
"""
from . import flow
from .layout import floating, layout_block, layout_para


def _normal(spec):
    """The spec with every body block a dict (a copy of the lists, the blocks themselves are shared) and its sections."""
    spec = dict(spec)
    secs = [dict(s) for s in (spec.get('sections') or [spec])]
    for s in secs:
        s['body'] = [{'p': b} if isinstance(b, str) else b for b in s.get('body', [])]
    if spec.get('sections'):
        spec['sections'] = secs
    else:
        spec = secs[0]
        secs = [spec]
    return spec, secs


def page_report(spec, pic_dir='.'):
    spec, secs = _normal(spec)
    where = {id(b): (i, k) for i, s in enumerate(secs) for k, b in enumerate(s['body'])}
    tag, ptag, hold = {}, {}, []

    def tagged(ctx, blocks, cs, width_mm):         # layout.layout_blocks, remembering which block each atom comes from
        atoms, after_table, carry = [], False, []
        for b in blocks:
            bi = where.get(id(b), (None, None))[1]
            if carry and isinstance(b, dict) and 'p' in b:
                b, carry = dict(b, shapes=list(b.get('shapes') or []) + carry), []
            elif carry:
                atoms += layout_para(ctx, {'p': '', 'shapes': carry}, cs, width_mm, after_table)
                carry = []
            got = floating(ctx, b, cs, width_mm) if isinstance(b, dict) and b.get('same_para') else None
            if got:
                carry += got
                continue
            new = layout_block(ctx, b, cs, width_mm, after_table)
            for a in new:
                hold.append(a)
                tag[id(a)] = bi
                if a.para is not None:
                    ptag[id(a.para)] = bi
            atoms += new
            after_table = isinstance(b, dict) and 'table' in b
            if not after_table and new and new[-1].absorb:
                after_table = new[-1].absorb
        if carry:
            atoms += layout_para(ctx, {'p': '', 'shapes': carry}, cs, width_mm, after_table)
        return atoms
    trace = flow.Trace()
    saved = flow.layout_blocks
    flow.layout_blocks = tagged
    try:
        from .drawers import prepare
        prepare(spec, pic_dir)
        ctx = flow.lay_out(spec, pic_dir, trace)
    finally:
        flow.layout_blocks = saved
    # a section laid out twice (flow.render_section): only the events after its LAST 'section' mark count
    last = {}
    for k, e in enumerate(trace.events):
        if e[0] == 'section':
            last[e[1]] = k
    events, cur = [], None
    for k, e in enumerate(trace.events):
        if e[0] == 'section':
            cur = e[1]
        elif k > last[cur]:
            events.append(e)
    out = []
    for pg in ctx.pages:
        i = (getattr(pg, 'info', None) or {}).get('section', 0)
        out.append({'no': pg.n, 'section': i, 'y0': pg.g['y0'], 'y1': pg.g['y1'],
                    'columns': (secs[i].get('columns') or {}).get('count', 1), 'items': [], 'used': 0.0, 'capacity': 0.0,
                    'why': 'start', '_cols': {}, '_first': None, '_n': []})
    for e in events:
        pgd = out[e[1] - 1]
        if e[0] == 'notes':
            pgd['used'] += e[3] * (pgd['columns'] if e[2] < 0 else 1)
            continue
        if e[0] == 'notes_cont':
            pgd['notes_cont'] = True
            continue
        if e[0] == 'defer':                        # a table waits for the next page; the text after it goes on here (P18)
            pgd.setdefault('deferred', []).append(tag.get(id(e[4])))
            continue
        _, _, col, y, a = e
        bi = tag.get(id(a))
        if bi is None and a.para is not None:
            bi = ptag.get(id(a.para))
        if a.emit is not None or a.h - a.trail > 1e-9:          # room only (the empty line under a waiting table) is not text
            pgd['_cols'][col] = max(pgd['_cols'].get(col, pgd['y0']), y + a.h - a.trail)
        if pgd['_first'] is None:
            pgd['_first'] = a
        if bi is None:
            continue
        it = pgd['_n'][-1] if pgd['_n'] else None
        if it and it['block'] == bi and it['col'] == col:
            it['n'] += 1
            it['h'] += a.h
        else:
            pgd['_n'].append({'block': bi, 'col': col, 'n': 1, 'h': a.h})
    count = {}
    for n, p in enumerate(out):
        for it in p.pop('_n'):                     # rows counted over the document: where this page's rows start in the block
            k0 = count.get((p['section'], it['block']), 0)
            count[(p['section'], it['block'])] = k0 + it['n']
            p['items'].append({'block': it['block'], 'k0': k0, 'k1': k0 + it['n'], 'h': it['h']})
        p['used'] += sum(v - p['y0'] for v in p.pop('_cols').values())
        p['capacity'] = p['columns'] * (p['y1'] - p['y0'])
        first = p.pop('_first')
        prev = out[n - 1] if n and out[n - 1]['section'] == p['section'] else None
        if prev is not None:
            p['why'] = ('forced_break' if first is not None and first.keep == 'break' else
                        'split' if prev['items'] and p['items'] and prev['items'][-1]['block'] == p['items'][0]['block'] else 'overflow')
    return out


page_report.keep_rules = True      # the flow applies keep_next, keep_lines, widow, page_break_before (preview rules P17)
