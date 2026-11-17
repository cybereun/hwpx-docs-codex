"""edit: change the text of an existing HWPX (a received form) and keep everything else; check the result.

Public interface (other modules use only these):
  edit.Doc(path)   .slots() -> [{key, label, text}], .fill({key or label: text}) -> missing keys,
                   .set(key, text), .replace(old, new) -> count, .check(label, mark='☑') -> bool, .save(dst) -> dst
  guard.report(original, edited, forbid=(), require=(), max_unchanged=None, out=print) -> fail count
Depends on core only (read, build in the self-test, layout and textfit for the line budget).
Tests: the self-tests of edit.py and guard.py build their own samples (no fixture files).
"""
COMMANDS = {
    'slots': ('edit', ['slots'], '<in.hwpx> [--json f]  editable slots (paragraphs, cells, labels) of a file'),
    'edit': ('edit', [], '<in.hwpx> <out.hwpx> [...]  change text only: --values/--set/--replace/--check'),
    'guard': ('guard', [], '<original.hwpx> <edited.hwpx>  structure, text budget (page drift), residue'),
}


def selftest():
    from . import edit, guard
    edit.selftest()
    guard.selftest()
