"""gongmun: the official 기안문 form (fields, label words, order) as a check on a spec.

The 공문 defaults themselves are data: `templates/gongmun.json` (skeleton, named styles) and the table
`docs/gongmun-defaults.md` (official value or "convention", with the source). This package only checks wording.
Public interface: form.check(spec) -> [(id, message, line)]. Depends on core only (build in the self-test).
Tests: the self-test of form.py checks the template and the example and builds them (no fixture files).
"""
COMMANDS = {
    'gongmun-check': ('form', [], '<spec.json>  official 기안문 fields and wording (GM01-GM05)'),
}


def selftest():
    from . import form
    form.selftest()
