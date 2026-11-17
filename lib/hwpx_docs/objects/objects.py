"""Drawing objects, text boxes and pictures."""
import os
from ..core import registry
from ..core.units import HU_PER, color, hu, image_size, line, quad


def _post(kind):
    """Feature packages may change the XML of a picture or a drawing object (registry.post_xml, POST)."""
    def deco(fn):
        def wrapped(self, spec, *a, **k):
            return registry.post_xml(kind, self, spec, fn(self, spec, *a, **k), *a)
        return wrapped
    return deco


class ObjectsMixin:
    """Drawing objects, text boxes and pictures. Mixed into core.build.Doc."""

    # ---- drawing objects (rect, text box, line, ellipse) ----
    @_post('shape')
    def shape(self, s, ctx):
        """s: {'type': 'rect'|'line'|'ellipse', 'x','y','w','h' (mm; line: 'x2','y2'), 'rel': 'paper'|'page'|'para',
        'line': line spec, 'fill': colour, 'round': corner % (rect), 'text': str or blocks (text box),
        'pad': text margin mm, 'valign', 'wrap': 'in_front_of_text'|'behind_text'|'top_and_bottom'|'square',
        'arrow': 'end'|'start'|'both' (line)}."""
        kind = s.get('type', 'rect')
        oid = self.next_obj()
        x, y = hu(s.get('x', 0)), hu(s.get('y', 0))
        if kind == 'line':
            x2, y2 = hu(s.get('x2', s.get('x', 0) + s.get('w', 0))), hu(s.get('y2', s.get('y', 0) + s.get('h', 0)))
            w, h = max(abs(x2 - x), 1), max(abs(y2 - y), 1)
            x, y = min(x, x2), min(y, y2)
        else:
            w, h = hu(s['w']), hu(s['h'])
        t, wd, col = line(s.get('line', '0.12mm solid #000000'))
        lw = round(float(wd.split()[0]) * HU_PER['mm'])
        arrow = str(s.get('arrow', '')).lower()
        head_style = 'ARROW' if arrow in ('start', 'both') else 'NORMAL'
        tail_style = 'ARROW' if arrow in ('end', 'both') else 'NORMAL'
        ls = (f'<hp:lineShape color="{col}" width="{lw}" style="{t}" endCap="FLAT" headStyle="{head_style}" '
              f'tailStyle="{tail_style}" headfill="1" tailfill="1" headSz="MEDIUM_MEDIUM" tailSz="MEDIUM_MEDIUM" '
              'outlineStyle="NORMAL" alpha="0"/>')
        fill = s.get('fill')
        fb = (f'<hc:fillBrush><hc:winBrush faceColor="{color(fill)}" hatchColor="#000000" alpha="0"/></hc:fillBrush>'
              if fill and kind != 'line' else '')
        ident = '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        # curSz 0 0 = "not resized" (Hangul writes it so: corpus/shapes_rt)
        common = (f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="0" height="0"/>'
                  f'<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
                  f'<hp:renderingInfo>{ident}{ident.replace("trans", "sca")}{ident.replace("trans", "rot")}</hp:renderingInfo>')
        text = ''
        if s.get('text') is not None and kind != 'line':
            blocks = [{'p': s['text']}] if isinstance(s['text'], str) else s['text']
            pad = quad(s.get('pad', 1))
            text = (f'<hp:drawText lastWidth="{w}" name="" editable="0">'
                    f'{self.sublist(blocks, ctx, str(s.get("valign", "center")).upper())}'
                    f'<hp:textMargin left="{pad[0]}" right="{pad[1]}" top="{pad[2]}" bottom="{pad[3]}"/></hp:drawText>')
        rel = {'paper': 'PAPER', 'page': 'PAGE', 'para': 'PARA'}[s.get('rel', 'paper')]
        hrel = 'COLUMN' if rel == 'PARA' else rel
        wrap = str(s.get('wrap', 'in_front_of_text')).upper()
        tail = (f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
                f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="{1 if rel == "PARA" else 0}" allowOverlap="1" '
                f'holdAnchorAndSO="0" vertRelTo="{rel}" horzRelTo="{hrel}" vertAlign="TOP" horzAlign="LEFT" '
                f'vertOffset="{y}" horzOffset="{x}"/><hp:outMargin left="0" right="0" top="0" bottom="0"/>')
        attrs = (f'id="{1500000000 + oid}" zOrder="{oid}" numberingType="PICTURE" textWrap="{wrap}" textFlow="BOTH_SIDES" '
                 f'lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{1600000000 + oid}"')
        shadow = '<hp:shadow type="NONE" color="#B2B2B2" offsetX="0" offsetY="0" alpha="0"/>'
        if kind == 'rect':
            pts = f'<hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/>'
            return (f'<hp:rect {attrs} ratio="{int(s.get("round", 0))}">{common}{ls}{fb}{shadow}{text}{pts}{tail}'
                    '<hp:shapeComment>사각형입니다.</hp:shapeComment></hp:rect>')
        if kind == 'ellipse':
            pts = (f'<hc:center x="{w // 2}" y="{h // 2}"/><hc:ax1 x="{w}" y="{h // 2}"/><hc:ax2 x="{w // 2}" y="0"/>'
                   f'<hc:start1 x="0" y="0"/><hc:end1 x="0" y="0"/><hc:start2 x="0" y="0"/><hc:end2 x="0" y="0"/>')
            return (f'<hp:ellipse {attrs} intervalDirty="0" hasArcPr="0" arcType="NORMAL">{common}{ls}{fb}{shadow}{text}{pts}'
                    f'{tail}<hp:shapeComment>타원입니다.</hp:shapeComment></hp:ellipse>')
        if kind == 'line':
            sx, sy = hu(s.get('x', 0)) - x, hu(s.get('y', 0)) - y
            ex, ey = hu(s.get('x2', 0)) - x, hu(s.get('y2', 0)) - y
            return (f'<hp:line {attrs} isReverseHV="0">{common}{ls}{shadow}<hc:startPt x="{sx}" y="{sy}"/><hc:endPt x="{ex}" y="{ey}"/>'
                    f'{tail}<hp:shapeComment>선입니다.</hp:shapeComment></hp:line>')
        raise ValueError(f'unknown shape type: {kind}')

    # ---- pictures ----
    @_post('pic')
    def pic(self, p, inline=True):
        path = os.path.join(self.base, p['src'])
        data = open(path, 'rb').read()
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        ext = 'jpg' if ext == 'jpeg' else ext
        media = {'png': 'image/png', 'jpg': 'image/jpg', 'bmp': 'image/bmp', 'gif': 'image/gif'}[ext]
        pw, ph = image_size(data)
        w = hu(p['w']) if 'w' in p else pw * 75
        h = hu(p['h']) if 'h' in p else (round(w * ph / pw) if 'w' in p else ph * 75)
        n = len(self.bins) + 1
        item = f'image{n}'
        self.bins.append((item, f'BinData/{item}.{ext}', data, media))
        oid = self.next_obj()
        pos = p.get('pos')
        if pos and not inline:
            rel = {'page': 'PAGE', 'paper': 'PAPER', 'para': 'PARA'}[pos.get('rel', 'paper')]
            posxml = (f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="0" allowOverlap="1" holdAnchorAndSO="0" '
                      f'vertRelTo="{rel}" horzRelTo="{rel}" vertAlign="TOP" horzAlign="LEFT" '
                      f'vertOffset="{hu(pos.get("y", 0))}" horzOffset="{hu(pos.get("x", 0))}"/>')
            wrap = str(p.get('wrap', 'in_front_of_text')).upper()
        else:
            posxml = (f'<hp:pos treatAsChar="{int(inline)}" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
                      'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
                      'vertOffset="0" horzOffset="0"/>')
            wrap = 'TOP_AND_BOTTOM'
        ident = '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        return (f'<hp:pic id="{1100000000 + oid}" zOrder="{oid}" numberingType="PICTURE" textWrap="{wrap}" '
                f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{1200000000 + oid}" reverse="0">'
                f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="{w}" height="{h}"/>'
                f'<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
                f'<hp:renderingInfo>{ident}{ident.replace("trans", "sca")}{ident.replace("trans", "rot")}</hp:renderingInfo>'
                f'<hc:img binaryItemIDRef="{item}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
                f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
                f'<hp:imgClip left="0" right="{pw * 75}" top="0" bottom="{ph * 75}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
                f'<hp:imgDim dimwidth="{pw * 75}" dimheight="{ph * 75}"/><hp:effects/>'
                f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>{posxml}'
                f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>')


def nice_max(v):
    """Smallest 1/2/2.5/5 x 10^k that is >= v (axis top)."""
    import math
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    return next(m * e for m in (1, 2, 2.5, 5, 10) if m * e >= v)


def chart_shapes(c):
    """Chart spec -> shapes (bar or line chart drawn with Hangul drawing objects; vector, editable).
    c: {'type': 'bar'|'line', 'w': mm, 'h': mm, 'categories': [...], 'series': [{'name', 'values', 'color'}],
        'max': axis top (optional), 'ticks': 5, 'title': str, 'unit': str, 'font': face, 'size': pt, 'labels': true}
    Anchor: the paragraph that holds the chart; the shapes are placed relative to it (rel para) and push the
    text below (top_and_bottom)."""
    palette = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5', '#70AD47']
    W, H = c.get('w', 160), c.get('h', 80)
    cats, series = c['categories'], c['series']
    font, size = c.get('font', '맑은 고딕'), c.get('size', 9)
    top = 8 if c.get('title') else 3
    legend_h = 6 if len(series) > 1 or c.get('legend') else 0
    left, bottom = 14, 7
    pw, ph = W - left - 3, H - top - bottom - legend_h
    x0, y0 = left, top + ph                     # plot origin (bottom-left), mm from the anchor
    vmax = c.get('max') or nice_max(max(v for s in series for v in s['values']))
    ticks = c.get('ticks', 5)
    out = []

    def label(x, y, w, h, text, align='center', bold=False, sz=size):
        out.append({'type': 'rect', 'rel': 'para', 'x': x, 'y': y, 'w': w, 'h': h, 'line': 'none', 'pad': 0,
                    'wrap': 'top_and_bottom', 'valign': 'center',
                    'text': [{'p': text, 'align': align, 'font': font, 'size': sz, 'bold': bold, 'line': 100}]})
    if c.get('title'):
        label(0, 0, W, 6, c['title'], bold=True, sz=size + 2)
    for k in range(ticks + 1):                   # grid lines and y labels
        y = y0 - ph * k / ticks
        out.append({'type': 'line', 'rel': 'para', 'x': x0, 'y': y, 'x2': x0 + pw, 'y2': y, 'wrap': 'top_and_bottom',
                    'line': '0.12mm solid #000000' if k == 0 else '0.12mm solid #D9D9D9'})
        v = vmax * k / ticks
        label(0, y - 2.5, left - 1.5, 5, f'{v:,.0f}' if float(v).is_integer() else f'{v:,.1f}', align='right')
    if c.get('unit'):
        label(0, top - 5, left + 10, 4, f'({c["unit"]})', align='left', sz=size - 1)
    out.append({'type': 'line', 'rel': 'para', 'x': x0, 'y': y0 - ph, 'x2': x0, 'y2': y0, 'line': '0.12mm solid #000000',
                'wrap': 'top_and_bottom'})
    gw = pw / len(cats)
    for i, cat in enumerate(cats):               # category labels
        label(x0 + gw * i, y0 + 1, gw, 5, str(cat))
    for j, s in enumerate(series):
        col = s.get('color', palette[j % len(palette)])
        pts = []
        for i, v in enumerate(s['values']):
            h = ph * v / vmax
            if c.get('type', 'bar') == 'bar':
                bw = gw * 0.6 / len(series)
                x = x0 + gw * i + gw * 0.2 + bw * j
                out.append({'type': 'rect', 'rel': 'para', 'x': x, 'y': y0 - h, 'w': bw, 'h': max(h, 0.1), 'fill': col,
                            'line': 'none', 'wrap': 'top_and_bottom'})
                if c.get('labels', True):
                    label(x - 3, y0 - h - 5, bw + 6, 4.5, f'{v:,}', sz=size - 1)
            else:
                pts.append((x0 + gw * i + gw / 2, y0 - h))
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            out.append({'type': 'line', 'rel': 'para', 'x': xa, 'y': ya, 'x2': xb, 'y2': yb, 'line': f'0.5mm solid {col}',
                        'wrap': 'top_and_bottom'})
        for i, ((x, y), v) in enumerate(zip(pts, s['values'])):
            out.append({'type': 'ellipse', 'rel': 'para', 'x': x - 1.2, 'y': y - 1.2, 'w': 2.4, 'h': 2.4, 'fill': col,
                        'line': f'0.12mm solid {col}', 'wrap': 'top_and_bottom'})
            if c.get('labels', True):
                # the value of a lower line goes under its point, so labels of two lines do not overlap
                lower = any(o['values'][i] > v for o in series if o is not s)
                label(x - 8, y + 2 if lower else y - 6.5, 16, 4.5, f'{v:,}', sz=size - 1)
    if legend_h:                                 # legend under the plot
        lx = x0
        for j, s in enumerate(series):
            col = s.get('color', palette[j % len(palette)])
            out.append({'type': 'rect', 'rel': 'para', 'x': lx, 'y': H - legend_h + 1.5, 'w': 3, 'h': 3, 'fill': col,
                        'line': 'none', 'wrap': 'top_and_bottom'})
            label(lx + 4, H - legend_h + 0.5, 30, 5, s.get('name', f'계열 {j + 1}'), align='left')
            lx += 36
    return out
