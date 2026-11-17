"""Convert documents with Hangul itself: HWP (binary) <-> HWPX, and HWP/HWPX -> PDF.

  python convert.py <in.hwp|hwpx> <out.hwp|hwpx|pdf>
  python convert.py --to hwpx|hwp|pdf [--out-dir DIR] <in> [<in> ...]       batch, output name = input stem

The output format comes from the output extension (or --to). Hangul opens each input and saves it in the new
format (Open, then SaveAs "HWPX" | "HWP" | "PDF"). The whole batch runs in ONE hidden Hangul, so the file-access
prompt of Hangul ("모두 허용") comes at most once per batch; the user answers it, this code never does
(see hwpcom.py). A result line per file: `CONVERT OK <in> -> <out>` or `CONVERT FAIL <in>: <reason>`.
Exit code 0 = all done, 1 = some failed, 3 = Hangul (Windows + Hangul + pywin32) is missing.
Hangul converts what it can read: a protected or damaged file may fail (the reason is printed).
"""
from ..core import tmpdir
import os
import sys
import zipfile

FORMATS = {'.hwp': 'HWP', '.hwpx': 'HWPX', '.pdf': 'PDF'}
READABLE = ('.hwp', '.hwpx')
NO_HANGUL = ('NO HANGUL: converting needs Windows, Hancom Office Hangul (2024 tested) and pywin32 '
             '(pip install pywin32). Without Hangul you can still make HWPX files (hd build / md / html).')


def hangul_available():
    """True if Windows, pywin32 and the Hangul automation class are all there (nothing is started)."""
    if os.name != 'nt':
        return False
    try:
        import winreg
        import win32com.client  # noqa: F401
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'HWPFrame.HwpObject'))
        return True
    except (ImportError, OSError):
        return False


def fmt_of(path):
    """Hangul format name of a path by its extension, or None."""
    return FORMATS.get(os.path.splitext(path)[1].lower())


def plan(args):
    """Command line -> ([(src, dst), ...], error text or None)."""
    to = out_dir = None
    rest = list(args)
    for flag in ('--to', '--out-dir'):
        if flag in rest:
            i = rest.index(flag)
            if i + 1 >= len(rest):
                return [], f'{flag} needs a value'
            val = rest[i + 1]
            del rest[i:i + 2]
            if flag == '--to':
                to = val.lower().lstrip('.')
            else:
                out_dir = val
    if to is None:
        if len(rest) != 2:
            return [], 'usage: convert <in> <out>   or   convert --to hwpx|hwp|pdf [--out-dir DIR] <in> ...'
        pairs = [(rest[0], rest[1])]
    else:
        if '.' + to not in FORMATS:
            return [], f'--to must be hwpx, hwp or pdf (got {to})'
        pairs = [(s, os.path.join(out_dir or os.path.dirname(os.path.abspath(s)),
                                  os.path.splitext(os.path.basename(s))[0] + '.' + to)) for s in rest]
        if not pairs:
            return [], 'no input files'
    for src, dst in pairs:
        if os.path.splitext(src)[1].lower() not in READABLE:
            return [], f'input must be .hwp or .hwpx: {src}'
        if fmt_of(dst) is None:
            return [], f'output must end with .hwp, .hwpx or .pdf: {dst}'
        if os.path.abspath(src).lower() == os.path.abspath(dst).lower():
            return [], f'output is the input file: {src}'
        if not os.path.isfile(src):
            return [], f'input not found: {src}'
    return pairs, None


def check_output(dst):
    """Reason text if the saved file is not plausible, else None."""
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        return 'no output file written'
    ext = os.path.splitext(dst)[1].lower()
    with open(dst, 'rb') as f:
        head = f.read(8)
    if ext == '.hwpx' and not (zipfile.is_zipfile(dst)):
        return 'output is not a zip (HWPX)'
    if ext == '.pdf' and not head.startswith(b'%PDF'):
        return 'output is not a PDF'
    if ext == '.hwp' and not head.startswith(b'\xd0\xcf\x11\xe0'):
        return 'output is not an HWP 5 file (OLE2)'
    return None


def convert_job(h, item):
    """One file in an open Hangul session `h` (methods open, save). item = (src, dst)."""
    src, dst = item
    if not h.open(src, fmt_of(src)):
        print(f'CONVERT FAIL {src}: Hangul did not open it (damaged, protected, or the access prompt was not allowed)')
        return False
    if not h.save(dst, fmt_of(dst)):
        print(f'CONVERT FAIL {src}: Hangul did not save {fmt_of(dst)}')
        return False
    why = check_output(dst)
    if why:
        print(f'CONVERT FAIL {src}: {why}')
        return False
    print(f'CONVERT OK {src} -> {dst}')
    return True


def convert(pairs):
    """Convert all (src, dst) pairs in one Hangul. Returns {(src, dst): True/False}.
    Raises RuntimeError(NO_HANGUL) if Hangul is missing."""
    if not hangul_available():
        raise RuntimeError(NO_HANGUL)
    from ..render.hwpcom import run_jobs
    return run_jobs(pairs, convert_job)


def main(args):
    pairs, err = plan(args)
    if err:
        print(err)
        return 2
    try:
        result = convert(pairs)
    except RuntimeError as e:
        print(e)
        return 3
    return 0 if all(result.values()) else 1


def _selftest():
    """No Hangul: argument planning, extension checks, output checks, job logic with a fake session."""
    d = tmpdir.mkdtemp('hwpx_docs_cv_')
    src = os.path.join(d, 'a.hwp')
    open(src, 'wb').write(b'\xd0\xcf\x11\xe0fake')
    assert plan([src, os.path.join(d, 'a.hwpx')])[0] == [(src, os.path.join(d, 'a.hwpx'))]
    pairs, err = plan(['--to', 'pdf', '--out-dir', os.path.join(d, 'o'), src])
    assert not err and pairs[0][1] == os.path.join(d, 'o', 'a.pdf'), (pairs, err)
    assert plan([src])[1] and plan([src, src])[1] and plan(['--to', 'doc', src])[1]
    assert plan([src, os.path.join(d, 'a.txt')])[1] and plan([os.path.join(d, 'none.hwp'), 'x.hwpx'])[1]
    assert plan(['--to', 'hwpx', os.path.join(d, 'a.txt')])[1] == f'input must be .hwp or .hwpx: {os.path.join(d, "a.txt")}'

    class Fake:                                    # stands for hwpcom.Hwp
        def __init__(self, content):
            self.content, self.calls = content, []

        def open(self, path, fmt):
            self.calls.append(('open', fmt))
            return True

        def save(self, path, fmt):
            self.calls.append(('save', fmt))
            open(path, 'wb').write(self.content)
            return True
    import contextlib
    import io
    ok_dst = os.path.join(d, 'ok.hwpx')
    h = Fake(b'PK\x05\x06' + b'\0' * 18)           # an empty zip
    with contextlib.redirect_stdout(io.StringIO()):    # the job prints OK / FAIL lines (paths); not wanted here
        assert convert_job(h, (src, ok_dst)) and h.calls == [('open', 'HWP'), ('save', 'HWPX')], h.calls
        assert not convert_job(Fake(b'not a zip'), (src, os.path.join(d, 'bad.hwpx')))
        assert not convert_job(Fake(b''), (src, os.path.join(d, 'empty.pdf')))
        assert convert_job(Fake(b'%PDF-1.7'), (src, os.path.join(d, 'x.pdf')))
        if not hangul_available():
            assert main([src, os.path.join(d, 'm.hwpx')]) == 3
    print('convert self-check ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        _selftest()
    else:
        sys.exit(main(sys.argv[1:]))
