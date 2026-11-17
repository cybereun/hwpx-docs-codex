"""hwpx-docs command line.

  python lib/hd.py <command> [arguments]

Commands (each runs one module of the package hwpx_docs; `python lib/hd.py <command> --help` is not needed:
the arguments are in the module header and in the skills):
  build <spec.json> <out.hwpx|out.hwp>    core.build      spec -> HWPX (an .hwp output goes through hwp5: no Hangul)
  (an .hwp given to a command for .hwpx runs it through hwp5: `UNSUPPORTED <what> <where>` = no mapping yet,
   `ERROR <tohwpx|fromhwpx> <exception>` = a bug; nothing is written. See docs/hwp-parity.md)
  read <in.hwpx> <out.json>                core.read       HWPX -> spec
  md <in.md> <out.hwpx> [...]              text.markdown   Markdown -> HWPX (presets)
  html <in.html> <out.hwpx> [--spec f]     text.html_css   any HTML (CSS computed like a browser) -> HWPX
  preset-from <sample> <out.json>          text.preset_from draft preset from an HWPX or a spec
  readability <in.hwpx|spec.json> [--fix f] check.readability
  check <in.hwpx> <checklist.md>           check.check_xml fidelity checklist
  measure <image.png> [--page-mm 210]      check.measure   lines, grid and text bands of a form image
  diff dump|diff|sdiff ...                 check.hwpx_diff XML difference of two HWPX files
  roundtrip <out_dir> <a.hwpx> ...         check.roundtrip HWPX -> spec -> HWPX -> render (Windows + Hangul)
  render hwpx|html|topng|side ...          render.render   page images (preview by default; Hangul with --backend hangul; Edge)
  img topng|side|overlay|compare ...       render.img      PNG/BMP convert, side by side, overlay, ink difference
  textwidth "<text>" [--font F] [--size S] core.textfit   width in pt in the real font (Windows)
  selftest                                 every module self-test (no Hangul needed)
Commands of feature packages (they register themselves, core/registry.py):"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

COMMANDS = {'build': 'core.build', 'read': 'core.read', 'md': 'text.markdown', 'html': 'text.html_css',
            'preset-from': 'text.preset_from', 'readability': 'check.readability', 'check': 'check.check_xml',
            'measure': 'check.measure', 'diff': 'check.hwpx_diff', 'roundtrip': 'check.roundtrip',
            'render': 'render.render', 'img': 'render.img', 'textwidth': 'core.textfit'}
# ponytail: the table above is the older modules' list; move an entry into its package's COMMANDS when that
# module changes next. New features never add a line here.


# A .hwp given to a command made for .hwpx. Same job in `hd hwp` -> run that (HWP_SUB). Otherwise (HWP_VIA) the lossless
# route of hwp5: each .hwp input -> temporary HWPX (tohwpx), the command, an .hwp output <- the HWPX (fromhwpx).
HWP_SUB = {'text': 'text', 'slots': 'slots', 'edit': 'edit', 'guard': 'guard', 'read': 'tospec', 'preview': 'render'}
HWP_VIA = {'text', 'build', 'md', 'html', 'form', 'pagefit', 'readability', 'check', 'diff', 'secure'}


def _docs(args):
    """Indexes of the arguments that name an .hwp or .hwpx file."""
    return [i for i, a in enumerate(args) if a.lower().endswith(('.hwp', '.hwpx'))]


def _positional_docs(args):
    """Indexes of the document arguments that are NOT the value of an option (`--values v.hwp`): only these can be the output."""
    return [i for i in _docs(args) if not (i > 0 and args[i - 1].startswith('--'))]


def _same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _writes(cmd, args):
    return {'build': True, 'md': True, 'html': True, 'form': 'fill' in args, 'pagefit': 'fix' in args,
            'secure': '--info' not in args}.get(cmd, False)


def hwp_dispatch(argv):
    """argv to run: a command of `hd hwp` when it does the same job on an .hwp, else argv."""
    cmd, args = argv[0], argv[1:]
    if cmd in HWP_SUB and any(args[i].lower().endswith('.hwp') for i in _docs(args)) and '--md' not in args:   # text --md: HWP_VIA
        if cmd == 'preview':                   # ponytail: the .hwp renderer has no --no-png (it always writes PNG)
            args = [a for a in args if a != '--no-png'] + ['--backend', 'preview']
        return ['hwp', HWP_SUB[cmd]] + args
    return argv


def hwp_via(argv):
    """True when argv is a HWP_VIA command that names an .hwp file the command cannot take as it is."""
    args = argv[1:]
    return (argv[0] in HWP_VIA and any(args[i].lower().endswith('.hwp') for i in _docs(args))
            and not (argv[0] == 'secure' and {'--info', '--password-env', '--distribute'} & set(args)))   # secure: Hangul works on the file itself (post.py says "must be .hwpx")


def hwp_route(argv, run):
    """Run argv (a command for .hwpx) on .hwp files; run(argv) -> exit code. The output .hwp is a new file written by
    fromhwpx, not the input patched (use `hd edit` to keep every other byte)."""
    import shutil
    from hwpx_docs.core import tmpdir
    from hwpx_docs.core import protect
    from hwpx_docs.hwp5 import build, fmt, owpml
    cmd, args = argv[0], list(argv[1:])
    docs, out = _docs(args), None
    pos = _positional_docs(args)
    if _writes(cmd, args) and (cmd in ('build', 'md', 'html') or len(docs) > 1) and pos and args[pos[-1]].lower().endswith('.hwp'):
        if any(_same_file(args[i], args[pos[-1]]) for i in docs if i != pos[-1]):        # the output is never the input
            print(f'NOT WRITTEN: the output {args[pos[-1]]} is also an input; give a new file name (the received file stays as it is)')
            return 2
        out = args[pos[-1]]
    tmp = tmpdir.mkdtemp('hd_hwp_')
    try:
        return _route(cmd, args, docs, pos, out, tmp, run, build, fmt, owpml, protect)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)              # also when a step failed (no folder is left behind)


def _route(cmd, args, docs, pos, out, tmp, run, build, fmt, owpml, protect):
    import contextlib
    import io
    tmp_out = os.path.join(tmp, 'out.hwpx')
    if out:
        args[pos[-1]] = tmp_out
        docs = [i for i in docs if i != pos[-1]]
    try:
        for k, i in enumerate(docs):
            if args[i].lower().endswith('.hwp'):
                src, args[i] = args[i], os.path.join(tmp, f'in{k}.hwpx')
                owpml.convert(src, args[i])
    except owpml.Unsupported as e:             # no mapping yet: its own message and exit code (as `hd hwp tohwpx`)
        print(e)
        return 5
    except (fmt.Hwp5Error, protect.ProtectedDocument) as e:
        print(e)
        return 3 if isinstance(e, fmt.Hwp5Error) else protect.EXIT_CODE
    except Exception as e:                     # a bug, not a missing mapping: say so, nothing is written
        print(f'ERROR tohwpx {type(e).__name__}: {e}')
        return 3
    buf = io.StringIO()                        # the temporary HWPX is not the result, so its name is never printed
    try:
        with contextlib.redirect_stdout(buf):
            code = run([cmd] + args)
    except SystemExit as e:
        code = e.code
    text = buf.getvalue()
    if out:
        text = text.replace(tmp_out, out if not code else '(temporary file)')
    sys.stdout.write(text)
    if code or not out:
        return code or 0
    try:                                       # UNSUPPORTED <what> <where> and its exit code come from `hd hwp fromhwpx`
        return build.main(['fromhwpx', tmp_out, out])
    except Exception as e:                     # a bug, not a missing mapping: say so, nothing is written
        print(f'ERROR fromhwpx {type(e).__name__}: {e}')
        return 3


def _selftest():
    assert hwp_dispatch(['slots', 'a.hwp']) == ['hwp', 'slots', 'a.hwp']
    assert hwp_dispatch(['slots', 'a.hwpx']) == ['slots', 'a.hwpx']
    assert hwp_via(['build', 's.json', 'x.HWP']) and not hwp_via(['build', 's.json', 'x.hwpx'])
    assert hwp_via(['pagefit', 'check', 'a.hwp']) and not hwp_via(['secure', '--info', 'a.hwp'])
    assert not hwp_via(['hwp', 'text', 'a.hwp']) and not hwp_via(['read', 'a.hwpx'])
    assert hwp_dispatch(['text', 'a.hwp', '--md'])[0] == 'text' and hwp_via(['text', 'a.hwp', '--md'])
    assert _positional_docs(['fill', 'a.hwp', '--values', 'v.hwp', 'out.hwp']) == [1, 4]       # an option value is never the output
    import contextlib
    import hashlib
    import io
    import tempfile
    from hwpx_docs.core import tmpdir
    from hwpx_docs.hwp5 import tests
    d = tmpdir.mkdtemp('hd_self_')                           # removed at exit (a self-test run leaves nothing in %TEMP%)
    src = tests.build(os.path.join(d, 'in.hwp'))
    before = hashlib.sha256(open(src, 'rb').read()).hexdigest()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):                    # input == output is refused and the received file stays
        assert hwp_route(['form', 'fill', src, src], lambda a: 0) == 2
    assert 'NOT WRITTEN' in buf.getvalue() and hashlib.sha256(open(src, 'rb').read()).hexdigest() == before
    from hwpx_docs.hwp5 import owpml
    made, real, real_convert = [], tmpdir.mkdtemp, owpml.convert
    tmpdir.mkdtemp = lambda *a, **k: made.append(real(*a, **k)) or made[-1]
    owpml.convert = lambda s, t: open(t, 'wb').write(b'x')      # the minimal test file has no .hwp -> HWPX mapping
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):                # a failing run leaves no temporary folder and names no temporary file
            code = hwp_route(['form', 'fill', src, os.path.join(d, 'out.hwp')],
                             lambda a: print('FORM FILLED 1 of 1 ->', a[-1]) or 1)
    finally:
        tmpdir.mkdtemp, owpml.convert = real, real_convert
    assert code == 1 and made and not any(os.path.exists(m) for m in made), (code, made)
    assert 'hd_hwp_' not in buf.getvalue() and '(temporary file)' in buf.getvalue(), buf.getvalue()
    from hwpx_docs.core import addons
    addons.selftest()
    print('SELFTEST hd PASS')


def main(argv):
    for stream in (sys.stdout, sys.stderr):    # pipes on Korean Windows default to cp949: ✓, ☑ and others fail
        stream.reconfigure(encoding='utf-8')
    if argv == ['--version']:
        from hwpx_docs import __version__
        print(f'hwpx-docs-codex v{__version__}')
        return 0
    from hwpx_docs.core import registry
    found = registry.commands()
    usage = __doc__ + ''.join(f'\n  {c} {u.split("  ")[0]:<36} {m:<15} {u.split("  ", 1)[-1]}'
                              for c, (m, _, u) in found.items())
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(usage)
        return 0
    if argv[0] == 'selftest':
        from hwpx_docs import selftest
        _selftest()
        return selftest.main(argv[1:])
    argv = hwp_dispatch(argv)
    both = set(found) & set(COMMANDS)
    if both:
        raise ValueError(f'commands in hd.py and in a package: {sorted(both)}')
    if not (found.get(argv[0]) or COMMANDS.get(argv[0])):
        print('unknown command:', argv[0])
        print(usage)
        return 2
    from hwpx_docs.core import addons
    argv, finish, rc = addons.attach(argv)        # add-on output filter / write resolver; nothing installed: no change
    try:
        if rc:
            return rc
        return hwp_route(argv, lambda a: run(a, found)) if hwp_via(argv) else run(argv, found)
    except BaseException as e:                    # with a filter attached, the error report goes through it (it may hold a real value)
        if not finish:
            raise
        return addons.report(e)
    finally:
        if finish:
            finish()


def run(argv, found):
    mod, pre, _ = found.get(argv[0]) or (COMMANDS.get(argv[0]), [], '')
    sys.argv = [f'hd {argv[0]}'] + pre + argv[1:]
    from hwpx_docs.core import protect
    try:
        runpy.run_module(f'hwpx_docs.{mod}', run_name='__main__', alter_sys=True)
    except protect.ProtectedDocument as e:       # protected file: say so, no traceback
        print(e)
        return protect.EXIT_CODE
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
