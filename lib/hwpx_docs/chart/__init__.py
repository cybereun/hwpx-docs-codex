"""Native Hangul chart package (coverage C6.10). Depends on `hwpx_docs.core` only.

Public interface (one line): `ooxml.chart_xml(spec)`, `ooxml.parse(xml, strict=True)`, `draw.svg(spec, x, y)`; spec
block `{"chart": {"native": true, ...}}`; command `hd chart make|dump`. It registers itself (core/registry.py):
COMMANDS, selftest, BLOCKS, READS, DRAWS below.

Files: ooxml.py (chart spec <-> `Chart/chartN.xml`), section.py (`hp:chart` writer and reader, builder/reader hooks),
draw.py (the chart as a viewer draws it: SVG in Hangul's default style),
cli.py (`hd chart make|dump`), tests.py (self-test), fixtures/ (Hangul-made samples), rules.md (CH01-CH11), spec.md (spec keys),
coverage.md (rows). A fix to charts touches this folder only.
"""
COMMANDS = {
    'chart': ('cli', [], 'make <chart.json> <out.hwpx> | dump <in.hwpx>  native Hangul chart object'),
}
BLOCKS = {'chart': 'section:block'}       # builder: a `chart` block with native: true
READS = {'switch': 'section:read'}        # reader: hp:switch that holds an hp:chart
DRAWS = {'chart': 'draw:svg'}             # viewer (preview): the chart as SVG


def selftest():
    from . import tests as t
    t.run()
