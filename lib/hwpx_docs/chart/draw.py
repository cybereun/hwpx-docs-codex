"""The chart as a viewer draws it (registered as DRAWS['chart'], used by the preview): the spec block `chart` with
`native: true` (as core.read gives it) in Hangul's default chart style. Lengths in mm. The numbers are measured on
Hangul 2024 pages of the chart fixtures at 96 dpi (preview rules P10): frame, title, plot area, axes, ticks, legend,
bar gaps, line widths and the default colours.

  svg(c, x, y)    the chart `c` (spec dict with w, h) with its top-left corner at (x, y) -> [SVG elements]; None when
                  there is nothing to draw it from (not native, or a part kept whole with no `view`)
"""
import math
from ..core import textfit

PT = 25.4 / 72                             # mm per pt


class _Out:
    def __init__(self):
        self.svg = []


def f3(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def fam(name):
    return "'%s','Malgun Gothic',sans-serif" % name


def rect(page, x, y, w, h, fill=None, ln=None):
    page.svg.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"%s/>' % (
        f3(x), f3(y), f3(w), f3(h), fill or 'none', ' stroke="%s" stroke-width="%s"' % (ln[2], f3(ln[0])) if ln else ''))


def stroke(page, x1, y1, x2, y2, ln, ext=False):
    page.svg.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
        f3(x1), f3(y1), f3(x2), f3(y2), ln[2], f3(ln[0])))


DY = -0.17        # mm: the chart sits this much higher in Hangul's 96 dpi pages than the layout's top (scan of -0.05 ... -0.4 against the
                  # 26 chart pages: ink mean 28.4 / 18.1 -> 15.2 / 14.2 at -0.17; the best value differs a little per chart, -0.13 ... -0.26)


def svg(c, x, y):
    if not isinstance(c, dict) or not c.get('native') or not ('series' in c or c.get('view')):
        return None
    out = _Out()
    draw(out, c, x, y + DY)
    return out.svg

# series colours of Hangul's default style; ponytail: the first 4 are measured, 5 and 6 are assumed (no sample yet)
PALETTE = ('#6182D6', '#FF843A', '#B2B2B2', '#FFD700', '#4BA3D9', '#6CB86C')
GREY = (0.265, 'solid', '#868686')        # frame, axes, gridlines and ticks: 0.75 pt
FONT, SIZE = '함초롬돋움', 10               # chart text (c:txPr defRPr sz 1000)
TITLE_PT = 14
PAD = 3.4                                  # frame to the first text on the left and right
TICK = 1.2                                 # tick marks point out of the plot
GAP = 1.5                                  # c:gapWidth 150: space between bar groups = 1.5 bar widths
BAR_LINE = 0.79                            # line series: 2.25 pt


def tw(s, pt=SIZE, font=FONT):
    """Width of a text in mm (real font widths on Windows, an estimate elsewhere)."""
    g = textfit.gdi()
    return sum(g.em(ch, font, False) for ch in str(s)) * pt * PT


def text(page, x, y, s, pt=SIZE, anchor='middle', font=FONT, fill='#000000'):
    """Text with its middle at y (Hangul draws chart text centred on its line)."""
    page.svg.append('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="%s" '
                    'dominant-baseline="central">%s</text>' % (
                        f3(x), f3(y), fam(font), f3(pt * PT), fill, anchor,
                        str(s).replace('&', '&amp;').replace('<', '&lt;')))


def scale(lo, hi, length, step=None, min_mm=7.0):
    """Axis min, max and major unit like Hangul: 5 % head room, steps 1, 2, 5 x 10^k, at least `min_mm` per step: 7 mm on a vertical
    value axis, 10 mm on a horizontal one (horizontal bars, the x axis of a scatter chart: labels side by side need more room).
    Fits the Hangul charts: vertical 0-6 by 2 on 39 mm, 0-8 by 2 (maximum 6), 0-6 by 1 (maximum 5) and 0-80 by 20 (maximum 60) on 43 mm;
    horizontal on 88.7 mm: 0-6 by 1 (maximum 5), 0-12 by 2 (9.9), 0-14 by 2 (12.3), 0-5 by 0.5 on 101 mm (scatter x). A single 12.5 mm
    rule fitted the horizontal bars but gave 0-10 by 5 on 43 mm; a single 7 mm rule gave 0-5.5 by 0.5 on the horizontal bars."""
    if hi == lo:
        hi = lo + 1
    span = (hi - lo) * 1.05
    if not step:
        raw = span / max(2, int(length // min_mm))
        k = 10 ** math.floor(math.log10(raw))
        step = next(m * k for m in (1, 2, 5, 10) if m * k >= raw - 1e-12)
    top = math.ceil((lo + span) / step - 1e-9) * step if hi > 0 else 0
    bot = math.floor(lo / step + 1e-9) * step if lo < 0 else 0
    return bot, top, step


def fmt(v, step):
    d = max(0, -math.floor(math.log10(step) + 1e-9)) if step < 1 else 0
    return ('%.*f' % (d, v)) if d else str(int(round(v)))


def colour(s, j):
    return s.get('color') or PALETTE[j % len(PALETTE)]


def slice_colour(s, i):
    cols = s.get('colors') or []
    return (cols[i] if i < len(cols) else None) or PALETTE[i % len(PALETTE)]


def draw(page, c, x, y):
    w, h = c.get('w', 150), c.get('h', 90)
    rect(page, x, y, w, h, '#FFFFFF', GREY)
    if 'series' not in c and c.get('view'):    # a part kept whole (`ooxml`): its data as the chart package read it
        c = dict(c['view'], w=w, h=h)
    pt = c.get('size', SIZE)
    font = c.get('font', FONT)
    kind = c.get('type', 'bar')
    series = c['series'] if kind != 'pie' else c['series'][:1]
    cats = c.get('categories') or [str(i + 1) for i in range(max(len(s['values']) for s in series))]
    n = len(cats)
    # title: '' is Hangul's automatic title ("차트 제목"; a pie shows its series name)
    title = c.get('title')
    if title == '':
        title = series[0].get('name', '') if kind == 'pie' else '차트 제목'
    top = 4.16
    if title:
        text(page, x + w / 2, y + 6.35, title, TITLE_PT * pt / SIZE, font=font)
        top = 12.96
    # legend: one entry per series (a pie: per category); a horizontal bar chart lists them from the last
    legend = c.get('legend', 'right')
    if kind == 'pie':
        entries = [(cat, slice_colour(series[0], i), 'box') for i, cat in enumerate(cats)]
    else:
        # Hangul's legend keeps the default colour of a bar series even when the bars have their own (chart rules)
        entries = [(s.get('name', ''), colour(s, j), 'line') if (s.get('type') or kind) == 'line'
                   else (s.get('name', ''), PALETTE[j % len(PALETTE)], 'box') for j, s in enumerate(series)]
        if kind == 'hbar' and not c.get('stacked'):      # Hangul lists clustered horizontal bars from the last
            entries.reverse()
    left, right, bottom = x + PAD, x + w - 2.9, y + h - 2.95
    if legend:
        ew = [3.2 + 1.06 + tw(e[0], pt * 0.9, font) for e in entries]
        if legend in ('right', 'left'):
            lw = max(ew)
            ly = (y + top - 4.16 + y + h) / 2 - (len(entries) - 1) * 2.5
            lx = right - lw if legend == 'right' else left
            for k, e in enumerate(entries):
                legend_entry(page, lx, ly + 5.0 * k, e, pt, font)
            if legend == 'right':
                right = lx - 3.3
            else:
                left = lx + lw + 3.3
        else:
            total = sum(ew) + 0.8 * (len(entries) - 1)
            lx = x + (w - total) / 2
            ly = (y + h - 4.0) if legend == 'bottom' else (y + top + 0.8)
            for e, ww in zip(entries, ew):
                legend_entry(page, lx, ly, e, pt, font)
                lx += ww + 0.8
            if legend == 'bottom':
                bottom -= 7.2
            else:
                top += 7.2
    if kind == 'pie':
        pie(page, c, series[0], cats, (left, y + top, right, bottom), pt, font)
        return
    stacked = bool(c.get('stacked'))
    horiz = kind == 'hbar'
    vals =[[v or 0 for v in s['values']] for s in series]
    # secondary value axis (vertical charts only; ponytail: a horizontal chart draws such a series on the primary scale)
    sec = [s.get('axis') == 'secondary' and not horiz and not stacked for s in series]
    if stacked:
        pos = [sum(max(0, s[i]) for s in vals if i < len(s)) for i in range(n)]
        neg = [sum(min(0, s[i]) for s in vals if i < len(s)) for i in range(n)]
        lo, hi = min(neg + [0]), max(pos + [0])
    else:
        flat = [v for s, sc in zip(vals, sec) for v in s if not sc] or [0]
        lo, hi = min(flat + [0]), max(flat + [0])
    # space for the axis labels and the axis titles
    cat_lbl = max(tw(cat, pt, font) for cat in cats) if cats else 0
    bottom -= 8.05                          # category (or value) labels under the plot
    # axis titles follow their axis: category axis at the bottom (left for horizontal bars), value axis on the left
    side_title, low_title = (c.get('x_title'), c.get('y_title')) if horiz else (c.get('y_title'), c.get('x_title'))
    if low_title:
        bottom -= 5.5
    if not horiz:
        top += 2.91                         # the top value label is centred on the top gridline
    plot_len = (right - left - (2.4 if horiz else 0)) if horiz else (bottom - (y + top))
    lo_v, hi_v, step = scale(lo, hi, plot_len, min_mm=10.0 if horiz else 7.0)
    lo_v = c.get('min', lo_v)
    hi_v = c.get('max', hi_v)
    labels = [lo_v + k * step for k in range(int(round((hi_v - lo_v) / step)) + 1)]
    val_lbl = max(tw(fmt(v, step), pt, font) for v in labels)
    lo2_v = hi2_v = step2 = labels2 = None
    if any(sec):                            # second value axis on the right: its labels and title take room there
        f2 = [v for s, sc in zip(vals, sec) for v in s if sc] or [0]
        lo2_v, hi2_v, step2 = scale(min(f2 + [0]), max(f2 + [0]), plot_len, min_mm=10.0 if horiz else 7.0)
        lo2_v, hi2_v = c.get('y2_min', lo2_v), c.get('y2_max', hi2_v)
        labels2 = [lo2_v + k * step2 for k in range(int(round((hi2_v - lo2_v) / step2)) + 1)]
        right -= max(tw(fmt(v, step2), pt, font) for v in labels2) + 3.9 + (tw(c['y2_title'], pt, font) + 2.6 if c.get('y2_title') else 0)
    if side_title:                          # Hangul writes axis titles level (bodyPr rot 0, vert horz)
        text(page, left, (y + top + bottom) / 2, side_title, pt, 'start', font=font)
        left += tw(side_title, pt, font) + 2.6
    if horiz:                               # the last value label is centred on the right end of the plot
        px0, px1 = left + cat_lbl + 2.8 + TICK, right - 1.43 - tw(fmt(labels[-1], step), pt, font) / 2
    else:
        px0, px1 = left + val_lbl + 3.2, right
        if kind == 'scatter':
            px1 -= 2.1                                # Hangul keeps 4.9 mm to the frame (render of chart_scatter), 2.8 mm without this
        if n > 1 and all((s.get('type') or kind) == 'area' for s in series):
            px1 -= tw(cats[-1], pt, font) / 2         # area only: the last category label is centred on the plot edge (render of chart_area)
    py0, py1 = y + top, bottom
    if low_title:
        text(page, (px0 + px1) / 2, py1 + 11.0, low_title, pt, font=font)
    span = (hi_v - lo_v) or 1

    def vpos(v):                            # value -> coordinate on the value axis
        return px0 + (v - lo_v) / span * (px1 - px0) if horiz else py1 - (v - lo_v) / span * (py1 - py0)

    band = ((py1 - py0) if horiz else (px1 - px0)) / max(n, 1)

    def cpos(i):                            # category i -> start of its band (horizontal bars: from the bottom)
        return py1 - (i + 1) * band if horiz else px0 + i * band

    if c.get('gridlines', True):
        for v in labels:
            p = vpos(v)
            stroke(page, p, py0, p, py1, GREY, ext=False) if horiz else stroke(page, px0, p, px1, p, GREY, ext=False)
    for v in labels:                        # value labels and their ticks
        p = vpos(v)
        if horiz:
            stroke(page, p, py1, p, py1 + TICK, GREY, ext=False)
            text(page, p, py1 + 5.8, fmt(v, step), pt, font=font)
        else:
            stroke(page, px0 - TICK, p, px0, p, GREY, ext=False)
            text(page, px0 - 3.2, p, fmt(v, step), pt, 'end', font=font)

    def vpos2(v):                           # value -> coordinate on the secondary value axis
        return py1 - (v - lo2_v) / ((hi2_v - lo2_v) or 1) * (py1 - py0)

    def scale_of(j):                        # (position function, axis min, axis max) of series j
        return (vpos2, lo2_v, hi2_v) if sec[j] else (vpos, lo_v, hi_v)
    if any(sec):                            # secondary axis: line, ticks and labels on the right, title at the edge
        stroke(page, px1, py0, px1, py1, GREY, ext=False)
        for v in labels2:
            stroke(page, px1, vpos2(v), px1 + TICK, vpos2(v), GREY, ext=False)
            text(page, px1 + 3.2, vpos2(v), fmt(v, step2), pt, 'start', font=font)
        if c.get('y2_title'):
            lbl = max(tw(fmt(v, step2), pt, font) for v in labels2)         # Hangul: level title right of the labels (render, 120 x 70 mm)
            text(page, px1 + 3.2 + lbl + 2.6, (py0 + py1) / 2, c['y2_title'], pt, 'start', font=font)
    if kind == 'scatter':                   # numeric x axis; markers, and lines when `lines` (ponytail: layout assumed, unmeasured)
        xs = [float(v) for v in cats]
        lox, hix, stepx = scale(min(xs), max(xs), px1 - px0, min_mm=10.0)
        lox, hix = c.get('x_min', lox), c.get('x_max', hix)

        def sx(v):
            return px0 + (v - lox) / ((hix - lox) or 1) * (px1 - px0)
        for k in range(int(round((hix - lox) / stepx)) + 1):
            stroke(page, sx(lox + k * stepx), py1, sx(lox + k * stepx), py1 + TICK, GREY, ext=False)
            text(page, sx(lox + k * stepx), py1 + 6.08, '%g' % round(lox + k * stepx, 9), pt, font=font)     # number format General: 0.5, 1, 1.5
        stroke(page, px0, py0, px0, py1, GREY, ext=False)
        stroke(page, px0, vpos(max(lo_v, 0)), px1, vpos(max(lo_v, 0)), GREY, ext=False)
        for j, s in enumerate(series):
            vp = scale_of(j)[0]
            pts = [(sx(a), vp(v)) for a, v in zip(xs, s['values']) if v is not None]
            if c.get('lines') and len(pts) > 1:
                page.svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" '
                                'stroke-linecap="round"/>' % (' '.join('%s,%s' % (f3(a), f3(b)) for a, b in pts), colour(s, j), f3(BAR_LINE)))
            for a, b in pts if c.get('markers', True) else []:
                page.svg.append('<circle cx="%s" cy="%s" r="1.2" fill="%s"/>' % (f3(a), f3(b), colour(s, j)))
        return
    # area only: the points sit on the ticks (c:crossBetween midCat), else in the middle of the bands
    mid = n > 1 and not horiz and all((s.get('type') or kind) == 'area' for s in series)

    def xc(i):
        return px0 + i * (px1 - px0) / (n - 1) if mid else cpos(i) + band / 2
    for i, cat in enumerate(cats):          # category labels and the ticks between the bands
        if horiz:
            text(page, px0 - TICK - 2.8, cpos(i) + band / 2, cat, pt, 'end', font=font)
        else:
            text(page, xc(i), py1 + 6.08, cat, pt, font=font)
    for i in range(n if mid else n + 1):
        p = (py1 - i * band) if horiz else (xc(i) if mid else px0 + i * band)
        stroke(page, px0 - TICK, p, px0, p, GREY, ext=False) if horiz else stroke(page, p, py1, p, py1 + TICK, GREY, ext=False)
    # areas (behind the bars): filled down to the axis, or to the series below when stacked
    acc = [0.0] * n
    for j, s in enumerate(series):
        if (s.get('type') or kind) != 'area':
            continue
        vp, lv, hv = scale_of(j)
        lower = list(acc) if stacked else [max(lv, 0)] * n
        upper = [(acc[i] + vals[j][i]) if stacked else vals[j][i] for i in range(n)]
        acc = upper if stacked else acc
        poly = [(xc(i), vp(upper[i])) for i in range(n)] + [(xc(i), vp(lower[i])) for i in reversed(range(n))]
        page.svg.append('<polygon points="%s" fill="%s"/>' % (' '.join('%s,%s' % (f3(a), f3(b)) for a, b in poly), colour(s, j)))
    # bars
    bar_idx = [j for j, s in enumerate(series) if (s.get('type') or kind) in ('bar', 'hbar')]
    k = 1 if stacked else max(1, len(bar_idx))
    bw = band / (k + GAP)
    base_p, base_n = [0.0] * n, [0.0] * n
    for slot, j in enumerate(bar_idx):
        col = colour(series[j], j)
        vpos_j, lo_j, hi_j = scale_of(j)
        for i in range(n):
            v = vals[j][i] if i < len(vals[j]) else 0
            if stacked:
                b0 = base_p[i] if v >= 0 else base_n[i]
                b1 = b0 + v
                if v >= 0:
                    base_p[i] = b1
                else:
                    base_n[i] = b1
                off = cpos(i) + (band - bw) / 2
            else:
                b0, b1 = 0, v
                off = cpos(i) + (band - k * bw) / 2 + (k - 1 - slot if horiz else slot) * bw
            a, b = sorted((vpos_j(max(lo_j, min(hi_j, b0))), vpos_j(max(lo_j, min(hi_j, b1)))))
            if horiz:
                rect(page, a, off, b - a, bw, col)
            else:
                rect(page, off, a, bw, b - a, col)
            if c.get('labels') and series[j]['values'][i] is not None:
                if horiz:
                    text(page, b + 1.2, off + bw / 2, fmt(v, step / 10 if v != int(v) else 1), pt * 0.9, 'start', font=font)
                else:
                    text(page, off + bw / 2, a - 1.8, fmt(v, step / 10 if v != int(v) else 1), pt * 0.9, font=font)
    # axes over the bars
    if horiz:
        stroke(page, px0, py0, px0, py1, GREY, ext=False)
        stroke(page, px0, py1, px1, py1, GREY, ext=False)
    else:
        stroke(page, px0, py0, px0, py1, GREY, ext=False)
        stroke(page, px0, vpos(max(lo_v, 0)), px1, vpos(max(lo_v, 0)), GREY, ext=False)
    # lines
    for j, s in enumerate(series):
        if (s.get('type') or kind) != 'line':
            continue
        col = colour(s, j)
        pts = [(cpos(i) + band / 2, scale_of(j)[0](v)) for i, v in enumerate(s['values'][:n]) if v is not None]
        if len(pts) > 1:
            page.svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" '
                            'stroke-linecap="round"/>' % (' '.join('%s,%s' % (f3(a), f3(b)) for a, b in pts), col, f3(BAR_LINE)))
        for (a, b), v in zip(pts, [v for v in s['values'][:n] if v is not None]):
            if c.get('markers'):
                page.svg.append('<circle cx="%s" cy="%s" r="1" fill="%s"/>' % (f3(a), f3(b), col))
            if c.get('labels'):
                text(page, a, b - 2.6, fmt(v, step / 10 if v != int(v) else 1), pt * 0.9, font=font)


def legend_entry(page, x, y, e, pt, font):
    name, col, mark = e
    if mark == 'line':
        page.svg.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
            f3(x), f3(y), f3(x + 3.2), f3(y), col, f3(BAR_LINE)))
    else:
        rect(page, x + 0.6, y - 1.0, 2.1, 2.1, col)
    text(page, x + 3.2 + 1.06, y, name, pt * 0.9, 'start', font=font)


def pie(page, c, s, cats, box, pt, font):
    x0, y0, x1, y1 = box
    r = min(x1 - x0, y1 - y0) / 2 * 0.963
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    vals = [max(0, v or 0) for v in s['values'][:len(cats)]]
    total = sum(vals) or 1
    a = -math.pi / 2                         # first slice at 12 o'clock, clockwise (c:firstSliceAng 0)
    for i, v in enumerate(vals):
        b = a + 2 * math.pi * v / total
        col = slice_colour(s, i)
        if v >= total:
            page.svg.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f3(cx), f3(cy), f3(r), col))
        elif v > 0:
            page.svg.append('<path d="M%s,%s L%s,%s A%s,%s 0 %d 1 %s,%s Z" fill="%s"/>' % (
                f3(cx), f3(cy), f3(cx + r * math.cos(a)), f3(cy + r * math.sin(a)), f3(r), f3(r), int(b - a > math.pi),
                f3(cx + r * math.cos(b)), f3(cy + r * math.sin(b)), col))
        if c.get('labels') and v > 0:
            m = (a + b) / 2
            lab = '%d%%' % round(100 * v / total) if c['labels'] == 'percent' else fmt(v, 1 if v == int(v) else 0.1)
            text(page, cx + 0.7 * r * math.cos(m), cy + 0.7 * r * math.sin(m), lab, pt * 0.9, font=font)
        a = b
