"""Draft preset (presets/<name>.json) from a sample document: a Hangul HWPX, or a spec JSON (for example the spec
that you made from an image with references/image-to-hwpx.md).

  hd preset-from <sample.hwpx | spec.json> <out.json> [--name <name>]

The draft lists every distinct text style (char + para props) as s1..sN in order of first use, with its count and
an example text, the page setup, and a summary of each table (cell fills, lines, margins). LAYOUT is "hangul": the
values are Hangul's own (no browser spacing model). The other keys (BOX, CELL_PAD, MAP, ...) are copied from
presets/report-gongmun.json. Next steps (skill hwpx-text, references/presets.md, "New preset"): rename the styles to
the roles that markdown.py uses, set BOX/CELL_PAD/HEAD_FILL from the table summary, fill MAP, delete the keys that
start with "_".
"""
import json
import os
import sys

from ..core import read as hwpx2spec
from .markdown import PRESET_DIR

KEYS = ('font', 'size', 'bold', 'color', 'align', 'left', 'indent', 'before', 'after', 'line', 'word_break')
CELL_ONLY = {'p', 'blocks', 'cs', 'rs', 'fill', 'border', 'pad', 'valign', 'diag', 'diag_line'}
PAPER = {'A4': (210, 297), 'A3': (297, 420), 'A5': (148, 210), 'B4': (257, 364), 'B5': (182, 257),
         'LETTER': (215.9, 279.4), 'LEGAL': (215.9, 355.6)}


def text_of(p):
    return p if isinstance(p, str) else ''.join(x if isinstance(x, str) else str(x.get('t', '')) for x in p)


def paragraphs(blocks, inh, tables):
    """Yield (effective props, text) of each paragraph; table cells included (they inherit only char props)."""
    char_keys = hwpx2spec.CHAR_KEYS
    fresh = {k: v for k, v in inh.items() if k in char_keys}
    fresh.update({k: v for k, v in hwpx2spec.DEF_PARA.items()})
    for b in blocks:
        if isinstance(b, str):
            b = {'p': b}
        if 'table' in b:
            t = b['table']
            tables.append(t)
            base = dict(fresh, **{k: v for k, v in b.items() if k in char_keys}, **t.get('cell', {}))
            for row in t.get('rows', []):
                cells = row.get('cells', []) if isinstance(row, dict) else row
                rs = dict(base, **(row.get('style', {}) if isinstance(row, dict) else {}))
                for c in cells:
                    c = {'p': c} if isinstance(c, str) else c
                    cs = dict(rs, **{k: v for k, v in c.items() if k not in CELL_ONLY})
                    inner = c.get('blocks') or [{'p': x} for x in str(c.get('p', '')).split('\n')]
                    yield from paragraphs(inner, cs, tables)
        elif 'p' in b:
            for line in (b['p'].split('\n') if isinstance(b['p'], str) else [b['p']]):
                yield dict(inh, **{k: v for k, v in b.items() if k != 'p'}), text_of(line)


def table_summary(t):
    fills, lines, pads = {}, {}, {}
    for row in t.get('rows', []):
        for c in (row.get('cells', []) if isinstance(row, dict) else row):
            if isinstance(c, dict):
                if c.get('fill'):
                    fills[c['fill']] = fills.get(c['fill'], 0) + 1
                for v in (c['border'].values() if isinstance(c.get('border'), dict) else [c.get('border')]):
                    if v:
                        lines[v] = lines.get(v, 0) + 1
                if c.get('pad') is not None:
                    pads[json.dumps(c['pad'])] = pads.get(json.dumps(c['pad']), 0) + 1
    return {'cols': t.get('cols'), 'border': t.get('border'), 'pad': t.get('pad'), 'cell_fills': fills,
            'cell_lines': lines, 'cell_pads': pads}


def draft(spec, name):
    sec = spec['sections'][0] if 'sections' in spec else spec
    base = dict(hwpx2spec.DEF_CHAR, **hwpx2spec.DEF_PARA, **(spec.get('defaults') or sec.get('defaults') or {}))
    styles, tables = {}, []
    for props, text in paragraphs(sec.get('body', []), base, tables):
        key = json.dumps([props.get(k) for k in KEYS], ensure_ascii=False)
        st = styles.setdefault(key, {'props': props, 'count': 0, 'example': text.strip()[:40]})
        st['count'] += 1
        st['example'] = st['example'] or text.strip()[:40]
    TEXT, fonts = {}, {}
    for i, st in enumerate(styles.values(), 1):
        p = st['props']
        fonts[p['font']] = p['font']
        e = dict(font=p['font'], size=p['size'], bold=bool(p['bold']), color=p['color'], align=str(p['align']).upper(),
                 left=p['left'], indent=p['indent'], before=p['before'], after=p['after'], line=p['line'])
        if p.get('word_break', 'char') != 'char':
            e['word_break'] = p['word_break']
        TEXT[f's{i}'] = dict(e, _count=st['count'], _example=st['example'])
    pg = sec.get('page', {})
    size = pg.get('size', 'A4')
    w, h = PAPER.get(str(size).upper(), (210, 297)) if isinstance(size, str) else size
    if pg.get('landscape'):
        w, h = h, w
    m = pg.get('margin', {})
    base = json.load(open(os.path.join(PRESET_DIR, 'report-gongmun.json'), encoding='utf-8'))
    out = {'name': name, 'about': f'Draft from a sample document ({name}); roles not assigned yet.', 'LAYOUT': 'hangul',
           'FONT': fonts, 'PAGE': dict(width_mm=w, height_mm=h, left_mm=m.get('left', 30), right_mm=m.get('right', 30),
                                       top_mm=m.get('top', 20), bottom_mm=m.get('bottom', 15)),
           'TEXT': TEXT, '_tables': [table_summary(t) for t in tables]}
    for k in ('BORDER', 'BOX', 'THIN', 'THICK', 'CELL_PAD', 'HEAD_FILL', 'BLANK_ROW_PT', 'BAR_WIDTH_PT', 'LIST_MARK',
              'MAP'):
        out[k] = base[k]
    out['_todo'] = ('Rename s1..sN to the roles of markdown.py (docno title subtitle date summary chapter attach item sub '
                    'l0 l1 l2 note para th td code end gap); set BOX, CELL_PAD, HEAD_FILL from _tables; fill MAP; '
                    'delete every key and field that starts with "_" (references/presets.md).')
    return out


def main(args):
    src, dst = args[0], args[1]
    name = args[args.index('--name') + 1] if '--name' in args else os.path.splitext(os.path.basename(dst))[0]
    if src.lower().endswith('.hwpx'):
        spec = hwpx2spec.read(src, dst)
    else:
        spec = json.load(open(src, encoding='utf-8'))
    d = draft(spec, name)
    json.dump(d, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('PRESET DRAFT', dst, 'styles', len(d['TEXT']), 'tables', len(d['_tables']))
    for k, v in d['TEXT'].items():
        print(f'  {k}: {v["font"]} {v["size"]}pt{" bold" if v["bold"] else ""} {v["align"]} left {v["left"]} '
              f'indent {v["indent"]} x{v["_count"]} "{v["_example"]}"')


if __name__ == '__main__':
    main(sys.argv[1:])
