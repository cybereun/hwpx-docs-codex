"""Files of the preview: SVG pages, HTML, PNG (Edge print through `render.render.html_pages`), font files for Edge."""
import html
import os
import re
from .flow import render_pages
from .svg import f3


_SCALE = [1.0]                         # PDF -> PNG size correction found at run time (see render_files)


def font_files(faces):
    """{face: [(file, bold)]} of fonts that Windows lists in its registry (Hangul's own fonts such as HY헤드라인M have only
    a Korean family name that Edge does not match by name: an @font-face with the file fixes it)."""
    out = {}
    try:
        import winreg
    except ImportError:
        return out
    for root, base in ((winreg.HKEY_LOCAL_MACHINE, os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')), (winreg.HKEY_CURRENT_USER, None)):
        try:
            k = winreg.OpenKey(root, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
        except OSError:
            continue
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(k, i)
            except OSError:
                break
            i += 1
            n = name.rsplit(' (', 1)[0]
            bold = n.endswith(' Bold')
            f = n[:-5] if bold else n
            if f in faces and val.lower().endswith(('.ttf', '.otf')):
                path = val if os.path.isabs(val) else os.path.join(base or '', val)
                if os.path.exists(path):
                    out.setdefault(f, []).append((path, bold))
    return out


def font_css(svgs):
    faces = set()
    for s in svgs:
        faces.update(re.findall(r"font-family=\"&#x27;([^&]*)&#x27;", s))
    css = []
    for f, lst in font_files({html.unescape(x) for x in faces}).items():
        for path, bold in lst:
            css.append("@font-face{font-family:'%s';font-weight:%s;src:url('file:///%s')}" % (f, 'bold' if bold else 'normal', path.replace(chr(92), '/')))
    return ''.join(css)


def render_files(path, out_dir, dpi=96, png=True):
    """Write <stem>_p<N>.svg, <stem>_preview.html and (Edge) <stem>_p<N>.png. Returns the PNG paths ([] without Edge)."""
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    pages = render_pages(path, dpi)
    for n, (_, _, svg) in enumerate(pages, 1):
        open(os.path.join(out_dir, '%s_p%d.svg' % (stem, n)), 'w', encoding='utf-8').write(svg)
    w = pages[0][0]
    sizes = sorted({(p[0], p[1]) for p in pages})
    page_css = ''.join('@page s%d{size:%smm %smm;margin:0}svg.s%d{page:s%d}' % (i, f3(w), f3(h), i, i) for i, (w, h) in enumerate(sizes))
    body = '\n'.join(p[2].replace('<svg ', '<svg class="s%d" ' % sizes.index((p[0], p[1])), 1) for p in pages)
    # The pages come from a received file: no script and no network in this page, whatever a value in the file holds (CSP)
    csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data: file:; '
           'style-src \'unsafe-inline\'; font-src file: data:">')
    doc = ('<!doctype html><html><head><meta charset="utf-8">' + csp + '<title>%s</title><style>%s%s'
           'html,body{margin:0;padding:0}svg{break-after:page}svg:last-child{break-after:auto}'
           '</style></head><body>%s</body></html>' % (html.escape(stem), font_css([p[2] for p in pages]), page_css, body))
    hp = os.path.join(out_dir, stem + '_preview.html')
    open(hp, 'w', encoding='utf-8').write(doc)
    if not png:
        return []
    from ..render import img, render
    try:
        pngs = render.html_pages(hp, out_dir, dpi * _SCALE[0])
        want = round(w / 25.4 * dpi)
        got = img.load(pngs[0])[0]
        if abs(got - want) > 1:      # Windows.Data.Pdf sizes pages in DIPs that follow the display scaling (150 % -> 1.5 x too wide)
            _SCALE[0] *= want / got
            pngs = render.html_pages(hp, out_dir, dpi * _SCALE[0])
    except RuntimeError as e:
        print('NO PNG (%s)' % e)
        return []
    out = []
    for n, p in enumerate(pngs, 1):                  # html_pages names them <stem>_preview_web_p<N>.png
        dst = os.path.join(out_dir, '%s_p%d.png' % (stem, n))
        if os.path.exists(dst):
            os.remove(dst)
        os.replace(p, dst)
        out.append(dst)
    return out
