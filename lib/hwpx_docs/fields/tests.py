"""Self-test of the fields package (no Hangul needed): `hd selftest --only fields`.

Form objects: spec -> HWPX -> spec (same), raw XML kept when the spec cannot hold it, fill by name and by radio group,
`hd form list|fill`, preview drawing (every type draws; a raw element draws). Fixtures of this package
(`fields/fixtures/*.hwpx`, made by Hangul) read -> build -> read to the same spec, when there are any.
"""
from ..core import tmpdir
import glob
import io
import contextlib
import os
import zipfile
from xml.dom import minidom

from ..core import build, read
from . import cli, forms

FORMS = [
    {'type': 'check', 'name': 'agree', 'caption': '동의함', 'checked': True},
    {'type': 'check', 'name': 'later', 'caption': 'later'},
    {'type': 'radio', 'name': 'r1', 'caption': '남', 'group': 'sex'},
    {'type': 'radio', 'name': 'r2', 'caption': '여', 'group': 'sex', 'checked': True},
    {'type': 'combo', 'name': 'city', 'items': ['서울', '부산', {'text': '대구', 'value': 'D'}], 'value': '서울', 'w': 30, 'h': 6},
    {'type': 'edit', 'name': 'who', 'text': '홍길동', 'w': 40, 'h': 6},
    {'type': 'edit', 'name': 'memo', 'text': 'a\nb', 'multiline': True, 'readonly': True, 'align': 'right', 'max': 50},
    {'type': 'list', 'name': 'pick', 'items': ['가', '나', '다'], 'value': '나'},
    {'type': 'button', 'name': 'go', 'caption': '확인', 'fill': '#CCDDEE'},
    {'type': 'scroll', 'name': 'bar'},
]


def _build(spec, name):
    out = os.path.join(tmpdir.mkdtemp('hwpx_docs_f_'), name + '.hwpx')
    build.write(spec, out)
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.xml', '.hpf'))}
    for t in parts.values():
        minidom.parseString(t)
    return out, parts


def _forms_of(path):
    spec = read.read(path, os.path.join(os.path.dirname(path), 'r.json'))
    return [p['form'] for b in spec['body'] if isinstance(b.get('p'), list) for p in b['p'] if isinstance(p, dict) and 'form' in p]


def run():
    forms_test()
    refs_test()
    track_test()


def forms_test():
    spec = {'body': [{'p': ['선택 ', {'form': f}, ' 끝']} for f in FORMS]}
    path, parts = _build(spec, 'forms')
    s = parts['Contents/section0.xml']
    for tag in ('checkBtn', 'radioBtn', 'comboBox', 'edit', 'listBox', 'btn', 'scrollBar'):
        assert f'<hp:{tag} ' in s, tag
    assert 'value="CHECKED"' in s and 'selectedValue="서울"' in s and '<hp:text>홍길동</hp:text>' in s
    back = _forms_of(path)
    assert len(back) == len(FORMS), (len(back), len(FORMS))
    for a, b in zip(FORMS, back):
        assert b == a, ('read back differs', a, b)

    # fill: by name, by radio group (caption selects), combo by text or item value, edit text
    out = os.path.join(os.path.dirname(path), 'filled.hwpx')
    missing = forms.fill_file(path, out, {'later': 'yes', 'agree': 'no', 'sex': '남', 'city': 'D', 'who': 'A & B', 'pick': '다',
                                          'nothere': '1'})
    assert missing == ['nothere'], missing
    got = {f['name']: f for f in _forms_of(out)}
    assert got['later']['checked'] is True and not got['agree'].get('checked')
    assert got['r1'].get('checked') and not got['r2'].get('checked')
    assert got['city']['value'] == '대구' and got['who']['text'] == 'A & B' and got['pick']['value'] == '다'
    assert forms.fill_file(path, out, {'city': '없는 도시'}) == ['city'], 'a value that no item has is refused'
    assert zipfile.ZipFile(out).read('Contents/header.xml') == zipfile.ZipFile(path).read('Contents/header.xml')

    # the command line
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(['list', path]) == 0
        assert cli.main(['fill', path, out, '--set', 'agree=no']) == 0
    assert buf.getvalue().count('FORM ') >= len(FORMS) and 'FORM FILLED 1 of 1' in buf.getvalue(), buf.getvalue()

    # a form object with a child the spec has no key for stays raw OWPML (nothing is lost)
    odd = ('<hp:checkBtn id="1" zOrder="1" numberingType="NONE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
           'dropcapstyle="None" href="" groupLevel="0" instid="2" name="x" caption="c" value="UNCHECKED"><hp:sz width="1000" '
           'widthRelTo="ABSOLUTE" height="1000" heightRelTo="ABSOLUTE" protect="0"/><hp:pos treatAsChar="1"/>'
           '<hp:metaTag>{}</hp:metaTag></hp:checkBtn>')
    assert forms.parse(odd) is None
    raw_path, parts = _build({'body': [{'p': ['a', {'xml': odd}]}]}, 'odd')
    assert odd in parts['Contents/section0.xml']
    item = read.read(raw_path, os.path.join(os.path.dirname(raw_path), 'o.json'))['body'][0]['p'][1]
    assert list(item) == ['xml'] and '<hp:metaTag>{}</hp:metaTag>' in item['xml'], item

    # preview: every type draws; a raw element draws; one the spec cannot hold gets the placeholder
    from ..preview import render_pages
    svg = ''.join(p[2] for p in render_pages(path))
    assert svg.count('<rect') + svg.count('<circle') >= 12 and '동의함' in svg and '홍길동' in svg and 'PREVIEW' not in svg
    svg2 = ''.join(p[2] for p in render_pages(raw_path))
    assert '<hp:checkBtn' not in svg2

    # fixtures made by Hangul: read -> build -> read gives the same body; the form object file holds all ten objects
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'fixtures', '*.hwpx'))):
        first = read.read(f, os.path.join(tmpdir.mkdtemp(), 'f.json'))
        p2, _ = _build(first, 'fx')
        assert read.read(p2, os.path.join(os.path.dirname(p2), 'g.json'))['body'] == first['body'], f
        if os.path.basename(f) == 'form_objects.hwpx':
            assert len(_forms_of(f)) == 10 and _forms_of(f) == _forms_of(p2), 'Hangul-saved form objects read as spec'
    print('SELFTEST fields forms PASS')


def refs_test():
    """Cross-reference and index mark (run items), generated 차례 and 색인 with page numbers from the preview renderer."""
    body = [{'toc': {'levels': 2}}]
    for ch in (1, 2, 3):
        body += [{'p': f'제{ch}장', 'outline_level': 0, 'page_break': ch > 1},
                 {'p': ['글 ', {'index_mark': {'first': '사과', 'second': '파이'}}, '본문']},
                 {'p': f'{ch}.1 절', 'outline_level': 1},
                 {'p': ['보기 ', {'xref': {'target': 'mark1'}}, ' 참조']}]
    body.append({'index': {}})
    path, parts = _build({'body': body}, 'refs')
    s = parts['Contents/section0.xml']
    assert s.count('type="CROSSREF"') == 3 and s.count('<hp:fieldEnd') == 3 and 'name="RefPath">mark1;<' in s
    assert s.count('<hp:indexmark><hp:firstKey>사과</hp:firstKey><hp:secondKey>파이</hp:secondKey>') == 3
    text = ''.join(p[2] for p in __import__('hwpx_docs.preview', fromlist=['x']).render_pages(path))
    import re
    flat = re.sub(r'\s+', '', re.sub(r'<[^>]+>', ' ', text))
    assert flat.count('제1장') == 2 and flat.count('(사)') == 1, 'list entries and the list itself'
    back = read.read(path, os.path.join(os.path.dirname(path), 'r.json'))
    assert sum('xml' in r and 'CROSSREF' in r['xml'] for b in back['body'] if isinstance(b.get('p'), list)
               for r in b['p'] if isinstance(r, dict)) >= 3, 'cross-reference stays raw OWPML (no loss)'
    print('SELFTEST fields refs PASS')


def track_test():
    """Track changes: insert, delete, format -> header records + body marks -> same spec; two authors; the preview draws them."""
    body = [{'p': [{'change': {'type': 'delete', 't': '옛', 'author': 'A', 'date': '2026-01-02T03:04:05Z'}}, '글 ',
                   {'change': {'type': 'format', 't': '굵게', 'author': 'B'}, 'bold': True}, ' 끝']},
            {'p': [{'change': {'type': 'insert', 't': '새 문단', 'author': 'A', 'paraend': True}}]}]
    path, parts = _build({'body': body}, 'track')
    s, h = parts['Contents/section0.xml'], parts['Contents/header.xml']
    assert '<hp:deleteBegin Id="1" TcId="1"/>옛<hp:deleteEnd Id="1" TcId="1" paraend="0"/>' in s and 'charTcId="2"' in s
    assert 'paraend="1"' in s and h.count('<hh:trackChange ') == 3 and 'type="CharShape"' in h and 'charshapeID=' in h
    assert '<hh:trackChangeAuthors itemCnt="2">' in h and 'name="A" mark="1" id="1"' in h and 'trackchageConfig flags="57"' in h
    back = read.read(path, os.path.join(os.path.dirname(path), 't.json'))['body']
    got = [r['change'] for b in back for r in b['p'] if isinstance(r, dict) and 'change' in r]
    assert [(c['type'], c['t'], c['author']) for c in got] == [('delete', '옛', 'A'), ('format', '굵게', 'B'), ('insert', '새 문단', 'A')]
    assert got[0]['date'] == '2026-01-02T03:04:05Z' and got[2].get('paraend') is True, got
    from ..preview import render_pages
    import re
    svg = ''.join(p[2] for p in render_pages(path))
    assert re.sub(r'<[^>]+>', '', svg).replace(' ', '').count('옛') == 1 and '#FF0000' in svg
    assert 'trackChange ' not in _build({'body': [{'p': 'x'}]}, 'p2')[1]['Contents/header.xml']
    print('SELFTEST fields track PASS')
