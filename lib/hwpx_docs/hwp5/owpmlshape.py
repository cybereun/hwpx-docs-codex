"""Drawing objects (`gso `) -> OWPML: rectangle, ellipse, arc, polygon, curve, line, connect line, container, picture,
OLE, text art (rules HW29-). Every object starts with the common control header (owpmlobj.Common) and a SHAPE_COMPONENT
record (the kind id, offsets, sizes, matrices, line, fill, shadow); the shape itself is in the record below it.
"""
import struct

from . import fmt
from . import owpmlmap as om
from .fmt import Unsupported
from .owpmlmap import ARROW_SIZE, ARROWS, GRADIENT, HATCH, IMG_EFFECT, IMG_MODES, LINE, El, Reader, color

T = fmt.T
SHADOW = dict(enumerate(om.SHADOW))             # all 9 measured in Hangul (owpmlmap.SHADOW)


def pt(tag, x, y):
    return El(tag, {'x': x, 'y': y})


def fill_brush(r, place, head=None):
    """The fill part of an object or border fill (r at the fill type) -> hc:fillBrush, or None when there is no fill."""
    ftype = r.u('I')
    if ftype & ~7:
        raise Unsupported(f'fill type {ftype}', place)
    parts, grad = [], None                              # colour, gradient, image: the parts of one fill brush in this order (type 3, 6)
    center = 50
    if ftype & 1:
        face, hatch, pat = r.u('IIi')
        at = {'faceColor': color(face), 'hatchColor': color(hatch)}
        if pat >= 0:
            if pat >= len(HATCH):
                raise Unsupported(f'hatch style {pat}', place)
            at['hatchStyle'] = HATCH[pat]
        at['alpha'] = 0
        parts.append(El('hc:winBrush', at))
    if ftype & 4:
        kind, angle, cx, cy, step, num = r.u('biiiii')
        if num > 2:
            r.raw(4 * num)                              # the stop positions: OWPML keeps only the colours
        cols = [r.u('I') for _ in range(num)]
        grad = El('hc:gradation', {'type': GRADIENT[min(kind, 4)], 'angle': angle,
                                   'centerX': cx, 'centerY': cy, 'step': step, 'colorNum': num, 'stepCenter': center, 'alpha': 0}
                  ).add(*[El('hc:color', {'value': color(c)}) for c in cols])
        parts.append(grad)
    if ftype & 2:
        # image fill: mode byte, brightness, contrast, effect, BIN_DATA number; the mode names are Hangul 2024's (IMG_MODES: measured
        # one value at a time, 0-15; 16 and above write no brush)
        if head is None:
            raise Unsupported(f'image fill with fill type {ftype}', place)
        mode, contrast, bright, effect, binid = r.u('BbbBH')
        if mode >= len(IMG_MODES) or effect >= len(IMG_EFFECT):
            raise Unsupported(f'image fill mode {mode} / effect {effect}', place)
        parts.append(El('hc:imgBrush', {'mode': IMG_MODES[mode]},
                        El('hc:img', {'binaryItemIDRef': head.bin_ref(binid, place), 'bright': bright, 'contrast': contrast,
                                      'effect': IMG_EFFECT[effect], 'alpha': 0})))
    if r.left() >= 4:
        extra = r.raw(r.u('I'))                         # the extra fill properties: a gradient keeps its step centre here
        if extra and grad is not None:
            grad.at['stepCenter'] = extra[0]
    if ftype and r.left() >= 1:
        r.u('B')                                        # a byte that follows every fill but "no fill"
    return El('hc:fillBrush', None, *parts) if parts else None


class Shape:
    """SHAPE_COMPONENT of an object, decoded. `child` = it sits in a container (one kind id instead of two)."""

    def __init__(self, node, place, child=False):
        d = node.d
        self.node, self.place = node, place
        self.kind = d[:4][::-1].decode('latin-1')
        r = Reader(d, 4 if child else 8)
        self.x, self.y = r.u('ii')
        self.level, self.version = r.u('HH')
        self.org = r.u('II')
        self.cur = r.u('II')
        self.attr = r.u('I')
        self.angle = r.u('h')
        self.center = r.u('ii')
        n = r.u('H')
        self.mats = [r.u('6d') for _ in range(1 + 2 * n)]
        self.r = r
        cd = node.first(T['CTRL_DATA'])                 # a link (`href`) or a parameter set: the last child of the shape
        self.href, self.pset = shape_data(cd.d, place) if cd is not None else ('', None)

    def head_elements(self):
        a = self.attr
        out = [pt('hp:offset', self.x & 0xFFFFFFFF, self.y & 0xFFFFFFFF),
               El('hp:orgSz', {'width': self.org[0], 'height': self.org[1]}),
               El('hp:curSz', {'width': 0 if self.cur[0] == self.org[0] else self.cur[0],
                               'height': 0 if self.cur[1] == self.org[1] else self.cur[1]}),
               El('hp:flip', {'horizontal': a & 1, 'vertical': a >> 1 & 1}),
               El('hp:rotationInfo', {'angle': self.angle, 'centerX': self.center[0], 'centerY': self.center[1],
                                      'rotateimage': a >> 19 & 1})]
        ri = El('hp:renderingInfo')
        names = ['hc:transMatrix'] + ['hc:scaMatrix', 'hc:rotMatrix'] * ((len(self.mats) - 1) // 2)
        for nm, m in zip(names, self.mats):
            ri.add(El(nm, {f'e{i + 1}': num(v) for i, v in enumerate(m)}))
        out.append(ri)
        return out

    def line_fill_shadow(self, head=None):
        """-> (lineShape, fillBrush or None, shadow); also reads the instance id."""
        r = self.r
        lcolor, lwidth, lattr = r.u('IiI')
        outline = r.u('B')
        ltype = lattr & 63
        line = El('hp:lineShape', {'color': color(lcolor), 'width': lwidth,
                                   'style': LINE[ltype] if ltype < len(LINE) else 'SOLID',
                                   'endCap': 'FLAT' if lattr >> 6 & 1 else 'ROUND',
                                   'headStyle': ARROWS[min(lattr >> 10 & 63, 9)], 'tailStyle': ARROWS[min(lattr >> 16 & 63, 9)],
                                   'headfill': lattr >> 30 & 1, 'tailfill': lattr >> 31 & 1,
                                   'headSz': ARROW_SIZE[min(lattr >> 22 & 15, 8)], 'tailSz': ARROW_SIZE[min(lattr >> 26 & 15, 8)],
                                   'outlineStyle': om.OUTLINE_STYLE[min(outline, 2)], 'alpha': 0})
        brush = fill_brush(r, self.place, head)
        if r.left() < 16:           # the oldest records end after the fill: Hangul 2024 writes a shadow of type NONE, black (3 files)
            st, scolor, sx, sy = 0, 0, 0, 0
            self.inst, salpha = 0, 0
        else:
            st, scolor, sx, sy = r.u('IIii')
            if st not in SHADOW:
                raise Unsupported(f'shadow type {st}', self.place)
            self.inst = r.u('I') if r.left() >= 4 else 0
            line.at['alpha'] = r.u('B') if r.left() >= 1 else 0
            salpha = r.u('B') if r.left() >= 1 else 0
        shadow = El('hp:shadow', {'type': SHADOW[st], 'color': color(scolor), 'offsetX': sx, 'offsetY': sy, 'alpha': salpha})
        return line, brush, shadow


def num(v):
    """A double as Hangul writes it: 6 decimals, trailing zeros dropped (1, 2.95614, -0.80288, 1.087719)."""
    s = ('%.6f' % v).rstrip('0').rstrip('.')
    if float(s or 0) != v:                                  # more digits than Hangul keeps: the value of the original stays (HW107)
        return repr(v)
    return '0' if s in ('-0', '') else s


# ---- the shapes ---------------------------------------------------------------------------------------------------------
def common_attrs(c, sh, extra=None):
    """The attributes every drawing object carries. c = owpmlobj.Common, or None for an object inside a container."""
    if c is None:
        at = {'id': 0, 'zOrder': 0, 'numberingType': 'NONE', 'textWrap': 'TOP_AND_BOTTOM', 'textFlow': 'BOTH_SIDES'}
    else:
        at = {'id': c.inst, 'zOrder': c.z, 'numberingType': om.NUMBERING[c.attr >> 26 & 3],
              'textWrap': c.wrap, 'textFlow': c.flow}
    # attribute bit 30 = lock + dropcapstyle DoubleLine (3 shapes of one file in Hangul 2024's HWPX); bit 31 has no sample
    if c is not None and c.attr >> 31 & 1:
        raise Unsupported('object attribute bit 31', sh.place)
    lock = c.attr >> 30 & 1 if c is not None else 0
    at.update({'lock': lock, 'dropcapstyle': 'DoubleLine' if lock else 'None', 'href': sh.href, 'groupLevel': sh.level,
               'instid': sh.inst})
    at.update(extra or {})
    return at


def draw_text(sec, sc):
    """The text of a rectangle / ellipse ... (a LIST_HEADER below the SHAPE_COMPONENT) -> hp:drawText, or None."""
    from . import owpmlobj
    lists = owpmlobj.lists_of(sc)
    if not lists:
        return None
    lh, paras = lists[0]
    attr = struct.unpack_from('<I', lh.d, 4)[0]
    ml, mr, mt, mb, width = struct.unpack_from('<4HI', lh.d, 8)
    # 33 bytes: the number at 28 = editable (0 / 1); 33 + a parameter set when byte 32 is 0xff: `1b02 0100 0000 0040 0100 <len> <chars>`
    # = the name of the text box (rule HW53: a text box named in Hangul 2024's HWPX, editable in another)
    name, editable = '', 0
    if len(lh.d) >= 33:
        editable = struct.unpack_from('<I', lh.d, 28)[0]
        if editable > 1:
            raise Unsupported(f'text box editable value {editable}', sec.place)
        if len(lh.d) > 33:
            ex = lh.d[33:]
            if lh.d[32] != 0xff or ex[:10] != bytes.fromhex('1b02' '0100' '0000' '0040' '0100') or len(ex) < 12 \
                    or len(ex) != 12 + 2 * struct.unpack_from('<H', ex, 10)[0]:
                raise Unsupported('text box header with an unknown extra part', sec.place)
            name = ex[12:].decode('utf-16-le', 'replace')
    return El('hp:drawText', {'lastWidth': width, 'name': name, 'editable': editable},
              owpmlobj.sub_list(sec, attr, paras),
              El('hp:textMargin', {'left': ml, 'right': mr, 'top': mt, 'bottom': mb}))


def shape_el(sec, tag, c, sh, extra_attrs, parts, text=True, fill=True):
    """Assemble one object: head, line, fill, shadow, [drawText], the shape parts, and (top level) size / position."""
    from . import owpmlobj
    line, brush, shadow = sh.line_fill_shadow(sec.head)
    el = El(tag, common_attrs(c, sh, extra_attrs))
    el.add(*sh.head_elements())
    el.add(line)
    if fill:
        el.add(brush)
    el.add(shadow)
    if text:
        el.add(draw_text(sec, sh.node))
    el.add(*parts)
    if c is not None:
        if shadow.at['type'] != 'NONE':
            c.margins = (0, 0, 0, 0)       # Hangul adds the room of a shadow to the margin; the saved HWPX has the user's (0)
        el.add(*c.tail(sec))
    return el


def rect(sec, c, sh, rec):
    ratio = rec.d[0]
    pts = [struct.unpack_from('<ii', rec.d, 1 + 8 * k) for k in range(4)]
    return shape_el(sec, 'hp:rect', c, sh, {'ratio': ratio}, [pt(f'hc:pt{k}', *p) for k, p in enumerate(pts)])


def ellipse(sec, c, sh, rec):
    attr = struct.unpack_from('<I', rec.d, 0)[0]
    p = [struct.unpack_from('<ii', rec.d, 4 + 8 * k) for k in range(7)]
    arc = ['NORMAL', 'PIE', 'CHORD', 'ARC'][min(attr >> 2 & 3, 3)]
    parts = [pt(n, *v) for n, v in zip(('hc:center', 'hc:ax1', 'hc:ax2', 'hc:start1', 'hc:end1', 'hc:start2', 'hc:end2'), p)]
    return shape_el(sec, 'hp:ellipse', c, sh, {'intervalDirty': attr & 1, 'hasArcPr': attr >> 1 & 1, 'arcType': arc}, parts)


def arc(sec, c, sh, rec):
    t = rec.d[0]
    p = [struct.unpack_from('<ii', rec.d, 1 + 8 * k) for k in range(3)]
    kind = om.ARC_TYPE[min(t, 2)]
    return shape_el(sec, 'hp:arc', c, sh, {'type': kind}, [pt(n, *v) for n, v in zip(('hc:center', 'hc:ax1', 'hc:ax2'), p)])


def polygon(sec, c, sh, rec):
    n = struct.unpack_from('<i', rec.d, 0)[0]
    pts = [struct.unpack_from('<ii', rec.d, 4 + 8 * k) for k in range(n)]
    return shape_el(sec, 'hp:polygon', c, sh, {}, [pt('hc:pt', *p) for p in pts])


def curve(sec, c, sh, rec):
    n = struct.unpack_from('<i', rec.d, 0)[0]
    pts = [struct.unpack_from('<ii', rec.d, 4 + 8 * k) for k in range(n)]
    types = rec.d[4 + 8 * n:4 + 8 * n + n - 1]
    segs = [El('hp:seg', {'type': 'CURVE' if types[k] else 'LINE', 'x1': pts[k][0], 'y1': pts[k][1], 'x2': pts[k + 1][0],
                          'y2': pts[k + 1][1]}) for k in range(n - 1)]
    return shape_el(sec, 'hp:curve', c, sh, {}, segs)


def line(sec, c, sh, rec):
    x1, y1, x2, y2, rev = struct.unpack_from('<4iI', rec.d, 0)
    return shape_el(sec, 'hp:line', c, sh, {'isReverseHV': rev & 1}, [pt('hc:startPt', x1, y1), pt('hc:endPt', x2, y2)],
                    text=False, fill=False)


def fnum(f):
    """A float (single precision) as Hangul prints it in the picture effects: 0.5, 600, -25, 0.997."""
    s = '%g' % struct.unpack('<f', struct.pack('<f', f))[0]
    return s


COLOR_EFFECTS = om.COLOR_EFFECT                  # 11 measured in Hangul (owpmlmap.COLOR_EFFECT)


def effects_color(r, place):
    """A colour with its colour effects: type (0 = RGB), the colour as 0x00RRGGBB, the number of effects, each (id, value)."""
    ctype = r.u('I')
    if ctype != 0:
        raise Unsupported(f'effects colour type {ctype}', place)
    rgb = r.u('I')
    el = El('hp:effectsColor', {'type': 'RGB', 'schemeIdx': -1, 'systemIdx': -1, 'presetIdx': -1})
    el.add(El('hp:rgb', {'r': rgb >> 16 & 255, 'g': rgb >> 8 & 255, 'b': rgb & 255}))
    for _ in range(r.u('I')):
        eid, val = r.u('If')
        if eid not in COLOR_EFFECTS:
            raise Unsupported(f'colour effect {eid:#x}', place)
        el.add(El('hp:effect', {'type': COLOR_EFFECTS[eid], 'value': fnum(val)}))
    return el


def picture_effects(r, place):
    """The effects of a picture: a flag word (1 shadow, 2 glow, 4 soft edge, 8 reflection) and one block each, in that order."""
    flags = r.u('I')
    if flags & ~(1 | 2 | 4 | 8):
        raise Unsupported(f'picture effect flags {flags:#x}', place)
    el = El('hp:effects')
    if flags & 1:
        style, alpha, radius, direction, distance, align = r.u('IffffI')
        skx, sky, scx, scy = r.u('4f')
        rot = r.u('I')
        if style not in (0, 1):
            raise Unsupported(f'shadow style {style}', place)
        el.add(El('hp:shadow', {'style': om.SHADOW_STYLE[style], 'alpha': fnum(alpha), 'radius': fnum(radius),
                                'direction': fnum(direction), 'distance': fnum(distance), 'alignStyle': om.EFFECT_ALIGN[min(align, 8)],
                                'rotationStyle': rot},
                  El('hp:skew', {'x': fnum(skx), 'y': fnum(sky)}), El('hp:scale', {'x': fnum(scx), 'y': fnum(scy)}),
                  effects_color(r, place)))
    if flags & 2:
        alpha, radius = r.u('ff')
        el.add(El('hp:glow', {'alpha': fnum(alpha), 'radius': fnum(radius)}, effects_color(r, place)))
    if flags & 4:                                    # soft edge: one float (2 files of Hangul 2024's HWPX: 300 and 1000 / 500)
        el.add(El('hp:softEdge', {'radius': fnum(r.u('f'))}))
    if flags & 8:
        align, radius, direction, distance = r.u('Ifff')
        skx, sky, scx, scy = r.u('4f')
        rot = r.u('I')
        a0, p0, a1, p1, fade = r.u('5f')
        el.add(El('hp:reflection', {'alignStyle': om.EFFECT_ALIGN[min(align, 8)], 'radius': fnum(radius), 'direction': fnum(direction),
                                    'distance': fnum(distance), 'rotationStyle': rot, 'fadeDirection': fnum(fade)},
                  El('hp:skew', {'x': fnum(skx), 'y': fnum(sky)}), El('hp:scale', {'x': fnum(scx), 'y': fnum(scy)}),
                  El('hp:alpha', {'start': fnum(a0), 'end': fnum(a1)}), El('hp:pos', {'start': fnum(p0), 'end': fnum(p1)})))
    return el


def border_line(legacy, lcolor, lwidth, lattr, alpha=0):
    """The border of a picture / OLE object. The 2014 build writes the bits of the attribute and OUTER; Hangul 2018+ (checked on
    Hangul 2024's HWPX of 7 files) writes no head / tail fill and NORMAL."""
    ltype = lattr & 63
    return El('hp:lineShape', {'color': color(lcolor), 'width': lwidth, 'style': LINE[ltype] if ltype < len(LINE) else 'SOLID',
                               'endCap': 'FLAT' if lattr >> 6 & 1 else 'ROUND', 'headStyle': 'NORMAL', 'tailStyle': 'NORMAL',
                               'headfill': lattr >> 30 & 1 if legacy else 0, 'tailfill': lattr >> 31 & 1 if legacy else 0,
                               'headSz': ARROW_SIZE[min(lattr >> 22 & 15, 8)], 'tailSz': ARROW_SIZE[min(lattr >> 26 & 15, 8)],
                               'outlineStyle': 'OUTER' if legacy else 'NORMAL', 'alpha': alpha})


def picture(sec, c, sh, sc):
    rec = sc.first(T['SHAPE_COMPONENT_PICTURE'])
    r = Reader(rec.d)
    lcolor, lwidth, lattr = r.u('IiI')
    pts = [r.u('ii') for _ in range(4)]
    cl, ct, cr, cb = r.u('4i')
    ml, mr, mt, mb = r.u('4H')
    contrast, bright, effect, binid = r.u('bbBH')          # the record keeps the contrast first (a picture with 70 / -50 in Hangul 2024's HWPX)
    if effect >= len(IMG_EFFECT):
        raise Unsupported(f'picture effect {effect}', sec.place)
    lalpha, inst = 0, 0
    eff = El('hp:effects')
    if r.left() >= 9 + 8:
        lalpha, inst = r.u('BI')
        eff = picture_effects(r, sec.place)
    dw, dh = r.u('II') if r.left() >= 8 else (0, 0)
    sh.inst = inst
    el = El('hp:pic', common_attrs(c, sh, {'reverse': sh.attr >> 24 & 1}))
    el.add(*sh.head_elements())
    if lcolor or lwidth or lattr:
        el.add(border_line(sec.head.legacy, lcolor, lwidth, lattr, lalpha))
    img = El('hc:img', {'binaryItemIDRef': sec.bin_ref(binid, sec.place), 'bright': bright, 'contrast': contrast,
                        'effect': IMG_EFFECT[effect], 'alpha': 0})
    parts = [El('hp:imgRect', None, *[pt(f'hc:pt{k}', *p) for k, p in enumerate(pts)]),
             El('hp:imgClip', {'left': cl, 'right': cr, 'top': ct, 'bottom': cb}),
             El('hp:inMargin', {'left': ml, 'right': mr, 'top': mt, 'bottom': mb}),
             El('hp:imgDim', {'dimwidth': dw, 'dimheight': dh})]
    # the picture comes after the rectangle in the 2014 build's HWPX (hwp2hwpx pairs), before it in Hangul 2018+ (Hangul 2024 file)
    el.add(*(parts + [img] if sec.head.legacy else [img] + parts), eff)
    if c is not None:                                   # not inside a container
        el.add(*c.tail(sec))
    return el


def ole(sec, c, sh, sc):
    rec = sc.first(T['SHAPE_COMPONENT_OLE'])
    r = Reader(rec.d)
    attr, ew, eh, binid, lcolor, lwidth, lattr = r.u('IIIHIiI')
    # attribute (measured in Hangul 2024, both directions; HW74): bits 0-7 draw aspect, bit 8 has moniker, bits 9-15 the equation base
    # line, bits 16-21 object type; the 4 bytes after the border of a type other than EQUATION are 0 or noise
    aspect, otype = attr & 255, attr >> 16 & 63
    if aspect not in om.OLE_ASPECT or otype >= len(om.OLE_TYPE) or attr >> 22 or (otype != 4 and attr >> 9 & 127):
        raise Unsupported(f'OLE attribute {attr:#x}', sec.place)
    # the OLE record keeps no instance id: Hangul 2018+ writes 0, the 2014 build id - 0x3FFFFFFF (the other objects keep theirs)
    sh.inst = 0 if not sec.head.legacy else ((c.inst if c is not None else 0) - 0x3FFFFFFF) & 0xFFFFFFFF
    el = El('hp:ole', common_attrs(c, sh, {'objectType': om.OLE_TYPE[otype], 'binaryItemIDRef': sec.bin_ref(binid, sec.place),
                                           'hasMoniker': attr >> 8 & 1, 'drawAspect': om.OLE_ASPECT[aspect],
                                           'eqBaseLine': attr >> 9 & 127 if otype == 4 else 0}))
    el.add(*sh.head_elements())
    el.add(pt('hc:extent', ew, eh), border_line(sec.head.legacy, lcolor, lwidth, lattr))
    if c is not None:
        el.add(*c.tail(sec))
    return el


TEXT_SHAPES = dict(enumerate(om.TEXT_SHAPE))      # 55 shapes, measured in Hangul (owpmlmap.TEXT_SHAPE)
TEXT_SHADOW = SHADOW                              # the 9 kinds of every drawing object


def textart(sec, c, sh, sc):
    rec = sc.first(0x5A)
    if rec is None:
        raise Unsupported('text art without its record', sec.place)
    r = Reader(rec.d)
    pts = [r.u('ii') for _ in range(4)]
    text, font, style = r.wstr(), r.wstr(), r.wstr()
    ftype, shape, lsp, csp, align = r.u('5I')
    stype, sx, sy, scol = r.u('IiiI')
    if shape not in TEXT_SHAPES or stype not in TEXT_SHADOW or align >= len(om.TEXT_ALIGN) or ftype not in om.TEXT_FONT:
        raise Unsupported(f'text art shape {shape} / shadow {stype} / align {align} / font {ftype}', sec.place)
    salpha = r.u('B') if r.left() else 0
    pr = El('hp:textartPr', {'fontName': font, 'fontStyle': style, 'fontType': om.TEXT_FONT[ftype],
                             'textShape': TEXT_SHAPES[shape], 'lineSpacing': lsp, 'charSpacing': csp,
                             'align': om.TEXT_ALIGN[align]},
            El('hp:shadow', {'type': TEXT_SHADOW[stype], 'color': color(scol), 'offsetX': sx, 'offsetY': sy, 'alpha': salpha}))
    return shape_el(sec, 'hp:textart', c, sh, {'text': text}, [pt(f'hc:pt{k}', *p) for k, p in enumerate(pts)] + [pr], text=False)


def connect_line(sec, c, sh, sc):
    rec = sc.first(T['SHAPE_COMPONENT_LINE'])
    r = Reader(rec.d)
    x1, y1, x2, y2, ctype, sref, sidx, eref, eidx, n = r.u('4iIIIIII')
    pts = [r.u('iiH') for _ in range(n)]
    if ctype >= len(om.CONNECT_TYPES):
        raise Unsupported(f'connect line type {ctype}', sec.place)
    parts = [El('hp:startPt', {'x': x1, 'y': y1, 'subjectIDRef': sref, 'subjectIdx': sidx}),
             El('hp:endPt', {'x': x2, 'y': y2, 'subjectIDRef': eref, 'subjectIdx': eidx}),
             El('hp:controlPoints', None, *[El('hp:point', {'x': x, 'y': y, 'type': t}) for x, y, t in pts])]
    return shape_el(sec, 'hp:connectLine', c, sh, {'type': om.CONNECT_TYPES[ctype]}, parts, text=False, fill=False)


def container(sec, c, sh, sc):
    """A group: its SHAPE_COMPONENT lists the ids of its children, each child is a SHAPE_COMPONENT record below it
    (with one kind id instead of two)."""
    r = sh.r
    n = r.u('H')
    r.raw(4 * n)
    sh.inst = r.u('I') if r.left() >= 4 else 0       # the oldest container records end after the child kinds (1 file)
    el = El('hp:container', common_attrs(c, sh))
    el.add(*sh.head_elements())
    for k in sc.kids:
        if k.tag == T['SHAPE_COMPONENT']:
            el.add(build(sec, None, Shape(k, sec.place, child=True), k))
    if c is not None:
        el.add(*c.tail(sec))
    return el


def shape_data(d, place):
    """The CTRL_DATA below a SHAPE_COMPONENT -> (href, hp:parameterset or None) (rule HW53; read from Hangul 2024's HWPX of 5 files).
    Six zero bytes: nothing. Else a parameter set `1b02 <count> 0000` with one item `<id> 8000` = a nested set `<id> <count> 0000`
    whose items are (id, type, value): type 1 a string (length + UTF-16), type 9 a 4-byte number. The set 0x026f is the link set: its
    string 0x0265 is the `href` (`\\:` undone; the other strings repeat it); an empty one writes `<hp:parameterset cnt="0"
    name="539"/>` at the end of the shape. Any other nested set with numbers only writes a `hp:parameterset` with a `hp:listParam`
    (cnt / name = the set ids in decimal). Any other layout stops."""
    import re
    if d == bytes(6):
        return '', None
    try:
        top, count, zero = struct.unpack_from('<HHH', d, 0)
        if top != 0x021b or zero or count != 1:
            raise ValueError
        item, kind, sid, n, zero = struct.unpack_from('<HHHHH', d, 6)
        if kind != 0x8000 or sid != item or zero:
            raise ValueError
        pos, href, nums = 16, '', []
        for _ in range(n):
            iid, kind = struct.unpack_from('<HH', d, pos)
            pos += 4
            if kind == 1 and sid == 0x026f:
                ln = struct.unpack_from('<H', d, pos)[0]
                text = d[pos + 2:pos + 2 + 2 * ln].decode('utf-16-le', 'replace')
                pos += 2 + 2 * ln
                if iid == 0x0265 and not href:
                    href = re.sub(r'\\([:;])', r'\1', text)
            elif kind == 9 and sid != 0x026f:
                nums.append(El('hp:unsignedintegerParam', {'name': iid}, text=str(struct.unpack_from('<I', d, pos)[0])))
                pos += 4
            else:
                raise ValueError
        if pos != len(d):
            raise ValueError
    except (ValueError, struct.error):
        raise Unsupported('gso CTRL_DATA that is neither a link nor a set of numbers', place) from None
    if sid == 0x026f:
        return href, (None if n else El('hp:parameterset', {'cnt': 0, 'name': 0x021b}))
    return '', El('hp:parameterset', {'cnt': 1, 'name': 0x021b}, El('hp:listParam', {'cnt': n, 'name': sid}, *nums))


def gso(sec, node):
    from . import owpmlobj
    c = owpmlobj.Common(sec, node.d)
    sc = node.first(T['SHAPE_COMPONENT'])
    if sc is None:
        raise Unsupported('gso without SHAPE_COMPONENT', sec.place)
    sh = Shape(sc, sec.place)
    lists = [l for l in owpmlobj.lists_of(node) if l[0].at < sc.at]       # a caption list comes before the shape record
    if lists:
        c.caption = lists[0]
    return [build(sec, c, sh, sc)]


SPECIFIC = {'$rec': (T['SHAPE_COMPONENT_RECTANGLE'], rect), '$ell': (T['SHAPE_COMPONENT_ELLIPSE'], ellipse),
            '$arc': (T['SHAPE_COMPONENT_ARC'], arc), '$pol': (T['SHAPE_COMPONENT_POLYGON'], polygon),
            '$cur': (T['SHAPE_COMPONENT_CURVE'], curve), '$lin': (T['SHAPE_COMPONENT_LINE'], line)}


def build(sec, c, sh, sc):
    direct = {'$con': container, '$pic': picture, '$ole': ole, '$tat': textart, '$col': connect_line}
    if sh.kind in direct:
        el = direct[sh.kind](sec, c, sh, sc)
    else:
        if sh.kind not in SPECIFIC:
            raise Unsupported(f'drawing object {sh.kind!r}', sec.place)
        tag, fn = SPECIFIC[sh.kind]
        rec = sc.first(tag)
        if rec is None:
            raise Unsupported(f'drawing object {sh.kind!r} without its record', sec.place)
        el = fn(sec, c, sh, rec)
    return el.add(sh.pset)
