"""문단 첫 글자 장식 (drop cap). Block `{"dropcap": {"lines": 2|3|"margin", ...}, "p": "text"}` (the first character of
the text) or the run item `{"dropcap": {"char": "문", "lines": 2}}` that `hd read` writes. Keys: `lines` (2, 3 or "margin"),
`font`, `color` (of the character), `frame` (a line spec such as "0.4mm solid #FF0000"), `fill` (a colour), `gap` (mm to the text).
Hangul's form is a floating text box (`hp:rect dropcapstyle`) in the paragraph's first run (textstyle/rules.md TS17)."""
from ..core.units import color, esc, hu, line

STYLES = {2: ('DoubleLine', 1), 3: ('TripleLine', 2), 'margin': ('Margin', 3)}
NAMES = {v[0]: k for k, v in STYLES.items()}
NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph', 'hc': 'http://www.hancom.co.kr/hwpml/2011/core'}


def _lines(d):
    k = d.get('lines', 2)
    k = int(k) if str(k).isdigit() else str(k).lower()
    if k not in STYLES:
        raise ValueError(f'dropcap lines {d.get("lines")!r}: 2, 3 or "margin"')
    return k


def block(doc, b, ctx, extra, pending_break):
    """Builder (block key `dropcap`): a substitute block with the first character as a dropcap run item."""
    d = dict(b['dropcap'])
    text = b.get('p', '')
    pieces = list(text) if isinstance(text, list) else [text]
    first = next((i for i, x in enumerate(pieces) if isinstance(x, str) and x), None)
    if first is None:
        raise ValueError('dropcap needs text in "p"')
    d['char'] = pieces[first][0]
    pieces[first:first + 1] = [{'dropcap': d}] + ([pieces[first][1:]] if pieces[first][1:] else [])
    return dict({k: v for k, v in b.items() if k != 'dropcap'}, p=pieces)


def run(doc, piece, ctx):
    """Builder (run item `dropcap`): the rect run; the text after it is the next run."""
    if not isinstance(piece.get('dropcap'), dict):
        return None
    d = piece['dropcap']
    style, number = STYLES[_lines(d)]
    n = 2 if style == 'DoubleLine' else 3
    size = float(ctx.get('size', 10))
    ln = ctx.get('line', 160)
    pitch = size * ln / 100 if not isinstance(ln, dict) else float(next(iter(ln.values())))
    box = hu(round((n - 1) * pitch + size, 2), 'pt')                     # 2 lines of 10 pt at 160 %: 26 pt (measured)
    cprops = dict(ctx, size=box / 100, **{k: v for k, v in (('font', d.get('font')), ('color', d.get('color'))) if v})
    cid, own = doc.head.char_pr(cprops), doc.head.char_pr(ctx)
    pid = doc.head.para_pr({**{k: v for k, v in doc.defaults.items() if k in ('line', 'align')}, 'align': 'center'})
    oid = doc.next_obj()
    t, wd, col = line(d['frame']) if d.get('frame') else ('NONE', '0.1 mm', '#000000')
    lw = round(float(wd.split()[0]) * 7200 / 25.4) if d.get('frame') else 25
    face = color(d['fill']) if d.get('fill') else 'none'
    fill = f'<hc:winBrush faceColor="{face}" hatchColor="#000000" alpha="0"/>'
    ident = '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
    rect = (f'<hp:rect id="{1500000000 + oid}" zOrder="{oid}" numberingType="NONE" textWrap="SQUARE" textFlow="RIGHT_ONLY" lock="1" '
            f'dropcapstyle="{style}" href="" groupLevel="0" instid="{1600000000 + oid}" ratio="0">'
            f'<hp:offset x="0" y="0"/><hp:orgSz width="{box}" height="{box}"/><hp:curSz width="0" height="0"/>'
            '<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="0" centerY="0" rotateimage="1"/>'
            f'<hp:renderingInfo>{ident}{ident.replace("trans", "sca")}{ident.replace("trans", "rot")}</hp:renderingInfo>'
            f'<hp:lineShape color="{col}" width="{lw}" style="{t}" endCap="ROUND" headStyle="NORMAL" tailStyle="NORMAL" headfill="1" '
            'tailfill="1" headSz="SMALL_SMALL" tailSz="SMALL_SMALL" outlineStyle="NORMAL" alpha="0"/>'
            f'<hc:fillBrush>{fill}</hc:fillBrush><hp:shadow type="NONE" color="#B2B2B2" offsetX="0" offsetY="0" alpha="0"/>'
            '<hp:drawText lastWidth="4294967295" name="" editable="0"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
            'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="0" paraPrIDRef="{pid}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{cid}"><hp:t>{esc(str(d.get("char", "")))}</hp:t></hp:run></hp:p></hp:subList>'
            '<hp:textMargin left="0" right="0" top="0" bottom="0"/></hp:drawText>'
            f'<hc:pt0 x="0" y="0"/><hc:pt1 x="{box}" y="0"/><hc:pt2 x="{box}" y="{box}"/><hc:pt3 x="0" y="{box}"/>'
            f'<hp:sz width="{box}" widthRelTo="ABSOLUTE" height="{box}" heightRelTo="ABSOLUTE" protect="1"/>'
            '<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="1" holdAnchorAndSO="0" vertRelTo="PARA" '
            'horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" '
            f'horzOffset="{2 ** 32 - box if style == "Margin" else 0}"/><hp:outMargin left="0" right="{hu(d.get("gap", 0))}" top="0" bottom="0"/>'
            '<hp:shapeComment>사각형입니다.</hp:shapeComment><hp:parameterset cnt="1" name="539"><hp:listParam cnt="1" name="12291">'
            f'<hp:unsignedintegerParam name="28673">{number}</hp:unsignedintegerParam></hp:listParam></hp:parameterset></hp:rect>')
    return f'<hp:run charPrIDRef="{own}">{rect}<hp:t/></hp:run>'


def read(reader, el):
    """Reader: a `hp:rect` with dropcapstyle -> run item; any other rect is not ours (None)."""
    style = el.get('dropcapstyle', 'None')
    if style not in NAMES:
        return None
    p = el.find('hp:drawText/hp:subList/hp:p', NS)
    d = {'char': ''.join(p.itertext()) if p is not None else '', 'lines': NAMES[style]}
    run = el.find('hp:drawText/hp:subList/hp:p/hp:run', NS)
    cp = reader.refs.char.get(run.get('charPrIDRef'), {}) if run is not None else {}
    if cp.get('font') and cp['font'] != '함초롬바탕':
        d['font'] = cp['font']
    if cp.get('color') not in (None, '#000000'):
        d['color'] = cp['color']
    ls = el.find('hp:lineShape', NS)
    if ls is not None and ls.get('style') != 'NONE':
        d['frame'] = f'{round(int(ls.get("width")) * 25.4 / 7200, 3)}mm {ls.get("style").lower()} {ls.get("color")}'
    om = el.find('hp:outMargin', NS)
    if om is not None and om.get('right', '0') != '0':
        d['gap'] = round(int(om.get('right')) * 25.4 / 7200, 3)
    wb = el.find('hc:fillBrush/hc:winBrush', NS)
    if wb is not None and wb.get('faceColor') != 'none':
        d['fill'] = wb.get('faceColor')
    return {'_run': True, 'dropcap': d}
