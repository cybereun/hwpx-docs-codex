"""Markdown -> HWPX in the style of a preset (default "report-gongmun"), through the generic builder.

  hd md <in.md> <out.hwpx> [--preset <name>|<file.json>] [--spec out.json] [--fallback] [--keep]
  hd md --selftest

The Markdown parser is mdparse.py; the design values are data in presets/<name>.json (skill hwpx-text,
references/presets.md). Markdown that the parser has no block for (h5, a body blockquote, a picture, a 4th list
level, a footnote, a link, italic, ...) is UNMAPPED unless the preset's MAP names a style for it: the default mode
lists it and stops (exit 2); --fallback uses the nearest preset style, else a core feature, else plain text, and logs
each choice. Text rules (wording, item symbols, 끝.) belong to skill gongmun-style.
"""
from ..core import tmpdir
import json
import os
import re
import sys
import types

from ..text import mdparse as G
from ..core import build as hwpx_build

HERE = os.path.dirname(os.path.abspath(__file__))
PRESET_DIR = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'presets'))     # <plugin>/presets
P = None    # the preset in use: TEXT, BOX, PAGE, FONT, BORDER, ... (names of mdparse.py)


def load_preset(name='report-gongmun'):
    """presets/<name>.json, or a path to a preset JSON -> the preset in use.
    LAYOUT "css" (default): the values are CSS values of an HTML design and css_layout() gives the browser's layout;
    "hangul": the values are Hangul's own (a preset made from an HWPX with preset_from.py)."""
    global P, CSS
    path = name if name.lower().endswith('.json') else os.path.join(PRESET_DIR, name + '.json')
    P = types.SimpleNamespace(**json.load(open(path, encoding='utf-8')))
    CSS = getattr(P, 'LAYOUT', 'css') == 'css'
    return P


ROLES_TEXT = ('docno', 'title', 'subtitle', 'date', 'summary', 'chapter', 'attach', 'item', 'sub', 'l0', 'l1', 'l2',
              'note', 'para', 'th', 'td', 'code', 'end', 'gap')
ROLES_BOX = ('title', 'summary', 'bar', 'chapter', 'attach', 'code')
KEYS = ('FONT', 'BORDER', 'PAGE', 'TEXT', 'BOX', 'THIN', 'THICK', 'CELL_PAD', 'HEAD_FILL', 'BLANK_ROW_PT',
        'BAR_WIDTH_PT', 'LIST_MARK', 'MAP')


def check_preset():
    """-> list of what the preset in use lacks (a draft from preset_from.py before its roles are set)."""
    miss = [f'key {k}' for k in KEYS if not hasattr(P, k)]
    miss += [f'TEXT role {r}' for r in ROLES_TEXT if r not in getattr(P, 'TEXT', {})]
    miss += [f'BOX role {r}' for r in ROLES_BOX if r not in getattr(P, 'BOX', {})]
    return miss


def char(name, kind='n'):
    t = P.TEXT[name]
    d = dict(font=P.FONT.get(t['font'], t['font']), size=t['size'], bold=t['bold'], color=t['color'])
    if t['font'] == 'mono':
        d['font_latin'] = 'Consolas'
    if kind == 'b':
        d['bold'] = True
    elif kind == 'c':
        d.update(font=P.FONT.get('mono', '굴림체'), font_latin='Consolas', size=9.5)
    return d


def para(name, text='', **over):
    """One paragraph block in style `name`; **bold** and `code` become runs."""
    t = dict(P.TEXT[name], **over)
    # CSS hanging indent: first line at left + indent, other lines at left. Hangul: first line at left, other lines at
    # left + |indent| (rules.md H25). So Hangul left = CSS left + indent when the indent is negative.
    left = t['left'] + t['indent'] if (CSS and t['indent'] < 0) else t['left']
    b = dict(char(name), align=t['align'].lower(), left=left, indent=t['indent'], before=t['before'],
             after=t['after'], line=t['line'])
    if 'word_break' in t:
        b['word_break'] = t['word_break']
    segs = G.segments(text) if text else []
    if len(segs) == 1 and segs[0][0] == 'n':
        b['p'] = segs[0][1]
    elif segs:
        b['p'] = [dict(t=s, **char(name, k)) if k != 'n' else s for k, s in segs]
    else:
        b['p'] = ''
    return b


def side(s):
    return 'none' if not s else f'{P.BORDER.get(s[0], s[0])} solid {s[1]}'


def box(kind, blocks, width_mm, page_break=False):
    bx = P.BOX[kind]
    top, right, bottom, left = (side(s) for s in bx['sides'])
    cell = {'blocks': blocks, 'border': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
            'pad': [f'{bx["pad"][3]}pt', f'{bx["pad"][1]}pt', f'{bx["pad"][0]}pt', f'{bx["pad"][2]}pt']}
    if bx['fill']:
        cell['fill'] = bx['fill']
    b = dict(para('gap'), table={'cols': [width_mm], 'border': 'none', 'margin': 0, 'rows': [[cell]]})
    b.pop('p')
    if page_break:
        b['page_break'] = True
    return b


def gap(pt):
    return para('gap', before=pt)


def spec(md, fallback=False, base_dir='.', log=print):
    """Markdown -> spec. Returns (spec, unmapped); with unmapped parts and no fallback the spec is None."""
    found = scan(md)
    unmapped = [f for f in found if resolve(f[1])[0] is None]
    if unmapped and not fallback:
        return None, unmapped
    md, notes = rewrite(md, found, log if fallback else None)
    meta, blocks = G.parse(md)
    return spec_from(meta, retag(blocks), notes, base_dir), unmapped


def spec_from(meta, blocks, notes=None, base_dir='.'):
    p = P.PAGE
    W = p['width_mm'] - p['left_mm'] - p['right_mm']
    body = [para('docno', meta['docno'])] if meta['docno'] else []      # "문서: ..." line of the Markdown
    body.append(box('title', [para('title', meta['title'])] + [para('subtitle', s) for s in meta['subtitles']], W))
    body.append(para('date', meta['date']) if meta['date'] else gap(8))
    if meta['summary']:
        body.append(box('summary', [para('summary', s) for s in meta['summary']], W))
    thin, thick = side(P.THIN), side(P.THICK)
    for b in blocks:
        kind = b[0]
        if kind == 'chapter':
            body.append(gap(10))
            bar, chap = P.BOX['bar'], P.BOX['chapter']
            bar_w = P.BAR_WIDTH_PT * 25.4 / 72
            cells = [{'blocks': [para('gap')], 'fill': bar['fill'], 'border': 'none', 'pad': 0},
                     {'blocks': [para('chapter', b[1])], 'fill': chap['fill'],
                      'border': {'bottom': side(chap['sides'][2]), 'top': 'none', 'left': 'none', 'right': 'none'},
                      'pad': [f'{chap["pad"][3]}pt', f'{chap["pad"][1]}pt', f'{chap["pad"][0]}pt', f'{chap["pad"][2]}pt']}]
            t = dict(para('gap'), table={'cols': [bar_w, W - bar_w], 'border': 'none', 'margin': 0, 'rows': [cells]})
            t.pop('p')
            body.append(t)
            body.append(gap(4))
        elif kind == 'attach':
            body.append(box('attach', [para('attach', b[1])], W, page_break=True))
            body.append(gap(4))
        elif kind == 'pic':
            body.append(picture(b[1], b[2], W, base_dir))
        elif kind not in ('list', 'end', 'code', 'table') and kind in P.TEXT:
            body.append(para(kind, b[1]))           # item, sub, note, para, or a style named by the preset MAP
        elif kind == 'list':
            _, lvl, mark, text = b
            if lvl < len(G.LIST_MARK) and mark == G.LIST_MARK[lvl] and lvl < len(P.LIST_MARK):
                mark = P.LIST_MARK[lvl]
            body.append(para(f'l{lvl}', mark + text))
        elif kind == 'end':
            body.append(para('end', '끝.'))
        elif kind == 'code':
            body.append(box('code', [para('code', line or ' ') for line in b[1]], W))
        elif kind == 'table':
            head, rows, fr = b[1], b[2], b[3]
            cols = [W * f for f in fr]
            pad = [f'{P.CELL_PAD[3]}pt', f'{P.CELL_PAD[1]}pt', f'{P.CELL_PAD[0]}pt', f'{P.CELL_PAD[2]}pt']
            grid = [[dict(blocks=[para('th', h)], fill=P.HEAD_FILL, pad=pad, border={'top': thick}) for h in head]]
            for n, r in enumerate(rows):
                r = r + [''] * (len(head) - len(r))
                row = []
                for c in r[:len(head)]:
                    cell = dict(blocks=[para('td', c)], pad=pad)
                    if n == len(rows) - 1:
                        cell['border'] = {'bottom': thick}
                    row.append(cell)
                grid.append(row)
            # the design: a cell is 1000 hu high, an empty cell BLANK_ROW_PT; the row takes the highest cell
            # (Hangul grows a row that needs more room for its text)
            def row_pt(r):
                return max((10 if c else P.BLANK_ROW_PT) for c in (r + [''] * (len(head) - len(r)))[:len(head)])
            heights = [10 * 25.4 / 72] + [row_pt(r) * 25.4 / 72 for r in rows]
            t = dict(para('gap'), table={'cols': cols, 'border': thin, 'margin': 0, 'rows': grid, 'header_rows': 1,
                                         'heights': heights})
            t.pop('p')
            body.append(gap(3))
            body.append(t)
            body.append(gap(4))
    s = {'title': meta['title'],
         'page': {'size': [p['width_mm'], p['height_mm']],
                  'margin': {'left': p['left_mm'], 'right': p['right_mm'], 'top': p['top_mm'], 'bottom': p['bottom_mm'],
                             'header': 0, 'footer': 0}},
         # word_break "word": the HTML has CSS word-break: keep-all (breaks only between words)
         'defaults': dict(char('para'), align='justify', line=160, word_break='word' if CSS else 'char'),
         'body': [expand_runs(b, notes or {}) for b in body]}
    return css_layout(s, W) if CSS else s


load_preset()   # sets P and CSS (True = the browser's layout of the HTML; False = Hangul spacing)


# ---------------------------------------------------------------- Markdown that the parser has no block for

# element -> (nearest preset style, core feature, plain text): resolve() takes the first one that the preset has
FALLBACK = {
    'h5': ('sub', None, 'paragraph'), 'h6': ('sub', None, 'paragraph'),
    'blockquote': ('note', None, 'paragraph'), 'list3': ('l2', None, 'paragraph'),
    'star_list': ('l0', None, 'paragraph'),
    'image': (None, 'picture', 'alt text'), 'footnote': (None, 'footnote', 'text in brackets'),
    'link': (None, 'hyperlink', 'link text'), 'italic': (None, 'italic run', 'text'),
    'hr': (None, None, 'left out'), 'html': (None, None, 'text without tags'),
}
WHAT = {'h5': 'heading level 5', 'h6': 'heading level 6', 'blockquote': 'blockquote in the body',
        'list3': 'list level 4 or deeper', 'star_list': 'list with * or + marker', 'image': 'picture',
        'footnote': 'footnote', 'link': 'link', 'italic': 'italic text', 'hr': 'horizontal rule ***',
        'html': 'inline HTML tag'}
RE = {
    'image': re.compile(r'!\[([^\]]*)\]\(([^)\s]+)[^)]*\)'),
    'footnote': re.compile(r'\[\^([^\]]+)\]'),
    'link': re.compile(r'(?<!!)\[([^\]^][^\]]*)\]\(([^)\s]+)[^)]*\)'),
    'italic': re.compile(r'(?<![*\w])\*(?=[^*\s])([^*\n]+?)(?<=\S)\*(?![*\w])|(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)'),
    'html': re.compile(r'</?[a-zA-Z][^>]*>'),
}


def resolve(el):
    """-> (how, value): ('map', style) from the preset MAP, or (None, None) when UNMAPPED."""
    v = (getattr(P, 'MAP', {}) or {}).get(el)
    return ('map', v) if v else (None, None)


def fallback_of(el):
    """--fallback choice: nearest preset style, else a core feature, else plain text."""
    style, core, plain = FALLBACK[el]
    if style and style in P.TEXT:
        return 'style', style
    if core:
        return 'core', core
    return 'plain', plain


def scan(md):
    """-> [(line, element, text)] for the Markdown that gongmun_md.parse turns into no block of its own."""
    out, code, body = [], False, False
    for n, raw in enumerate(md.split('\n'), 1):
        s = raw.strip()
        if s.startswith('```'):
            code, body = not code, True
            continue
        if code or not s or s == '---':
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        meta = (s.startswith(('# ', '◇')) or (not body and (s.startswith('>') or
                re.match(r'^(작성일|날짜|문서)\s*[:：]', s))))
        if re.match(r'#{5,6} ', s):
            out.append((n, f'h{len(s.split()[0])}', s))
        elif s.startswith('>') and body:
            out.append((n, 'blockquote', s))
        elif re.match(r'[*+] ', s):
            out.append((n, 'star_list', s))
        elif re.match(r'(\*\s*){3,}$|(_\s*){3,}$', s):
            out.append((n, 'hr', s))
        if re.match(r'([-*+]|\d+\.) ', s) and indent // 2 >= 3:
            out.append((n, 'list3', s))
        for el in ('image', 'footnote', 'link', 'italic', 'html'):
            if RE[el].search(s if el != 'italic' else re.sub(r'^[*+] ', '', s)):
                out.append((n, el, s))
        body = body or not meta
    return out


def rewrite(md, found, log):
    """Rewrite the UNMAPPED parts into what gongmun_md.parse reads; a style block is the line "\\x01style\\x01text".
    Footnote, link and italic become placeholders that expand_runs() turns into runs. Returns (md, notes)."""
    lines = md.split('\n')
    notes = {}
    seen = set()
    for n, el, _ in found:
        how, val = resolve(el)
        if how is None:
            how, val = fallback_of(el)
            if log and (n, el) not in seen:
                log(f'FALLBACK line {n}: {WHAT[el]} -> {how} {val}')
        seen.add((n, el))
        raw = lines[n - 1]
        s, ind = raw.strip(), raw[:len(raw) - len(raw.lstrip(' '))]
        style = val if how in ('map', 'style') and val in P.TEXT else None
        if el in ('h5', 'h6', 'blockquote'):
            text = s.lstrip('#> ').strip()
            lines[n - 1] = f'\x01{style}\x01{text}' if style else text
        elif el == 'star_list':
            lines[n - 1] = ind + '- ' + s[2:]
        elif el == 'list3' and style and style != 'l2':
            m = re.match(r'([-*+]|\d+\.) (.*)', s)
            mark = (m.group(1) + ' ') if m.group(1)[0].isdigit() else ''
            lines[n - 1] = f'\x01{style}\x01{mark}{m.group(2)}'
        elif el == 'hr':
            lines[n - 1] = ''
        elif el == 'image':
            m = RE['image'].fullmatch(s)
            if m and how != 'plain':
                lines[n - 1] = f'\x01@pic\x01{m.group(2)}\x01{m.group(1)}'
            else:
                lines[n - 1] = RE['image'].sub(lambda m: m.group(1), raw)
        elif el == 'footnote':
            m = re.match(r'\[\^([^\]]+)\]:\s*(.*)', s)
            if m:
                notes[m.group(1)] = m.group(2)
                lines[n - 1] = ''
            else:
                lines[n - 1] = RE['footnote'].sub(
                    (lambda m: f'\x02{m.group(1)}\x02') if how != 'plain' else (lambda m: f'[{m.group(1)}]'), raw)
        elif el == 'link':
            lines[n - 1] = RE['link'].sub(
                (lambda m: f'\x03{m.group(1)}\x04{m.group(2)}\x03') if how != 'plain' else (lambda m: m.group(1)), raw)
        elif el == 'italic':
            lines[n - 1] = RE['italic'].sub(
                lambda m: (f'\x05{m.group(1) or m.group(2)}\x05' if how != 'plain' else (m.group(1) or m.group(2))), raw)
        elif el == 'html':
            lines[n - 1] = RE['html'].sub('', raw)
    return '\n'.join(lines), notes


def retag(blocks):
    """("para", "\\x01style\\x01text") -> (style, text); a picture line -> ("pic", src, alt)."""
    out = []
    for b in blocks:
        if b[0] == 'para' and b[1].startswith('\x01'):
            _, style, rest = b[1].split('\x01', 2)
            out.append(('pic', *rest.split('\x01', 1)) if style == '@pic' else (style, rest))
        else:
            out.append(b)
    return out


def expand_runs(b, notes):
    """Placeholders in text -> runs: \\x02id\\x02 footnote, \\x03text\\x04url\\x03 link, \\x05text\\x05 italic."""
    if 'table' in b:
        for row in b['table'].get('rows', []):
            for cell in row:
                if isinstance(cell, dict) and 'blocks' in cell:
                    cell['blocks'] = [expand_runs(x, notes) for x in cell['blocks']]
        return b
    p = b.get('p')
    flat = p if isinstance(p, str) else ''.join(x if isinstance(x, str) else str(x.get('t', '')) for x in p or [])
    if not any(c in flat for c in '\x02\x03\x05'):
        return b
    out = []
    for r in ([p] if isinstance(p, str) else p):
        t = r if isinstance(r, str) else r.get('t')
        if t is None:
            out.append(r)
            continue
        props = {} if isinstance(r, str) else {k: v for k, v in r.items() if k != 't'}
        for part in re.split(r'(\x02[^\x02]*\x02|\x03[^\x03]*\x03|\x05[^\x05]*\x05)', t):
            if not part:
                continue
            if part[0] == '\x02':
                out.append({'footnote': notes.get(part[1:-1], part[1:-1])})
            elif part[0] == '\x03':
                text, url = part[1:-1].split('\x04', 1)
                out.append(dict(props, link=url, t=text))
            elif part[0] == '\x05':
                out.append(dict(props, t=part[1:-1], italic=True))
            else:
                out.append(dict(props, t=part) if props else part)
    return dict(b, p=out)


def picture(src, alt, width_mm, base_dir):
    """Markdown picture -> picture block at 96 dpi, not wider than the text area (inline, like an HTML img)."""
    path = src if os.path.isabs(src) else os.path.join(base_dir, src)
    size = hwpx_build.image_size(open(path, 'rb').read()) if os.path.exists(path) else None
    if not size:
        return para('para', f'[{alt or src}]')
    w, h = size[0] * 25.4 / 96, size[1] * 25.4 / 96
    if w > width_mm:
        w, h = width_mm, h * width_mm / w
    b = dict(para('para'), pic={'src': os.path.abspath(path), 'w': round(w, 2), 'h': round(h, 2), 'inline': True})
    b.pop('p')                  # the builder reads "p" before "pic"
    return b


PT_MM = 25.4 / 72


def css_layout(spec, text_width_mm):
    """Make the Hangul layout equal to the browser layout of the same design (user 2026-11-14: judge by the HTML).
    Measured differences (measure.py on Edge and Hangul pages of 7 report documents) and how this function removes them:
    1. HTML shows a run of spaces as one space; the browser uses the font's own space width -> collapse spaces,
       font_space = true.
    2. CSS: the margins of two blocks overlap (the bigger one counts) and the extra line height is split above and
       below the text (half-leading). Hangul: before + lines x size x line% + after, text at the top of the line.
       -> after = 0 and before_i = max(after_(i-1), before_i) + hl_i - hl_(i-1), hl = size x (line% - 100) / 2.
    3. CSS table rows = padding + lines x size x line% + border (a cell height is a minimum); Hangul cells leave out
       the extra of the last line -> explicit row heights from the CSS model; cell text starts at pad_top + hl."""
    def plain(t):
        return ' '.join(t.split())

    def hl(b):
        ln = b.get('line', 160)
        return b.get('size', 10) * (ln - 100) / 200 if isinstance(ln, (int, float)) else 0

    def lines(b, width_mm):
        """Wrapped line count of a paragraph: real font widths (textfit.py, Windows GDI); without GDI an estimate
        (Korean char = 1 em, other = 0.55 em) that is too high for Latin text and wide titles."""
        try:
            from ..core import textfit
            return textfit.count_lines(b, width_mm)
        except (ImportError, AttributeError, OSError):
            pass
        p = b.get('p', '')
        t = p if isinstance(p, str) else ''.join(x if isinstance(x, str) else x.get('t', '') for x in p)
        em = sum(1 if ord(ch) > 0x2E80 else 0.55 for ch in t)
        avail = (width_mm - b.get('left', 0) * PT_MM) / (b.get('size', 10) * PT_MM)
        return max(1, -(-em // max(avail, 1)))

    def fix_text(b):
        p = b.get('p')
        if isinstance(p, str):
            b['p'] = plain(p)
        elif isinstance(p, list):
            # a run of spaces is one space, also across run edges; trim only the ends of the paragraph
            out, sp = [], True
            for x in p:
                t = x if isinstance(x, str) else x.get('t')
                if t is None:                       # not a text run (note, field, ...)
                    out.append(x)
                    continue
                t = re.sub(r'\s+', ' ', t)
                if sp and t.startswith(' '):
                    t = t[1:]
                if t:
                    sp = t.endswith(' ')
                out.append(t if isinstance(x, str) else dict(x, t=t))
            last = max((i for i, x in enumerate(out) if isinstance(x, str) or 't' in x), default=None)
            if last is not None:
                x = out[last]
                out[last] = x.rstrip() if isinstance(x, str) else dict(x, t=x['t'].rstrip())
            b['p'] = out
        b['font_space'] = True

    def block_h(b, width_mm):
        """CSS height (pt) of a block inside a cell, margins included."""
        ln = b.get('line', 160)
        pitch = b.get('size', 10) * ln / 100 if isinstance(ln, (int, float)) else 0
        return b.get('before', 0) + lines(b, width_mm) * pitch + b.get('after', 0)

    def side_pt(cell, side):
        b = cell.get('border')
        v = b.get(side) if isinstance(b, dict) else b
        if not v or str(v).startswith('none'):
            return 0
        return float(str(v).split()[0].rstrip('m')) / PT_MM

    def cell_fix(cell, width_mm, border_pt):
        blocks = cell.get('blocks', [])
        for b in blocks:
            fix_text(b)
        pad = [float(str(v).rstrip('pt')) for v in cell.get('pad', ['0pt'] * 4)] if isinstance(cell.get('pad'), list) else [0] * 4
        # a CSS border lies inside the cell box: thick top/bottom borders push the text and add to the height
        bt, bb = side_pt(cell, 'top'), side_pt(cell, 'bottom')
        if bt > 0.6 or bb > 0.6:
            pad[2] += bt / 2
            pad[3] += bb / 2
            border_pt = (bt + bb) / 2
            cell['pad'] = [f'{v}pt' for v in pad]
        inner = width_mm - (pad[0] + pad[1]) * PT_MM
        content = 0
        prev_mb = None
        for b in blocks:
            mt = b.get('before', 0)
            content += (mt if prev_mb is None else max(prev_mb, mt)) + block_h(dict(b, before=0, after=0), inner)
            prev_mb = b.get('after', 0)
        content += prev_mb or 0
        # text starts at pad_top + half-leading of the first line; Hangul stacks the rest like CSS
        prev_mb, prev_hl = None, 0
        for n, b in enumerate(blocks):
            h = hl(b)
            b['before'] = (b.get('before', 0) + h) if n == 0 else max(max(prev_mb, b.get('before', 0)) + h - prev_hl, 0)
            prev_mb, prev_hl = b.get('after', 0), h
            b['after'] = 0
        cell['valign'] = 'top'
        return (pad[2] + content + pad[3]) + border_pt

    body = spec['body']
    prev_mb, prev_hl = 0, 0
    prev_table = None
    for n, b in enumerate(body):
        if 'table' in b:
            t = b['table']
            bw = 0.5 if t.get('border', 'none') != 'none' else 0
            heights = []
            for row in t['rows']:
                h_row = 0
                c = 0
                hs = []
                for cell in row:
                    w = sum(t['cols'][c:c + cell.get('cs', 1)])
                    c += cell.get('cs', 1)
                    va = cell.get('valign', 'top')
                    hs.append((cell, va, cell_fix(cell, w, bw)))
                    h_row = max(h_row, hs[-1][2])
                # CSS vertical-align middle/bottom: the cell text moves down inside the row (cells stay "top")
                for cell, va, h in hs:
                    if va in ('center', 'bottom') and cell.get('blocks') and cell.get('rs', 1) == 1:
                        cell['blocks'][0]['before'] += (h_row - h) / (2 if va == 'center' else 1)
                heights.append(h_row)
            given = t.get('heights') or [0] * len(heights)
            # blank rows of the design: CSS height 20 pt is the content box (padding and border come on top)
            t['heights'] = [max(h, (g / PT_MM + 7 + bw) if g and g / PT_MM > 15 else 0) * PT_MM
                            for h, g in zip(heights, given)]
            # the table's own CSS margins (0 in the report-gongmun preset, which uses gap paragraphs)
            own_mt, own_mb = b.get('before', 0), b.get('after', 0)
            gap_pt = max(max(prev_mb, own_mt) - prev_hl, 0)
            b['before'] = b['after'] = 0
            t['margin'] = [0, 0, 0, 0]
            # Hangul puts a block table at the top of its paragraph and ignores that paragraph's "before"
            # (measured: summary box 3.7 mm too high): the gap goes into the table's top outer margin
            if prev_table is not None:
                prev_table['margin'][3] = gap_pt * PT_MM
            else:
                t['margin'][2] = gap_pt * PT_MM
            prev_mb, prev_hl = own_mb, 0
            prev_table = t
        else:
            fix_text(b)
            h = hl(b)
            mt = b.get('before', 0)
            b['before'] = max((mt if n == 0 else max(prev_mb, mt)) + h - prev_hl, 0)
            # Hangul ignores the "before" of the paragraph after a block table when the table is taller than
            # its anchor line (measured: date line 0.6 mm under the title box): use the table's bottom margin
            if prev_table is not None:
                prev_table['margin'][3] = b['before'] * PT_MM
                b['before'] = 0
            prev_mb, prev_hl = b.get('after', 0), h
            b['after'] = 0
            prev_table = None
    return spec


SELFTEST_MD = '\n'.join([
    '# 시험 문서', '> 부제', '작성일: 2026. 11. 14.(토)', '## Ⅰ. 장', '### 항목', '#### 소항목 h4',
    '> 본문 인용문', '![그림](t.png)', '- 1단계', '  - 2단계', '    - 3단계', '      - 4단계', '```', 'print(1)', '```',
    '각주가 있는 문장[^1]', '[^1]: 각주 내용', '끝.'])


def selftest(out_dir):
    """Preset front end check (references/presets.md, self-test): no Hangul needed; render the HWPX to check OPEN."""
    from ..render import img
    os.makedirs(out_dir, exist_ok=True)
    img.save_png(os.path.join(out_dir, 't.png'), (96, 48, [bytes([200, 60, 60]) * 96] * 48))
    load_preset('report-gongmun')
    found = {el for _, el, _ in scan(SELFTEST_MD)}
    assert found == {'blockquote', 'image', 'list3', 'footnote'}, found          # h4 and the code block are mapped
    s, unmapped = spec(SELFTEST_MD)
    assert s is None and len(unmapped) == 5, unmapped                            # footnote: reference + definition
    log = []
    s, _ = spec(SELFTEST_MD, fallback=True, base_dir=out_dir, log=log.append)
    assert len(log) == 5 and all(x.startswith('FALLBACK line ') for x in log), log
    text = json.dumps(s, ensure_ascii=False)
    body = s['body']
    assert any('pic' in b and 'p' not in b and b['pic']['w'] == 25.4 for b in body), 'picture 96 px = 25.4 mm'
    assert any(isinstance(b.get('p'), list) and {'footnote': '각주 내용'} in b['p'] for b in body), 'footnote run'
    assert any(b.get('p') == '본문 인용문' and b['size'] == P.TEXT['note']['size'] for b in body), 'blockquote -> note'
    assert any(b.get('p') == '· 4단계' and b['size'] == P.TEXT['l2']['size'] for b in body), 'list level 4 -> l2'
    assert '소항목 h4' in text and 'print(1)' in text and not re.search(r'\\u000[1-5]', text), 'no placeholder left'
    # a preset that maps the blockquote to a style: no longer UNMAPPED
    P.MAP = dict(P.MAP, blockquote='para')
    assert 'blockquote' not in {el for _, el, _ in spec(SELFTEST_MD)[1]}
    load_preset('report-gongmun')
    dst = hwpx_build.write(spec(SELFTEST_MD, fallback=True, base_dir=out_dir, log=lambda m: None)[0],
                           os.path.join(out_dir, 'selftest.hwpx'))
    print('MD2HWPX SELFTEST PASS', dst)


def main(args):
    if args and args[0] == '--selftest':
        import tempfile                 # never write into the plugin folder (it is a read-only cache)
        return selftest(args[1] if len(args) > 1 else tmpdir.mkdtemp('hwpx_docs_md_'))
    src, dst = args[0], args[1]
    if '--preset' in args:
        load_preset(args[args.index('--preset') + 1])
        miss = check_preset()
        if miss:
            print(f'PRESET "{P.name}" IS NOT COMPLETE:', ', '.join(miss))
            sys.exit(2)
    s, unmapped = spec(open(src, encoding='utf-8').read(), fallback='--fallback' in args,
                       base_dir=os.path.dirname(os.path.abspath(src)))
    if s is None:
        for n, el, text in unmapped:
            print(f'UNMAPPED line {n}: {WHAT[el]}: {text[:60]}')
        print(f'STOP: preset "{P.name}" has no style for these. Add them to its MAP (references/presets.md), '
              'or rerun with --fallback')
        sys.exit(2)
    from ..check import readability          # a new document: apply the safe readability fixes (--keep: list them only)
    if '--keep' in args:
        readability.report_only(s)
    else:
        found = readability.check(s)
        readability.report(found)
        print('READABILITY FIXED', readability.fix(found))
    if '--spec' in args:
        json.dump(s, open(args[args.index('--spec') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('HWPX WRITTEN', hwpx_build.write(s, dst))


if __name__ == '__main__':
    main(sys.argv[1:])
