"""Drawing objects of OWPML (pic, rect, ellipse, line ...) -> the `gso ` control of an HWP 5.0 file (rules HW20, HW22).

  gso(writer, el, level) -> [[tag, level, bytes], ...]       CTRL_HEADER, SHAPE_COMPONENT, the shape record, [text list]

Layouts follow tospec.py / rules HW22 and were fitted to the hwp2hwpx pairs (tools/verify.py fromhwpx).
A shape kind with no code here raises Unsupported (never skipped).
"""
import re
import struct

from . import owpmlmap as om
from .fo_head import LINE, Unsupported, color, fill_info, first, kids, ln, num, pick, snum, wstr
from .fo_body import b, cid, rec

KIND = {'pic': '$pic', 'rect': '$rec', 'ellipse': '$ell', 'line': '$lin', 'arc': '$arc', 'polygon': '$pol', 'curve': '$cur',
        'container': '$con', 'ole': '$ole', 'textart': '$tat', 'connectLine': '$col'}
HEAD_SIZE = om.inverse(om.ARROW_SIZE)
ARROW = om.inverse(om.ARROWS)                # as measured on the pairs (line: EMPTY_DIAMOND = 4, EMPTY_CIRCLE = 5)
SHADOW_TYPE = om.inverse(om.SHADOW)                 # measured in Hangul: the PARELLEL_* spelling is Hangul's own
# The shadow info, the instance id and the two alpha bytes at the end of a shape's SHAPE_COMPONENT (the instance id alone for a container)
# are missing in the files of 5.0.1.7 and before (line 217 / 239 bytes, container 206 / 210) and there in 5.0.2.4 and after; nothing
# between is measured, so the limit is the first version of 5.0.2 (HW94).
SHAPE_TAIL_VER = (5, 0, 2, 0)


def matrix(m):
    return struct.pack('<6d', *[float(m.get(f'e{i}', 0)) for i in range(1, 7)])


def line_info(ls):
    """Line colour, width, attribute (type, end cap, arrows and their sizes and fill) and outline style."""
    if ls is None:
        return struct.pack('<IiIB', 0, 0, 0, 0)
    t = pick({n: i for i, n in enumerate(LINE)}, ls.get('style', 'SOLID'), 'line style')
    a = t | {'ROUND': 0, 'FLAT': 1}.get(ls.get('endCap', 'FLAT'), 1) << 6
    a |= pick(ARROW, ls.get('headStyle', 'NORMAL'), 'arrow') << 10 | pick(ARROW, ls.get('tailStyle', 'NORMAL'), 'arrow') << 16
    a |= pick(HEAD_SIZE, ls.get('headSz', 'MEDIUM_MEDIUM'), 'arrow size') << 22
    a |= pick(HEAD_SIZE, ls.get('tailSz', 'MEDIUM_MEDIUM'), 'arrow size') << 26
    a |= b(ls.get('headfill')) << 30 | b(ls.get('tailfill')) << 31
    return struct.pack('<IiIB', color(ls.get('color'), 0), snum(ls.get('width')), a,
                       om.inverse(om.OUTLINE_STYLE).get(ls.get('outlineStyle', 'NORMAL'), 0))


def shape_component(el, kind, level, tail, grouped=False, ver=(5, 1, 1, 0)):
    """SHAPE_COMPONENT: kind twice, offset, group level, size, flags, rotation, the matrices, then `tail`."""
    off, org, cur = first(el, 'offset'), first(el, 'orgSz'), first(el, 'curSz')
    rot, rinfo = first(el, 'rotationInfo'), first(el, 'renderingInfo')
    flip = first(el, 'flip')
    sz = first(el, 'sz')
    cw = num(cur.get('width')) or (num(sz.get('width')) if sz is not None else 0) or num(org.get('width'))      # a 0 falls back to the next size (HW87)
    chh = num(cur.get('height')) or (num(sz.get('height')) if sz is not None else 0) or num(org.get('height'))
    fl = 0x80000 if rot is None or b(rot.get('rotateimage', '1')) else 0
    if ver >= (5, 1, 1, 0):
        fl |= 1 << 16                                        # Hangul 2024 sets bit 16 of every shape when it saves a HWPX (12 shapes of 153 forms; HW81)
    if kind == 'pic':
        dim = first(el, 'imgDim')
        fl |= 0x20000000 | b(el.get('reverse')) << 24
        if dim is not None and (num(dim.get('dimwidth')) or num(dim.get('dimheight'))):
            fl |= 0x04000000                                # bit 26: the picture has its own size (imgDim not 0; HW87)
    elif first(el, 'drawText') is not None:
        fl |= 1 << 24                                        # a shape with its own text
    if flip is not None:
        fl |= b(flip.get('horizontal')) | b(flip.get('vertical')) << 1
    ident = {'e1': 1, 'e5': 1}
    if rinfo is not None:
        sca, rot_ = kids(rinfo, 'scaMatrix'), kids(rinfo, 'rotMatrix')
        mats = [first(rinfo, 'transMatrix')] + [m for pair in zip(sca, rot_) for m in pair]
    else:
        mats = [None] * 3
    npairs = max((len(mats) - 1) // 2, 1)
    ms = b''.join(matrix(m.attrib if m is not None else ident) for m in mats)
    ox = num(off.get('x'))
    oy = num(off.get('y'))
    ox = ox - (1 << 32) if ox >= 1 << 31 else ox
    oy = oy - (1 << 32) if oy >= 1 << 31 else oy
    data = (cid(KIND[kind]) + (b'' if grouped else cid(KIND[kind])) + struct.pack('<iiHH', ox, oy, num(el.get('groupLevel')), 1)
            + struct.pack('<IIII', num(org.get('width')), num(org.get('height')), cw, chh)
            + struct.pack('<Ihii', fl, snum(rot.get('angle')) if rot is not None else 0,
                          snum(rot.get('centerX')) if rot is not None else 0, snum(rot.get('centerY')) if rot is not None else 0)
            + struct.pack('<H', npairs) + ms)
    return rec('SHAPE_COMPONENT', level, data + tail)


def shape_data(el, level):
    """The CTRL_DATA below a SHAPE_COMPONENT (HW88): a link (`href`: set 0x026F with the string item 0x0265; every colon is written
    with a backslash before it; a link in the form `url;n;n;n;` is kept, any other text keeps its part up to the first semicolon and gets
    `;0;0;0;`, as Hangul 2024 does) or a `hp:parameterset` of numbers."""
    href = el.get('href') or ''
    ps = first(el, 'parameterset')
    if href:
        text = href
        if not re.search(r';\d+;\d+;\d+;$', text):
            text = text.split(';')[0] + ';0;0;0;'
        text = text.replace(':', chr(92) + ':')
        body = struct.pack('<HHH', 0x021B, 1, 0) + struct.pack('<HH', 0x026F, 0x8000) + struct.pack('<HHH', 0x026F, 1, 0)             + struct.pack('<HHH', 0x0265, 1, len(text)) + text.encode('utf-16-le')
        return [rec('CTRL_DATA', level + 1, body)]
    if ps is not None:
        lp = first(ps, 'listParam')
        if lp is None:
            return [rec('CTRL_DATA', level + 1, struct.pack('<HHH', 0x021B, 1, 0) + struct.pack('<HH', 0x026F, 0x8000) + struct.pack('<HHH', 0x026F, 0, 0))]
        items = [(num(i.get('name')), num(i.text)) for i in lp if ln(i) == 'unsignedintegerParam']
        sid = num(lp.get('name'))
        body = struct.pack('<HHH', 0x021B, 1, 0) + struct.pack('<HH', sid, 0x8000) + struct.pack('<HHH', sid, len(items), 0)             + b''.join(struct.pack('<HHI', iid, 9, v) for iid, v in items)
        return [rec('CTRL_DATA', level + 1, body)]
    return []


def shape_records(el, kind, level, tail, grouped=False, ver=(5, 1, 1, 0)):
    return [shape_component(el, kind, level, tail, grouped, ver)] + shape_data(el, level)


def shadow_info(sh):
    """Shadow type, colour, offsets (16 bytes); the shadow transparency follows the instance id (see gso)."""
    if sh is None:
        return struct.pack('<IIii', 0, 0xB2B2B2, 0, 0)
    return struct.pack('<IIii', pick(SHADOW_TYPE, sh.get('type', 'NONE'), 'shadow type'), color(sh.get('color'), 0xB2B2B2),
                       snum(sh.get('offsetX')), snum(sh.get('offsetY')))


def points(el, names):
    out = b''
    for n in names:
        p = first(el, n)
        out += struct.pack('<ii', snum(p.get('x')), snum(p.get('y')))
    return out


SHAPES = ('pic', 'rect', 'ellipse', 'line', 'polygon', 'arc', 'curve', 'ole', 'textart', 'connectLine')


def gso(w, el, level):
    """One drawing object (a `gso ` control) with its records; `w` is the Writer (for text lists and pictures)."""
    kind = ln(el)
    if kind not in SHAPES + ('container',):
        raise Unsupported(f'element hp:{kind} in paragraph (shape kind not converted yet)')
    desc = first(el, 'shapeComment')
    out = [rec('CTRL_HEADER', level, w.common(el, 'gso ', (desc.text or '') if desc is not None else ''))]
    cap = first(el, 'caption')                       # a caption comes before the shape records (measured in Hangul, as for a table)
    if cap is not None:
        out += w.caption(cap, level + 1)
    return out + body(w, el, level + 1)


def body(w, el, level, grouped=False):
    """SHAPE_COMPONENT (at `level`), the shape's own record(s) at level + 1; a container writes its children after its own."""
    kind = ln(el)
    ls, fb, sh = first(el, 'lineShape'), first(el, 'fillBrush'), first(el, 'shadow')
    inst = struct.pack('<I', num(el.get('instid')) & 0xFFFFFFFF)
    if kind == 'container':
        children = [c for c in el if ln(c) in SHAPES + ('container',)]
        for c in el:
            if isinstance(c.tag, str) and ln(c) not in SHAPES + ('container',) and ln(c) not in (
                    'offset', 'orgSz', 'curSz', 'flip', 'rotationInfo', 'renderingInfo', 'sz', 'pos', 'outMargin',
                    'shapeComment', 'lineShape', 'fillBrush', 'shadow', 'caption', 'parameterset'):
                raise Unsupported(f'element hp:{ln(c)} in hp:container id={el.get("id")}')
        tail = struct.pack('<H', len(children)) + b''.join(cid(KIND[ln(c)]) for c in children) + (inst if w.ver >= SHAPE_TAIL_VER else b'')
        out = shape_records(el, kind, level, tail, grouped, w.ver)
        for c in children:
            out += body(w, c, level + 1, True)
        return out
    if kind == 'pic':
        return shape_records(el, kind, level, b'', grouped, w.ver) + [rec('SHAPE_COMPONENT_PICTURE', level + 1, picture(w, el))]
    if kind == 'ole':
        # the attribute word: drawing aspect, moniker, equation base line, object type (rule HW74; owpmlmap.OLE_*)
        eqb = num(el.get('eqBaseLine'))
        if not 0 <= eqb <= 127:
            raise Unsupported(f'OLE equation base line {eqb} in hp:ole id={el.get("id")}')
        oattr = (pick(om.inverse(om.OLE_ASPECT), el.get('drawAspect', 'CONTENT'), 'OLE drawing aspect')
                 | b(el.get('hasMoniker')) << 8 | eqb << 9 | pick(om.inverse(om.OLE_TYPE), el.get('objectType', 'EMBEDDED'), 'OLE object type') << 16)
        bid = w.bins.by_ref.get(el.get('binaryItemIDRef')) if el.get('binaryItemIDRef') else 0       # no reference: id 0 (HW88)
        if bid is None:
            raise Unsupported(f'OLE file {el.get("binaryItemIDRef")} is not in the package')
        ex = first(el, 'extent')
        return shape_records(el, kind, level, b'', grouped, w.ver) + [
                rec(0x54, level + 1, struct.pack('<IIIH', oattr, num(ex.get('x')), num(ex.get('y')), bid)
                    + line_info(ls)[:12]
                    + (struct.pack('<I', num(el.get('instid')) & 0xFFFFFFFF) if w.ver >= (5, 1, 0, 0) else b''))]       # Hangul 2024 (5.1): the object id
    if fb is not None:
        fill = fill_info(el, w.bins.by_ref, w.ver)
    else:
        fill = struct.pack('<II', 0, 0)                                            # no fill: type, extra size
    tail = line_info(ls) + fill
    if w.ver >= SHAPE_TAIL_VER:
        tail += shadow_info(sh) + inst + bytes([num(ls.get('alpha')) if ls is not None else 0, num(sh.get('alpha')) if sh is not None else 0])
    out = shape_records(el, kind, level, tail, grouped, w.ver)
    dt = first(el, 'drawText')
    if dt is not None:
        sl = first(dt, 'subList')
        plist = kids(sl, 'p')
        tm = first(dt, 'textMargin')
        out.append(rec('LIST_HEADER', level + 1, struct.pack('<II4HI', len(plist), w.list_attr(sl), num(tm.get('left')),
                                                            num(tm.get('right')), num(tm.get('top')), num(tm.get('bottom')),
                                                            num(dt.get('lastWidth'))) + bytes(13)))
        out += w.paras(plist, level + 1)
    if kind == 'rect':
        out.append(rec('SHAPE_COMPONENT_RECTANGLE', level + 1, bytes([num(el.get('ratio'))])
                       + points(el, ('pt0', 'pt1', 'pt2', 'pt3'))))
    elif kind == 'ellipse':
        arc = b(el.get('hasArcPr')) | om.inverse(om.ARC_TYPE).get(el.get('arcType', 'NORMAL'), 0) << 1
        out.append(rec('SHAPE_COMPONENT_ELLIPSE', level + 1, struct.pack('<I', arc)
                       + points(el, ('center', 'ax1', 'ax2', 'start1', 'end1', 'start2', 'end2'))))
    elif kind == 'polygon':
        pts = [(snum(p.get('x')), snum(p.get('y'))) for p in kids(el, 'pt')]
        out.append(rec(0x52, level + 1, struct.pack('<I', len(pts)) + b''.join(struct.pack('<ii', *q) for q in pts)
                       + struct.pack('<I', 1)))
    elif kind == 'arc':
        out.append(rec(0x51, level + 1, bytes([om.inverse(om.ARC_TYPE).get(el.get('type', 'NORMAL'), 0)])
                       + points(el, ('center', 'ax1', 'ax2'))))
    elif kind == 'curve':
        segs = kids(el, 'seg')
        pts = [(snum(segs[0].get('x1')), snum(segs[0].get('y1')))] + [(snum(g.get('x2')), snum(g.get('y2'))) for g in segs]
        out.append(rec(0x53, level + 1, struct.pack('<I', len(pts)) + b''.join(struct.pack('<ii', *q) for q in pts)
                       + bytes(1 if g.get('type') == 'CURVE' else 0 for g in segs) + struct.pack('<I', 0)))
    elif kind == 'textart':
        pr, text = first(el, 'textartPr'), el.get('text', '')
        shape = pick(om.inverse(om.TEXT_SHAPE), pr.get('textShape'), 'text art shape')       # 55 shapes measured in Hangul
        shd = first(pr, 'shadow')
        out.append(rec(0x5A, level + 1, points(el, ('pt0', 'pt1', 'pt2', 'pt3')) + wstr(text) + wstr(pr.get('fontName', ''))
                       + wstr(pr.get('fontStyle', ''))
                       + struct.pack('<5I', pick(om.inverse(om.TEXT_FONT), pr.get('fontType', 'TTF'), 'text art font type'), shape,
                                     num(pr.get('lineSpacing')), num(pr.get('charSpacing')),
                                     pick(om.inverse(om.TEXT_ALIGN), pr.get('align', 'LEFT'), 'text art align'))
                       + struct.pack('<IiiIB', pick(SHADOW_TYPE, shd.get('type', 'NONE'), 'text art shadow'), snum(shd.get('offsetX')),
                                     snum(shd.get('offsetY')), color(shd.get('color'), 0), num(shd.get('alpha')))
                       + bytes(3)))                                       # the alpha is padded to 4 bytes
    elif kind == 'connectLine':
        sp, ep = first(el, 'startPt'), first(el, 'endPt')
        pts = kids(first(el, 'controlPoints'), 'point') if first(el, 'controlPoints') is not None else []
        out.append(rec('SHAPE_COMPONENT_LINE', level + 1, struct.pack(
            '<4iIIIIII', num(sp.get('x')), num(sp.get('y')), num(ep.get('x')), num(ep.get('y')),
            pick(om.inverse(om.CONNECT_TYPES), el.get('type', 'STRAIGHT_NOARROW'), 'connector type'), num(sp.get('subjectIDRef')),
            num(sp.get('subjectIdx')), num(ep.get('subjectIDRef')), num(ep.get('subjectIdx')), len(pts))
            + b''.join(struct.pack('<iiH', snum(p.get('x')), snum(p.get('y')), num(p.get('type'))) for p in pts) + bytes(4)))
    elif kind == 'line':
        out.append(rec('SHAPE_COMPONENT_LINE', level + 1, points(el, ('startPt', 'endPt'))
                       + struct.pack('<I', b(el.get('isReverseHV')))))
    return out


EFFECT_ALIGN = om.inverse(om.EFFECT_ALIGN)
COLOR_EFFECTS = om.inverse(om.COLOR_EFFECT)        # 11 measured in Hangul; the rest of the schema has no id (rule HW71)


def f(v):
    return float(v) if v not in (None, '') else 0.0


def effects_color(ec, where):
    """An effects colour (RGB only): type 0, 0x00RRGGBB, the colour effects as (id, value)."""
    if ec is None or ec.get('type') != 'RGB':
        raise Unsupported(f'effects colour type {None if ec is None else ec.get("type")} in {where}')
    rgb = first(ec, 'rgb')
    fx = kids(ec, 'effect')
    for e in fx:
        if e.get('type') not in COLOR_EFFECTS:
            raise Unsupported(f'colour effect {e.get("type")} in {where}')
    return (struct.pack('<III', 0, num(rgb.get('r')) << 16 | num(rgb.get('g')) << 8 | num(rgb.get('b')), len(fx))
            + b''.join(struct.pack('<If', COLOR_EFFECTS[e.get('type')], f(e.get('value'))) for e in fx))


def effects(eff, el):
    """The picture effects (shadow 1, glow 2, soft edge 4, reflection 8, in that order): a flag word, then one block each."""
    where = f'picture id={el.get("id")}'
    if eff is None or not len(eff):
        return struct.pack('<I', 0)
    sh, gl, se, rf = first(eff, 'shadow'), first(eff, 'glow'), first(eff, 'softEdge'), first(eff, 'reflection')
    for c in eff:
        if isinstance(c.tag, str) and ln(c) not in ('shadow', 'glow', 'reflection', 'softEdge'):
            raise Unsupported(f'picture effect hp:{ln(c)} in {where}')
    out = struct.pack('<I', (1 if sh is not None else 0) | (2 if gl is not None else 0) | (4 if se is not None else 0)
                      | (8 if rf is not None else 0))
    if sh is not None:
        sk, sc = first(sh, 'skew'), first(sh, 'scale')
        out += (struct.pack('<IffffI', pick(om.inverse(om.SHADOW_STYLE), sh.get('style', 'OUTSIDE'), 'shadow style'), f(sh.get('alpha')),
                            f(sh.get('radius')), f(sh.get('direction')), f(sh.get('distance')),
                            pick(EFFECT_ALIGN, sh.get('alignStyle', 'TOP_LEFT'), 'effect alignment'))
                + struct.pack('<4f', f(sk.get('x')), f(sk.get('y')), f(sc.get('x')), f(sc.get('y')))
                + struct.pack('<I', num(sh.get('rotationStyle'))) + effects_color(first(sh, 'effectsColor'), where))
    if gl is not None:
        out += struct.pack('<ff', f(gl.get('alpha')), f(gl.get('radius'))) + effects_color(first(gl, 'effectsColor'), where)
    if se is not None:
        out += struct.pack('<f', f(se.get('radius')))                      # soft edge: one float (measured in Hangul)
    if rf is not None:
        sk, sc, al, ps = first(rf, 'skew'), first(rf, 'scale'), first(rf, 'alpha'), first(rf, 'pos')
        out += (struct.pack('<Ifff', pick(EFFECT_ALIGN, rf.get('alignStyle', 'TOP_LEFT'), 'effect alignment'), f(rf.get('radius')),
                            f(rf.get('direction')), f(rf.get('distance')))
                + struct.pack('<4f', f(sk.get('x')), f(sk.get('y')), f(sc.get('x')), f(sc.get('y')))
                + struct.pack('<I', num(rf.get('rotationStyle')))
                + struct.pack('<5f', f(al.get('start')), f(ps.get('start')), f(al.get('end')), f(ps.get('end')),
                              f(rf.get('fadeDirection'))))
    return out


def picture(w, el):
    """SHAPE_COMPONENT_PICTURE: border, image rectangle, crop, margins, brightness, contrast, effect, picture id."""
    ls = first(el, 'lineShape')
    rect = first(el, 'imgRect')
    clip, im, img, dim = first(el, 'imgClip'), first(el, 'inMargin'), first(el, 'img'), first(el, 'imgDim')
    eff = first(el, 'effects')
    line = line_info(ls)
    bid = w.bins.by_ref.get(img.get('binaryItemIDRef')) if img.get('binaryItemIDRef') else 0     # a picture of the original that points to no BinData item: id 0 (HW88)
    if bid is None:
        raise Unsupported(f'picture {img.get("binaryItemIDRef")} has no BinData file (a linked picture: the HWPX has no place for its path)')
    return (line[:12] + points(rect, ('pt0', 'pt1', 'pt2', 'pt3'))
            + struct.pack('<iiii', snum(clip.get('left')), snum(clip.get('top')), snum(clip.get('right')), snum(clip.get('bottom')))
            + struct.pack('<4H', num(im.get('left')), num(im.get('right')), num(im.get('top')), num(im.get('bottom')))
            + struct.pack('<bbBH', snum(img.get('contrast')), snum(img.get('bright')),     # measured in Hangul: contrast first
                          om.inverse(om.IMG_EFFECT).get(img.get('effect', 'REAL_PIC'), 0), bid)
            + struct.pack('<BI', num(ls.get('alpha')) if ls is not None else 0, num(el.get('instid')) & 0xFFFFFFFF)
            + effects(eff, el)
            + struct.pack('<II', num(dim.get('dimwidth')), num(dim.get('dimheight')))
            + (bytes(1) if w.ver >= (5, 1, 0, 0) else b''))      # Hangul 2024 (5.1) ends the record with one more byte (measured)
