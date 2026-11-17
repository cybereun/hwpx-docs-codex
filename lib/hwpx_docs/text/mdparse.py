"""Markdown parser of the report presets (개조식 보고서, 공문). The design values used by markdown.py come from
presets/<name>.json; the constants below are the values of the default preset report-gongmun.

Markdown subset:
  # 제목                  -> title box          > 부제              -> subtitle (before the body)
  작성일: 2026. 11. 16.(월) -> date line          문서: 문서 표시     -> small line above the title
  ◇ 요약 문장             -> summary box         ## Ⅰ. 장 제목      -> chapter heading
  ## 붙임 1. ...          -> attachment heading (new page)
  ### 항목                -> □ item              #### 소제목         -> small heading
  - 글 / 하위 - 글         -> ○ / - / · levels   - [ ] 글 / - [x] 글 -> ☐ / ☑ check box
  1. 글                   -> numbered item       ※ 글               -> note
  | 표 |                  -> table (first row = header; empty cells keep a writing space)
  ```                     -> code block          끝.                 -> end mark
  **굵게**, `코드`         -> bold, code
"""
import re

NAVY = '#1F3864'

# Text styles: font ('batang', 'dotum', 'mono'), size in pt, bold, color, align,
# left margin pt, first-line indent pt (negative = hanging), space before pt, space after pt, line spacing %.
TEXT = {
    'docno':    dict(font='dotum',  size=10,   bold=False, color='#333333', align='LEFT',    left=0,  indent=0,   before=0, after=4,  line=160),
    'title':    dict(font='dotum',  size=22,   bold=True,  color='#000000', align='CENTER',  left=0,  indent=0,   before=0, after=0,  line=135),
    'subtitle': dict(font='dotum',  size=12.5, bold=False, color='#000000', align='CENTER',  left=0,  indent=0,   before=5, after=0,  line=160),
    'date':     dict(font='batang', size=11.5, bold=False, color='#000000', align='RIGHT',   left=0,  indent=0,   before=6, after=12, line=160),
    'summary':  dict(font='batang', size=12,   bold=False, color='#000000', align='JUSTIFY', left=15, indent=-15, before=2, after=2,  line=160),
    'chapter':  dict(font='dotum',  size=15,   bold=True,  color='#000000', align='LEFT',    left=0,  indent=0,   before=0, after=0,  line=160),
    'attach':   dict(font='dotum',  size=13,   bold=True,  color='#000000', align='LEFT',    left=0,  indent=0,   before=0, after=0,  line=160),
    'item':     dict(font='dotum',  size=12.5, bold=True,  color='#000000', align='JUSTIFY', left=16, indent=-16, before=9, after=2,  line=160),
    'sub':      dict(font='dotum',  size=11,   bold=True,  color='#000000', align='LEFT',    left=0,  indent=0,   before=7, after=1,  line=160),
    'l0':       dict(font='batang', size=12,   bold=False, color='#000000', align='JUSTIFY', left=31, indent=-15, before=2, after=2,  line=160),
    'l1':       dict(font='batang', size=11.5, bold=False, color='#000000', align='JUSTIFY', left=43, indent=-11, before=1, after=1,  line=160),
    'l2':       dict(font='batang', size=11,   bold=False, color='#000000', align='JUSTIFY', left=55, indent=-11, before=1, after=1,  line=160),
    'note':     dict(font='batang', size=10.5, bold=False, color='#222222', align='JUSTIFY', left=31, indent=-15, before=3, after=2,  line=160),
    'para':     dict(font='batang', size=12,   bold=False, color='#000000', align='JUSTIFY', left=0,  indent=0,   before=3, after=3,  line=160),
    'th':       dict(font='dotum',  size=10.5, bold=True,  color='#000000', align='CENTER',  left=0,  indent=0,   before=0, after=0,  line=145),
    'td':       dict(font='batang', size=10.5, bold=False, color='#000000', align='LEFT',    left=0,  indent=0,   before=0, after=0,  line=145),
    'code':     dict(font='mono',   size=9.5,  bold=False, color='#000000', align='LEFT',    left=0,  indent=0,   before=0, after=0,  line=140),
    'end':      dict(font='batang', size=12,   bold=False, color='#000000', align='RIGHT',   left=0,  indent=0,   before=14, after=0, line=160),
    'gap':      dict(font='batang', size=4,    bold=False, color='#000000', align='LEFT',    left=0,  indent=0,   before=0, after=0,  line=100),
}

# Boxes: border (top, right, bottom, left) as (width, color) or None, fill color or None, cell padding pt (top, right, bottom, left).
THIN, THICK = ('0.5pt', '#000000'), ('1.5pt', '#000000')
BOX = {
    'title':   dict(sides=(('3pt', NAVY), None, ('3pt', NAVY), None), fill=None, pad=(12, 6, 11, 6)),
    'summary': dict(sides=(('1pt', '#000000'),) * 4, fill='#F2F2F2', pad=(8, 12, 8, 12)),
    'bar':     dict(sides=(None,) * 4, fill=NAVY, pad=(0, 0, 0, 0)),
    'chapter': dict(sides=(None, None, ('1pt', NAVY), None), fill='#EEF1F6', pad=(3, 8, 2, 8)),
    'attach':  dict(sides=(None, None, THICK, None), fill=None, pad=(0, 0, 3, 0)),
    'code':    dict(sides=(THIN,) * 4, fill='#F7F7F7', pad=(5, 8, 5, 8)),
}
CELL_PAD = (3.5, 5, 3.5, 5)
HEAD_FILL = '#D9D9D9'
BLANK_ROW_PT = 20
BAR_WIDTH_PT = 6
PAGE = dict(width_mm=210, height_mm=297, left_mm=20, right_mm=20, top_mm=20, bottom_mm=15)

LIST_MARK = ['○ ', '- ', '· ']


def segments(text):
    """Split inline text into (kind, text) with kind in 'n' (normal), 'b' (bold), 'c' (code)."""
    out = []
    for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', text):
        if not part:
            continue
        if part.startswith('`') and part.endswith('`'):
            out.append(('c', part[1:-1]))
        elif part.startswith('**') and part.endswith('**'):
            out.append(('b', part[2:-2]))
        else:
            out.append(('n', part))
    return out


def cells(row):
    return [c.strip() for c in row.strip().strip('|').split('|')]


def col_fractions(head, rows, hint=None):
    """Column width fractions. hint = dash counts of the Markdown separator row (|---|------|);
    when the counts differ, they set the widths; else the widths follow the text length."""
    if hint and len(hint) == len(head) and len(set(hint)) > 1:
        weights = list(hint)
    else:
        weights = []
        for c, h in enumerate(head):
            texts = [r[c] for r in rows if c < len(r) and r[c]]
            avg = sum(len(t) for t in texts) / len(texts) if texts else 0
            weights.append(max(len(h) * 1.3, min(avg, 40), 3))
    s = sum(weights)
    return [w / s for w in weights]


def parse(md):
    """Return (meta, blocks). meta: title, subtitles, date, docno, summary.
    blocks: ('chapter', text) ('attach', text) ('item', text) ('sub', text) ('list', level, mark, text)
            ('note', text) ('para', text) ('table', head, rows, fractions) ('code', lines) ('end',)"""
    meta = dict(title='', subtitles=[], date='', docno='', summary=[])
    blocks, lines, i = [], md.split('\n'), 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        indent = len(raw) - len(raw.lstrip(' '))
        i += 1
        if not s or s == '---':
            continue
        if s.startswith('```'):
            block = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i])
                i += 1
            i += 1
            blocks.append(('code', block))
            continue
        if s.startswith('|'):
            rows = [raw]
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(lines[i])
                i += 1
            sep = len(rows) > 1 and re.match(r'^\|[\s:|-]+\|?$', rows[1].strip())
            hint = [c.count('-') for c in cells(rows[1])] if sep else None
            head, body = cells(rows[0]), [cells(r) for r in rows[(2 if sep else 1):]]
            blocks.append(('table', head, body, col_fractions(head, body, hint)))
            continue
        m = re.match(r'^(#{1,4}) (.*)$', s)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not meta['title']:
                meta['title'] = text
            elif level == 2:
                blocks.append(('attach' if text.startswith('붙임') else 'chapter', text))
            elif level == 3:
                blocks.append(('item', text if text.startswith('□') else '□ ' + text))
            else:
                blocks.append(('sub', text))
            continue
        if not blocks:
            if s.startswith('>'):
                meta['subtitles'].append(s.lstrip('> ').strip())
                continue
            m = re.match(r'^(작성일|날짜)\s*[:：]\s*(.*)$', s)
            if m:
                meta['date'] = m.group(2)
                continue
            m = re.match(r'^문서\s*[:：]\s*(.*)$', s)
            if m:
                meta['docno'] = m.group(1)
                continue
        if s.startswith('◇'):
            meta['summary'].append(s)
            continue
        if s == '끝.':
            blocks.append(('end',))
            continue
        if s.startswith('※'):
            blocks.append(('note', s))
            continue
        lvl = min(indent // 2, 2)
        m = re.match(r'^- \[( |x|X)\] (.*)$', s)
        if m:
            blocks.append(('list', lvl, '☑ ' if m.group(1).lower() == 'x' else '☐ ', m.group(2)))
            continue
        m = re.match(r'^- (.*)$', s)
        if m:
            blocks.append(('list', lvl, LIST_MARK[lvl], m.group(1)))
            continue
        m = re.match(r'^(\d+)\. (.*)$', s)
        if m:
            blocks.append(('list', lvl, m.group(1) + '. ', m.group(2)))
            continue
        blocks.append(('para', s))
    return meta, blocks


def selftest():
    md = '\n'.join(['# 제목', '> 부제', '작성일: 2026. 11. 16.(월)', '◇ 요약', '## Ⅰ. 장', '### 항목', '- 하나',
                    '  - 둘', '- [ ] 체크', '| 가 | 나 |', '|---|---|', '| 1 |  |', '※ 참고', '## 붙임 1. 표',
                    '```', 'code', '```', '**굵게** 와 `코드`', '끝.'])
    meta, blocks = parse(md)
    assert meta['title'] == '제목' and meta['subtitles'] == ['부제'] and meta['date'] == '2026. 11. 16.(월)'
    assert meta['summary'] == ['◇ 요약']
    kinds = [b[0] for b in blocks]
    assert kinds == ['chapter', 'item', 'list', 'list', 'list', 'table', 'note', 'attach', 'code', 'para', 'end'], kinds
    assert blocks[1] == ('item', '□ 항목') and blocks[3][2] == '- ' and blocks[4][2] == '☐ '
    assert blocks[5][:3] == ('table', ['가', '나'], [['1', '']])
    assert segments('**굵게** 와 `코드`') == [('b', '굵게'), ('n', ' 와 '), ('c', '코드')]
    _, b2 = parse('| a | b |\n|-|---|\n| 1 | 2 |')
    assert [round(f, 2) for f in b2[0][3]] == [0.25, 0.75], b2
    print('GONGMUN_MD SELFTEST PASS')


if __name__ == '__main__':
    selftest()
