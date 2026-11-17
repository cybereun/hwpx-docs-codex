"""The two entry points that the core calls, and what they do around a command.

  output_filter(argv)   learns the documents of the call, masks every text the command shows, and (finish) masks the text files the command wrote
                        (`hd text -o`, `hd read doc spec.json`, md / html / svg / txt exports); a final document (.hwp, .hwpx) keeps real values
  write_resolver(argv)  tags in arguments and in text input files -> real values (with the Korean particle fixed to the real word);
                        a drawing command (render, preview) gets a covered copy of the document, so a picture never shows a real value

Temporary copies live in the user's own folder (<vault home>\\tmp), are removed when the command ends, and the removal is checked.
"""
import json
import os
import re
import shutil
import tempfile
import time
from collections import Counter

from . import docscan, vault as vaultmod
from .engine import TAGP, TEXT_INPUT, PrivacyError, Session, has_tag, is_render


# ---- output ---------------------------------------------------------------------------------------------------------
def _mask_obj(s, obj):
    if isinstance(obj, str):
        return s.mask(obj)
    if isinstance(obj, list):
        return [_mask_obj(s, x) for x in obj]
    if isinstance(obj, dict):
        return {k: _mask_obj(s, v) for k, v in obj.items()}
    return obj


def _mask_file(s, path):
    """Mask a text file that the command wrote, in place. True when it changed, False when it did not, None when it is not text."""
    raw = open(path, 'rb').read()
    try:
        txt = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return None
    if b'\x00' in raw[:4096]:
        return None                                                        # a binary
    new = txt
    if path.lower().endswith('.json'):
        try:
            new = json.dumps(_mask_obj(s, json.loads(txt)), ensure_ascii=False, indent=1)
        except ValueError:
            new = s.mask(txt)
    else:
        new = s.mask(txt)
    if new != txt:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        return True
    return False


MAX_LISTED = 3000     # files of one folder that are looked at


def _stat(p):
    try:
        st = os.stat(p)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _arg_paths(argv):
    """(files, parents): the file arguments and the files inside a folder argument (two levels), and the folders that hold an output
    (an argument that is a path and does not exist yet is an output: its folder is looked at too, a command can write more than it is told)."""
    files, parents = [], set()
    for a in argv[1:]:
        if a.startswith('--') and '=' in a:
            a = a.split('=', 1)[1]
        if not a or a.startswith('-'):
            continue
        try:
            if os.path.isfile(a):
                files.append(os.path.abspath(a))
            elif os.path.isdir(a):
                base = os.path.abspath(a).count(os.sep)
                for root, dirs, fs in os.walk(a):
                    if os.path.abspath(root).count(os.sep) - base >= 2:
                        dirs.clear()                                           # two levels
                    files += [os.path.abspath(os.path.join(root, f)) for f in fs[:MAX_LISTED]]
            elif os.sep in a or '/' in a or PATHLIKE.search(a):
                d = os.path.dirname(os.path.abspath(a))
                if os.path.isdir(d):
                    parents.add(d)
        except OSError:
            continue
    return list(dict.fromkeys(files)), parents


def _listing(dirs):
    out = {}
    for d in dirs:
        try:
            for f in os.listdir(d)[:MAX_LISTED]:
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    out[os.path.abspath(p)] = _stat(p)
        except OSError:
            pass
    return out


def _now(argv):
    """(files, parents, stat of every file that the call may write)."""
    files, parents = _arg_paths(argv)
    now = _listing(parents | {os.path.dirname(p) for p in files})
    now.update({p: _stat(p) for p in files})
    return files, parents, now


def snapshot(argv):
    """(path, size, mtime in ns) of the files the call may write, taken before the command runs. A written file is one that is new or differs:
    no clock is compared, so a slow clock (FAT32: 2 s, a network drive) cannot hide a write."""
    return _now(argv)[2]


def _written(argv, before):
    """(named, near): the files that the call wrote: the file arguments (and the files inside a folder argument) that are new or changed, and
    the other new or changed files next to them (a command can write more than it is told: `hd read` also writes the pictures of the document).
    A neighbour may belong to another process that works in the same folder, so a neighbour is never rewritten, only closed to the Read gate."""
    files, parents, now = _now(argv)
    changed = {p for p, st in now.items() if st is not None and before.get(p) != st}
    named = [p for p in files if p in changed]
    dirs = {os.path.dirname(p) for p in named} | parents
    near = [p for p in changed if p not in named and os.path.dirname(p) in dirs]
    return named, near


PATHMAP = {}          # temporary copy -> the file the user named: a message that names the copy shows the original


class Filter:
    """What the core wraps around stdout / stderr: it holds text until the command ends, then masks it."""
    def __init__(self, session, before, lock):
        self.s = session
        self.before = before
        self.lock = lock

    def __call__(self, text):
        text = self.s.mask(text)
        for tmp, orig in PATHMAP.items():                                    # "preview of <vault>\tmp\r-x\doc.hwpx" -> the file the user named
            for form in (tmp, tmp.replace('\\', '/')):
                text = text.replace(form, orig)
        return text

    def finish(self):
        with self.lock:
            self._finalize()

    def _finalize(self):
        s = self.s
        cmd = s.argv[0] if s.argv else ''
        masked_files, tainted, failed = [], [], []
        try:
            named, near = _written(s.argv, self.before)
        except Exception:                                                    # the list of written files could not be made: nothing is trusted
            named, near = [], []
            failed.append('list')
        closed = (s.counts or s.docs) and not is_render(s.argv)

        def close(p):
            if closed:
                s.vault.taint(p, cmd)                                        # closed to the Read gate (a render comes from a covered copy: open)
                tainted.append(vaultmod.src_id(p))
        for p in named:
            try:
                if docscan.sniff(p):
                    continue                                                 # a final document (HWP, HWPX by content) keeps its real values; the Read gate refuses it
                done = _mask_file(s, p)                                      # any readable text, whatever its extension (.py, .yaml, .hwpx that is not a document)
                if done:
                    masked_files.append(vaultmod.src_id(p))
                elif done is None:
                    close(p)                                                 # a picture or another binary made from a real document (also when no text
            except Exception:                                                # was found: a picture can be a seal or a photo)
                failed.append(vaultmod.src_id(p))                            # a file that vanished or cannot be masked: closed, never left open
                try:
                    close(p)
                except Exception:
                    pass
        for p in near:                                                       # what appeared next to it (the pictures and text parts of `hd read`)
            try:                                                             # a neighbour is closed, not rewritten (another process may use it)
                if not docscan.sniff(p):
                    close(p)
            except Exception:
                failed.append(vaultmod.src_id(p))
        vaultmod.audit('command', cmd=cmd, docs=[vaultmod.src_id(d) for d in s.docs], masked=dict(s.counts),
                       masked_files=masked_files, tainted=tainted, failed=failed, mode=s.mode, sec=round(time.time() - s.t0, 2))
        s.vault.save()


def output_filter(argv):
    """Entry point 1: the filter of one call."""
    lock = vaultmod.lock()
    try:
        cleanup_stale()
        PATHMAP.clear()
        s = Session(argv)
        for d in s.docs:
            s.learn(d)
        return Filter(s, snapshot(argv), lock)
    except BaseException:
        lock.close()
        raise


# ---- unmask on write ------------------------------------------------------------------------------------------------
def _jong(value):
    """The final consonant class of the last readable character: 0 none, 8 ㄹ, other = a final consonant; None = unknown (Latin letter)."""
    digits = {'0': 4, '1': 8, '2': 0, '3': 16, '4': 0, '5': 0, '6': 1, '7': 8, '8': 8, '9': 0}        # 영 일 이 삼 사 오 육 칠 팔 구
    for c in reversed(value.strip()):
        if '가' <= c <= '힣':
            return (ord(c) - 0xAC00) % 28
        if c in digits:
            return digits[c]
        if c in ')]}」』>”’"\' .,':
            continue
        return None
    return None


def fix_particle(value, p):
    """The particle `p` that followed a tag, in the form that fits the real word (은/는, 이/가, 을/를, 와/과, (으)로, (이)다, (이)나, 아/야)."""
    j = _jong(value)
    if j is None:
        return p
    has, rieul = j != 0, j == 8
    pair = {'은': ('은', '는'), '는': ('은', '는'), '이': ('이', '가'), '가': ('이', '가'), '을': ('을', '를'), '를': ('을', '를'),
            '와': ('과', '와'), '과': ('과', '와'), '이다': ('이다', '다'), '다': ('이다', '다'), '이나': ('이나', '나'), '나': ('이나', '나'),
            '아': ('아', '야'), '야': ('아', '야')}
    if p in ('으로', '로'):
        return '으로' if has and not rieul else '로'
    a, b = pair[p]
    return a if has else b


def resolve_text(text, vault, used=None):
    def sub(m):
        tid = m.group(1).strip()
        e = vault.get(tid)
        if e is None:
            raise PrivacyError(f'unknown tag ⟪{tid}⟫: it is not in the vault (the document was not read with hd on this PC, '
                               'or `pv.py forget` removed it)')
        if used is not None:
            used[e['kind']] += 1
        return e['value'] + (fix_particle(e['value'], m.group(2)) if m.group(2) else '')
    return TAGP.sub(sub, text)


def _resolve_json(obj, vault, used):
    if isinstance(obj, str):
        return resolve_text(obj, vault, used)
    if isinstance(obj, list):
        return [_resolve_json(x, vault, used) for x in obj]
    if isinstance(obj, dict):
        return {_resolve_json(k, vault, used): _resolve_json(v, vault, used) for k, v in obj.items()}
    return obj


PATHLIKE = re.compile(r'\.(?:hwpx?|json|txt|md|html?|png|svg|csv|xml|pdf|bmp|jpe?g|gif|log|tsv|rdf)$', re.I)


def tag_in_path(a):
    """True when an argument holds a tag and can be a path: it has a separator or a file extension, or it is a bare / glued tag (`⟪성명1⟫`,
    `x⟪성명1⟫`, `⟪성명1⟫.yaml`). Text with a space and a value `KEY=TEXT` (the `=` comes before the tag) are not paths."""
    m = TAGP.search(a)
    if not m:
        return False
    if '=' in a[:m.start()]:
        return False
    if os.sep in a or '/' in a or '\\' in a or PATHLIKE.search(TAGP.sub('', a)):
        return True
    return not re.search(r'[\s=]', a)


def tmp_base():
    p = os.path.join(vaultmod.home(), 'tmp')
    os.makedirs(p, exist_ok=True)
    return p


def _alive(pid):
    """True when a process with this id runs (a failed check counts as running: nothing is removed by mistake)."""
    try:
        if os.name == 'nt':
            import ctypes
            k = ctypes.windll.kernel32
            k.OpenProcess.restype = ctypes.c_void_p
            h = k.OpenProcess(0x1000, False, pid)                    # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return k.GetLastError() != 87                        # 87 = invalid parameter = no such process; access denied = it runs
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
            k.CloseHandle(ctypes.c_void_p(h))
            return (not ok) or code.value == 259                     # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def cleanup_stale(max_age=3600):
    """Temporary folders of a call that died: removed at once when the process that made them is gone (its id is in the folder),
    else after an hour (a folder with no id file)."""
    base = tmp_base()
    for name in os.listdir(base):
        p = os.path.join(base, name)
        if not os.path.isdir(p):
            continue
        try:
            pid = int(open(os.path.join(p, '.pid')).read().strip())
        except (OSError, ValueError):
            pid = None
        if pid is not None:
            if not _alive(pid):
                shutil.rmtree(p, ignore_errors=True)
        elif time.time() - os.path.getmtime(p) > max_age:
            shutil.rmtree(p, ignore_errors=True)


def write_resolver(argv):
    """Entry point 2. (argv2, cleanup). Unknown tag = PrivacyError."""
    noop = (argv, lambda: None)
    cmd = argv[0] if argv else ''
    files = [a for a in argv if os.path.isfile(a)]
    render = is_render(argv) and any(docscan.sniff(a) for a in files)
    texts = [a for a in files if a.lower().endswith(TEXT_INPUT) and os.path.getsize(a) < 8_000_000]
    if not render and not any(has_tag(a) for a in argv) and not texts:
        return noop
    for a in argv[1:]:                                                       # a tag in the name of a file or folder would put a real value into a name
        if tag_in_path(a):
            raise PrivacyError('a tag cannot be part of a file or folder name (the real value would become visible in the name); '
                               'give the file a plain name')
    sess = Session(argv)
    vault = sess.vault
    used, tmp, out, originals = Counter(), None, [], []
    cleanup_stale()

    def tempdir():
        nonlocal tmp
        if tmp is None:
            tmp = tempfile.mkdtemp(prefix='r-', dir=tmp_base())
            with open(os.path.join(tmp, '.pid'), 'w') as f:
                f.write(str(os.getpid()))                                    # a later call removes this folder when this process is gone
        return tmp
    for i, a in enumerate(argv):
        if i == 0:
            out.append(a)
        elif render and docscan.sniff(a) == 'hwp':
            raise PrivacyError('a picture of an HWP would show real values. Convert first: `hd hwp tohwpx in.hwp in.hwpx`, then draw in.hwpx '
                               '(drawing makes a covered copy of an HWPX)')
        elif render and docscan.sniff(a) == 'hwpx':
            from . import redact
            dst = os.path.join(tempdir(), os.path.basename(a))
            originals.append(a)
            redact.redact(a, dst, sess)                            # every value, hidden place and picture covered
            out.append(dst)
            PATHMAP[dst] = os.path.abspath(a)
            used['covered copy'] += 1
        elif has_tag(a):
            out.append(resolve_text(a, vault, used))
        elif os.path.isfile(a) and a in texts:
            txt = None
            try:
                txt = open(a, 'rb').read().decode('utf-8-sig')
            except UnicodeDecodeError:
                pass
            if txt is None:
                out.append(a)
                continue
            before = used.total()
            if a.lower().endswith('.json'):
                try:
                    txt = json.dumps(_resolve_json(json.loads(txt), vault, used), ensure_ascii=False, indent=1)
                except json.JSONDecodeError:
                    txt = resolve_text(txt, vault, used)
            else:
                txt = resolve_text(txt, vault, used)
            if used.total() == before:
                out.append(a)
                continue
            new = os.path.join(tempdir(), f'{i}-{os.path.basename(a)}')
            with open(new, 'w', encoding='utf-8') as f:
                f.write(txt)
            out.append(new)
            PATHMAP[new] = os.path.abspath(a)
        else:
            out.append(a)
    pos = [i for i, a in enumerate(out) if i > 0 and not a.startswith('-') and out[i - 1] != '--dpi']
    if render and originals and len(pos) - (1 if cmd == 'render' else 0) == 1:       # no output folder was given: the command would use the
        out.append(os.path.dirname(os.path.abspath(originals[0])))                  # folder of the covered copy; use the folder of the original
    vault.save()
    if used:
        vaultmod.audit('resolve', cmd=cmd, tags=dict(used))

    def cleanup():
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
            vaultmod.audit('temp-removed' if not os.path.exists(tmp) else 'temp-left', cmd=cmd)
            if os.path.exists(tmp):
                shutil.rmtree(tmp, ignore_errors=True)
    return out, cleanup
