"""Self-test of the table package (no Hangul needed): `hd selftest --only table`.

Builds tables with every table key, checks that the parts parse, and that read -> build -> read gives the same spec.
The fixtures folder (Hangul-made samples of this package): every file reads -> builds -> reads to the same spec.
"""
from ..core import tmpdir
import glob
import json
import os
import zipfile
from xml.dom import minidom

from ..core import build, read
from ..render import img


def _build(spec, name, base=None):
    d = base or tmpdir.mkdtemp('hwpx_docs_tb_')
    out = os.path.join(d, name + '.hwpx')
    build.write(spec, out, base=d)
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.xml', '.hpf'))}
    for t in parts.values():
        minidom.parseString(t)
    return out, parts


def _again(path):
    """spec of a built file, and the spec of the file built from it: they must be equal."""
    d = os.path.dirname(path)
    a = read.read(path, os.path.join(d, 'a.json'))
    out, _ = _build(a, 'again', d)
    b = read.read(out, os.path.join(d, 'b.json'))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), (a, b)
    return a


def _table(**kw):
    t = {'cols': [30, 40], 'heights': [10, 10], 'rows': [['a', 'b'], ['c', 'd']]}
    t.update(kw)
    return {'body': [{'table': t}]}


def run():
    # base grid, merges, borders (the old core test)
    spec = {'body': [{'table': {'cols': [30, 40, 50], 'heights': [10, 10, 10], 'border': '0.12mm solid',
                                'rows': [[{'p': '머리', 'cs': 2, 'fill': '#D9D9D9', 'bold': True}, {'p': '세로', 'rs': 2}],
                                         ['a', {'p': 'b', 'border': {'bottom': '0.5mm double'}}],
                                         ['c', 'd', 'e']]}}]}
    _, parts = _build(spec, 'table')
    s, h = parts['Contents/section0.xml'], parts['Contents/header.xml']
    assert s.count('<hp:tc ') == 7, s.count('<hp:tc ')
    assert 'colSpan="2"' in s and 'rowSpan="2"' in s and 'DOUBLE_SLIM' in h and '#D9D9D9' in h.upper()
    # gradient and picture fills
    grad = {'type': 'gradient', 'kind': 'radial', 'angle': 45, 'center': [50, 50], 'colors': ['#FFFFFF', '#3366CC']}
    d = tmpdir.mkdtemp('hwpx_docs_tb_')
    img.save_png(os.path.join(d, 'a.png'), (8, 8, [bytes([200, 120, 40]) * 8] * 8))
    pic = {'type': 'image', 'src': 'a.png', 'mode': 'total'}
    spec = _table(rows=[[{'p': 'g', 'fill': grad}, {'p': 'i', 'fill': pic}], [{'p': 'i2', 'fill': pic}, 'd']])
    path, parts = _build(spec, 'fills', d)
    assert 'colorNum="2"' in parts['Contents/header.xml'] and 'mode="TOTAL"' in parts['Contents/header.xml']
    assert sum(1 for n in parts if n == 'Contents/header.xml') == 1
    with zipfile.ZipFile(path) as z:
        assert len([n for n in z.namelist() if n.startswith('BinData/')]) == 1, 'one picture stored once'
    cells = _again(path)['body'][0]['table']['rows']
    assert cells[0][0]['fill'] == grad and cells[0][1]['fill']['mode'] == 'total', cells
    # caption
    for cap in ({'text': '제목'}, {'text': '제목', 'side': 'top', 'label': '표'}, {'text': '글', 'number': False}):
        path, parts = _build(_table(caption=cap), 'caption')
        assert '<hp:caption ' in parts['Contents/section0.xml']
        t = _again(path)['body'][0]['table']
        assert t['caption']['text'] == cap['text'] and t['caption']['number'] == cap.get('number', True), t['caption']
    # hold: a flow table that keeps its paragraph on its page (holdAnchorAndSO), read back as a flow table, not a floating one
    path, parts = _build(_table(hold=True), 'hold')
    assert 'holdAnchorAndSO="1"' in parts['Contents/section0.xml']
    t = _again(path)['body'][0]['table']
    assert t.get('hold') is True and 'pos' not in t, t
    # cell protect
    path, parts = _build(_table(rows=[[{'p': 'a', 'protect': True}, 'b'], ['c', 'd']]), 'protect')
    assert parts['Contents/section0.xml'].count('protect="1"') == 1
    assert _again(path)['body'][0]['table']['rows'][0][0]['protect'] is True
    # formula cells
    f1, f2 = {'expr': '=SUM(?1:?3)', 'format': '%g,'}, '=SUM(A1:A3);60'
    path, parts = _build(_table(rows=[[{'p': '60', 'formula': f1}, {'p': '', 'formula': f2}], ['c', 'd']]), 'formula')
    s = parts['Contents/section0.xml']
    assert s.count('type="FORMULA"') == 2 and 'cnt="5"' in s and 'cnt="3"' in s and 'LastResult">60<' in s, s[:400]
    row = _again(path)['body'][0]['table']['rows'][0]
    assert row[0]['formula'] == f1 and row[0]['p'] == '60' and row[1]['formula'] == f2, row
    # text flow beside a square-wrapped table (textFlow): `side` goes out and comes back
    for side in ('left_only', 'right_only', 'largest_only'):
        path, parts = _build(_table(wrap='square', side=side, pos={'x': 0, 'y': 0, 'rel': 'paper'}), 'side')
        assert f'textFlow="{side.upper()}"' in parts['Contents/section0.xml']
        assert _again(path)['body'][0]['table']['side'] == side
    # floating position
    for pos in ({'x': 20, 'y': 30, 'rel': 'paper'}, {'x': 0, 'y': 0, 'rel': 'page', 'valign': 'bottom', 'halign': 'right'},
                {'x': 5, 'y': 10, 'vrel': 'para', 'hrel': 'column', 'flow': True, 'overlap': False}):
        path, parts = _build(_table(pos=pos, wrap='square'), 'pos')
        assert 'treatAsChar="0"' in parts['Contents/section0.xml']
        t = _again(path)['body'][0]['table']
        got = {k: round(v, 1) if isinstance(v, float) else v for k, v in t['pos'].items()}    # mm -> hu -> mm rounds
        assert got == pos and t['wrap'] == 'square', (got, pos)
    draw_tests(d)
    fixtures()


def draw_tests(d):
    """Preview drawing with stand-ins for the preview's layout functions (the hooks themselves live in preview/)."""
    from . import draw

    class Page:
        svg = []

    class Atom:
        def __init__(self, h, emit=None, trail=0.0, keep=False, absorb=0.0):
            self.h, self.emit, self.keep, self.trail, self.absorb = h, emit, keep, trail, absorb

    class Ctx:
        def image(self, src):
            p = os.path.join(d, src)
            import base64
            return 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode() if os.path.exists(p) else None

    page = Page()
    page.svg = []
    assert draw.paint(Ctx(), page, '#FF0000', 10, 10) == '#FF0000'
    grad = {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'colors': ['#FFFFFF', '#000000']}
    p = draw.paint(Ctx(), page, grad, 10, 10)
    assert p.startswith('url(#tbg') and '<linearGradient' in page.svg[-1] and p[5:-1] in page.svg[-1], page.svg
    assert '<radialGradient' in (draw.paint(Ctx(), page, {'type': 'gradient', 'kind': 'conical'}, 5, 5) and page.svg[-1])
    p = draw.paint(Ctx(), page, {'type': 'image', 'src': 'a.png', 'mode': 'total'}, 20, 10)
    assert p.startswith('url(#tbi') and '<pattern' in page.svg[-1]
    assert draw.paint(Ctx(), page, {'type': 'image', 'src': 'missing.png'}, 5, 5) == '#D9D9D9'

    def layout_table(ctx, t, cst, avail, align='left', inline=False):
        return sum(t['cols']), [Atom(10)]

    def layout_para(ctx, b, cst, width, no_before=False):
        return [Atom(5)] if 'shapes' not in b else [b['shapes'][0]]
    ctx = Ctx()
    t = {'cols': [30, 40], 'rows': [['a', 'b']], 'caption': {'text': '제목', 'side': 'top'}}
    out = draw.wrap(ctx, {'table': t}, {}, 160, layout_table, layout_para)
    assert [a.h for a in out] == [5, 10] and ctx.table_caps == 1, 'top caption comes first'
    out = draw.wrap(ctx, {'table': dict(t, caption='아래')}, {}, 160, layout_table, layout_para)
    assert [a.h for a in out] == [10, 5] and ctx.table_caps == 2, 'bottom caption comes last'
    assert draw.wrap(ctx, {'table': {'cols': [30], 'rows': [['a']]}}, {}, 160, layout_table, layout_para) is None
    seen = []                                   # left and right captions stand beside the table: same number of atoms, table moved
    for side, shift in (('left', 23.0), ('right', 0.0)):
        t2 = dict(t, caption={'text': '옆', 'side': side, 'width': 20})
        out = draw.wrap(ctx, {'table': t2}, {}, 160, layout_table,
                        lambda c, b, st, wd, nb=False: [Atom(5, lambda x, y, pg: seen.append(('cap', round(x, 1), round(y, 1))))])
        assert len(out) == 1 and out[0].h == 10, side
        out[0].emit(0, 0, Page())
        assert seen[-1][0] == 'cap' and seen[-1][1] == (1.0 if side == 'left' else 1.0 + 70 + 3.0), seen
    page2 = Page()
    page2.svg = []
    draw.stroke_wave(page2, 0, 0, 20, 0, 0.4, '#000')
    draw.stroke_doublewave(page2, 0, 5, 20, 5, 0.4, '#000')
    assert len(page2.svg) == 3 and all(e.startswith('<path ') for e in page2.svg), page2.svg
    out = draw.wrap(ctx, {'table': dict(t, caption=None, pos={'x': 20, 'y': 30, 'rel': 'paper'})}, {}, 160, layout_table,
                    layout_para)
    sh = out[0]
    assert sh['type'] == 'object' and sh['x'] == 20 and sh['rel'] == 'paper' and sh['w'] == 70 and sh['obj']['kind'] == 'drawn'
    assert sh['obj']['draw'](20, 30) == []
    # through the real preview (hooks drawers.paint / drawers.table_wrap, drawers/table.py)
    from ..preview import render_pages
    spec = {'body': ['본문', {'table': {'cols': [40, 40], 'heights': [10], 'caption': {'text': '캡션'},
                                       'rows': [[{'p': 'g', 'fill': grad_spec()}, 'b']]}},
                     {'table': {'cols': [30], 'heights': [10], 'rows': [['떠']], 'pos': {'x': 100, 'y': 200, 'rel': 'paper'}}}]}
    path, _ = _build(spec, 'prev', d)
    svg = render_pages(path)[0][2]
    assert 'linearGradient' in svg and 'url(#tbg' in svg, 'gradient cell is painted'
    assert 'PREVIEW NOT DRAWN' not in svg and svg.count('<rect') >= 1


def grad_spec():
    return {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'colors': ['#FFFFFF', '#3366CC']}


def fixtures():
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', '*.hwpx')))
    tmp = tmpdir.mkdtemp('hwpx_docs_tbf_')
    bad = []
    for f in files:
        n = os.path.splitext(os.path.basename(f))[0]
        a = read.read(f, os.path.join(tmp, n + '.a.json'))
        build.write(a, os.path.join(tmp, n + '.hwpx'), base=tmp)
        b = read.read(os.path.join(tmp, n + '.hwpx'), os.path.join(tmp, n + '.b.json'))
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            bad.append(n)
    assert not bad, f'{len(bad)} of {len(files)} table fixtures not stable: {bad[:8]}'
    if not files:
        return

    def table_of(name):
        spec = read.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', name + '.hwpx'),
                         os.path.join(tmp, name + '.json'))
        return next(b['table'] for b in spec['body'] if 'table' in b)
    lt = table_of('cell_line_types')
    types = {line.split()[1] for r in lt['rows'] for c in r if isinstance(c, dict)
             for line in c.get('border', {}).values() if not line.startswith('none')} | {lt['border'].split()[1]}
    assert {'dash_dot', 'dash_dot_dot', 'long_dash', 'circle', 'double_slim', 'slim_thick', 'thick_slim', 'slim_thick_slim', 'wave',
            'doublewave', 'thick3d'} <= types, types                                   # C5.06: sampled line types
    g = table_of('cell_fill_gradient')['rows'][0]
    assert [c['fill']['kind'] for c in g] == ['linear', 'radial', 'square'], g           # C5.09
    assert table_of('cell_fill_image')['rows'][0][1]['fill'] == {'type': 'image', 'src': 'image1.png', 'mode': 'total'}   # C5.10
    assert table_of('table_pos_VertAlign2')['pos']['valign'] == 'bottom'                # C5.13
    assert table_of('table_pos_HorzRelTo0')['pos']['hrel'] == 'paper'
    assert table_of('table_pos_TextWrap2')['wrap'] == 'behind_text'
    assert [table_of(f'table_pos_TextFlow{k}').get('side') for k in range(4)] == [None, 'left_only', 'right_only', 'largest_only']
    assert table_of('table_caption_right')['caption']['side'] == 'right'
    assert table_of('table_caption_left')['caption']['side'] == 'left'                  # C5.17
    assert table_of('table_caption')['caption']['number'] is True
    assert table_of('cell_protect')['rows'][0][0]['protect'] is True                    # C5.19
    fs = [c for r in table_of('table_formula_sum')['rows'] for c in r if isinstance(c, dict) and 'formula' in c]   # C5.18
    assert fs[0]['formula'] == {'expr': '=SUM(?1:?3)', 'format': '%g,'} and fs[0]['p'] == '60', fs
    assert table_of('table_formula_avg')['rows'][0][0] == '10'
    more = table_of('cell_line_types_more')
    assert {'thickrev3d', '3d', 'rev3d'} <= {line.split()[1] for r in more['rows'] for c in r if isinstance(c, dict)
                                              for line in c.get('border', {}).values() if not line.startswith('none')}
