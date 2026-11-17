"""The new drawing object kinds as one spec block `{"object": {...}}` (C6.08, C6.11, C8.01, C8.02):
polygon, curve (free-form pen drawing), connector (연결선), textart (글맵시), group (묶음).

Spec of `object` (lengths in mm, all positions relative to the object's own top-left corner):
  kind     "polygon" | "curve" | "connector" | "textart" | "group"
  w, h     size
  inline   true (default): on the text line; false: floating, with `pos`, `wrap`, `side` (pos.py)
  line     "0.12mm solid #000000" | "none"        fill  "#RRGGBB"        caption  (pos.py)
  polygon  points [[x, y], ...], closed (default true)
  curve    segs [["line"|"curve", x1, y1, x2, y2], ...]  (three "curve" segs in a row = one cubic Bezier: start -> c1 -> c2 -> end)
  connector type "straight"|"elbow"|"arc", arrow "none"|"end"|"both", from [x, y], to [x, y], from_ref / to_ref {"id", "idx"}
  textart  text, shape (name of Hangul's 글맵시 shape, SHAPES), font, align "left|center|right", char_space %, line_space %,
           shadow {"type": "left_top"|"right_top", "x": %, "y": %}
  group    items [child objects with x, y inside the group, or kind rect | ellipse | line (core shapes)]
`build(doc, o, ctx)` -> XML of one object; `read(reader, el)` -> spec item. Rules: rules.md OB09-OB16.
"""
import re

from ..core.units import HU_PER, color, esc, hu, inherit, line
from . import pos as P

NS = P.NS
MM = P.MM
ID0, INST0 = 1700000000, 1800000000
# the 36 shapes of 글맵시, in the order of the COM item `Shape` 0..35 (corpus ta_shapes; default 17 = WAVE2)
SHAPES = ['PARALLELOGRAM', 'INVERTED_PARALLELOGRAM', 'INVERTED_UPWARD_CASCADE', 'INVERTED_DOWNWARD_CASCADE', 'UPWARD_CASCADE',
          'DOWNWARD_CASCADE', 'REDUCE_RIGHT', 'REDUCE_LEFT', 'ISOSCELES_TRAPEZOID', 'INVERTED_ISOSCELES_TRAPEZOID',
          'TOP_RIBBON_RECTANGLE', 'BOTTOM_RIBBON_RECTANGLE', 'CHEVRON_DOWN', 'CHEVRON', 'BOW_TIE', 'HEXAGON', 'WAVE1', 'WAVE2',
          'WAVE3', 'WAVE4', 'LEFT_TILT_CYLINDER', 'RIGHT_TILT_CYLINDER', 'BOTTOM_WIDE_CYLINDER', 'TOP_WIDE_CYLINDER',
          'THIN_CURVE_UP1', 'THIN_CURVE_UP2', 'THIN_CURVE_DOWN1', 'THIN_CURVE_DOWN2', 'INVERSED_FINGERNAIL', 'FINGERNAIL',
          'GINKO_LEAF1', 'GINKO_LEAF2', 'INFLATE_RIGHT', 'INFLATE_LEFT', 'INFLATE_UP_CONVEX', 'INFLATE_BOTTOM_CONVEX']
CONNECT_KIND = {'straight': 'STRAIGHT', 'elbow': 'STROKE', 'arc': 'ARC'}
CONNECT_ARROW = {'none': 'NOARROW', 'end': 'ONEWAY', 'both': 'BOTH'}
SHADOW = {'left_top': 'PARELLEL_LEFTTOP', 'right_top': 'PARELLEL_RIGHTTOP'}      # (sic) Hangul's spelling
ID = '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'


def mm(v):
    return round(int(v) / MM, 3)


def num(v):
    return int(v) if float(v) == int(float(v)) else round(float(v), 3)


# ---- common parts ------------------------------------------------------------------------------------------------------
def line_xml(o, filled=True):
    t, wd, col = line(o.get('line', '0.12mm solid #000000'))
    lw = round(float(wd.split()[0]) * HU_PER['mm'])
    arrow = o.get('arrow', 'none')
    head = 'ARROW' if arrow == 'both' else 'NORMAL'
    tail = 'ARROW' if arrow in ('end', 'both') else 'NORMAL'
    return (f'<hp:lineShape color="{col}" width="{lw}" style="{t}" endCap="FLAT" headStyle="{head}" tailStyle="{tail}" '
            'headfill="1" tailfill="1" headSz="MEDIUM_MEDIUM" tailSz="MEDIUM_MEDIUM" outlineStyle="NORMAL" alpha="0"/>')


def fill_xml(o):
    if not o.get('fill'):
        return ''
    return f'<hc:fillBrush><hc:winBrush faceColor="{color(o["fill"])}" hatchColor="#000000" alpha="0"/></hc:fillBrush>'


SHADOW0 = '<hp:shadow type="NONE" color="#B2B2B2" offsetX="0" offsetY="0" alpha="0"/>'


def head(doc, o, tag, w, h, child=None, extra=''):
    """Opening tag and the common children up to the shadow. child = (x, y) hu inside a group."""
    oid = doc.next_obj()
    gl, (cx, cy) = (1, child) if child is not None else (0, (0, 0))
    wrap = str(o.get('wrap', 'square')).upper() if not o.get('inline', True) else 'TOP_AND_BOTTOM'
    mat = ID.replace('e3="0"', f'e3="{cx}"').replace('e6="0"', f'e6="{cy}"')
    return (f'<hp:{tag} id="{ID0 + oid}" zOrder="{oid}" numberingType="NONE" textWrap="{wrap}" textFlow="BOTH_SIDES" lock="0" '
            f'dropcapstyle="None" href="" groupLevel="{gl}" instid="{INST0 + oid}"{extra}>'
            f'<hp:offset x="{cx}" y="{cy}"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="0" height="0"/>'
            f'<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
            f'<hp:renderingInfo>{mat}{ID.replace("trans", "sca")}{ID.replace("trans", "rot")}</hp:renderingInfo>')


def tail(o, w, h, child=None):
    """sz, pos, outMargin; the caption is added by the caller. A child of a group has none (Hangul writes none)."""
    if child is not None:
        return ''
    if o.get('inline', True):
        pos = ('<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>')
    else:
        p = o.get('pos') or {}
        rel = p.get('rel', 'para')
        a = dict(treatAsChar=0, affectLSpacing=0, flowWithText=int(p.get('flow', True)), allowOverlap=int(p.get('overlap', False)),
                 holdAnchorAndSO=0, vertRelTo=P.VREL[rel], horzRelTo=P.HREL[p.get('hrel', 'column' if rel == 'para' else rel)],
                 vertAlign=str(p.get('valign', 'top')).upper(), horzAlign=str(p.get('halign', 'left')).upper(),
                 vertOffset=hu(p.get('y', 0)), horzOffset=hu(p.get('x', 0)))
        pos = '<hp:pos ' + ' '.join(f'{k}="{v}"' for k, v in a.items()) + '/>'
    return (f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>{pos}'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/>')


def finish(doc, o, ctx, xml, tag, w):
    xml = xml + f'</hp:{tag}>'
    xml = P.set_side(xml, o.get('side'))
    return P.add_caption(xml, doc, o, ctx, w, number=False)


def size(o):
    return hu(o['w']), hu(o['h'])


# ---- kinds: builder ----------------------------------------------------------------------------------------------------
def polygon(doc, o, ctx, child=None):
    w, h = size(o)
    pts = [(hu(x), hu(y)) for x, y in o['points']]
    if o.get('closed', True) and pts[0] != pts[-1]:
        pts.append(pts[0])                                   # Hangul lists the first point again at the end of a closed polygon
    geo = ''.join(f'<hc:pt x="{x}" y="{y}"/>' for x, y in pts)
    xml = head(doc, o, 'polygon', w, h, child) + line_xml(o) + fill_xml(o) + SHADOW0 + geo + tail(o, w, h, child)
    return finish(doc, o, ctx, xml, 'polygon', w)


def curve(doc, o, ctx, child=None):
    w, h = size(o)
    geo = ''.join(f'<hp:seg type="{t.upper()}" x1="{hu(a)}" y1="{hu(b)}" x2="{hu(c)}" y2="{hu(d)}"/>' for t, a, b, c, d in o['segs'])
    xml = head(doc, o, 'curve', w, h, child) + line_xml(o) + fill_xml(o) + SHADOW0 + geo + tail(o, w, h, child)
    return finish(doc, o, ctx, xml, 'curve', w)


def connector(doc, o, ctx, child=None):
    w, h = size(o)
    kind = f'{CONNECT_KIND[o.get("type", "straight")]}_{CONNECT_ARROW[o.get("arrow", "none")]}'
    ends = []
    for tag, key in (('startPt', 'from'), ('endPt', 'to')):
        x, y = o.get(key, [0, 0] if key == 'from' else [o['w'], o['h']])
        ref = o.get(key + '_ref') or {}
        ends.append(f'<hp:{tag} x="{hu(x)}" y="{hu(y)}" subjectIDRef="{ref.get("id", 0)}" subjectIdx="{ref.get("idx", 0)}"/>')
    xml = (head(doc, o, 'connectLine', w, h, child, f' type="{kind}"') + line_xml(o) + SHADOW0 + ''.join(ends)
           + tail(o, w, h, child))
    return finish(doc, o, ctx, xml, 'connectLine', w)


def textart(doc, o, ctx, child=None):
    w, h = size(o)
    pw, ph = 14173, 14173                                    # Hangul's own box of the art (orgSz); the real size is `sz`
    sh = o.get('shadow') or {}
    shadow = (f'<hp:shadow type="{SHADOW[sh["type"]]}" color="#000000" offsetX="{int(sh.get("x", 0))}" '
              f'offsetY="{int(sh.get("y", 0))}" alpha="0"/>' if sh else
              '<hp:shadow type="NONE" color="#000000" offsetX="0" offsetY="0" alpha="0"/>')
    shape = str(o.get('shape', 'WAVE2')).upper()
    if shape not in SHAPES:
        raise ValueError(f'unknown 글맵시 shape {shape!r}; one of {SHAPES}')
    pr = (f'<hp:textartPr fontName="{esc(o.get("font", "함초롬바탕"))}" fontStyle="보통" fontType="TTF" textShape="{shape}" '
          f'lineSpacing="{int(o.get("line_space", 120))}" charSpacing="{int(o.get("char_space", 100))}" '
          f'align="{str(o.get("align", "left")).upper()}">{shadow}</hp:textartPr>')
    o = dict(o, fill=o.get('fill', '#0000FF'), line=o.get('line', 'none'))
    xml = (head(doc, o, 'textart', pw, ph, child, f' text="{esc(o.get("text", "내용을 입력하세요."))}"').replace(
        f'<hp:rotationInfo angle="0" centerX="{pw // 2}" centerY="{ph // 2}"', '<hp:rotationInfo angle="0" centerX="0" centerY="0"')
        + line_xml(o) + fill_xml(o) + SHADOW0
        + f'<hc:pt0 x="0" y="0"/><hc:pt1 x="{pw}" y="0"/><hc:pt2 x="{pw}" y="{ph}"/><hc:pt3 x="0" y="{ph}"/>' + pr
        + tail(o, w, h, child))
    return finish(doc, o, ctx, xml, 'textart', w)


def plain(kind):
    """A core shape (rect, ellipse, line) as a child of a group: core builds it, the head moves into the group."""
    def build(doc, o, ctx, child=None):
        s = {k: v for k, v in o.items() if k not in ('kind', 'inline', 'pos')}
        s['type'] = kind
        s['x'] = s['y'] = 0
        if kind == 'line':
            s.update(x2=o.get('x2', o['w']), y2=o.get('y2', o['h']))
        xml = doc.shape(s, ctx)
        cx, cy = child
        xml = xml.replace('groupLevel="0"', 'groupLevel="1"', 1).replace('<hp:offset x="0" y="0"/>', f'<hp:offset x="{cx}" y="{cy}"/>', 1)
        return xml.replace(ID, ID.replace('e3="0"', f'e3="{cx}"').replace('e6="0"', f'e6="{cy}"'), 1)
    return build


def group(doc, o, ctx, child=None):
    items = o['items']
    w = hu(o['w']) if 'w' in o else max(hu(c.get('x', 0)) + hu(c['w']) for c in items)
    h = hu(o['h']) if 'h' in o else max(hu(c.get('y', 0)) + hu(c['h']) for c in items)
    kids = ''.join(BUILD[c['kind']](doc, c, ctx, (hu(c.get('x', 0)), hu(c.get('y', 0)))) for c in items)
    xml = head(doc, o, 'container', w, h, child) + kids + tail(o, w, h, child)
    return finish(doc, o, ctx, xml, 'container', w)


BUILD = {'polygon': polygon, 'curve': curve, 'connector': connector, 'textart': textart, 'group': group,
         'rect': plain('rect'), 'ellipse': plain('ellipse'), 'line': plain('line')}


def block(doc, b, ctx, extra, pending_break):
    """Builder handler of the spec key `object`."""
    o = b['object']
    if not isinstance(o, dict) or o.get('kind') not in BUILD or o['kind'] in ('rect', 'ellipse', 'line'):
        return None
    xml = BUILD[o['kind']](doc, o, ctx)
    return f'<hp:run charPrIDRef="{doc.head.char_pr(inherit(ctx, b))}">{xml}<hp:t/></hp:run>'     # core makes the paragraph (same_para)


# ---- reader ------------------------------------------------------------------------------------------------------------
def read_line(el, d):
    ls = el.find('hp:lineShape', NS)
    if ls is not None:
        d['line'] = (f'{round(int(ls.get("width")) / MM, 2)}mm {ls.get("style").lower()} {ls.get("color")}'
                     if ls.get('style') != 'NONE' else 'none')
        heads = (ls.get('headStyle') != 'NORMAL', ls.get('tailStyle') != 'NORMAL')
        if any(heads):
            d['arrow'] = 'both' if all(heads) else 'end'
    wb = el.find('hc:fillBrush/hc:winBrush', NS)
    if wb is not None and wb.get('faceColor') != 'none':
        d['fill'] = wb.get('faceColor')


def read_common(el, tag, child):
    if child:                  # a child of a group: Hangul writes no sz / pos for it; size = orgSz, place = hp:offset
        off, sz = el.find('hp:offset', NS), el.find('hp:orgSz', NS)
        return {'kind': tag, 'x': mm(off.get('x')), 'y': mm(off.get('y')), 'w': mm(sz.get('width')), 'h': mm(sz.get('height'))}
    sz = el.find('hp:sz', NS)
    d = {'kind': tag, 'w': mm(sz.get('width')), 'h': mm(sz.get('height'))}
    pos = el.find('hp:pos', NS)
    if pos.get('treatAsChar') != '1':
        vrel = pos.get('vertRelTo').lower()
        d['inline'] = False
        d['pos'] = dict({'x': mm(pos.get('horzOffset')), 'y': mm(pos.get('vertOffset')), 'rel': vrel},
                        **P.read_pos(el, {'hrel': 'column' if vrel == 'para' else vrel, 'flow': True, 'overlap': False}))
        d['wrap'] = el.get('textWrap').lower()
    if el.get('textFlow', 'BOTH_SIDES') != 'BOTH_SIDES':
        d['side'] = el.get('textFlow').lower()
    return d


def read_kind(reader, el, child=False):
    tag = el.tag.rsplit('}', 1)[-1]
    if tag in ('rect', 'ellipse', 'line'):
        d = read_common(el, tag, True)
        read_line(el, d)
        d.pop('arrow', None)
        return d
    name = {'polygon': 'polygon', 'curve': 'curve', 'connectLine': 'connector', 'textart': 'textart', 'container': 'group'}[tag]
    d = read_common(el, name, child)
    if tag == 'polygon':
        pts = [[mm(p.get('x')), mm(p.get('y'))] for p in el.findall('hc:pt', NS)]
        if len(pts) > 2 and pts[0] == pts[-1]:              # closed (the default): the repeated first point is dropped
            d['points'] = pts[:-1]
        else:
            d['points'], d['closed'] = pts, False
    elif tag == 'curve':
        d['segs'] = [[s.get('type').lower()] + [mm(s.get(k)) for k in ('x1', 'y1', 'x2', 'y2')] for s in el.findall('hp:seg', NS)]
    elif tag == 'connectLine':
        kind, _, arrow = el.get('type', 'STRAIGHT_NOARROW').partition('_')
        d['type'] = {v: k for k, v in CONNECT_KIND.items()}.get(kind, 'straight')
        sp, ep = el.find('hp:startPt', NS), el.find('hp:endPt', NS)
        d['from'], d['to'] = [mm(sp.get('x')), mm(sp.get('y'))], [mm(ep.get('x')), mm(ep.get('y'))]
        for key, e in (('from_ref', sp), ('to_ref', ep)):
            if e.get('subjectIDRef', '0') != '0' or e.get('subjectIdx', '0') != '0':
                d[key] = {'id': int(e.get('subjectIDRef')), 'idx': int(e.get('subjectIdx'))}
    elif tag == 'textart':
        pr = el.find('hp:textartPr', NS)
        d['text'] = el.get('text', '')
        d['shape'] = pr.get('textShape')
        d['font'] = pr.get('fontName')
        d['align'] = pr.get('align', 'LEFT').lower()
        for key, attr, default in (('char_space', 'charSpacing', 100), ('line_space', 'lineSpacing', 120)):
            if int(pr.get(attr, default)) != default:
                d[key] = int(pr.get(attr))
        sh = pr.find('hp:shadow', NS)
        if sh is not None and sh.get('type') != 'NONE':
            d['shadow'] = {'type': {v: k for k, v in SHADOW.items()}[sh.get('type')], 'x': int(sh.get('offsetX')), 'y': int(sh.get('offsetY'))}
    else:
        d['items'] = [read_kind(reader, c, True) for c in el if c.tag.rsplit('}', 1)[-1] in
                      ('polygon', 'curve', 'connectLine', 'textart', 'container', 'rect', 'ellipse', 'line')]
    if tag in ('polygon', 'curve', 'connectLine', 'textart'):
        read_line(el, d)
        if tag == 'textart':
            d.setdefault('fill', '#0000FF')
            if d.get('line') == 'none':
                d.pop('line')
    cap = P.read_caption(el)
    if cap:
        d['caption'] = cap
    return d


def read(reader, el):
    """Reader handler (READS): the element of an object kind -> `{"object": spec}` (a block of its own). An element that lacks the
    parts Hangul always writes (hand-made, cut down) is not mine: None, and core keeps it as raw OWPML."""
    try:
        return {'object': read_kind(reader, el)}
    except (AttributeError, TypeError, KeyError, ValueError):
        return None
