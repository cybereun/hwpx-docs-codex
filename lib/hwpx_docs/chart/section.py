"""The chart in the section: `hp:chart` (writer) and its reader. Plugs into core through `chart.register()`.

  block(doc, b, ctx, extra, pending_break)   builder handler of the spec key `chart` (native charts only)
  read(reader, el)                           reader handler of `hp:switch` that holds an `hp:chart`
Rules: rules.md in this folder (CH02, CH03).
"""
from xml.etree import ElementTree as ET
from ..core.units import HU_PER, hu, inherit
from .ooxml import chart_xml, parse

OOXMLCHART = 'http://www.hancom.co.kr/hwpml/2016/ooxmlchart'
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def element(doc, c, inline=True):
    """Chart spec -> the `hp:switch` element (Hangul form, no OLE branch). Stores the part in doc.parts."""
    xml = chart_xml(c)                           # raises ValueError for a spec that cannot be drawn
    n = 1 + sum(1 for k in doc.parts if k.startswith('Chart/'))
    name = f'Chart/chart{n}.xml'
    doc.parts[name] = xml.encode('utf-8')
    oid = doc.next_obj()
    w, h = hu(c.get('w', 150)), hu(c.get('h', 90))
    pos = c.get('pos') or {}
    if inline:
        wrap, posxml = 'TOP_AND_BOTTOM', ('<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
                                          'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
                                          'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>')
    else:
        rel = {'page': 'PAGE', 'paper': 'PAPER', 'para': 'PARA'}[pos.get('rel', 'para')]
        wrap = str(c.get('wrap', 'square')).upper()
        posxml = (f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="{int(rel == "PARA")}" allowOverlap="0" '
                  f'holdAnchorAndSO="0" vertRelTo="{rel}" horzRelTo="{"COLUMN" if rel == "PARA" else rel}" '
                  f'vertAlign="TOP" horzAlign="LEFT" vertOffset="{hu(pos.get("y", 0))}" horzOffset="{hu(pos.get("x", 0))}"/>')
    return (f'<hp:switch><hp:case hp:required-namespace="{OOXMLCHART}"><hp:chart id="{1900000000 + oid}" zOrder="{oid}" '
            f'numberingType="PICTURE" textWrap="{wrap}" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" '
            f'chartIDRef="{name}"><hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'{posxml}<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:chart></hp:case></hp:switch>')


def block(doc, b, ctx, extra, pending_break):
    """Builder handler. Returns the paragraphs of a native chart; None for a chart drawn with shapes; a substitute
    block (drawing-object chart) when the spec cannot be drawn natively."""
    c = b['chart']
    if not isinstance(c, dict) or not c.get('native'):
        return None
    try:
        run = (f'<hp:run charPrIDRef="{doc.head.char_pr(inherit(ctx, b))}">{element(doc, c, c.get("inline", True))}'
               '<hp:t/></hp:run>')
    except ValueError as e:
        print(f'FALLBACK chart: {e}')
        c = {k: v for k, v in c.items() if k != 'native'}
        c['type'] = c.get('type', 'bar') if c.get('type', 'bar') in ('bar', 'line') else 'bar'
        return dict(b, chart=c)
    return [doc.para_xml([], ctx, b, extra + run, pending_break)]


def read(reader, el):
    """Reader handler: `hp:switch` with an `hp:chart` -> {'chart': spec}; None for any other element."""
    ch = el.find('.//' + HP + 'chart')
    if el.tag != HP + 'switch' or ch is None:
        return None
    xml = reader.z.read(ch.get('chartIDRef')).decode('utf-8')
    d = parse(xml)
    if 'ooxml' in d:                         # kept whole for writing; `view` = what a viewer draws (preview)
        v = parse(xml, strict=False)
        if 'ooxml' not in v:
            d['view'] = v
    sz, pos = ch.find(HP + 'sz'), ch.find(HP + 'pos')
    mm = lambda v: round(int(v) / HU_PER['mm'], 3)      # 3 decimals: the builder gets the same hu back
    d.update(native=True, w=mm(sz.get('width')), h=mm(sz.get('height')))
    if pos.get('treatAsChar') != '1':
        d['inline'] = False
        d['pos'] = {'x': mm(pos.get('horzOffset')), 'y': mm(pos.get('vertOffset')), 'rel': pos.get('vertRelTo').lower()}
        d['wrap'] = ch.get('textWrap').lower()
    return {'chart': d}
