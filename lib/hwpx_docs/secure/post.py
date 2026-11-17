"""Protect an HWPX with Hangul itself (a post-step: Hangul opens the file, sets the protection, saves a new file).

  python post.py <in.hwpx> <out.hwpx> --password-env NAME                       document password (open password)
  python post.py <in.hwpx> <out.hwpx> --password-env NAME --distribute [--no-print] [--no-copy]
                                                                                 distribution document (배포용)
  python post.py --info <file.hwpx> [...]                                        protection report, no Hangul

The password is read from the environment variable NAME, which the user names and sets. It is never a command-line
argument (a `--password` option is refused), and it is never printed, logged, written to a file or put in a job
item. The whole batch runs in ONE hidden Hangul, so the file-access prompt ("모두 허용") comes at most once; the user
answers it, this code never does (see render/hwpcom.py). Hangul's own security settings and the registry are not touched.
No cipher is written here: Hangul protects the file; the result is checked only by the package marks (core/protect.py).
Result lines: `SECURE OK <in> -> <out> (password|distribution)` or `SECURE FAIL <in>: <reason>`.
Exit code 0 = done, 1 = failed, 2 = usage, 3 = Hangul (Windows + Hangul + pywin32) is missing.
"""
from ..core import tmpdir
import os
import shutil
import sys
import uuid

from ..core import protect

NO_HANGUL = ('NO HANGUL: protecting a file needs Windows, Hancom Office Hangul (2024 tested) and pywin32 '
             '(pip install pywin32). Without Hangul you can still read the protection of a file: secure --info.')
USAGE = ('usage: secure <in.hwpx> <out.hwpx> --password-env NAME [--distribute [--no-print] [--no-copy]]\n'
         '       secure <in.hwpx> <out.hwpx> --mask-private      (hide ID, phone, e-mail, card numbers; no Hangul)\n'
         '       secure --info <file.hwpx> [...]')
REFUSED = ('--password', '--pw', '-p', '--passwd')


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


def plan(args):
    """Command line -> (options, error text or None). Options: {'info': [paths]} or
    {'pairs': [(src, dst)], 'env': NAME, 'distribute': bool, 'no_print': bool, 'no_copy': bool}."""
    rest = list(args)
    for a in rest:
        if a.split('=')[0] in REFUSED:
            return None, 'a password is never accepted on the command line: set an environment variable and use --password-env NAME'
    if '--info' in rest:
        files = [a for a in rest if a != '--info']
        if not files or any(a.startswith('-') for a in files):
            return None, USAGE
        return {'info': files}, None
    if '--mask-private' in rest:                                   # no Hangul, no password: see mask.py
        rest = [a for a in rest if a != '--mask-private']
        if len(rest) != 2 or any(a.startswith('-') for a in rest) or not all(a.lower().endswith('.hwpx') for a in rest):
            return None, USAGE
        if os.path.abspath(rest[0]).lower() == os.path.abspath(rest[1]).lower() or not os.path.isfile(rest[0]):
            return None, f'input not found, or output is the input file: {rest[0]}'
        return {'mask': tuple(rest)}, None
    flags = {f: f in rest for f in ('--distribute', '--no-print', '--no-copy')}
    rest = [a for a in rest if a not in flags]
    env = None
    if '--password-env' in rest:
        i = rest.index('--password-env')
        if i + 1 >= len(rest):
            return None, '--password-env needs the name of an environment variable'
        env = rest[i + 1]
        del rest[i:i + 2]
    if env is None:
        return None, 'no password source: --password-env NAME is required\n' + USAGE
    if (flags['--no-print'] or flags['--no-copy']) and not flags['--distribute']:
        return None, '--no-print and --no-copy belong to a distribution document: add --distribute'
    if len(rest) != 2 or any(a.startswith('-') for a in rest):
        return None, USAGE
    src, dst = rest
    if not src.lower().endswith('.hwpx') or not dst.lower().endswith('.hwpx'):
        return None, 'input and output must be .hwpx files'
    if os.path.abspath(src).lower() == os.path.abspath(dst).lower():
        return None, f'output is the input file: {src}'
    if not os.path.isfile(src):
        return None, f'input not found: {src}'
    return {'pairs': [(src, dst)], 'env': env, 'distribute': flags['--distribute'],
            'no_print': flags['--no-print'], 'no_copy': flags['--no-copy']}, None


def report(path):
    """One line: the protection of `path` ("none" or "encrypted ..."). No Hangul."""
    info = protect.detect(path)
    if not info:
        return f'PROTECTION {path}: none'
    return (f'PROTECTION {path}: encrypted ({len(info["parts"])} part(s); password or distribution document; '
            f'{info["algorithm"] or "algorithm not listed"})')


def save_distributed(h, dst, password, no_print, no_copy):
    """SaveAs a copy, make it a distribution document in place with Hangul's FileSetSecurity, copy it to `dst`.
    (The same temp-path rule as Hwp.save: SaveAs goes to a never-used path.)"""
    dst = os.path.abspath(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = os.path.join(tmpdir.mkdtemp('hwpcom_'), uuid.uuid4().hex + '.hwpx')
    h.temps.append(tmp)
    h.guard()
    h.hwp.SaveAs(tmp, 'HWPX', '')
    if not os.path.exists(tmp):
        return False
    if not h.act('FileSetSecurity', 'HFileSetSecurity', Password=password, NoPrint=int(no_print), NoCopy=int(no_copy)):
        return False
    shutil.copyfile(tmp, dst)
    return True


def secure_job(h, item, opts, password):
    """One file in an open Hangul session `h` (methods open, save, act, guard, temps, hwp). item = (src, dst)."""
    src, dst = item
    kind = 'distribution' if opts['distribute'] else 'password'
    if protect.detect(src):
        print(f'SECURE FAIL {src}: the input is already protected (Hangul cannot open it without its password)')
        return False
    if not h.open(src, 'HWPX'):
        print(f'SECURE FAIL {src}: Hangul did not open it (damaged, or the access prompt was not allowed)')
        return False
    if opts['distribute']:
        ok = save_distributed(h, dst, password, opts['no_print'], opts['no_copy'])
    else:
        ok = bool(h.act('FilePassword', 'HPassword', string=password)) and h.save(dst, 'HWPX')
    if not ok:
        print(f'SECURE FAIL {src}: Hangul did not set the {kind} protection or did not save')
        return False
    if not protect.detect(dst):
        print(f'SECURE FAIL {src}: the saved file shows no protection marks')
        return False
    print(f'SECURE OK {src} -> {dst} ({kind})')
    return True


def apply(opts):
    """Run the batch in one Hangul. Returns {(src, dst): True/False}. Raises RuntimeError(NO_HANGUL) if Hangul is
    missing, ValueError if the environment variable is not set (its name is in the text, its value never)."""
    password = os.environ.get(opts['env'])
    if not password:
        raise ValueError(f'environment variable {opts["env"]} is not set or empty')
    if not hangul_available():
        raise RuntimeError(NO_HANGUL)
    from ..render.hwpcom import run_jobs
    return run_jobs(opts['pairs'], lambda h, item: secure_job(h, item, opts, password))


def main(args):
    opts, err = plan(args)
    if err:
        print(err)
        return 2
    if 'info' in opts:
        for p in opts['info']:
            print(report(p))
        return 0
    if 'mask' in opts:
        from . import mask
        n = mask.apply(*opts['mask'])
        print(f'SECURE MASK OK {opts["mask"][0]} -> {opts["mask"][1]} ({n} item(s) hidden)')
        return 0
    try:
        result = apply(opts)
    except ValueError as e:
        print(e)
        return 2
    except RuntimeError as e:
        print(e)
        return 3
    return 0 if all(result.values()) else 1


def _selftest():
    """No Hangul: argument planning, the password rules, the job logic with a fake session, the --info report."""
    import contextlib
    import io
    import subprocess
    from ..core import build
    d = tmpdir.mkdtemp('hwpx_docs_sec_')
    src, out = os.path.join(d, 'a.hwpx'), os.path.join(d, 'out.hwpx')
    build.write({'body': [{'p': '보안 시험'}]}, src)
    PW = 'Throwaway-' + uuid.uuid4().hex[:8]               # test value, lives in this process only

    # planning
    o, e = plan([src, out, '--password-env', 'X_PW'])
    assert not e and o['pairs'] == [(src, out)] and o['env'] == 'X_PW' and not o['distribute'], (o, e)
    o, e = plan([src, out, '--password-env', 'X_PW', '--distribute', '--no-print', '--no-copy'])
    assert not e and o['distribute'] and o['no_print'] and o['no_copy']
    assert plan([src, out, '--password', 'abc'])[1] and plan([src, out, '--password=abc'])[1] and plan([src, out, '-p', 'a'])[1]
    assert plan([src, out])[1] and plan([src, out, '--password-env'])[1]
    assert plan([src, out, '--password-env', 'X', '--no-print'])[1]                  # needs --distribute
    assert plan([src, src, '--password-env', 'X'])[1] and plan(['none.hwpx', out, '--password-env', 'X'])[1]
    assert plan([src, os.path.join(d, 'o.txt'), '--password-env', 'X'])[1]
    assert plan(['--info', src])[0] == {'info': [src]} and plan(['--info'])[1]

    class Hw:                                               # stands for hwp.hwp (the COM object)
        def __init__(self, h):
            self.h = h

        def SaveAs(self, path, fmt, arg):
            self.h.calls.append(('SaveAs', fmt))
            open(path, 'wb').write(open(src, 'rb').read())

    class Fake:                                             # stands for hwpcom.Hwp
        def __init__(self, ok=True):
            self.calls, self.temps, self.hwp, self.ok, self.pending = [], [], Hw(self), ok, None

        def guard(self, seconds=None):
            pass

        def open(self, path, fmt):
            self.calls.append(('open', fmt))
            return True

        def act(self, action, setname, /, **items):
            self.calls.append(('act', action, setname, sorted(items)))
            self.pending = action
            self.items = items
            return self.ok

        def save(self, path, fmt):
            self.calls.append(('save', fmt))
            protect.fake_protected(src, path) if self.pending == 'FilePassword' else shutil.copyfile(src, path)
            return True

    def run(h, opts):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = secure_job(h, (src, out), opts, PW)
        assert PW not in buf.getvalue()                      # the password is never printed
        return ok, buf.getvalue()
    base = {'pairs': [(src, out)], 'env': 'X', 'distribute': False, 'no_print': False, 'no_copy': False}
    h = Fake()
    ok, text = run(h, base)
    assert ok and h.calls == [('open', 'HWPX'), ('act', 'FilePassword', 'HPassword', ['string']), ('save', 'HWPX')], h.calls
    assert h.items == {'string': PW} and 'SECURE OK' in text and '(password)' in text
    assert protect.detect(out)
    os.remove(out)
    h = Fake()                                              # distribution: the fake SaveAs writes an unprotected copy
    ok, text = run(h, dict(base, distribute=True, no_print=True))      # -> the job must see "no protection marks"
    assert not ok and 'no protection marks' in text and h.items == {'Password': PW, 'NoPrint': 1, 'NoCopy': 0}, (text, h.items)
    assert h.calls[0] == ('open', 'HWPX') and h.calls[1] == ('SaveAs', 'HWPX') and h.calls[2][1] == 'FileSetSecurity'
    for t in h.temps:
        os.remove(t)
    ok, text = run(Fake(ok=False), base)
    assert not ok and 'did not set' in text
    prot = os.path.join(d, 'p.hwpx')
    protect.fake_protected(src, prot)
    h = Fake()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert not secure_job(h, (prot, out), base, PW) and h.calls == []   # an input that is already protected is refused
    assert 'already protected' in buf.getvalue()

    # environment variable and exit codes (no Hangul started: the checks come before it)
    os.environ.pop('HWPX_DOCS_NOPE', None)
    with contextlib.redirect_stdout(io.StringIO()):
        assert main([src, out, '--password-env', 'HWPX_DOCS_NOPE']) == 2
        assert main([src, out, '--password', 'x']) == 2
        assert main(['--info', src, prot]) == 0
    assert report(src).endswith(': none') and 'encrypted (2 part(s)' in report(prot)

    # the whole CLI, as a process: protected files give a clear message, never a traceback
    hd = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'hd.py')
    r = subprocess.run([sys.executable, '-I', hd, 'read', prot, os.path.join(d, 'r.json')],
                       capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == protect.EXIT_CODE and 'PROTECTED:' in r.stdout and 'Traceback' not in r.stderr, (r.returncode, r.stderr[-300:])
    r = subprocess.run([sys.executable, '-I', hd, 'secure', '--info', prot], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0 and 'encrypted' in r.stdout, r.stdout
    # --mask-private (no Hangul): text between tags only, other text and the input stay as they are
    from . import mask
    fake = '번호 000000-1000000 전화 010-0000-0000 메일 a.b@example.com 카드 0000-1111-2222-3333 끝'
    t, k = mask.mask_text(fake)
    assert k == 4 and t == '번호 000000-******* 전화 ***-****-**** 메일 *.*@*******.*** 카드 ****-****-****-**** 끝', t
    assert mask.mask_text('1234-5678 7 abc')[1] == 0
    m_in, m_out = os.path.join(d, 'm.hwpx'), os.path.join(d, 'm_out.hwpx')
    build.write({'body': [{'p': fake}, {'p': '보통 문장'}]}, m_in)
    assert mask.apply(m_in, m_out) == 4
    import zipfile
    s = zipfile.ZipFile(m_out).read('Contents/section0.xml').decode('utf-8')
    assert '010-0000-0000' not in s and '***-****-****' in s and '보통 문장' in s
    assert '010-0000-0000' in zipfile.ZipFile(m_in).read('Contents/section0.xml').decode('utf-8')
    assert zipfile.ZipFile(m_out).namelist() == zipfile.ZipFile(m_in).namelist() and not protect.detect(m_out)
    # the preview text and picture of the file must not keep what the sections hide (security review 2026-11-15)
    m_prev = os.path.join(d, 'm_prev.hwpx')
    with zipfile.ZipFile(m_in) as zi, zipfile.ZipFile(m_prev, 'w') as zo:
        for it in zi.infolist():
            if it.filename not in ('Preview/PrvText.txt', 'Preview/PrvImage.png'):
                zo.writestr(it, zi.read(it.filename))
        zo.writestr('Preview/PrvText.txt', fake.encode('utf-16'))
        zo.writestr('Preview/PrvImage.png', b'\x89PNG\r\n\x1a\n' + b'old page picture')
    assert mask.apply(m_prev, m_out) == 4
    with zipfile.ZipFile(m_out) as z:
        prv = z.read('Preview/PrvText.txt').decode('utf-16')
        assert '010-0000-0000' not in prv and '***-****-****' in prv and b'old page picture' not in z.read('Preview/PrvImage.png'), prv
    assert plan([m_in, m_out, '--mask-private'])[0] == {'mask': (m_in, m_out)} and plan([m_in, '--mask-private'])[1]
    try:
        mask.apply(prot, m_out)
        raise AssertionError('a protected input must be refused')
    except protect.ProtectedDocument:
        pass
    print('secure self-check ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        _selftest()
    else:
        sys.exit(main(sys.argv[1:]))
