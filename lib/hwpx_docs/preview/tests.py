"""Self-test of the preview package.

  hd selftest                                  runs run(): lays out small documents (no Hangul, no Edge) and, when Edge is
                                               installed, three corpus pages against Hangul's reference pages
  python -m hwpx_docs.preview.tests fidelity   all reference pages -> table "document ink coarse" (about 3 minutes)
Reference pages: fixtures/ref/<name>_page<N>.png (made by `hd render hwpx <fixture> --backend hangul`, 96 dpi);
fixtures/fidelity.json holds the values of the last full run; the quick test must stay within 4 points of them.
"""
from ..core import tmpdir
import glob
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, '..', '..', '..', 'tests', 'fixtures')      # the shared Hangul-made samples (read only)
QUICK = ('table_form', 'hoeuirok', 'gyehoekseo')


def layout_test():
    """Small documents with no Hangul and no Edge: text, table, shape, picture, header, page number, page break."""
    from ..core import build
    from ..render import img
    from . import render_pages
    tmp = tmpdir.mkdtemp('hwpx_preview_t_')
    img.save_png(os.path.join(tmp, 'p.png'), (4, 4, [bytes([200, 0, 0] * 4)] * 4))
    spec = {'page': {'size': 'A4'}, 'header': ['머리'], 'page_number': {'pos': 'bottom_center', 'side': '-'},
            'body': [{'p': '가나다 ' * 80, 'size': 10, 'align': 'justify'},
                     {'table': {'cols': [40, 60], 'border': '0.2mm solid',
                                'rows': [['a', 'b'], ['c', {'p': 'd', 'fill': '#EEEEEE'}]]}},
                     {'shapes': [{'type': 'rect', 'x': 30, 'y': 200, 'w': 40, 'h': 20, 'fill': '#ABCDEF', 'text': '글상자'}],
                      'p': '도형'},
                     {'pic': {'src': 'p.png', 'w': 20, 'h': 10}},
                     {'p': '끝', 'page_break': True}]}
    out = os.path.join(tmp, 't.hwpx')
    build.write(spec, out, base=tmp)
    pages = render_pages(out)
    assert len(pages) == 2, len(pages)
    p1, p2 = pages[0][2], pages[1][2]
    assert p1.count('<text') > 8 and '#EEEEEE' in p1 and '#ABCDEF' in p1 and '<image' in p1, 'text, table fill, shape, picture'
    assert '머리' in p1 and '머리' in p2 and '-1-' in p1 and '-2-' in p2, 'header and page number on both pages'
    assert '끝' in p2
    xs = [float(v) for m in re.findall(r'<text x="([^"]*)"', p1) for v in m.split()]
    assert max(xs) < 190, max(xs)          # nothing starts right of the text area (190 mm)
    assert max(xs) > 184, max(xs)          # justified lines end at the right margin
    from ..core import read as rd                  # rules P08: Hangul's own space is 0.5 em; useFontSpace: the font's
    from .measure import cwidth
    st = dict(rd.DEF_CHAR, font='함초롬바탕', size=10)
    assert cwidth(' ', st) == 5.0 and abs(cwidth(' ', dict(st, font='함초롬돋움', spacing=-10)) - 4.0) < 1e-9
    assert 2.5 < cwidth(' ', dict(st, font_space=True)) < 3.5                  # GDI 0.3 em (report-markdown)
    assert cwidth('가', dict(st, vcell=True)) == 10.0 and cwidth('.', dict(st, vcell=True)) == 10.0     # 세로쓰기 cells
    print('PREVIEW LAYOUT PASS', len(pages), 'pages')


def drawers_test():
    """preview/drawers: drawers registered at run time draw (a block on the line, a floating block, a raw element);
    an object of an unknown type gets the dashed placeholder and one warning line."""
    import contextlib
    import io
    from ..core import read as rd
    from . import drawers
    from .layout import Ctx, layout_blocks
    from .svg import Page
    seen = []

    def box(item, st):
        seen.append(item)
        return {'w': item['w'], 'h': item['h'], 'base': None,
                'draw': lambda x, y: ['<rect x="%s" y="%s" width="%s" height="%s" fill="#123456"/>' % (x, y, item['w'], item['h'])]}

    def raw(xml, st):
        return {'w': 4, 'h': 4, 'base': 3, 'draw': lambda x, y: ['<circle cx="%s" cy="%s" r="2" fill="#654321"/>' % (x + 2, y + 2)]}
    drawers.register('dummy_box', box)
    drawers.register_inline('hp:dummy', raw)
    log, pg = io.StringIO(), Page(1, 1, {'left': 20, 'top': 20})
    try:
        blocks = [{'dummy_box': {'w': 30, 'h': 10}},
                  {'dummy_box': {'w': 20, 'h': 5, 'inline': False, 'pos': {'x': 50, 'y': 0, 'rel': 'para'}}},
                  {'p': ['글 ', {'xml': '<hp:dummy/>'}, ' ', {'mystery': {'w': 12, 'h': 6}}]}]
        with contextlib.redirect_stdout(log):
            y = 20.0
            for a in layout_blocks(Ctx({}, tmpdir.mkdtemp()), blocks, dict(rd.DEF_CHAR), 170):
                if a.emit:
                    a.emit(20, y, pg)
                y += a.h
    finally:
        drawers.unregister('dummy_box', 'hp:dummy')
    s = ''.join(pg.svg)
    assert s.count('#123456') == 2 and '#654321' in s and len(seen) == 2, 'registered drawers draw (inline, floating, raw)'
    assert '>mystery<' in s and 'PREVIEW NOT DRAWN mystery 12.0 x 6.0 mm on page 1' in log.getvalue(), log.getvalue()
    assert drawers.block('dummy_box') is None and drawers.inline('hp:compose'), 'unregister; built-in drawers load'
    print('PREVIEW DRAWERS PASS')


def hooks_test():
    """drawers.register_paint (a dict fill), register_table_wrap (None = plain table; atoms = drawn by the wrapper) and
    register_page_layer (under and over the body of every page, with the page info)."""
    import contextlib
    import io
    from ..core import build
    from ..core import read as rd
    from . import drawers, render_pages
    from .layout import A, Ctx, layout_blocks
    from .svg import Page

    def gradient(ctx, page, fill, w, h):
        page.svg.append('<defs><linearGradient id="gt1"><stop offset="0" stop-color="%s"/></linearGradient></defs>'
                        % fill['colors'][0])
        return 'url(#gt1)'

    def caption(ctx, b, st, w, layout_table, layout_para):
        if 'caption' not in b['table']:
            return None
        return [A(7.0, lambda x, y, page: page.svg.append('<text>%s</text>' % b['table']['caption']))]
    seen = []

    def under(ctx, page, info):
        seen.append(dict(info, lines=list(page.lines), marks=set(page.marks)))
        return ['<rect id="under" width="1" height="1"/>']

    def hide(xml, st):                       # an inline mark (for example 쪽 감추기): no room, marks its page
        return {'w': 0, 'h': 0, 'base': None, 'draw': None, 'marks': {'hide_header'}}

    def over(ctx, page, info):
        return ['<rect id="over" width="1" height="1"/>']
    drawers._load()            # packages' own painters and wrappers (drawers/table.py ...) must not take part in this test
    saved = (dict(drawers._PAINT), list(drawers._WRAP))
    drawers._PAINT.clear()
    drawers._WRAP.clear()
    drawers.register_paint('gradient', gradient)
    drawers.register_table_wrap(caption)
    drawers.register_page_layer(under, 'under')
    drawers.register_page_layer(over, 'over')
    drawers.register_inline('hp:pageHiding', hide)
    log, pg = io.StringIO(), Page(1, 1, {'left': 20, 'top': 20})
    try:
        t = {'cols': [30, 30], 'rows': [[{'p': 'a', 'fill': {'type': 'gradient', 'colors': ['#ABCDEF', '#FFFFFF']}},
                                         {'p': 'b', 'fill': {'type': 'image', 'color': '#EEEEEE'}}]]}
        blocks = [{'table': t}, {'table': dict(t, caption='표 1. 시험')}]
        with contextlib.redirect_stdout(log):
            ats = layout_blocks(Ctx({}, tmpdir.mkdtemp()), blocks, dict(rd.DEF_CHAR), 170)
            y = 20.0
            for a in ats:
                if a.emit:
                    a.emit(20, y, pg)
                y += a.h
        out = os.path.join(tmpdir.mkdtemp('hwpx_preview_h_'), 'h.hwpx')
        build.write({'body': ['본문', '둘째 줄', {'p': ['둘째 쪽', {'xml': '<hp:pageHiding hideHeader="1"/>'}],
                                                'page_break': True}]}, out)
        pages = render_pages(out)
    finally:
        drawers.unregister_hooks('gradient', caption, under)
        drawers.unregister_hooks(layer=over)
        drawers._PAINT.update(saved[0])
        drawers._WRAP[:] = saved[1]
        drawers.unregister(tag='hp:pageHiding')
    s = ''.join(pg.svg)
    assert 'fill="url(#gt1)"' in s and 'stop-color="#ABCDEF"' in s, 'a registered painter fills the cell'
    assert 'fill="#EEEEEE"' in s and 'PREVIEW NOT DRAWN fill image' in log.getvalue(), 'unknown fill: colour + warning'
    assert s.count('<text>표 1. 시험</text>') == 1 and s.count('url(#gt1)') == 1, 'wrapper draws its table, None = plain path'
    p1 = pages[0][2]
    assert p1.index('id="under"') < p1.index('본문') < p1.index('id="over"') and len(pages) == 2, 'layers under and over'
    assert [i['no'] for i in seen] == [1, 2] and seen[0]['odd'] and not seen[1]['odd'] and seen[0]['first'], seen
    assert seen[0]['size'] == pages[0][:2] and seen[0]['columns']['count'] == 1 and 'left' in seen[0]['margin'], seen[0]
    assert not seen[0]['is_last'] and seen[1]['is_last'] and seen[1]['is_last_doc'] and not seen[0]['is_last_doc'], seen
    a, b = seen[0]['lines']
    assert b[0] > a[0] and a[1] == b[1] == seen[0]['body'][0] and a[2] == 0, seen[0]['lines']     # [baseline y, x, column]
    assert seen[1]['marks'] == {'hide_header'} and not seen[0]['marks'], 'an inline drawer marks its page'
    assert under not in drawers.page_layers('under') and drawers.table_wrap(None, {'table': t}, {}, 1, None, None) is None
    print('PREVIEW HOOKS PASS')


def tabs_test():
    """사용자 탭 (spec `tabs`): decimal, right and auto_right stops, and the leader line before the stop."""
    from ..core import read as rd
    from .layout import Ctx, layout_blocks
    from .svg import Page
    pg = Page(1, 1, {})
    blocks = [{'p': '항목\t1,234.5', 'tabs': [{'pos': 100, 'type': 'decimal', 'leader': 'dot'}]},
              {'p': '왼\t오른', 'tabs': {'stops': [{'pos': 40, 'type': 'right', 'leader': 'solid'}]}},
              {'p': 'a\tb', 'tabs': {'stops': [], 'auto_right': True}}]
    y = 20.0
    for a in layout_blocks(Ctx({}, tmpdir.mkdtemp()), blocks, dict(rd.DEF_CHAR), 170):
        a.emit(20, y, pg)
        y += a.h
    s = '\n'.join(pg.svg)
    runs = {t: [float(v) for v in xs.split()] for xs, t in re.findall(r'<text x="([^"]*)"[^>]*>([^<]*)</text>', s)}
    assert abs(runs['1,234.5'][5] - 120) < 0.05, runs['1,234.5']             # the '.' sits on the stop (20 + 100 mm)
    assert 'stroke-dasharray' in s and s.count('<line ') >= 2, 'dot and solid leaders'
    assert 25 < runs['왼오른'][1] < runs['왼오른'][2] < 60, runs['왼오른']      # '오른' ends at the right stop (20 + 40 mm)
    assert 186 < runs['ab'][1] < 190, runs['ab']                             # auto right stop at the line end (190 mm)
    print('PREVIEW TABS PASS')


def columns_test():
    """단 설정 나누기 (C10.03): one column -> two columns -> one column on the same page, given as the spec block
    `columns_here` and as the raw hp:colPr that the reader keeps; the two columns are made even before the next setting."""
    from .flow import colpr, render_section
    from .layout import Ctx
    raw = '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="2" sameSz="1" sameGap="2268"/></hp:ctrl>'
    assert colpr(raw)['count'] == 2 and abs(colpr(raw)['gap'] - 8.0) < 0.01, colpr(raw)
    text = [{'p': '가나다라 마바사 아자차카 타파하 ' * 3} for _ in range(7)]
    for change in ({'columns_here': {'count': 2, 'gap': 8}, 'p': '둘째 구역'}, {'p': [{'xml': raw}, '둘째 구역']}):
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'body': [{'p': '머리 문단'}, change] + text + [{'columns_here': {'count': 1}, 'p': '끝'}]}, 1)
        assert len(ctx.pages) == 1, len(ctx.pages)
        ls = ctx.pages[0].lines
        two = [l for l in ls[1:-1]]
        left, right = [l for l in two if l[2] == 0], [l for l in two if l[2] == 1]
        assert ls[0][2] == 0 and ls[-1][2] == 0 and ls[0][1] == ls[-1][1] == 20, (ls[0], ls[-1])     # one column
        assert left and right and abs(len(left) - len(right)) <= 1, (len(left), len(right))           # even columns
        assert abs(right[0][1] - (20 + (170 - 8) / 2 + 8)) < 0.01 and right[0][0] == left[0][0] > ls[0][0], right[0]
        assert ls[-1][0] > max(l[0] for l in two), 'the next setting starts under the columns'
    print('PREVIEW COLUMNS PASS')


def vertical_test():
    """세로쓰기 (rules P14): the first letter where Hangul put it in vertical_B / vertical_head_B (line centre 188.2 /
    173.2 mm from the paper left, first letter 45 / 30 mm down), Latin turned in "vertical", the paper not turned."""
    from . import vertical
    from .layout import Ctx
    for head, cx, top in ((False, 188.24, 45.0), (True, 173.24, 30.0)):
        sec = {'text_direction': 'vertical', 'vertical_head': head,
               'page': {'size': 'A4', 'margin': {'left': 30, 'right': 30, 'top': 20, 'bottom': 15, 'header': 15, 'footer': 15}},
               'body': [{'p': '세로 ' + '가나다라마바사 ' * 12}, {'p': 'AB 12'}]}
        ctx = Ctx({}, tmpdir.mkdtemp())
        vertical.render(ctx, sec, 1)
        pg, s = ctx.pages[0], ''.join(ctx.pages[0].svg)
        cells = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"([^>]*)>([^<]*)</text>', s)
        x, y, _, ch = cells[0]
        assert ch == '세' and abs(float(x) - cx) < 0.3 and abs(float(y) - (top + 1.76)) < 0.3, cells[0]
        assert any(c[3] == 'A' and 'rotate(90' in c[2] for c in cells) and pg.g['w'] < pg.g['h'], 'Latin on its side'
        assert len({round(float(c[0])) for c in cells}) >= 3, 'lines stack from the right to the left'
    # vertical_all: Latin upright in full cells; a table stands upright; the header stays horizontal (vt_* samples)
    sec = {'text_direction': 'vertical_all', 'header': ['머리말'],
           'page': {'size': 'A4', 'margin': {'left': 20, 'right': 20, 'top': 20, 'bottom': 15, 'header': 15, 'footer': 15}},
           'body': [{'p': 'AB 가'}, {'table': {'cols': [30, 30], 'border': '0.12mm solid', 'rows': [['가', '나']]}}]}
    ctx = Ctx({}, tmpdir.mkdtemp())
    vertical.render(ctx, sec, 1)
    s = ''.join(ctx.pages[0].svg)
    cells = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"([^>]*)>([^<]*)</text>', s)
    a, b = [c for c in cells if c[3] in 'AB'][:2]
    assert 'rotate' not in a[2] + b[2] and abs(float(b[1]) - float(a[1]) - 3.528) < 0.05, (a, b)
    up = re.search(r'<g data-upright="1">(.*?)</g>', s, re.S).group(1)
    xs = [float(v) for v in re.findall(r'<line x1="([\d.]+)"', up)]
    assert max(xs) - min(xs) > 59, 'the table stands upright: 60 mm wide across the paper'
    assert re.search(r'<text x="[\d. ]+"[^>]*>머리말</text>', s) and ctx.pages[0].g['w'] < ctx.pages[0].g['h'], 'header'
    import contextlib                                            # a floating picture stands upright too (40 x 20 mm)
    import io
    sec['body'] = [{'p': '가'}, {'pic': {'src': 'none.png', 'w': 40, 'h': 20, 'inline': False, 'wrap': 'top_and_bottom',
                                         'pos': {'x': 0, 'y': 0, 'rel': 'para'}}}]
    ctx = Ctx({}, tmpdir.mkdtemp())
    with contextlib.redirect_stdout(io.StringIO()):              # the missing file: a placeholder and a warning line
        vertical.render(ctx, sec, 1)
    up = re.findall(r'<g data-upright="1"><rect x="[\d.]+" y="[\d.]+" width="([\d.]+)" height="([\d.]+)"', ''.join(ctx.pages[0].svg))
    assert up == [('40', '20')], up
    # vertical_head: the header is written down the page at the right (vt2_head_hf: column 186.8-189.7 mm); a table
    # with pos floats upright (vt2_table_para: 97.6-158.0 mm across the paper)
    sec = dict(sec, vertical_head=True, header=['머리말'], text_direction='vertical', body=[{'p': '가'}])
    ctx = Ctx({}, tmpdir.mkdtemp())
    vertical.render(ctx, sec, 1)
    s = ''.join(ctx.pages[0].svg)
    head = [float(x) for x, ch in re.findall(r'<text x="([\d.]+)" y="[\d.]+"[^>]*>([^<]*)</text>', s) if ch == '머']
    assert head and 187 < head[0] < 190, head
    sec = dict(sec, vertical_head=False, body=[{'p': '세로\n쓰기'}, {'table': {
        'cols': [30, 30], 'border': '0.12mm solid', 'rows': [['가', '나']], 'wrap': 'square',
        'pos': {'x': 10, 'y': 20, 'vrel': 'para', 'hrel': 'column'}}}, {'p': '나'}])
    ctx = Ctx({}, tmpdir.mkdtemp())
    vertical.render(ctx, sec, 1)
    s = ''.join(ctx.pages[0].svg)
    up = re.search(r'<g data-upright="1">(.*?)</g>', s, re.S).group(1)
    xs = [float(v) for v in re.findall(r'<line x1="([\d.]+)"', up)]
    assert abs(min(xs) - 97.6) < 0.3 and abs(max(xs) - 158.0) < 0.3, (min(xs), max(xs))
    print('PREVIEW VERTICAL PASS')


def notes_test():
    """주석 모양 (section note_shape, rules P15): number format, prefix/suffix, start number, separator line type /
    colour / length; endnotes after the text of the section."""
    from .flow import render_section
    from .layout import Ctx
    sec = {'note_shape': {'footnote': {'format': 'circled_digit', 'prefix': '[', 'suffix': ']', 'start': 3,
                                       'line': '0.4mm dash #FF0000', 'line_length': 30},
                          'endnote': {'format': 'roman_capital', 'place': 'end_of_section'}},
           'body': [{'p': ['본문', {'footnote': '각주 글'}, ' 그리고', {'endnote': '미주 글'}]}, {'p': '끝 문단'}]}
    ctx = Ctx({}, tmpdir.mkdtemp())
    render_section(ctx, sec, 1)
    s = '\n'.join(ctx.pages[0].svg)
    assert '③' in s and '>[<' in s.replace('>[③', '>[<') or '[③]' in s, 'footnote mark: [③]'
    red = re.search(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)"[^>]*stroke="#FF0000"[^>]*stroke-dasharray', s)
    assert red and abs(float(red.group(3)) - float(red.group(1)) - 30) < 0.01, 'separator: dash, red, 30 mm'
    ys = {t: float(y) for y, t in re.findall(r'<text x="[^"]*" y="([\d.]+)"[^>]*>([^<]*)</text>', s)}
    assert ys['I)'] > ys['끝문단'] and ys['미주글'] > ys['끝문단'] and ys['각주글'] > ys['미주글'], ys    # spaces are not drawn
    page = {'size': 'A4', 'margin': {'left': 20, 'right': 20, 'top': 20, 'bottom': 15, 'header': 15, 'footer': 15}}

    def pages(body, **sec):
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, dict(sec, page=page, body=body), 1)
        return ['\n'.join(p.svg) for p in ctx.pages]

    def seps(s):                                                 # separator lines: (x1, y)
        return [(float(x), float(y)) for x, y in re.findall(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="[\d.]+" y2="\2"', s)]
    # Hangul (nt_room): the row stays when the first line of its note fits; the note goes on at the next page's bottom
    body = [{'p': '줄 %d' % i} for i in range(38)] + [{'p': ['각주 줄', {'footnote': '긴 각주 글 ' * 30}]}, {'p': '뒤'}]
    s = pages(body)
    assert len(s) == 2 and '각주줄' in s[0] and '>뒤<' in s[1] and seps(s[0]) and seps(s[1]), 'the note goes on'
    assert seps(s[0])[0][1] > 255 and s[1].count('긴각주글') >= 1, 'the block at the bottom, the rest on page 2'
    s = pages([{'p': ['가', {'footnote': '하나'}]}, {'p': ['나', {'footnote': '둘'}], 'page_break': True},
               {'p': ['다', {'footnote': '셋'}]}], note_shape={'footnote': {'numbering': 'on_page'}})
    assert re.findall(r'>(\d\))<', s[1]) == ['1)', '2)', '1)', '2)'], 'on_page: numbers start again'
    s = pages([{'p': ['가', {'footnote': '하나'}]}], note_shape={'footnote': {'beneath_text': True}})
    assert seps(s[0])[0][1] < 45, 'beneath_text: the line right under the text'
    two = [{'p': ['왼', {'footnote': '왼쪽'}]}] + [{'p': '줄'}] * 45 + [{'p': ['오른', {'footnote': '오른쪽'}]}]
    got = {pl: [x for x, _ in seps(pages(two, columns={'count': 2, 'gap': 10}, note_shape={'footnote': {'place': pl}})[0])]
           for pl in ('each_column', 'merged_column', 'right_most_column')}
    assert got == {'each_column': [20.0, 109.999], 'merged_column': [20.0], 'right_most_column': [109.999]}, got
    print('PREVIEW NOTES PASS')


def keep_test():
    """Hangul's keep rules in the flow (rules P17 = pagefit PF02): keep_next with the first line (two with widow) of
    the next block, widow at the bottom and at the top of a page, keep_lines, page_break_before. A page holds 41 rows."""
    from .flow import render_section
    from .layout import Ctx
    page = {'size': 'A4', 'margin': {'left': 20, 'right': 20, 'top': 20, 'bottom': 15, 'header': 15, 'footer': 15}}
    fill, long = [{'p': '채움 %d' % i} for i in range(39)], '가나다라마바사 ' * 30          # long: 5 rows

    def rows(body):
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': body}, 1)
        return [len({y for y in re.findall(r'<text x="[^"]*" y="([\d.]+)"', '\n'.join(p.svg))}) for p in ctx.pages]
    assert rows(fill + [{'p': '제목', 'keep_next': True}, {'p': long}]) == [41, 4], 'keep_next: its first line fits'
    assert rows(fill + [{'p': '제목', 'keep_next': True}, {'p': long, 'widow': True}]) == [39, 6], 'two lines needed'
    assert rows(fill + [{'p': '한줄'}, {'p': long, 'widow': True}]) == [40, 5], 'widow: no single line at the bottom'
    assert rows(fill[:37] + [{'p': long, 'widow': True}]) == [40, 2], 'widow: no single line at the top'
    assert rows(fill[:37] + [{'p': long, 'keep_lines': True}]) == [37, 5], 'keep_lines: whole on the next page'
    assert rows(fill[:37] + [{'p': long}]) == [41, 1], 'no rule: the first line that does not fit goes on'
    assert rows(fill[:3] + [{'p': '새 쪽', 'page_break_before': True}]) == [3, 1], 'page_break_before'
    # tables (pagefit PF02): page_break none moves a table that fits on a page; no cut inside merged rows; the header row
    # again on the next page; keep_next toward a table does nothing
    def table(n, **k):
        return {'table': dict({'cols': [40, 60, 60], 'rows': [['열0', '열1', '열2']] + [['가%d' % i, '나', '다'] for i in range(n)],
                               'header_rows': 1, 'border': '0.12mm solid #000000'}, **k)}

    def texts(body):
        """The text of each page, one string per line (runs of a line joined from left to right)."""
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': body}, 1)
        out = []
        for p in ctx.pages:
            rows = {}
            for x, y, t in re.findall(r'<text x="([\d.]+)[^"]*" y="([\d.]+)"[^>]*>([^<]*)<', '\n'.join(p.svg)):
                rows.setdefault(round(float(y), 1), []).append((float(x), t))
            out.append([''.join(t for _, t in sorted(rows[y])) for y in sorted(rows)])
        return out
    assert texts(fill[:30] + [table(14, page_break='none')])[1][0].startswith('열0'), 'page_break none: the whole table on page 2'
    assert texts(fill[:30] + [{'p': '표 앞', 'keep_next': True}, table(14, page_break='none')])[0][-1] == '표앞', \
        'keep_next toward a table does nothing'
    pg = texts([table(70, page_break='table')])
    assert len(pg) >= 2 and pg[1][0].startswith('열0'), 'the header row again on the next page'
    merged = table(0, page_break='table', rows=[['열0', '열1', '열2']] + [[{'p': '병합', 'rs': 4}, '나%d' % i, '다'] if i % 4 == 0
                                                                       else ['나%d' % i, '다'] for i in range(72)])
    pg = texts([{'p': '앞 %d' % i} for i in range(5)] + [merged])
    firsts = [int(re.search(r'나(\d+)', next(t for t in p if '나' in t)).group(1)) for p in pg[1:]]
    assert len(pg) >= 2 and all(n % 4 == 0 for n in firsts), ('a page starts with a merged group', firsts)
    # a row cut inside its cells (rules P18, Hangul kc_* samples): the lines that fit stay, the part is closed by its own
    # edge, the rest goes on under the table's outer margin (1 mm: body top 35 -> 36 mm) or the header row; widow in a cell
    nine = [{'p': '칸' + c} for c in '가나다라마바사아자']
    long9 = {'p': '긴 ' + '가나다라마바사 ' * 27, 'widow': True}                                     # 9 rows at 85 mm

    def kc(n, cell, pre=None, after=(), **k):
        rows_ = [['머리', '머리'], ['위', '위'], [{'blocks': cell}, {'blocks': [{'p': '둘째'}] * 3}], ['아래', '아래']]
        t = dict({'cols': [85, 85], 'rows': rows_, 'heights': [6.64] * 4, 'border': '0.12mm solid #000000'}, **k)
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': (fill[:n] if pre is None else pre) + [{'table': t}] + list(after)}, 1)
        out, hl, kc.svg = [], [], ['\n'.join(p.svg) for p in ctx.pages]
        for s in kc.svg:
            rows = {}
            for x, y, tx in re.findall(r'<text x="([\d.]+)[^"]*" y="([\d.]+)"[^>]*>([^<]*)<', s):
                rows.setdefault(round(float(y), 1), []).append((float(x), tx))
            out.append([''.join(tx for _, tx in sorted(rows[y])) for y in sorted(rows)])
            hl.append(sorted({round(float(a), 1) for a, b in re.findall(r'<line x1="[\d.]+" y1="([\d.]+)" x2="[\d.]+" y2="([\d.]+)"', s)
                              if a == b}))
        return out, hl
    pg, hl = kc(34, nine)
    assert pg[0][-1].startswith('칸라') and pg[1][0].startswith('칸마'), ('four lines stay (kc_cell)', pg)
    assert len(hl[0]) == 4 and hl[1][0] == 36.0, ('part 1 closed, the rest 1 mm under the body top', hl)
    pg, hl = kc(34, nine, header_rows=1)
    assert pg[1][0].startswith('머리') and hl[1][0] == 36.0, ('the header row again before the rest (kc_hdr)', pg[1][:2])
    pg, hl = kc(34, nine, header_rows=1, margin=[1.0, 1.0, 4.5, 1.0])      # a top margin made of the offset: only margin_cont (1 mm) on page 2
    assert hl[1][0] == 36.0, ('the gap above a table that goes on is its margin_cont, at most 1 mm without it', hl[1][:2])
    pg, hl = kc(34, nine, header_rows=1, margin=[1.0, 1.0, 4.5, 1.0], margin_cont=2.0)
    assert hl[1][0] == 37.0, ('margin_cont 2 mm', hl[1][:2])
    pg, hl = kc(34, nine, page_break='table')
    assert not any(r.startswith('칸') for r in pg[0]) and len(hl[0]) == 3 and hl[1][0] == 36.0, ('TABLE: whole rows', hl)
    for widow, k in ((True, 2), (False, 1)):
        pg, _ = kc(30, [dict(long9, widow=widow)])
        assert next(j for j, r in enumerate(pg[1]) if r.startswith('아래')) == k, ('widow at the top of a part (kc_w2)', pg[1])
    pg, _ = kc(37, [long9])
    assert pg[0][-1].startswith('긴'), ('the first paragraph of a cell keeps its one line (kc_w1)', pg[0][-2:])
    pg, _ = kc(36, [{'p': '짧은'}, long9])
    assert not any(r.startswith('긴') for r in pg[0]), ('widow: one line of a later paragraph goes on (kc_mix)', pg[0][-2:])
    two = [{'p': '앞 %d' % i} for i in range(3)] + [{'columns_here': {'count': 2, 'gap': 10}, 'p': '단 바뀜'}] + \
        [{'p': '채움 %d' % i} for i in range(30)]
    kc(0, nine, pre=two, cols=[38, 38])                        # after a column change: cut at the end of column 1 (kc_r2)
    at = {t: float(x) for x, t in re.findall(r'<text x="([\d.]+)[^"]*" y="[\d.]+"[^>]*>(칸[라마])<', kc.svg[0])}
    assert len(kc.svg) == 1 and at['칸라'] < 100 < at['칸마'], ('a region row cut over its columns', at)
    pg, _ = kc(34, nine, after=[{'p': '표 뒤'}], cols=[65, 65], caption={'text': '캡션', 'side': 'left'})
    assert pg[0][-1] == '표뒤' and not any(r.startswith('칸') for r in pg[0]) and any(r.startswith('칸가') for r in pg[1]), \
        ('a side caption: the table whole on the next page, the text goes on (kc_capl)', pg[0][-2:])

    def last_row(cap):                                         # a bottom caption keeps its room on each page (kc_capbt)
        t = {'cols': [65, 65], 'rows': [['줄%d' % i, '칸'] for i in range(60)], 'border': '0.12mm solid #000000',
             'page_break': 'table', **({'caption': {'text': '캡션', 'side': 'bottom'}} if cap else {})}
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': fill[:20] + [{'table': t}]}, 1)
        return len(re.findall(r'>칸<', '\n'.join(ctx.pages[0].svg)))           # rows on page 1
    assert last_row(True) < last_row(False), 'room for the bottom caption'
    for hold in (False, True):                                 # kept whole (kh_none): it waits, the text goes on; with hold
        ctx = Ctx({}, tmpdir.mkdtemp())                         # its paragraph and the heading before it go with it (kh_hold)
        t = {'cols': [60, 60], 'rows': [['열', '열']] + [['행', '칸']] * 12, 'border': '0.12mm solid #000000', 'page_break': 'none'}
        render_section(ctx, {'page': page, 'body': fill[:30] + [{'p': '앞 제목', 'keep_next': True}, {'table': dict(t, hold=hold)},
                                                                {'p': '뒤 문단'}]}, 1)
        on = ['\n'.join(p.svg) for p in ctx.pages]
        assert ('뒤문단' in on[0]) != hold and ('앞제목' in on[0]) != hold and '>행<' in on[1] and '>행<' not in on[0], ('defer', hold)
    for kn, at in ((False, 0), (True, 1)):                     # a heading box with keep_next goes on with its paragraph (PF25)
        ctx = Ctx({}, tmpdir.mkdtemp())
        box = {'table': {'cols': [85, 85], 'rows': [['상자', '나'], ['다', '라']], 'border': '0.4mm solid #000000'}, 'keep_next': kn}
        render_section(ctx, {'page': page, 'body': fill[:39] + [box, {'p': '다음 문단'}]}, 1)
        assert [k for k, p in enumerate(ctx.pages) if '>상자<' in ''.join(p.svg)] == [at], ('keep_next table', kn)
    # after a column change (kp_region_w36): a widow paragraph with one line left at the bottom of column 1 goes on
    unit = '가나다라마바사 ' * 8                                                              # 3 rows at 80 mm
    body = [{'p': '앞 %d' % i} for i in range(3)] + [{'columns_here': {'count': 2, 'gap': 10}, 'p': '단 바뀜'}] + \
        [{'p': '채움 %d' % i} for i in range(36)]
    for widow, first in ((False, 'col1'), (True, 'col2')):
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': body + [{'p': '대상 ' + unit, 'widow': widow}]}, 1)
        x = float(re.search(r'<text x="([\d.]+)[^"]*" y="[\d.]+"[^>]*>대상', '\n'.join(ctx.pages[0].svg)).group(1))
        assert (x < 100) == (first == 'col1'), (widow, x)
    # merged rows with page_break cell: Hangul does not keep a group together, it cuts it between rows or inside one (merged
    # rows, 64 samples; rules P18): a page may start inside a group, the cell that crosses goes on without its text again
    cell_t = table(0, rows=[['열0', '열1', '열2']] + [[{'p': '병합%d' % i, 'rs': 4}, '나%d' % i, '다'] if i % 4 == 0 else ['나%d' % i, '다']
                                                   for i in range(72)])
    pg = texts([{'p': '앞 %d' % i} for i in range(5)] + [cell_t])
    firsts = [int(re.search(r'나(\d+)', next(t for t in p if '나' in t)).group(1)) for p in pg[1:]]
    assert len(pg) >= 2 and any(n % 4 for n in firsts), ('page_break cell: a page starts inside a merged group', firsts)
    assert all(sum(t.count('병합') for t in p) <= 1 + len(p) // 4 for p in pg) and \
        sum(t.count('병합') for p in pg for t in p) == 18, 'the merged text is drawn once, not again on the next page'
    # a table that flows with the text (hwp5 pos.flow): the text of its paragraph first, the table under it, cut at the page end
    flow_t = table(60, pos={'x': 0.0, 'y': 3.0, 'rel': 'para', 'flow': True, 'overlap': False})
    pg = texts([{'table': flow_t['table'], 'same_para': True}, {'p': '표 제목'}])
    assert pg[0][0] == '표제목' and pg[0][1].startswith('열0') and len(pg) >= 2, ('text before the flowing table', pg[0][:3])
    print('PREVIEW KEEP PASS')


def wrap_test():
    """Floating objects and the text around them (rules P16): square wrap beside an object on the left, on both sides of
    a centred one and in the anchor paragraph itself; top_and_bottom on the page moves the text placed before its
    anchor; a table anchored to a paragraph and aligned right; the free ranges of each textFlow side."""
    from .flow import free_ranges, render_section
    from .layout import Ctx
    page = {'size': 'A4', 'margin': {'left': 20, 'right': 20, 'top': 20, 'bottom': 15, 'header': 15, 'footer': 15}}
    rect = {'type': 'rect', 'x': 0, 'y': 0, 'w': 60, 'h': 30, 'rel': 'para', 'wrap': 'square', 'line': '0.12mm solid #000000'}
    text = {'p': '가나다라 ' * 60}

    def rows(body):
        ctx = Ctx({}, tmpdir.mkdtemp())
        render_section(ctx, {'page': page, 'body': body}, 1)
        s = '\n'.join(ctx.pages[0].svg)
        out = {}
        for x, y, t in re.findall(r'<text x="([\d.]+)[^"]*" y="([\d.]+)"[^>]*>([^<]*)</text>', s):
            out.setdefault(round(float(y), 1), []).append(round(float(x), 1))
        return [out[y] for y in sorted(out)], s
    r, _ = rows([{'p': '', 'shapes': [rect]}, text])           # body top 35 mm: the box covers 35-65 mm
    assert r[:5] == [[80.0]] * 5 and r[5] == [20.0], r          # beside the box, then the full width
    r, _ = rows([{'p': '', 'shapes': [dict(rect, w=40, halign='center', hrel='column')]}, text])
    assert r[0] == [20.0, 125.0] and r[5] == [20.0], r          # both sides of the centred box (85-125 mm)
    r, _ = rows([dict(text, shapes=[dict(rect, x=110)])])
    assert len(r) == 8 and all(x == [20.0] for x in r), r       # the anchor paragraph itself: shorter rows, one more
    r, s = rows([{'p': '첫 문단'}, {'p': '', 'shapes': [dict(rect, rel='page', wrap='top_and_bottom', h=20)]}])
    y = float(re.search(r'y="([\d.]+)"[^>]*>첫문단<', s).group(1))
    assert 55 < y < 60, y                                       # below the box at the body top (35-55 mm)
    tbl = {'table': {'cols': [40, 40], 'rows': [['가', '나']], 'border': '0.12mm solid #000000', 'wrap': 'square',
                     'pos': {'x': 0, 'y': 5, 'vrel': 'para', 'hrel': 'column', 'halign': 'right'}}}
    _, s = rows([{'p': '앞'}, tbl])
    xs = [float(a) for a, b in re.findall(r'<line x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)"', s) if a == b]   # vertical lines
    assert abs(max(xs) - 189) < 0.05 and abs(min(xs) - 109) < 0.05, (min(xs), max(xs))     # right edge 1 mm in
    _, s = rows([{'p': '', 'shapes': [rect]}, {'table': {'cols': [50], 'rows': [['표']], 'border': '0.12mm solid #000000'}}])
    ys = [float(v) for v in re.findall(r'<line x1="[\d.]+" y1="([\d.]+)"', s)]
    assert min(ys) > 64.9, ys                                   # a block table goes below the box (35-65 mm)
    from ..core import build, read                               # a table in the paragraph of its text (rules S26)
    from . import render_pages
    d = tmpdir.mkdtemp('hwpx_preview_w_')
    t2 = dict(tbl['table'], pos=dict(tbl['table']['pos'], y=0))
    build.write({'body': [{'p': '앞'}, {'table': t2, 'same_para': True}, {'p': '가나다라 ' * 40}]}, os.path.join(d, 'w.hwpx'))
    sp = read.read(os.path.join(d, 'w.hwpx'), os.path.join(d, 'w.json'))
    assert [sorted(b) for b in sp['body']] == [['p'], ['same_para', 'table'], ['p']], sp['body']
    s = render_pages(os.path.join(d, 'w.hwpx'))[0][2]
    got = sorted((float(y), len(t)) for x, y, t in re.findall(r'<text x="([\d.]+)[^"]*" y="([\d.]+)"[^>]*>([^<]*)</text>', s)
                 if float(x) < 21 and t != '앞')
    first = float(re.search(r'y="([\d.]+)"[^>]*>앞<', s).group(1))
    assert abs(got[0][0] - first - 5.64) < 0.05, (first, got)   # the text right under '앞': no empty anchor line
    assert got[0][1] < 30 and got[2][1] > 40, got               # beside the table (right, 12 mm high), then full rows
    import zipfile                                               # textFlow -> side (tables, rect / ellipse / line)
    build.write({'body': [{'p': '', 'shapes': [rect]}, {'table': t2}]}, os.path.join(d, 'f.hwpx'))
    with zipfile.ZipFile(os.path.join(d, 'f.hwpx')) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['Contents/section0.xml'] = parts['Contents/section0.xml'].replace(b'textFlow="BOTH_SIDES"', b'textFlow="LARGEST_ONLY"')
    with zipfile.ZipFile(os.path.join(d, 'g.hwpx'), 'w') as z:
        for n, v in parts.items():
            z.writestr(n, v)
    sp = read.read(os.path.join(d, 'g.hwpx'), os.path.join(d, 'g.json'))
    assert sp['body'][0]['shapes'][0]['side'] == 'largest_only' and sp['body'][1]['table']['side'] == 'largest_only', sp
    # page-relative, centred both ways in the body area (objects session rect_align_center_b: 85-125 x 141-161 mm)
    _, s = rows([{'p': '앞'}, {'p': '', 'shapes': [dict(rect, rel='page', hrel='page', halign='center', vpos='center',
                                                        h=20, wrap='square')]}])
    box = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="60" height="20"', s)
    assert box and abs(float(box.group(1)) - 75) < 0.05 and abs(float(box.group(2)) - 141) < 0.05, box and box.groups()
    z = [dict(x0=40, x1=60, y0=0, y1=10, wrap='square', side='both_sides', para=None)]
    assert free_ranges(z, 0, 100, 2, 4) == ([(0, 40), (60, 100)], 10)
    assert free_ranges([dict(z[0], side='largest_only', x0=30, x1=50)], 0, 100, 2, 4)[0] == [(50, 100)]
    assert free_ranges([dict(z[0], side='left_only')], 0, 100, 2, 4)[0] == [(0, 40)]
    assert free_ranges([dict(z[0], wrap='top_and_bottom')], 0, 100, 2, 4) == ([], 10)
    assert free_ranges(z, 0, 100, 10, 14) == ([(0.0, 100)], None)
    print('PREVIEW WRAP PASS')


def objects_test():
    """Objects of feature packages (registry DRAWS: a native chart, inline and floating), 글자 겹치기, and a dashed
    placeholder with a warning line for an object the preview cannot draw (never a silent blank)."""
    import contextlib
    import io
    from ..core import build
    from . import render_pages
    cats = ['1분기', '2분기', '3분기']
    ser = [{'name': '가', 'values': [3, 5, 4]}, {'name': '나', 'values': [2, 4, 6], 'type': 'line'}]
    raw = ('<hp:textart id="1" zOrder="0"><hp:sz width="8504" widthRelTo="ABSOLUTE" height="2834" heightRelTo="ABSOLUTE" '
           'protect="0"/></hp:textart>')
    out = os.path.join(tmpdir.mkdtemp('hwpx_preview_c_'), 'c.hwpx')
    build.write({'body': [{'chart': {'native': True, 'type': 'combo', 'w': 120, 'h': 70, 'title': '실적', 'categories': cats,
                                     'series': ser}},
                          {'chart': {'native': True, 'type': 'pie', 'w': 100, 'h': 60, 'categories': cats, 'inline': False,
                                     'pos': {'x': 0, 'y': 0, 'rel': 'para'}, 'series': ser[:1], 'labels': 'percent'}},
                          {'p': ['겹침 ', {'xml': '<hp:compose circleType="SHAPE_CIRCLE" charSz="-3" composeType="OVERLAP" '
                                                  'charPrCnt="0" composeText="12"/>'}, ' 글맵시 ', {'xml': raw}]}]}, out)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        s = render_pages(out)[0][2]
    assert '<polyline' in s and '>실적<' in s and '>1분기<' in s and s.count('<path d="M') == 3 and '25%' in s, 'charts'
    assert '<circle' in s and '>12<' in s, '글자 겹치기'
    assert 'stroke-dasharray="1.5 1"' in s and '>hp:textart<' in s, 'placeholder box with its type name'
    assert 'PREVIEW NOT DRAWN hp:textart 30.0 x 10.0 mm' in log.getvalue(), log.getvalue()
    print('PREVIEW OBJECTS PASS')


def corpus_test():
    """Every shared fixture is laid out with no error (no Hangul needed)."""
    from . import render_pages
    files = sorted(glob.glob(os.path.join(CORPUS, '*.hwpx')))
    bad = [os.path.basename(f) for f in files if not render_pages(f)]
    assert not bad, bad
    print('PREVIEW CORPUS PASS', len(files), 'files')


def fidelity(names=None):
    """Render `names` (default: all reference documents) and return {page: (ink, coarse)} against fixtures/ref."""
    from ..render import img
    from ..render.render import EDGE
    from . import render_files
    if not any(os.path.exists(e) for e in EDGE):
        return None
    keep = json.load(open(os.path.join(HERE, 'fixtures', 'fidelity.json'), encoding='utf-8'))     # page keys <doc>_p<N>
    pages = [(k, k.rsplit('_p', 1)) for k in sorted(keep)]
    docs = names or sorted({doc for _, (doc, _) in pages})
    out = {}
    with tempfile.TemporaryDirectory(prefix='hwpx_preview_f_') as tmp:      # the rendered pages go when it is done
        for d in docs:
            render_files(os.path.join(CORPUS, d + '.hwpx'), tmp)
            for k, (doc, n) in pages:
                if doc == d:    # the reference is named <doc>_page<N>.png: *_p<N>.png is git-ignored (render output)
                    a, o = img.load(os.path.join(HERE, 'fixtures', 'ref', '%s_page%s.png' % (doc, n))), img.load(os.path.join(tmp, k + '.png'))
                    out[k] = (img.compare(a, o), img.compare(a, o, cell=12))
    return out


def fidelity_test():
    res = fidelity(list(QUICK))
    if res is None:
        print('PREVIEW FIDELITY SKIPPED (no Edge)')
        return
    last = json.load(open(os.path.join(HERE, 'fixtures', 'fidelity.json'), encoding='utf-8'))
    for k, (ink, coarse) in res.items():
        assert ink <= last[k]['ink'] + 4 and coarse <= last[k]['coarse'] + 4, (k, ink, coarse, last[k])
    print('PREVIEW FIDELITY PASS', {k: round(v[0], 1) for k, v in res.items()})


def protected_test():
    """A password / distribution document gives one placeholder page, not an error."""
    import tempfile
    from ..core import build, protect
    d = tmpdir.mkdtemp('hwpx_prev_prot_')
    plain, prot = os.path.join(d, 'plain.hwpx'), os.path.join(d, 'prot.hwpx')
    build.write({'body': [{'p': '보호 시험'}]}, plain)
    protect.fake_protected(plain, prot)
    from .flow import render_pages
    pages = render_pages(prot)
    assert len(pages) == 1 and '보호된 문서' in pages[0][2] and pages[0][:2] == (210.0, 297.0), pages
    assert len(render_pages(plain)) == 1 and '보호된 문서' not in render_pages(plain)[0][2]
    print('preview protected placeholder ok')


def run():
    protected_test()
    layout_test()
    drawers_test()
    hooks_test()
    tabs_test()
    columns_test()
    vertical_test()
    notes_test()
    keep_test()
    wrap_test()
    from . import equation
    equation.selftest()
    objects_test()
    corpus_test()
    fidelity_test()


if __name__ == '__main__':
    if sys.argv[1:2] == ['fidelity']:
        res = fidelity()
        for k, (ink, coarse) in sorted(res.items()):
            print('%-30s INK_DIFF %.2f coarse12 %.2f' % (k + '.png', ink, coarse))
        print('mean %.2f coarse12 %.2f' % (sum(v[0] for v in res.values()) / len(res), sum(v[1] for v in res.values()) / len(res)))
    else:
        run()
