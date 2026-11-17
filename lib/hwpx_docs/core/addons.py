"""Generic hook points for add-on plugins. With nothing installed this module does nothing.

An add-on is a folder with `hwpx-addon.json`:
  {"path": "scripts",                                   folder added to sys.path (relative to the add-on folder)
   "output_filter": "package.module:function",          function(argv) -> f or None; f(text) -> text; f.finish() is optional
   "write_resolver": "package.module:function"}         function(argv) -> (argv2, cleanup)
The first two entry points get the argument list of the `hd` call (without `hd`).

Which add-ons are on: the user's fixed file `%LOCALAPPDATA%\\hwpx-docs\\addons.json` (`~/.config/hwpx-docs/addons.json` elsewhere; the
environment variable HWPX_DOCS_ADDONS_CONFIG names another file) with {"addons": [folder, ...], "enforce": true|false}, plus the folders in the
environment variable HWPX_DOCS_ADDONS (os.pathsep list; a test override that can only add). With "enforce": true an add-on that cannot be
loaded stops the call: `PRIVACY ADDON NOT LOADED`, nothing is run, no document text is shown (fail closed).

  output filter   every text that the command shows. The standard output and the standard error of the whole call (also of child
                  processes and the error report) are collected in files while the command runs, passed through `f`, then shown.
  write resolver  runs before the command: it may replace arguments (for example a placeholder by a value, or a path by a prepared
                  copy). `cleanup()` runs when the command ends. An exception stops the call with exit code 2 and its message.

The core knows nothing about what an add-on does with these two points.
"""
import os
import sys

ENV = 'HWPX_DOCS_ADDONS'
ENV_CONFIG = 'HWPX_DOCS_ADDONS_CONFIG'


def _entry(ref):
    import importlib
    mod, _, fn = ref.partition(':')
    return getattr(importlib.import_module(mod), fn)


def config_path():
    p = os.environ.get(ENV_CONFIG)
    if p:
        return p
    base = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(base or os.path.expanduser('~'), 'hwpx-docs', 'addons.json')


def settings():
    """(folders, enforce, config path). The fixed file first; the environment variable only adds folders.
    A file that cannot be read, a path that is not a file (a folder), a list that is not a list: enforce, with a folder that cannot load."""
    folders, enforce, cfg = [], False, config_path()
    if os.path.exists(cfg):
        try:
            import json
            c = json.load(open(cfg, encoding='utf-8'))
            folders, enforce = list(c['addons']), bool(c.get('enforce'))
            if enforce and not folders:
                folders = ['<empty list of add-ons>']                          # enforce with nothing to load is not "off"
        except (OSError, ValueError, AttributeError, TypeError, KeyError):
            folders, enforce = ['<unreadable settings file>'], True          # a broken file must not switch the layer off
    folders += [p for p in os.environ.get(ENV, '').split(os.pathsep) if p and p not in folders]
    return folders, enforce, cfg


def _addons(folders):
    """([manifest dicts], [folders that cannot be loaded])."""
    out, bad = [], []
    for folder in folders:
        manifest = os.path.join(folder, 'hwpx-addon.json')
        try:
            import json
            conf = json.load(open(manifest, encoding='utf-8'))
            path = os.path.join(folder, conf.get('path', '.'))
            if path not in sys.path:
                sys.path.insert(0, path)
            out.append(conf)
        except (OSError, ValueError, AttributeError, TypeError):
            bad.append(folder)
    return out, bad


def _not_loaded(cfg, what):
    print(f'PRIVACY ADDON NOT LOADED: {what}. Nothing was run and no document text was shown. '
          f'Repair or reinstall the add-on, or delete {cfg} to switch the layer off.')


def attach(argv):
    """(argv2, finish, exit code or None). Call finish() after the command (also after an error). No add-on: (argv, None, None)."""
    folders, enforce, cfg = settings()
    if not folders and not enforce:
        return argv, None, None
    confs, bad = _addons(folders)
    if enforce and bad:
        _not_loaded(cfg, 'cannot read ' + ', '.join(bad))
        return argv, None, 2
    if enforce and not all(c.get('output_filter') and c.get('write_resolver') for c in confs):
        _not_loaded(cfg, 'an add-on has no output filter or no write resolver')
        return argv, None, 2
    if not any(c.get('output_filter') or c.get('write_resolver') for c in confs):
        return argv, None, None
    try:
        filters = [_entry(c['output_filter'])(argv) for c in confs if c.get('output_filter')]
        if enforce and (not filters or any(f is None for f in filters)):
            raise ValueError('the output filter is off')
        filters = [f for f in filters if f]
    except Exception as e:
        if enforce:
            _not_loaded(cfg, f'the output filter failed to start ({type(e).__name__})')
            return argv, None, 2
        raise
    saved, files = None, None
    if filters:
        for s in (sys.stdout, sys.stderr):
            s.flush()
        import tempfile
        files = [tempfile.TemporaryFile(), tempfile.TemporaryFile()]
        saved = [os.dup(1), os.dup(2)]
        os.dup2(files[0].fileno(), 1)
        os.dup2(files[1].fileno(), 2)
    cleanups = []

    def finish():
        if saved:
            for s in (sys.stdout, sys.stderr):
                s.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            for fd in saved:
                os.close(fd)
            buffered = []
            try:
                for f in files:
                    f.seek(0)
                    text = f.read().decode('utf-8', 'replace')
                    for flt in filters:
                        text = flt(text)
                    buffered.append(text)
                for flt in filters:
                    if hasattr(flt, 'finish'):
                        flt.finish()
                for stream, text in zip((sys.stdout, sys.stderr), buffered):
                    stream.write(text)
                    stream.flush()
            finally:
                for f in files:
                    f.close()
                for c in cleanups:
                    c()
        else:
            for c in cleanups:
                c()
    try:
        for c in confs:
            if c.get('write_resolver'):
                argv, cleanup = _entry(c['write_resolver'])(argv)
                cleanups.append(cleanup)
    except Exception as e:                      # the message is the add-on's (it must be safe to show)
        print(f'add-on: {e}')
        return argv, finish, 2
    return argv, finish, None


def report(e):
    """The exit code of an exception (or SystemExit) after printing its report; call it while the filter is attached, so the report is masked."""
    import traceback
    if isinstance(e, SystemExit):
        if e.code is None or isinstance(e.code, int):
            return e.code or 0
        print(e.code, file=sys.stderr)
        return 1
    if isinstance(e, KeyboardInterrupt):
        return 130
    traceback.print_exception(e)
    return 1


def selftest():
    import json
    import subprocess
    from . import tmpdir
    d = tmpdir.mkdtemp('addon_selftest_')
    os.makedirs(os.path.join(d, 'x'))
    open(os.path.join(d, 'hwpx-addon.json'), 'w').write(json.dumps({'path': 'x', 'output_filter': 'selftest_addon:filt',
                                                                  'write_resolver': 'selftest_addon:res'}))
    open(os.path.join(d, 'x', 'selftest_addon.py'), 'w').write(
        'def filt(argv):\n    return lambda t: t.replace("unknown", "UNKN")\n'
        'def res(argv):\n    return ([a.replace("@@", "unknowncmd") for a in argv], lambda: None)\n')
    lib = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    code = '; '.join(['import os, subprocess, sys', f'sys.path.insert(0, {lib!r})', 'from hwpx_docs.core import addons',
                      'argv, finish, rc = addons.attach(["@@"])', 'print("unknown", argv[0], rc)',
                      'subprocess.run([sys.executable, "-c", "print(\'unknown child\')"])',
                      'os.write(2, b"unknown err")', 'finish and finish()'])
    nocfg = os.path.join(d, 'no-such-settings.json')
    env = dict(os.environ, **{ENV: d, ENV_CONFIG: nocfg}, PYTHONUTF8='1')
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    out = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
    assert 'UNKN UNKNcmd' in out and 'UNKN child' in out and 'UNKN err' in out and 'unknown' not in out, out   # resolver, filter, child, stderr
    env.pop(ENV)
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    assert b'unknown @@' in r.stdout and b'unknown child' in r.stdout, r.stdout                                   # nothing installed: unchanged
    cfg = os.path.join(d, 'settings.json')                                                                        # the fixed file turns it on
    open(cfg, 'w').write(json.dumps({'addons': [d], 'enforce': True}))
    env[ENV_CONFIG] = cfg
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    assert b'UNKN UNKNcmd' in r.stdout, r.stdout
    open(cfg, 'w').write(json.dumps({'addons': [os.path.join(d, 'gone')], 'enforce': True}))                      # enforce + missing: stops
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    assert b'PRIVACY ADDON NOT LOADED' in r.stdout and b'unknown @@ 2' in r.stdout, r.stdout                     # rc 2: the caller does not run the command
    open(cfg, 'w').write('{broken')                                                                               # a broken file does not switch it off
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    assert b'PRIVACY ADDON NOT LOADED' in r.stdout, r.stdout
    for broken in ('{"addons": [], "enforce": true}', '{"addons": null, "enforce": true}', '[1]'):                 # nothing to load, a null, a list
        open(cfg, 'w').write(broken)
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
        assert b'PRIVACY ADDON NOT LOADED' in r.stdout, (broken, r.stdout)
    os.remove(cfg)
    os.makedirs(cfg)                                                                                              # a folder at the settings path
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    assert b'PRIVACY ADDON NOT LOADED' in r.stdout, r.stdout
    env[ENV], env[ENV_CONFIG] = d, nocfg                                                                          # an error report is filtered
    code2 = '; '.join(['import sys', f'sys.path.insert(0, {lib!r})', 'from hwpx_docs.core import addons',
                       'argv, finish, rc = addons.attach(["x"])', 'rc = addons.report(ValueError("unknown value"))',
                       'addons.report(SystemExit("unknown exit"))', 'finish()'])
    r = subprocess.run([sys.executable, '-c', code2], capture_output=True, env=env)
    out = r.stderr.decode('utf-8', 'replace')
    assert 'UNKN value' in out and 'UNKN exit' in out and 'unknown' not in out, out
    print('SELFTEST addons PASS')
