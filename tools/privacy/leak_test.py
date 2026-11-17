"""Leak test: fake people are filled into forms on this PC (fill.py); every read command, error message and hook path is run with the
privacy add-on active; no planted value may appear in anything that would reach the model.

  python tools/privacy/leak_test.py <t9 dir> [--limit N] [--templates DIR] [--workers 4] [--mode standard|strict]

Reads <t9>/canaries.json. Prints `PRIVACY LEAK <leaks>/<n> canaries` (n = planted values; a value that shows in any output is a leak),
`PRIVACY HOOKS <passed>/<total>`, and writes <t9>/leak-report.txt (kind, command; never a value into stdout).
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
HD = os.path.join(ROOT, 'lib', 'hd.py')
ADDON = os.path.join(ROOT, 'addons', 'hwpx-docs-privacy')
HOOK = os.path.join(ADDON, 'scripts', 'hook.py')
PV = os.path.join(ADDON, 'scripts', 'pv.py')


SENS_TERMS = sorted({w for subs in json.load(open(os.path.join(ADDON, 'packs', 'kr-sensitive-terms', 'pack.json'), encoding='utf-8'))['terms'].values()
                     for ws in subs.values() for w in ws if len(w) >= 2}, key=len, reverse=True)
F_KINDS = ('employer', 'school')                              # group F: masked in strict mode only
PROMPT_LABEL = {'rrn': '주민등록번호', 'phone': '휴대전화', 'tel': '전화번호', 'email': '이메일', 'card': '카드번호', 'brn': '사업자등록번호',
                'driving': '운전면허번호', 'passport': '여권번호', 'bank': '계좌번호'}


def env_for(home, mode='standard', templates=None):
    os.makedirs(home, exist_ok=True)
    cfg = os.path.join(home, 'addons.json')
    want = {'addons': [ADDON.replace(chr(92), '/')], 'enforce': True}
    try:
        same = json.load(open(cfg, encoding='utf-8')) == want
    except (OSError, ValueError):
        same = False
    if not same:                                                   # documents of one worker share this file: never truncate it while another reads
        json.dump(want, open(cfg, 'w'))
    e = dict(os.environ, HWPX_PRIVACY_HOME=home, HWPX_PRIVACY_MODE=mode, PYTHONUTF8='1', HWPX_DOCS_ADDONS_CONFIG=cfg)
    e.pop('HWPX_DOCS_ADDONS', None)
    if templates:
        e['HWPX_PRIVACY_TEMPLATES'] = templates
    else:
        e.pop('HWPX_PRIVACY_TEMPLATES', None)
    return e


def plain(env):
    """The same environment with the layer off (a settings file that does not exist): `hd` as it is without the add-on."""
    return dict(env, HWPX_DOCS_ADDONS_CONFIG=os.path.join(env['HWPX_PRIVACY_HOME'], 'none.json'))


def run(args, env, cwd=None, timeout=180):
    """`hd <args>`; the vault commands (`vault scan ...`) are the add-on's own script, not an hd command."""
    cmd = [sys.executable, '-X', 'utf8', PV] + args[1:] if args and args[0] == 'vault' else [sys.executable, '-X', 'utf8', HD] + args
    r = subprocess.run(cmd, capture_output=True, env=env, cwd=cwd, timeout=timeout)
    return (r.stdout + b'\n' + r.stderr).decode('utf-8', 'replace')


def hook(event, payload, env):
    r = subprocess.run([sys.executable, '-X', 'utf8', HOOK, event], input=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                       capture_output=True, env=env, timeout=120)
    return r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def canary_in(value, kind, text, squashed, digits):
    """True when the planted value is readable in `text`: as written, without spaces, or (numbers) by its digits."""
    v = value.strip()
    if v in text or ''.join(v.split()) in squashed:
        return True
    d = re.sub(r'\D', '', v)
    if len(d) >= 7 and (d in digits or d[:-2] in digits and len(d) >= 9):      # also a value cut by 1-2 digits at the end of a line
        return True
    s = ''.join(v.split())
    return len(s) >= 6 and not d and s[:-2] in squashed                         # a text value cut by 1-2 characters (a listing that shows 60)


def prepare(text):
    return text, ''.join(text.split()), re.sub(r'(?<=\d)[\s.\-](?=\d)', '', text).replace(' ', '')


def commands(rel, path):
    """The read commands for one document: (label, args)."""
    hwpx = path.lower().endswith('.hwpx')
    base = os.path.basename(path)
    out = [('text', ['text', path]), ('slots', ['slots', path]), ('guard-self', ['guard', path, path]),
           ('edit-unmatched', ['edit', path, path + '.x', '--set', 'zzz-no-such-label=1']),
           ('edit-unknown-tag', ['edit', path, path + '.x', '--set', 'p1=⟪성명9999⟫', '--allow-missing']),
           ('text-missing', ['text', path + '.missing']), ('slots-json', ['slots', path, '--json', path + '.slots.json'])]
    if hwpx:
        out += [('form-list', ['form', 'list', path]), ('read-json', ['read', path, path + '.spec.json']),
                ('diff-dump', ['diff', 'dump', path]), ('check', ['check', path, path]), ('secure-info', ['secure', '--info', path]),
                ('textstyle-dump', ['textstyle', 'dump', path]), ('text-md', ['text', path, '--md']), ('text-out', ['text', path, '-o', path + '.txt']),
                ('preview', ['preview', path, os.path.dirname(path) + '/pv-' + base]), ('pv-scan', ['vault', 'scan', path])]          # `vault ...` = the add-on's pv.py (run() routes it)
    else:
        out += [('hwp-info', ['hwp', 'info', path]), ('hwp-text', ['hwp', 'text', path]), ('hwp-tospec', ['hwp', 'tospec', path, path + '.spec.json']),
                ('hwp-tohwpx', ['hwp', 'tohwpx', path, path + '.x.hwpx']), ('text-out', ['text', path, '-o', path + '.txt']),
                ('preview', ['preview', path, os.path.dirname(path) + '/pv-' + base]), ('pv-scan', ['vault', 'scan', path])]
    return out


def one(task):
    rel, info, t9, home, mode, templates = task
    info = dict(info, canaries=[c for c in info['canaries'] if mode == 'strict' or c[0] not in F_KINDS])
    path = os.path.join(t9, rel)
    env = env_for(home, mode, templates)
    leaks, outputs, hooks, counted = [], {}, [], {}
    work = path + '.work'
    for label, args in commands(rel, path):
        try:
            outputs[label] = run(args, env)
        except subprocess.TimeoutExpired:
            outputs[label] = 'TIMEOUT'
    # files that the commands wrote, as a model would read them next. A final document is refused by the Read gate; a text file that the
    # command wrote (spec, text export, slots json) was masked in place: its content must be clean and the Read gate must let it through
    derived = [p for p in (path + s for s in ('.slots.json', '.spec.json', '.txt', '.x.hwpx')) if os.path.exists(p)]
    for p in derived + [path]:
        is_doc = p.lower().endswith(('.hwp', '.hwpx'))
        out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': p}}, env)
        hooks.append((f'read {"document" if is_doc else "derived text"}', ('deny' in out) == is_doc))
        if not is_doc:
            outputs['file-' + os.path.basename(p)] = open(p, encoding='utf-8', errors='replace').read()
        outputs['hook-read-' + os.path.basename(p)] = out
    if os.path.exists(path + '.txt'):                                  # the text export, as a masked copy that a model may read
        outputs['mask-copy'] = run(['vault', 'mask-copy', path + '.txt', path + '.masked.txt'], env)
        if os.path.exists(path + '.masked.txt'):
            outputs['masked-text'] = open(path + '.masked.txt', encoding='utf-8', errors='replace').read()
    if path.lower().endswith('.hwpx'):                                 # the covered copy of the document: every part, also the hidden ones
        outputs['mask-copy-hwpx'] = run(['vault', 'mask-copy', path, path + '.masked.hwpx'], env)
        if os.path.exists(path + '.masked.hwpx'):
            import zipfile
            with zipfile.ZipFile(path + '.masked.hwpx') as z:
                outputs['masked-hwpx'] = '\n'.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist() if n.lower().endswith(('.xml', '.hpf', '.txt', '.rdf')))
    # the gate: what must be refused (the inside of a document) and what must pass (a user's own work)
    d = os.path.dirname(path)
    py_inline = 'python -c "import zipfile;print(zipfile.ZipFile(r\'' + path + '\').read(\'Contents/section0.xml\'))"'
    refused = [('Bash', f'unzip -p "{path}" Contents/section0.xml', 'bash-unzip'), ('Bash', f'cat "{path}"', 'bash-cat'), ('Bash', f'strings "{path}"', 'bash-strings'),
               ('Bash', py_inline, 'bash-python'), ('Bash', f'grep -a . "{path}"', 'bash-grep'),
               ('PowerShell', f'Get-Content -Raw "{path}"', 'ps-get-content'), ('PowerShell', f'Expand-Archive "{path}" -DestinationPath x', 'ps-expand'),
               ('PowerShell', f'[IO.Compression.ZipFile]::OpenRead("{path}")', 'ps-zip'), ('PowerShell', f'Select-String -Path "{path}" -Pattern x', 'ps-select'),
               ('Grep', {'pattern': '.', 'path': path}, 'grep-tool-doc'), ('Grep', {'pattern': '.', 'path': d}, 'grep-tool-dir'),
               ('Read', {'file_path': path}, 'read-doc')]
    passed = [('Bash', f'python {HD} text "{path}"', 'bash-hd'), ('PowerShell', f'python {HD} slots "{path}"', 'ps-hd'),
              ('Bash', f'ls "{d}"', 'ok-ls'), ('Bash', 'git status', 'ok-git'), ('Bash', f'cp "{path}" "{path}.bak"', 'ok-cp'),
              ('Bash', f'wc -l "{path}"', 'ok-wc'), ('Bash', 'python -c "print(1+1)"', 'ok-python'), ('Bash', 'echo hello', 'ok-echo'),
              ('PowerShell', f'Get-ChildItem "{d}"', 'ok-gci'), ('PowerShell', f'Copy-Item "{path}" "{path}.bak"', 'ok-copy'),
              ('PowerShell', f'Test-Path "{path}"', 'ok-test'), ('Read', {'file_path': os.path.join(ROOT, 'README.md')}, 'ok-read-readme')]
    for want_deny, group in ((True, refused), (False, passed)):
        for tool, arg, label in group:
            ti = arg if isinstance(arg, dict) else {'command': arg}
            out, _ = hook('pre-tool', {'tool_name': tool, 'tool_input': ti, 'cwd': d}, env)
            denied = 'deny' in out
            hooks.append((label, denied == want_deny))
            if not want_deny:
                counted['benign'] = counted.get('benign', 0) + 1
                counted['false-denials'] = counted.get('false-denials', 0) + denied
            outputs['hook-' + label] = out
    out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': os.path.join(home, 'vault.bin')}}, env)
    hooks.append(('read-vault', 'deny' in out))
    # N-7a: a spreadsheet export that holds the planted numbers, in the layouts that an office program writes (cp949 CSV of even and of odd
    # length, UTF-8 with a mark, UTF-16): the Read gate refuses every one
    nums = [v for k, v in info['canaries'] if k in ('rrn', 'card')][:1]
    if nums:
        cdir = os.path.join(home, 'csv')
        os.makedirs(cdir, exist_ok=True)
        base_csv = '성명,번호\n홍길동,' + nums[0] + '\n'
        layouts = {'cp949-even': base_csv.encode('cp949'), 'cp949-odd': (base_csv + 'a').encode('cp949'),
                   'utf8-bom': base_csv.encode('utf-8-sig'), 'utf16': base_csv.encode('utf-16')}
        layouts['cp949-even'] += b'' if len(layouts['cp949-even']) % 2 == 0 else b' '
        layouts['cp949-odd'] += b'' if len(layouts['cp949-odd']) % 2 == 1 else b' '
        # a list with an address column (Excel export): the address rule takes a whole row; a different number of rows, even and odd length
        for head in ('성명,주민번호,주소,연락처', '번호,성명,주민등록번호,주소,연락처,비고'):
            for nrows in (1, 2):
                body = '\r\n'.join(['홍길동%d,%s,서울특별시 강남구 테헤란로 %d길 5,010-1234-56%02d' % (i, nums[0], i + 10, i) for i in range(nrows)])
                for par in (0, 1):
                    for tag, enc, sep in (('cp949', 'cp949', ','), ('utf8', 'utf-8', ','), ('tab', 'cp949', '\t')):
                        raw = (head + '\r\n' + body + '\r\n').replace(',', sep).encode(enc) if sep != ',' else (head + '\r\n' + body + '\r\n').encode(enc)
                        raw += b'a' if len(raw) % 2 != par else b''
                        layouts[f'list{len(head)}-{nrows}rows-{tag}-{"odd" if par else "even"}'] = raw
        for name, raw in layouts.items():
            fp = os.path.join(cdir, name + '.csv')
            open(fp, 'wb').write(raw)
            out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': fp}}, env)
            hooks.append(('N-7a csv ' + name, 'deny' in out))
            out, _ = hook('pre-tool', {'tool_name': 'Bash', 'tool_input': {'command': f'cat "{fp}"'}, 'cwd': cdir}, env)
            hooks.append(('N-7a csv bash ' + name, 'deny' in out))
    for cmd in ('HWPX_DOCS_ADDONS= python x.py', 'set HWPX_PRIVACY_MODE=off', f'python {PV} disable', f'python "{PV}" purge --yes'):
        out, _ = hook('pre-tool', {'tool_name': 'Bash', 'tool_input': {'command': cmd}}, env)
        hooks.append(('bash-bypass', 'deny' in out))
    # prompts: only the certain ones are refused (valid RRN / FRN, card, labelled account); the word #허용 lets one through
    for kind, value in info['canaries']:
        label = PROMPT_LABEL.get(kind, kind)                      # a user names the field in words ("계좌번호 ..."), not by an English id
        out, _ = hook('prompt', {'prompt': f'신청서에 {label} {value} 를 넣어 주세요', 'hook_event_name': 'UserPromptSubmit'}, env)
        outputs['hook-prompt'] = outputs.get('hook-prompt', '') + out
        if kind in ('rrn', 'card', 'bank'):
            hooks.append(('prompt-' + kind, 'block' in out))
            out2, _ = hook('prompt', {'prompt': f'신청서에 {label} {value} 를 넣어 주세요 #허용', 'hook_event_name': 'UserPromptSubmit'}, env)
            hooks.append(('prompt-allow-word', 'block' not in out2))
        else:
            counted['benign'] = counted.get('benign', 0) + 1
            counted['false-denials'] = counted.get('false-denials', 0) + ('block' in out)
    # drawing: a picture is made from a covered copy; an HWP is refused until it is converted
    if path.lower().endswith('.hwpx'):
        env_plain = plain(env)
        da, db = path + '.pvA', path + '.pvB'
        import shutil
        for d_ in (da, db):                                   # a folder of an earlier run must not take part
            shutil.rmtree(d_, ignore_errors=True)
        run(['vault', 'mask-copy', path, path + '.cov.hwpx'], env)           # first a warm-up: the vault learns the document, so A and B see the same state
        run(['preview', path, da], env)
        run(['vault', 'mask-copy', path, path + '.cov.hwpx'], env)
        run(['preview', path + '.cov.hwpx', db], env_plain)

        def pngs(dd):                                        # the SVG text of the pages (PNG bytes differ between runs: antialiasing, workers)
            if not os.path.isdir(dd):
                return []
            svg = sorted(open(os.path.join(dd, f), 'rb').read() for f in os.listdir(dd) if f.lower().endswith('.svg'))
            return svg or sorted(open(os.path.join(dd, f), 'rb').read() for f in os.listdir(dd) if f.lower().endswith('.png'))
        a_, b_ = pngs(da), pngs(db)
        hooks.append(('preview made from a covered copy', bool(a_) and a_ == b_))
    else:
        out = run(['preview', path, path + '.pvA'], env)
        hooks.append(('preview of an hwp refused', 'hwp tohwpx' in out and not os.path.isdir(path + '.pvA')))
        outputs['preview-hwp'] = out
    # the fixed settings file only (no environment variable): a direct `python lib/hd.py` call is filtered; enforce with a missing add-on stops
    cfg = os.path.join(home, 'settings-%d.json' % abs(hash(rel)))          # one file per document: two documents of a worker may run at the same time
    json.dump({'addons': [ADDON.replace(chr(92), '/')], 'enforce': True}, open(cfg, 'w'))
    env_cfg = dict(env, HWPX_DOCS_ADDONS_CONFIG=cfg)
    outputs['text-config-only'] = run(['text', path], env_cfg)
    hooks.append(('settings file loads the layer', 'PRIVACY ADDON NOT LOADED' not in outputs['text-config-only']))
    json.dump({'addons': [os.path.join(home, 'gone')], 'enforce': True}, open(cfg, 'w'))
    outputs['not-loaded'] = run(['text', path], env_cfg) + run(['slots', path], env_cfg)
    hooks.append(('enforce stops when not loaded', 'PRIVACY ADDON NOT LOADED' in outputs['not-loaded'] and len(outputs['not-loaded']) < 900))
    tmpd = os.path.join(home, 'tmp')                               # the temporary folder of the write resolver is empty again
    hooks.append(('temp folder emptied', not os.path.isdir(tmpd) or not os.listdir(tmpd)))
    for label, text in outputs.items():
        t, sq, dg = prepare(text)
        for kind, value in info['canaries']:
            if canary_in(value, kind, t, sq, dg):
                leaks.append((rel, kind, label))
        if mode == 'strict' and not label.startswith('hook-prompt'):          # strict: the dictionary terms of the planted sentence are masked
            for term in SENS_TERMS:
                if term in info['sens'] and term in t:
                    leaks.append((rel, 'sens', label))
                    break
    for f in derived + [path + '.masked.txt', path + '.masked.hwpx', path + '.cov.hwpx', path + '.bak']:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    return rel, info, leaks, hooks, counted


def hook_rc(event, raw, env):
    r = subprocess.run([sys.executable, '-X', 'utf8', HOOK, event], input=raw.encode('utf-8') if isinstance(raw, str) else raw, capture_output=True, env=env, timeout=120)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def signal6_phase(t9, base, docs, mode, templates):
    """The cases that a review found (N-6b, c, i, j, k, l, p, q, s, t, u, x, y, af and the wording of a refusal). Returns [(name, ok)]."""
    import shutil
    import time
    res = []
    work = os.path.join(base, 's6')
    os.makedirs(work, exist_ok=True)
    home = os.path.join(work, 'home')
    env = env_for(home, mode, templates)
    names = [(rel, info) for rel, info in docs.items()]
    rel_hwp = next((r for r, _ in names if r.endswith('.hwp')), None)
    rel_x = next((r for r, _ in names if r.endswith('.hwpx')), None)

    def canaries(rel):
        return [v for k, v in docs[rel]['canaries'] if k in ('name', 'rrn', 'phone', 'tel', 'email', 'bank', 'card', 'plate') and (mode == 'strict' or k not in F_KINDS)]

    def clean(rel, text):
        t, sq, dg = prepare(text)
        return not any(canary_in(v, 'x', t, sq, dg) for v in canaries(rel))
    for rel in (rel_hwp, rel_x):
        if not rel:
            continue
        src = os.path.join(t9, rel)
        ext = os.path.splitext(src)[1]
        doc = os.path.join(work, 'doc' + ext)
        shutil.copyfile(src, doc)
        shown = run(['text', doc], env)
        m = re.search(r'⟪성명\d+[^⟫]*⟫', shown)
        tag = m.group(0) if m else '⟪성명1⟫'
        tag_ok = bool(m)
        res.append((f'{ext}: a name tag is shown', tag_ok))
        # N-6b: the error report of a command goes through the filter
        bad = os.path.join(work, 'bad.json')
        json.dump({'body': [{'zzz': tag}]}, open(bad, 'w', encoding='utf-8'), ensure_ascii=False)
        out1 = run(['build', bad, os.path.join(work, 'o.hwpx')], env)
        out2 = run(['edit', doc, doc + '.x', '--set', f'{tag}=1'], env)
        res.append((f'{ext}: N-6b an exception report is masked', clean(rel, out1) and clean(rel, out2)))
        # N-6c: the mode cannot be switched off by a variable
        out = run(['text', doc], dict(env, HWPX_PRIVACY_MODE='off'))
        res.append((f'{ext}: N-6c HWPX_PRIVACY_MODE=off does not switch the layer off', clean(rel, out) and '⟪' in out))
        # N-6i: enforce with nothing to load, or an add-on without a filter, stops
        bare = os.path.join(work, 'bare-addon')
        os.makedirs(bare, exist_ok=True)
        json.dump({'name': 'hwpx-docs-privacy', 'path': '.'}, open(os.path.join(bare, 'hwpx-addon.json'), 'w'))
        stops = []
        for conf in ({'addons': [], 'enforce': True}, {'addons': None, 'enforce': True}, {'addons': [bare.replace(chr(92), '/')], 'enforce': True}):
            cfg = os.path.join(work, 'c.json')
            json.dump(conf, open(cfg, 'w'))
            out = run(['text', doc], dict(env, HWPX_DOCS_ADDONS_CONFIG=cfg))
            stops.append('PRIVACY ADDON NOT LOADED' in out and clean(rel, out))
        res.append((f'{ext}: N-6i enforce stops when there is no filter', all(stops)))
        # N-6j: an output file is judged by its content; N-6k: a tag cannot be in a file name
        py = os.path.join(work, 'o.py')
        hx = os.path.join(work, 'o.hwpx')
        run(['text', doc, '-o', py], env)
        run(['text', doc, '-o', hx], env)
        txt = lambda f: open(f, encoding='utf-8', errors='replace').read() if os.path.exists(f) else ''
        res.append((f'{ext}: N-6j text written to .py / .hwpx is masked', clean(rel, txt(py)) and clean(rel, txt(hx))))
        out = run(['text', doc, '-o', os.path.join(work, tag + '.txt')], env)
        res.append((f'{ext}: N-6k a tag in a file name is refused', 'cannot be part of' in out and not any(not clean(rel, f) for f in os.listdir(work))))
        # N-6u: a renamed copy is still learned, N-6s: the audit log holds no file name
        ren = os.path.join(work, 'copy.bin')
        shutil.copyfile(src, ren)
        out = run(['text', ren], env)
        res.append((f'{ext}: N-6u a renamed copy: the values are not shown', clean(rel, out)))
        audit = os.path.join(home, 'audit.jsonl')
        a = open(audit, encoding='utf-8').read() if os.path.exists(audit) else ''
        res.append((f'{ext}: N-6s the audit log holds no file name', 'doc' + ext not in a and '.hwp' not in a and clean(rel, a)))
        # N-6y: drawing without an output folder writes next to the original
        if ext == '.hwpx':
            for f in os.listdir(work):
                if f.lower().endswith('.png'):
                    os.remove(os.path.join(work, f))
            run(['preview', doc], env)
            res.append(('N-6y preview without an output folder writes next to the original', any(f.lower().endswith('.png') for f in os.listdir(work))))
            out = run(['slots', doc], env)
            res.append(('N-6af no RuntimeWarning on stderr', 'RuntimeWarning' not in out))
    # N-6l: the pictures that `hd read` writes are closed to the Read gate
    pic = os.path.join(ROOT, 'tests', 'fixtures', 'picture_doc.hwpx')
    if os.path.exists(pic):
        rd = os.path.join(work, 'rd')
        os.makedirs(rd, exist_ok=True)
        run(['read', pic, os.path.join(rd, 'spec.json')], env)
        pngs = [os.path.join(rd, f) for f in os.listdir(rd) if f.lower().endswith(('.png', '.jpg', '.bmp'))]
        okp = bool(pngs)
        for f in pngs:
            out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': f}}, env)
            okp &= 'deny' in out
        res.append(('N-6l pictures written by hd read are refused by the Read gate', okp))
    # N-6x: a person-label cell with a name that forms print as a sample
    tx = os.path.join(work, 'x.txt')
    open(tx, 'w', encoding='utf-8').write('성명 홍길동\n신청인 성명 최도현\n담당자 김하준 주무관에게 문의하십시오.\n')
    run(['vault', 'mask-copy', tx, tx + '.m'], env)
    m = txt(tx + '.m')
    res.append(('N-6x / N-6a: 홍길동 and the name after a compound label are masked', '홍길동' not in m and '최도현' not in m and '김하준' not in m))
    # N-6q: an old temporary folder is removed by the next call
    old = os.path.join(home, 'tmp', 'r-old')
    os.makedirs(old, exist_ok=True)
    t = time.time() - 7200
    os.utime(old, (t, t))
    run(['text', os.path.join(work, 'doc' + os.path.splitext(rel_x or rel_hwp)[1])], env)
    res.append(('N-6q an old temporary folder is removed', not os.path.exists(old)))
    # N-6p: the hook never lets a call through by failing; a large file is asked about; python or py -3
    rc, _, _ = hook_rc('pre-tool', '', env)
    res.append(('N-6p empty hook input ends with exit code 2', rc == 2))
    rc, _, _ = hook_rc('pre-tool', '{not json', env)
    res.append(('N-6p broken hook input ends with exit code 2', rc == 2))
    big = os.path.join(work, 'big.txt')
    open(big, 'w', encoding='utf-8').write('plain words without personal data\n' * 20000)
    out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': big}}, env)
    res.append(('N-6p a file above the scan limit is asked about, not scanned whole', '"ask"' in out))
    h = open(os.path.join(ADDON, 'hooks', 'hooks.json'), encoding='utf-8').read()
    res.append(('N-6p hooks fall back to py -3; N-6n Monitor is gated like Bash', 'py -3' in h and '|Monitor|' in h))
    if rel_x:
        out, _ = hook('pre-tool', {'tool_name': 'Monitor', 'tool_input': {'command': f'unzip -p "{os.path.join(work, "doc.hwpx")}" Contents/section0.xml'}}, env)
        res.append(('N-6n Monitor with a dump command is refused', 'deny' in out and 'work around' in out))
    # N-6t: a settings file that cannot be written is told to the user and nothing is let through
    blocker = os.path.join(work, 'blocker')
    open(blocker, 'w').write('x')
    bad_cfg = os.path.join(blocker, 'sub', 'addons.json')
    env_bad = dict(env, HWPX_DOCS_ADDONS_CONFIG=bad_cfg)
    rc, out, _ = hook_rc('session-start', json.dumps({'session_id': 's'}), env_bad)
    res.append(('N-6t SessionStart tells the user when the settings file cannot be written', 'systemMessage' in out))
    out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': os.path.join(ROOT, 'README.md')}}, env_bad)
    res.append(('N-6t nothing is let through until the settings file exists', 'deny' in out and 'not switched on' in out))
    return res


UNIT7 = r'''
import json, os, sys, time
sys.path.insert(0, os.path.join(sys.argv[1], 'scripts'))
from hwpxpriv.engine import Session
from hwpxpriv import ioflow, vault as V, gates
work, doc = sys.argv[2], sys.argv[3]
res = {}
# N-7b: a file is written when it is new or differs from the snapshot; no clock is compared (an old mtime does not hide a write)
out = os.path.join(work, 'u-out.txt')
old = os.path.join(work, 'u-old.txt')
open(old, 'w').write('x')
argv = ['text', doc, '-o', out, old]
before = ioflow.snapshot(argv)
open(out, 'w', encoding='utf-8').write('new')
os.utime(out, (315532800, 315532800))                       # 1980: the clock of a FAT32 or a network drive says "long ago"
open(os.path.join(work, 'u-image1.txt'), 'w').write('text part next to the output')
open(old, 'w').write('changed size')
os.utime(old, (315532800, 315532800))
named, near = ioflow._written(argv, before)
res['N-7b a new file with an old time is found; an overwritten one too'] = os.path.abspath(out) in named and os.path.abspath(old) in named
res['N-7c a text file next to the output is found'] = os.path.abspath(os.path.join(work, 'u-image1.txt')) in near
# N-7c / N-7t: a neighbour is closed (never rewritten); a file that cannot be handled is closed
s = Session(argv)
s.learn(doc)
f = ioflow.Filter(s, before)
real = ioflow._mask_file
def boom(s_, p):
    if p == os.path.abspath(old):
        raise OSError('gone')
    return real(s_, p)
ioflow._mask_file = boom
f.finish()
ioflow._mask_file = real
v = V.Vault()
res['N-7c a text neighbour is tainted, not rewritten'] = v.tainted(os.path.join(work, 'u-image1.txt')) and open(os.path.join(work, 'u-image1.txt')).read() == 'text part next to the output'
res['N-7t an error on one file does not stop the others; the file is closed'] = v.tainted(old)
# N-7g: the time budget of a Bash check: over it the gate asks
g = gates.Gate()
gates.BASH_SECONDS = -1
r = g.pre_bash('cat "%s" "%s"' % (old, out), work)
res['N-7g a Bash check over its time budget asks'] = bool(r) and r[0] == 'ask'
print(json.dumps(res))
'''


def signal7_phase(t9, base, docs, mode, templates):
    """The cases of review signal 7 (N-7a ... w). Returns [(name, ok)]."""
    import shutil
    import time
    res = []
    work = os.path.join(base, 's7')
    os.makedirs(work, exist_ok=True)
    home = os.path.join(work, 'home')
    env = env_for(home, mode, templates)
    names = list(docs)
    rel_hwp = next((r for r in names if r.endswith('.hwp')), None)
    rel_x = next((r for r in names if r.endswith('.hwpx')), None)

    def canaries(rel):
        return [v for k, v in docs[rel]['canaries'] if k in ('name', 'rrn', 'phone', 'tel', 'email', 'bank', 'card', 'plate') and (mode == 'strict' or k not in F_KINDS)]

    def clean(rel, text):
        t, sq, dg = prepare(text)
        return not any(canary_in(v, 'x', t, sq, dg) for v in canaries(rel))
    txt = lambda f: open(f, encoding='utf-8', errors='replace').read() if os.path.exists(f) else ''
    if rel_x:
        src = os.path.join(t9, rel_x)
        doc = os.path.join(work, 'doc.hwpx')
        shutil.copyfile(src, doc)
        shown = run(['text', doc], env)
        m = re.search(r'⟪성명\d+[^⟫]*⟫', shown)
        tag = m.group(0) if m else '⟪성명1⟫'
        # N-7f: a tag in any path argument is refused; N-7v: a value that holds tags is not
        for label, args, made in (('-o <tag>', ['text', doc, '-o', tag], tag), ('<tag>.yaml', ['text', doc, '-o', tag + '.yaml'], tag + '.yaml'),
                                  ('x<tag>', ['text', doc, '-o', 'x' + tag], 'x' + tag), ('diff dump doc <tag>', ['diff', 'dump', doc, tag], tag)):
            out = run(args, env, cwd=work)
            res.append((f'N-7f a tag in a path is refused: {label}', 'cannot be part of' in out and not os.path.exists(os.path.join(work, made))))
        out = run(['edit', doc, doc + '.x', '--set', f'비고={tag}/{tag}', '--allow-missing'], env, cwd=work)
        res.append(('N-7v a value with tags is not refused as a file name', 'cannot be part of' not in out))
        # N-7d: the title of a document is learned (a name in the title)
        import zipfile
        t_doc = os.path.join(work, 'titled.hwpx')
        who = '곽단솔'
        with zipfile.ZipFile(doc) as zi, zipfile.ZipFile(t_doc, 'w', zipfile.ZIP_DEFLATED) as zo:
            for it in zi.infolist():
                data = zi.read(it.filename)
                if it.filename == 'Contents/content.hpf':
                    s = data.decode('utf-8')
                    title = f'<opf:title>{who} 민원 신청서</opf:title>'
                    s = re.sub(r'<opf:title\s*/>|<opf:title>[^<]*</opf:title>', title, s, count=1) if re.search(r'<opf:title', s) else s.replace('<opf:metadata>', '<opf:metadata>' + title, 1)
                    data = s.encode('utf-8')
                zo.writestr(it, data)
        dd = os.path.join(work, 'dd')
        shutil.rmtree(dd, ignore_errors=True)
        run(['diff', 'dump', t_doc, dd], env)
        hpf = os.path.join(dd, 'Contents', 'content.hpf')
        found = [os.path.join(r, f) for r, _, fs in os.walk(dd) for f in fs if f == 'content.hpf']
        res.append(('N-7d a name in the document title is masked in a dump', bool(found) and all(who not in txt(p) for p in found)))
        # N-7i: mask-copy of an HWP or of a binary says no
        if rel_hwp:
            hw = os.path.join(work, 'doc.hwp')
            shutil.copyfile(os.path.join(t9, rel_hwp), hw)
            out = run(['vault', 'mask-copy', hw, hw + '.m.txt'], env)
            res.append(('N-7i mask-copy of an HWP is refused and writes nothing', 'refused' in out and not os.path.exists(hw + '.m.txt')))
        bn = os.path.join(work, 'pic.png')
        open(bn, 'wb').write(b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 20)
        out = run(['vault', 'mask-copy', bn, bn + '.m.txt'], env)
        res.append(('N-7i mask-copy of a binary is refused and writes nothing', 'refused' in out and not os.path.exists(bn + '.m.txt')))
        # N-7o: the message of a drawing command does not name the covered copy or the vault folder
        out = run(['preview', doc], env, cwd=work)
        res.append(('N-7o a preview message names neither the covered copy nor the vault folder', os.path.join(home, 'tmp').lower() not in out.lower() and '\\r-' not in out))
    # N-7k: an ID number in line 1 and a 3-byte character cut by the 256 KB limit
    nums = [v for rel in names[:5] for k, v in docs[rel]['canaries'] if k == 'rrn'][:1]
    if nums:
        big = os.path.join(work, 'cut.txt')
        open(big, 'w', encoding='utf-8').write(nums[0] + '\n' + '가' * 100000)
        out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': big}}, env)
        res.append(('N-7k an ID number in line 1 of a file with a cut character is denied', 'deny' in out))
    # N-7e / N-7s: the settings file keeps its other keys; the user's `disable` is honoured
    cfg = os.path.join(work, 'cfg', 'addons.json')
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    json.dump({'addons': [], 'enforce': True, 'mode': 'strict'}, open(cfg, 'w'))
    env_c = dict(env, HWPX_DOCS_ADDONS_CONFIG=cfg)
    hook_rc('session-start', json.dumps({'session_id': 's'}), env_c)
    c = json.load(open(cfg, encoding='utf-8'))
    res.append(('N-7e SessionStart keeps the mode key', c.get('mode') == 'strict' and c.get('addons')))
    json.dump({'addons': [], 'enforce': False, 'disabled_by_user': True}, open(cfg, 'w'))
    hook_rc('session-start', json.dumps({'session_id': 's'}), env_c)
    c = json.load(open(cfg, encoding='utf-8'))
    out, _ = hook('pre-tool', {'tool_name': 'Read', 'tool_input': {'file_path': os.path.join(ROOT, 'README.md')}}, env_c)
    res.append(('N-7s after `pv.py disable` SessionStart does not switch the layer on and no call is refused', not c.get('addons') and 'deny' not in out))
    # N-7h: the temporary folder of a process that is gone is removed at once; one of a running process stays
    tmp = os.path.join(home, 'tmp')
    dead, live = os.path.join(tmp, 'r-dead'), os.path.join(tmp, 'r-live')
    for d_, pid in ((dead, 2147000000), (live, os.getpid())):
        os.makedirs(d_, exist_ok=True)
        open(os.path.join(d_, '.pid'), 'w').write(str(pid))
        open(os.path.join(d_, 'x.json'), 'w').write('{}')
    run(['text', os.path.join(work, 'doc.hwpx')] if rel_x else ['selftest'], env)
    res.append(('N-7h a temporary folder of a dead process is removed, one of a live process stays', not os.path.exists(dead) and os.path.exists(live)))
    shutil.rmtree(live, ignore_errors=True)
    # N-7g: the hook command ends with exit 2 when no interpreter is found
    h = open(os.path.join(ADDON, 'hooks', 'hooks.json'), encoding='utf-8').read()
    res.append(('N-7g hooks end with exit 2 after the py -3 fallback', h.count('|| exit 2') == 3))
    # N-7b, c, g, t: in-process checks of the written-file list, the neighbours and the time budget of the Bash gate
    if rel_x:
        r = subprocess.run([sys.executable, '-X', 'utf8', '-c', UNIT7, ADDON, work, os.path.join(work, 'doc.hwpx')], capture_output=True, env=env, timeout=120)
        try:
            for k, v in json.loads(r.stdout.decode('utf-8', 'replace').strip().splitlines()[-1]).items():
                res.append((k, bool(v)))
        except (ValueError, IndexError):
            res.append(('N-7b/c/g/t in-process checks ran: ' + r.stderr.decode('utf-8', 'replace')[-200:], False))
    return [(n, bool(ok)) for n, ok in res]


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    t9 = argv[0]
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else 10 ** 9
    workers = int(argv[argv.index('--workers') + 1]) if '--workers' in argv else 4
    mode = argv[argv.index('--mode') + 1] if '--mode' in argv else 'standard'
    templates = argv[argv.index('--templates') + 1] if '--templates' in argv else None
    docs = json.load(open(os.path.join(t9, 'canaries.json'), encoding='utf-8'))
    only = argv[argv.index('--only') + 1] if '--only' in argv else ''
    every = int(argv[argv.index('--every') + 1]) if '--every' in argv else 1
    items = [kv for kv in docs.items() if only in kv[0]][::every][:limit]
    import time
    base = os.path.join(t9, 'vaults-' + time.strftime('%H%M%S'))          # a fresh vault per run: earlier runs must not help
    tasks = [(rel, info, t9, os.path.join(base, f'w{i % workers}'), mode, templates) for i, (rel, info) in enumerate(items)]
    leaks, hooks, n, counted = [], [], 0, {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for rel, info, lk, hk, cn in ex.map(one, tasks):
            leaks += lk
            hooks += hk
            n += len([c for c in info['canaries'] if mode == 'strict' or c[0] not in F_KINDS])
            for k, v in cn.items():
                counted[k] = counted.get(k, 0) + v
    uniq = {(r, k) for r, k, _ in leaks}
    with open(os.path.join(t9, 'leak-report.txt'), 'w', encoding='utf-8') as f:
        for r, k, label in sorted(leaks):
            f.write(f'{r}\t{k}\t{label}\n')
    kinds = {}
    for _, k, _ in leaks:
        kinds[k] = kinds.get(k, 0) + 1
    print(f'PRIVACY LEAK {len(leaks)}/{n} canaries (documents {len(items)}, mode {mode}, templates {"yes" if templates else "no"}); by kind {kinds}')
    bad = [h for h in hooks if not h[1]]
    print(f'PRIVACY HOOKS {len(hooks) - len(bad)}/{len(hooks)} checks' + (f'; failed {sorted({h[0] for h in bad})}' if bad else ''))
    print(f'PRIVACY GATE false-denials {counted.get("false-denials", 0)}/{counted.get("benign", 0)} benign calls')
    s6 = signal6_phase(t9, base, docs, mode, templates)
    for name, ok in s6:
        if not ok:
            print('  SIGNAL6 FAIL', name)
    print(f'PRIVACY SIGNAL6 {sum(ok for _, ok in s6)}/{len(s6)} cases of the review')
    s7 = signal7_phase(t9, base, docs, mode, templates)
    for name, ok in s7:
        if not ok:
            print('  SIGNAL7 FAIL', name)
    print(f'PRIVACY SIGNAL7 {sum(ok for _, ok in s7)}/{len(s7)} cases of the review')
    tl, tn = typo_phase(t9, os.path.join(base, 'typo'), docs, mode, templates)
    print(f'PRIVACY LEAK typo {tl}/{tn} damaged canaries (full-width digits, dots, spaces, zero-width, O for 0)')
    return 1 if leaks or bad or tl or counted.get('false-denials', 0) or any(not ok for _, ok in s6 + s7) else 0


DAMAGE = [lambda v: v.translate(str.maketrans('0123456789-', '０１２３４５６７８９－')), lambda v: v.replace('-', '.'), lambda v: v.replace('-', ' - '),
          lambda v: v[:3] + '​' + v[3:], lambda v: v.replace('0', 'O').replace('1', 'l', 1)]
TYPO_FIELDS = (('rrn', '주민등록번호'), ('phone', '휴대전화'), ('card', '카드번호'), ('brn', '사업자등록번호'), ('driving', '운전면허번호'))


def typo_phase(t9, base, docs, mode, templates, n_docs=40):
    """Numbers written wrongly (full-width digits, dots, spaces, zero-width, O for 0) into a form: none may reach the output."""
    sys.path.insert(0, os.path.join(ROOT, 'lib'))
    sys.path.insert(0, HERE)
    import gen
    os.makedirs(base, exist_ok=True)
    leaks = total = 0
    env = env_for(os.path.join(base, 'home'), mode, templates)
    env_plain = plain(env)
    for i, rel in enumerate(list(docs)[:n_docs]):
        src = os.path.join(t9, rel)
        if src.lower().endswith('.hwpx'):
            from hwpx_docs.edit.edit import Doc
        else:
            from hwpx_docs.hwp5.edit import Doc
        empty = [r['key'] for r in Doc(src).slots() if not r['text'].strip() and r['kind'] in ('body', 'cell')]
        if not empty:
            continue
        p = gen.person(30000 + i)
        bad, parts = [], []
        for k, (kind, label) in enumerate(TYPO_FIELDS):
            v = DAMAGE[(i + k) % len(DAMAGE)](p[kind])
            if v != p[kind]:
                bad.append((kind, p[kind], v))
                parts.append(f'{label} {v}')
        dst = os.path.join(base, f'doc{i}{os.path.splitext(src)[1]}')
        vp = dst + '.values.json'
        json.dump({empty[0]: ' / '.join(parts)}, open(vp, 'w', encoding='utf-8'), ensure_ascii=False)
        subprocess.run([sys.executable, '-X', 'utf8', HD, 'edit', src, dst, '--values', vp, '--allow-missing'], capture_output=True, env=env_plain)
        if not os.path.exists(dst):
            continue
        out = run(['text', dst], env)
        t, sq, dg = prepare(out)
        for kind, real, v in bad:
            total += 1
            d = re.sub(r'\D', '', real)
            if v in out or real in t or d in dg:
                leaks += 1
    return leaks, total


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
