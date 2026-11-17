"""Placement and captions of floating objects (C6.12-C6.14): `hp:pos`, `textWrap`, `textFlow`, `hp:caption`.

One spec convention for pictures, drawing objects and the new object kinds (the same keys as a floating table,
table/rules.md TB05):
  pos     {"x", "y" (mm), "rel": "paper|page|para" (vertical reference; also the horizontal one unless `hrel` is given),
           "hrel": "paper|page|column|para", "valign": "top|center|bottom|inside|outside",
           "halign": "left|center|right|inside|outside", "flow": bool (flowWithText), "overlap": bool (allowOverlap)}
  wrap    "square" | "top_and_bottom" | "behind_text" | "in_front_of_text"
  side    "both_sides" | "left_only" | "right_only" | "largest_only"   (textFlow; side of a square-wrapped object)
  caption string (text after the number) or {"text", "label", "number": bool, "side": "left|right|top|bottom", "gap", "width"} (mm)
Rules: rules.md OB01-OB05.
"""
import re

from ..core.units import esc, hu

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph', 'hc': 'http://www.hancom.co.kr/hwpml/2011/core'}
MM = 7200 / 25.4
VREL = {'paper': 'PAPER', 'page': 'PAGE', 'para': 'PARA'}
HREL = {'paper': 'PAPER', 'page': 'PAGE', 'column': 'COLUMN', 'para': 'PARA'}
SIDES = {'top': 'TOP', 'bottom': 'BOTTOM', 'left': 'LEFT', 'right': 'RIGHT'}
CAP_GAP, CAP_WIDTH = 850, 8504            # Hangul's defaults: 3 mm gap, 30 mm caption width (left / right captions)
POS_KEYS = ('hrel', 'valign', 'halign', 'flow', 'overlap')


def mm(v):
    return round(int(v) / MM, 3)           # 3 decimals: the builder gets the same HWPUNIT back


# ---- hp:pos -----------------------------------------------------------------------------------------------------------
def pos_attrs(el_pos):
    return dict(re.findall(r'(\w+)="([^"]*)"', el_pos))


def set_pos(xml, pos):
    """Rewrite `hp:pos` of the object XML with the keys that `pos` gives (the others stay as the writer made them)."""
    m = re.search(r'<hp:pos [^>]*/>', xml)
    if not m or not any(k in pos for k in POS_KEYS + ('vrel',)):
        return xml
    a = pos_attrs(m.group(0))
    if 'vrel' in pos or 'rel' in pos:
        a['vertRelTo'] = VREL[pos.get('vrel', pos.get('rel'))]
    if 'hrel' in pos:
        a['horzRelTo'] = HREL[pos['hrel']]
    if 'valign' in pos:
        a['vertAlign'] = str(pos['valign']).upper()
    if 'halign' in pos:
        a['horzAlign'] = str(pos['halign']).upper()
    if 'flow' in pos:
        a['flowWithText'] = int(bool(pos['flow']))
    if 'overlap' in pos:
        a['allowOverlap'] = int(bool(pos['overlap']))
    new = '<hp:pos ' + ' '.join(f'{k}="{v}"' for k, v in a.items()) + '/>'
    return xml[:m.start()] + new + xml[m.end():]


def set_side(xml, side):
    """textFlow of the object (the first tag of the element): both_sides, left_only, right_only, largest_only."""
    if not side:
        return xml
    return re.sub(r'textFlow="[A-Z_]*"', f'textFlow="{str(side).upper()}"', xml, count=1)


def read_pos(el, defaults):
    """Extra position keys of an object: only those that differ from `defaults` (what the writer makes by itself).
    defaults: {'hrel': ..., 'flow': bool, 'overlap': bool} as lower-case / bool values."""
    p = el.find('hp:pos', NS)
    out = {}
    if p is None:
        return out
    g = p.get
    if g('horzRelTo').lower() != defaults['hrel']:
        out['hrel'] = g('horzRelTo').lower()
    if g('vertAlign') != 'TOP':
        out['valign'] = g('vertAlign').lower()
    if g('horzAlign') != 'LEFT':
        out['halign'] = g('horzAlign').lower()
    if (g('flowWithText') == '1') != defaults['flow']:
        out['flow'] = g('flowWithText') == '1'
    if (g('allowOverlap') == '1') != defaults['overlap']:
        out['overlap'] = g('allowOverlap') == '1'
    return out


# ---- caption ----------------------------------------------------------------------------------------------------------
def caption_xml(doc, cap, ctx, width_hu, number=True, label='그림'):
    """`hp:caption` for the spec key `caption` (see the module doc). width_hu: width of the object (lastWidth above or below)."""
    if isinstance(cap, str):
        cap = {'text': cap}
    side = SIDES[str(cap.get('side', 'bottom')).lower()]
    gap = hu(cap['gap']) if 'gap' in cap else CAP_GAP
    width = hu(cap['width']) if 'width' in cap else CAP_WIDTH
    number = cap.get('number', number)
    label, text = cap.get('label', label if number else ''), cap.get('text', '')
    if number:                                       # "<label> <auto number> <text>"
        doc.caps_obj = getattr(doc, 'caps_obj', 0) + 1
        runs = f'<hp:t>{esc(label + " ")}</hp:t>' if label else ''
        runs += (f'<hp:ctrl><hp:autoNum num="{doc.caps_obj}" numType="PICTURE"><hp:autoNumFormat type="DIGIT" userChar="" '
                 'prefixChar="" suffixChar="" supscript="0"/></hp:autoNum></hp:ctrl>')
        runs += f'<hp:t>{esc(" " + text)}</hp:t>' if text else ''
    else:
        runs = f'<hp:t>{esc((label + " " if label else "") + text)}</hp:t>' if label or text else ''
    cid = doc.head.char_pr(ctx)
    para = (f'<hp:p id="0" paraPrIDRef="19" styleIDRef="22" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{cid}">{runs}</hp:run></hp:p>')
    last = width if side in ('LEFT', 'RIGHT') else width_hu
    return (f'<hp:caption side="{side}" fullSz="0" width="{width}" gap="{gap}" lastWidth="{last}">'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{para}</hp:subList></hp:caption>')


def add_caption(xml, doc, spec, ctx, width_hu, number=True):
    """Put the caption of `spec` at the end of the object element (after hp:shapeComment, as Hangul writes it)."""
    cap = spec.get('caption')
    if not cap:
        return xml
    close = xml.rindex('</hp:')
    return xml[:close] + caption_xml(doc, cap, ctx, width_hu, number) + xml[close:]


def read_caption(el):
    """`hp:caption` child of an object -> spec `caption` dict, or None."""
    cap = el.find('hp:caption', NS)
    if cap is None:
        return None
    d = {'side': cap.get('side', 'BOTTOM').lower()}
    before, after, number = '', '', False
    for e in cap.iter():                    # document order: text before the number is the label, after it the text
        tag = e.tag.rsplit('}', 1)[-1]
        if tag == 'autoNum':
            number = True
        elif tag == 't' and e.text:
            if number:
                after += e.text
            else:
                before += e.text
    if number:
        label, text = before.rstrip(), after[1:] if after.startswith(' ') else after
    else:
        label, text = '', before
    d.update(label=label, number=number, text=text)
    if int(cap.get('gap', CAP_GAP)) != CAP_GAP:
        d['gap'] = mm(cap.get('gap'))
    if int(cap.get('width', CAP_WIDTH)) != CAP_WIDTH:
        d['width'] = mm(cap.get('width'))
    return d
