"""Picture bullets (paragraph key `bullet_image`, textstyle/rules.md TS22): the bullet image itself is drawn, as high as the text,
at the place of the bullet. The layout draws a bullet as text, so a prepare step (drawers.register_prepare) replaces the paragraph's
`bullet` and `bullet_image` by an inline run item `{"bullet_pic": {...}}` in front of the text, which the drawer below draws.
With a hanging indent the object is as wide as the hang, so the text starts where the wrapped lines start (like the layout does
for a text bullet). A missing image file keeps the character bullet and prints `PREVIEW BULLET IMAGE MISSING <name>`."""
import base64
import os
import sys

from ...core.units import image_size
from ..measure import PT, eff_size
from ..svg import f3
from . import register, register_prepare

MIME = {'png': 'png', 'jpg': 'jpeg', 'jpeg': 'jpeg', 'bmp': 'bmp', 'gif': 'gif'}
GAP = 0.5           # em between the image and the text when there is no hanging indent


def _prepare(node, pic_dir):
    if isinstance(node, list):
        for x in node:
            _prepare(x, pic_dir)
    elif isinstance(node, dict):
        name = node.get('bullet_image')
        if name:
            path = os.path.join(pic_dir, name)
            if not os.path.exists(path):
                print('PREVIEW BULLET IMAGE MISSING', name, file=sys.stderr)
            else:
                data = open(path, 'rb').read()
                w, h = image_size(data)
                uri = 'data:image/%s;base64,%s' % (MIME.get(os.path.splitext(name)[1].lower().lstrip('.'), 'png'),
                                                  base64.b64encode(data).decode())
                p = node.get('p', '')
                runs = list(p) if isinstance(p, list) else ([p] if p else [])
                hang = -float(node['indent']) * PT if isinstance(node.get('indent'), (int, float)) and node['indent'] < 0 else 0
                node['p'] = [{'bullet_pic': {'data': uri, 'ratio': w / h, 'hang': hang}}] + runs
                node.pop('bullet_image')
                node.pop('bullet', None)
        for v in node.values():
            if isinstance(v, (list, dict)):
                _prepare(v, pic_dir)


def bullet_pic(item, st):
    h = eff_size(st, 0) * PT
    w = h * item['ratio']
    room = max(w + h * GAP, item.get('hang', 0))

    def draw(x, y):
        return ['<image x="%s" y="%s" width="%s" height="%s" href="%s"/>' % (f3(x), f3(y), f3(w), f3(h), item['data'])]
    return {'w': room, 'h': h, 'base': None, 'draw': draw}


register('bullet_pic', bullet_pic)
register_prepare(_prepare)
