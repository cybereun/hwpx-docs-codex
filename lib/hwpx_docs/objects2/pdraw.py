"""Preview drawing of picture effects, captions and aligned floating objects (C6.02, C6.13, C6.14), registered by
preview/drawers/objects2.py.

A picture with `bright`, `contrast`, `effect`, `crop`, `border` or `caption` is replaced, before the layout (a prepare step), by the
item `{"picfx": {...}}`; the drawer draws it with an SVG clip (crop), a colour filter (gray, black and white, contrast, brightness:
measured on Hangul 2024 renders of the pic_* fixtures) and a border. An `object` with a `caption` grows by the caption's room and
draws the caption text; a floating `object` with `halign`, `valign` or `hrel` becomes a floating shape of an empty paragraph that the
layout places. Limits (rules OB15): the caption of a rect / ellipse / line is not drawn; a caption beside an object is one line;
`valign` center / bottom on `page` uses the margins of the spec's `page` (header and footer are not subtracted).
"""
import base64
import itertools
import os
import sys

from . import draw as D

MIME = {'png': 'png', 'jpg': 'jpeg', 'jpeg': 'jpeg', 'bmp': 'bmp', 'gif': 'gif'}
FX_KEYS = ('bright', 'contrast', 'effect', 'crop', 'border', 'caption')
PT = 25.4 / 72
CAP_PT = 9
_ids = itertools.count(1)


def cap_text(cap, n, number_default):
    number = cap.get('number', number_default)
    label = cap.get('label', '그림' if number else '')
    return ' '.join(x for x in (label, str(n) if number else '', cap.get('text', '')) if x)


def cap_room(cap, w, h):
    """(new w, new h, caption box x, y relative to the object, box w, h) of an object w x h mm with a caption."""
    c = {'text': cap} if isinstance(cap, str) else cap
    side = c.get('side', 'bottom')
    gap = c.get('gap', 3.0)
    ch = CAP_PT * PT * 1.6
    cw = c.get('width', 30.0) if side in ('left', 'right') else w
    if side == 'bottom':
        return w, h + gap + ch, 0, h + gap, cw, ch
    if side == 'top':
        return w, h + gap + ch, 0, 0, cw, ch
    if side == 'left':
        return w + gap + cw, h, 0, 0, cw, ch
    return w + gap + cw, h, w + gap, 0, cw, ch


def anchor_aligned(node, key, o):
    """A floating object (`object` or `ole`) with `halign` / `valign` / `hrel` becomes a floating shape of an empty paragraph, which the
    layout places (`halign`, `hrel` and `vpos` as for a rect: the layout aligns it in the page body or on the paper, layout.shape_at)."""
    from ..preview.layout import object_of
    pos = dict(o.get('pos') or {})
    rel = pos.get('rel', 'para')
    shape = dict(type='object', obj=object_of({key: o}, {}), x=pos.get('x', 0), y=pos.get('y', 0), rel=rel,
                 hrel=pos.get('hrel', 'column' if rel == 'para' else rel), halign=pos.get('halign', 'left'),
                 vpos=pos.get('valign', 'top'), w=o['w'], h=o['h'], wrap=o.get('wrap', 'square'), side=o.get('side', 'both_sides'))
    node.pop(key)
    node.update(p='', shapes=[shape])


def shape_captions(node, n0):
    """The caption of a rect / ellipse of the paragraph's `shapes` (also a text box: the layout draws its text, so the caption is a
    shape of its own next to it): a label shape `gap` mm beside the object, on the side the spec says. n0 = pictures and drawing
    objects counted before this paragraph (the number of the caption)."""
    from ..preview.layout import object_of
    extra = []
    for i, s in enumerate(node['shapes']):
        cap = s.get('caption') if isinstance(s, dict) else None
        if not cap or s.get('type') not in ('rect', 'ellipse') or 'w' not in s:
            continue
        c = {'text': cap} if isinstance(cap, str) else cap
        _, _, _, _, cw, ch = cap_room(c, s['w'], s['h'])
        gap, side = c.get('gap', 3.0), c.get('side', 'bottom')
        dx, dy = {'bottom': (0, s['h'] + gap), 'top': (0, -ch - gap), 'left': (-cw - gap, 0), 'right': (s['w'] + gap, 0)}[side]
        lab = {'kind': 'label', 'w': cw, 'h': ch, 'text': cap_text(c, n0 + i + 1, False)}
        sh = dict(type='object', obj=object_of({'object': lab}, {}), x=s.get('x', 0) + dx, y=s.get('y', 0) + dy, rel=s.get('rel', 'paper'),
                  w=cw, h=ch, wrap='in_front_of_text', side='both_sides')
        sh.update({k: s[k] for k in ('hrel', 'vpos') if k in s})
        if side in ('top', 'bottom') and 'halign' in s:
            sh['halign'] = s['halign']
        extra.append(sh)
    node['shapes'] = list(node['shapes']) + extra


def prepare(node, pic_dir, state=None):
    """Walk the spec: a pic with effects or a caption -> picfx; an object with a caption -> room for it; an aligned floating object
    -> a shape. The caption number counts every picture and drawing object before it, as Hangul numbers them (numberingType PICTURE)."""
    if state is None:
        state = {'n': 0}
    if isinstance(node, list):
        for x in node:
            prepare(x, pic_dir, state)
        return
    if not isinstance(node, dict):
        return
    if isinstance(node.get('shapes'), list) and any(isinstance(s, dict) and s.get('caption') for s in node['shapes']):
        shape_captions(node, state['n'])
    state['n'] += sum(1 for s in node.get('shapes') or [] if not (isinstance(s, dict) and s.get('obj', {}).get('name') == 'object'))      # core drawing objects are numbered like pictures
    p = node.get('pic')
    if isinstance(p, dict):
        state['n'] += 1
        if any(k in p for k in FX_KEYS):
            path = os.path.join(pic_dir, p['src'])
            if not os.path.exists(path):
                print('PREVIEW PICTURE MISSING', p['src'], file=sys.stderr)
            else:
                ext = os.path.splitext(path)[1].lower().lstrip('.')
                uri = 'data:image/%s;base64,%s' % (MIME.get(ext, 'png'), base64.b64encode(open(path, 'rb').read()).decode())
                item = {k: v for k, v in p.items() if k != 'src'}
                node['picfx'] = dict(item, data=uri, cap_no=state['n'])
                del node['pic']
    ole = node.get('ole')
    if isinstance(ole, dict):
        ole.setdefault('w', 26.72)                              # Hangul's size of a new OLE object (7574 x 6225 hu)
        ole.setdefault('h', 21.96)
        view = os.path.join(pic_dir, ole['view']) if ole.get('view') else None
        if view and os.path.exists(view) and '_view' not in ole:
            ole['_view'] = 'data:image/png;base64,' + base64.b64encode(open(view, 'rb').read()).decode()
        if not ole.get('inline', True) and any(k in (ole.get('pos') or {}) for k in ('hrel', 'halign', 'valign')):
            anchor_aligned(node, 'ole', ole)
    o = node.get('object')
    if isinstance(o, dict) and '_box' not in o:
        if o.get('caption'):
            o['_box'] = (o['w'], o['h'])
            o['cap_no'] = state['n']
            o['w'], o['h'] = cap_room(o['caption'], o['w'], o['h'])[:2]
        if not o.get('inline', True) and any(k in (o.get('pos') or {}) for k in ('hrel', 'halign', 'valign')):
            anchor_aligned(node, 'object', o)
    for v in list(node.values()):
        if isinstance(v, (list, dict)):
            prepare(v, pic_dir, state)


def caption_svg(cap, n, x, y, w, ch, number_default):
    c = {'text': cap} if isinstance(cap, str) else cap
    t = cap_text(c, n, number_default).replace('&', '&amp;').replace('<', '&lt;')
    return (f'<text x="{D.f3(x + w / 2)}" y="{D.f3(y + ch * 0.72)}" text-anchor="middle" font-size="{D.f3(CAP_PT * PT)}" '
            f'font-family="\'함초롬돋움\',\'Malgun Gothic\',sans-serif" fill="#000000">{t}</text>')


def filters(item, fid):
    """<filter> for effect / contrast / brightness (Hangul 2024: brightness b adds b % of the range; contrast c scales by 1 + 0.016 c
    around mid grey; gray = luma 0.299 / 0.587 / 0.114; black and white = threshold at mid grey)."""
    fx, c, b = item.get('effect', 'real'), item.get('contrast', 0), item.get('bright', 0)
    if fx == 'real' and not c and not b:
        return ''
    parts = []
    if fx in ('gray', 'bw'):
        parts.append('<feColorMatrix type="matrix" values="0.299 0.587 0.114 0 0  0.299 0.587 0.114 0 0  0.299 0.587 0.114 0 0  0 0 0 1 0"/>')
    if fx == 'bw':
        parts.append('<feComponentTransfer><feFuncR type="discrete" tableValues="0 1"/><feFuncG type="discrete" tableValues="0 1"/>'
                     '<feFuncB type="discrete" tableValues="0 1"/></feComponentTransfer>')
    if c or b:
        k = 1 + 0.016 * c
        icpt = 0.5 - 0.5 * k + b / 100
        fn = ''.join(f'<{f} type="linear" slope="{k:.3f}" intercept="{icpt:.3f}"/>' for f in ('feFuncR', 'feFuncG', 'feFuncB'))
        parts.append(f'<feComponentTransfer>{fn}</feComponentTransfer>')
    return f'<filter id="{fid}" color-interpolation-filters="sRGB">{"".join(parts)}</filter>'


def offsets(cap, cw, ch):
    """Where the object sits inside the room of its caption: (x, y) in mm."""
    if not isinstance(cap, dict):
        return 0.0, 0.0
    gap = cap.get('gap', 3.0)
    side = cap.get('side', 'bottom')
    return (cw + gap if side == 'left' else 0.0), (ch + gap if side == 'top' else 0.0)


def picfx(item, style):
    w, h = item['w'], item['h']
    cap = item.get('caption')
    W, H, cx, cy, cw, ch = cap_room(cap, w, h) if cap else (w, h, 0, 0, 0, 0)
    ox, oy = offsets(cap, cw, ch) if cap else (0.0, 0.0)

    def draw(x, y):
        n = next(_ids)
        x0, y0 = x, y
        x, y = x + ox, y + oy
        fid, cid = f'pfx{n}', f'pcl{n}'
        l, t, r, b = (v / 100 for v in (item.get('crop') or [0, 0, 0, 0]))
        iw, ih = w / (1 - l - r), h / (1 - t - b)
        defs = filters(item, fid)
        flt = f' filter="url(#{fid})"' if defs else ''
        out = [f'<defs>{defs}<clipPath id="{cid}"><rect x="{D.f3(x)}" y="{D.f3(y)}" width="{D.f3(w)}" height="{D.f3(h)}"/></clipPath></defs>',
               f'<image x="{D.f3(x - l * iw)}" y="{D.f3(y - t * ih)}" width="{D.f3(iw)}" height="{D.f3(ih)}" preserveAspectRatio="none" '
               f'clip-path="url(#{cid})"{flt} href="{item["data"]}"/>']
        if item.get('border'):
            out.append(f'<rect x="{D.f3(x)}" y="{D.f3(y)}" width="{D.f3(w)}" height="{D.f3(h)}"{D.pen({"line": item["border"]})}/>')
        if cap:
            out.append(caption_svg(cap, item['cap_no'], x0 + cx, y0 + cy, cw, ch, True))
        return out
    return {'w': W, 'h': H, 'draw': draw, 'base': None}


def svg_ole(o, x, y):
    """DRAWS['ole']: Hangul shows nothing for an OLE object without a cached picture (blank in its render); the preview draws a
    thin dashed box with the file name so that the place is visible (rules OB20)."""
    w, h = o['w'], o['h']
    if o.get('_view'):                                 # the picture Hangul keeps for the object (a bitmap in the OLE file)
        return [f'<image x="{D.f3(x)}" y="{D.f3(y)}" width="{D.f3(w)}" height="{D.f3(h)}" preserveAspectRatio="none" href="{o["_view"]}"/>']
    name = (o.get('label') or os.path.basename(str(o.get('src', '')))).replace('&', '&amp;').replace('<', '&lt;')
    return [f'<rect x="{D.f3(x)}" y="{D.f3(y)}" width="{D.f3(w)}" height="{D.f3(h)}" fill="none" stroke="#999999" stroke-width="0.15" '
            'stroke-dasharray="1.5 1"/>',
            f'<text x="{D.f3(x + w / 2)}" y="{D.f3(y + h / 2)}" text-anchor="middle" font-size="2.6" fill="#777777" '
            f'font-family="\'함초롬돋움\',\'Malgun Gothic\',sans-serif">OLE {name}</text>']


def svg_object(o, x, y):
    """DRAWS['object']: the object (draw.svg) and, when it has a caption, the caption text around it (prepare made room for it)."""
    cap = o.get('caption')
    if not cap or '_box' not in o:
        return D.svg(o, x, y)
    w, h = o['_box']
    W, H, cx, cy, cw, ch = cap_room(cap, w, h)
    ox, oy = offsets(cap, cw, ch)
    out = D.svg(dict(o, w=w, h=h), x + ox, y + oy)
    return None if out is None else out + [caption_svg(cap, o['cap_no'], x + cx, y + cy, cw, ch, False)]
