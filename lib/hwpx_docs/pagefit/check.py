"""pagefit check: what makes a reader turn the page back, and what makes a page look empty (rules PF03, PF15-PF20 in rules.md).

check(spec, pic_dir, fill=85, last_lines=3, min_rows=3, ...) -> ([Finding], pages); report(findings, pages) -> text lines. A finding has the
page number (1 = first page of the document), a kind and a Korean sentence. Kinds:
  unit        a reading unit that fits on one page is cut by a page break (units.py: heading + first content, item with its sub items,
              table with caption / introduction / notes, figure, box, 붙임, last paragraph with 끝. and the 결문)
  table_rows  a table longer than a page leaves fewer than `min_rows` rows on a page (the first or the last part)
  table_head  a table that goes on over a page has no header row to repeat (`header_rows` 0, or `repeat_header` off)
  table_cell  a table that goes on over a page may be cut inside a cell (`page_break` cell)
  table       a table is cut after its header row(s) only
  ref         a sentence that points at "표 3" / "그림 2" is not on the page of that table or figure
  note        a footnote goes on at the next page (pages of the preview's flow)
  order       a table kept whole (`page_break` none, no `hold`) does not fit and waits for the next page while the headings and text
              after it move up before it (Hangul; pages of the preview's flow): the reading order is broken (rules PF26)
  pageref     the text points at a page by number or direction (쪽, 다음 쪽, 앞 쪽): fixing may move it
  heading     a heading is the last thing on a page (its paragraph is on the next page)
  orphan_end / orphan_start   one line of a paragraph at the bottom of a page / one line carried over to the top of the next
  empty       a page except the last is filled less than `fill` percent (free space under the text in mm, and why the next page starts)
  last        the last page has `last_lines` lines or fewer
"""
import re

from . import model, units
from . import profile as prof_mod

WHY = {'forced_break': '강제 쪽 나눔', 'keep_next': '제목을 다음 문단과 함께 두려고', 'keep_lines': '문단을 한 쪽에 두려고',
       'widow': '외톨이 줄 보호', 'overflow': '다음 블록이 들어가지 않아서', 'split': '문단이 쪽을 넘어서', 'start': '새 구역',
       'table_group': '병합된 행을 나누지 않으려고'}
KIND_LABEL = {'heading': '제목과 첫 내용', 'item': '항목 묶음', 'table': '표와 그 캡션·소개 문장·주석', 'figure': '그림과 그 캡션',
              'box': '요약 상자', 'attach': '붙임 목록', 'tail': '마지막 문단과 끝.·결문', 'section': '짧은 절', 'list': '번호 목록'}
REF = re.compile(r'(표|그림)\s*(\d+)\s*(참조|와\s*같이|과\s*같이|에서|를\s*보|을\s*보|\)|와|과|의|은|는|이|가)')
LABEL = re.compile(r'^\s*[<\[\(〈]?\s*(표|그림)\s*(\d+)')
PAGEREF = re.compile(r'(\d+\s*쪽|\d+\s*페이지|(다음|앞|뒤|이전|위|아래)\s*(쪽|페이지)|(\d+)\s*p\.)')


class Finding:
    def __init__(self, page, kind, text, block=None, unit=None, **extra):
        self.page, self.kind, self.text, self.block, self.unit = page, kind, text, block, unit
        self.extra = extra

    def __str__(self):
        return f'쪽 {self.page}  [{self.kind}]  {self.text}'


def block_pages(pgs):
    """(section, block) -> [page numbers it is on]."""
    out = {}
    for p in pgs:
        for bi, k0, k1 in p.items:
            out.setdefault((p.section, bi), []).append(p.no)
    return out


def _cut_ok(u, info, where, T):
    """True when a unit is cut only the way the profile allows (`tables.split_gap_mm` on): its table may be cut between rows
    (`page_break` table, header rows repeat: fix gives that to a table of `split_min_ratio` of a page or more that would leave a big gap
    when moved whole, and every other table that fits a page gets `none`), and every block of the unit before the table is on the page
    where the table starts and every block after it on the page where the table ends."""
    if not (T['cut_between_rows'] and T['split_gap_mm'] > 0):
        return False
    sec = info['index']
    for i in range(u.a, u.b + 1):
        b = info['body'][i]
        t = b.get('table') if isinstance(b, dict) else None
        if not (isinstance(t, dict) and t.get('page_break') == 'table' and (not int(t.get('header_rows', 0) or 0) or t.get('repeat_header', True))):
            continue
        pg = where.get((sec, i), [])
        if pg and all(set(where.get((sec, j), [])) <= {pg[0]} for j in range(u.a, i)) \
                and all(set(where.get((sec, j), [])) <= {pg[-1]} for j in range(i + 1, u.b + 1)):
            return True
    return False


def check(spec, pic_dir='.', fill=None, last_lines=None, min_rows=None, section_ratio=None, list_ratio=None, weak=None, profile=None):
    """Findings of the document and its pages. With a `profile` (profile.py; a name, a path or a dict) only the kinds that profile lists
    are reported and its numbers are the defaults; without one every kind is reported (fix uses that to see everything). A keyword
    argument overrides one value; `weak` True also looks at weak units (short sections, numbered lists)."""
    P = prof_mod.load(profile if profile is not None else 'readable', fill=fill, last_lines=last_lines, min_rows=min_rows,
                      section_ratio=section_ratio, list_ratio=list_ratio)
    fill, last_lines = P['check']['fill'], P['check']['last_lines']
    min_rows = P['fix']['tables']['min_rows'] or 3
    section_ratio, list_ratio = P['fix']['units']['section_ratio'], P['fix']['units']['list_ratio']
    kinds = set(P['check']['kinds']) if profile is not None else None
    want = set(P['fix']['units']['strong']) | (set(P['fix']['units']['weak']) if (weak or (weak is None and profile is not None)) else set())
    if profile is None:
        want = set(prof_mod.STRONG_KINDS) | (set(prof_mod.WEAK_KINDS) if weak else set())
    pgs = model.pages(spec, pic_dir)
    infos = model.section_info(spec, pic_dir)
    bodies = [i['body'] for i in infos]
    size = model.body_size(spec)
    out = []
    total = {}                                  # (section, block) -> rows of the block over the whole document
    for p in pgs:
        for bi, k0, k1 in p.items:
            total[(p.section, bi)] = total.get((p.section, bi), 0) + k1 - k0
    where = block_pages(pgs)
    # reading units cut by a page break
    for info in infos:
        for u in units.find_units(info['body'], info['heights'], info['cap'], size, section_ratio, list_ratio):
            if u.kind not in want or not (u.strong or u.kind in want):
                continue
            if sum(info['heights'][u.a:u.b + 1]) > info['cap'] + 0.5:
                continue                                  # does not fit on a page: nothing to keep whole
            on = sorted({n for bi in range(u.a, u.b + 1) for n in where.get((info['index'], bi), [])})
            from_flow = any(p.renderer and p.section == info['index'] for p in pgs) and not model.renderer_keeps()      # a flow without the keep rules
            if len(on) > 1 and not (from_flow and units.realized(u, info['body'], info['heights'], info['cap'])) \
                    and not _cut_ok(u, info, where, P['fix']['tables']):
                out.append(Finding(on[0], 'unit', f'{KIND_LABEL[u.kind]}이(가) 쪽 {on[0]}·{on[-1]}에 걸쳐 나뉨: '
                                   f'"{model.text_of(info["body"][u.a], 30)}" — 읽다가 쪽을 넘겨야 함 ({u.why})', u.a, u))
    # tables that go over pages
    for (sec, bi), nums in where.items():
        b = bodies[sec][bi] if sec < len(bodies) else None
        if not (isinstance(b, dict) and 'table' in b) or len(nums) < 2:
            continue
        t = b['table']
        hr = int(t.get('header_rows', 0) or 0)
        rows_on = [(p.no, sum(k1 - k0 for bj, k0, k1 in p.items if bj == bi and p.section == sec)) for p in pgs
                   if any(bj == bi and p.section == sec for bj, _, _ in p.items)]
        if not hr or not t.get('repeat_header', True):
            out.append(Finding(nums[1], 'table_head', f'나뉜 표에 반복할 머리 행이 없음({"머리 행 지정 없음" if not hr else "제목 줄 반복 꺼짐"}): '
                               f'다음 쪽에서 열 이름이 안 보임', bi))
        if t.get('page_break', 'cell') == 'cell':
            out.append(Finding(nums[0], 'table_cell', '표가 쪽 경계에서 셀 중간을 나눌 수 있음(page_break: cell): 행 단위(table)로 바꾸는 편이 읽기 좋음', bi))
        for k, (no, rows) in enumerate(rows_on):
            body_rows = rows - hr if k == 0 else rows
            if k in (0, len(rows_on) - 1) and body_rows < min_rows:
                out.append(Finding(no, 'table_rows', f'표가 쪽 {no}에 {max(body_rows, 0)}행만 남음({"앞" if k == 0 else "뒤"}쪽 조각): '
                                   f'앞뒤 어느 쪽에도 {min_rows}행 이상 있어야 읽기 좋음', bi, which='first' if k == 0 else 'last',
                                   rows=max(body_rows, 0)))
    # references to tables and figures
    labels = {}
    for si, body in enumerate(bodies):
        for bi, b in enumerate(body):
            m = LABEL.match(model.text_of(b, 40)) if isinstance(b, dict) else None

            def is_obj(j):
                return 0 <= j < len(body) and isinstance(body[j], dict) and ('table' in body[j] or 'pic' in body[j])
            if m and (is_obj(bi + 1) or is_obj(bi - 1)):         # a caption sits right before or after its table or picture
                labels[(si, m.group(1), m.group(2))] = bi + 1 if is_obj(bi + 1) else bi - 1
    for si, body in enumerate(bodies):
        for bi, b in enumerate(body):
            if not isinstance(b, dict) or 'p' not in b or (bi in {v for k, v in labels.items() if k[0] == si} or any(
                    labels.get((si, k[1], k[2])) in (bi - 1, bi + 1) and LABEL.match(model.text_of(b, 40)) for k in [()] if False)):
                continue
            if LABEL.match(model.text_of(b, 40)) and any(isinstance(body[j], dict) and ('table' in body[j] or 'pic' in body[j])
                                                          for j in (bi - 1, bi + 1) if 0 <= j < len(body)):
                continue                                          # a caption
            text = model.text_of(b, 400)
            for m in REF.finditer(text):
                tgt = labels.get((si, m.group(1), m.group(2)))
                mine, theirs = set(where.get((si, bi), [])), set(where.get((si, tgt), [])) if tgt is not None else set()
                if tgt is not None and mine and theirs and not (mine & theirs):
                    out.append(Finding(min(mine), 'ref', f'"{m.group(1)} {m.group(2)}"를 가리키는 문장(쪽 {min(mine)})과 그 {m.group(1)}'
                                       f'(쪽 {min(theirs)})이 다른 쪽에 있음', bi))
            pr = PAGEREF.search(text)
            if pr and where.get((si, bi)):
                out.append(Finding(where[(si, bi)][0], 'pageref', f'쪽을 가리키는 말이 있음("{pr.group(0)}"): 고친 뒤 쪽이 바뀌었는지 확인 필요', bi))
    # footnotes that go on at the next page; tables kept whole that wait for a later page while the text after them moves up
    for p in pgs:
        if getattr(p, 'notes_cont', False):
            out.append(Finding(p.no, 'note', '각주가 다음 쪽으로 이어짐: 본문과 각주를 한 쪽에서 읽을 수 없음'))
        for bi in getattr(p, 'deferred', ()):
            out.append(Finding(p.no, 'order', f'통째로 둔 표가 들어가지 않아 다음 쪽으로 넘어가고 그 뒤 제목·문단이 표보다 앞에 놓임'
                               f'(읽는 순서 바뀜): "{model.text_of(bodies[p.section][bi - 1], 24) if bi else "[표]"}" 다음의 표 — '
                               f'표에 "개체와 조판 부호를 항상 같은 쪽에 놓기"(hold)를 켜면 막힘', bi))
    # headings, single lines, tables cut after the header, empty pages, short last page
    for n, p in enumerate(pgs):
        if p.skipped:
            out.append(Finding(p.no, 'skipped', '세로쓰기 구역은 검사하지 않음'))
            continue
        body = bodies[p.section]
        nxt = pgs[n + 1] if n + 1 < len(pgs) else None
        last = nxt is None
        if not last and p.fill * 100 < fill:
            why = WHY.get(nxt.why, nxt.why)
            out.append(Finding(p.no, 'empty', f'본문 {p.fill * 100:.0f}% 채움, 아래 {p.free:.0f} mm 비어 있음'
                               + (f' (다음 쪽은 {why}로 시작)' if why else '')))
        if not p.items:
            continue
        bi, k0, k1 = p.items[-1]
        lines = total[(p.section, bi)]
        b = body[bi]
        cont = bool(nxt and nxt.section == p.section and nxt.items and nxt.items[0][0] == bi and k1 < lines)     # goes on next page
        guarded = p.renderer and not model.renderer_keeps()      # a flow without keep_next / widow: Hangul applies them when the block says so
        if not last and not cont and model.is_heading(b, size) and not (guarded and model.flags(b)['keep_next']):
            out.append(Finding(p.no, 'heading', f'쪽 맨 아래에 제목만 남음: "{model.text_of(b)}" (다음 문단과 떨어짐)', bi))
        elif not last and not cont and isinstance(b, dict) and b.get('keep_next') and nxt.why == 'forced_break' \
                and nxt.section == p.section and nxt.items:
            out.append(Finding(p.no, 'heading', f'"다음과 함께" 블록이 쪽 맨 아래에 남음: "{model.text_of(b)}" — 다음 블록이 강제 쪽 나눔으로 '
                               f'시작해 한글이 둘을 붙이지 않음(쪽 나눔은 그 제목·소개 문장 묶음의 맨 앞에 걸어야 함)', bi))
        if not last and cont and lines >= 2 and k0 == 0 and k1 == 1 and b.get('p') is not None \
                and not (guarded and model.flags(b)['widow']):
            out.append(Finding(p.no, 'orphan_end', f'쪽 맨 아래에 문단의 한 줄만 남음: "{model.text_of(b)}"', bi))
        if isinstance(b, dict) and 'table' in b and cont and k0 == 0:
            t = b['table']
            hr = int(t.get('header_rows', 1 if t.get('repeat_header', True) else 0))
            if hr and k1 <= hr:
                out.append(Finding(p.no, 'table', f'표가 쪽 끝에서 머리 행({k1}행)만 남고 잘림', bi))
        bi, k0, k1 = p.items[0]
        if k0 > 0 and k1 == total[(p.section, bi)] and k1 - k0 == 1 and not (isinstance(body[bi], dict) and 'table' in body[bi]) \
                and not (guarded and model.flags(body[bi])['widow']):
            out.append(Finding(p.no, 'orphan_start', f'쪽 맨 위에 문단의 한 줄만 넘어옴: "{model.text_of(body[bi])}"', bi))
        if last and len(pgs) > 1:
            rows = sum(k1 - k0 for _, k0, k1 in p.items)
            if rows <= last_lines:
                out.append(Finding(p.no, 'last', f'마지막 쪽에 {rows}줄만 있음'))
    out.sort(key=lambda f: (f.page, f.kind))
    if kinds is not None:
        out = [f for f in out if f.kind in kinds]
    return out, pgs


def report(findings, pgs, fill=85):
    lines = [f'쪽 수 {len(pgs)}  쪽별 채움: ' + ' '.join(f'{p.fill * 100:.0f}%' for p in pgs)]
    lines += [str(f) for f in findings]
    warn = {'pageref', 'skipped'}
    lines.append(f'점검 결과: 문제 {sum(1 for f in findings if f.kind not in warn)}건, 확인 {sum(1 for f in findings if f.kind == "pageref")}건 '
                 f'(기준: 마지막 쪽 빼고 채움 {fill}% 이상)')
    return lines
