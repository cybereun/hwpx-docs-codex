"""Read an HWPX file into the JSON spec of hwpx_build.py (references/spec.md). Standard library only.

  python hwpx2spec.py <in.hwpx> <out.json>

Uses: (1) round-trip tests (Hangul file -> spec -> builder -> compare pages); (2) start a new
form from an existing HWPX: extract, edit the JSON, build. Pictures go next to the JSON file.
Elements that the spec cannot hold are listed on stderr as "UNSUPPORTED <tag>" (not dropped silently).
"""
import json
import os
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

NS = {'hh': 'http://www.hancom.co.kr/hwpml/2011/head', 'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
      'hc': 'http://www.hancom.co.kr/hwpml/2011/core', 'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
      'opf': 'http://www.idpf.org/2007/opf/'}
HP = '{%s}' % NS['hp']
MM = 7200 / 25.4
DEF_CHAR = dict(font='함초롬바탕', size=10, bold=False, italic=False, underline=False, strike=False, color='#000000',
                shade='none', spacing=0, ratio=100, sup=False, sub=False, rel_size=100, offset=0, outline=False,
                shadow=False, emboss=False, engrave=False, emphasis=None, kerning=False, font_space=False,
                char_border=None, char_fill=None)
DEF_PARA = dict(align='justify', left=0, right=0, indent=0, before=0, after=0, line=160, keep_next=False,
                keep_lines=False, page_break_before=False, widow=False, word_break='char', snap=True,
                line_valign='baseline', condense=0, latin_break='word', autospace=False)
FONT_LANGS = ('latin', 'hanja', 'japanese', 'other', 'symbol', 'user')
CHAR_KEYS = set(DEF_CHAR) | {'font_' + x for x in FONT_LANGS}
PARA_KEYS = set(DEF_PARA) | {'border', 'fill', 'border_offset', 'border_connect', 'bullet', 'bullet_image', 'number', 'outline_level', 'tabs'}
PROOF_FIELDS = {'PROOFREADING_MARKS_' + k for k in ('LINEATTACH', 'ATTACH', 'DELETE', 'CLIPPING')}     # 교정 부호 (objects2 OB18)
unsupported = Counter()


for _p, _u in (('hp', NS['hp']), ('hh', NS['hh']), ('hc', NS['hc']), ('hs', NS['hs'])):
    ET.register_namespace(_p, _u)


def raw(el):
    """Element -> OWPML text with the usual prefixes (hp:, hc:, ...)."""
    s = ET.tostring(el, encoding='unicode')
    return __import__('re').sub(r' xmlns:\w+="[^"]*"', '', s)


def mm(v):
    # 3 decimals: 0.001 mm < 0.3 HWPUNIT, so the builder gets the same HWPUNIT back
    # (2 decimals moved table lines by 1 px in the round trip)
    return round(int(v) / MM, 3)


def pt(v):
    return round(int(v) / 100, 2)


def num(x):
    return int(x) if float(x).is_integer() else x


def line_str(el):
    t = el.get('type', 'NONE')
    if t == 'NONE':      # an invisible side still has a width that Hangul uses at corners
        return 'none' if (el.get('width'), el.get('color')) in (('0.12 mm', '#000000'), ('0.1 mm', '#000000')) \
            else f'none {el.get("width").replace(" ", "")} {el.get("color")}'
    return f'{el.get("width").replace(" ", "")} {t.lower()} {el.get("color")}'


def strength(s):
    if s.startswith('none'):
        return (0, 0)
    w = float(s.split()[0].rstrip('m'))
    return (1, w)


def builtin_styles():
    """{style id: name} of the styles that every new Hangul document has (the builder's template)."""
    import re
    from .units import TEMPLATE
    h = open(os.path.join(TEMPLATE, 'Contents', 'header.xml'), encoding='utf-8').read()
    return {int(i): n for i, n in re.findall(r'<hh:style id="(\d+)"[^>]* name="([^"]*)"', h)}


def safe_xml(data):
    """Parse a part of a received file. A colour attribute (`textColor`, `faceColor`, `color` ...) that is not `#RRGGBB`,
    `#AARRGGBB` or `none` becomes `#000000`: the preview writes colours into SVG attributes, so a crafted value must not be
    able to end the attribute and add markup or script."""
    import re
    root = ET.fromstring(data)
    ok = re.compile(r'#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?|none')
    for el in root.iter():
        colour_el = str(el.tag).rsplit('}', 1)[-1].lower() == 'color'      # hc:color value="..." (gradient stops)
        for k, v in el.attrib.items():
            if (k.lower().endswith('color') or (colour_el and k == 'value')) and not ok.fullmatch(v):
                el.set(k, '#000000')
    return root


class Refs:
    def __init__(self, head):
        root = safe_xml(head)
        self.fonts = {}
        for ff in root.iter('{%s}fontface' % NS['hh']):
            self.fonts[ff.get('lang')] = {f.get('id'): f.get('face') for f in ff.findall('hh:font', NS)}
        self.bf = {}
        for b in root.iter('{%s}borderFill' % NS['hh']):
            sides = {k: line_str(b.find(f'hh:{k}Border', NS)) for k in ('left', 'right', 'top', 'bottom')}
            wb = b.find('hc:fillBrush/hc:winBrush', NS)
            fill = wb.get('faceColor') if wb is not None and wb.get('faceColor') != 'none' else None
            brush = b.find('hc:fillBrush', NS)
            for x in (list(brush) if brush is not None else []):
                if x.tag not in ('{%s}winBrush' % NS['hc'], '{%s}gradation' % NS['hc'], '{%s}imgBrush' % NS['hc']):
                    unsupported['fillBrush/' + x.tag.split('}')[1]] += 1      # gradient, picture: table/fills.py
            slash = b.find('hh:slash', NS).get('type') != 'NONE'
            back = b.find('hh:backSlash', NS).get('type') != 'NONE'
            dg = b.find('hh:diagonal', NS)
            self.bf[b.get('id')] = dict(sides=sides, fill=fill, slash=slash, back=back, diag=line_str(dg), brush=brush)
        self.bullets = {b.get('id'): b.get('char') for b in root.iter('{%s}bullet' % NS['hh'])}
        self.bullet_imgs = {}        # picture bullets: bullet id -> binary item id (textstyle/rules.md TS22)
        for b in root.iter('{%s}bullet' % NS['hh']):
            im = b.find('hc:img', NS)
            if b.get('useImage') == '1' and im is not None and im.get('binaryItemIDRef'):
                self.bullet_imgs[b.get('id')] = im.get('binaryItemIDRef')
        self.numberings = {}
        for nb in root.iter('{%s}numbering' % NS['hh']):
            levels = []
            for ph in sorted(nb.findall('hh:paraHead', NS), key=lambda x: int(x.get('level'))):
                lv = {'format': ph.get('numFormat')}
                if ph.text:
                    lv['text'] = ph.text
                if ph.get('start', '1') != '1':
                    lv['start'] = int(ph.get('start'))
                levels.append(lv)
            self.numberings[nb.get('id')] = levels
        self.tabs = {}               # tabPr id -> spec `tabs` (only a tabPr that has stops)
        for tp in root.iter('{%s}tabPr' % NS['hh']):
            items = tp.findall('hp:switch/hp:case/hh:tabItem', NS) or tp.findall('hh:tabItem', NS)      # case = real HWPUNIT; unit CHAR = 1/5 of it (textstyle/rules.md TS02)
            if items:
                stops = [{'pos': mm(int(t.get('pos')) * (5 if t.get('unit') == 'CHAR' else 1)), 'type': t.get('type').lower(),
                          'leader': t.get('leader', 'NONE').lower()} for t in items]
                auto = {'auto_left': tp.get('autoTabLeft') == '1', 'auto_right': tp.get('autoTabRight') == '1'}
                self.tabs[tp.get('id')] = dict(stops=stops, **auto) if any(auto.values()) else stops
        self.char = {c.get('id'): self.char_props(c) for c in root.iter('{%s}charPr' % NS['hh'])}
        authors = {a.get('id'): a.get('name') for a in root.iter('{%s}trackChangeAuthor' % NS['hh'])}
        self.tracks = {t.get('id'): {'type': t.get('type'), 'date': t.get('date'), 'author': authors.get(t.get('authorID'), '')}
                       for t in root.iter('{%s}trackChange' % NS['hh'])}     # tracked changes (fields/rules.md T01)
        self.para = {p.get('id'): self.para_props(p) for p in root.iter('{%s}paraPr' % NS['hh'])}
        self.styles = self.named_styles(root)

    def named_styles(self, root):
        """{style id: name} of the styles the spec can name; self.user = spec `named_styles` (the document's own)."""
        built = builtin_styles()
        names, self.user = {}, {}      # user: style id -> (name, spec props, next style id)
        for st in root.iter('{%s}style' % NS['hh']):
            i, n = int(st.get('id')), st.get('name')
            if built.get(i) == n:
                names[st.get('id')] = n
            elif i >= len(built):
                names[st.get('id')] = n
                kind = st.get('type', 'PARA').lower()
                d = {} if kind == 'para' else {'type': 'char'}
                if kind == 'para':
                    d.update({k: v for k, v in diff(self.para.get(st.get('paraPrIDRef'), {}), DEF_PARA).items()
                              if k in PARA_KEYS and k not in ('number', 'bullet', 'outline_level')})
                d.update(rel(self.char.get(st.get('charPrIDRef'), DEF_CHAR), DEF_CHAR))
                if st.get('engName'):
                    d['eng'] = st.get('engName')
                self.user[st.get('id')] = (n, d, st.get('nextStyleIDRef'))
        for sid, (n, d, nxt) in self.user.items():     # `next` by name; a style that is its own next has none
            if nxt != sid and nxt in names and 'type' not in d:
                d['next'] = names[nxt]
        return names

    def char_props(self, c):
        fr = c.find('hh:fontRef', NS)
        def seven(tag):                  # one number when all 7 languages agree, else a list of 7
            el = c.find(f'hh:{tag}', NS)
            v = [int(el.get(a)) for a in ('hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user')]
            return v[0] if len(set(v)) == 1 else v

        def has(tag):
            return c.find(f'hh:{tag}', NS) is not None
        d = dict(font=self.fonts['HANGUL'][fr.get('hangul')], size=pt(c.get('height')), bold=has('bold'), italic=has('italic'),
                 color=c.get('textColor'), shade=c.get('shadeColor'), spacing=seven('spacing'), ratio=seven('ratio'),
                 rel_size=seven('relSz'), offset=seven('offset'), sup=has('supscript'), sub=has('subscript'),
                 emboss=has('emboss'), engrave=has('engrave'), kerning=c.get('useKerning') == '1',
                 font_space=c.get('useFontSpace') == '1',
                 emphasis=None if c.get('symMark', 'NONE') == 'NONE' else c.get('symMark').lower())
        for lang in ('latin', 'hanja', 'japanese', 'other', 'symbol', 'user'):
            face = self.fonts[lang.upper()][fr.get(lang)]
            if face != d['font']:         # e.g. ○ □ ☐ are SYMBOL characters: their own font
                d['font_' + lang] = face
        ul = c.find('hh:underline', NS)
        if ul.get('type') == 'NONE':
            d['underline'] = False
        elif ul.get('type') == 'BOTTOM' and ul.get('shape') == 'SOLID':
            d['underline'] = True if ul.get('color') == d['color'] else ul.get('color')
        else:
            d['underline'] = {'pos': ul.get('type').lower(), 'shape': ul.get('shape').lower(), 'color': ul.get('color')}
        so = c.find('hh:strikeout', NS)
        if so.get('shape') == 'NONE':
            d['strike'] = False
        else:
            d['strike'] = True if (so.get('shape') == 'SOLID' and so.get('color') == d['color']) else \
                {'shape': so.get('shape').lower(), 'color': so.get('color')}
        ol = c.find('hh:outline', NS)
        d['outline'] = False if ol is None or ol.get('type') == 'NONE' else (True if ol.get('type') == 'SOLID' else ol.get('type').lower())
        sh = c.find('hh:shadow', NS)
        d['shadow'] = False if sh is None or sh.get('type') == 'NONE' else \
            {'type': sh.get('type').lower(), 'color': sh.get('color'), 'x': int(sh.get('offsetX')), 'y': int(sh.get('offsetY'))}
        bf = self.bf.get(c.get('borderFillIDRef'))
        if c.get('borderFillIDRef') != '2' and bf:     # 글자 테두리/배경
            sides = {k: v for k, v in bf['sides'].items() if v != 'none'}
            d['char_border'] = sides or None
            d['char_fill'] = bf['fill']
        return d

    def para_props(self, p):
        al = p.find('hh:align', NS).get('horizontal')
        al = {'DISTRIBUTE_SPACE': 'divide'}.get(al, al.lower())
        # hp:switch may hold the margins (HwpUnitChar case) or the heading (2016/paragraph case)
        case = next((c for c in p.findall('hp:switch/hp:case', NS) if c.find('hh:margin', NS) is not None), p)
        m = case.find('hh:margin', NS)
        vals = {t: (pt(m.find(f'hc:{t}', NS).get('value')) if m is not None else 0)
                for t in ('intent', 'left', 'right', 'prev', 'next')}
        ls = case.find('hh:lineSpacing', NS)
        if ls is None:
            ls = ET.Element('x', type='PERCENT', value='160')
        lt, lv = ls.get('type'), int(ls.get('value'))
        line = lv if lt == 'PERCENT' else {{'FIXED': 'fixed', 'AT_LEAST': 'at_least', 'BETWEEN_LINES': 'between'}[lt]: pt(lv)}
        bs = p.find('hh:breakSetting', NS)
        d = dict(align=al, indent=vals['intent'], left=vals['left'], right=vals['right'], before=vals['prev'],
                 after=vals['next'], line=line, keep_next=bs.get('keepWithNext') == '1', keep_lines=bs.get('keepLines') == '1',
                 page_break_before=bs.get('pageBreakBefore') == '1', widow=bs.get('widowOrphan') == '1',
                 word_break='word' if bs.get('breakNonLatinWord') == 'BREAK_WORD' else 'char', snap=p.get('snapToGrid') == '1',
                 line_valign=p.find('hh:align', NS).get('vertical', 'BASELINE').lower(), condense=int(p.get('condense', 0)),
                 latin_break={'KEEP_WORD': 'word', 'HYPHENATION': 'hyphen', 'BREAK_WORD': 'char'}.get(bs.get('breakLatinWord'), 'word'),
                 autospace=(p.find('hh:autoSpacing', NS) is not None and p.find('hh:autoSpacing', NS).get('eAsianEng') == '1'))
        if p.get('tabPrIDRef') in self.tabs:             # custom tab stops (textstyle/rules.md TS01)
            d['tabs'] = self.tabs[p.get('tabPrIDRef')]
        hd = p.find('hh:heading', NS)
        if hd is None:
            hd = next((c.find('hh:heading', NS) for c in p.findall('hp:switch/hp:case', NS)
                       if c.find('hh:heading', NS) is not None), ET.Element('x', type='NONE'))
        if hd.get('type') == 'BULLET':
            d['bullet'] = self.bullets.get(hd.get('idRef'), '•')
            if hd.get('idRef') in self.bullet_imgs:
                d['bullet_image'] = self.bullet_imgs[hd.get('idRef')]      # binary item id; Reader.paragraph saves the file
        elif hd.get('type') == 'NUMBER':
            d['number'] = (hd.get('idRef'), int(hd.get('level')))     # list index set by Reader
        elif hd.get('type') == 'OUTLINE' and p.find('hh:heading', NS) is not None:
            d['outline_level'] = int(hd.get('level'))
        elif hd.get('type') != 'NONE':
            d['_unsupported'] = 'heading/' + hd.get('type')    # counted only if a paragraph uses it
        b = p.find('hh:border', NS)
        bf = self.bf.get(b.get('borderFillIDRef'))
        if bf and (any(v != 'none' for v in bf['sides'].values()) or bf['fill']):
            d['border'] = {k: v for k, v in bf['sides'].items() if v != 'none'}
            if bf['fill']:
                d['fill'] = bf['fill']
            d['border_offset'] = [mm(b.get(k)) for k in ('offsetLeft', 'offsetRight', 'offsetTop', 'offsetBottom')]
            if b.get('connect') == '1':
                d['border_connect'] = True
        return d


def diff(d, base):
    return {k: v for k, v in d.items() if base.get(k, None) != v}


def _get(d, k):
    if k in d:
        return d[k]
    return d.get('font') if k.startswith('font_') else DEF_CHAR.get(k)


def rel(cp, base):
    """Char props of cp that the builder must state, given that it inherits `base`."""
    return {k: _get(cp, k) for k in set(cp) | set(base) if k in CHAR_KEYS and _get(cp, k) != _get(base, k)}


class Reader:
    def __init__(self, z, refs, out_dir):
        self.z, self.refs, self.out_dir = z, refs, out_dir
        self.num_ids = []       # header numbering ids in the order of first use -> spec 'numberings'
        self.colpr_seen = False  # True after the section's own colPr: a later one is a column change inside the page
        self.bins = {}
        hpf = ET.fromstring(z.read('Contents/content.hpf'))
        for it in hpf.iter('{%s}item' % NS['opf']):
            self.bins[it.get('id')] = it.get('href')
        self.saved = set()

    SAFE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.wmf', '.emf', '.txt', '.csv', '.pdf', '.hwp',
                '.hwpx', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.zip', '.ole', '.bin'}

    def save(self, name, data):
        """Write a part of the file (picture, embedded file) next to the spec -> the name used. The name comes from the received file,
        so: only its last part, plain characters, an extension from SAFE_EXT (else `.bin` is added: no .dll, .url, .lnk next to
        the user's files), and never over a file that is already there with other content (`name_1.ext`, ...)."""
        import re
        name = os.path.basename(str(name).replace('\\', '/')).strip().strip('.') or 'part'
        name = re.sub(r'[^\w .()\-]', '_', name)
        stem, ext = os.path.splitext(name)
        if ext.lower() not in self.SAFE_EXT:
            stem, ext = name, '.bin'
        n, final = 0, stem + ext
        while True:
            path = os.path.join(self.out_dir, final)
            if not os.path.exists(path) or open(path, 'rb').read() == data:
                break
            n += 1
            final = f'{stem}_{n}{ext}'
        with open(path, 'wb') as f:
            f.write(data)
        self.saved.add(final)
        return final

    def text_of(self, t):
        """hp:t -> list of (text, highlight colour or None, tracked change or None); 형광펜 = markpenBegin/End inside
        hp:t; a tracked change (변경 추적) = insertBegin/End, deleteBegin/End: the change is (kind, id, paraend)."""
        segs, s, hl, chg = [], t.text or '', None, None
        for ch in t:
            tag = ch.tag.replace(HP, '')
            if tag == 'tab':
                s += '\t'
            elif tag == 'lineBreak':
                s += '\n'
            elif tag in ('markpenBegin', 'markpenEnd'):
                if s:
                    segs.append((s, hl, chg))
                s, hl = '', (ch.get('color') if tag == 'markpenBegin' else None)
            elif tag in ('insertBegin', 'insertEnd', 'deleteBegin', 'deleteEnd'):
                if s:
                    segs.append((s, hl, chg))
                s, chg = '', ((tag[:6], ch.get('TcId'), False) if tag.endswith('Begin') else None)
                if tag.endswith('End') and ch.get('paraend') == '1' and segs:
                    segs[-1] = segs[-1][:2] + ((segs[-1][2][0], segs[-1][2][1], True),)
            else:
                unsupported['t/' + tag] += 1
            s += ch.tail or ''
        if s:
            segs.append((s, hl, chg))
        return segs

    def change(self, chg, char_tc, s):
        """Spec dict of one tracked piece of text: {type insert|delete|format, t, author, date, id[, paraend]}."""
        tid = chg[1] if chg else char_tc
        rec = self.refs.tracks.get(tid, {})
        kind = chg[0] if chg else 'format'
        d = {'type': kind, 't': s, 'author': rec.get('author', ''), 'date': rec.get('date', ''), 'id': int(tid or 0)}
        if chg and chg[2]:
            d['paraend'] = True
        return d

    def paragraphs(self, parent, base=None):
        """hp:p children of `parent` -> list of blocks. base: the char props that the builder
        gives these paragraphs by inheritance (doc defaults, or the table's paragraph for cells)."""
        blocks = []
        for p in parent.findall('hp:p', NS):
            blocks += self.paragraph(p, base or DEF_CHAR)
        return blocks

    def paragraph(self, p, base=DEF_CHAR):
        pp = self.refs.para[p.get('paraPrIDRef')]
        runs, extra = [], []           # runs: (char props, item); extra: block tables / pictures
        link = None                    # URL while inside a HYPERLINK field
        field = None                   # dict while inside a CLICK_HERE field (누름틀)
        proof = None                   # dict while inside a 교정 부호 field (objects2 rules OB18)
        shapes = []                    # floating rect / ellipse / line anchored here
        shape_cp = None
        for r in p.findall('hp:run', NS):
            cp = self.refs.char[r.get('charPrIDRef')]
            for el in r:
                tag = el.tag.replace(HP, '')
                if tag == 't':
                    for s, hl, chg in self.text_of(el):
                        if (chg or r.get('charTcId')) and field is None and not link:     # tracked change (fields/rules.md T01)
                            runs.append((cp, {'change': self.change(chg, r.get('charTcId'), s)}))
                        elif field is not None:
                            field['t'] = field.get('t', '') + s      # the field's guide text
                            field['_cp'] = cp                        # its own char shape
                        elif proof is not None:
                            proof['text'] += s
                        elif link:
                            if runs and isinstance(runs[-1][1], dict) and runs[-1][1].get('link') == link and runs[-1][0] is cp:
                                runs[-1][1]['t'] += s
                            else:
                                runs.append((cp, {'link': link, 't': s}))
                        elif hl:
                            runs.append((cp, {'t': s, 'highlight': hl}))
                        else:
                            runs.append((cp, s))
                elif tag == 'ctrl':
                    for c in el:
                        ct = c.tag.replace(HP, '')
                        if ct == 'fieldBegin' and c.get('type') == 'HYPERLINK':
                            path = c.find("hp:parameters/hp:stringParam[@name='Path']", NS)
                            link = path.text if path is not None else ''
                        elif ct == 'fieldBegin' and c.get('type') == 'CLICK_HERE':
                            help_ = c.find("hp:parameters/hp:stringParam[@name='HelpState']", NS)
                            field = {'field': c.get('name', ''), 'memo': help_.text if help_ is not None and help_.text else ''}
                            runs.append((cp, field))
                        elif ct == 'fieldBegin' and c.get('type') in PROOF_FIELDS:      # 교정 부호: {"proof": kind, "text": text}
                            proof = {'proof': c.get('type')[len('PROOFREADING_MARKS_'):].lower(), 'text': ''}
                            runs.append((cp, proof))
                        elif ct == 'fieldEnd' and proof is not None:
                            proof = None
                        elif ct == 'fieldEnd' and field is not None:
                            field = None
                        elif ct == 'fieldEnd' and link is not None:
                            link = None
                        elif ct in ('footNote', 'endNote'):      # builder: note text = run style + size 9
                            fb = self.paragraphs(c.find('hp:subList', NS), dict(cp, size=9))
                            if fb and isinstance(fb[0].get('p'), str) and fb[0]['p'].startswith(' '):
                                fb[0]['p'] = fb[0]['p'][1:]     # Hangul's space after the number
                            runs.append((cp, {'footnote' if ct == 'footNote' else 'endnote': fb}))
                        elif ct == 'autoNum' and c.get('numType') == 'PAGE':
                            runs.append((cp, {'page_num': True}))
                        elif ct == 'bookmark':
                            runs.append((cp, {'bookmark': c.get('name', '')}))
                        elif ct == 'newNum' and c.get('numType') == 'PAGE':
                            runs.append((cp, {'new_page_num': int(c.get('num', 1))}))
                        elif ct == 'colPr' and self.colpr_seen:
                            runs.append((cp, {'xml': raw(el)}))     # a column change inside the page (C10.03)
                        elif ct in ('colPr', 'header', 'footer', 'pageNum', 'secPr', 'autoNum'):
                            self.colpr_seen |= ct == 'colPr'        # section level: read by section()
                        else:            # anything else: keep it as raw OWPML (written back as given)
                            unsupported['raw ctrl/' + ct] += 1
                            runs.append((cp, {'xml': raw(el)}))
                elif tag == 'tbl':
                    t = self.table(el, cp)
                    if t.get('inline'):
                        runs.append((cp, {'table': t}))
                    else:
                        extra.append((cp, {'table': t}))
                elif tag == 'pic':
                    pic = self.pic(el)
                    if pic.get('inline', True):
                        runs.append((cp, {'pic': pic}))
                    else:
                        extra.append((cp, {'pic': pic}))
                elif tag in ('rect', 'ellipse', 'line') and el.find('hp:pos', NS).get('treatAsChar') != '1' and el.get('dropcapstyle', 'None') == 'None':      # a drop cap rect goes to registry
                    shapes.append(self.shape(el, tag, cp))
                    shape_cp = cp
                elif tag == 'equation':
                    sz = el.find('hp:sz', NS)
                    sc = el.find('hp:script', NS)
                    runs.append((cp, {'equation': {'script': sc.text if sc is not None else '', 'size': pt(el.get('baseUnit', 1000)),
                                                   'color': el.get('textColor', '#000000'), 'font': el.get('font', 'HancomEQN'),
                                                   'baseline': int(el.get('baseLine', 66)),
                                                   'w': mm(sz.get('width')), 'h': mm(sz.get('height'))}}))
                elif tag in ('secPr',):
                    pass
                else:
                    from . import registry          # a feature package may know the element (registry.py)
                    item = registry.read_element(self, el)
                    if item is not None:
                        (runs if item.pop('_run', False) else extra).append((cp, item))      # '_run': a run item, not a block
                    else:        # anything else: keep it as raw OWPML (written back as given)
                        unsupported['raw run/' + tag] += 1
                        runs.append((cp, {'xml': raw(el)}))
            if not list(r) and not runs:
                runs.append((cp, ''))
        # footnote paragraphs: drop the number control and the space Hangul puts after it
        first_cp = next((c for c, _ in runs), None) or shape_cp or (self.refs.char['0'] if not extra else extra[0][0])
        pp = dict(pp)
        if pp.get('bullet_image'):           # picture bullet: the image is saved next to the spec like a picture
            href = self.bins[pp['bullet_image']]
            name = os.path.splitext(os.path.basename(href))[0] + os.path.splitext(href)[1].lower()
            pp['bullet_image'] = self.save(name, self.z.read(href))
        if '_unsupported' in pp:
            unsupported[pp.pop('_unsupported')] += 1
        if 'number' in pp:
            nid, lv = pp['number']
            if nid not in self.num_ids:
                self.num_ids.append(nid)
            idx = self.num_ids.index(nid)
            pp['number'] = {'list': idx, 'level': lv} if idx else lv
        block = diff(pp, DEF_PARA)
        block.update(rel(first_cp, base))
        if p.get('styleIDRef') in self.refs.styles and p.get('styleIDRef') != '0':     # named style (textstyle/rules.md TS11)
            block['style'] = self.refs.styles[p.get('styleIDRef')]
        if p.get('pageBreak') == '1':
            block['page_break'] = True
        if p.get('columnBreak') == '1':
            block['column_break'] = True
        out = []
        for cp, item in extra:          # a block table/picture: own block with the paragraph spacing
            b = diff(pp, DEF_PARA)
            b.update(rel(cp, base))
            if not out and block.get('page_break'):
                b['page_break'] = True
            b.update(item)
            out.append(b)
        if shapes:
            block['shapes'] = shapes
        texts = [(c, s) for c, s in runs if not (s == '' and len(runs) > 1)]
        if extra and not any(s for _, s in texts):
            return out
        for b in out:                   # a table / picture in the same hp:p as the text block that follows (rules S26)
            if 'table' in b or 'pic' in b or 'object' in b or 'ole' in b:
                b['same_para'] = True
        items = []
        for cp, s in texts:
            if isinstance(s, dict) and '_cp' in s:      # a field: style of its guide text
                s = dict(s)
                cp = s.pop('_cp')
            d = rel(cp, first_cp)
            if isinstance(s, str):
                if items and isinstance(items[-1], dict) and 't' in items[-1] and set(items[-1]) - {'t'} == set(d) and \
                        all(items[-1][k] == v for k, v in d.items()):
                    items[-1]['t'] += s
                    continue
                items.append(dict(t=s, **d) if d else s)
            else:
                items.append(dict(s, **d) if d else s)
        if len(items) == 1 and isinstance(items[0], str):
            block['p'] = items[0]
        elif not items:
            block['p'] = ''
        else:
            block['p'] = [(i if isinstance(i, str) or set(i) != {'t'} else i['t']) for i in items]
        out.append(block)
        return out

    def table(self, tbl, base=DEF_CHAR):
        rows = tbl.findall('hp:tr', NS)
        ncol, nrow = int(tbl.get('colCnt')), int(tbl.get('rowCnt'))
        cells = []
        for tr in rows:
            for tc in tr.findall('hp:tc', NS):
                a, s, z = tc.find('hp:cellAddr', NS), tc.find('hp:cellSpan', NS), tc.find('hp:cellSz', NS)
                cells.append(dict(r=int(a.get('rowAddr')), c=int(a.get('colAddr')), rs=int(s.get('rowSpan')),
                                  cs=int(s.get('colSpan')), w=int(z.get('width')), h=int(z.get('height')), el=tc))
        cols = solve([(x['c'], x['cs'], x['w']) for x in cells], ncol)
        heights = solve([(x['r'], x['rs'], x['h']) for x in cells], nrow)
        inm = tbl.find('hp:inMargin', NS)
        pad = [int(inm.get(k)) for k in ('left', 'right', 'top', 'bottom')]
        # edges: the stronger of the two cell sides on each grid line (what Hangul shows)
        H, V = {}, {}

        def put(store, key, val):
            if key not in store or strength(val) > strength(store[key]):
                store[key] = val
        for x in cells:
            sides = self.refs.bf[x['el'].get('borderFillIDRef')]['sides']
            for dc in range(x['cs']):
                put(H, (x['r'], x['c'] + dc), sides['top'])
                put(H, (x['r'] + x['rs'], x['c'] + dc), sides['bottom'])
            for dr in range(x['rs']):
                put(V, (x['r'] + dr, x['c']), sides['left'])
                put(V, (x['r'] + dr, x['c'] + x['cs']), sides['right'])
        common = Counter(list(H.values()) + list(V.values())).most_common(1)[0][0]
        grid = [[] for _ in range(nrow)]
        for x in sorted(cells, key=lambda x: (x['r'], x['c'])):
            tc = x['el']
            r, c, rs, cs = x['r'], x['c'], x['rs'], x['cs']
            bf = self.refs.bf[tc.get('borderFillIDRef')]
            cell = {}
            if rs > 1:
                cell['rs'] = rs
            if cs > 1:
                cell['cs'] = cs
            own = {'top': H[(r, c)], 'bottom': H[(r + rs, c)], 'left': V[(r, c)], 'right': V[(r, c + cs)]}
            border = {k: v for k, v in own.items() if v != common}
            if border:
                cell['border'] = border
            if bf['fill']:
                cell['fill'] = bf['fill']
            from . import registry          # feature package table: gradient/picture fill, protect (READS fillBrush, tc)
            if bf['brush'] is not None and not bf['fill']:
                cell.update(registry.read_element(self, bf['brush']) or {})
            extra = registry.read_element(self, tc) or {}
            cell.update({k: v for k, v in extra.items() if k != 'p'})
            if bf['slash'] or bf['back']:
                cell['diag'] = 'both' if bf['slash'] and bf['back'] else ('slash' if bf['slash'] else 'back')
                cell['diag_line'] = bf['diag']
            sl = tc.find('hp:subList', NS)
            va = sl.get('vertAlign', 'CENTER').lower()
            if va != 'center':
                cell['valign'] = va
            if tc.get('hasMargin') == '1':
                cm = tc.find('hp:cellMargin', NS)
                cell['pad'] = [mm(cm.get(k)) for k in ('left', 'right', 'top', 'bottom')]
            if tc.get('header') == '1':
                cell['header'] = True
            blocks = self.paragraphs(sl, base)
            if 'p' in extra:                # a formula cell (table/ext.py): the shown text; the paragraph's own style stays
                blocks = [dict({k: v for k, v in blocks[0].items() if k != 'p'}, p=extra['p'])]
            simple = all(set(b) - {'p'} == set(blocks[0]) - {'p'} and all(b[k] == blocks[0][k] for k in b if k != 'p')
                         and isinstance(b.get('p'), str) for b in blocks)
            if simple:
                cell.update({k: v for k, v in blocks[0].items() if k != 'p'})
                cell['p'] = '\n'.join(b['p'] for b in blocks)
            else:
                cell['blocks'] = blocks
            grid[r].append(cell if set(cell) != {'p'} else cell['p'])
        t = dict(cols=[mm(v) for v in cols], heights=[mm(v) for v in heights], border=common, rows=grid)
        if pad != [510, 510, 141, 141]:
            t['pad'] = [mm(v) for v in pad]
        pos = tbl.find('hp:pos', NS)
        om = tbl.find('hp:outMargin', NS)
        omv = [mm(om.get(k)) for k in ('left', 'right', 'top', 'bottom')]
        if pos.get('treatAsChar') == '1':
            t['inline'] = True
            if any(omv):
                t['margin'] = omv
        else:
            if omv != [1.0, 1.0, 1.0, 1.0]:
                t['margin'] = omv
            if pos.get('horzAlign') != 'LEFT':
                t['align'] = pos.get('horzAlign').lower()
        from . import registry         # feature package table: floating position, caption (READS tbl)
        t.update(registry.read_element(self, tbl) or {})
        if tbl.get('pageBreak') != 'CELL':
            t['page_break'] = tbl.get('pageBreak').lower()
        if tbl.get('repeatHeader') == '0':
            t['repeat_header'] = False
        if tbl.get('textWrap') != 'TOP_AND_BOTTOM':
            t['wrap'] = tbl.get('textWrap').lower()
        if tbl.get('textFlow', 'BOTH_SIDES') != 'BOTH_SIDES':
            t['side'] = tbl.get('textFlow').lower()
        hdr = sum(1 for row in grid if row and isinstance(row[0], dict) and row[0].pop('header', False))
        if hdr:
            t['header_rows'] = hdr
        return t

    def shape(self, el, kind, cp):
        """hp:rect / hp:ellipse / hp:line -> builder shape dict (paper/page/para relative position)."""
        sz, pos = el.find('hp:sz', NS), el.find('hp:pos', NS)
        ls = el.find('hp:lineShape', NS)
        x, y = int(pos.get('horzOffset')), int(pos.get('vertOffset'))
        d = {'type': kind, 'x': mm(x), 'y': mm(y), 'rel': pos.get('vertRelTo').lower(),
             'line': (f'{round(int(ls.get("width")) / MM, 2)}mm {ls.get("style").lower()} {ls.get("color")}'
                      if ls.get('style') != 'NONE' else 'none'),
             'wrap': el.get('textWrap').lower()}
        if el.get('textFlow', 'BOTH_SIDES') != 'BOTH_SIDES':
            d['side'] = el.get('textFlow').lower()
        if kind == 'line':
            sp, ep = el.find('hc:startPt', NS), el.find('hc:endPt', NS)
            d.update(x=mm(x + int(sp.get('x'))), y=mm(y + int(sp.get('y'))), x2=mm(x + int(ep.get('x'))), y2=mm(y + int(ep.get('y'))))
            heads = (ls.get('headStyle') != 'NORMAL', ls.get('tailStyle') != 'NORMAL')
            if any(heads):
                d['arrow'] = 'both' if all(heads) else ('start' if heads[0] else 'end')
        else:
            d.update(w=mm(sz.get('width')), h=mm(sz.get('height')))
            wb = el.find('hc:fillBrush/hc:winBrush', NS)
            if wb is not None and wb.get('faceColor') != 'none':
                d['fill'] = wb.get('faceColor')
            if kind == 'rect' and el.get('ratio', '0') != '0':
                d['round'] = int(el.get('ratio'))
            dt = el.find('hp:drawText', NS)
            if dt is not None:
                sl = dt.find('hp:subList', NS)
                d['text'] = self.paragraphs(sl, cp)
                d['valign'] = sl.get('vertAlign', 'CENTER').lower()
                tm = dt.find('hp:textMargin', NS)
                d['pad'] = [mm(tm.get(k)) for k in ('left', 'right', 'top', 'bottom')]
        from . import registry          # feature packages add keys (objects2: position, caption)
        registry.read_extras('shape', self, el, d)
        return d

    def pic(self, el):
        img = el.find('hc:img', NS)
        href = self.bins[img.get('binaryItemIDRef')]
        name = self.save(href, self.z.read(href))
        sz = el.find('hp:sz', NS)
        pos = el.find('hp:pos', NS)
        d = {'src': name, 'w': mm(sz.get('width')), 'h': mm(sz.get('height'))}
        if pos.get('treatAsChar') != '1':
            d['inline'] = False
            d['pos'] = {'x': mm(pos.get('horzOffset')), 'y': mm(pos.get('vertOffset')), 'rel': pos.get('vertRelTo').lower()}
            d['wrap'] = el.get('textWrap').lower()
            if el.get('textFlow', 'BOTH_SIDES') != 'BOTH_SIDES':
                d['side'] = el.get('textFlow').lower()
        from . import registry          # feature packages add keys (objects2: effects, crop, border, caption)
        registry.read_extras('pic', self, el, d)
        return d

    def section(self, xml):
        root = safe_xml(xml)
        sec = {}
        sp = root.find('.//hp:secPr', NS)
        pp = sp.find('hp:pagePr', NS)
        m = pp.find('hp:margin', NS)
        w, h = mm(pp.get('width')), mm(pp.get('height'))
        # exact size: 1 HWPUNIT of page width moves centred and justified text by a sub-pixel
        page = {'size': 'A4'} if (pp.get('width'), pp.get('height')) == ('59528', '84186') else {'size': [w, h]}
        if pp.get('landscape') == 'NARROWLY':
            page['landscape'] = True
        page['margin'] = {k: mm(m.get(k)) for k in ('left', 'right', 'top', 'bottom', 'header', 'footer')}
        if m.get('gutter', '0') != '0':
            page['margin']['gutter'] = mm(m.get('gutter'))
        sn = sp.find('hp:startNum', NS)
        if sn is not None and sn.get('page') not in ('0', None):
            page['start_page'] = int(sn.get('page'))
        sec['page'] = page
        pbf = sp.find("hp:pageBorderFill[@type='BOTH']", NS)
        if pbf is not None and pbf.get('borderFillIDRef') != '1':
            bf = self.refs.bf[pbf.get('borderFillIDRef')]
            o = pbf.find('hp:offset', NS)
            sec['page_border'] = {'border': {k: v for k, v in bf['sides'].items() if v != 'none'}, 'fill': bf['fill'],
                                  'offset': [mm(o.get(k)) for k in ('left', 'right', 'top', 'bottom')],
                                  'text_border': pbf.get('textBorder').lower(), 'fill_area': pbf.get('fillArea').lower(),
                                  'header_inside': pbf.get('headerInside') == '1', 'footer_inside': pbf.get('footerInside') == '1'}
        col = root.find('.//hp:colPr', NS)
        if col is not None and (int(col.get('colCount', 1)) > 1 or col.get('type') != 'NEWSPAPER'):
            c = {'count': int(col.get('colCount')), 'gap': mm(col.get('sameGap'))}
            if col.get('type') != 'NEWSPAPER':
                c['type'] = {'BALANCED_NEWSPAPER': 'balanced', 'PARALLEL': 'parallel'}.get(col.get('type'), 'newspaper')
            cl = col.find('hp:colLine', NS)
            if cl is not None:
                c['line'] = line_str(cl)
            sec['columns'] = c
        # header/footer/page number controls can sit in any top-level paragraph (not only the first)
        for ctrl in root.findall('hp:p/hp:run/hp:ctrl', NS):
            for c in ctrl:
                tag = c.tag.replace(HP, '')
                if tag in ('header', 'footer'):
                    blocks = self.paragraphs(c.find('hp:subList', NS))
                    sec[tag] = blocks if c.get('applyPageType') == 'BOTH' else {'blocks': blocks, 'apply': c.get('applyPageType').lower()}
                elif tag == 'pageNum':
                    sec['page_number'] = {'pos': c.get('pos').lower(), 'format': c.get('formatType').lower(), 'side': c.get('sideChar')}
        from . import registry              # feature packages read more section keys (registry.py)
        for hook in registry.section_hooks('read'):
            hook(self, root, sec)
        self.colpr_seen = False             # the first colPr is the section's own; later ones are kept raw (pagex)
        sec['body'] = self.paragraphs(root)
        return sec


def solve(spans, n):
    """Sizes of n grid tracks from (start, span, size) items."""
    size = [None] * n
    for s, k, v in spans:
        if k == 1:
            size[s] = v
    for _ in range(n):
        for s, k, v in spans:
            unknown = [i for i in range(s, s + k) if size[i] is None]
            if len(unknown) == 1:
                size[unknown[0]] = v - sum(size[i] for i in range(s, s + k) if size[i] is not None)
    return [v if v is not None else 0 for v in size]


def read(path, out_json):
    from . import protect
    protect.guard(path)                      # a password / distribution document: clear message, not a crash
    out_dir = os.path.dirname(os.path.abspath(out_json))
    with zipfile.ZipFile(path) as z:
        refs = Refs(z.read('Contents/header.xml'))
        rd = Reader(z, refs, out_dir)
        names = sorted((n for n in z.namelist() if n.startswith('Contents/section')),
                       key=lambda n: int(n[len('Contents/section'):-4]))
        secs = [rd.section(z.read(n)) for n in names]
    spec = {'sections': secs} if len(secs) > 1 else secs[0]
    if refs.user:
        spec['named_styles'] = {n: d for n, d, _ in refs.user.values()}
    if rd.num_ids:
        spec['numberings'] = [{'levels': refs.numberings[i]} for i in rd.num_ids]
    return spec


if __name__ == '__main__':
    spec = read(sys.argv[1], sys.argv[2])
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    for k, v in unsupported.items():
        print('UNSUPPORTED', k, v, file=sys.stderr)
    print('SPEC WRITTEN', sys.argv[2])
