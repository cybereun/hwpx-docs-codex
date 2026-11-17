"""header.xml registries: fonts, char/para shapes, border fills, tabs, numbering."""
import json
import re
from .units import ALIGNS, LANGS, LANG_ATTRS, LINE_TYPES, NO_LINE, TYPEINFO, color, esc, hu, langs, quad, sides_of


class Header:
    """Template header.xml plus the items that the document adds."""

    def __init__(self, text):
        self.text = text
        hangul = re.search(r'<hh:fontface lang="HANGUL".*?</hh:fontface>', text, re.S).group(0)
        self.fonts = re.findall(r'<hh:font id="\d+" face="([^"]*)"', hangul)
        self.n_font = len(self.fonts)
        self.items = {k: [] for k in ('borderFill', 'charPr', 'paraPr', 'bullet', 'tabPr', 'numbering', 'style')}
        self.base = {
            'borderFill': len(re.findall(r'<hh:borderFill id=', text)) + 1,   # border fill ids start at 1
            'charPr': len(re.findall(r'<hh:charPr id=', text)),
            'paraPr': len(re.findall(r'<hh:paraPr id=', text)),
            'bullet': len(re.findall(r'<hh:bullet id=', text)) + 1,
            'tabPr': len(re.findall(r'<hh:tabPr id=', text)),
            'numbering': len(re.findall(r'<hh:numbering id=', text)) + 1,
            'style': len(re.findall(r'<hh:style id=', text)),
        }
        # style name (Korean or English) -> id: the template's built-in styles, then the document's (named_styles)
        self.style_ids = {}
        for m in re.finditer(r'<hh:style id="(\d+)"[^>]* name="([^"]*)" engName="([^"]*)"', text):
            self.style_ids[m.group(2)] = self.style_ids[m.group(3)] = int(m.group(1))
        self.cache = {}

    def font(self, face):
        if face not in self.fonts:
            self.fonts.append(face)
        return self.fonts.index(face)

    def add(self, kind, key, make):
        if (kind, key) not in self.cache:
            n = self.base[kind] + len(self.items[kind])
            self.items[kind].append(make(n))
            self.cache[(kind, key)] = n
        return self.cache[(kind, key)]

    # border/fill: sides = dict left/right/top/bottom -> line tuple; fill colour or None; diag
    def border_fill(self, sides=None, fill=None, slash=False, back=False, diag=None):
        sides = sides or {}
        s = tuple(sides.get(k, NO_LINE) for k in ('left', 'right', 'top', 'bottom'))
        d = diag or ('SOLID', '0.1 mm', '#000000')
        key = (s, fill, slash, back, d)

        def make(n):
            out = [f'<hh:borderFill id="{n}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">',
                   f'<hh:slash type="{"CENTER" if slash else "NONE"}" Crooked="0" isCounter="0"/>',
                   f'<hh:backSlash type="{"CENTER" if back else "NONE"}" Crooked="0" isCounter="0"/>']
            for tag, (t, w, c) in zip(('leftBorder', 'rightBorder', 'topBorder', 'bottomBorder'), s):
                out.append(f'<hh:{tag} type="{t}" width="{w}" color="{c}"/>')
            out.append(f'<hh:diagonal type="{d[0]}" width="{d[1]}" color="{d[2]}"/>')
            if fill and fill.startswith('<hc:fillBrush'):       # a finished brush (gradient, picture): table/fills.py
                out.append(fill)
            elif fill and fill != 'none':
                out.append(f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#000000" alpha="0"/></hc:fillBrush>')
            out.append('</hh:borderFill>')
            return ''.join(out)
        return self.add('borderFill', key, make)

    def char_pr(self, c):
        face = c.get('font', '함초롬바탕')
        # one face for all 7 languages, unless font_<lang> sets one (○ □ ☐ ※ are SYMBOL characters)
        fonts = [self.font(c.get('font_' + a, face) if a != 'hangul' else face) for a in LANG_ATTRS]
        height = hu(c.get('size', 10), 'pt')

        def seven(k, default):          # one number, or 7 numbers (one per language)
            v = c.get(k, default)
            return [round(x) for x in (v if isinstance(v, (list, tuple)) else [v] * 7)]
        ul = c.get('underline')        # True | '#colour' | {'pos': bottom|top|center, 'shape': line type, 'color'}
        if not ul:
            ul_x = '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        else:
            u = ul if isinstance(ul, dict) else ({'color': ul} if isinstance(ul, str) else {})
            ul_x = (f'<hh:underline type="{str(u.get("pos", "bottom")).upper()}" '
                    f'shape="{LINE_TYPES[str(u.get("shape", "solid")).lower()]}" color="{color(u.get("color", c.get("color")))}"/>')
        st = c.get('strike')           # True | {'shape', 'color'}
        if not st:
            st_x = '<hh:strikeout shape="NONE" color="#000000"/>'
        else:
            s = st if isinstance(st, dict) else {}
            st_x = f'<hh:strikeout shape="{LINE_TYPES[str(s.get("shape", "solid")).lower()]}" color="{color(s.get("color", c.get("color")))}"/>'
        ol = c.get('outline')
        ol_x = f'<hh:outline type="{LINE_TYPES[ol.lower()] if isinstance(ol, str) else ("SOLID" if ol else "NONE")}"/>'
        sh = c.get('shadow')           # True | {'type': drop|continuous, 'color', 'x', 'y'} (x, y in %)
        if not sh:
            sh_x = '<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>'
        else:
            s = sh if isinstance(sh, dict) else {}
            sh_x = (f'<hh:shadow type="{str(s.get("type", "drop")).upper()}" color="{color(s.get("color", "#C0C0C0"))}" '
                    f'offsetX="{s.get("x", 10)}" offsetY="{s.get("y", 10)}"/>')
        bf = 2
        if c.get('char_border') or c.get('char_fill'):     # 글자 테두리/배경
            bf = self.border_fill(sides_of(c.get('char_border')), color(c['char_fill']) if c.get('char_fill') else None)
        flags = ''.join(f'<hh:{t}/>' for k, t in (('italic', 'italic'), ('bold', 'bold')) if c.get(k))
        tail = ''.join(f'<hh:{t}/>' for k, t in (('emboss', 'emboss'), ('engrave', 'engrave'), ('sup', 'supscript'),
                                                 ('sub', 'subscript')) if c.get(k))
        head = (f'height="{height}" textColor="{color(c.get("color"))}" shadeColor="{color(c.get("shade"), "none")}" '
                f'useFontSpace="{int(bool(c.get("font_space")))}" useKerning="{int(bool(c.get("kerning")))}" '
                f'symMark="{str(c.get("emphasis") or "none").upper()}" borderFillIDRef="{bf}"')
        body = (f'<hh:fontRef {langs("", fonts)}/><hh:ratio {langs("", seven("ratio", 100))}/>'
                f'<hh:spacing {langs("", seven("spacing", 0))}/><hh:relSz {langs("", seven("rel_size", 100))}/>'
                f'<hh:offset {langs("", seven("offset", 0))}/>{flags}{ul_x}{st_x}{ol_x}{sh_x}{tail}')
        key = (head, body)

        def make(n):
            return f'<hh:charPr id="{n}" {head}>{body}</hh:charPr>'
        return self.add('charPr', key, make)

    def para_pr(self, p):
        align = ALIGNS[p.get('align', 'justify')]
        m = [hu(p.get(k, 0), 'pt') for k in ('indent', 'left', 'right', 'before', 'after')]
        ln = p.get('line', 160)
        if isinstance(ln, dict):
            kind, val = next(iter(ln.items()))
            ltype = {'fixed': 'FIXED', 'at_least': 'AT_LEAST', 'between': 'BETWEEN_LINES'}[kind]
            lval = hu(val, 'pt')
            lval2 = lval * 2      # HWPUNIT values are doubled in hp:default (corpus/diff/para_line_fixed)
        else:
            ltype, lval, lval2 = 'PERCENT', round(ln), round(ln)
        border = p.get('border')
        fill = color(p.get('fill'), 'none') if p.get('fill') else None
        bf = 2
        if border or fill:
            bf = self.border_fill(sides_of(border), fill)
        off = quad(p.get('border_offset', 0)) if (border or fill) else [0, 0, 0, 0]
        head = p.get('heading')     # ('BULLET'|'NUMBER', id, level) set by para_xml
        if head is None and p.get('outline_level') is not None:      # 개요 level 0-9 (corpus/diff/para_outline)
            head = ('OUTLINE', 0, int(p['outline_level']))
        htype, hid, hlv = head if head else ('NONE', 0, 0)

        def margin(k, lv):
            return ('<hh:margin>' + ''.join(f'<hc:{t} value="{v * k}" unit="HWPUNIT"/>' for t, v in
                                            zip(('intent', 'left', 'right', 'prev', 'next'), m))
                    + f'</hh:margin><hh:lineSpacing type="{ltype}" value="{lv}" unit="HWPUNIT"/>')
        # Korean line break. Measured (verify/imagetest1): KEEP_WORD breaks INSIDE words ("정확/한") = 글자,
        # BREAK_WORD breaks between words = 어절. The names are the opposite of what they say.
        wb = 'BREAK_WORD' if p.get('word_break') == 'word' else 'KEEP_WORD'
        lb = {'word': 'KEEP_WORD', 'hyphen': 'HYPHENATION', 'char': 'BREAK_WORD'}[p.get('latin_break', 'word')]
        tab = self.tab_pr(p.get('tabs')) if p.get('tabs') else 0
        auto = int(bool(p.get('autospace')))
        body = (f'tabPrIDRef="{tab}" condense="{int(p.get("condense", 0))}" fontLineHeight="0" '
                f'snapToGrid="{1 if p.get("snap", True) else 0}" suppressLineNumbers="0" checked="0" textDir="LTR">'
                f'<hh:align horizontal="{align}" vertical="{str(p.get("line_valign", "baseline")).upper()}"/>'
                f'<hh:heading type="{htype}" idRef="{hid}" level="{hlv}"/>'
                f'<hh:breakSetting breakLatinWord="{lb}" breakNonLatinWord="{wb}" '
                f'widowOrphan="{int(bool(p.get("widow")))}" keepWithNext="{int(bool(p.get("keep_next")))}" '
                f'keepLines="{int(bool(p.get("keep_lines")))}" pageBreakBefore="{int(bool(p.get("page_break_before")))}" '
                f'lineWrap="BREAK"/><hh:autoSpacing eAsianEng="{auto}" eAsianNum="{auto}"/>'
                '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
                f'{margin(1, lval)}</hp:case><hp:default>{margin(2, lval2)}</hp:default></hp:switch>'
                f'<hh:border borderFillIDRef="{bf}" offsetLeft="{off[0]}" offsetRight="{off[1]}" offsetTop="{off[2]}" '
                f'offsetBottom="{off[3]}" connect="{int(bool(p.get("border_connect")))}" ignoreMargin="0"/></hh:paraPr>')
        return self.add('paraPr', body, lambda n: f'<hh:paraPr id="{n}" {body}')

    def tab_pr(self, tabs):
        """tabs: list of {'pos': mm, 'type': 'left|right|center|decimal', 'leader': 'none|dot|...'} or
        {'stops': [...], 'auto_left': bool, 'auto_right': bool} (textstyle/rules.md TS01-TS03). Hangul's own form:
        each stop in its own hp:switch: hp:case (unit HWPUNIT, the real position) and hp:default (twice the HWPUNIT)."""
        stops, auto = (tabs.get('stops', []), tabs) if isinstance(tabs, dict) else (tabs, {})
        key = json.dumps(tabs, sort_keys=True)

        def make(n):
            def item(t, case):       # case: the real position in HWPUNIT; default: twice that (like the paragraph margins)
                return (f'<hh:tabItem pos="{hu(t["pos"]) * (1 if case else 2)}" type="{t.get("type", "left").upper()}" '
                        f'leader="{LINE_TYPES[str(t.get("leader", "none")).lower()]}"{" unit=" + chr(34) + "HWPUNIT" + chr(34) if case else ""}/>')
            # one hp:switch for EACH stop (measured: a switch that holds all stops is read wrong, render differs)
            body = ''.join('<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
                           f'{item(t, True)}</hp:case><hp:default>{item(t, False)}</hp:default></hp:switch>' for t in stops)
            return (f'<hh:tabPr id="{n}" autoTabLeft="{int(bool(auto.get("auto_left")))}" '
                    f'autoTabRight="{int(bool(auto.get("auto_right")))}">{body}</hh:tabPr>')
        return self.add('tabPr', key, make)

    def style_id(self, name):
        """Id of a named style (template built-in or the document's); 0 = 바탕글 for no name."""
        if not name:
            return 0
        if name not in self.style_ids:
            raise ValueError(f'unknown style "{name}" (built-in names or spec named_styles)')
        return self.style_ids[name]

    def style(self, name, kind='para', para_id=0, char_id=0, nxt=None, eng=''):
        """A named style (hh:style). Its id is already in style_ids (Doc.define_styles). textstyle/rules.md TS10."""
        sid = self.style_ids[name]
        nxt = 0 if kind == 'char' else (self.style_ids[nxt] if nxt else sid)       # Hangul: a char style has next 0
        self.items['style'].append(
            f'<hh:style id="{sid}" type="{kind.upper()}" name="{esc(name)}" engName="{esc(eng)}" paraPrIDRef="{para_id}" '
            f'charPrIDRef="{char_id}" nextStyleIDRef="{nxt}" langID="1042" lockForm="0"/>')
        return sid

    def numbering(self, levels):
        """levels: list of {'text': '^1.', 'format': 'DIGIT', 'start': 1} for paragraph levels 0..9
        (Hangul's paraHead level is 1-based). '^N' is the number of level N."""
        key = json.dumps(levels, sort_keys=True, ensure_ascii=False)

        def make(n):
            heads = []
            for i in range(10):
                lv = levels[i] if i < len(levels) else {}
                text = lv.get('text', '')
                heads.append(f'<hh:paraHead start="{lv.get("start", 1)}" level="{i + 1}" align="{lv.get("align", "left").upper()}" '
                             'useInstWidth="1" autoIndent="1" widthAdjust="0" textOffsetType="PERCENT" textOffset="50" '
                             f'numFormat="{lv.get("format", "DIGIT").upper()}" charPrIDRef="4294967295" checkable="0"'
                             + (f'>{esc(text)}</hh:paraHead>' if text else '/>'))
            return f'<hh:numbering id="{n}" start="0">{"".join(heads)}</hh:numbering>'
        return self.add('numbering', key, make)

    def bullet_image(self, item, char='●'):
        """A picture bullet: `hh:bullet useImage="1"` with `hc:img` (binary item `item`); textstyle/rules.md TS22."""
        def make(n):
            return (f'<hh:bullet id="{n}" char="{esc(char)}" useImage="1"><hc:img binaryItemIDRef="{item}" bright="0" contrast="0" '
                    'effect="REAL_PIC" alpha="0"/><hh:paraHead level="0" align="LEFT" useInstWidth="0" autoIndent="1" widthAdjust="0" '
                    'textOffsetType="PERCENT" textOffset="50" numFormat="DIGIT" charPrIDRef="4294967295" checkable="0"/></hh:bullet>')
        return self.add('bullet', ('image', item), make)

    def bullet(self, char):
        def make(n):
            return (f'<hh:bullet id="{n}" char="{esc(char)}" useImage="0"><hh:paraHead level="0" align="LEFT" '
                    'useInstWidth="0" autoIndent="1" widthAdjust="0" textOffsetType="PERCENT" textOffset="50" '
                    'numFormat="DIGIT" charPrIDRef="4294967295" checkable="0"/></hh:bullet>')
        return self.add('bullet', char, make)

    def render(self):
        t = self.text
        for lang in LANGS:
            def addfonts(m):
                body = m.group(2) + ''.join(f'<hh:font id="{i}" face="{esc(f)}" type="TTF" isEmbedded="0">{TYPEINFO}</hh:font>'
                                            for i, f in enumerate(self.fonts) if i >= self.n_font)
                return f'{m.group(1)}fontCnt="{len(self.fonts)}">{body}</hh:fontface>'
            t = re.sub(rf'(<hh:fontface lang="{lang}" )fontCnt="\d+">(.*?)</hh:fontface>', addfonts, t, count=1, flags=re.S)
        for kind, tag in (('borderFill', 'borderFills'), ('charPr', 'charProperties'), ('paraPr', 'paraProperties'),
                          ('tabPr', 'tabProperties'), ('numbering', 'numberings'), ('bullet', 'bullets'), ('style', 'styles')):
            items = self.items[kind]
            if not items:
                continue
            if f'<hh:{tag} ' not in t:     # bullets: not in the empty template; goes before paraProperties
                t = t.replace('<hh:paraProperties', f'<hh:{tag} itemCnt="0"></hh:{tag}><hh:paraProperties', 1)

            def grow(m):
                return f'<hh:{tag} itemCnt="{int(m.group(1)) + len(items)}">{m.group(2)}{"".join(items)}</hh:{tag}>'
            t = re.sub(rf'<hh:{tag} itemCnt="(\d+)">(.*?)</hh:{tag}>', grow, t, count=1, flags=re.S)
        return t
