"""Self-test of the reading units of pagefit (called by tests.py): every kind of unit is found cut by a page break and held whole after
fix; a long table, references, footnote continuation and merged rows. Synthetic documents only; no Hangul needed."""
from ..core import tmpdir
import copy

from . import check, fix, model

TX = '사업의 배경과 목적, 추진 방법과 기대 효과를 차례로 설명하며 한 쪽에 여러 문단이 놓입니다. '


def _filler(n, after=6):
    return [{'p': TX * 2 + f'({i})', 'after': after} for i in range(n)]


def _item(t, n=2):
    return {'p': '□ ' + t + ' ' + TX * n, 'after': 3}


def _sub(t, n=1):
    return {'p': '○ ' + t + ' ' + TX * n, 'after': 2, 'left': 8}


def _tbl(rows, hr=1, pb='cell', cols=3):
    return {'table': {'cols': [40, 60, 60][:cols], 'header_rows': hr, 'repeat_header': True, 'page_break': pb,
                      'rows': [[f'열{c}' for c in range(cols)]] + [[f'가{r}', f'나{r}', f'다{r}'][:cols] for r in range(rows)],
                      'border': '0.4mm solid #000000'}}


def _search(make, kind, rng):
    """The first n in rng for which the check of make(n) has a finding of this kind: (n, spec)."""
    for n in rng:
        spec = make(n)
        if any(f.kind == kind for f in check.check(spec)[0]):
            return n, spec
    raise AssertionError(f'no document with a {kind} finding in {rng}')


def reading_units():
    cases = {
        '항목': lambda n: {'body': _filler(n) + [_item('첫 항목', 3), _sub('하위 1'), _sub('하위 2'), _item('둘째 항목'), _sub('하위 3')]},
        '표': lambda n: {'body': _filler(n) + [{'p': '추진 일정은 아래 표 1과 같습니다.', 'after': 4},
                                              {'p': '표 1. 추진 일정', 'after': 2, 'bold': True}, _tbl(8),
                                              {'p': '※ 일정은 바뀔 수 있습니다.', 'after': 8}] + _filler(2)},
        '붙임': lambda n: {'body': _filler(n) + [{'p': '마지막 문단입니다. ' + TX, 'after': 6}, {'p': '붙임  1. 사업계획서 1부.', 'after': 2},
                                               {'p': '2. 예산서 1부.  끝.', 'after': 10},
                                               {'p': '발신 명의 ○○○○기관장', 'after': 6, 'align': 'center', 'bold': True, 'size': 14}]},
        '상자': lambda n: {'body': _filler(n) + [dict(b, border='0.4mm solid #000000', fill='#EEEEEE')
                                                for b in [{'p': '요약 ' + TX * 2, 'after': 0}, {'p': '핵심 ' + TX * 2, 'after': 6}]] + _filler(1)},
    }
    for name, make in cases.items():
        n, spec = _search(make, 'unit', range(6, 24))
        work = copy.deepcopy(spec)
        log = fix.fix(work, profile='readable')
        found2 = check.check(work)[0]
        assert not any(x.kind in ('unit', 'heading', 'orphan_end', 'orphan_start') for x in found2), (name, [str(x) for x in found2], log)
        assert [b.get('p') for b in work['body']] == [b.get('p') for b in spec['body']], f'{name}: text and order never change'
    # a table longer than a page: cut between rows, the header repeats, no part shorter than 3 rows
    n, spec = _search(lambda k: {'body': _filler(k) + [_tbl(60)]}, 'table_rows', range(1, 20))
    work = copy.deepcopy(spec)
    fix.fix(work, profile='readable')
    t = work['body'][-1]['table']
    assert t['page_break'] == 'table' and t['repeat_header'] is True, t
    left = [str(f) for f in check.check(work)[0] if f.kind in ('table_rows', 'table_cell')]
    assert not left, left
    # a table that fits a page is not cut, an introduction stays with it
    n, spec = _search(lambda k: {'body': _filler(k) + [{'p': '아래 표와 같이 정리합니다.', 'after': 4}, _tbl(14)] + _filler(1)}, 'unit', range(6, 24))
    work = copy.deepcopy(spec)
    fix.fix(work, profile='readable')
    assert not any(f.kind == 'unit' for f in check.check(work)[0])


def references_and_notes():
    spec = {'body': _filler(15) + [{'p': '표 1 참조: 일정을 따릅니다.', 'after': 6}] + _filler(4)
            + [{'p': '표 1. 일정', 'after': 2, 'bold': True}, _tbl(3), {'p': '다음 쪽을 보십시오.', 'after': 3}] + _filler(2)}
    kinds = [f.kind for f in check.check(spec)[0]]
    assert 'ref' in kinds and 'pageref' in kinds, kinds                 # a pointer to a table on another page, a pointer to a page
    note = '각주 본문입니다. 아주 긴 설명이 줄줄이 이어집니다. ' * 12
    spec = {'body': [{'p': ['본문 줄입니다. ' * 12, {'footnote': note}], 'after': 6} for _ in range(30)]}
    found, pgs = check.check(spec)
    assert any(f.kind == 'note' for f in found) and pgs[1].notes_cont, [str(f) for f in found]


def merged_rows():
    atoms = [{'h': 5.0, 'trail': 0.0, 'keep': False, 'line': False} for _ in range(8)]
    blk = {'table': {'rows': [['a'], ['b', {'p': 'c', 'rs': 3}], ['d'], ['e'], ['f'], ['g'], ['h'], ['i']], 'header_rows': 0}}
    assert model.row_groups(blk) == {2, 3}, model.row_groups(blk)          # no cut before row 2 or 3: rows 1-3 are one group

    def sec(blocks, y1=100.0):
        return {'index': 0, 'geom': {'y0': 0.0, 'y1': y1}, 'columns': 1,
                'blocks': [{'index': i, 'block': b, 'floating': False, 'region': False, 'atoms': a} for i, (b, a) in enumerate(blocks)]}

    def lines(n):
        return [{'h': 5.0, 'trail': 0.0, 'keep': False, 'line': True} for _ in range(n)]
    pgs = model.paginate(sec([({}, lines(17)), (blk, atoms)]))             # 17 lines + 3 rows fit; the cut after row 2 is not allowed
    cuts = [k1 for p in pgs for bi, k0, k1 in p.items if bi == 1 and k1 != 8]
    assert cuts and all(k not in (2, 3) for k in cuts), [p.items for p in pgs]
    blk = {'table': {'rows': [['h']] + [['x']] * 10, 'header_rows': 1, 'repeat_header': True}}
    rows = [{'h': 5.0, 'trail': 0.0, 'keep': False, 'line': False} for _ in range(11)]
    pgs = model.paginate(sec([({}, lines(18)), (blk, rows)]))
    assert len(pgs) == 2 and pgs[1].used >= 5.0 * 2, (pgs[1].used, [p.items for p in pgs])   # the header row again on the second page


def run():
    reading_units()
    references_and_notes()
    merged_rows()
    marks()
    profiles()
    chain_breaks()
    split_big_table()


def _head(t):
    return {'p': t, 'size': 14, 'bold': True, 'after': 4, 'keep_next': True}


def chain_breaks():
    """A forced break before a table goes before the heading and the introduction that keep with it (rule PF23); a heading box counts as
    a heading; the check reports a block that keeps with the next one and is followed by a forced break."""
    intro = {'p': '아래 표와 같이 정리하였습니다.', 'after': 4, 'keep_next': True}
    tbl = dict(_tbl(6, pb='none'), page_break_before=True)
    spec = {'body': _filler(16) + [_head('1. 추진 일정'), intro, tbl] + _filler(2)}
    found = check.check(spec, profile='minimal')[0]
    assert any(f.kind == 'heading' and 'page_break' not in f.text and '강제 쪽 나눔' in f.text for f in found), [str(f) for f in found]
    for prof in ('minimal', 'readable'):
        work = copy.deepcopy(spec)
        log = fix.fix(work, profile=prof)
        body = work['body']
        assert body[16].get('page_break_before') and not body[18].get('page_break_before'), (prof, log)
        assert not any(f.kind == 'heading' for f in check.check(work, profile=prof)[0]), prof
    off = {'name': 'nochain', 'extends': 'minimal', 'fix': {'breaks': {'chain_start': False}}}
    work = copy.deepcopy(spec)
    fix.fix(work, profile=off)
    assert not work['body'][16].get('page_break_before'), 'chain_start false leaves the break where it is'
    # a heading box: a table of one cell with a bold heading, size above the body text
    box = {'table': {'cols': [170], 'rows': [[{'p': '2. 붙임 목록', 'size': 14, 'bold': True}]], 'border': '0.4mm solid #000000'}}
    assert model.is_heading(box, 10.0) and not model.is_heading(_tbl(2), 10.0)


def split_big_table():
    """A table of a third of a page or more that would leave 40 mm or more empty above it is cut between rows (header repeats) instead of
    moved whole; a small table stays whole; split_gap_mm 0 turns it off (rule PF24)."""
    def make(n):
        return {'body': _filler(n) + [_head('표 제목'), _tbl(20, pb='none'), {'p': '끝 문단', 'after': 6}]}
    n = next(k for k in range(2, 24) if any(f.kind == 'empty' and 'None' not in f.text for f in check.check(make(k), profile='readable')[0])
             and model.pages(make(k))[0].free > 45 and len(model.pages(make(k))) >= 2)
    spec = make(n)
    work = copy.deepcopy(spec)
    log = fix.fix(work, profile='readable')
    t = work['body'][-2]['table']
    assert t['page_break'] == 'table' and t['repeat_header'] and any('행 경계에서 나눔' in x for x in log), (log, t.get('page_break'))
    assert model.pages(work)[0].free < 40, [round(p.free) for p in model.pages(work)]
    off = {'name': 'nosplit', 'extends': 'readable', 'fix': {'tables': {'split_gap_mm': 0}}}
    work2 = copy.deepcopy(spec)
    fix.fix(work2, profile=off)
    assert work2['body'][-2]['table']['page_break'] == 'none', 'split_gap_mm 0: the table stays whole'
    small = {'body': _filler(n) + [_head('표 제목'), _tbl(3, pb='none'), {'p': '끝 문단', 'after': 6}]}
    work3 = copy.deepcopy(small)
    fix.fix(work3, profile='readable')
    assert work3['body'][-2]['table']['page_break'] == 'none', 'a small table stays whole'
    # fixed row heights are kept unless the profile frees them
    heights = copy.deepcopy(spec)
    heights['body'][-2]['table']['heights'] = [7.0] * 21
    fix.fix(heights, profile='readable')
    assert heights['body'][-2]['table'].get('heights'), 'free_heights false: the row heights stay'
    free = {'name': 'free', 'extends': 'readable', 'fix': {'tables': {'free_heights': True}}}
    heights = copy.deepcopy(spec)
    heights['body'][-2]['table']['heights'] = [7.0] * 21
    fix.fix(heights, profile=free)
    assert 'heights' not in heights['body'][-2]['table'], 'free_heights true: the row heights go'


def marks():
    """The item marks: 개조식 and the 공문 levels L1-L8; an item with its deeper items is one unit."""
    from . import units
    for text, want in (('□ 항목', ('gae', 1)), ('○ 항목', ('gae', 2)), ('- 항목', ('gae', 3)), ('1. 항목', ('gong', 1)), ('가. 항목', ('gong', 2)),
                       ('1) 항목', ('gong', 3)), ('가) 항목', ('gong', 4)), ('(1) 항목', ('gong', 5)), ('(가) 항목', ('gong', 6)),
                       ('① 항목', ('gong', 7)), ('㉮ 항목', ('gong', 8)), ('일반 문단', None)):
        assert units.mark({'p': text}) == want, (text, units.mark({'p': text}))
    body = [{'p': '1. 첫째 항목'}, {'p': '가. 하위'}, {'p': '1) 더 하위'}, {'p': '2. 둘째 항목'}, {'p': '가. 하위'}, {'p': '일반 문단'}]
    got = {(u.kind, u.a, u.b) for u in units.find_units(body, [10.0] * 6, 200.0, 10.0)}
    assert ('item', 0, 2) in got and ('item', 3, 4) in got, got      # the nested (1, 2) is inside (0, 2): merged


def profiles():
    """Profiles: the built-in ones, `extends`, an own file, wrong keys and values, a profile that changes what is looked for and done."""
    import json
    import os
    from . import profile
    assert set(profile.builtin()) >= {'minimal', 'readable'}
    mini, read = profile.load(None), profile.load('readable')
    assert mini['name'] == 'minimal' and not mini['fix']['units']['strong'] and read['fix']['units']['strong'] and read['fix']['tables']['min_rows'] == 3
    d = tmpdir.mkdtemp('hwpx_docs_pf_')
    mine = os.path.join(d, 'mine.json')
    json.dump({'name': 'mine', 'extends': 'readable', 'fix': {'tables': {'min_rows': 5}, 'units': {'weak': []}}, 'check': {'fill': 90}},
              open(mine, 'w', encoding='utf-8'))
    p = profile.load(mine, max_extra=2)
    assert p['fix']['tables']['min_rows'] == 5 and p['fix']['units']['weak'] == [] and p['fix']['units']['strong'] and p['check']['fill'] == 90
    assert p['fix']['spacing']['max_extra'] == 2 and p['fix']['tables']['cut_between_rows'], p            # inherited and overridden
    for bad, what in (({'fix': {'tabels': {}}}, 'fix.tabels'), ({'fix': {'tables': {'min_rows': 'x'}}}, 'fix.tables.min_rows'),
                      ({'check': {'kinds': ['nonsense']}}, 'check.kinds'), ({'fix': {'keep': {'headings': 1}}}, 'fix.keep.headings'),
                      ({'extends': 'no such profile'}, 'no such profile')):
        try:
            profile.load(bad)
            raise AssertionError(f'{what}: must stop')
        except ValueError as e:
            assert what in str(e), (what, str(e))
    # the same document: minimal does not look for units, readable does and fixes them
    n, spec = _search(lambda k: {'body': _filler(k) + [_item('첫 항목', 3), _sub('하위 1'), _sub('하위 2'), _item('둘째 항목')]}, 'unit', range(6, 24))
    assert not any(f.kind == 'unit' for f in check.check(spec, profile='minimal')[0])
    assert any(f.kind == 'unit' for f in check.check(spec, profile='readable')[0])
    a, b = copy.deepcopy(spec), copy.deepcopy(spec)
    fix.fix(a)
    fix.fix(b, profile=mine)
    assert not any('keep_lines' in x for x in a['body']) and any('keep_lines' in x for x in b['body']), 'minimal keeps no unit, mine does'
    assert not any(f.kind == 'unit' for f in check.check(b, profile=mine)[0])
