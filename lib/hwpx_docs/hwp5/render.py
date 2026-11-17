"""Pages of a .hwp and the before / after comparison of an edit (rules HW25-HW28).

  hd hwp render <in.hwp> [out_dir] [--backend preview|hangul] [--dpi 96]
  hd hwp compare <before.hwp> <after.hwp> <out_dir> [--backend preview|hangul] [--dpi 96]

Backends
  preview  no Hangul: HWP -> spec (tospec: Hangul's own line starts kept as `hangul_lines`, red "NOT DRAWN" boxes
           for objects it cannot draw) -> the preview (`registry.backend('specpages', 'preview')`): <stem>_p<N>.svg
           and <stem>_preview.html everywhere, PNG with Microsoft Edge on Windows. An approximation: the reference
           is Hangul's own page (backend hangul).
  hangul   Windows + Hangul 2024: Hangul opens a SAFE COPY of the .hwp (format "HWP"; `safecopy`: scripts blanked, linked pictures
           removed) and writes <stem>_p<N>.png. Only with `--backend hangul`.
  (no --backend) = preview: Hangul never starts by itself; one rule for HWPX and .hwp (`hd render`, `hd hwp render`).

compare draws both files with the same backend and checks every page:
  COMPARE PAGES <n> -> <m>                      the page count (a change means the text pushed pages)
  COMPARE PAGE <n> SAME | TEXT <k> | FORM <k>   preview: TEXT = only text elements changed; FORM = lines, boxes,
                                                pictures moved or changed (the form itself is not the same)
  COMPARE PAGE <n> INK <percent>                hangul: share of 4 x 4 px cells whose ink differs
and writes <stem>_compare.html (preview: before | after with red boxes on what changed) or
<stem>_compare_p<N>.png (hangul: before | after side by side). Returns the number of FORM / page count findings.
"""
import html
import os
import re
import sys

from ..core import registry, tmpdir

BOX = re.compile(r'\b(x|y|x1|y1|x2|y2|width|height|font-size)="(-?[\d.]+)[" ]')


MAX_PAGES = 200            # the Hangul backend writes at most this many page images of a file


def refuse_overwrite(out_dir, stems):
    """No file of an earlier run is overwritten: a page image, preview or compare file of these stems in `out_dir` stops the command."""
    if not os.path.isdir(out_dir):
        return
    pat = re.compile(r'^(?:%s)_(?:p\d+\.(?:png|svg)|preview\.html|compare(?:_p\d+\.png|\.html))$' % '|'.join(re.escape(s) for s in stems))
    for n in sorted(os.listdir(out_dir)):
        if pat.match(n):
            raise FileExistsError(f'{os.path.join(out_dir, n)} exists already: give an empty folder (nothing is overwritten)')


def pick(backend):
    """The backend of a command: `preview` (the default; `auto` of old command lines means the same) or `hangul` (only on request:
    it opens a safe copy, HW109)."""
    backend = 'preview' if backend == 'auto' else backend
    if backend not in ('preview', 'hangul'):
        raise ValueError(f'unknown backend: {backend}')
    return backend


# ---- preview (no Hangul) ----------------------------------------------------------------------------------------------
def spec_pages(path, dpi=96):
    """[(w mm, h mm, svg text)] of every page of a .hwp: tospec (Hangul's own line starts kept) -> the preview's
    `specpages` backend, with no HWPX in between."""
    from . import tospec
    work = tmpdir.mkdtemp('hwp5_render_')
    stem = os.path.splitext(os.path.basename(path))[0]
    spec = tospec.read(path, os.path.join(work, stem + '.json'), placeholders=True)
    missing = spec.pop('_not_drawn', [])
    for kind in sorted(set(missing)):
        print(f'PREVIEW NOT DRAWN hwp {kind} x{missing.count(kind)}')
    fn = registry.backend('specpages', 'preview')
    if fn is None:
        raise RuntimeError('the preview package is not there')
    return fn(spec, work, dpi)


def svg_pages(path):
    """[svg text] of every page of a .hwp, drawn by the preview."""
    return [svg for _, _, svg in spec_pages(path)]


def preview_files(path, out_dir, dpi=96):
    """<stem>_p<N>.svg and <stem>_preview.html (+ <stem>_p<N>.png with Edge on Windows) in out_dir; returns the page
    files (PNG when there are, else SVG)."""
    pages = spec_pages(path, dpi)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    svgs = []
    for n, (_, _, svg) in enumerate(pages, 1):
        p = os.path.join(out_dir, f'{stem}_p{n}.svg')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(svg)
        svgs.append(p)
    csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data: file:; '
           'style-src \'unsafe-inline\'; font-src file: data:">')
    page = os.path.join(out_dir, stem + '_preview.html')
    with open(page, 'w', encoding='utf-8') as f:
        f.write('<!doctype html><html><head><meta charset="utf-8">' + csp + f'<title>{html.escape(stem)}</title>'
                '<style>html,body{margin:0;padding:0}svg{break-after:page}svg:last-child{break-after:auto}</style>'
                '</head><body>' + '\n'.join(svg for _, _, svg in pages) + '</body></html>')
    if os.name != 'nt':
        return svgs
    try:                                           # PNG through Edge (Windows), as the preview does
        from ..render import render as rr
        pngs = rr.html_pages(page, out_dir, dpi)
    except Exception as e:                         # no Edge: the SVG pages stay
        print('NO PNG (%s)' % e)
        return svgs
    out = []
    for n, p in enumerate(pngs, 1):
        dst = os.path.join(out_dir, f'{stem}_p{n}.png')
        if os.path.exists(dst):
            os.remove(dst)
        os.replace(p, dst)
        out.append(dst)
    return out or svgs


# ---- Hangul (Windows) -------------------------------------------------------------------------------------------------
def hangul_pages(paths, out_dir, dpi=96, stems=None):
    """Open each .hwp in Hangul (format HWP) and write <stem>_p<N>.png. {path: [png] or None}. `Hwp.open` opens a safe copy
    (hwpcom `_safe_copy`: no macros, no links to outside), so nothing is done here for that."""
    from ..render import img
    from ..render.hwpcom import run_jobs
    os.makedirs(out_dir, exist_ok=True)
    result = {}

    def job(h, p):
        stem = os.path.join(out_dir, (stems or {}).get(p) or os.path.splitext(os.path.basename(p))[0])
        if not h.open(p, fmt='HWP'):
            print('OPEN FAIL', p)
            result[p] = None
            return False
        h.run('Cancel')
        h.hwp.MovePos(2, 0, 0)
        pngs = []
        if h.hwp.PageCount > MAX_PAGES:
            print(f'NOTE {os.path.basename(p)} has {h.hwp.PageCount} pages: only the first {MAX_PAGES} are written')
        for bmp in h.page_images(stem, dpi=dpi, fmt='bmp', limit=MAX_PAGES):
            if os.path.exists(bmp):
                png = bmp[:-4] + '.png'
                img.save_png(png, img.load(bmp))
                os.remove(bmp)
                pngs.append(png)
        print('OPEN OK', p, 'pages', len(pngs))
        result[p] = pngs
        return True
    run_jobs(paths, job)
    return result


def pages(path, out_dir, backend='preview', dpi=96):
    refuse_overwrite(out_dir, [os.path.splitext(os.path.basename(path))[0]])
    os.makedirs(out_dir, exist_ok=True)
    if pick(backend) == 'hangul':
        return hangul_pages([path], out_dir, dpi).get(path) or []
    return preview_files(path, out_dir, dpi)


# ---- compare ----------------------------------------------------------------------------------------------------------
def elements(svg):
    """(text elements, other elements) of a preview page, one SVG element per line."""
    body = [x for x in svg.split('\n') if x.startswith('<') and not x.startswith(('<svg', '</svg', '<rect width='))]
    text = [x for x in body if x.startswith('<text')]
    other = [x for x in body if not x.startswith('<text')]
    return text, other


def bbox(el):
    v = {}
    for k, n in BOX.findall(el):
        v.setdefault(k, float(n))
    if 'x1' in v:
        x0, x1 = sorted((v['x1'], v.get('x2', v['x1'])))
        y0, y1 = sorted((v['y1'], v.get('y2', v['y1'])))
        return x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5
    if el.startswith('<text') and 'font-size' in v:
        size = v['font-size']
        xs = [float(t) for t in re.search(r'\bx="([^"]*)"', el).group(1).split()] if ' x="' in el else [0.0]
        return min(xs), v.get('y', 0) - size, max(xs) + size, v.get('y', 0) + size * 0.3
    if 'x' in v and 'width' in v:
        return v['x'], v.get('y', 0), v['x'] + v['width'], v.get('y', 0) + v.get('height', 0)
    return None


def changed(a, b):
    """Elements of b that a does not have (as a multiset)."""
    from collections import Counter
    left = Counter(a)
    out = []
    for e in b:
        if left[e]:
            left[e] -= 1
        else:
            out.append(e)
    return out


def marks(svg, els, colour):
    boxes = [bbox(e) for e in els]
    rects = ''.join('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" fill-opacity="0.18" stroke="%s" '
                    'stroke-width="0.4"/>' % (b[0], b[1], b[2] - b[0], b[3] - b[1], colour, colour) for b in boxes if b)
    return svg.replace('</svg>', rects + '</svg>')


def compare_preview(before, after, out_dir, out=print):
    pa, pb = svg_pages(before), svg_pages(after)
    fails = 0
    out(f'COMPARE PAGES {len(pa)} -> {len(pb)}')
    if len(pa) != len(pb):
        fails += 1
    rows = []
    for n in range(max(len(pa), len(pb))):
        sa = pa[n] if n < len(pa) else ''
        sb = pb[n] if n < len(pb) else ''
        ta, oa = elements(sa)
        tb, ob = elements(sb)
        moved = changed(oa, ob) + changed(ob, oa)
        text = changed(ta, tb)
        if not sa or not sb:
            out(f'COMPARE PAGE {n + 1} {"ADDED" if not sa else "REMOVED"}')
        elif moved:
            out(f'COMPARE PAGE {n + 1} FORM {len(moved)} (lines, boxes or pictures moved or changed)')
            fails += 1
        elif text:
            out(f'COMPARE PAGE {n + 1} TEXT {len(text)}')
        else:
            out(f'COMPARE PAGE {n + 1} SAME')
        rows.append((n + 1, sa, marks(marks(sb, text, '#E00000'), changed(oa, ob), '#0050E0') if sb else ''))
    stem = os.path.splitext(os.path.basename(after))[0]
    os.makedirs(out_dir, exist_ok=True)
    page = os.path.join(out_dir, stem + '_compare.html')
    csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; '
           'style-src \'unsafe-inline\'">')
    cells = ''.join(f'<h2>{n}</h2><div class="row"><div><p>before</p>{a}</div><div><p>after (red: text changed, blue: '
                    f'lines / boxes moved)</p>{b}</div></div>' for n, a, b in rows)
    with open(page, 'w', encoding='utf-8') as f:
        f.write('<!doctype html><html><head><meta charset="utf-8">' + csp + f'<title>{html.escape(stem)} compare</title>'
                '<style>body{font-family:sans-serif;margin:16px;background:#eee}.row{display:flex;gap:16px;flex-wrap:wrap}'
                '.row>div{flex:1;min-width:300px}svg{width:100%;height:auto;box-shadow:0 0 4px #999;background:#fff}'
                '</style></head><body>' + cells + '</body></html>')
    out(f'COMPARE WRITTEN {page}')
    return fails


def compare_hangul(before, after, out_dir, dpi=96, out=print):
    from ..render import img
    stems = {before: os.path.splitext(os.path.basename(before))[0] + '_before',
             after: os.path.splitext(os.path.basename(after))[0] + '_after'}
    res = hangul_pages([before, after], out_dir, dpi, stems)
    pa, pb = res.get(before) or [], res.get(after) or []
    fails = int(len(pa) != len(pb))
    out(f'COMPARE PAGES {len(pa)} -> {len(pb)}')
    for n, (a, b) in enumerate(zip(pa, pb), 1):
        ia, ib = img.load(a), img.load(b)
        out(f'COMPARE PAGE {n} INK {img.compare(ia, ib):.2f}')
        dst = os.path.join(out_dir, f'{stems[after]}_compare_p{n}.png')
        img.save_png(dst, img.side_by_side([ia, ib]))
    return fails


def compare(before, after, out_dir, backend='preview', dpi=96, out=print):
    stems = [os.path.splitext(os.path.basename(p))[0] for p in (before, after)]
    refuse_overwrite(out_dir, stems + [s + '_before' for s in stems] + [s + '_after' for s in stems])
    if pick(backend) == 'hangul':
        return compare_hangul(before, after, out_dir, dpi, out)
    return compare_preview(before, after, out_dir, out)


def main(args):
    dpi, backend = 96, 'preview'
    if '--dpi' in args:
        i = args.index('--dpi')
        dpi = int(args[i + 1])
        del args[i:i + 2]
    if '--backend' in args:
        i = args.index('--backend')
        backend = args[i + 1]
        del args[i:i + 2]
    cmd, rest = args[0], args[1:]
    try:
        if cmd == 'render' and len(rest) >= 2:                 # the output folder is required: never the folder of the received file
            for p in pages(rest[0], rest[1], backend, dpi):
                print('PAGE', p)
            return 0
        if cmd == 'render' and rest:
            print('NOT WRITTEN: name an output folder, for example `hd hwp render form.hwp out/` (the pages are not written next to '
                  'the received file)')
            return 2
        if cmd == 'compare' and len(rest) >= 3:
            return 1 if compare(rest[0], rest[1], rest[2], backend, dpi) else 0
    except FileExistsError as e:
        print('NOT WRITTEN:', e)
        return 2
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
