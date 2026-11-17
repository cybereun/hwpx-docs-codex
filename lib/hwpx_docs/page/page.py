"""Sections: page size, margins, columns, header/footer, numbers."""
from ..core import tmpdir
import os
import re
from ..core import registry
from ..core.units import PAPER, TEMPLATE, color, esc, hu, line, quad, read, sides_of


class PageMixin:
    """Sections: page size, margins, columns, header/footer, numbers. Mixed into core.build.Doc."""

    # ---- sections ----
    def section_xml(self, sec, index):
        tmpl = read(os.path.join(TEMPLATE, 'Contents', 'section0.xml'))
        head = tmpl[:tmpl.index('<hp:p ')]
        secpr = re.search(r'<hp:secPr.*?</hp:secPr>', tmpl, re.S).group(0)
        pg = dict(self.spec.get('page', {}), **sec.get('page', {}))
        size = pg.get('size', 'A4')
        w, h = PAPER[size.upper()] if isinstance(size, str) else size
        w, h = hu(pg.get('width', w)), hu(pg.get('height', h))
        land = bool(pg.get('landscape'))
        if w > h:                 # Hangul keeps width < height and sets landscape="NARROWLY"
            w, h, land = h, w, True
        mg = dict(left=20, right=20, top=20, bottom=15, header=15, footer=15, gutter=0)
        mg.update(pg.get('margin', {}))
        mg = {k: hu(v) for k, v in mg.items()}
        secpr = re.sub(r'<hp:pagePr [^>]*>', f'<hp:pagePr landscape="{"NARROWLY" if land else "WIDELY"}" '
                       f'width="{w}" height="{h}" gutterType="LEFT_ONLY">', secpr)
        secpr = re.sub(r'<hp:margin [^>]*/>', f'<hp:margin header="{mg["header"]}" footer="{mg["footer"]}" gutter="{mg["gutter"]}" '
                       f'left="{mg["left"]}" right="{mg["right"]}" top="{mg["top"]}" bottom="{mg["bottom"]}"/>', secpr)
        if 'start_page' in pg:
            secpr = re.sub(r'(<hp:startNum [^>]*page=")\d+', rf'\g<1>{int(pg["start_page"])}', secpr)
        col = sec.get('columns') or {}
        cl = ''
        if col.get('line'):
            t, wd, c = line(col['line'])
            cl = f'<hp:colLine type="{t}" width="{wd}" color="{c}"/>'
        ctype = {'newspaper': 'NEWSPAPER', 'balanced': 'BALANCED_NEWSPAPER', 'parallel': 'PARALLEL'}[col.get('type', 'newspaper')]
        pb = sec.get('page_border', self.spec.get('page_border') if index == 0 else None)
        if pb:      # 쪽 테두리/배경 (corpus/diff/page_border): borderFill on the BOTH pageBorderFill
            bfid = self.head.border_fill(sides_of(pb.get('border')), color(pb['fill']) if pb.get('fill') else None)
            o = quad(pb.get('offset', 5))
            tb = pb.get('text_border', 'paper')
            tb = 'content' if tb == 'page' else tb      # 'page' was never a textBorder value (OWPML: PAPER|CONTENT)
            secpr = re.sub(r'<hp:pageBorderFill type="BOTH" borderFillIDRef="\d+" textBorder="\w+" headerInside="\d" '
                           r'footerInside="\d" fillArea="\w+"><hp:offset [^>]*/>',
                           f'<hp:pageBorderFill type="BOTH" borderFillIDRef="{bfid}" textBorder="{tb.upper()}" '
                           f'headerInside="{int(bool(pb.get("header_inside")))}" footerInside="{int(bool(pb.get("footer_inside")))}" '
                           f'fillArea="{pb.get("fill_area", "paper").upper()}"><hp:offset left="{o[0]}" right="{o[1]}" '
                           f'top="{o[2]}" bottom="{o[3]}"/>', secpr)
        colpr = (f'<hp:colPr id="" type="{ctype}" layout="LEFT" colCount="{col.get("count", 1)}" sameSz="1" '
                 f'sameGap="{hu(col.get("gap", 8)) if col.get("count", 1) > 1 else 0}"' + (f'>{cl}</hp:colPr>' if cl else '/>'))
        ctx = dict(self.defaults)
        ctx.update(sec.get('defaults', {}))
        cid = self.head.char_pr(ctx)
        ctrls = []
        text_w = (h if land else w) - mg['left'] - mg['right']
        for kind in ('header', 'footer'):
            hf = sec.get(kind, self.spec.get(kind) if index == 0 else None)
            if hf:
                blocks = hf.get('blocks') if isinstance(hf, dict) else hf
                apply = (hf.get('apply', 'both') if isinstance(hf, dict) else 'both').upper()
                hctx = dict(ctx)
                hctx.update(hf.get('style', {}) if isinstance(hf, dict) else {})
                valign = 'TOP' if kind == 'header' else 'BOTTOM'
                ctrls.append(f'<hp:ctrl><hp:{kind} id="{len(ctrls) + 1}" applyPageType="{apply}">'
                             f'{self.sublist(blocks, hctx, valign, text_w, mg[kind])}</hp:{kind}></hp:ctrl>')
        pn = sec.get('page_number', self.spec.get('page_number') if index == 0 else None)
        if pn:
            pn = {'pos': pn} if isinstance(pn, str) else pn
            ctrls.insert(0, f'<hp:ctrl><hp:pageNum pos="{pn.get("pos", "bottom_center").upper()}" '
                            f'formatType="{pn.get("format", "digit").upper()}" sideChar="{esc(pn.get("side", "-"))}"/></hp:ctrl>')
        for hook in registry.section_hooks('build'):         # feature packages (registry.py): pagex
            secpr, ctrls = hook(self, sec, index, secpr, ctrls, ctx, text_w, mg)
        first = f'<hp:run charPrIDRef="FIRST">{secpr}<hp:ctrl>{colpr}</hp:ctrl></hp:run>'
        if ctrls:
            first += f'<hp:run charPrIDRef="FIRST">{"".join(ctrls)}</hp:run>'
        paras = self.blocks_xml(sec.get('body', []), ctx, first)
        return head + ''.join(paras) + '</hs:sec>'


def selftest():
    """Landscape, columns, header/footer, page number; `page_border.text_border` writes only OWPML values (PAPER, CONTENT)."""
    import zipfile
    from xml.dom import minidom
    from ..core import build

    def section(spec):
        out = os.path.join(tmpdir.mkdtemp('hwpx_docs_page_'), 'p.hwpx')
        build.write(spec, out)
        with zipfile.ZipFile(out) as z:
            xml = z.read('Contents/section0.xml').decode('utf-8')
        minidom.parseString(xml)
        return xml

    s = section({'page': {'size': 'A4', 'landscape': True, 'margin': {'left': 15, 'right': 15}},
                 'columns': {'count': 2, 'gap': 8, 'line': '0.12mm solid'},
                 'header': ['머리말'], 'footer': ['꼬리말'], 'page_number': {'pos': 'bottom_center'}, 'body': ['본문']})
    assert 'landscape="NARROWLY"' in s and 'colCount="2"' in s, 'landscape and 2 columns'
    assert '<hp:header' in s and '<hp:footer' in s and 'pageNum' in s, 'header, footer, page number'
    for given, want in (('paper', 'PAPER'), ('content', 'CONTENT'), ('page', 'CONTENT')):   # S15: no PAGE in textBorder
        s = section({'page_border': {'border': '0.4mm solid', 'text_border': given}, 'body': ['가']})
        assert f'textBorder="{want}"' in s, given
