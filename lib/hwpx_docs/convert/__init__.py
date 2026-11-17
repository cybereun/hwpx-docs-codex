"""convert: change the file format of a document with Hangul itself (HWP <-> HWPX, HWP/HWPX -> PDF).

Public interface (other modules use only these):
  convert.convert(pairs) -> {(src, dst): bool}   pairs of paths; one hidden Hangul for the whole batch;
                                                 raises RuntimeError (NO_HANGUL text) if Hangul is missing
  convert.plan(args) -> (pairs, error or None)   command line -> pairs
  convert.hangul_available() -> bool             Windows + pywin32 + Hangul automation class (starts nothing)
Depends on core only, plus `render.hwpcom.run_jobs` (the one Hangul COM session; it should move to core).
Tests: the self-test builds its own files and uses a fake Hangul session (no Hangul needed).
Docs: docs/coverage.md section C12.
"""
COMMANDS = {
    'convert': ('convert', [], '<in> <out> | --to hwpx|hwp|pdf [--out-dir D] <in>...  '
                               'HWP <-> HWPX, HWP/HWPX -> PDF with Hangul (one batch)'),
}


def selftest():
    from . import convert
    convert._selftest()
