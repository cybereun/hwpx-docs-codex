"""Reading units of pagefit: groups of blocks that should stay on ONE page when they fit on one (rules PF15-PF18).

A reader who has to turn back a page to finish a thought is the problem pagefit solves, so the unit is the thing to keep whole:
  heading     headings in a row + the first content block under them (a table, picture or box whole; a paragraph of 8 lines or fewer)
  item        one item (□, 1., 가. ...) with its sub items (○ -, 가. 1) ...): a block with an item mark and the deeper ones after it
  table       a table with its caption, the sentence that introduces it ("아래 표와 같이"), its unit line ("(단위: 원)") and notes
              under it ("※ ...", "주)", "자료:", "출처:")
  figure      a picture with its caption and notes
  box         bordered or filled paragraphs in a row (a summary box); a one-cell table is a table
  attach      "붙임" and its numbered lines, up to "끝."
  tail        the last paragraph, "끝." and what follows (발신 명의, 결재란, 결문)
  section     a heading with everything up to the next heading of its level or higher, when all of it is at most `section_ratio` of a page (weak)
  list        a run of numbered items of one level, at most `list_ratio` of a page (weak)
`strong` units are kept whole whenever they fit on a page; `weak` ones only while that does not leave a page empty (fix decides).
Item marks: the 개조식 marks □ ○ - · and the 공문 levels L1-L8 of gongmun-style (1. 가. 1) 가) (1) (가) ① ㉮, `levels.json` of that skill).
"""
import re

from . import model

# (system, level, pattern): 개조식 marks and the 공문 item levels L1-L8 (skills/gongmun-style/references/levels.json)
MARKS = [('gae', 1, r'^[□■◻▣]'), ('gae', 2, r'^[○●◎◯]'), ('gae', 3, r'^[-–—]\s'), ('gae', 4, r'^[·ㆍ•∙]'),
         ('gong', 1, r'^\d+\.\s'), ('gong', 2, r'^[가-힣]\.\s'), ('gong', 3, r'^\d+\)\s?'), ('gong', 4, r'^[가-힣]\)\s?'),
         ('gong', 5, r'^\(\d+\)'), ('gong', 6, r'^\([가-힣]\)'), ('gong', 7, r'^[①-⑳]'), ('gong', 8, r'^[㉮-㉻]')]
NOTE = re.compile(r'^\s*(※|주\)|주\s*:|\*\s|자료\s*:|출처\s*:|비고\s*:)')
CAPTION = re.compile(r'^\s*[<\[\(〈]?\s*(표|그림|도표|사진|도|Table|Figure|Fig\.)\s*\d*[\s\.\)\]>〉:：-]')
UNITLINE = re.compile(r'^\s*[\(\[<]?\s*단위\s*[:：]')
INTRO = re.compile(r'((아래|다음|위|앞|뒤)\s*의?\s*(표|그림|도표|사진)|(표|그림|도표)\s*\d*\s*(과|와)\s*같이|다음과 같|아래와 같|같습니다[\.\)]?\s*$|[:：]\s*$)')
END = re.compile(r'(^|\s)끝\.?\s*$')
ATTACH = re.compile(r'^\s*붙임')


class Unit:
    def __init__(self, kind, a, b, strong=True, why=''):
        self.kind, self.a, self.b, self.strong, self.why = kind, a, b, strong, why

    def __repr__(self):
        return f'Unit({self.kind} {self.a}-{self.b}{"" if self.strong else " weak"})'


def mark(b):
    """(system, level) of the item mark that starts a paragraph, or None."""
    if not isinstance(b, dict) or 'p' not in b:
        return None
    t = model.text_of(b, 40).lstrip()
    for sysm, lv, rx in MARKS:
        if re.match(rx, t):
            return sysm, lv
    n = b.get('number')
    if n is not None:
        return 'num', (n.get('level', 0) if isinstance(n, dict) else int(n)) + 1
    return None


def kind(b):
    if not isinstance(b, dict):
        return 'para'
    if 'table' in b:
        return 'table'
    if 'pic' in b and 'p' not in b:
        return 'figure'
    if 'p' in b and (b.get('border') or b.get('fill')):
        return 'box'
    return 'para'


def hkey(b):
    """Order of heading levels: the outline level, else the bigger the size the higher the level."""
    return float(b['outline_level']) if b.get('outline_level') is not None else -float(b.get('size', 10))


def find_units(body, heights, cap, size, section_ratio=0.4, list_ratio=0.5, item_ratio=0.8, heading_lines=8):
    """The reading units of one section: `body` the resolved blocks, `heights` the height (mm) of each block, `cap` the body height of
    a page, `size` the body text size. -> [Unit]"""
    n = len(body)
    text = [model.text_of(b, 400) if isinstance(b, dict) else '' for b in body]
    kinds = [kind(b) for b in body]
    head = [model.is_heading(b, size) for b in body]
    marks = [None if head[i] else mark(b) for i, b in enumerate(body)]
    units = []

    def h(a, b):
        return sum(heights[a:b + 1])

    # headings + the first content under them
    i = 0
    while i < n:
        if head[i]:
            j = i
            while j + 1 < n and head[j + 1]:
                j += 1
            if j + 1 < n:
                nxt = j + 1
                small = kinds[nxt] != 'para' or heights[nxt] <= heading_lines * 6.0
                units.append(Unit('heading', i, nxt if small else j, True, '제목과 그 아래 첫 내용'))
            i = j + 1
        else:
            i += 1
    # items with their sub items
    for i in range(n):
        if marks[i] is None or marks[i][0] == 'num':
            continue
        sysm, lv = marks[i]
        j = i
        while j + 1 < n and not head[j + 1] and (NOTE.match(text[j + 1]) or (marks[j + 1] and marks[j + 1][0] == sysm and marks[j + 1][1] > lv)):
            j += 1
        if j > i:
            if h(i, j) <= item_ratio * cap:
                units.append(Unit('item', i, j, True, '항목과 그 하위 항목'))
            else:
                units.append(Unit('item', i, i + 1, True, '항목과 그 첫 하위 항목'))
    # tables and figures with caption, introduction, unit line and notes
    for i in range(n):
        if kinds[i] not in ('table', 'figure'):
            continue
        a, b = i, i
        k = 0
        while a - 1 >= 0 and k < 3 and kinds[a - 1] == 'para' and not head[a - 1] and len(text[a - 1]) <= 200 and \
                (CAPTION.match(text[a - 1]) or UNITLINE.match(text[a - 1]) or INTRO.search(text[a - 1])
                 or (NOTE.match(text[a - 1]) and len(text[a - 1]) <= 60)):
            a -= 1
            k += 1
        k = 0
        while b + 1 < n and k < 3 and kinds[b + 1] == 'para' and not head[b + 1] and len(text[b + 1]) <= 200 and \
                (CAPTION.match(text[b + 1]) or NOTE.match(text[b + 1])):
            b += 1
            k += 1
        units.append(Unit(kinds[i], a, b, True, '표·그림과 그 캡션·소개 문장·주석'))
    # boxes
    i = 0
    while i < n:
        if kinds[i] == 'box':
            j = i
            while j + 1 < n and kinds[j + 1] == 'box':
                j += 1
            units.append(Unit('box', i, j, True, '요약 상자'))
            i = j + 1
        else:
            i += 1
    # 붙임 and the tail
    for i in range(n):
        if ATTACH.match(text[i]):
            j = i
            while j + 1 < n and not head[j + 1] and (END.search(text[j]) is None) and (marks[j + 1] == ('gong', 1) or END.search(text[j + 1])
                                                                                         or kinds[j + 1] == 'para' and len(text[j + 1]) < 60):
                j += 1
            if j > i:
                units.append(Unit('attach', i, j, True, '붙임 목록'))
    ends = [i for i in range(n) if END.search(text[i])]
    if ends:
        e = ends[-1]
        a = e - 1 if re.fullmatch(r'\s*끝\.?\s*', text[e]) and e > 0 else e
        if a < n - 1 or a != e:
            units.append(Unit('tail', a, n - 1, True, '마지막 문단·끝.·결문'))
    # short sections (weak)
    for i in range(n):
        if head[i]:
            j = i + 1
            while j < n and not (head[j] and hkey(body[j]) <= hkey(body[i])):
                j += 1
            j -= 1
            if j > i and h(i, j) <= section_ratio * cap:
                units.append(Unit('section', i, j, False, '짧은 절 전체'))
    # numbered lists (weak)
    i = 0
    while i < n:
        if marks[i] and marks[i][0] in ('gong', 'num'):
            j = i
            while j + 1 < n and marks[j + 1] == marks[i]:
                j += 1
            if j > i and h(i, j) <= list_ratio * cap:
                units.append(Unit('list', i, j, False, '번호 목록'))
            i = j + 1
        else:
            i += 1
    seen, out = set(), []
    for u in units:
        key = (u.kind, u.a, u.b)
        if key not in seen and (u.b > u.a or u.kind in ('table', 'figure')):
            seen.add(key)
            out.append(u)
    return merge(out, heights, cap)


def merge(units, heights, cap):
    """Strong units that share a block (a heading + its first content that is also the introduction of a table) are one reading unit when
    that fits on a page: kept apart they would each ask for a break of their own. Weak units stay as they are."""
    strong = sorted((u for u in units if u.strong), key=lambda u: (u.a, -u.b))
    out, cur = [u for u in units if not u.strong], None
    pending = []
    for u in strong:
        if cur is not None and u.a <= cur.b and sum(heights[cur.a:max(cur.b, u.b) + 1]) <= cap + 0.5:
            cur = Unit(cur.kind if cur.kind in ('table', 'figure') else u.kind if u.kind in ('table', 'figure') else cur.kind,
                       cur.a, max(cur.b, u.b), True, cur.why)
            continue
        if cur is not None:
            pending.append(cur)
        cur = u
    if cur is not None:
        pending.append(cur)
    return pending + out


def text_block(b):
    return kind(b) in ('para', 'box')


def wanted_flags(u, body, heights, cap):
    """The paragraph flags that hold unit `u` on one page in Hangul: ({block index: {key: value}}, tied). keep_next ties a paragraph to
    the next PARAGRAPH only (Hangul ignores it toward a table or a picture, measured), keep_lines keeps a paragraph whole, a table that
    fits a page gets `page_break: none`. tied is False when a table, picture or object follows a paragraph of the unit: flags cannot
    hold that unit, a page break before the unit does (fix adds it when the unit would be cut)."""
    out, tied = {}, True
    for i in range(u.a, u.b + 1):
        b, d = body[i], {}
        if text_block(b):
            if heights[i] <= cap:
                d['keep_lines'] = True
            if i < u.b:
                if text_block(body[i + 1]):
                    d['keep_next'] = True
                else:
                    tied = False
        else:
            if kind(b) == 'table' and heights[i] <= cap:
                d['page_break'] = 'none'
            if i < u.b and not text_block(body[i + 1]):
                tied = False                    # a heading box before a table, a table before a picture: no flag holds them (measured)
        out[i] = d
    return out, tied


def has_flags(b, want):
    t = b.get('table') if isinstance(b, dict) and isinstance(b.get('table'), dict) else {}
    return all((t.get('page_break') == v) if k == 'page_break' and t else (isinstance(b, dict) and b.get(k) == v) for k, v in want.items())


def realized(u, body, heights, cap):
    """True when the flags that hold the unit are all there (and no break is needed to tie it)."""
    want, tied = wanted_flags(u, body, heights, cap)
    ok = all(has_flags(body[i], d) for i, d in want.items())
    if tied:
        return ok
    first = body[u.a] if isinstance(body[u.a], dict) else {}
    return ok and bool(first.get('page_break') or first.get('page_break_before'))
