"""덧말 (hp:dutmal, kept raw by the reader): the main text in the line, the small sub text centred above (posType TOP) or
below (BOTTOM) it; szRatio = sub text size in % of the main text (0 or none = 50). The sub text sets the object's width when
it is wider (align CENTER; the other aligns put it at the left / right edge). textstyle/rules.md TS15."""
import html
import re

from ..measure import BASE, PT, cwidth, eff_size, face, fam
from ..svg import f3
from . import register, register_inline


def _text(xml, tag):
    m = re.search(r'<hp:%s\b[^>]*>(.*?)</hp:%s>' % (tag, tag), xml, re.S)
    return html.unescape(re.sub(r'<[^>]+>', '', m.group(1))) if m else ''


def dutmal(xml, st):
    """Raw `hp:dutmal` element text (a file that the spec does not model)."""
    pos = re.search(r'posType="(\w+)"', xml)
    ratio = re.search(r'szRatio="(\d+)"', xml)
    align = re.search(r'align="(\w+)"', xml)
    return _draw(_text(xml, 'mainText'), _text(xml, 'subText'), pos.group(1) if pos else 'TOP', int(ratio.group(1)) if ratio else 0,
                 align.group(1) if align else 'CENTER', st)


def dutmal_item(item, st):
    """Spec item `{"dutmal": {main, sub, pos, size, align}}` (what `hd read` writes)."""
    d = item.get('dutmal', item)
    return _draw(d.get('main', ''), d.get('sub', ''), str(d.get('pos', 'top')).upper(), int(d.get('size', 50)),
                 str(d.get('align', 'center')).upper(), st)


def _draw(main, sub, pos, ratio, align, st):
    size = eff_size(st, 0) * PT                                    # main text height, mm
    k = (ratio or 50) / 100
    sst = dict(st, size=st.get('size', 10) * k)
    wm = sum(cwidth(c, st) for c in main) * PT
    ws = sum(cwidth(c, sst) for c in sub) * PT
    w, hs, top = max(wm, ws), size * k, pos != 'BOTTOM'

    def at(width, a):
        return {'LEFT': 0, 'RIGHT': w - width}.get(a, (w - width) / 2)

    def draw(x, y):
        ym = y + (hs if top else 0)
        ys = 0 if top else size
        fam_ = html.escape(fam(face(st, 1)), quote=True)
        out = []
        for txt, width, sz, yy, a in ((main, wm, size, ym, 'CENTER'), (sub, ws, hs, y + ys, align)):
            if txt:
                out.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s">%s</text>' % (
                    f3(x + at(width, a)), f3(yy + sz * BASE), fam_, f3(sz), st['color'], html.escape(txt)))
        return out
    return {'w': w, 'h': size + hs, 'base': (hs if top else 0) + size * BASE, 'draw': draw}


register_inline('hp:dutmal', dutmal)
register('dutmal', dutmal_item)
