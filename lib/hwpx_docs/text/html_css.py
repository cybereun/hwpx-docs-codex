"""HTML + CSS of any design -> HWPX, with no per-class rules (user 2026-11-14: generic methods; judge by the HTML).

  python html_css.py <in.html> <out.hwpx> [--spec out.json]

It computes the style of each element like a browser in print mode (UA defaults, <style> rules with @media print,
selector specificity, inheritance, style="" attributes). Then it writes paragraphs, boxes (1-cell tables) and tables
with the CSS values, and md2hwpx.css_layout changes the CSS spacing model into Hangul's (rules.md W01-W07).

Selectors: tag, .class, #id, tag.class, *, descendant and child (>) combinators, comma lists.
Properties: font-family/-size/-weight/-style, color, background(-color), text-align, text-indent, line-height,
letter-spacing, word-break, white-space, text-decoration, vertical-align (cells, sub/sup), margin*, padding*, border*,
width, box-sizing, display: none, page-break-before/-after, break-before/-after; @page size and margin.
Everything else is printed as "UNSUPPORTED ..." (nothing is dropped in silence).
"""
import json
import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
from ..core import build as hwpx_build
from ..text import markdown as md2hwpx

PT_MM = 25.4 / 72
SIDES = ('top', 'right', 'bottom', 'left')
VOID = {'br', 'col', 'img', 'hr', 'meta', 'link', 'input', 'wbr', 'source', 'area', 'base'}
SKIP = {'head', 'style', 'script', 'title', 'template', 'noscript', 'meta', 'link', 'colgroup', 'col'}
BLOCK = {'html', 'body', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'table', 'ul', 'ol', 'li', 'blockquote',
         'section', 'article', 'header', 'footer', 'main', 'nav', 'aside', 'figure', 'figcaption', 'address', 'dl',
         'dt', 'dd', 'center', 'form', 'fieldset', 'details', 'summary'}
INLINE = {'span', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'del', 'ins', 'code', 'a', 'small', 'big', 'mark',
          'kbd', 'samp', 'tt', 'var', 'cite', 'abbr', 'q', 'sub', 'sup', 'font', 'label', 'time', 'br', 'wbr'}
PRE = ('pre', 'pre-wrap', 'pre-line', 'break-spaces')
BSTYLES = {'none', 'hidden', 'solid', 'dashed', 'dotted', 'double', 'groove', 'ridge', 'inset', 'outset'}
LINE_TYPE = {'dashed': 'dash', 'dotted': 'dot', 'double': 'double'}
HANDLED = {'font-family', 'font-size', 'font-weight', 'font-style', 'color', 'background-color', 'text-align',
           'text-indent', 'line-height', 'letter-spacing', 'word-break', 'white-space', 'text-decoration',
           'vertical-align', 'width', 'box-sizing', 'display', 'border-collapse', 'page-break-before',
           'page-break-after', 'break-before', 'break-after'} | {
    f'{p}-{s}' for p in ('margin', 'padding') for s in SIDES} | {
    f'border-{s}-{k}' for s in SIDES for k in ('width', 'style', 'color')}
NAMED = {'black': '#000000', 'white': '#FFFFFF', 'red': '#FF0000', 'green': '#008000', 'blue': '#0000FF',
         'gray': '#808080', 'grey': '#808080', 'silver': '#C0C0C0', 'navy': '#000080', 'yellow': '#FFFF00',
         'orange': '#FFA500', 'maroon': '#800000', 'purple': '#800080', 'teal': '#008080'}
# Hangul face names of fonts that Windows registers under an English name
ALIAS = {'hcr batang': '함초롬바탕', 'hcr dotum': '함초롬돋움', 'malgun gothic': '맑은 고딕', 'batang': '바탕',
         'batangche': '바탕체', 'gungsuh': '궁서', 'gungsuhche': '궁서체', 'dotum': '돋움', 'dotumche': '돋움체',
         'gulim': '굴림', 'gulimche': '굴림체', 'nanumgothic': '나눔고딕', 'nanummyeongjo': '나눔명조',
         'd2coding': 'D2Coding'}
REV = {v.lower(): k for k, v in ALIAS.items()}
GENERIC = {'serif': ('바탕', 'Times New Roman'), 'sans-serif': ('맑은 고딕', 'Arial'),
           'monospace': ('굴림체', 'Consolas'), 'system-ui': ('맑은 고딕', 'Segoe UI'),
           'cursive': ('궁서', 'Comic Sans MS'), 'fantasy': ('궁서', 'Impact')}
UA = """
body { margin: 8px; }
p { margin: 1em 0; }
h1 { font-size: 2em; font-weight: bold; margin: 0.67em 0; }
h2 { font-size: 1.5em; font-weight: bold; margin: 0.83em 0; }
h3 { font-size: 1.17em; font-weight: bold; margin: 1em 0; }
h4 { font-weight: bold; margin: 1.33em 0; }
h5 { font-size: 0.83em; font-weight: bold; margin: 1.67em 0; }
h6 { font-size: 0.67em; font-weight: bold; margin: 2.33em 0; }
b, strong, th, dt { font-weight: bold; }
i, em, cite, var, address { font-style: italic; }
u, ins { text-decoration: underline; }
s, strike, del { text-decoration: line-through; }
th { text-align: center; }
td, th { padding: 1px; vertical-align: middle; }
pre, code, kbd, samp, tt { font-family: monospace; }
pre { white-space: pre; margin: 1em 0; }
blockquote { margin: 1em 40px; }
ul, ol { margin: 1em 0; padding-left: 40px; }
dd { margin-left: 40px; }
sub { vertical-align: sub; font-size: smaller; }
sup { vertical-align: super; font-size: smaller; }
small { font-size: smaller; }
center { text-align: center; }
"""


# ---------------------------------------------------------------- values

def color(v):
    v = (v or '').strip().lower()
    if v in NAMED:
        return NAMED[v]
    m = re.fullmatch(r'#([0-9a-f]{3}|[0-9a-f]{6})', v)
    if m:
        h = m.group(1)
        return '#' + (''.join(c * 2 for c in h) if len(h) == 3 else h).upper()
    m = re.fullmatch(r'rgba?\(([^)]*)\)', v)
    if m:
        p = [x for x in re.split(r'[\s,/]+', m.group(1).strip()) if x]
        if len(p) > 3 and float(p[3].rstrip('%')) == 0:
            return None
        rgb = [round(float(x[:-1]) * 2.55) if x.endswith('%') else int(float(x)) for x in p[:3]]
        return '#' + ''.join(f'{max(0, min(255, x)):02X}' for x in rgb)
    return None


UNIT = {'pt': 1, 'px': 0.75, 'mm': 1 / PT_MM, 'cm': 10 / PT_MM, 'in': 72, 'pc': 12, 'q': 0.25 / PT_MM}


def length(v, fs, base=None):
    """CSS length -> pt (em = fs pt, % of base pt). None for auto or an unknown value."""
    m = re.fullmatch(r'(-?[\d.]+)([a-z%]*)', (v or '').strip().lower())
    if not m:
        return None
    x, u = float(m.group(1)), m.group(2)
    if u in UNIT:
        return x * UNIT[u]
    if u == 'em':
        return x * fs
    if u == 'rem':
        return x * 12
    if u == '%' and base is not None:
        return x * base / 100
    return 0.0 if (u == '' and x == 0) else None


def tokens(v):
    return re.findall(r'rgba?\([^)]*\)|\S+', v)


def expand(p, v):
    """Shorthand -> longhand declarations."""
    if p in ('margin', 'padding', 'border-width', 'border-style', 'border-color'):
        a = tokens(v)
        a = {1: a * 4, 2: a * 2, 3: [a[0], a[1], a[2], a[1]] if len(a) == 3 else a}.get(len(a), a[:4])
        if p in ('margin', 'padding'):
            return {f'{p}-{s}': x for s, x in zip(SIDES, a)}
        return {f'border-{s}-{p[7:]}': x for s, x in zip(SIDES, a)}
    if p == 'border' or p in (f'border-{s}' for s in SIDES):
        w, st, c = 'medium', 'none', 'currentcolor'
        for t in tokens(v):
            if t in BSTYLES:
                st = t
            elif re.match(r'-?[\d.]', t) or t in ('thin', 'medium', 'thick'):
                w = t
            else:
                c = t
        out = {}
        for s in (SIDES if p == 'border' else (p[7:],)):
            out.update({f'border-{s}-width': w, f'border-{s}-style': st, f'border-{s}-color': c})
        return out
    if p == 'background':
        return {'background-color': next((t for t in tokens(v) if color(t) or t == 'transparent'), 'transparent')}
    if p == 'text-decoration-line':
        return {'text-decoration': v}
    return {p: v}


def decls(body):
    d = {}
    for item in body.split(';'):
        if ':' in item:
            p, v = item.split(':', 1)
            d.update(expand(p.strip().lower(), v.replace('!important', '').strip()))
    return d


# ---------------------------------------------------------------- CSS rules and selectors

def parse_sel(s):
    out = []
    for t in re.sub(r'\s*>\s*', ' > ', s.strip()).split():
        if t == '>':
            out.append('>')
            continue
        if out and out[-1] != '>':
            out.append(' ')
        m = re.fullmatch(r'([a-zA-Z][\w-]*|\*)?((?:[.#][\w-]+)*)', t)
        if not m:
            return None
        ids = re.findall(r'#([\w-]+)', m.group(2))
        out.append(((m.group(1) or '*').lower(), frozenset(re.findall(r'\.([\w-]+)', m.group(2))), ids[0] if ids else None))
    return out or None


def specificity(sel):
    comp = [c for c in sel if isinstance(c, tuple)]
    return (sum(1 for c in comp if c[2]), sum(len(c[1]) for c in comp), sum(1 for c in comp if c[0] != '*'))


def css_blocks(text):
    """(prelude, body) of each top-level block of a CSS text."""
    i = 0
    while True:
        j = text.find('{', i)
        if j < 0:
            return
        depth, k = 1, j + 1
        while depth and k < len(text):
            depth += {'{': 1, '}': -1}.get(text[k], 0)
            k += 1
        yield text[i:j].strip(), text[j + 1:k - 1]
        i = k


def parse_css(text, origin, rules, page, unsupported):
    for pre, body in css_blocks(re.sub(r'/\*.*?\*/', '', text, flags=re.S)):
        if pre.startswith('@media'):
            if re.search(r'\b(print|all)\b', pre):          # print-to-PDF uses print media
                parse_css(body, origin, rules, page, unsupported)
        elif pre.startswith('@page'):
            page.update({k.strip().lower(): v.strip() for k, v in
                         (x.split(':', 1) for x in body.split(';') if ':' in x)})
        elif not pre.startswith('@'):
            d = decls(body)
            for p in d:
                if p not in HANDLED:
                    unsupported[f'property {p}'] += 1
            for s in pre.split(','):
                sel = parse_sel(s)
                if sel is None:
                    unsupported[f'selector {s.strip()}'] += 1
                else:
                    rules.append((sel, origin, specificity(sel), len(rules), d))


def matches(sel, chain):
    def ok(c, n):
        return (c[0] == '*' or c[0] == n.tag) and c[1] <= n.cls and (c[2] is None or c[2] == n.id)

    def at(i, j):
        if not ok(sel[i], chain[j]):
            return False
        if i == 0:
            return True
        if sel[i - 1] == '>':
            return j > 0 and at(i - 2, j - 1)
        return any(at(i - 2, k) for k in range(j - 1, -1, -1))
    return at(len(sel) - 1, len(chain) - 1)


# ---------------------------------------------------------------- DOM

class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.parent, self.kids = tag, parent, []
        self.attrs = dict(attrs)
        self.cls = frozenset((self.attrs.get('class') or '').split())
        self.id = self.attrs.get('id')

    def chain(self):
        n, out = self, []
        while n.parent is not None:
            out.append(n)
            n = n.parent
        return out[::-1]


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node('#root', [], None)
        self.css, self.title = [], ''

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'li', 'td', 'th', 'tr') and self.cur.tag == tag:     # implicit end tags
            self.handle_endtag(tag)
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n.parent is not None and n.tag != tag:
            n = n.parent
        if n.parent is not None:
            self.cur = n.parent

    def handle_data(self, d):
        if self.cur.tag == 'style':
            self.css.append(d)
        elif self.cur.tag == 'title':
            self.title += d
        else:
            self.cur.kids.append(d)


# ---------------------------------------------------------------- converter

def installed_fonts():
    names = set()
    try:
        import winreg
    except ImportError:
        return names
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            k = winreg.OpenKey(root, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
        except OSError:
            continue
        i = 0
        while True:
            try:
                n = winreg.EnumValue(k, i)[0]
            except OSError:
                break
            i += 1
            for part in re.sub(r'\s*\([^)]*\)\s*$', '', n).split('&'):
                names.add(part.strip().lower())
    return names


class Conv:
    def __init__(self, html):
        t = Tree()
        t.feed(html)
        self.tree, self.title = t, ' '.join(t.title.split())
        self.rules, self.page, self.unsupported = [], {}, Counter()
        parse_css(UA, 0, self.rules, {}, Counter())
        parse_css('\n'.join(t.css), 1, self.rules, self.page, self.unsupported)
        self.fonts_ok = installed_fonts()
        self.pending_break = False
        self.font_cache = {}

    # ---- style
    def compute(self, node, ps):
        d = {}
        chain = node.chain()
        for r in sorted((r for r in self.rules if matches(r[0], chain)), key=lambda r: (r[1], r[2], r[3])):
            d.update(r[4])
        d.update(decls(node.attrs.get('style', '')))
        for p in decls(node.attrs.get('style', '')):
            if p not in HANDLED:
                self.unsupported[f'property {p} (style="")'] += 1
        pfs = ps['fs']
        s = dict(ps)                                     # inherited values
        if 'font-size' in d:
            v = d['font-size']
            kw = {'xx-small': 7, 'x-small': 7.5, 'small': 10, 'medium': 12, 'large': 13.5, 'x-large': 18,
                  'xx-large': 24, 'smaller': pfs / 1.2, 'larger': pfs * 1.2}
            s['fs'] = kw.get(v) or length(v, pfs, pfs) or pfs
        fs = s['fs']
        if 'font-family' in d:
            s['family'] = [f.strip().strip('"\'') for f in d['font-family'].split(',')]
        if 'font-weight' in d:
            w = d['font-weight']
            s['bold'] = w in ('bold', 'bolder') or (w.isdigit() and int(w) >= 600)
        if 'font-style' in d:
            s['italic'] = d['font-style'] in ('italic', 'oblique')
        if 'color' in d:
            s['color'] = color(d['color']) or ps['color']
        if 'line-height' in d:
            v = d['line-height']
            if v == 'normal':
                s['lh'] = ('num', 1.2)
            elif re.fullmatch(r'[\d.]+', v):
                s['lh'] = ('num', float(v))
            else:
                s['lh'] = ('pt', length(v, fs, fs) or fs * 1.2)
        if 'text-align' in d:
            s['align'] = {'start': 'left', 'end': 'right', 'justify-all': 'justify'}.get(d['text-align'], d['text-align'])
        if 'letter-spacing' in d:
            s['ls'] = length(d['letter-spacing'], fs) or 0
        for k, p in (('wb', 'word-break'), ('ws', 'white-space')):
            if p in d:
                s[k] = d[p]
        if 'text-indent' in d:
            s['ti'] = length(d['text-indent'], fs) or 0
        if 'text-decoration' in d:
            s['deco'] = d['text-decoration']
        va = d.get('vertical-align', 'baseline')
        s['script'] = 'sup' if va == 'super' else 'sub' if va == 'sub' else ps.get('script')
        # not inherited
        s['va'] = va
        for p, k in (('margin', 'm'), ('padding', 'pd')):
            for side in SIDES:
                s[f'{k}_{side}'] = length(d.get(f'{p}-{side}', '0'), fs) or 0
        s['border'] = {}
        for side in SIDES:
            st = d.get(f'border-{side}-style', 'none')
            w = d.get(f'border-{side}-width', 'medium')
            w = {'thin': 0.75, 'medium': 2.25, 'thick': 3.75}.get(w) or length(w, fs) or 0
            c = d.get(f'border-{side}-color', 'currentcolor')
            s['border'][side] = (w if st not in ('none', 'hidden') else 0, st, color(c) or s['color'])
        s['bg'] = color(d.get('background-color'))
        s['width'] = d.get('width')
        s['border_box'] = d.get('box-sizing') == 'border-box'
        s['display'] = d.get('display', '')
        s['pbb'] = any(d.get(p) in ('always', 'page', 'left', 'right') for p in ('page-break-before', 'break-before'))
        s['keep'] = any(d.get(p) in ('avoid', 'avoid-page') for p in ('page-break-after', 'break-after'))
        return s

    def root_style(self):
        return dict(fs=12.0, family=['serif'], bold=False, italic=False, color='#000000', lh=('num', 1.2),
                    align='left', ls=0, wb='normal', ws='normal', ti=0, deco='none', script=None)

    def fonts(self, family):
        key = tuple(family)
        if key in self.font_cache:
            return self.font_cache[key]

        def ok(f):
            return f.lower() in self.fonts_ok or REV.get(f.lower(), '') in self.fonts_ok

        hangul = latin = None
        for f in family:
            g = GENERIC.get(f.lower())
            if g:
                hangul, latin = hangul or g[0], latin or g[1]
                break
            if not ok(f):
                continue
            name = ALIAS.get(f.lower(), f)
            latin = latin or name
            if re.search('[가-힣]', name) or f.lower() in ALIAS:
                hangul = name
                break
        hangul = hangul or '함초롬바탕'
        self.font_cache[key] = (hangul, latin or hangul)
        return self.font_cache[key]

    def char(self, st):
        hangul, latin = self.fonts(st['family'])
        d = dict(font=hangul, size=round(st['fs'], 2), bold=st['bold'], color=st['color'])
        if latin != hangul:
            d['font_latin'] = latin
        if st['italic']:
            d['italic'] = True
        if st['ls']:
            d['spacing'] = round(st['ls'] / st['fs'] * 100)
        if 'underline' in st['deco']:
            d['underline'] = True
        if 'line-through' in st['deco']:
            d['strike'] = True
        if st.get('script'):
            d[st['script']] = True
        return d

    @staticmethod
    def line_pct(s):
        k, v = s['lh']
        return round(v * 100) if k == 'num' else round(v / s['fs'] * 100)

    @staticmethod
    def line_spec(b):
        w, st, c = b
        if not w:
            return 'none'
        return f'{w * PT_MM:.3f}mm {LINE_TYPE.get(st, "solid")} {c}'

    def boxed(self, s):
        return any(w for w, _, _ in s['border'].values()) or (s['bg'] not in (None, '#FFFFFF'))

    def outer_width(self, s, avail):
        """Border-box width (mm) of a block in a containing block of `avail` mm."""
        w = length(s['width'], s['fs'], avail / PT_MM) if s['width'] else None
        if w is None:
            return avail - (s['m_left'] + s['m_right']) * PT_MM
        if not s['border_box']:
            w += s['pd_left'] + s['pd_right'] + s['border']['left'][0] + s['border']['right'][0]
        return w * PT_MM

    # ---- blocks
    def flow(self, kids, s, avail, left):
        """Children of a block container -> spec blocks; runs of inline content become anonymous paragraphs."""
        out, inline = [], []
        for k in kids:
            if isinstance(k, str) or k.tag in INLINE or k.tag not in BLOCK | {'table'} | SKIP:
                inline.append(k)
                continue
            out += self.para(inline, s, avail, left, own=False)
            inline = []
            out += self.block(k, s, avail, left)
        return out + self.para(inline, s, avail, left, own=False)

    def block(self, node, ps, avail, left):
        if node.tag in SKIP:
            return []
        s = self.compute(node, ps)
        if s['display'] == 'none':
            return []
        leaf = all(isinstance(k, str) or k.tag in INLINE or k.tag not in BLOCK | {'table'} for k in node.kids)
        if node.tag == 'table':
            out = self.table(node, s, avail)
        elif self.boxed(s):
            out = [self.box(node, s, avail, leaf)]
        elif leaf:
            out = self.para(node.kids, s, avail, left, own=True)
        else:
            inner = self.outer_width(s, avail) - (s['pd_left'] + s['pd_right']) * PT_MM
            out = self.flow(node.kids, s, inner, left + s['m_left'] + s['pd_left'])
            if out:            # a container's margins collapse with its first/last child's when it has no padding
                f, b = out[0], out[-1]
                f['before'] = (max(s['m_top'], f.get('before', 0)) if not s['pd_top']
                               else s['m_top'] + s['pd_top'] + f.get('before', 0))
                b['after'] = (max(s['m_bottom'], b.get('after', 0)) if not s['pd_bottom']
                              else s['m_bottom'] + s['pd_bottom'] + b.get('after', 0))
        if node.tag == 'li' and out and 'p' in out[0]:
            self.marker(node, out[0], s)
        if s['pbb'] and not out:
            self.pending_break = True
        elif out and (s['pbb'] or self.pending_break):
            out[0]['page_break'] = True
            self.pending_break = False
        if out and s['keep']:
            out[-1]['keep_next'] = True
        return out

    def marker(self, node, b, s):
        """List item marker outside the text, like list-style-position: outside."""
        sibs = [k for k in node.parent.kids if not isinstance(k, str) and k.tag == 'li']
        mark = f'{sibs.index(node) + 1}. ' if node.parent.tag == 'ol' else '• '
        mw = round(sum(1 if ord(c) > 0x2E80 else 0.55 for c in mark) * s['fs'], 2)
        p = b['p']
        b['p'] = mark + p if isinstance(p, str) else [mark] + p
        b['left'] = b['left'] - mw
        b['indent'] = -mw

    def segments(self, kids, s, segs):
        for k in kids:
            if isinstance(k, str):
                segs.append((k, s))
            elif k.tag == 'br':
                segs.append(('\n', None))
            elif k.tag not in SKIP:
                ks = self.compute(k, s)
                if ks['display'] == 'none':
                    continue
                if k.tag not in INLINE:
                    self.unsupported[f'element <{k.tag}> (text kept)'] += 1
                self.segments(k.kids, ks, segs)

    @staticmethod
    def lines(segs, pre):
        """Segments -> lines (lists of (text, style)); <br> and, in pre text, newlines end a line."""
        lines, cur = [], []
        for t, st in segs:
            if st is None:
                lines.append(cur)
                cur = []
            elif pre:
                for i, part in enumerate(t.split('\n')):
                    if i:
                        lines.append(cur)
                        cur = []
                    if part:
                        cur.append((part, st))
            else:
                cur.append((re.sub(r'\s+', ' ', t), st))
        lines.append(cur)
        if pre:
            if segs and segs[0][0].startswith('\n') and not lines[0]:
                lines = lines[1:]                        # a newline right after <pre> is not shown
            if len(lines) > 1 and not lines[-1]:
                lines = lines[:-1]
            return lines
        out = []
        for ln in lines:                                 # collapse spaces across element edges, trim line ends
            res, sp = [], True
            for t, st in ln:
                if sp and t.startswith(' '):
                    t = t[1:]
                if t:
                    res.append([t, st])
                    sp = t.endswith(' ')
            if res and res[-1][0].endswith(' '):
                res[-1][0] = res[-1][0][:-1]
            out.append([(t, st) for t, st in res if t])
        if len(out) > 1 and not out[-1]:
            out = out[:-1]
        return out

    def para(self, kids, s, avail, left, own):
        segs = []
        self.segments(kids, s, segs)
        lines = self.lines(segs, s['ws'] in PRE)
        if not any(lines):
            return []
        base = self.char(s)
        L = left + ((s['m_left'] + s['pd_left']) if own else 0)
        out = []
        for i, ln in enumerate(lines):
            first, last = i == 0, i == len(lines) - 1
            ti = s['ti'] if first else 0
            b = dict(base, align=s['align'], left=round(L + ti if ti < 0 else L, 2), indent=round(ti, 2),
                     before=(s['m_top'] + s['pd_top']) if own and first else 0,
                     after=(s['m_bottom'] + s['pd_bottom']) if own and last else 0,
                     line=self.line_pct(s), word_break='word' if s['wb'] == 'keep-all' else 'char')
            if own and (s['m_right'] + s['pd_right']):
                b['right'] = s['m_right'] + s['pd_right']
            runs = []
            for t, st in ln:
                c = self.char(st)
                runs.append(t if c == base else dict(t=t, **c))
            # Hangul sets the break rule per paragraph: use the rule of most of the text (td code {break-all})
            n_all = sum(len(t) for t, st in ln if st['wb'] == 'break-all')
            if n_all * 2 > sum(len(t) for t, _ in ln):
                b.update(word_break='char', latin_break='char')
            b['p'] = runs[0] if len(runs) == 1 and isinstance(runs[0], str) else (runs or '')
            out.append(b)
        return out

    def anchor(self, s, table):
        """Paragraph that holds a block table (small, like the preset: rules.md W05)."""
        return dict(font=self.char(s)['font'], size=4, line=100, align='left', table=table,
                    before=s['m_top'], after=s['m_bottom'])

    def box(self, node, s, avail, leaf):
        """A block with a border or a fill -> 1-cell table; its padding = cell margins."""
        W = self.outer_width(s, avail)
        sides = {k: self.line_spec(s['border'][k]) for k in SIDES}
        # a left/right side wider than 1 mm (a bar) is a filled column of its exact width (Hangul lines snap to a list)
        bars = {k: s['border'][k] for k in ('left', 'right') if s['border'][k][0] * PT_MM > 1.0}
        inner = W - sum(b[0] for b in bars.values()) * PT_MM
        for k in bars:
            sides[k] = 'none'
        content_w = inner - (s['pd_left'] + s['pd_right']) * PT_MM
        blocks = (self.para(node.kids, s, content_w, 0, own=False) if leaf
                  else self.flow(node.kids, s, content_w, 0))
        if not blocks:
            blocks = [dict(self.char(s), p='', line=self.line_pct(s))]
        cell = {'blocks': blocks, 'border': sides,
                'pad': [f'{v}pt' for v in (s['pd_left'], s['pd_right'], s['pd_top'], s['pd_bottom'])]}
        if s['bg'] and s['bg'] != '#FFFFFF':
            cell['fill'] = s['bg']
        def bar(b):
            return {'blocks': [{'p': '', 'size': 1, 'line': 100}], 'fill': b[2], 'pad': 0,
                    'border': {'top': sides['top'], 'bottom': sides['bottom'], 'left': 'none', 'right': 'none'}}
        cols = ([bars['left'][0] * PT_MM] if 'left' in bars else []) + [inner] + (
            [bars['right'][0] * PT_MM] if 'right' in bars else [])
        cells = ([bar(bars['left'])] if 'left' in bars else []) + [cell] + (
            [bar(bars['right'])] if 'right' in bars else [])
        return self.anchor(s, {'cols': [round(x, 3) for x in cols], 'border': 'none', 'margin': 0, 'rows': [cells]})

    def table(self, node, s, avail):
        W = self.outer_width(s, avail)
        if not s['width']:
            self.unsupported['table width auto (100 % used)'] += 1
        sections = {'thead': [], 'body': [], 'tfoot': []}
        cols_spec = []

        def walk(n, ps, sec):
            for k in n.kids:
                if isinstance(k, str):
                    continue
                if k.tag in ('thead', 'tbody', 'tfoot'):
                    walk(k, self.compute(k, ps), 'body' if k.tag == 'tbody' else k.tag)
                elif k.tag == 'colgroup':
                    walk(k, self.compute(k, ps), sec)
                elif k.tag == 'col':
                    cs = self.compute(k, ps)
                    w = cs['width'] or k.attrs.get('width')
                    cols_spec.extend([w] * int(k.attrs.get('span', 1)))
                elif k.tag == 'tr':
                    sections[sec].append((k, self.compute(k, ps)))
                elif k.tag == 'caption':
                    self.unsupported['element <caption>'] += 1
        walk(node, s, 'body')
        trs = sections['thead'] + sections['body'] + sections['tfoot']
        # grid positions (rowspan / colspan)
        occ, place = set(), []
        for r, (tr, trs_s) in enumerate(trs):
            c = 0
            for td in (k for k in tr.kids if not isinstance(k, str) and k.tag in ('td', 'th')):
                while (r, c) in occ:
                    c += 1
                cs, rs = int(td.attrs.get('colspan', 1)), int(td.attrs.get('rowspan', 1))
                occ |= {(r + i, c + j) for i in range(rs) for j in range(cs)}
                place.append((r, c, cs, rs, td, trs_s))
                c += cs
        ncol = max((c for _, c in occ), default=-1) + 1
        nrow = len(trs)
        widths = [length(w, s['fs'], W / PT_MM) if w else None for w in (cols_spec + [None] * ncol)[:ncol]]
        widths = [w * PT_MM if w else None for w in widths]
        for r, c, cs, rs, td, _ in place:                  # widths given on cells of a single column
            if cs == 1 and widths[c] is None:
                w = self.compute(td, s)['width']
                if w and length(w, s['fs'], W / PT_MM):
                    widths[c] = length(w, s['fs'], W / PT_MM) * PT_MM
        free = [i for i, w in enumerate(widths) if not w]
        if free:
            if len(free) == ncol:
                self.unsupported['table without column widths (equal columns)'] += 1
            rest = max(W - sum(w for w in widths if w), 0)
            for i in free:
                widths[i] = rest / len(free)
        tb = s['border']
        rows = [[] for _ in range(nrow)]
        for r, c, cs, rs, td, trs_s in place:
            cst = self.compute(td, trs_s)
            wmm = sum(widths[c:c + cs])
            inner = wmm - (cst['pd_left'] + cst['pd_right']) * PT_MM
            blocks = self.flow(td.kids, cst, inner, 0) or [dict(self.char(cst), p='', line=self.line_pct(cst))]
            edge = {'top': r == 0, 'bottom': r + rs == nrow, 'left': c == 0, 'right': c + cs == ncol}
            border = {}
            for side in SIDES:          # border-collapse: the wider line wins; the table edge counts on the outside
                cands = [cst['border'][side]] + ([tb[side]] if edge[side] else [])
                border[side] = self.line_spec(max(cands, key=lambda b: b[0]))
            cell = {'blocks': blocks, 'border': border,
                    'pad': [f'{v}pt' for v in (cst['pd_left'], cst['pd_right'], cst['pd_top'], cst['pd_bottom'])],
                    'valign': {'middle': 'center', 'bottom': 'bottom'}.get(cst['va'], 'top')}
            fill = cst['bg'] or trs_s['bg']
            if fill and fill != '#FFFFFF':
                cell['fill'] = fill
            if cs > 1:
                cell['cs'] = cs
            if rs > 1:
                cell['rs'] = rs
            rows[r].append(cell)
        inner_line = next((c['border']['left'] for row in rows for c in row), 'none')
        t = {'cols': [round(w, 3) for w in widths], 'border': inner_line, 'margin': 0, 'rows': rows}
        if sections['thead']:
            t.update(header_rows=len(sections['thead']), repeat_header=True)
        return [self.anchor(s, t)]

    # ---- document
    def spec(self):
        size = self.page.get('size', 'A4').split()
        paper = {'a4': (210, 297), 'a3': (297, 420), 'a5': (148, 210), 'b5': (176, 250), 'letter': (215.9, 279.4),
                 'legal': (215.9, 355.6)}
        pw, ph = paper.get(size[0].lower(), (210, 297)) if not re.match(r'[\d.]', size[0]) else (
            length(size[0], 12) * PT_MM, length(size[-1], 12) * PT_MM)
        if 'landscape' in size:
            pw, ph = ph, pw
        m = [length(x, 12) * PT_MM for x in tokens(self.page.get('margin', '0.4in'))]
        m = {1: m * 4, 2: m * 2, 3: m + m[1:2]}.get(len(m), m[:4])
        W = pw - m[1] - m[3]
        root = self.root_style()
        body = self.flow(self.tree.root.kids, root, W, 0)
        html = next((k for k in self.tree.root.kids if not isinstance(k, str) and k.tag == 'html'), None)
        bnode = next((k for k in (html.kids if html else []) if not isinstance(k, str) and k.tag == 'body'), None)
        bs = self.compute(bnode, self.compute(html, root)) if bnode else root
        spec = {'title': self.title,
                'page': {'size': [round(pw, 3), round(ph, 3)],
                         'margin': {'top': round(m[0], 3), 'right': round(m[1], 3), 'bottom': round(m[2], 3),
                                    'left': round(m[3], 3), 'header': 0, 'footer': 0}},
                'defaults': dict(self.char(bs), line=self.line_pct(bs), align=bs['align']),
                'body': body}
        return md2hwpx.css_layout(spec, W)


def convert(html):
    """HTML text -> (spec, unsupported Counter)."""
    c = Conv(html)
    return c.spec(), c.unsupported


def selftest():
    html = '''<html><head><style>
    @page { size: A4; margin: 20mm }
    body { margin: 0; font-family: "함초롬바탕", serif; font-size: 12pt; line-height: 1.6 }
    p { margin: 0 } .a { color: #f00 } p.a { font-weight: bold }
    @media screen { p { color: #00f } }
    .box { border: 1pt solid #000; background: #eee; padding: 4pt }
    h2 { font-size: 15pt; margin: 0; border-left: 8pt solid #123456 }
    table { width: 100%; border-collapse: collapse; border-top: 1.5pt solid #000 }
    td { border: 0.5pt solid #000; padding: 2pt 4pt; vertical-align: middle }
    .x { box-shadow: none }
    </style></head><body>
    <p class="a">빨강 <b>굵게</b> <code>code</code></p><div class="box"><p>상자</p></div><h2>제목</h2>
    <table><colgroup><col style="width:30%"><col></colgroup><tr><td>가</td><td>나</td></tr></table></body></html>'''
    spec, uns = convert(html)
    b = spec['body']
    assert spec['page']['margin']['left'] == 20 and spec['page']['size'] == [210, 297]
    assert b[0]['color'] == '#FF0000' and b[0]['bold'] and b[0]['size'] == 12 and b[0]['line'] == 160, b[0]
    assert b[0]['p'][-1] == dict(t='code', font='굴림체', font_latin='Consolas', size=12, bold=True,
                                 color='#FF0000'), b[0]['p']
    cell = b[1]['table']['rows'][0][0]
    assert cell['fill'] == '#EEEEEE' and cell['border']['top'].startswith('0.353mm solid'), cell
    bar = b[2]['table']
    assert abs(bar['cols'][0] - 8 * PT_MM) < 0.01 and bar['rows'][0][0]['fill'] == '#123456', bar
    t = b[3]['table']
    assert t['cols'] == [51.0, 119.0] and t['rows'][0][0]['border']['top'].startswith('0.529mm'), t
    assert t['rows'][0][1]['border']['left'].startswith('0.176mm'), t['rows'][0][1]
    assert uns['property box-shadow'] == 1, uns
    print('HTML_CSS SELFTEST PASS')


def main(args):
    if args and args[0] == '--selftest':
        return selftest()
    src, dst = args[0], args[1]
    spec, unsupported = convert(open(src, encoding='utf-8').read())
    for k, n in sorted(unsupported.items()):
        print(f'UNSUPPORTED {k} ({n})')
    from ..check import readability          # a reproduction: list readability findings, change nothing
    readability.report_only(spec)
    if '--spec' in args:
        json.dump(spec, open(args[args.index('--spec') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('HWPX WRITTEN', hwpx_build.write(spec, dst))


if __name__ == '__main__':
    main(sys.argv[1:])
