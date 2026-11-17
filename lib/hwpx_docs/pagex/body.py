"""Page controls inside the body: `hide_page` (현재 쪽만 감추기) and `columns_here` (단 설정 나누기).

Both are builder handlers of the spec keys (registered in BLOCKS). A block is a paragraph that also holds the control:
  {"hide_page": ["header", "footer", "page_number"], "p": "text"}
  {"columns_here": {"count": 2, "gap": 8, "line": "0.12mm solid", "type": "newspaper"}, "p": "text"}
The reader keeps both controls as raw OWPML run items ({"xml": ...}); they round-trip unchanged (rules PX09, PX10).
"""
from ..core.units import esc, hu, line

HIDE_ATTRS = {'header': 'hideHeader', 'footer': 'hideFooter', 'master_page': 'hideMasterPage', 'border': 'hideBorder',
              'fill': 'hideFill', 'page_number': 'hidePageNum'}
COL_TYPES = {'newspaper': 'NEWSPAPER', 'balanced': 'BALANCED_NEWSPAPER', 'parallel': 'PARALLEL'}


def hide_xml(names):
    """`hp:pageHiding` for a list of names (header, footer, master_page, border, fill, page_number) or True (all)."""
    names = list(HIDE_ATTRS) if names is True else names
    bad = [n for n in names if n not in HIDE_ATTRS]
    if bad:
        raise ValueError(f'hide_page: unknown {bad}; use {list(HIDE_ATTRS)}')
    return '<hp:pageHiding ' + ' '.join(f'{a}="{int(n in names)}"' for n, a in HIDE_ATTRS.items()) + '/>'


def columns_xml(col):
    count = int(col.get('count', 1))
    cl = ''
    if col.get('line'):
        t, w, c = line(col['line'])
        cl = f'<hp:colLine type="{t}" width="{w}" color="{c}"/>'
    gap = f'sameGap="{hu(col.get("gap", 8)) if count > 1 else 0}"'
    return (f'<hp:colPr id="" type="{COL_TYPES[col.get("type", "newspaper")]}" layout="LEFT" colCount="{count}" sameSz="1" {gap}'
            + (f'>{cl}</hp:colPr>' if cl else '/>'))


def with_ctrl(doc, b, ctx, extra, pending_break, key, ctrl):
    """The block as paragraph(s); the control sits at the start of the first one."""
    rest = {k: v for k, v in b.items() if k != key}
    text = rest.pop('p', '')
    run = f'<hp:run charPrIDRef="FIRST"><hp:ctrl>{ctrl}</hp:ctrl></hp:run>'
    if not isinstance(text, str):
        return [doc.para_xml(text, ctx, rest, extra + run, pending_break)]
    lines = text.split('\n')
    out = [doc.para_xml([lines[0]] if lines[0] else [], ctx, rest, extra + run, pending_break)]
    return out + [doc.para_xml([ln] if ln else [], ctx, rest, '', False) for ln in lines[1:]]


def hide_page(doc, b, ctx, extra, pending_break):
    return with_ctrl(doc, b, ctx, extra, pending_break, 'hide_page', hide_xml(b['hide_page']))


def columns_here(doc, b, ctx, extra, pending_break):
    return with_ctrl(doc, b, ctx, extra, pending_break, 'columns_here', columns_xml(b['columns_here']))
