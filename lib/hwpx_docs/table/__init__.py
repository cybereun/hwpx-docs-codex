"""Table package (coverage C5). Depends on `hwpx_docs.core` only.

Public interface: the builder mixin `table.table.TableMixin` (`Doc.table`, spec block `table`); table extras in `ext.py`
(floating position `pos`, `caption`, cell `protect` / `editable`) and `fills.py` (cell `fill` as gradient or picture).
Registers itself (core/registry.py): selftest, READS (the reader asks it for the table extras and the non-colour fills).

Files: table.py (grid, merges, lines, fills, sizes), fills.py, ext.py, tests.py (self-test), fixtures/ (Hangul-made
samples and pairs of this package), rules.md (TB rows), coverage.md (C5 rows), samples.py (makes the Hangul samples;
needs Hangul). A fix to tables touches this folder only (and the three small hook lines in core/header.py, core/read.py).
"""
COMMANDS = {
    'table-samples': ('samples', [], 'window <out_dir> | build <out_dir>  Hangul samples of the table package (window needs Hangul)'),
}
READS = {'tbl': 'ext:read_table', 'tc': 'ext:read_cell', 'fillBrush': 'ext:read_fill'}


def selftest():
    from . import tests as t
    t.run()
