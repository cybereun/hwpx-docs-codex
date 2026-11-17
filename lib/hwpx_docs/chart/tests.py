"""Self-test of the chart package (no Hangul needed): `hd selftest --only chart`.

Every chart kind builds to a part that parses and reads back to the same spec; a chart that cannot be drawn natively
falls back to drawing objects. The fixtures folder: every file reads -> builds -> reads to the same spec.
"""
from ..core import tmpdir
import glob
import json
import os
import zipfile
from xml.dom import minidom

from ..core import build, read
from . import ooxml


def _build(spec, name):
    out = os.path.join(tmpdir.mkdtemp('hwpx_docs_c_'), name + '.hwpx')
    build.write(spec, out)
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.xml', '.hpf'))}
    for t in parts.values():
        minidom.parseString(t)
    return out, parts


def run():
    ooxml.selftest()
    cats, ser = ['가', '나'], [{'name': 'a', 'values': [3, 5]}, {'name': 'b', 'values': [2, 4], 'type': 'line'}]
    for kind in ('bar', 'hbar', 'line', 'pie', 'combo'):
        c = {'native': True, 'type': kind, 'w': 100, 'h': 60, 'categories': cats, 'series': ser, 'title': 'T'}
        path, parts = _build({'body': [{'chart': c}]}, 'chart_' + kind)
        s = parts['Contents/section0.xml']
        assert 'chartIDRef="Chart/chart1.xml"' in s and 'ooxmlchart' in s and '<hp:ole' not in s, kind
        assert 'c:chartSpace' in parts['Chart/chart1.xml'], kind
        back = read.read(path, os.path.join(os.path.dirname(path), 'c.json'))['body'][0]['chart']
        assert back['type'] == kind and back['native'] and back['categories'] == cats and 'ooxml' not in back, (kind, back)
        assert back['series'][0]['values'] == [3, 5] and back['title'] == 'T', back
    # area, scatter, secondary axis: the whole path spec -> HWPX -> spec (Hangul render of these: coverage.md, "open")
    for name, extra in (('area', {'type': 'area'}), ('scatter', {'type': 'scatter', 'categories': [1, 2.5], 'lines': True}),
                        ('secondary', {'type': 'combo', 'y2_title': '%',
                                       'series': [ser[0], dict(ser[1], axis='secondary')]})):
        c = dict({'native': True, 'w': 100, 'h': 60, 'categories': cats, 'series': ser}, **extra)
        path, parts = _build({'body': [{'chart': c}]}, 'chart_' + name)
        back = read.read(path, os.path.join(os.path.dirname(path), 'c.json'))['body'][0]['chart']
        assert 'ooxml' not in back and back['type'] == c['type'] and back['categories'] == c['categories'], (name, back)
        assert [s.get('axis') for s in back['series']] == [s.get('axis') for s in c['series']], (name, back)
    two = {'native': True, 'type': 'bar', 'categories': cats, 'series': ser[:1]}
    _, parts = _build({'body': [{'chart': two}, 'text', {'chart': dict(two, type='line')}]}, 'chart_two')
    assert 'Chart/chart2.xml' in parts, 'two charts, two parts'
    _, parts = _build({'body': [{'chart': {'native': True, 'type': 'radar', 'categories': cats, 'series': ser[:1]}}]}, 'chart_fb')
    assert 'Chart/chart1.xml' not in parts and '<hp:rect' in parts['Contents/section0.xml'], 'fallback draws shapes'
    _, parts = _build({'body': [{'chart': {'type': 'bar', 'categories': cats, 'series': ser[:1]}}]}, 'chart_shapes')
    assert 'Chart/chart1.xml' not in parts, 'a chart without native stays a drawing'
    draw_test(cats, ser)
    fixtures()


def draw_test(cats, ser):
    """The chart as a viewer draws it (DRAWS['chart'])."""
    from . import draw
    c = {'native': True, 'type': 'combo', 'w': 120, 'h': 70, 'title': '실적', 'categories': cats, 'series': ser}
    s = ''.join(draw.svg(c, 10, 20))
    assert s.count('stroke="#868686"') > 8 and draw.PALETTE[0] in s and '<polyline' in s and '>실적<' in s, 'combo'
    pie = ''.join(draw.svg(dict(c, type='pie', labels='percent', series=[{'name': 'a', 'values': [1, 3]}]), 0, 0))
    assert pie.count('<path d="M') == 2 and '25%' in pie and '75%' in pie, 'pie slices and percent labels'
    view = draw.svg({'native': True, 'w': 100, 'h': 60, 'ooxml': '<x/>', 'view': dict(c, type='hbar', title='')}, 0, 0)
    assert '>차트 제목<' in ''.join(view), 'a part kept whole is drawn from its view'
    assert draw.svg({'native': True, 'w': 100, 'h': 60, 'ooxml': '<x/>'}, 0, 0) is None, 'nothing to draw it from'
    assert draw.svg({'type': 'bar', 'w': 100, 'h': 60}, 0, 0) is None, 'not native'
    # area, scatter, secondary axis (layout numbers assumed, not measured on Hangul pages: coverage.md)
    cs = {'native': True, 'w': 100, 'h': 60, 'categories': ['a', 'b', 'c'], 'legend': False}
    ar = ''.join(draw.svg(dict(cs, type='area', series=[{'name': 'a', 'values': [1, 3, 2]}]), 0, 0))
    assert '<polygon' in ar and draw.PALETTE[0] in ar, 'area'
    sc = ''.join(draw.svg(dict(cs, type='scatter', categories=[1, 2, 3], lines=True, series=[{'name': 'a', 'values': [1, 3, 2]}]), 0, 0))
    assert sc.count('<circle') == 3 and '<polyline' in sc, 'scatter'
    two = dict(cs, type='combo', y2_title='%', series=[{'name': 'a', 'values': [1, 3, 2], 'type': 'bar'},
                                                       {'name': 'b', 'values': [10, 30, 20], 'type': 'line', 'axis': 'secondary'}])
    se = ''.join(draw.svg(two, 0, 0))
    assert '>40<' in se and '>%<' in se, 'secondary axis labels (0, 20, 40) and title'
    assert draw.scale(0, 5, 39.15)[1:] == (6, 2) and draw.scale(0, 5, 75.4)[1:] == (6, 1), 'Hangul axis steps'
    assert draw.scale(0, 5, 88.7, min_mm=10.0)[1:] == (6, 1) and draw.scale(0, 9.9, 88.7, min_mm=10.0)[1:] == (12, 2) \
        and draw.scale(0, 12.3, 88.7, min_mm=10.0)[1:] == (14, 2), 'horizontal bars (the default chart): 0-6 by 1, 0-12 by 2, 0-14 by 2'
    assert draw.scale(0, 6, 43.1)[1:] == (8, 2) and draw.scale(0, 5, 43.1)[1:] == (6, 1) and draw.scale(0, 60, 43.1)[1:] == (80, 20), \
        'Hangul axis steps of the area / scatter / secondary-axis charts (chart_area.hwpx ...)'


def fixtures():
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', '*.hwpx')))
    assert files, 'no chart fixtures'
    tmp = tmpdir.mkdtemp('hwpx_docs_cf_')
    bad = []
    for f in files:
        n = os.path.splitext(os.path.basename(f))[0]
        a = read.read(f, os.path.join(tmp, n + '.a.json'))
        build.write(a, os.path.join(tmp, n + '.hwpx'), base=tmp)
        b = read.read(os.path.join(tmp, n + '.hwpx'), os.path.join(tmp, n + '.b.json'))
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            bad.append(n)
    assert not bad, f'{len(bad)} of {len(files)} chart fixtures not stable: {bad[:8]}'
    # a part kept whole (`ooxml`, Hangul's default chart) still gives its data to viewers as `view`
    d = read.read(os.path.join(os.path.dirname(files[0]), 'chart_default.hwpx'), os.path.join(tmp, 'd.json'))
    c = next(b['chart'] for b in d['body'] if isinstance(b, dict) and 'chart' in b)
    assert 'ooxml' in c and c['view']['type'] == 'hbar' and len(c['view']['series']) == 3, c.get('view')
    print(f'  chart fixtures stable {len(files)}/{len(files)}')
