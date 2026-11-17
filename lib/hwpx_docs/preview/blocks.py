"""Block atoms of the preview: what the layout makes of each body block, for tools that plan pages (pagefit).

`section_atoms(spec, pic_dir='.')` -> [section]; a section is
  {'index': i, 'geom': {x0, y0, x1, y1, ...mm}, 'columns': n, 'blocks': [block]}
and a block is {'index': k (position in the section's `body`), 'block': the spec block, 'atoms': [atom], 'floating': bool,
'region': True when a column change makes the section more than one setting}; an atom is
  {'h': mm, 'trail': mm (spacing under the last line that the flow does not need at the page end), 'keep': 'break' | 'skip' | False,
   'line': True for a text line (False: a table row, a gap, an object)}.
The spec is what `core.read` gives (blocks with their properties in place); a spec with `class` or `named_styles` is resolved by the
caller (`core.layout.Layout.eff`). Registered as the backend `blocks` / `preview` (core/registry.py `backend('blocks', 'preview')`).
Footnotes, columns and floating objects are NOT placed here: the caller decides what to do with them.
"""
from ..core import read as rd
from .flow import column_regions, geometry
from .layout import Ctx, layout_block


def section_atoms(spec, pic_dir='.'):
    from .drawers import prepare
    prepare(spec, pic_dir)
    ctx = Ctx(spec, pic_dir)
    out = []
    for i, sec in enumerate(spec.get('sections') or [spec]):
        ctx.spec, ctx.section = spec, i
        g = geometry(sec)
        ncol = (sec.get('columns') or {}).get('count', 1)
        cw = (g['x1'] - g['x0'] - (ncol - 1) * (sec.get('columns') or {}).get('gap', 0)) / ncol
        body = sec.get('body', [])
        regions = column_regions(body, sec.get('columns') or {})
        blocks, after_table = [], False
        for k, b in enumerate(body):
            floating = isinstance(b, dict) and bool(b.get('same_para') or b.get('shapes') or b.get('shape'))
            atoms = [] if floating else layout_block(ctx, b, dict(rd.DEF_CHAR), cw, after_table)
            after_table = isinstance(b, dict) and 'table' in b
            blocks.append({'index': k, 'block': b, 'floating': floating, 'region': len(regions) > 1,
                           'atoms': [{'h': a.h, 'trail': a.trail, 'keep': a.keep, 'line': a.base is not None} for a in atoms]})
        out.append({'index': i, 'geom': g, 'columns': ncol, 'blocks': blocks})
    return out
