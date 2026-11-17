"""extract: HWPX -> plain text or Markdown (headings, Markdown tables, footnotes).

Public interface: extract.extract(path, md=False) -> str. Depends on core only (read; build in the self-test).
Tests: the self-test of extract.py builds its own sample (no fixture files).
"""
COMMANDS = {
    'text': ('extract', [], '<in.hwpx> [--md] [-o f]  plain text or Markdown'),
}


def selftest():
    from . import extract
    extract.selftest()
