"""The vault: a local store of tag <-> real value. Never leaves this PC; never printed.

Windows: the file is encrypted with DPAPI (user scope, ctypes, standard library). Other systems (or HWPX_PRIVACY_BACKEND=file):
file mode 600, encrypted with a key derived from the passphrase in HWPX_PRIVACY_PASSPHRASE, else with a random key file next to
it (protects against a stray copy of the vault, not against a process of the same user).
Home folder: HWPX_PRIVACY_HOME, else %LOCALAPPDATA%\\hwpx-docs-privacy (Windows) or ~/.local/share/hwpx-docs-privacy.

Files in the home folder: vault.bin (encrypted JSON), audit.jsonl (plain; holds tags, counts and hashes only, never a value),
consents.json (plain; written only by the user on a terminal).
"""
import hashlib
import hmac
import json
import os
import sys
import time

ENTROPY = b'hwpx-docs-privacy/vault/1'


def src_id(name):
    """The id of a file name: audit log and vault keep this, never the name (a file name often holds a person's name)."""
    return hashlib.sha1(os.path.basename(str(name)).lower().encode('utf-8')).hexdigest()[:10]


def home():
    h = os.environ.get('HWPX_PRIVACY_HOME')
    if not h:
        base = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.path.join(os.path.expanduser('~'), '.local', 'share')
        h = os.path.join(base or os.path.expanduser('~'), 'hwpx-docs-privacy')
    os.makedirs(h, exist_ok=True)
    return h


def lock():
    """Lock the vault for a whole read/modify/save operation. Close the handle to release it."""
    handle = open(os.path.join(home(), 'vault.lock'), 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
    except BaseException:
        handle.close()
        raise
    return handle


# ---- encryption -----------------------------------------------------------------------------------------------------
def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    def blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf
    bin_, keep1 = blob(data)
    ent, keep2 = blob(ENTROPY)
    out = Blob()
    crypt = ctypes.windll.crypt32
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    ok = fn(ctypes.byref(bin_), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out))
    if not ok:
        raise OSError('DPAPI failed (the vault belongs to another Windows account?)')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _stream(key, nonce, n):
    out, i = b'', 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, 'big'), hashlib.sha256).digest()
        i += 1
    return out[:n]


def _file_key():
    pw = os.environ.get('HWPX_PRIVACY_PASSPHRASE')
    salt_path = os.path.join(home(), 'salt.bin')
    if not os.path.exists(salt_path):
        with open(salt_path, 'wb') as f:
            f.write(os.urandom(32))
        _chmod(salt_path)
    salt = open(salt_path, 'rb').read()
    if pw:
        return hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, 200000)
    kp = os.path.join(home(), 'key.bin')
    if not os.path.exists(kp):
        with open(kp, 'wb') as f:
            f.write(os.urandom(32))
        _chmod(kp)
    return hashlib.sha256(open(kp, 'rb').read() + salt).digest()


def _chmod(p):
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def backend():
    if os.environ.get('HWPX_PRIVACY_BACKEND') == 'file' or os.name != 'nt':
        return 'file'
    return 'dpapi'


def seal(data):
    if backend() == 'dpapi':
        return b'D1' + _dpapi(data, True)
    key, nonce = _file_key(), os.urandom(16)        # ponytail: HMAC-CTR stream + HMAC tag, no AES in the standard library
    body = bytes(a ^ b for a, b in zip(data, _stream(key, nonce, len(data))))
    tag = hmac.new(key, nonce + body, hashlib.sha256).digest()
    return b'F1' + nonce + tag + body


def unseal(blob):
    if blob[:2] == b'D1':
        return _dpapi(blob[2:], False)
    if blob[:2] != b'F1':
        raise ValueError('not a vault file')
    key, nonce, tag, body = _file_key(), blob[2:18], blob[18:50], blob[50:]
    if not hmac.compare_digest(tag, hmac.new(key, nonce + body, hashlib.sha256).digest()):
        raise ValueError('vault file damaged or wrong passphrase')
    return bytes(a ^ b for a, b in zip(body, _stream(key, nonce, len(body))))


# ---- the vault ------------------------------------------------------------------------------------------------------
def norm(kind_digits, value):
    """Key of a value: numbers compare by their digits (phone with and without hyphens is one value)."""
    v = value.strip()
    if kind_digits:
        d = ''.join(c for c in v if c.isdigit())
        if d:
            return d
    return ''.join(v.split())


class Vault:
    def __init__(self):
        self.path = os.path.join(home(), 'vault.bin')
        self.data = {'counters': {}, 'entries': {}, 'index': {}, 'taint': {}}
        if os.path.exists(self.path):
            self.data = json.loads(unseal(open(self.path, 'rb').read()).decode('utf-8'))
            self.data.setdefault('taint', {})
        self.dirty = False

    def save(self):
        if not self.dirty:
            return
        tmp = self.path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(seal(json.dumps(self.data, ensure_ascii=False).encode('utf-8')))
        _chmod(tmp)
        os.replace(tmp, self.path)
        self.dirty = False

    def add(self, kind, label, value, numeric=False, source=None, attrs=None, status='', extra=None):
        """The tag id of `value` (a new id when the value is new). `label` is the tag prefix (성명, 주민번호 ...)."""
        key = kind + '\0' + hashlib.sha256(norm(numeric, value).encode('utf-8')).hexdigest()
        tid = self.data['index'].get(key)
        if tid is None:
            n = self.data['counters'].get(label, 0) + 1
            self.data['counters'][label] = n
            tid = f'{label}{n}'
            self.data['index'][key] = tid
            self.data['entries'][tid] = {'kind': kind, 'label': label, 'value': value, 'attrs': attrs or [], 'status': status,
                                         'sources': [], 'numeric': numeric, 't': int(time.time()), **(extra or {})}
            self.dirty = True
        e = self.data['entries'][tid]
        if source and source not in e['sources']:
            e['sources'].append(source)
            self.dirty = True
        return tid

    def get(self, tid):
        return self.data['entries'].get(tid)

    def values(self):
        """[(value, tag id)] of every entry, longest first (for exact masking)."""
        out = []
        for tid, e in self.data['entries'].items():
            if e.get('numeric'):
                out.append((e['value'], tid))
            else:
                out.append((e['value'], tid))
        return sorted(out, key=lambda x: -len(x[0]))

    def forget(self, source):
        n = 0
        for tid in list(self.data['entries']):
            e = self.data['entries'][tid]
            if source in e['sources']:
                e['sources'].remove(source)
                self.dirty = True
                if not e['sources']:
                    self._drop(tid)
                    n += 1
        return n

    def _drop(self, tid):
        self.data['entries'].pop(tid, None)
        self.data['index'] = {k: v for k, v in self.data['index'].items() if v != tid}
        self.dirty = True

    def taint(self, path, reason=''):
        """A file that was made from a document with personal data (a render, a dump): the Read gate refuses it."""
        self.data['taint'][os.path.abspath(path).lower()] = {'t': int(time.time()), 'why': reason}
        self.dirty = True

    def tainted(self, path):
        return os.path.abspath(path).lower() in self.data['taint']


def purge():
    h = home()
    n = 0
    for name in ('vault.bin', 'key.bin', 'salt.bin'):
        p = os.path.join(h, name)
        if os.path.exists(p):
            with open(p, 'r+b') as f:                      # overwrite before delete (best effort)
                f.write(b'\0' * os.path.getsize(p))
            os.remove(p)
            n += 1
    return n


# ---- audit and consent ----------------------------------------------------------------------------------------------
def audit(event, **fields):
    rec = {'t': time.strftime('%Y-%m-%dT%H:%M:%S'), 'event': event, **fields}
    with open(os.path.join(home(), 'audit.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def audit_records():
    p = os.path.join(home(), 'audit.jsonl')
    if not os.path.exists(p):
        return []
    return [json.loads(x) for x in open(p, encoding='utf-8') if x.strip()]


def consents():
    p = os.path.join(home(), 'consents.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'tags': {}, 'types': {}}


def add_consent(what, name, fine=False, reason=''):
    """what = 'tags' | 'types'. Only the CLI calls this, and only from a terminal."""
    c = consents()
    c[what][name] = {'t': time.strftime('%Y-%m-%dT%H:%M:%S'), 'fine': fine, 'reason': reason}
    with open(os.path.join(home(), 'consents.json'), 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    audit('consent', what=what, name=name, fine=fine, reason=reason)


def selftest():
    import tempfile
    old = os.environ.get('HWPX_PRIVACY_HOME')
    os.environ['HWPX_PRIVACY_HOME'] = tempfile.mkdtemp(prefix='pvtest')
    try:
        for be in (None, 'file'):
            if be:
                os.environ['HWPX_PRIVACY_BACKEND'] = be
            v = Vault()
            t1 = v.add('rrn', '주민번호', '800101-1234563', True, 'a.hwpx')
            t2 = v.add('rrn', '주민번호', '8001011234563', True, 'b.hwpx')
            assert t1 == t2 == '주민번호1' and v.get(t1)['sources'] == ['a.hwpx', 'b.hwpx']
            v.save()
            raw = open(v.path, 'rb').read()
            assert b'800101' not in raw and '주민번호'.encode() not in raw
            assert Vault().get(t1)['value'] == '800101-1234563'
            v2 = Vault()
            assert v2.forget('a.hwpx') == 0 and v2.forget('b.hwpx') == 1 and not v2.data['entries']
            assert purge() >= 1
    finally:
        os.environ.pop('HWPX_PRIVACY_BACKEND', None)
        if old is None:
            os.environ.pop('HWPX_PRIVACY_HOME')
        else:
            os.environ['HWPX_PRIVACY_HOME'] = old
    print('VAULT SELFTEST PASS')


if __name__ == '__main__':
    selftest()
