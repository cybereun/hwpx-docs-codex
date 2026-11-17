"""page: sections (page size, margins, columns, header/footer, page numbers, page border). Mixed into core.build.Doc.

Tests: the self-test of page.py builds its own samples (no fixture files).
"""


def selftest():
    from . import page
    page.selftest()
