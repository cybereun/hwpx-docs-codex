"""Build an HWPX file from a JSON spec. Standard library only.

  python hwpx_build.py <spec.json> <out.hwpx>

The spec format is in references/spec.md. The builder starts from a Hangul-made empty document
(scripts/template/, saved by Hangul 2024) and adds fonts, char shapes, para shapes and
border/fills after the template items, as Hangul does. Every XML form that it writes comes from
the corpus (references/rules.md).
"""
from . import tmpdir
import datetime
import json
import os
import re
import sys
import zipfile
from .units import CHAR_KEYS, DEFAULT_NUMBERING, NO_LINE, PARA_KEYS, TEMPLATE, esc, hu, inherit, line, quad, read, width_str
from .units import PAPER, image_size  # noqa: F401  (used by callers as build.PAPER, build.image_size)
from .header import Header
from . import registry
from ..text.text import TextMixin
from ..table.table import TableMixin
from ..objects.objects import ObjectsMixin, chart_shapes
from ..page.page import PageMixin


class Doc(TextMixin, TableMixin, ObjectsMixin, PageMixin):
    """One document: spec -> header.xml and section XML. Feature writers come from the mixins."""
    named = {}          # spec named_styles (Layout and Check build a Doc without __init__)

    def __init__(self, spec, base='.'):
        self.spec = spec
        self.base = base        # folder for relative picture paths (the spec file's folder)
        self.head = Header(read(os.path.join(TEMPLATE, 'Contents', 'header.xml')))
        self.bins = []          # (item id, file name in BinData, bytes, media type)
        self.parts = {}         # extra zip parts of feature packages (registry.py): {'Chart/chart1.xml': bytes}
        self.manifest = []      # (item id, href) of parts that the manifest lists (content.hpf), for example master pages
        self.obj = 0           # z order / object counter
        self.notes = 0
        self.defaults = dict(font='함초롬바탕', size=10, align='justify', line=160)
        self.defaults.update(spec.get('defaults', {}))
        self.styles = spec.get('styles', {})    # named prop sets: a block, cell or run takes them with "class"
        self.named = spec.get('named_styles') or {}      # Hangul named styles (hh:style): a block takes one with "style"
        self.define_styles()

    def klass(self, d):
        """{"class": "a b", ...props} -> styles a, then b, then the item's own props (like CSS classes).
        {"style": "name"} (a Hangul named style of `named_styles`) puts that style's props under all of them."""
        if not isinstance(d, dict) or not ('class' in d or d.get('style') in self.named):
            return d
        out = {k: v for k, v in self.named.get(d.get('style'), {}).items() if k not in ('type', 'eng', 'next')}
        for name in str(d.get('class', '')).split():
            if name not in self.styles:
                raise ValueError(f'unknown class "{name}" (spec "styles" has: {", ".join(self.styles) or "none"})')
            out.update(self.styles[name])
        out.update({k: v for k, v in d.items() if k != 'class'})
        return out

    def bullet_bin(self, name):
        """Picture bullet `{"image": "file.png"}`: the file goes to BinData once; returns its binary item id."""
        done = self.__dict__.setdefault('_bullet_bins', {})
        if name not in done:
            data = open(os.path.join(self.base, name), 'rb').read()
            ext = os.path.splitext(name)[1].lower().lstrip('.')
            ext = 'jpg' if ext == 'jpeg' else ext
            done[name] = f'image{len(self.bins) + 1}'
            self.bins.append((done[name], f'BinData/{done[name]}.{ext}', data,
                              {'png': 'image/png', 'jpg': 'image/jpg', 'bmp': 'image/bmp', 'gif': 'image/gif'}[ext]))
        return done[name]

    def define_styles(self):
        """Spec `named_styles` -> hh:style items after the template's (textstyle/rules.md TS10-TS12)."""
        head = self.head
        for i, name in enumerate(self.named):
            head.style_ids[name] = head.base['style'] + i
        for name, s in self.named.items():
            kind = s.get('type', 'para')
            base = {k: v for k, v in self.defaults.items()}
            para = head.para_pr({**base, **{k: v for k, v in s.items() if k in PARA_KEYS}}) if kind == 'para' else 0
            char = head.char_pr({**base, **{k: v for k, v in s.items() if k in CHAR_KEYS}})
            head.style(name, kind, para, char, s.get('next'), s.get('eng', ''))

    def next_obj(self):
        self.obj += 1
        return self.obj

    def para_xml(self, runs, ctx, block, extra_runs='', page_break=False):
        p = dict(ctx)
        p.update({k: v for k, v in block.items() if k in PARA_KEYS})
        if p.get('bullet_image'):                  # picture bullet (textstyle/rules.md TS22); `bullet` is its character
            p['heading'] = ('BULLET', self.head.bullet_image(self.bullet_bin(p['bullet_image']), p.get('bullet') or '●'), 0)
        elif p.get('bullet'):
            p['heading'] = ('BULLET', self.head.bullet(p['bullet']), 0)
        if p.get('number') is not None:           # Hangul automatic paragraph number
            num = p['number'] if isinstance(p['number'], dict) else {'level': p['number']}
            lists = self.spec.get('numberings') or [{'levels': DEFAULT_NUMBERING}]
            levels = lists[num.get('list', 0)]['levels']
            p['heading'] = ('NUMBER', self.head.numbering(levels), int(num.get('level', 0)))
        pid = self.head.para_pr(p)
        body = ''.join(self.run_xml(r, inherit(ctx, block)) for r in runs)
        own = self.head.char_pr(inherit(ctx, block))
        if not body and not extra_runs:
            body = f'<hp:run charPrIDRef="{own}"/>'
        # The section-setting run of the first paragraph uses the paragraph's own char shape (as
        # Hangul does): a bigger char shape there makes the first line taller (corpus round trip).
        m = re.search(r'<hp:run charPrIDRef="(\d+)">', body)
        extra_runs = extra_runs.replace('charPrIDRef="FIRST"', f'charPrIDRef="{m.group(1) if m else own}"')
        brk = int(bool(page_break or block.get('page_break')))
        col = int(bool(block.get('column_break')))
        return (f'<hp:p id="0" paraPrIDRef="{pid}" styleIDRef="{self.head.style_id(block.get("style"))}" pageBreak="{brk}" columnBreak="{col}" merged="0">'
                f'{extra_runs}{body}</hp:p>')

    def blocks_xml(self, blocks, ctx, first_runs=''):
        """List of blocks -> list of paragraph XML. first_runs goes into the first paragraph."""
        out = []
        pending_break = False
        carry = ''                      # runs of `same_para` blocks: they go into the next paragraph (rules S26)
        for b in blocks:
            if isinstance(b, str):
                b = {'p': b}
            b = self.klass(b)
            if b.get('page_break') is True and len(b) == 1:
                pending_break = True
                continue
            extra = carry or (first_runs if not out else '')
            carry = ''
            done = False
            for key in [k for k in b if registry.block_handlers(k)]:     # feature packages (registry.py)
                for handler in registry.block_handlers(key):
                    r = handler(self, b, ctx, extra, pending_break)
                    if isinstance(r, dict):                              # a substitute block (a fallback)
                        b = r
                    elif isinstance(r, str):                             # the run of a floating object: own paragraph or `same_para`
                        if b.get('same_para'):
                            carry = extra + r
                        else:
                            out.append(self.para_xml([], ctx, {k: v for k, v in b.items() if k != key}, extra + r, pending_break))
                        done = True
                        break
                    elif r is not None:
                        out += r
                        done = True
                        break
                if done:
                    break
            if done:
                pending_break = False
                continue
            if 'chart' in b:                    # a chart is drawn with the same shapes (rules.md S25)
                b = dict(b, shapes=chart_shapes(b['chart']))
                b.pop('chart')
            if 'shapes' in b or 'shape' in b:
                # floating drawing objects (rect, text box, line, ellipse) anchored in this paragraph;
                # the paragraph itself is empty unless 'p' is given
                shapes = b.get('shapes') or [b['shape']]
                sc = inherit(ctx, b)
                extra += (f'<hp:run charPrIDRef="{self.head.char_pr(sc)}">' + ''.join(self.shape(s, sc) for s in shapes)
                          + '<hp:t/></hp:run>')
                b = {k: v for k, v in b.items() if k not in ('shapes', 'shape')}
                b.setdefault('p', '')
            if 'p' in b:
                text = b['p']
                if isinstance(text, str):
                    lines = text.split('\n')
                    for n, ln in enumerate(lines):
                        out.append(self.para_xml([ln] if ln else [], ctx, b, extra if n == 0 else '', pending_break and n == 0))
                        extra = ''
                else:
                    out.append(self.para_xml(text, ctx, b, extra, pending_break))
            elif 'table' in b:
                c = inherit(ctx, b)
                cid = self.head.char_pr(c)
                run = f'<hp:run charPrIDRef="{cid}">{self.table(b["table"], c, inline=b["table"].get("inline", False))}<hp:t/></hp:run>'
                if b.get('same_para'):
                    carry = extra + run
                    continue
                out.append(self.para_xml([], ctx, b, extra + run, pending_break))
            elif 'pic' in b:
                cid = self.head.char_pr(inherit(ctx, b))
                run = f'<hp:run charPrIDRef="{cid}">{self.pic(b["pic"], inline=b["pic"].get("inline", True))}<hp:t/></hp:run>'
                if b.get('same_para'):
                    carry = extra + run
                    continue
                out.append(self.para_xml([], ctx, b, extra + run, pending_break))
            elif 'gap' in b:
                g = dict(b, line={'fixed': b['gap']}, size=min(10, float(str(b['gap']).rstrip('pt'))), p='')
                g.pop('gap')
                out.append(self.para_xml([], ctx, g, extra, pending_break))
            else:
                raise ValueError(f'unknown block: {b!r}')
            pending_break = False
        if carry:                       # a `same_para` block last: its own paragraph
            out.append(self.para_xml([], ctx, {}, carry, pending_break))
        if not out:
            out.append(self.para_xml([], ctx, {}, first_runs))
        return out

    def sublist(self, blocks, ctx, valign='TOP', width=0, height=0):
        paras = ''.join(self.blocks_xml(blocks or [{'p': ''}], ctx))
        return (f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="{valign}" linkListIDRef="0" '
                f'linkListNextIDRef="0" textWidth="{width}" textHeight="{height}" hasTextRef="0" hasNumRef="0">{paras}</hp:subList>')

    def build(self):
        secs = self.spec.get('sections') or [self.spec]
        sections = [self.section_xml(s, i) for i, s in enumerate(secs)]
        header = self.head.render()
        for h in registry.block_handlers('doc.header'):       # a feature package adds to header.xml (fields: tracked changes)
            header = h(self, header)
        header = re.sub(r'secCnt="\d+"', f'secCnt="{len(sections)}"', header, count=1)
        return header, sections


def plain_text(sections):
    t = re.sub(r'<hp:subList.*?</hp:subList>', '', sections[0], flags=re.S)
    return ''.join(re.findall(r'<hp:t>([^<]*)', t))[:1000]


def write(spec, path, base='.'):
    doc = Doc(spec, base)
    header, sections = doc.build()
    hpf = read(os.path.join(TEMPLATE, 'Contents', 'content.hpf'))
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    hpf = re.sub(r'<opf:title/>|<opf:title>.*?</opf:title>', f'<opf:title>{esc(spec.get("title", ""))}</opf:title>', hpf)
    hpf = re.sub(r'(name="(?:CreatedDate|ModifiedDate)" content="text">)[^<]*', rf'\g<1>{now}', hpf)
    hpf = re.sub(r'(name="(?:creator|lastsaveby)" content="text">)[^<]*', r'\g<1>hwpx-docs', hpf)
    items = ['<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>']
    items += [f'<opf:item id="{i}" href="{href}" media-type="application/xml"/>' for i, href in doc.manifest]
    items += [f'<opf:item id="{i}" href="{name}" media-type="{media}" isEmbeded="1"/>' for i, name, _, media in doc.bins]
    items += [f'<opf:item id="section{n}" href="Contents/section{n}.xml" media-type="application/xml"/>' for n in range(len(sections))]
    items.append('<opf:item id="settings" href="settings.xml" media-type="application/xml"/>')
    spine = '<opf:itemref idref="header" linear="yes"/>' + ''.join(
        f'<opf:itemref idref="section{n}" linear="yes"/>' for n in range(len(sections)))
    hpf = re.sub(r'<opf:manifest>.*</opf:manifest>', '<opf:manifest>' + ''.join(items) + '</opf:manifest>', hpf, flags=re.S)
    hpf = re.sub(r'<opf:spine>.*</opf:spine>', '<opf:spine>' + spine + '</opf:spine>', hpf, flags=re.S)
    settings = re.sub(r'pos="\d+"', 'pos="0"', read(os.path.join(TEMPLATE, 'settings.xml')))
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/hwp+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('version.xml', read(os.path.join(TEMPLATE, 'version.xml')), compress_type=zipfile.ZIP_STORED)
        z.writestr('Contents/header.xml', header.encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
        for n, s in enumerate(sections):
            z.writestr(f'Contents/section{n}.xml', s.encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
        for name, data in doc.parts.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('Preview/PrvText.txt', plain_text(sections).encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('settings.xml', settings, compress_type=zipfile.ZIP_DEFLATED)
        for _, name, data, _ in doc.bins:
            z.writestr(name, data, compress_type=zipfile.ZIP_STORED)
        for f in ('META-INF/container.rdf', 'META-INF/container.xml', 'META-INF/manifest.xml'):
            z.writestr(f, read(os.path.join(TEMPLATE, *f.split('/'))), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('Contents/content.hpf', hpf.encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)
    return path


def _selftest():
    assert hu(10, 'pt') == 1000 and hu('20mm') == 5669 and hu('1in') == 7200
    assert line('0.4mm solid #000') == ('SOLID', '0.4 mm', '#000000')
    assert line('1mm double') == ('DOUBLE_SLIM', '1.0 mm', '#000000')
    assert line('none') == NO_LINE and width_str(0.12) == '0.12 mm'
    assert quad([1, 2]) == [hu(1), hu(1), hu(2), hu(2)]
    p = os.path.join(tmpdir.mkdtemp(), 't.hwpx')
    write({'body': ['가', {'table': {'cols': [30, 40], 'rows': [['a', {'p': 'b', 'rs': 2}], ['c']]}}]}, p)
    with zipfile.ZipFile(p) as z:
        s = z.read('Contents/section0.xml').decode('utf-8')
        h = z.read('Contents/header.xml').decode('utf-8')
    from xml.dom import minidom
    minidom.parseString(s)
    minidom.parseString(h)
    assert s.count('<hp:tc ') == 3 and 'rowSpan="2"' in s
    print('HWPX_BUILD SELFTEST PASS')


if __name__ == '__main__':
    if sys.argv[1] == 'selftest':
        _selftest()
    else:
        spec = json.load(open(sys.argv[1], encoding='utf-8'))
        print('HWPX WRITTEN', write(spec, sys.argv[2], os.path.dirname(os.path.abspath(sys.argv[1]))))
        if '--no-check' not in sys.argv:            # every build reports readability (it changes nothing)
            from ..check import readability
            readability.report_only(spec)
