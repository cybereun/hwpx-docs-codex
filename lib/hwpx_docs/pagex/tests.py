"""Self-test of pagex (no Hangul): build every feature, parse the XML, read it back, build again, compare."""
from ..core import tmpdir
import json
import os
import zipfile
from xml.dom import minidom

from ..core import build
from ..core.read import read

SPEC = {
    'header_odd': ['홀수쪽 머리말'], 'header_even': ['짝수쪽 머리말'], 'footer_odd': ['홀수쪽 꼬리말'], 'footer_even': ['짝수쪽 꼬리말'],
    'master_pages': [{'type': 'both', 'body': ['바탕쪽 양쪽']}, {'type': 'even', 'body': ['바탕쪽 짝수'], 'front': True},
                     {'type': 'optional', 'page': 3, 'body': ['바탕쪽 3쪽']}],
    'text_direction': 'vertical',
    'line_numbers': {'count_by': 5, 'distance': 5, 'start': 3, 'restart': 1},
    'manuscript': 1,
    'hide_first': {'header': True, 'page_number': True, 'border': 'hide_first'},
    'note_shape': {'footnote': {'format': 'circled_digit', 'prefix': '[', 'suffix': ']', 'line': '0.4mm dash #FF0000',
                                'numbering': 'on_page', 'start': 3, 'between': 2, 'line_length': 30, 'superscript': True},
                   'endnote': {'format': 'roman_capital', 'place': 'end_of_section', 'line_length': 'default'}},
    'body': ['첫 쪽 본문', '둘째 문단',
             {'hide_page': ['header', 'page_number'], 'p': '이 쪽만 감춤'},
             {'columns_here': {'count': 2, 'gap': 6, 'line': '0.12mm solid'}, 'p': '두 단 본문\n둘째 줄'}],
}


def parts(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def run():
    d = tmpdir.mkdtemp('hwpx_docs_pagex_')
    a = os.path.join(d, 'a.hwpx')
    build.write(SPEC, a)
    pa = parts(a)
    for name, data in pa.items():
        if name.endswith('.xml') or name.endswith('.hpf'):
            minidom.parseString(data)                       # every part is well-formed
    s = pa['Contents/section0.xml'].decode('utf-8')
    for want in ('applyPageType="ODD"', 'applyPageType="EVEN"', 'textDirection="VERTICAL"', 'showLineNumber="1"',
                 'restartType="1" countBy="5"', 'wonggojiFormat="1"', 'hideFirstHeader="1"', 'border="HIDE_FIRST"',
                 'masterPageCnt="3"', '<hp:masterPage idRef="masterpage2"/>', '<hp:pageHiding hideHeader="1" hideFooter="0"',
                 'hidePageNum="1"', 'colCount="2"'):
        assert want in s, want
    assert s.count('<hp:header ') == 2 and s.count('<hp:footer ') == 2, 'odd and even, one control each'
    assert s.count('<hp:colPr') == 2, 'the section column and the change inside the page'
    assert 'type="CIRCLED_DIGIT"' in s and 'suffixChar="]"' in s and 'type="ON_PAGE" newNum="3"' in s, 'footnote shape'
    assert 'type="ROMAN_CAPITAL"' in s and 'place="END_OF_SECTION"' in s, 'endnote shape'
    m = pa['Contents/masterpage1.xml'].decode('utf-8')
    assert 'type="EVEN"' in m and 'pageFront="1"' in m and m.startswith('<?xml') and '<masterPage ' in m
    assert 'type="OPTIONAL_PAGE" pageNumber="3"' in pa['Contents/masterpage2.xml'].decode('utf-8')
    hpf = pa['Contents/content.hpf'].decode('utf-8')
    assert hpf.count('Contents/masterpage') == 3 and '<opf:itemref idref="masterpage' not in hpf, 'manifest, not spine'
    # round trip: read -> build -> the same parts
    spec2 = read(a, os.path.join(d, 'a.json'))
    for k in ('header_odd', 'header_even', 'footer_odd', 'footer_even', 'text_direction', 'line_numbers', 'manuscript',
              'hide_first', 'note_shape', 'master_pages'):
        assert k in spec2, f'reader lost {k}'
    assert 'header' not in spec2 and 'footer' not in spec2, 'odd/even headers are not read as `header`'
    assert spec2['note_shape']['endnote'] == {'format': 'roman_capital', 'line_length': 'default', 'place': 'end_of_section'}
    json.dumps(spec2, ensure_ascii=False)
    b = os.path.join(d, 'b.hwpx')
    build.write(spec2, b)
    pb = parts(b)
    for name in ('Contents/section0.xml', 'Contents/masterpage0.xml', 'Contents/masterpage1.xml', 'Contents/masterpage2.xml'):
        assert pa[name] == pb[name].replace(b' />', b'/>'), f'round trip changed {name}'   # raw run items: ElementTree writes " />"
    # a document without pagex keys is unchanged: no master page part, masterPageCnt 0
    c = os.path.join(d, 'c.hwpx')
    build.write({'body': ['가']}, c)
    pc = parts(c)
    assert not any('masterpage' in n for n in pc) and 'masterPageCnt="0"' in pc['Contents/section0.xml'].decode('utf-8')
    # errors
    for bad in ({'body': [{'hide_page': ['nothing'], 'p': 'x'}]}, {'text_direction': 'diagonal', 'body': ['x']}):
        try:
            build.write(bad, os.path.join(d, 'bad.hwpx'))
        except (ValueError, KeyError):
            continue
        raise AssertionError(f'no error for {bad}')
    run_preview()
    run_fixtures()


def run_preview():
    """The preview draws odd/even header and footer, master pages, line numbers and page hiding (drawers/page_layout.py)."""
    from ..preview import flow
    spec = {'header_odd': ['홀수머리'], 'header_even': ['짝수머리'], 'footer_even': ['짝수꼬리'],
            'master_pages': [{'type': 'both', 'body': ['공통바탕']}, {'type': 'even', 'body': ['짝수바탕']},
                             {'type': 'last', 'body': ['마지막바탕']}],
            'line_numbers': {'count_by': 1, 'distance': 5},
            'header': None, 'page_number': {'pos': 'bottom_center'},
            'body': ['가', {'page_break': True}, {'hide_page': ['page_number'], 'p': '나'}, {'page_break': True}, '다']}
    spec.pop('header')
    d = tmpdir.mkdtemp('hwpx_docs_pagex_')
    path = os.path.join(d, 'p.hwpx')
    build.write(spec, path)
    svg = [p[2] for p in flow.render_pages(path)]
    assert len(svg) == 3, len(svg)
    for i, (want, other) in enumerate((('홀수머리', '짝수머리'), ('짝수머리', '홀수머리'), ('홀수머리', '짝수머리'))):
        assert want in svg[i] and other not in svg[i], f'header variant on page {i + 1}'
    assert '공통바탕' in svg[0] and '짝수바탕' not in svg[0] and '짝수바탕' in svg[1] and '공통바탕' not in svg[1], 'master pages'
    assert '마지막바탕' in svg[2] and '공통바탕' not in svg[2], 'the last page master replaces the both master'
    assert '짝수꼬리' in svg[1] and '짝수꼬리' not in svg[0]
    assert '>1</text>' in svg[0] and '>1</text>' in svg[2], 'line number 1 on every page (restart 0)'
    assert svg[1].count('fill="#FFFFFF"') > svg[0].count('fill="#FFFFFF"'), 'page 2 hides its page number (white box)'


def run_fixtures():
    """Every Hangul-made fixture in fixtures/: read -> build -> read gives the same spec (the reader keeps what Hangul wrote)."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
    d = tmpdir.mkdtemp('hwpx_docs_pagex_fx_')
    n = 0
    for name in sorted(os.listdir(here)):
        if not name.endswith('.hwpx'):
            continue
        a = read(os.path.join(here, name), os.path.join(d, 'a.json'))
        build.write(a, os.path.join(d, 'b.hwpx'))
        b = read(os.path.join(d, 'b.hwpx'), os.path.join(d, 'b.json'))
        assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False),             f'fixture {name}: read -> build -> read is not stable'
        n += 1
    assert n, 'no fixtures'
    print(f'  pagex fixtures stable {n}/{n}')
