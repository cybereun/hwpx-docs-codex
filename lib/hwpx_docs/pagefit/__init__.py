"""pagefit: pages that read without turning back and look full (checks and fixes on the spec; no Hangul needed).

Public interface (one line): `model.pages(spec, pic_dir)` (pages with their blocks and fill), `check.check(spec, pic_dir, fill, last_lines)`
-> (findings, pages), `fix.fix(spec, pic_dir, profile=None)` -> log lines (the spec changes in place); commands `hd pagefit check|fix|profiles`.
It registers itself (core/registry.py): COMMANDS, selftest. Depends on core and, through the registered backends `blocks` and `pagereport` / `preview`
(`registry.backend`), on the line and table-row heights and the page flow of the preview package (columns, footnotes, objects); it imports
no other feature package except the constant `preview.measure.PT`.

Files: profile.py and profiles/ (the rules as a named style: minimal, readable, your own JSON), model.py (load, page model with the keep rules measured against Hangul), units.py (reading units), check.py (findings), fix.py
(the steps), cli.py, tests.py and tests_units.py,
rules.md (the rules and what is measured), the spec keys it sets are in `docs/spec.md` (`keep_next`, `widow`, `page_break_before`, `after`).
"""
COMMANDS = {
    'pagefit': ('cli', [], 'check <in> | fix <in> <out>  pages that read well and look full (checks and fixes the spec; no Hangul)'),
}


def selftest():
    from . import tests as t
    t.run()
