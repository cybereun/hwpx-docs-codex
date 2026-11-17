"""Native Hangul chart: the OOXML chart part `Chart/chartN.xml` and its reader (chart/rules.md).

  chart_xml(c)   chart spec -> text of one `c:chartSpace` part
  parse(xml)     chart part -> chart spec (a part with a chart kind not modelled here is kept as {'ooxml': xml})

Spec keys (all optional but categories and series): type 'bar' (columns) | 'hbar' | 'line' | 'pie' | 'combo',
categories, series [{name, values, color, type 'bar'|'line' (combo), colors [..] (pie slices)}], title, x_title,
y_title (or unit), legend ('right' | 'left' | 'top' | 'bottom' | False), labels (True | 'percent'), stacked, markers,
gridlines, min, max, font, size. `ooxml` = a complete chart part, written as given.
"""
import re
from xml.etree import ElementTree as ET
from ..core.units import color, esc

KINDS = ('bar', 'hbar', 'line', 'pie', 'combo', 'area', 'scatter')
HEAD = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><c:chartSpace '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:date1904 val="0"/>'
        '<c:roundedCorners val="0"/><mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
        '<mc:Choice xmlns:c14="http://schemas.microsoft.com/office/drawing/2007/8/2/chart" Requires="c14">'
        '<c14:style val="102"/></mc:Choice><mc:Fallback><c:style val="2"/></mc:Fallback></mc:AlternateContent>')
BODY_PR = '<a:bodyPr rot="0" vert="horz" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr" anchorCtr="1"/>'
PLOT_FRAME = ('<c:spPr><a:noFill/><a:ln w="9525" cap="flat" cmpd="sng" algn="ctr"><a:noFill/><a:prstDash val="solid"/>'
              '<a:round/><a:headEnd w="med" len="med"/><a:tailEnd w="med" len="med"/></a:ln></c:spPr>')
TAIL = ('<c:extLst><c:ext uri="CC8EB2C9-7E31-499d-B8F2-F6CE61031016"><ho:hncChartStyle '
        'xmlns:ho="http://schemas.haansoft.com/office/8.0" layoutIndex="-1" colorIndex="0" styleIndex="0"/></c:ext></c:extLst>'
        '</c:chartSpace>')
LEGEND_POS = {'right': 'r', 'left': 'l', 'top': 't', 'bottom': 'b'}
DEF_FONT, DEF_SIZE = '함초롬돋움', 10
C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def _num(v):
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def _rich(text):
    """Title text: a plain run with the Hangul default run properties."""
    rpr = 'b="0" i="0" u="none"'
    return (f'<c:title><c:tx><c:rich>{BODY_PR}<a:p><a:pPr algn="l"><a:defRPr {rpr}/></a:pPr><a:r><a:rPr {rpr}/>'
            f'<a:t>{esc(text)}</a:t></a:r><a:endParaRPr/></a:p></c:rich></c:tx><c:layout/><c:overlay val="0"/></c:title>')


PLACEHOLDER_TITLE = ('<c:title><c:layout/><c:overlay val="0"/><c:txPr>' + BODY_PR + '<a:p><a:pPr algn="l"><a:defRPr b="0" i="0" u="none"/>'
                     '</a:pPr><a:endParaRPr/></a:p></c:txPr></c:title>')   # Hangul shows "차트 제목" for it


def _fill(col):
    return f'<a:solidFill><a:srgbClr val="{color(col)[1:]}"/></a:solidFill>'


def _ser(c, j, s, kind, n):
    """One c:ser of a bar, line or pie group. Column letters: categories A, series B, C, ..."""
    col = chr(66 + j)
    cats = c['categories']
    name = s.get('name', f'계열 {j + 1}')
    out = (f'<c:ser><c:idx val="{j}"/><c:order val="{j}"/><c:tx><c:strRef><c:f>Sheet1!${col}$1</c:f><c:strCache>'
           f'<c:ptCount val="1"/><c:pt idx="0"><c:v>{esc(name)}</c:v></c:pt></c:strCache></c:strRef></c:tx>')
    if kind == 'line':
        out += (f'<c:spPr><a:ln w="28575" cap="rnd">{_fill(s["color"])}<a:round/></a:ln></c:spPr>' if s.get('color') else '')
        mk = ('<c:symbol val="circle"/><c:size val="7"/>' + (f'<c:spPr>{_fill(s["color"])}</c:spPr>' if s.get('color') else '')
              if c.get('markers', True) else '<c:symbol val="none"/><c:size val="7"/>')
        out += f'<c:marker>{mk}</c:marker>'
    elif kind == 'scatter':                               # markers only unless `lines`
        out += (f'<c:spPr><a:ln w="28575" cap="rnd">{_fill(s["color"]) if s.get("color") else ""}<a:round/></a:ln></c:spPr>'
                if c.get('lines') else '<c:spPr><a:ln w="28575"><a:noFill/></a:ln></c:spPr>')
        mk = ('<c:symbol val="circle"/><c:size val="7"/>' + (f'<c:spPr>{_fill(s["color"])}</c:spPr>' if s.get('color') else '')
              if c.get('markers', True) else '<c:symbol val="none"/><c:size val="7"/>')
        out += f'<c:marker>{mk}</c:marker>'
    elif kind == 'area':
        out += f'<c:spPr>{_fill(s["color"])}</c:spPr>' if s.get('color') else ''
    elif kind == 'bar':
        out += f'<c:spPr>{_fill(s["color"])}</c:spPr>' if s.get('color') else ''
        out += '<c:invertIfNegative val="0"/>'
    else:                                                 # pie: one colour per slice
        out += '<c:explosion val="0"/>'
        for i, pc in enumerate(s.get('colors', [])):
            out += f'<c:dPt><c:idx val="{i}"/><c:bubble3D val="0"/><c:spPr>{_fill(pc)}</c:spPr></c:dPt>'
    lab = c.get('labels')
    if lab:
        pct = 1 if (lab == 'percent' and kind == 'pie') else 0
        out += (f'<c:dLbls><c:showLegendKey val="0"/><c:showVal val="{1 - pct}"/><c:showCatName val="0"/>'
                f'<c:showSerName val="0"/><c:showPercent val="{pct}"/><c:showBubbleSize val="0"/></c:dLbls>')
    vals = s['values']
    if kind == 'scatter':                                 # x values = categories (numbers), shared by all series
        out += (f'<c:xVal><c:numRef><c:f>Sheet1!$A$2:$A${len(cats) + 1}</c:f><c:numCache><c:formatCode>General</c:formatCode>'
                f'<c:ptCount val="{len(cats)}"/>'
                + ''.join(f'<c:pt idx="{i}"><c:v>{_num(v)}</c:v></c:pt>' for i, v in enumerate(cats))
                + '</c:numCache></c:numRef></c:xVal>')
        tag = 'yVal'
    else:
        out += ('<c:cat><c:strRef><c:f>Sheet1!$A$2:$A$%d</c:f><c:strCache><c:ptCount val="%d"/>' % (len(cats) + 1, len(cats))
                + ''.join(f'<c:pt idx="{i}"><c:v>{esc(v)}</c:v></c:pt>' for i, v in enumerate(cats))
                + '</c:strCache></c:strRef></c:cat>')
        tag = 'val'
    out += (f'<c:{tag}><c:numRef><c:f>Sheet1!${col}$2:${col}${len(vals) + 1}</c:f><c:numCache><c:formatCode>General</c:formatCode>'
            f'<c:ptCount val="{len(vals)}"/>'
            + ''.join(f'<c:pt idx="{i}"><c:v>{_num(v)}</c:v></c:pt>' for i, v in enumerate(vals) if v is not None)
            + f'</c:numCache></c:numRef></c:{tag}>')
    if kind in ('line', 'scatter'):
        out += '<c:smooth val="0"/>'
    return out + '</c:ser>'


def _axis_title(t):
    return _rich(t) if t else ''


def chart_xml(c):
    if c.get('ooxml'):
        return c['ooxml']
    kind = c.get('type', 'bar')
    if kind not in KINDS:
        raise ValueError(f'unknown native chart type: {kind}')
    series = c['series']
    if not c.get('categories') or not series:
        raise ValueError('a native chart needs categories and series')
    if any(len(s['values']) != len(c['categories']) for s in series):
        raise ValueError('every series needs one value per category')
    font, size = c.get('font', DEF_FONT), c.get('size', DEF_SIZE)
    ax1, ax2 = '481900647', '209644262'
    stacked = bool(c.get('stacked'))
    kinds = [(s.get('type') or ('bar' if j == 0 else 'line')) if kind == 'combo' else kind.replace('hbar', 'bar')
             for j, s in enumerate(series)]
    if any(k not in ('bar', 'line', 'area') for k in kinds if kind == 'combo'):
        raise ValueError('a combo series has type bar, line or area')
    sec = [kind != 'pie' and s.get('axis') == 'secondary' for s in series]
    if all(sec):
        raise ValueError('at least one series stays on the primary axis')
    ax3, ax4 = '209644263', '481900648'                  # secondary value and category axis ids
    groups = ''
    for second in (False, True):
        for g in ('area', 'bar', 'line', 'scatter'):
            idx = [j for j, k in enumerate(kinds) if k == g and sec[j] == second]
            if not idx or kind == 'pie':
                continue
            sers = ''.join(_ser(c, j, series[j], g, len(series)) for j in idx)
            ids = (f'<c:axId val="{ax4}"/><c:axId val="{ax3}"/>' if second else f'<c:axId val="{ax2}"/><c:axId val="{ax1}"/>')
            if g == 'bar':
                groups += (f'<c:barChart><c:barDir val="{"bar" if kind == "hbar" else "col"}"/>'
                           f'<c:grouping val="{"stacked" if stacked else "clustered"}"/><c:varyColors val="0"/>{sers}'
                           f'<c:gapWidth val="150"/><c:overlap val="{100 if stacked else 0}"/>{ids}</c:barChart>')
            elif g == 'area':
                groups += (f'<c:areaChart><c:grouping val="{"stacked" if stacked else "standard"}"/><c:varyColors val="0"/>{sers}'
                           f'{ids}</c:areaChart>')
            elif g == 'scatter':
                groups += f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{sers}{ids}</c:scatterChart>'
            else:
                groups += (f'<c:lineChart><c:grouping val="{"stacked" if stacked else "standard"}"/><c:varyColors val="0"/>{sers}'
                           f'<c:marker val="1"/>{ids}</c:lineChart>')
    if kind == 'pie':
        groups = f'<c:pieChart><c:varyColors val="1"/>{_ser(c, 0, series[0], "pie", 1)}<c:firstSliceAng val="0"/></c:pieChart>'
    else:
        h = kind == 'hbar'
        grid = '<c:majorGridlines/>' if c.get('gridlines', True) else ''
        mn = f'<c:min val="{_num(c["min"])}"/>' if c.get('min') is not None else ''
        mx = f'<c:max val="{_num(c["max"])}"/>' if c.get('max') is not None else ''
        yt = c.get('y_title') or (f'({c["unit"]})' if c.get('unit') else '')
        # negative values: the category labels go to the bottom of the plot, not onto the zero line (rules.md CH10)
        low = 'low' if any(v is not None and v < 0 for sr in series for v in sr['values']) else 'nextTo'
        if kind == 'scatter':                    # two value axes: x (bottom) and y (left)
            xmn = f'<c:min val="{_num(c["x_min"])}"/>' if c.get('x_min') is not None else ''
            xmx = f'<c:max val="{_num(c["x_max"])}"/>' if c.get('x_max') is not None else ''
            cat = (f'<c:valAx><c:axId val="{ax2}"/><c:scaling><c:orientation val="minMax"/>{xmx}{xmn}</c:scaling>'
                   f'<c:axPos val="b"/><c:crossAx val="{ax1}"/><c:delete val="0"/>{_axis_title(c.get("x_title"))}'
                   '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
                   '<c:tickLblPos val="nextTo"/><c:crosses val="autoZero"/><c:crossBetween val="midCat"/></c:valAx>')
        else:
            cat = (f'<c:catAx><c:axId val="{ax2}"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
                   f'<c:axPos val="{"l" if h else "b"}"/><c:crossAx val="{ax1}"/><c:delete val="0"/>{_axis_title(c.get("x_title"))}'
                   f'<c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="{low}"/><c:crosses val="autoZero"/>'
                   '<c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:tickMarkSkip val="1"/><c:noMultiLvlLbl val="0"/></c:catAx>')
        between = 'midCat' if kind == 'scatter' or set(kinds) == {'area'} else 'between'
        val = (f'<c:valAx><c:axId val="{ax1}"/><c:scaling><c:orientation val="minMax"/>{mx}{mn}</c:scaling>'
               f'<c:axPos val="{"b" if h else "l"}"/><c:crossAx val="{ax2}"/><c:delete val="0"/>{grid}{_axis_title(yt)}'
               '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
               f'<c:tickLblPos val="nextTo"/><c:crosses val="autoZero"/><c:crossBetween val="{between}"/></c:valAx>')
        groups += cat + val
        if any(sec):                             # secondary axes: values on the right (top for horizontal bars), shared categories
            y2mn = f'<c:min val="{_num(c["y2_min"])}"/>' if c.get('y2_min') is not None else ''
            y2mx = f'<c:max val="{_num(c["y2_max"])}"/>' if c.get('y2_max') is not None else ''
            groups += (f'<c:valAx><c:axId val="{ax3}"/><c:scaling><c:orientation val="minMax"/>{y2mx}{y2mn}</c:scaling>'
                       f'<c:axPos val="{"t" if h else "r"}"/><c:crossAx val="{ax4}"/><c:delete val="0"/>{_axis_title(c.get("y2_title"))}'
                       '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
                       f'<c:tickLblPos val="nextTo"/><c:crosses val="max"/><c:crossBetween val="{between}"/></c:valAx>')
            if kind == 'scatter':
                groups += (f'<c:valAx><c:axId val="{ax4}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="b"/>'
                           f'<c:crossAx val="{ax3}"/><c:delete val="1"/><c:numFmt formatCode="General" sourceLinked="1"/>'
                           '<c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
                           '<c:crosses val="autoZero"/><c:crossBetween val="midCat"/></c:valAx>')
            else:
                groups += (f'<c:catAx><c:axId val="{ax4}"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
                           f'<c:axPos val="{"l" if h else "b"}"/><c:crossAx val="{ax3}"/><c:delete val="1"/>'
                           '<c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
                           '<c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/>'
                           '<c:tickMarkSkip val="1"/><c:noMultiLvlLbl val="0"/></c:catAx>')
    legend = c.get('legend', len(series) > 1 or kind == 'pie')
    pos = LEGEND_POS.get(legend if isinstance(legend, str) else 'right')
    leg = f'<c:legend><c:legendPos val="{pos}"/><c:layout/><c:overlay val="0"/></c:legend>' if legend else ''
    title = _rich(c['title']) if c.get('title') else PLACEHOLDER_TITLE if c.get('title') == '' else ''
    return (HEAD + f'<c:chart>{title}<c:autoTitleDeleted val="{0 if title else 1}"/><c:plotArea><c:layout/>{groups}{PLOT_FRAME}'
            f'</c:plotArea>{leg}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
            f'<c:txPr>{BODY_PR}<a:p><a:pPr algn="l"><a:defRPr sz="{round(size * 100)}" b="0" i="0" u="none">'
            + ''.join(f'<a:{t} typeface="{esc(font)}"/>' for t in ('latin', 'ea', 'cs', 'sym'))
            + '</a:defRPr></a:pPr><a:endParaRPr/></a:p></c:txPr>' + TAIL)


# ---- reader ---------------------------------------------------------------------------------------------------------
def _text(el):
    return ''.join(t.text or '' for t in el.iter(A + 't')) if el is not None else ''


def _val(el, tag, default=None):
    f = el.find(C + tag) if el is not None else None
    return f.get('val') if f is not None else default


def _vals(ref):
    pts = {int(p.get('idx')): p.find(C + 'v').text for p in ref.iter(C + 'pt')}
    n = int(_val(ref, 'ptCount', max(pts, default=-1) + 1))
    return [pts.get(i) for i in range(n)]


def _number(v):
    f = float(v)
    return int(f) if f.is_integer() else f


def _fillcol(sp):
    f = sp.find('.//' + A + 'solidFill/' + A + 'srgbClr') if sp is not None else None
    return color(f.get('val')) if f is not None else None


def parse(xml, strict=True):
    """Chart part -> spec. Returns {'ooxml': xml} when the part has anything that the spec cannot say.
    strict=False: the data and the main settings even when the part says more (for a viewer; not for writing)."""
    try:
        root = ET.fromstring(xml)
        ch = root.find(C + 'chart')
        plot = ch.find(C + 'plotArea')
        groups = [g for g in plot if g.tag.endswith('Chart')]
        names = [g.tag[len(C):] for g in groups]
        gids = [tuple(a.get('val') for a in g.findall(C + 'axId')) for g in groups]
        if (not set(names) <= {'barChart', 'lineChart', 'pieChart', 'areaChart', 'scatterChart'}
                or len(set(zip(names, gids))) != len(names) or len(set(gids)) > 2):
            raise ValueError(names)
        rows = []           # (kind, ser element, on the secondary axes) in series order
        for g, ids in zip(groups, gids):
            kind = {'barChart': 'bar', 'lineChart': 'line', 'pieChart': 'pie', 'areaChart': 'area',
                    'scatterChart': 'scatter'}[g.tag[len(C):]]
            rows += [(kind, s, ids != gids[0]) for s in g.findall(C + 'ser')]
        rows.sort(key=lambda r: int(_val(r[1], 'idx', 0)))
        series, cats = [], []
        for kind, s, second in rows:
            cat = s.find(C + 'cat')
            cats = [v or '' for v in _vals(cat)] if cat is not None else cats
            xv = s.find(C + 'xVal')
            if xv is not None:
                cats = [_number(v) for v in _vals(xv)]
            tx = s.find(C + 'tx')
            sd = {'name': ''.join(v.text or '' for v in tx.iter(C + 'v')) if tx is not None else ''}
            sd['values'] = [None if v is None else _number(v) for v in _vals(s.find(C + ('yVal' if kind == 'scatter' else 'val')))]
            sp = s.find(C + 'spPr')
            if kind == 'scatter':                    # the colour is the marker's
                mk = s.find(C + 'marker')
                col = _fillcol(mk.find(C + 'spPr') if mk is not None else None)
            else:
                col = _fillcol(sp.find(A + 'ln') if kind == 'line' and sp is not None and sp.find(A + 'ln') is not None else sp)
            if col:
                sd['color'] = col
            if second:
                sd['axis'] = 'secondary'
            if kind == 'pie':
                dpts = sorted(s.findall(C + 'dPt'), key=lambda d: int(_val(d, 'idx', 0)))
                cols = [_fillcol(d.find(C + 'spPr')) for d in dpts]
                if any(cols):
                    sd['colors'] = cols
            series.append(sd)
        sers_xml = [r[1] for r in rows]
        c = {'categories': cats, 'series': series}
        kinds = [r[0] for r in rows]
        bar = next((g for g in groups if g.tag == C + 'barChart'), None)
        if kinds and kinds[0] == 'pie':
            c['type'] = 'pie'
        elif len(set(kinds)) > 1:
            c['type'] = 'combo'
            for sd, k in zip(series, kinds):
                sd['type'] = k
        elif kinds[0] in ('line', 'area', 'scatter'):
            c['type'] = kinds[0]
        else:
            c['type'] = 'hbar' if _val(bar, 'barDir') == 'bar' else 'bar'
        grp = groups[0]
        if _val(grp, 'grouping') == 'stacked':
            c['stacked'] = True
        if ch.find(C + 'title') is not None:
            c['title'] = _text(ch.find(C + 'title'))      # '' = Hangul's placeholder title
        lg = ch.find(C + 'legend')
        pos = {v: k for k, v in LEGEND_POS.items()}.get(_val(lg, 'legendPos', 'r')) if lg is not None else False
        c['legend'] = pos
        d = sers_xml[0].find(C + 'dLbls') if sers_xml else None
        if d is not None and (_val(d, 'showVal') == '1' or _val(d, 'showPercent') == '1'):
            c['labels'] = 'percent' if _val(d, 'showPercent') == '1' else True
        mks = [r[1].find(C + 'marker') for r in rows if r[0] in ('line', 'scatter')]
        if mks:
            c['markers'] = _val(mks[0], 'symbol', 'none') != 'none' if mks[0] is not None else False
        if 'scatter' in kinds:
            ln = next(r[1] for r in rows if r[0] == 'scatter').find(C + 'spPr/' + A + 'ln')
            if ln is None or ln.find(A + 'noFill') is None:
                c['lines'] = True

        def axes(ids):          # (category or x axis, value axis) of a group with the axis ids `ids`
            els = [e for i in ids for e in plot if e.tag in (C + 'catAx', C + 'valAx') and _val(e, 'axId') == i]
            cax_ = next((e for e in els if e.tag == C + 'catAx'), els[0] if els else None)
            return cax_, next((e for e in els if e is not cax_), None)

        def num(sc, k):
            v = _val(sc, k)
            return None if v is None else _number(v)
        cax, vax = axes(gids[0]) if gids[0] else (None, None)
        if cax is not None and _text(cax.find(C + 'title')):
            c['x_title'] = _text(cax.find(C + 'title'))
        if cax is not None and kinds[0] == 'scatter':
            for k in ('min', 'max'):
                if num(cax.find(C + 'scaling'), k) is not None:
                    c['x_' + k] = num(cax.find(C + 'scaling'), k)
        if vax is not None:
            if _text(vax.find(C + 'title')):
                c['y_title'] = _text(vax.find(C + 'title'))
            if vax.find(C + 'majorGridlines') is None:
                c['gridlines'] = False
            for k in ('min', 'max'):
                if num(vax.find(C + 'scaling'), k) is not None:
                    c[k] = num(vax.find(C + 'scaling'), k)
        second = [g for g in gids if g != gids[0]]
        if second:
            _, v2 = axes(second[0])
            if v2 is not None:
                if _text(v2.find(C + 'title')):
                    c['y2_title'] = _text(v2.find(C + 'title'))
                for k in ('min', 'max'):
                    if num(v2.find(C + 'scaling'), k) is not None:
                        c['y2_' + k] = num(v2.find(C + 'scaling'), k)
        rpr = root.find(C + 'txPr/' + A + 'p/' + A + 'pPr/' + A + 'defRPr')
        if rpr is not None:
            sz = int(rpr.get('sz', DEF_SIZE * 100))
            if sz != DEF_SIZE * 100:
                c['size'] = sz // 100 if sz % 100 == 0 else sz / 100
            lat = rpr.find(A + 'latin')
            if lat is not None and lat.get('typeface') not in (None, DEF_FONT):
                c['font'] = lat.get('typeface')
        if strict and chart_xml(c) != xml and _fingerprint(chart_xml(c)) != _fingerprint(xml):
            # the part says more than the spec model (styles, layouts, data refs ...): keep it whole
            raise ValueError('not reproducible')
        return c
    except (ValueError, KeyError, AttributeError, ET.ParseError, TypeError, StopIteration):
        return {'ooxml': xml}


def _fingerprint(xml):
    """What the spec can say about a chart part: the structure with text and attributes, ids and the Hangul
    style extension left out. Two parts with the same fingerprint draw the same chart."""
    x = re.sub(r'<c:axId val="\d+"/>|<c:crossAx val="\d+"/>|<c:extLst>.*?</c:extLst>', '', xml, flags=re.S)
    # what Hangul adds when it saves a chart again (rules.md CH11): defaults that change nothing on the page
    x = re.sub(r'<c:size val="\d+"/>|<c:explosion val="0"/>|<c:smooth val="0"/>|<c:numFmt formatCode="[^"]*"|'
               r'<c:delete val="0"/>|<c:showLeaderLines val="0"/>|<c:dLblPos val="r"/>|<c:invertIfNegative val="0"/>| cmpd="sng"', '', x)
    return re.sub(r'\s+', '', re.sub(r'srgbClr val="(\w+)"', lambda m: f'srgbClr val="{m.group(1).lower()}"', x))


def selftest():
    spec = {'type': 'combo', 'title': '실적', 'categories': ['가', '나', '다'], 'x_title': '분기', 'y_title': '억 원',
            'series': [{'name': '매출', 'values': [3, 5.5, 4], 'color': '#C00000'},
                       {'name': '이익', 'values': [1, 2, 1.5], 'type': 'line', 'color': '#0070C0'}],
            'legend': 'bottom', 'labels': True, 'markers': True, 'stacked': False, 'gridlines': True, 'max': 10}
    x = chart_xml(spec)
    ET.fromstring(x)
    assert '<c:barChart>' in x and '<c:lineChart>' in x and x.count('<c:axId val="481900647"/>') == 3, 'combo shares axes'
    back = parse(x)
    assert 'ooxml' not in back, back
    assert chart_xml(back) == x, 'spec -> part -> spec -> part is stable'
    for t in ('bar', 'hbar', 'line'):
        s = {'type': t, 'categories': ['a', 'b'], 'series': [{'name': 'n', 'values': [1, 2]}], 'legend': False, 'gridlines': True,
             'stacked': False}
        assert 'ooxml' not in parse(chart_xml(s)) and parse(chart_xml(s))['type'] == t, t
    p = parse(chart_xml({'type': 'pie', 'categories': ['a', 'b'], 'series': [{'name': 'n', 'values': [1, 2], 'colors': ['#FF0000', '#00FF00']}],
                         'labels': 'percent'}))
    assert p['type'] == 'pie' and p['series'][0]['colors'] == ['#FF0000', '#00FF00'] and p['labels'] == 'percent', p
    neg = chart_xml({'categories': ['a', 'b'], 'series': [{'name': 's', 'values': [-1, 2]}]})
    assert 'tickLblPos val="low"' in neg and 'tickLblPos val="low"' not in chart_xml({'categories': ['a'], 'series': [{'values': [1]}]})
    # what Hangul writes when it saves the part again (rules.md CH11) still reads as a spec, not as a raw part
    hs = chart_xml(spec).replace('<c:dLbls>', '<c:dLbls><c:delete val="0"/>').replace('</c:dLbls>', '<c:showLeaderLines val="0"/></c:dLbls>')
    hs = hs.replace('C00000', 'c00000').replace('<a:ln w="28575" cap="rnd">', '<a:ln w="28575" cap="rnd" cmpd="sng">')
    assert 'ooxml' not in parse(hs) and chart_xml(parse(hs)) == x, 'a re-saved Hangul part is modelled'
    # area, scatter and the secondary axis: spec -> part -> spec -> part is stable (Hangul render: see coverage.md)
    cs, sr = ['가', '나', '다'], [{'name': 'a', 'values': [3, 5, 4], 'color': '#C00000'}, {'name': 'b', 'values': [2, 4, 1]}]
    for ex in ({'type': 'area', 'categories': cs, 'series': sr, 'legend': 'bottom'},
               {'type': 'area', 'categories': cs, 'series': sr, 'stacked': True, 'legend': 'bottom'},
               {'type': 'scatter', 'categories': [1, 2.5, 4], 'series': sr, 'x_title': 'x', 'y_title': 'y', 'x_min': 0, 'x_max': 5,
                'lines': True, 'legend': 'right'},
               {'type': 'scatter', 'categories': [1, 2.5, 4], 'series': sr, 'legend': False, 'markers': True},
               {'type': 'combo', 'categories': cs, 'legend': 'bottom', 'y_title': '억 원', 'y2_title': '%', 'y2_min': 0, 'y2_max': 100,
                'series': [{'name': 'a', 'values': [3, 5, 4]}, {'name': 'b', 'values': [20, 40, 10], 'type': 'line', 'axis': 'secondary'}]},
               {'type': 'bar', 'categories': cs, 'legend': 'bottom',
                'series': [{'name': 'a', 'values': [3, 5, 4]}, {'name': 'b', 'values': [20, 40, 10], 'axis': 'secondary'}]},
               {'type': 'combo', 'categories': cs, 'legend': 'bottom',
                'series': [{'name': 'a', 'values': [3, 5, 4], 'type': 'area'}, {'name': 'b', 'values': [2, 4, 1], 'type': 'line'}]}):
        xs = chart_xml(ex)
        ET.fromstring(xs)
        back = parse(xs)
        assert 'ooxml' not in back and chart_xml(back) == xs, (ex['type'], back)
        assert back['type'] == ex['type'] and [s.get('axis') for s in back['series']] == [s.get('axis') for s in ex['series']], back
    assert '<c:areaChart>' in chart_xml({'type': 'area', 'categories': cs, 'series': sr})
    sx = chart_xml({'type': 'scatter', 'categories': [1, 2], 'series': sr[:1] and [{'name': 'a', 'values': [1, 2]}]})
    assert '<c:scatterChart>' in sx and '<c:xVal>' in sx and sx.count('<c:valAx>') == 2 and '<c:catAx>' not in sx, 'scatter axes'
    se = chart_xml({'categories': cs, 'series': [{'values': [1, 2, 3]}, {'values': [3, 2, 1], 'axis': 'secondary'}]})
    assert se.count('<c:valAx>') == 2 and se.count('<c:catAx>') == 2 and 'crosses val="max"' in se, 'secondary axes'
    try:
        chart_xml({'categories': cs, 'series': [{'values': [1, 2, 3], 'axis': 'secondary'}]})
        raise AssertionError('all series on the secondary axis accepted')
    except ValueError:
        pass
    odd = HEAD + '<c:chart><c:plotArea><c:radarChart/></c:plotArea></c:chart></c:chartSpace>'
    assert parse(odd) == {'ooxml': odd}, 'an unmodelled kind is kept whole'
    for bad in ({'type': 'x', 'categories': ['a'], 'series': [{'values': [1]}]}, {'categories': ['a'], 'series': [{'values': [1, 2]}]}):
        try:
            chart_xml(bad)
        except ValueError:
            continue
        raise AssertionError('bad chart spec accepted')
    print('CHART SELFTEST PASS')


if __name__ == '__main__':
    selftest()
