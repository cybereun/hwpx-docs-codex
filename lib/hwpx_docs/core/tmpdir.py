"""Temporary folders that go when the process ends: use `tmpdir.mkdtemp(prefix)` where `tempfile.mkdtemp` was used.

`tempfile.mkdtemp` leaves the folder in %TEMP% for ever (one `hd selftest` left about 12 MB, and the disk of C: filled up). A folder made
here is removed at exit (atexit, also after an error and after sys.exit); `cleanup()` removes them at once. Nothing a user asked for may
live in such a folder: results go where the user said. A file that Hangul or another program still holds open stays (ignore_errors).
"""
import atexit
import shutil
import tempfile

_dirs = []


def mkdtemp(prefix='hwpx_docs_'):
    d = tempfile.mkdtemp(prefix=prefix)
    _dirs.append(d)
    return d


def cleanup():
    while _dirs:
        shutil.rmtree(_dirs.pop(), ignore_errors=True)


atexit.register(cleanup)
