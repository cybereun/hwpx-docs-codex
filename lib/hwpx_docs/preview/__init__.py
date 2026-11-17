"""preview: draw the pages of an HWPX with no Hangul and no third-party program (stdlib only; Edge only for PNG).

Public interface (other packages use only these):
  preview.render_pages(path, dpi=96) -> [(width mm, height mm, svg text)]   one SVG per page (no Edge needed)
  preview.render_files(path, out_dir, dpi=96, png=True) -> [png path]       SVG + HTML (+ PNG through Edge) files
Commands (registered, core/registry.py): `hd preview <in.hwpx> [out_dir] [--dpi 96] [--no-png]`; the same renderer is
the `preview` (alias `own`) backend of `hd render hwpx <file> --backend preview`; `--backend auto` = Hangul when it is
installed, else preview.
Depends on core (`core.read`, `core.textfit`) and, for the PNG step and the fidelity test only, on the public functions
`render.render.html_pages` (Edge print -> PNG) and `render.img` (ink difference).

Files: measure.py (styles, widths), svg.py (SVG writer), layout.py (lines, tables, shapes; objects only through
drawers/), drawers/ (one module per kind of object: register(key, fn), register_inline(tag, fn); see
docs/interfaces.md "Preview drawers"; charts come from the chart package's DRAWS), flow.py (pages, sections; `lay_out(spec, dir, trace)`), blocks.py and report.py (block atoms and the page report for page-planning tools such as pagefit),
output.py (SVG/HTML/PNG files), cli.py (`hd preview`), tests.py (self-test + fidelity against Hangul pages),
fixtures/ (Hangul reference pages, fidelity.json), rules.md (P01-P08, measured layout rules), coverage.md (C13 rows and the
fidelity table). A fix to the preview touches this folder only.
Clean-room: layout rules come from the public standard (KS X 6101), docs/rules.md, Hangul's own pages and the layout cache
(`hp:linesegarray`) that Hangul stores; no other renderer's code or notice is used.
"""
COMMANDS = {
    'preview': ('cli', [], '<in.hwpx> [out_dir] [--dpi 96] [--no-png]  page images with no Hangul (own renderer)'),
}
BACKENDS = {'render': {'preview': 'cli:render_backend', 'own': 'cli:render_backend'},
            'pages': {'preview': 'cli:pages_backend'},     # hd render hwpx f --backend preview
            'blocks': {'preview': 'blocks:section_atoms'},
            'pagereport': {'preview': 'report:page_report'}}  # what the layout makes of each block (pagefit; blocks.py)


def render_pages(path, dpi=96):
    from .flow import render_pages as f
    return f(path, dpi)


def render_files(path, out_dir, dpi=96, png=True):
    from .output import render_files as f
    return f(path, out_dir, dpi, png)


def selftest():
    from . import tests
    tests.run()
