"""pagefit fix: change the spec so that a reader never has to turn a page back, and every page still looks full (rules PF07-PF22).
Which of the steps below run, and with what numbers, is the profile (profile.py, profiles/*.json): `minimal` (the default) is steps 1, 2b, 4, 6, 8
without units; `readable` runs them all.
Text size, text and order of the blocks never change; only the keys `keep_next`, `keep_lines`, `widow`, `page_break`, `page_break_before`,
`after`, and for tables `page_break`, `margin`, `hold`, `header_rows`, `repeat_header`.

fix(spec, pic_dir, ...) -> [log line] (the spec changes in place). The steps, each checked against the page model of model.py:
  1. a heading gets `keep_next`; a paragraph of two lines or more gets `widow` (no single line at the top or bottom of a page);
  2. every strong reading unit that fits on a page (units.py) is held together: `keep_next` / `keep_lines` on its paragraphs, a table
     that fits gets `page_break: none`;
  3. a table longer than a page is cut between rows (`page_break: table`), its header rows repeat (`repeat_header`), and neither the
     first nor the last part has fewer than `min_rows` rows (the table starts on a new page when that helps); 3c. a table that
     goes over a page with no header row repeats its first row when that row looks like a header (fill or bold; rules PF27);
  4. a forced page break after a page filled less than `break_fill` percent (or less than `fill` when the spacing cannot take the
     free space, or when the unit after the break would fit in it: pulled up), or right after a heading that would stand alone, is
     taken away (not one that step 5 added);
  5. a unit that flags cannot hold (a table or picture follows a paragraph: Hangul ties a paragraph to the next PARAGRAPH only) and is
     still cut gets `page_break_before` on its first block;
  2d. (after step 2c, and again before 6) a table kept whole that fits on a page gets `hold` (`tables.hold_whole`; rules PF26): the
     text after it stays after it;
  6. a last page of `last_lines` lines or fewer is pulled back: the spacing under the blocks of the page before it shrinks (at most
     `max_shrink` pt each, never below 0) until the lines fit there;
  7. weak units (a short section, a numbered list) are held together too, one at a time, and kept only when that leaves no page emptier;
  8. the free space under the text of every other page goes to the spacing under its paragraphs (`after`) and tables (`margin` below),
     at most `max_extra` pt each; a page that cannot take all of it keeps the rest (the check says so).
`safety` mm stay free under the text of a page in step 8 (`safety_flow` mm, plus 4 mm for each footnote on it, on a page of the preview's
flow: columns, footnotes, objects; a full page of that kind spilled a paragraph to a new page in Hangul).
"""
from ..core import registry
from ..preview.measure import PT
from . import check, model, units
from . import profile as prof_mod


def _bodies(spec):
    return [s.get('body', []) for s in model.sections_of(spec)]


def _eff(spec):
    return _bodies(model.resolved(spec))


def _block(spec, sec, i):
    body = _bodies(spec)[sec]
    if isinstance(body[i], str):
        body[i] = {'p': body[i]}
    return body[i]


def _notes_on(eff, p):
    """How many footnotes and endnotes the blocks of page `p` refer to."""
    n = 0
    for bi, k0, k1 in p.items:
        b = eff[p.section][bi]
        runs = b.get('p') if isinstance(b, dict) else None
        n += sum(1 for r in (runs if isinstance(runs, list) else []) if isinstance(r, dict) and ('footnote' in r or 'endnote' in r))
    return n


def _keep_free(eff, p, safety, safety_flow):
    """mm that the spacing step leaves free under the text of page `p`: `safety`; a page of the preview's flow `safety_flow` and 4 mm
    more for each footnote on it (measured: footnote pages spilled a paragraph to a new page in Hangul with less)."""
    return safety_flow + 4.0 * _notes_on(eff, p) if p.renderer else safety


def _gaps(eff, p, last=False):
    """The spacings under the blocks that END on page `p` (not the last block of the page unless `last`): [(kind, block index)],
    kind 'after' for a paragraph, 'margin' for a table (its outer margin below)."""
    out = []
    items = p.items if last else p.items[:-1]
    total = {}
    for pg_bi, k0, k1 in p.items:
        total[pg_bi] = k1
    for bi, k0, k1 in items:
        b = eff[p.section][bi]
        if not isinstance(b, dict):
            continue
        if 'table' in b:
            out.append(('margin', bi))
        elif 'p' in b:
            out.append(('after', bi))
    return out


def _get(spec, eff, sec, kind, bi):
    b = eff[sec][bi]
    if kind == 'margin':
        m = (b['table'].get('margin') or [1.0, 1.0, 1.0, 1.0])
        return float(m[3] if len(m) == 4 else m[-1])
    return float(b.get('after', 0) or 0)


def _put(spec, sec, kind, bi, v):
    """Set the spacing; v in pt for 'after', in mm for 'margin' (bottom). Returns what to give back to _undo."""
    b = _block(spec, sec, bi)
    if kind == 'margin':
        t = b['table']
        old = t.get('margin')
        m = list(old) if old and len(old) == 4 else [1.0, 1.0, 1.0, 1.0]
        m[3] = round(v, 2)
        t['margin'] = m
        return ('margin', bi, old)
    old = b.get('after')
    b['after'] = round(v, 1)
    return ('after', bi, old)


def _undo(spec, sec, saved):
    for kind, bi, old in saved:
        b = _block(spec, sec, bi)
        tgt, key = (b['table'], 'margin') if kind == 'margin' else (b, 'after')
        if old is None:
            tgt.pop(key, None)
        else:
            tgt[key] = old


def _shape(pgs):
    return [(p.section, tuple(p.items)) for p in pgs]


def _score(pgs, fill):
    """(empty pages, pages): smaller is better."""
    return (sum(1 for p in pgs[:-1] if p.fill * 100 < fill and not p.skipped), len(pgs))


def _set(spec, sec, i, key, value, undo):
    """Set a block flag; remember what to give back. For a table, `page_break` is the table's own key."""
    b = _block(spec, sec, i)
    tgt = b['table'] if key == 'page_break' and isinstance(b.get('table'), dict) else b
    if tgt.get(key) != value:
        undo.append((tgt, key, tgt.get(key, KeyError)))
        tgt[key] = value
        return True
    return False


def _revert(undo):
    for tgt, key, old in reversed(undo):
        if old is KeyError:
            tgt.pop(key, None)
        else:
            tgt[key] = old


def _apply_unit(spec, sec, u, info, undo, split=()):
    """Set the flags that hold unit `u`; a table in `split` (section, block) stays cuttable between rows."""
    want, tied = units.wanted_flags(u, info['body'], info['heights'], info['cap'])
    n = 0
    for i, d in want.items():
        for k, v in d.items():
            if k == 'page_break' and (sec, i) in split:
                continue
            n += _set(spec, sec, i, k, v, undo)
    return n, tied


def _has_note(x):
    """True when a spec value (a table row, a cell, a run list ...) holds a footnote or an endnote."""
    if isinstance(x, dict):
        return 'footnote' in x or 'endnote' in x or any(_has_note(v) for v in x.values())
    return isinstance(x, list) and any(_has_note(v) for v in x)


def _has_break(b):
    return isinstance(b, dict) and bool(b.get('page_break') or b.get('page_break_before'))


def _chain_start(eff, sec, i, cmax):
    """The first block of the keep_next chain that ends at block `i` (at most `cmax` blocks back; a block that has a break of its own
    ends the chain): Hangul does not carry a block that keeps with the next one over a forced break on that next block, so the break
    belongs before the chain, not before its last block."""
    body = eff[sec]
    j = i
    while j > 0 and i - j < cmax and isinstance(body[j - 1], dict) and body[j - 1].get('keep_next'):
        j -= 1
        if _has_break(body[j]):
            break
    return j


def _move_break(spec, sec, i, undo, cmax=6):
    """A page break before block `i` goes before the first block of its keep_next chain (_chain_start). Returns that block."""
    j = _chain_start(_eff(spec), sec, i, cmax)
    if j != i:
        b = _block(spec, sec, i)
        for key in ('page_break_before', 'page_break'):
            if key in b:                                      # (a table's own `page_break` is inside b['table'], not here)
                undo.append((b, key, b[key]))
                del b[key]
    _set(spec, sec, j, 'page_break_before', True, undo)
    return j


def _chain_pass(spec, cmax, pf, log):
    """Every forced break before a block that follows a keep_next chain moves before the chain (rule PF23). Returns how many moved."""
    moved = 0
    for sec, body in enumerate(_eff(spec)):
        for i, b in enumerate(body):
            if not _has_break(b) or i == 0 or not (isinstance(body[i - 1], dict) and body[i - 1].get('keep_next')):
                continue
            j = _chain_start(_eff(spec), sec, i, cmax)
            if j == i:
                continue
            _move_break(spec, sec, i, [], cmax)
            if (sec, i) in pf:
                pf.discard((sec, i))
                pf.add((sec, j))
            moved += 1
            log.append(f'쪽 나눔을 "{model.text_of(_eff(spec)[sec][j], 24)}"(블록 {j}) 앞으로 옮김: 그 제목·소개 문장이 다음 쪽 첫 블록과 떨어지지 않게')
    return moved


def fix(spec, pic_dir='.', profile=None, **kw):
    """Fix the spec in place by the rules of a profile (profile.py; None = minimal) -> [log line]. Keyword arguments override single
    values: fill, last_lines, min_rows, break_fill, max_extra, max_shrink, safety, safety_flow, section_ratio, list_ratio."""
    P = prof_mod.load(profile, **kw)
    F, C = P['fix'], P['check']
    fill, last_lines = C['fill'], C['last_lines']
    U, T, Bk, Sp = F['units'], F['tables'], F['breaks'], F['spacing']
    min_rows, section_ratio, list_ratio = T['min_rows'], U['section_ratio'], U['list_ratio']
    max_extra, safety, safety_flow = Sp['max_extra'], Sp['safety'], Sp['safety_flow']
    cmax = Bk['chain_max'] if Bk['chain_start'] else 0         # a break goes before the keep_next chain that leads to its block
    log = []
    split, tried_split = set(), set()                        # (section, block) of tables that may be cut between rows / tried (steps 2c, 5)
    pf = set()                                               # (section, block) that a step gave a page break: the breaks step leaves them
    atoms = {}
    for sec in registry.backend('blocks', 'preview')(model.resolved(spec), pic_dir):
        for b in sec['blocks']:
            atoms[(sec['index'], b['index'])] = (len(b['atoms']), sum(a['line'] for a in b['atoms']))
    size = model.body_size(spec)

    def find(info):
        """The units of one section that this profile asks for."""
        want = set(U['strong']) | set(U['weak'])
        return [u for u in units.find_units(info['body'], info['heights'], info['cap'], size, section_ratio, list_ratio,
                                            U['item_ratio'], U['heading_lines']) if u.kind in want and (u.strong or u.kind in U['weak'])]

    def chk():
        return check.check(spec, pic_dir, profile=P)
    held = set()                                             # (section, block) of tables that this fix gave `hold`

    def hold_whole():
        """2d. A table kept whole (`page_break` none) that fits on a page holds its paragraph on its page (`hold`, 개체와 조판
        부호를 항상 같은 쪽에 놓기): Hangul would otherwise move it alone to the next page and the text after it up before it
        (rules PF26). Not for a table that may be cut (Hangul would not cut it) or one higher than a page (Hangul left empty
        pages). A table held here that may be cut now is let go. -> how many tables got it."""
        if not T['hold_whole']:
            return 0
        n = 0
        infos = {i['index']: i for i in model.section_info(spec, pic_dir)}
        for s, body in enumerate(_eff(spec)):
            for i, b in enumerate(body):
                t = b.get('table') if isinstance(b, dict) else None
                if not isinstance(t, dict) or t.get('pos') or t.get('inline') is True or s not in infos:
                    continue
                whole = t.get('page_break') == 'none' and infos[s]['heights'][i] <= infos[s]['cap'] + 0.5
                if whole and not t.get('hold'):
                    _block(spec, s, i)['table']['hold'] = True
                    held.add((s, i))
                    n += 1
                elif not whole and (s, i) in held:
                    _block(spec, s, i)['table'].pop('hold', None)
                    held.discard((s, i))
        return n
    # 1. keep rules
    nh = nw = 0
    for s, body in enumerate(_eff(spec)):
        for i, b in enumerate(body):
            if not isinstance(b, dict) or ('p' not in b and 'table' not in b):
                continue
            if 'table' in b and not (F['keep']['headings'] and model.is_heading(b, size)):
                continue
            if F['keep']['headings'] and model.is_heading(b, size) and not b.get('keep_next'):
                _block(spec, s, i)['keep_next'] = True
                nh += 1
            elif F['keep']['widow'] and not model.is_heading(b, size) and atoms.get((s, i), (0, 0))[1] >= 2 and not b.get('widow'):
                _block(spec, s, i)['widow'] = True
                nw += 1
    if nh or nw:
        log.append(f'제목 {nh}개에 "다음 문단과 함께", 문단 {nw}개에 외톨이 줄 보호를 켬')
    # 2. strong reading units
    count = {}
    if U['strong']:
        for info in model.section_info(spec, pic_dir):
            for u in find(info):
                if u.strong and sum(info['heights'][u.a:u.b + 1]) <= info['cap'] + 0.5:
                    n, _ = _apply_unit(spec, info['index'], u, info, [])
                    if n:
                        count[u.kind] = count.get(u.kind, 0) + 1
    if count:
        log.append('읽기 단위를 한 쪽에 묶음(keep_next·keep_lines·표 나누지 않음): ' + ', '.join(
            f'{check.KIND_LABEL[k]} {v}개' for k, v in count.items()))
    if cmax:
        _chain_pass(spec, cmax, pf, log)
    # 3. tables longer than a page
    if T['cut_between_rows'] or T['repeat_header']:
        for info in model.section_info(spec, pic_dir):
            eff = _eff(spec)
            for i, b in enumerate(info['body']):
                if not (isinstance(b, dict) and 'table' in b):
                    continue
                lead = sum(info['heights'][_chain_start(eff, info['index'], i, 6):i])      # the headings and sentences that keep with the table
                if info['heights'][i] > info['cap'] or (T['cut_between_rows'] and lead and info['heights'][i] + lead > info['cap'] + 0.5):
                    # a table that does not fit a page, or not together with its heading (a heading is not carried to a table: Hangul would
                    # leave it alone at the page end and move the whole table): it may be cut between rows
                    if info['heights'][i] <= info['cap']:
                        split.add((info['index'], i))
                    t = _block(spec, info['index'], i)['table']
                    ch = []
                    if T['cut_between_rows'] and t.get('page_break', 'cell') != 'table':
                        t['page_break'] = 'table'
                        ch.append('행 단위로만 나눔')
                    if T['repeat_header'] and int(t.get('header_rows', 0) or 0) and not t.get('repeat_header', True):
                        t['repeat_header'] = True
                        ch.append('제목 줄 반복 켬')
                    if T['free_heights'] and t.get('heights') and t.get('page_break') == 'table':
                        del t['heights']                       # fixed row heights (from HTML) make Hangul move the whole table (measured)
                        ch.append('고정 행 높이를 풀었음')
                    if ch:
                        log.append(f'쪽보다 긴 표(블록 {i}): ' + ', '.join(ch))
    def try_split(sec, bi, ok):
        """Cut table `bi` between rows (its header rows repeat, fixed row heights go) and keep that when `ok(findings, pages)` holds and
        no finding that a reader feels (a unit, a cut after the header, a heading alone, a single line) is added. True when kept."""
        bad = ('unit', 'table_rows', 'table', 'heading', 'orphan_end', 'orphan_start')
        before = sum(1 for f in chk()[0] if f.kind in bad)
        undo = []
        _set(spec, sec, bi, 'page_break', 'table', undo)
        t = _block(spec, sec, bi)['table']
        if t.get('hold') and (sec, bi) in held:              # a held table is not cut by Hangul: let it go
            undo.append((t, 'hold', True))
            del t['hold']
        if int(t.get('header_rows', 0) or 0) and not t.get('repeat_header', True):
            undo.append((t, 'repeat_header', t.get('repeat_header', KeyError)))
            t['repeat_header'] = True
        if T['free_heights'] and t.get('heights'):
            undo.append((t, 'heights', t['heights']))
            del t['heights']
        split.add((sec, bi))
        found, pgs1 = chk()
        if ok(found, pgs1) and sum(1 for f in found if f.kind in bad) <= before:
            return True
        _revert(undo)
        split.discard((sec, bi))
        return False
    # 2c. a table of a third of a page or more that would leave a big empty space above it is cut between rows instead of moved whole
    if T['cut_between_rows'] and T['split_gap_mm'] > 0:
        for _ in range(40):
            found0, pgs = chk()
            eff = _eff(spec)
            infos = {i['index']: i for i in model.section_info(spec, pic_dir)}
            hit = None
            for n in range(1, len(pgs)):
                p, q = pgs[n - 1], pgs[n]
                if p.skipped or q.skipped or q.section != p.section or q.why == 'forced_break' or p.free < T['split_gap_mm'] or not q.items:
                    continue
                for bi, k0, k1 in q.items:           # the table that starts the page, after the keep_next chain that leads to it
                    b = eff[q.section][bi]
                    if isinstance(b, dict) and 'table' in b and k0 == 0 and (q.section, bi) not in tried_split:
                        info = infos[q.section]
                        if T['split_min_ratio'] * info['cap'] <= info['heights'][bi] <= info['cap'] + 0.5:
                            hit = (n, q.section, bi)
                    if hit or not (isinstance(b, dict) and b.get('keep_next')):
                        break
                if hit:
                    break
            if hit is None:
                break
            n, sec, bi = hit
            tried_split.add((sec, bi))
            if try_split(sec, bi, lambda f, p, n=n: p[n - 1].free < T['split_gap_mm'] and len(p) <= len(pgs)):
                log.append(f'쪽 {pgs[n].no}: 표(블록 {bi})를 통째로 넘기면 앞 쪽이 {pgs[n - 1].free:.0f}mm 비므로 행 경계에서 나눔 '
                           f'(머리 행 반복, 고정 행 높이 풀기)')
    held_n = hold_whole()                                    # 2d. after 2c chose the tables that are cut instead of moved whole
    # 2b. a table cut after its header row only starts on the next page
    if T['header_only_fix']:
        for _ in range(20):
            found, pgs = chk()
            hit = next((f for f in found if f.kind == 'table' and (pgs[f.page - 1].section, f.block) not in pf), None)
            if hit is None:
                break
            sec = pgs[hit.page - 1].section
            start = _move_break(spec, sec, hit.block, [], cmax)
            pf.add((sec, hit.block))
            pf.add((sec, start))
            log.append(f'쪽 {hit.page}: 머리 행만 남은 표를 다음 쪽으로 보냄 (블록 {hit.block}' + (f', 앞 제목·소개 문장 {hit.block - start}개와 함께' if start != hit.block else '') + ')')
    # 4. forced breaks after a page that is mostly empty
    if Bk['remove_after_empty']:
        for _ in range(200):
            pgs = model.pages(spec, pic_dir)
            eff = _eff(spec)

            def pulled(n):
                if not Bk['pull_up']:
                    return False
                return pgs[n - 1].free >= _first_unit(spec, pic_dir, pgs[n], size, section_ratio, list_ratio) + safety
            hit = next((n for n in range(1, len(pgs)) if pgs[n].why == 'forced_break' and not pgs[n - 1].skipped and pgs[n].items
                        and (pgs[n].section, pgs[n].items[0][0]) not in pf
                        and (pgs[n - 1].fill * 100 < Bk['break_fill']
                             or (pgs[n - 1].fill * 100 < fill and (pgs[n - 1].free > _capacity(eff, pgs[n - 1], max_extra) or pulled(n))))),
                       None)
            if hit is None:
                break
            bi = pgs[hit].items[0][0]
            b = _block(spec, pgs[hit].section, bi)
            b.pop('page_break', None)
            b.pop('page_break_before', None)
            log.append(f'쪽 {pgs[hit].no}: 앞 쪽이 {pgs[hit - 1].fill * 100:.0f}%만 차서 강제 쪽 나눔을 풀었음: "{model.text_of(b)}"')
    if Bk['heading_before_break']:
        for _ in range(50):                                  # a heading alone before a forced break has nothing to keep with
            found, pgs = chk()
            hit = next((f for f in found if f.kind == 'heading' and f.page < len(pgs) and pgs[f.page].why == 'forced_break'
                        and pgs[f.page].items and (pgs[f.page].section, pgs[f.page].items[0][0]) not in pf), None)
            if hit is None:
                break
            b = _block(spec, pgs[hit.page].section, pgs[hit.page].items[0][0])
            b.pop('page_break', None)
            b.pop('page_break_before', None)
            log.append(f'쪽 {hit.page}: 쪽 끝에 홀로 남은 제목 뒤의 강제 쪽 나눔을 풀었음: "{model.text_of(b)}"')
    # 5. units that flags cannot hold: a page break before them
    if Bk['unit_break'] and U['strong']:
        for _ in range(100):
            found, pgs = chk()
            hit = next((f for f in found if f.kind == 'unit' and (pgs[f.page - 1].section, f.block) not in pf), None)
            if hit is None:
                break
            sec = pgs[hit.page - 1].section
            start = _unit_start(spec, pic_dir, sec, hit.block, size, section_ratio, list_ratio, P)
            if T['cut_between_rows'] and T['split_gap_mm'] > 0:      # a big table: cut it between rows instead of leaving a big gap
                eff_body = _eff(spec)[sec]
                info = next(i for i in model.section_info(spec, pic_dir) if i['index'] == sec)
                tb = next((i for i in range(hit.unit.a, hit.unit.b + 1) if isinstance(eff_body[i], dict) and 'table' in eff_body[i]
                           and T['split_min_ratio'] * info['cap'] <= info['heights'][i] <= info['cap'] + 0.5
                           and (sec, i) not in tried_split), None)
                pg = next((p for p in pgs if p.section == sec and any(bj == start for bj, _, _ in p.items)), None)
                gap = (pg.y1 - pg.y0) - sum(h for (bj, _, _), h in zip(pg.items, pg.hs) if bj < start) if pg else 0.0
                if tb is not None and gap > T['split_gap_mm']:
                    tried_split.add((sec, tb))
                    if try_split(sec, tb, lambda f, p, hb=hit.block: not any(x.kind == 'unit' and x.block == hb for x in f)):
                        log.append(f'쪽 {hit.page}: 표(블록 {tb})를 통째로 넘기면 앞 쪽이 {gap:.0f}mm 비므로 행 경계에서 나눔 '
                                   f'(머리 행 반복, 고정 행 높이 풀기)')
                        continue
            start = _move_break(spec, sec, start, [], cmax)
            pf.add((sec, start))
            pf.add((sec, hit.block))
            log.append(f'쪽 {hit.page}: {check.KIND_LABEL[hit.unit.kind]}이(가) 쪽을 넘어 나뉘어 그 앞에서 쪽을 나눔: '
                       f'"{model.text_of(_eff(spec)[sec][start], 24)}"')
    # 3c. a table that goes over a page repeats its first row when that row looks like a header (fill or bold; rules PF27)
    if T['repeat_header']:
        from ..check.readability import marked
        heads = 0
        for _ in range(20):
            found, pgs = chk()
            eff = _eff(spec)
            hit = None
            for f in found:
                if f.kind != 'table_head' or f.block is None:
                    continue
                sec = pgs[f.page - 1].section
                t = eff[sec][f.block]['table']
                rows = t.get('rows') or []
                row0 = (rows[0].get('cells', []) if isinstance(rows[0], dict) else rows[0]) if len(rows) > 1 else []
                if not int(t.get('header_rows', 0) or 0) and row0 and any(marked(c) for c in row0):
                    hit = (sec, f.block)
                    break
            if hit is None:
                break
            t = _block(spec, *hit)['table']
            t['header_rows'], t['repeat_header'] = 1, True
            heads += 1
        if heads:
            log.append(f'쪽을 넘는 표 {heads}개의 첫 행(머리 행처럼 칠하거나 굵게 쓴 행)을 다음 쪽에서 반복함')
    # 5b. a footnote that goes on at the next page: the paragraph with the last note of the page starts the next one; when that
    # note is in a row of a table cut at the page end, the cut moves up above that row (more room above the table, as in 3b)
    if F['notes']['move_paragraph']:
        tried_notes = set()
        for _ in range(10):
            found, pgs = chk()
            hit = next((f for f in found if f.kind == 'note' and f.page not in tried_notes), None)
            if hit is None:
                break
            tried_notes.add(hit.page)
            p = pgs[hit.page - 1]
            eff = _eff(spec)
            refs = [bi for bi, k0, k1 in p.items if isinstance(eff[p.section][bi], dict) and isinstance(eff[p.section][bi].get('p'), list)
                    and any(isinstance(r, dict) and ('footnote' in r or 'endnote' in r) for r in eff[p.section][bi]['p'])]
            undo, how = [], None
            tb, k0, k1 = p.items[-1]
            t = eff[p.section][tb].get('table') if isinstance(eff[p.section][tb], dict) else None
            noted = [r for r in range(k0, k1) if isinstance(t, dict) and r < len(t.get('rows', [])) and _has_note(t['rows'][r])]
            if noted and (not refs or refs[-1] < tb) and noted[-1] > max(k0, int(t.get('header_rows', 0) or 0)) \
                    and hit.page < len(pgs) and pgs[hit.page].items and pgs[hit.page].items[0][:2] == (tb, k1):
                info = next(i for i in model.section_info(spec, pic_dir) if i['index'] == p.section)
                row_h = info['heights'][tb] / max(1, len(t.get('rows', [])))
                tt = _block(spec, p.section, tb)['table']
                old = tt.get('margin')
                m = list(old) if old and len(old) == 4 else [1.0, 1.0, 1.0, 1.0]
                m[2] = round(m[2] + (k1 - noted[-1]) * row_h + 0.5, 2)
                undo.append((tt, 'margin', old if old else KeyError))
                tt['margin'] = m
                how = f'각주가 달린 표의 {noted[-1] + 1}행부터 다음 쪽으로 가도록 표 위 간격을 늘림(블록 {tb})'
            elif refs and (p.section, refs[-1]) not in pf and p.items[0][0] != refs[-1]:
                start = _unit_start(spec, pic_dir, p.section, refs[-1], size, section_ratio, list_ratio, P)
                start = _move_break(spec, p.section, start, undo, cmax)
                how = '마지막 각주가 달린 문단부터 새 쪽에서 시작함'
            if how is None:
                continue
            found2, pgs2 = chk()
            if sum(1 for f in found2 if f.kind == 'note') < sum(1 for f in found if f.kind == 'note') and len(pgs2) <= len(pgs) + 1:
                if not noted:
                    pf.add((p.section, start))
                log.append(f'쪽 {hit.page}: 각주가 다음 쪽으로 이어져 {how}')
            else:
                _revert(undo)
    # 3b. tables longer than a page: neither the first nor the last part is shorter than min_rows
    tried = set()
    for _ in range(20 if min_rows else 0):
        found, pgs = chk()
        hit = next((f for f in found if f.kind == 'table_rows' and (pgs[f.page - 1].section, f.block, f.extra['which']) not in tried), None)
        if hit is None:
            break
        sec, which = pgs[hit.page - 1].section, hit.extra['which']
        tried.add((sec, hit.block, which))
        count0 = sum(1 for f in found if f.kind == 'table_rows')
        info = next(i for i in model.section_info(spec, pic_dir) if i['index'] == sec)
        nrows = max(1, len(_eff(spec)[sec][hit.block]['table'].get('rows', [])))
        row_h = info['heights'][hit.block] / nrows
        undo = []
        if which == 'last':                                  # more room used above the table: the cut moves up, the last part grows
            t = _block(spec, sec, hit.block)['table']
            old = t.get('margin')
            m = list(old) if old and len(old) == 4 else [1.0, 1.0, 1.0, 1.0]
            m[2] = round(m[2] + (min_rows - hit.extra['rows']) * row_h + 0.5, 2)
            undo.append((t, 'margin', old if old else KeyError))
            t['margin'] = m
            how = f'표 위 간격을 {m[2] - (old[2] if old and len(old) == 4 else 1.0):.1f}mm 늘려 마지막 조각을 키움'
        else:                                                # the first part is short: the table starts on a new page
            first = _unit_start(spec, pic_dir, sec, hit.block, size, section_ratio, list_ratio, P)
            first = _move_break(spec, sec, first, undo, cmax)
            how = '표를 새 쪽에서 시작함'
        found2, pgs2 = chk()
        if sum(1 for f in found2 if f.kind == 'table_rows') < count0 and _score(pgs2, fill)[1] <= _score(pgs, fill)[1] + 1:
            if which == 'first':
                pf.add((sec, first))
            log.append(f'쪽 {hit.page}: 긴 표의 {"앞" if which == "first" else "뒤"} 조각이 {min_rows}행보다 짧아 {how}(블록 {hit.block})')
        else:
            _revert(undo)
    if cmax:
        _chain_pass(spec, cmax, pf, log)
    nhold = held_n + hold_whole()                            # again for the tables that later steps kept whole or let be cut
    if nhold:
        log.append(f'통째로 두는 표 {nhold}개에 "개체와 조판 부호를 항상 같은 쪽에 놓기"를 켬(뒤 문단이 표 앞으로 당겨지지 않게)')
    # 6. a short last page is pulled back
    pgs = model.pages(spec, pic_dir)
    if F['last_page']['pull_back'] and len(pgs) > 1 and not pgs[-1].skipped \
            and sum(k1 - k0 for _, k0, k1 in pgs[-1].items) <= F['last_page']['last_lines'] and pgs[-1].why != 'forced_break':
        n = len(pgs)
        if _spacing(spec, pic_dir, pgs, n - 2, -F['last_page']['max_shrink'], lambda new: len(new) < n, 'shrink', 0.0, Sp['tables']):
            log.append(f'마지막 쪽({n}쪽)이 짧아 앞 쪽의 문단 간격을 줄여 끌어올림')
    # 7. weak units, one at a time
    kept = {}
    if U['weak']:
        for info in model.section_info(spec, pic_dir):
            for u in find(info):
                if u.strong or sum(info['heights'][u.a:u.b + 1]) > info['cap'] + 0.5:
                    continue
                pgs = model.pages(spec, pic_dir)
                before = _score(pgs, fill)
                undo = []
                n, _ = _apply_unit(spec, info['index'], u, info, undo, split)
                if n:
                    if _score(model.pages(spec, pic_dir), fill) <= before:
                        kept[u.kind] = kept.get(u.kind, 0) + 1
                    else:
                        _revert(undo)
    if kept:
        log.append('약한 단위를 묶음(쪽이 더 비지 않는 것만): ' + ', '.join(f'{check.KIND_LABEL[k]} {v}개' for k, v in kept.items()))
    # 8. free space -> paragraph and table spacing
    done = 0
    if Sp['fill']:
        pgs = model.pages(spec, pic_dir)
        for idx in range(len(pgs) - 1):
            pgs = model.pages(spec, pic_dir)
            if idx >= len(pgs) - 1:
                break
            keep_free = _keep_free(_eff(spec), pgs[idx], safety, safety_flow)
            if pgs[idx].free > 3 + keep_free and not pgs[idx].skipped:
                before = _shape(pgs)
                if _spacing(spec, pic_dir, pgs, idx, max_extra, lambda new, idx=idx, before=before: _shape(new)[:idx + 1] == before[:idx + 1]
                            and len(new) == len(before), 'grow', keep_free, Sp['tables']):
                    done += 1
    if done:
        log.append(f'{done}개 쪽의 남는 공간을 문단{"·표" if Sp["tables"] else ""} 간격(최대 {max_extra:g}pt)으로 나눠 채움')
    return log


def _unit_start(spec, pic_dir, sec, bi, size, section_ratio, list_ratio, P=None):
    """Where a page break may go to start block `bi` on a new page: the first block of every strong unit that fits on a page and
    holds it (a break inside such a unit would cut it), found again until nothing moves."""
    for info in model.section_info(spec, pic_dir):
        if info['index'] != sec:
            continue
        us = [u for u in units.find_units(info['body'], info['heights'], info['cap'], size, section_ratio, list_ratio)
              if u.strong and (P is None or not P['fix']['units']['strong'] or u.kind in P['fix']['units']['strong'])
              and sum(info['heights'][u.a:u.b + 1]) <= info['cap'] + 0.5]
        a = bi
        while True:
            b = min([u.a for u in us if u.a < a <= u.b] or [a])
            if b == a:
                return a
            a = b
    return bi


def _first_unit(spec, pic_dir, page, size, section_ratio, list_ratio):
    """Height (mm) of the unit (or the block) that starts `page`: what a free space above it has to take for the forced break to go."""
    bi = page.items[0][0]
    for info in model.section_info(spec, pic_dir):
        if info['index'] != page.section:
            continue
        for u in units.find_units(info['body'], info['heights'], info['cap'], size, section_ratio, list_ratio):
            if u.strong and u.a == bi and sum(info['heights'][u.a:u.b + 1]) <= info['cap'] + 0.5:
                return sum(info['heights'][u.a:u.b + 1])
        return info['heights'][bi]
    return 1e9


def _capacity(eff, p, max_extra):
    """The free space (mm) that the spacing under the blocks of page `p` can take (up to `max_extra` pt each)."""
    return len(_gaps(eff, p)) * max_extra * PT


def _spacing(spec, pic_dir, pgs, idx, limit, ok, mode, keep_free=0.0, tables=True):
    """Change the spacing under the blocks that end on page `idx` (0-based): up to +limit pt (grow) or down to limit pt (shrink; at
    most -|limit|, never below 0), the amount the page has free (grow) or the last page needs (shrink). `ok(new pages)` decides
    whether the change stays. Returns True when it does."""
    p = pgs[idx]
    eff = _eff(spec)
    gaps = [g for g in _gaps(eff, p) if tables or g[0] != 'margin']
    if not gaps:
        return False
    if mode == 'grow':
        want_pt = max(0.0, p.free - keep_free) / PT
        if want_pt <= 0:
            return False
    else:
        last = pgs[idx + 1]
        want_pt = -(sum(last.hs) - p.free) / PT
        if want_pt >= 0:
            want_pt = -0.5
    base = {g: _get(spec, eff, p.section, g[0], g[1]) * (1.0 if g[0] == 'after' else 1 / PT) for g in gaps}       # pt
    for factor in ((1.1, 1.3, 1.6, 2.0) if mode == 'shrink' else (1.0, 0.8, 0.6, 0.4, 0.25, 0.1)):
        per = want_pt * factor / len(gaps)
        per = min(per, limit) if mode == 'grow' else max(per, limit)
        saved = []
        for g in gaps:
            v = max(0.0, base[g] + per)
            saved.append(_put(spec, p.section, g[0], g[1], v if g[0] == 'after' else v * PT))
        if ok(model.pages(spec, pic_dir)):
            return True
        _undo(spec, p.section, saved)
    return False
