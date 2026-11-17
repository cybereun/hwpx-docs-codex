"""Picture extras (C6.02) and the placement / caption / text flow of pictures and drawing objects (C6.12-C6.14).

Builder: `pic_post` / `shape_post` get the XML that core made (`registry.post_xml`) and change it by the spec keys below.
Reader: `pic_extra` / `shape_extra` add the keys to the dict that core.read made (`registry.read_extras`).
Picture keys: bright (-100..100), contrast (-100..100), effect "real|gray|bw", crop [left, top, right, bottom] in % of
the picture, border (line: "0.35mm solid #000000"), caption, side, pos extras. Shape keys: hrel, halign, vpos, flow,
overlap, caption, side. Rules: rules.md OB01-OB08.
"""
import re

from ..core.units import HU_PER, color, line
from . import pos as P

NS = P.NS
EFFECT = {'real': 'REAL_PIC', 'gray': 'GRAY_SCALE', 'bw': 'BLACK_WHITE'}
EFFECT_BACK = {v: k for k, v in EFFECT.items()}
PIC_KEYS = ('bright', 'contrast', 'effect', 'crop', 'border', 'caption', 'side')
SHAPE_KEYS = ('hrel', 'halign', 'vpos', 'flow', 'overlap', 'caption', 'side')


def border_xml(spec):
    """Line spec of a picture border -> `hp:lineShape`; the width is kept as given (Hangul takes any HWPUNIT here)."""
    t, _, col = line(spec)
    m = re.search(r'(\d+(?:\.\d+)?)\s*mm', str(spec if not isinstance(spec, dict) else spec.get('width', '0.12mm')))
    wd = round(float(m.group(1)) * HU_PER['mm']) if m else 34
    return (f'<hp:lineShape color="{col}" width="{wd}" style="{t}" endCap="ROUND" headStyle="NORMAL" tailStyle="NORMAL" '
            'headfill="0" tailfill="0" headSz="SMALL_SMALL" tailSz="SMALL_SMALL" outlineStyle="NORMAL" alpha="0"/>')


def read_border(ls):
    return f'{round(int(ls.get("width")) / P.MM, 3)}mm {ls.get("style").lower()} {ls.get("color")}'


def pic_post(doc, p, xml, *_):
    """Picture XML of core + the extra keys of the picture spec `p`."""
    if not any(k in p for k in PIC_KEYS) and not any(k in (p.get('pos') or {}) for k in P.POS_KEYS):
        return xml
    if 'bright' in p or 'contrast' in p or 'effect' in p:
        xml = re.sub(r'bright="-?\d+" contrast="-?\d+" effect="[A-Z_]+"',
                     f'bright="{int(p.get("bright", 0))}" contrast="{int(p.get("contrast", 0))}" '
                     f'effect="{EFFECT[str(p.get("effect", "real")).lower()]}"', xml, count=1)
    if 'crop' in p:                                      # % of the picture; imgClip is in picture units (pixel x 75)
        m = re.search(r'<hp:imgClip left="0" right="(\d+)" top="0" bottom="(\d+)"/>', xml)
        full_w, full_h = int(m.group(1)), int(m.group(2))
        l, t, r, b = (float(v) for v in p['crop'])
        xml = xml.replace(m.group(0), f'<hp:imgClip left="{round(full_w * l / 100)}" right="{round(full_w * (1 - r / 100))}" '
                                      f'top="{round(full_h * t / 100)}" bottom="{round(full_h * (1 - b / 100))}"/>')
    if p.get('border'):
        xml = xml.replace('<hp:imgRect>', border_xml(p['border']) + '<hp:imgRect>', 1)
    if not p.get('inline', True):
        xml = P.set_pos(xml, p.get('pos') or {})
    xml = P.set_side(xml, p.get('side'))
    w = int(re.search(r'<hp:sz width="(\d+)"', xml).group(1))
    return P.add_caption(xml, doc, p, {}, w, number=True)


def pic_extra(reader, el, d):
    """Add the picture extras to the spec dict `d` that core.read.pic made."""
    img = el.find('hc:img', NS)
    if img.get('bright', '0') != '0':
        d['bright'] = int(img.get('bright'))
    if img.get('contrast', '0') != '0':
        d['contrast'] = int(img.get('contrast'))
    if img.get('effect', 'REAL_PIC') != 'REAL_PIC':
        d['effect'] = EFFECT_BACK.get(img.get('effect'), img.get('effect').lower())
    clip = el.find('hp:imgClip', NS)
    dim = el.find('hp:imgDim', NS)
    fw, fh = int(dim.get('dimwidth', 0)), int(dim.get('dimheight', 0))
    if clip is not None and fw and fh:
        l, r, t, b = (int(clip.get(k)) for k in ('left', 'right', 'top', 'bottom'))
        crop = [round(l * 100 / fw, 2), round(t * 100 / fh, 2), round((fw - r) * 100 / fw, 2), round((fh - b) * 100 / fh, 2)]
        if any(crop):
            d['crop'] = crop
    ls = el.find('hp:lineShape', NS)
    if ls is not None and ls.get('style') != 'NONE':
        d['border'] = read_border(ls)
    if not d.get('inline', True):
        extra = P.read_pos(el, {'hrel': el.find('hp:pos', NS).get('vertRelTo').lower(), 'flow': False, 'overlap': True})
        if extra:
            d['pos'].update(extra)
    cap = P.read_caption(el)
    if cap:
        d['caption'] = cap


def shape_post(doc, s, xml, ctx=None):
    """Drawing object XML of core (rect, ellipse, line) + the extra keys of the shape spec `s`."""
    if not any(k in s for k in SHAPE_KEYS):
        return xml
    pos = {k: s[k] for k in P.POS_KEYS if k in s and k != 'valign'}
    if 'vpos' in s:                            # `valign` of a shape is the text inside a text box (core): the place is `vpos`
        pos['valign'] = s['vpos']
    xml = P.set_pos(xml, pos)
    xml = P.set_side(xml, s.get('side'))
    w = int(re.search(r'<hp:sz width="(\d+)"', xml).group(1))
    return P.add_caption(xml, doc, s, ctx or {}, w, number=False)


def shape_extra(reader, el, d):
    """Add the shape extras to the spec dict `d` that core.read.shape made."""
    vrel = el.find('hp:pos', NS).get('vertRelTo').lower()
    extra = P.read_pos(el, {'hrel': 'column' if vrel == 'para' else vrel, 'flow': vrel == 'para', 'overlap': True})
    if 'valign' in extra:                      # `valign` of a shape is the text inside a text box: the vertical place is `vpos`
        extra['vpos'] = extra.pop('valign')
    d.update(extra)
    cap = P.read_caption(el)
    if cap:
        d['caption'] = cap
