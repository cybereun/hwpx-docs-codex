"""Text style package: custom tab stops (C2.10), user styles and style links (C3.03, C3.04), drop cap (C9.01),
스타일마당 (C9.05), picture bullets (C2.19 = C8.08), 한자 병기 (C8.07), 덧말 (C7.04), Latin line break (C2.09).
Depends on `hwpx_docs.core` only. It registers itself (core/registry.py): COMMANDS, selftest below.

Spec keys (spec.md): paragraph `tabs`; document `named_styles`; block or run `style`. The small hooks of core that these
keys need (header tab/style registry, `Doc.define_styles`, reader) are listed in rules.md. Files: rules.md (TS01-),
spec.md, coverage.md (rows), samples.py (Hangul COM sample maker), cli.py, tests.py. Fixtures: tests/fixtures.
"""
COMMANDS = {
    'textstyle': ('cli', [], 'samples <phase> <out_dir> [name ...] | dump <in.hwpx>  tab stops, styles: Hangul samples and a dump'),
}
BLOCKS = {'dropcap': 'dropcap:block', 'run.dropcap': 'dropcap:run', 'run.dutmal': 'dutmal:run'}      # builder (TS12, TS14, TS17)
READS = {'rect': 'dropcap:read', 'dutmal': 'dutmal:read'}                                           # reader


def selftest():
    from . import tests as t
    t.run()
