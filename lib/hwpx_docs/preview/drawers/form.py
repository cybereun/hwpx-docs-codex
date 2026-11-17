"""Form objects (양식 개체) of the preview: check box, radio button, push button, combo box, list box, edit box, scroll
bar, from a spec item {"form": {...}} or a raw `hp:checkBtn|radioBtn|btn|comboBox|listBox|edit|scrollBar` element.
Drawn as Hangul prints them (fields/rules.md F08): no frame round an edit, combo or list box (borderTypeIDRef 0), a
down arrow on a combo box, a filled button; the caption or text uses the char style at that place."""
import html

from ...fields import forms
from ..measure import PT, eff_size, face, fam
from ..svg import f3
from . import register, register_inline

FRAME, ARROW = '#7A7A7A', '#404040'
SW = 0.2                                   # frame width, mm


def _text(x, y, s, st, size, fill, anchor='start'):
    return ('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="%s" dominant-baseline="central">%s</text>'
            % (f3(x), f3(y), html.escape(fam(face(st, 0)), quote=True), f3(size), fill, anchor, html.escape(s)))


def _box(x, y, w, h, fill, frame=True, rx=0):
    return ('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s/>'
            % (f3(x), f3(y), f3(w), f3(h), rx, fill, ' stroke="%s" stroke-width="%s"' % (FRAME, SW) if frame else ''))


def _toggle(f, st, size, ink, x, y, h):
    cy, b = y + h / 2, min(3.4, h * 0.7)
    bx, by = x + 0.3, cy - b / 2
    if f['type'] == 'check':
        out = [_box(bx, by, b, b, '#FFFFFF')]
        if f.get('checked'):
            out.append('<path d="M%s %s L%s %s L%s %s" fill="none" stroke="%s" stroke-width="0.35"/>'
                       % (f3(bx + b * .2), f3(by + b * .55), f3(bx + b * .43), f3(by + b * .78), f3(bx + b * .82),
                          f3(by + b * .22), ink))
    else:
        out = ['<circle cx="%s" cy="%s" r="%s" fill="#FFFFFF" stroke="%s" stroke-width="%s"/>'
               % (f3(bx + b / 2), f3(cy), f3(b / 2), FRAME, SW)]
        if f.get('checked'):
            out.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f3(bx + b / 2), f3(cy), f3(b * .22), ink))
    if f.get('caption'):
        out.append(_text(bx + b + 1.2, cy, f['caption'], st, size, ink))
    return out


def _edit(f, st, size, ink, x, y, w, h):
    text = str(f.get('text', ''))
    if f.get('password'):
        text = f['password'][:1] * len(text)
    al = f.get('align', 'left')
    tx = {'left': x + 0.8, 'center': x + w / 2, 'right': x + w - 0.8}[al]
    anchor = {'left': 'start', 'center': 'middle', 'right': 'end'}[al]
    lines = text.split('\n') if f.get('multiline') else [text.replace('\n', ' ')]
    return [_text(tx, (y + 0.5 + size / 2 + i * size * 1.25) if f.get('multiline') else y + h / 2, ln, st, size, ink, anchor)
            for i, ln in enumerate(lines)]


def _combo(f, st, size, ink, x, y, w, h):
    bw, cy = min(4.0, w / 3), y + h / 2
    return ['<path d="M%s %s L%s %s L%s %s Z" fill="%s"/>' % (f3(x + w - bw * .7), f3(cy - h * .08), f3(x + w - bw * .3),
                                                             f3(cy - h * .08), f3(x + w - bw * .5), f3(cy + h * .12), ARROW),
            _text(x + 0.8, cy, str(f.get('value', '')), st, size, ink)]


def _list(f, st, size, ink, x, y, w, h):
    out, step = [], size * 1.3
    for i, it in enumerate(forms.items_of(f)):
        ty = y + 0.4 + step * (i + .5)
        if ty + step / 2 > y + h:
            break
        on = f.get('value') in (it['text'], it['value'])
        if on:
            out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="#3399FF"/>' % (f3(x + .2), f3(ty - step / 2), f3(w - .4), f3(step)))
        out.append(_text(x + 0.8, ty, it['text'], st, size, '#FFFFFF' if on else ink))
    return out


def _scroll(x, y, w, h):
    out = [_box(bx, y, h, h, '#E1E1E1') for bx in (x, x + w - h)]
    return out + [_box(x + h, y, (w - 2 * h) * .25, h, '#CDCDCD')]


def draw_form(f, st):
    kind = f.get('type', 'check')
    w0, h0 = forms.default_size(f)
    w, h = f.get('w', w0), f.get('h', h0)
    size = eff_size(st, 0) * PT
    ink = f.get('color') or st.get('color') or '#000000'
    fill = f.get('fill', '#FFFFFF' if kind in ('edit', 'combo', 'list') else '#F0F0F0')

    def draw(x, y):
        if kind in ('check', 'radio'):
            return _toggle(dict(f, type=kind), st, size, ink, x, y, h)
        if kind == 'button':
            return [_box(x, y, w, h, fill, rx=0.4), _text(x + w / 2, y + h / 2, f.get('caption', ''), st, size, ink, 'middle')]
        if kind == 'scroll':
            return _scroll(x, y, w, h)
        body = {'edit': _edit, 'combo': _combo, 'list': _list}[kind]
        return [_box(x, y, w, h, fill, False)] + body(f, st, size, ink, x, y, w, h)
    return {'w': w, 'h': h, 'base': None, 'draw': draw}


def spec(item, style):
    return draw_form(item, style)


def raw(xml_text, style):
    f = forms.parse(xml_text)
    return None if f is None else draw_form(f, style)      # None: the preview draws its "not drawn" box


register('form', spec)
for _tag in forms.KINDS:
    register_inline('hp:' + _tag, raw)
