"""pagex: page layout beyond `page/` (coverage C4.12, C4.13, C4.16, C4.17, C10.01-C10.03, C10.05-C10.08).

Depends on `hwpx_docs.core` only. Registers itself (core/registry.py): SECTION hooks (builder and reader of section level
keys), BLOCKS (body blocks), COMMANDS, selftest.

Spec keys (spec.md): `header_odd`, `header_even`, `footer_odd`, `footer_even`; `master_pages`; `text_direction`; `line_numbers`;
`manuscript`; `hide_first`; `note_shape`; body blocks `hide_page`, `columns_here`.
Files: section.py (section builder/reader), body.py (body blocks), tests.py (self-test), rules.md (PX01-), spec.md, coverage.md,
jobs.md (Hangul work that is still open). A fix to these features touches this folder only.
"""
SECTION = {'build': 'section:build', 'read': 'section:read'}
COMMANDS = {'pagex': ('make_samples', [], 'list | run [name ...] [--out DIR] [--png DIR]  Hangul pair samples (needs Hangul; agreed window only)')}
BLOCKS = {'hide_page': 'body:hide_page', 'columns_here': 'body:columns_here'}


def selftest():
    from . import tests
    tests.run()
