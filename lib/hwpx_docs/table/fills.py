"""Cell fills that are not one colour: gradient (hc:gradation) and picture (hc:imgBrush). Rules TB03, TB04.

Spec `fill`:
  "#D9D9D9"                                                   one colour (core)
  {"type": "gradient", "kind": "linear|radial|conical|square", "angle": 90, "center": [0, 0], "step": 50,
   "step_center": 50, "colors": ["#FFFFFF", "#000000"]}
  {"type": "image", "src": "a.png", "mode": "tile|total|center|zoom|..."}
(`type` is the key of the preview's paint registry, drawers.register_paint.)
The builder gives `brush(doc, fill)` a fill and gets what `Header.border_fill` takes: a colour, or the finished
`<hc:fillBrush>` text. The reader gives `read_brush(reader, hc:fillBrush)` and gets the spec value.
"""
import os

from ..core.units import IMAGE_MEDIA, color

NS_HC = '{http://www.hancom.co.kr/hwpml/2011/core}'
GRADS = {'linear': 'LINEAR', 'radial': 'RADIAL', 'conical': 'CONICAL', 'square': 'SQUARE'}
MODES = ('TILE', 'TILE_HORZ_TOP', 'TILE_HORZ_BOTTOM', 'TILE_VERT_LEFT', 'TILE_VERT_RIGHT', 'TOTAL', 'CENTER', 'CENTER_TOP',
         'CENTER_BOTTOM', 'LEFT_CENTER', 'LEFT_TOP', 'LEFT_BOTTOM', 'RIGHT_CENTER', 'RIGHT_TOP', 'RIGHT_BOTTOM', 'ZOOM')
MEDIA = IMAGE_MEDIA
GRAD_DEFAULT = dict(angle=90, center=[0, 0], step=50, step_center=50)


def is_special(fill):
    return isinstance(fill, dict) and fill.get('type') in ('gradient', 'image')


def gradient_xml(g):
    kind = GRADS[str(g.get('kind', 'linear')).lower()]
    cols = [color(c) for c in g.get('colors', ['#FFFFFF', '#000000'])]
    if len(cols) < 2:        # more than 2 are written as given, but Hangul draws 3 colours black (S:cell_fill_gradient_angles)
        raise ValueError('gradient needs 2 colours')
    cx, cy = g.get('center', GRAD_DEFAULT['center'])
    return ('<hc:fillBrush>'
            f'<hc:gradation type="{kind}" angle="{round(g.get("angle", 90))}" centerX="{round(cx)}" centerY="{round(cy)}" '
            f'step="{round(g.get("step", 50))}" colorNum="{len(cols)}" stepCenter="{round(g.get("step_center", 50))}" alpha="0">'
            + ''.join(f'<hc:color value="{c}"/>' for c in cols) + '</hc:gradation></hc:fillBrush>')


def image_xml(doc, im):
    path = os.path.join(doc.base, im['src'])
    data = open(path, 'rb').read()
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    media = MEDIA[ext]
    ext = 'jpg' if ext == 'jpeg' else ext
    item = next((i for i, _, d, _ in doc.bins if d == data), None)      # the same picture is stored once
    if item is None:
        item = f'image{len(doc.bins) + 1}'
        doc.bins.append((item, f'BinData/{item}.{ext}', data, media))
    mode = str(im.get('mode', 'tile')).upper()
    if mode not in MODES:
        raise ValueError(f'bad picture fill mode {mode!r}; one of {", ".join(m.lower() for m in MODES)}')
    return (f'<hc:fillBrush><hc:imgBrush mode="{mode}"><hc:img binaryItemIDRef="{item}" bright="0" contrast="0" '
            'effect="REAL_PIC" alpha="0"/></hc:imgBrush></hc:fillBrush>')


def brush(doc, fill):
    """Fill spec -> colour string, '<hc:fillBrush>...' text, or None."""
    if not fill:
        return None
    if isinstance(fill, dict):
        if fill.get('type') == 'gradient':
            return gradient_xml(fill)
        if fill.get('type') == 'image':
            return image_xml(doc, fill)
        raise ValueError(f'bad fill {fill!r}: a colour, {{"type": "gradient", ...}} or {{"type": "image", ...}}')
    return color(fill)


def read_brush(reader, el):
    """hc:fillBrush element -> {'type': 'gradient', ...} | {'type': 'image', ...} | None (a winBrush is read by the core)."""
    g = el.find(NS_HC + 'gradation')
    if g is not None:
        d = {'type': 'gradient', 'kind': g.get('type', 'LINEAR').lower(),
             'colors': [c.get('value') for c in g.findall(NS_HC + 'color')]}
        for key, attr in (('angle', 'angle'), ('step', 'step'), ('step_center', 'stepCenter')):
            v = int(g.get(attr, GRAD_DEFAULT[key]))
            if v != GRAD_DEFAULT[key]:
                d[key] = v
        c = [int(g.get('centerX', 0)), int(g.get('centerY', 0))]
        if c != GRAD_DEFAULT['center']:
            d['center'] = c
        return d
    ib =el.find(NS_HC + 'imgBrush')
    if ib is not None:
        img = ib.find(NS_HC + 'img')
        href = reader.bins[img.get('binaryItemIDRef')]
        stem, ext = os.path.splitext(os.path.basename(href))
        name = stem + ext.lower()               # Hangul writes image1.PNG; the builder writes the extension in lower case
        d = {'type': 'image', 'src': reader.save(name, reader.z.read(href))}
        if ib.get('mode', 'TILE') != 'TILE':
            d['mode'] = ib.get('mode').lower()
        return d
    return None
