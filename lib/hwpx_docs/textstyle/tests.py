"""Self-test of the textstyle package (no Hangul needed): `hd selftest --only textstyle`.

Tab stops and named styles build to a header that parses, and read back to the same spec (build -> read -> build -> read).
Every fixture of this package under tests/fixtures reads -> builds -> reads to the same spec.
"""
from ..core import tmpdir
import glob
import os
import re
import zipfile
from xml.dom import minidom

from ..core import build, read

FIXTURES = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tests', 'fixtures'))
PREFIXES = ('tab_', 'tabs_custom', 'style_', 'styles_', 'dropcap_', 'dutmal_', 'picbullet_', 'hanja_', 'latin_break', 'para_break_latin')


def _build(spec, base='.'):
    out = os.path.join(tmpdir.mkdtemp('hwpx_docs_ts_'), 't.hwpx')
    build.write(spec, out, base)
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith('.xml')}
    for t in parts.values():
        minidom.parseString(t)
    return out, parts


def _again(path):
    d = tmpdir.mkdtemp('hwpx_docs_ts_a_')          # pictures that the reader saves land here, not next to the fixture
    first = read.read(path, os.path.join(d, 'a.json'))
    out, _ = _build(first, d)
    return first, read.read(out, os.path.join(d, 'b.json'))


def run():
    stops = [{'pos': 40, 'type': 'left', 'leader': 'dot'}, {'pos': 100, 'type': 'right', 'leader': 'solid'},
             {'pos': 130, 'type': 'decimal', 'leader': 'none'}]
    path, parts = _build({'body': [{'p': 'a\tb\t1.5', 'tabs': stops},
                                   {'p': 'x\ty', 'tabs': {'stops': stops[:1], 'auto_right': True}}, 'plain']})
    h = parts['Contents/header.xml']
    assert h.count('<hh:tabItem ') == 2 * (3 + 1), h.count('<hh:tabItem ')        # each stop twice (case and default)
    assert 'unit="HWPUNIT"' in h and 'autoTabRight="1"' in h and 'leader="DOT"' in h and 'type="DECIMAL"' in h
    first, second = _again(path)
    got = first['body'][0]['tabs']
    assert [t['type'] for t in got] == ['left', 'right', 'decimal'] and abs(got[0]['pos'] - 40) < 0.01, got
    assert first['body'][1]['tabs']['auto_right'] and 'tabs' not in first['body'][2] and first == second, first

    # a Hangul file with unit CHAR (1/5 HWPUNIT of real position, measured): 2834 -> 50 mm
    d = os.path.dirname(path)
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(os.path.join(d, 'c.hwpx'), 'w') as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == 'Contents/header.xml':
                data = re.sub(r'<hh:tabItem pos="\d+" type="LEFT" leader="DOT" unit="HWPUNIT"/>',
                              '<hh:tabItem pos="2834" type="LEFT" leader="DOT" unit="CHAR"/>', data.decode()).encode()
            zo.writestr(it, data)
    assert abs(read.read(os.path.join(d, 'c.hwpx'), os.path.join(d, 'c.json'))['body'][0]['tabs'][0]['pos'] - 50) < 0.05

    named = {'본문 가': {'size': 11, 'line': 170, 'left': 5, 'eng': 'Mybody', 'next': '본문 가'},
             '강조': {'type': 'char', 'bold': True, 'color': '#C00000'},
             '제목 나': {'size': 16, 'bold': True, 'align': 'center', 'next': '본문 가'}}
    path, parts = _build({'named_styles': named, 'body': [
        {'style': '본문 가', 'p': ['가나 ', {'t': '강조', 'style': '강조'}, ' 다']}, {'style': '개요 1', 'p': 'o'},
        {'style': '제목 나', 'p': 't'}, 'plain']})
    h, s = parts['Contents/header.xml'], parts['Contents/section0.xml']
    assert '<hh:styles itemCnt="26"' in h and re.findall(r'<hh:style id="2[3-5]" type="(\w+)" name="([^"]+)"', h) == [
        ('PARA', '본문 가'), ('CHAR', '강조'), ('PARA', '제목 나')], re.findall(r'<hh:style id="2[3-5]"[^>]*>', h)
    assert re.findall(r'styleIDRef="(\d+)"', s) == ['23', '2', '25', '0']
    first, second = _again(path)
    assert 'next' not in first['named_styles']['본문 가'] and first['named_styles']['강조']['type'] == 'char'
    assert first['named_styles']['제목 나']['next'] == '본문 가' and first == second, first
    try:
        _build({'body': [{'style': 'no such', 'p': 'x'}]})
        raise AssertionError('an unknown style must stop')
    except ValueError:
        pass

    # drop cap and 덧말: built, read as run items, built again, equal
    path, parts = _build({'body': [{'dropcap': {'lines': 3, 'frame': '0.4mm solid #FF0000', 'fill': '#FFFF00'}, 'p': '가나다라마바사'},
                                   {'p': ['앞 ', {'dutmal': {'main': '본말', 'sub': '덧말', 'pos': 'bottom', 'size': 60}}, ' 뒤']}]})
    s = parts['Contents/section0.xml']
    assert 'dropcapstyle="TripleLine"' in s and '<hp:t>가</hp:t>' in s and '나다라마바사' in s and 'posType="BOTTOM" szRatio="60"' in s
    first, second = _again(path)
    assert first['body'][0]['p'][0]['dropcap']['lines'] == 3 and first['body'][1]['p'][1]['dutmal']['pos'] == 'bottom' and first == second, first
    dut = ('<hp:dutmal posType="TOP" szRatio="50" option="0" styleIDRef="0" align="CENTER">'
           '<hp:mainText>본말</hp:mainText><hp:subText>덧말</hp:subText></hp:dutmal>')       # drawn by preview/drawers/dutmal.py
    try:
        from .. import preview
    except ImportError:
        preview = None
    if preview:
        for body in ([{'p': ['앞 ', {'xml': dut}, ' 뒤']}], [{'p': ['앞 ', {'dutmal': {'main': '본말', 'sub': '덧말'}}, ' 뒤']}]):
            path, _ = _build({'body': body})
            svg = preview.render_pages(path)[0][2]
            assert 'PREVIEW NOT DRAWN' not in svg and '덧말' in svg and svg.count('font-size="1.764"') == 1
        from .samples import _png
        d = tmpdir.mkdtemp('hwpx_docs_ts_b_')            # picture bullet: the image is drawn, the character is not
        open(os.path.join(d, 'b.png'), 'wb').write(_png(8, 8))
        path, _ = _build({'body': [{'bullet_image': 'b.png', 'bullet': '●', 'indent': -12, 'left': 12, 'p': '그림 글머리표'}]}, d)
        svg = preview.render_pages(path)[0][2]
        assert svg.count('<image ') == 1 and '●' not in svg and 'PREVIEW NOT DRAWN' not in svg
        path, _ = _build({'body': [{'dropcap': {'lines': 2}, 'p': '문단 첫 글자'}]})
        svg = preview.render_pages(path)[0][2]
        assert 'PREVIEW NOT DRAWN' not in svg and 'font-size="9.' in svg

    for f in sorted(glob.glob(os.path.join(FIXTURES, '*.hwpx'))):
        if os.path.basename(f).startswith(PREFIXES):
            first, second = _again(f)
            assert first == second, os.path.basename(f)
    from . import privacy_test
    privacy_test.run()
    print('SELFTEST textstyle: tabs, named styles, fixtures OK')
