"""secure: protect an HWPX with Hangul itself (password, distribution document) and report the protection of a file.

Public interface (other modules use only these):
  secure.protection(path) -> None | {'kind': 'encrypted', 'parts': [...], 'algorithm': str}   (no Hangul; core.protect)
  secure.apply(opts) -> {(src, dst): bool}      one hidden Hangul for the batch; RuntimeError (NO_HANGUL) if missing
  secure.plan(args) -> (opts, error or None)     command line -> options (the password is read from an environment
                                                 variable that the user names; it is never an argument)
Depends on core only, plus `render.hwpcom.run_jobs` (the one Hangul COM session; it should move to core).
Rules: no cipher is written or reverse-engineered (Hangul does the protecting; the reader only detects the package
marks); the password is never printed, logged or stored; Hangul's own security settings and the registry are not touched.
Tests: the self-test uses a fake Hangul session and a fake protected package (no Hangul needed).
Docs: docs/coverage.md section C11.
"""
COMMANDS = {
    'secure': ('post', [], '<in.hwpx> <out.hwpx> --password-env NAME [--distribute [--no-print] [--no-copy]] | '
                             '--mask-private | --info <file.hwpx>...  password / distribution document with Hangul; '
                             'hide personal data (no Hangul); protection report'),
}


def protection(path):
    from ..core import protect
    return protect.detect(path)


def plan(args):
    from . import post as m
    return m.plan(args)


def apply(opts):
    from . import post as m
    return m.apply(opts)


def selftest():
    from . import post as m
    m._selftest()
