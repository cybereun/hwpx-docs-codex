"""Table extras: floating position (hp:pos), caption (hp:caption), cell protect. Rules TB05-TB08.

Builder side: `pos_xml`, `caption_xml`. Reader side (called through core/registry.py READS): `read_table(reader, tbl)` gives
the extra table keys, `read_cell(reader, tc)` the extra cell keys, `read_fill(reader, fillBrush)` a gradient or picture fill.
"""
from ..core.units import esc, hu
from . import fills

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph', 'hc': 'http://www.hancom.co.kr/hwpml/2011/core'}
MM = 7200 / 25.4


def mm(v):
    return round(int(v) / MM, 3)         # 3 decimals: the builder gets the same HWPUNIT back (core/read.py mm)

# ---- position -------------------------------------------------------------------------------------------------------
VREL = {'paper': 'PAPER', 'page': 'PAGE', 'para': 'PARA'}
HREL = {'paper': 'PAPER', 'page': 'PAGE', 'column': 'COLUMN', 'para': 'PARA'}
VALIGN = ('top', 'center', 'bottom', 'inside', 'outside')
HALIGN = ('left', 'center', 'right', 'inside', 'outside')
# what a block table in the text flow has (Hangul's default); anything else is a floating position
FLOW = dict(vertRelTo='PARA', horzRelTo='COLUMN', vertAlign='TOP', flowWithText='1', allowOverlap='0', holdAnchorAndSO='0',
            affectLSpacing='0', vertOffset=0, horzOffset=0)


def pos_xml(pos, halign, inline, hold=False):
    """`hp:pos` of a table. pos = spec "pos" (a floating table) or None; halign = the table's `align` (flow table); hold = the flow
    table's `hold` (개체와 조판 부호를 항상 같은 쪽에 놓기: its paragraph stays on the table's page, rules TB05)."""
    if pos:
        rel = pos.get('rel', 'paper')
        a = dict(treatAsChar=0, affectLSpacing=int(pos.get('affect', False)), flowWithText=int(pos.get('flow', False)),
                 allowOverlap=int(pos.get('overlap', True)), holdAnchorAndSO=int(pos.get('hold', False)),
                 vertRelTo=VREL[pos.get('vrel', rel)], horzRelTo=HREL[pos.get('hrel', rel)],
                 vertAlign=str(pos.get('valign', 'top')).upper(), horzAlign=str(pos.get('halign', 'left')).upper(),
                 vertOffset=hu(pos.get('y', 0)), horzOffset=hu(pos.get('x', 0)))
    else:
        a = dict(treatAsChar=int(inline), affectLSpacing=0, flowWithText=1, allowOverlap=0, holdAnchorAndSO=int(bool(hold)),
                 vertRelTo='PARA', horzRelTo='COLUMN', vertAlign='TOP', horzAlign=halign, vertOffset=0, horzOffset=0)
    return '<hp:pos ' + ' '.join(f'{k}="{v}"' for k, v in a.items()) + '/>'


def read_pos(pos):
    """hp:pos of a block table -> spec "pos" dict, or None when it is a plain flow table (then `align` is read; holdAnchorAndSO
    is the flow table's `hold`, read_table)."""
    g = pos.get
    plain = all(g(k) == v for k, v in FLOW.items() if not k.endswith('Offset') and k != 'holdAnchorAndSO') \
        and g('vertOffset') == '0' and g('horzOffset') == '0'
    if plain:
        return None
    vrel, hrel = g('vertRelTo').lower(), g('horzRelTo').lower()
    d = {'x': mm(g('horzOffset')), 'y': mm(g('vertOffset'))}
    if vrel == hrel:
        d['rel'] = vrel
    else:
        d['vrel'], d['hrel'] = vrel, hrel
    if g('vertAlign') != 'TOP':
        d['valign'] = g('vertAlign').lower()
    if g('horzAlign') != 'LEFT':
        d['halign'] = g('horzAlign').lower()
    for key, attr, default in (('flow', 'flowWithText', '0'), ('overlap', 'allowOverlap', '1'),
                               ('hold', 'holdAnchorAndSO', '0'), ('affect', 'affectLSpacing', '0')):
        if g(attr) != default:
            d[key] = g(attr) == '1'
    return d


# ---- caption --------------------------------------------------------------------------------------------------------
SIDES = {'top': 'TOP', 'bottom': 'BOTTOM', 'left': 'LEFT', 'right': 'RIGHT'}
CAP_GAP, CAP_WIDTH = 850, 8504          # Hangul's defaults: 3 mm gap, 30 mm caption width (left/right captions)


def caption_xml(doc, cap, ctx, table_width):
    """`hp:caption` for the table spec key "caption": a string (text after "표 <number>") or
    {"text", "label": "표", "number": true, "side": "bottom", "gap": mm, "width": mm}."""
    if isinstance(cap, str):
        cap = {'text': cap}
    side = SIDES[str(cap.get('side', 'bottom')).lower()]
    gap = hu(cap['gap']) if 'gap' in cap else CAP_GAP
    width = hu(cap['width']) if 'width' in cap else CAP_WIDTH
    number = cap.get('number', True)
    label, text = cap.get('label', '표' if number else ''), cap.get('text', '')
    if number:                              # "<label> <auto number> <text>"
        doc.caps = getattr(doc, 'caps', 0) + 1
        runs = f'<hp:t>{esc(label + " ")}</hp:t>' if label else ''
        runs += (f'<hp:ctrl><hp:autoNum num="{doc.caps}" numType="TABLE"><hp:autoNumFormat type="DIGIT" userChar="" '
                 'prefixChar="" suffixChar="" supscript="0"/></hp:autoNum></hp:ctrl>')
        runs += f'<hp:t>{esc(" " + text)}</hp:t>' if text else ''
    else:                                   # plain text; the label stays in front of it
        runs = f'<hp:t>{esc((label + " " if label else "") + text)}</hp:t>' if label or text else ''
    cid = doc.head.char_pr(ctx)
    para = (f'<hp:p id="0" paraPrIDRef="19" styleIDRef="22" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{cid}">{runs}</hp:run></hp:p>')
    last = width if side in ('LEFT', 'RIGHT') else table_width       # Hangul: lastWidth = caption width beside, table width above/below
    return (f'<hp:caption side="{side}" fullSz="0" width="{width}" gap="{gap}" lastWidth="{last}">'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{para}</hp:subList></hp:caption>')


def read_caption(cap):
    d = {'side': cap.get('side', 'BOTTOM').lower()}
    before, after, number = '', '', False
    for el in cap.iter():                   # document order: text before the number is the label, after it the text
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 'autoNum':
            number = True
        elif tag == 't' and el.text:
            if number:
                after += el.text
            else:
                before += el.text
    if number:
        label, text = before.rstrip(), after[1:] if after.startswith(' ') else after
    else:                                   # no number: all the text is the caption text
        label, text = '', before
    d.update(label=label, number=number, text=text)
    if int(cap.get('gap', CAP_GAP)) != CAP_GAP:
        d['gap'] = mm(cap.get('gap'))
    if int(cap.get('width', CAP_WIDTH)) != CAP_WIDTH:
        d['width'] = mm(cap.get('width'))
    return d


# ---- reader hooks ---------------------------------------------------------------------------------------------------
def read_table(reader, tbl):
    """Extra table keys: `caption`, the floating `pos` and a flow table's `hold` (core reads the plain cases)."""
    out = {}
    pos = tbl.find('hp:pos', NS)
    if pos.get('treatAsChar') != '1':
        p = read_pos(pos)
        if p:
            out['pos'] = p
        elif pos.get('holdAnchorAndSO') == '1':
            out['hold'] = True
    cap = tbl.find('hp:caption', NS)
    if cap is not None:
        out['caption'] = read_caption(cap)
    return out


# ---- formula cell (계산식) ---------------------------------------------------------------------------------------------
FORMULA_FIELDID = 627469685          # the same in every Hangul formula field (window 2)


def formula_xml(doc, f, text):
    """Run content of a formula cell: one run with fieldBegin FORMULA, the shown result, fieldEnd (rules TB09).
    f = "=SUM(?1:?3)" or {"expr": "=SUM(?1:?3)", "format": "%g,"}; with a format Hangul's block-sum form (5 parameters:
    Command "<expr>??<format>;;<result>", Formula, ResultFormat, LastResult); without it the short form (Command = Formula)."""
    expr, fmt = (f['expr'], f.get('format')) if isinstance(f, dict) else (f, None)
    fid = 1247000000 + doc.next_obj()
    text = str(text)
    if fmt is not None:
        params = (f'<hp:parameters cnt="5" name=""><hp:integerParam name="Prop">8</hp:integerParam>'
                  f'<hp:stringParam name="Command">{esc(expr)}??{esc(fmt)};;{esc(text)}</hp:stringParam>'
                  f'<hp:stringParam name="Formula">{esc(expr)}</hp:stringParam>'
                  f'<hp:stringParam name="ResultFormat">{esc(fmt)}</hp:stringParam>'
                  f'<hp:stringParam name="LastResult">{esc(text)}</hp:stringParam></hp:parameters>')
    else:
        params = (f'<hp:parameters cnt="3" name=""><hp:integerParam name="Prop">8</hp:integerParam>'
                  f'<hp:stringParam name="Command">{esc(expr)}</hp:stringParam>'
                  f'<hp:stringParam name="Formula">{esc(expr)}</hp:stringParam></hp:parameters>')
    shown = f'<hp:t>{esc(text)}</hp:t>' if text else ''
    return (f'<hp:ctrl><hp:fieldBegin id="{fid}" type="FORMULA" name="" editable="0" dirty="0" zorder="-1" '
            f'fieldid="{FORMULA_FIELDID}">{params}</hp:fieldBegin></hp:ctrl>{shown}'
            f'<hp:ctrl><hp:fieldEnd beginIDRef="{fid}" fieldid="{FORMULA_FIELDID}"/></hp:ctrl><hp:t/>')


def read_formula(tc):
    """A cell that holds one paragraph with a FORMULA field -> {'formula': ..., 'p': shown text}, else None."""
    sl = tc.find('hp:subList', NS)
    paras = sl.findall('hp:p', NS) if sl is not None else []
    if len(paras) != 1:
        return None
    fb = next((e for e in paras[0].iter() if e.tag.endswith('}fieldBegin') and e.get('type') == 'FORMULA'), None)
    if fb is None:
        return None
    par = {p.get('name'): (p.text or '') for p in fb.iter() if p.tag.endswith('Param')}
    f = {'expr': par.get('Formula', '')}
    if 'ResultFormat' in par:
        f['format'] = par['ResultFormat']
    text = ''.join(t.text or '' for t in paras[0].iter() if t.tag.endswith('}t'))
    return {'formula': f if 'format' in f else f['expr'], 'p': text}


def read_cell(reader, tc):
    out = read_formula(tc) or {}
    if tc.get('protect') == '1':
        out['protect'] = True
    if tc.get('editable') == '1':
        out['editable'] = True
    return out


def read_fill(reader, brush):
    v = fills.read_brush(reader, brush)
    return {'fill': v} if v else None
