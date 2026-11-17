"""Self-test of the pagefit package (no Hangul needed): `hd selftest --only pagefit`.

1. The paginator: forced break, keep_next, keep_lines, widow, on synthetic atoms.
2. A plan with chapters and forced page breaks: with the keep rules off the model has the page count of the preview; check finds
   empty pages and a heading alone; fix makes the check pass, changes no text size and only the keys it is allowed to set.
3. A table cut after its header row and a short last page are found, and fix deals with them.
5. Reading units, long tables, references, footnote continuation, merged rows: tests_units.py.
4. Columns, footnotes and floating objects: the pages come from the preview's flow (registry backend `pagereport`); check and fix work.
"""
from ..core import tmpdir
import copy
import os

from ..core import build
from . import check, fix, model

LINE = 5.0                                       # mm per line of the synthetic atoms


def _atoms(n, keep=False, line=True, h=LINE, trail=0.0):
    out = [{'h': h, 'trail': 0.0, 'keep': False, 'line': line} for _ in range(n)]
    out[0]['keep'] = keep
    out[-1]['trail'] = trail
    return out


def _sec(blocks, y1=100.0):
    return {'index': 0, 'geom': {'y0': 0.0, 'y1': y1}, 'columns': 1,
            'blocks': [{'index': i, 'block': b, 'floating': False, 'region': False, 'atoms': a} for i, (b, a) in enumerate(blocks)]}


def paginator():
    # 20 lines fit (100 mm of 5 mm lines)
    base = [({}, _atoms(16)), ({}, _atoms(5))]
    pgs = model.paginate(_sec(base))
    assert [p.items for p in pgs] == [[(0, 0, 16), (1, 0, 4)], [(1, 4, 5)]], [p.items for p in pgs]
    pgs = model.paginate(_sec([({}, _atoms(17)), ({'widow': True}, _atoms(4))]))
    assert pgs[0].items[-1] == (1, 0, 2) and pgs[1].items == [(1, 2, 4)], [p.items for p in pgs]       # 2 + 2, not 3 + 1
    pgs = model.paginate(_sec([({}, _atoms(19)), ({'widow': True}, _atoms(3))]))
    assert pgs[0].items == [(0, 0, 19)] and pgs[1].items == [(1, 0, 3)], [p.items for p in pgs]        # 1 line would be alone: all moves
    pgs = model.paginate(_sec([({}, _atoms(19)), ({}, _atoms(3))]))
    assert pgs[0].items[-1] == (1, 0, 1) and pgs[1].items == [(1, 1, 3)], 'no rule: the single line stays'
    pgs = model.paginate(_sec([({}, _atoms(17)), ({'keep_lines': True}, _atoms(6))]))
    assert pgs[1].items == [(1, 0, 6)] and pgs[1].why == 'keep_lines'
    pgs = model.paginate(_sec([({}, _atoms(19)), ({'keep_next': True}, _atoms(1)), ({}, _atoms(3))]))
    assert pgs[1].items[0] == (1, 0, 1) and pgs[1].why == 'keep_next', [p.items for p in pgs]
    pgs = model.paginate(_sec([({}, _atoms(3)), ({}, _atoms(2, keep='break'))]))
    assert len(pgs) == 2 and pgs[1].why == 'forced_break'


def _plan(chapters=(14, 6, 11, 3), sub=True):
    def para(n, k):
        return '이 문단은 계획서의 본문입니다. 사업의 배경과 목적, 추진 방법과 기대 효과를 차례로 설명합니다. ' * k + f'({n})'
    body = []
    for ch, n in enumerate(chapters, 1):
        body.append({'p': f'{ch}. 장 제목 {ch}', 'bold': True, 'size': 16, 'after': 8, 'page_break': ch > 1})
        body += [{'p': para(f'{ch}-{i + 1}', 2 + i % 3), 'after': 6} for i in range(n)]
        if ch == 2 and sub:
            body.append({'p': '2.1 소제목', 'bold': True, 'size': 13, 'after': 4})
    return {'body': body}


def _write(spec):
    out = os.path.join(tmpdir.mkdtemp('hwpx_docs_pf_'), 't.hwpx')
    build.write(spec, out)
    return out


def _sizes(spec):
    return [b.get('size') for b in spec['body']]


def plan():
    spec = _plan()
    from .. import preview
    assert len(model.pages(spec)) == len(preview.render_pages(_write(spec))), 'keep rules off: the preview page count'
    found, pgs = check.check(spec)
    kinds = [f.kind for f in found]
    assert kinds.count('empty') >= 2 and 'heading' in kinds and len(pgs) >= 5, [str(f) for f in found]
    assert all(pgs[f.page].why == 'forced_break' for f in found if f.kind == 'empty'), 'each empty page ends at a forced break'
    work, sizes = copy.deepcopy(spec), _sizes(spec)
    log = fix.fix(work)
    found, pgs = check.check(work)
    assert not found and len(pgs) < len(model.pages(spec)) and log, ([str(f) for f in found], log)
    assert all(p.fill >= 0.85 for p in pgs[:-1]) and _sizes(work) == sizes, 'no text size change'
    allowed = {'keep_next', 'keep_lines', 'widow', 'page_break', 'page_break_before', 'after'}
    for a, b in zip(spec['body'], work['body']):
        assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} <= allowed, (a, b)
    assert any(f.kind == 'empty' for f in check.check(spec, fill=85)[0]) and not check.check(work)[0], 'before and after'
    # a fill that cannot be reached (spacing is limited) leaves a finding instead of a stretched page
    work = _plan((2, 1, 1, 1), sub=False)
    fix.fix(work, max_extra=0.0)
    assert any(f.kind == 'empty' for f in check.check(work)[0]) or len(model.pages(work)) == 1


def _table(rows):
    return {'table': {'cols': [40, 60, 60], 'rows': [[f'열{c}' for c in range(3)]] + [[f'가{r}', f'나{r}', f'다{r}'] for r in range(rows)],
                      'header_rows': 1, 'repeat_header': True, 'border': '0.4mm solid #000000'}}


def table_and_last():
    base = {'p': '본문 줄입니다. ' * 12, 'after': 6}
    for n in range(3, 40):
        spec = {'body': [dict(base) for _ in range(n)] + [_table(30)]}
        if any(f.kind == 'table' for f in check.check(spec)[0]):
            break
    else:
        raise AssertionError('no table cut after its header row found')
    fix.fix(spec)
    assert not any(f.kind == 'table' for f in check.check(spec)[0])
    for n in range(8, 60):
        spec = {'body': [{'p': '본문 줄입니다. ' * 10, 'after': 6} for _ in range(n)]}
        found, pgs = check.check(spec, last_lines=3)
        if any(f.kind == 'last' for f in found) and len(pgs) > 1:
            before = len(pgs)
            fix.fix(spec, last_lines=3)
            now = len(model.pages(spec))
            assert now <= before
            if now < before:
                return
    raise AssertionError('no short last page that fix pulls back')


def flow():
    """Columns, footnotes and floating objects: the pages come from the preview's own flow; check and fix work on them."""
    assert not model.uses_flow(_plan()) and model.uses_flow({'columns': {'count': 2}, 'body': []})
    assert model.uses_flow({'body': [{'p': ['a', {'footnote': 'n'}]}]}) and model.uses_flow({'body': [{'p': 'a', 'shapes': [{}]}]})
    assert model.uses_flow({'body': [{'pic': {'src': 'x.png', 'inline': False}}]})
    makers = {
        'columns': lambda: dict(_plan(), columns={'count': 2, 'gap': 8}),
        'footnotes': lambda: {'body': [dict(b, p=[b['p'], {'footnote': '각주 내용입니다.'}]) if i % 3 == 0 and 'page_break' not in b else b
                                       for i, b in enumerate(_plan()['body'])]},
        'objects': lambda: {'body': [dict(b, shapes=[{'type': 'rect', 'x': 120, 'y': 0, 'w': 45, 'h': 30, 'rel': 'para',
                                                      'wrap': 'square', 'fill': '#DDDDDD'}]) if i % 5 == 0 and 'page_break' not in b else b
                                     for i, b in enumerate(_plan()['body'])]}}
    for name, make in makers.items():
        spec = make()
        found, pgs = check.check(spec)
        assert pgs[0].renderer and any(f.kind == 'empty' for f in found), (name, [str(f) for f in found])
        before = len(pgs)
        work = copy.deepcopy(spec)
        fix.fix(work)
        found, pgs = check.check(work)
        # a footnote page differs a little between the preview and Hangul at the page bottom: no `empty` page is what the test asks for
        assert not any(f.kind == 'empty' for f in found) and len(pgs) < before and all(p.fill >= 0.85 for p in pgs[:-1]),             (name, [str(f) for f in found], len(pgs))
        assert _sizes(work) == _sizes(spec) or name != 'columns'


def order_and_head():
    """PF26: a table kept whole that does not fit waits for the next page while the text after it moves up (Hangul kh_none): check
    reports `order`, the readable fix gives the table `hold`. PF27: a table over pages repeats its bold first row."""
    fill = [{'p': '채움 %d' % i} for i in range(30)]
    tbl = {'table': {'cols': [60, 60], 'rows': [['열 1', '열 2']] + [['가 %d' % i, '나'] for i in range(12)],
                     'border': '0.12mm solid #000000', 'page_break': 'none'}}
    spec = {'body': fill + [{'p': '□ 앞 제목', 'keep_next': True}, tbl, {'p': '□ 뒤 제목', 'keep_next': True}, {'p': '뒤 문단'}]}
    assert any(f.kind == 'order' for f in check.check(spec, profile='readable')[0]), 'order not found'
    work = copy.deepcopy(spec)
    whole = {'extends': 'readable', 'fix': {'tables': {'split_gap_mm': 0}}}             # the table stays whole (not cut instead)
    fix.fix(work, profile=whole)
    assert work['body'][31]['table'].get('hold') and not any(f.kind == 'order' for f in check.check(work, profile=whole)[0])
    long = {'table': {'cols': [60, 60], 'page_break': 'table', 'border': '0.12mm solid #000000',
                      'rows': [[{'p': '열 1', 'bold': True}, {'p': '열 2', 'bold': True}]] + [['가 %d' % i, '나'] for i in range(40)]}}
    spec = {'body': fill[:20] + [long, {'p': '뒤 문단'}]}
    assert any(f.kind == 'table_head' for f in check.check(spec, profile='readable')[0])
    fix.fix(spec, profile='readable')
    assert spec['body'][20]['table'].get('header_rows') == 1 and spec['body'][20]['table'].get('repeat_header')


def run():
    paginator()
    plan()
    table_and_last()
    flow()
    order_and_head()
    from . import tests_units
    tests_units.run()
    print('SELFTEST pagefit: paginator, plan fix, table cut, short last page, columns / footnotes / objects, reading units OK')
