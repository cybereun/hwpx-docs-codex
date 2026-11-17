"""Privacy clean-up and scan of HWPX files that Hangul wrote on a PC (fixtures, samples): `hd textstyle scan [--fix] <files>`.

`sanitize` (the `--fix` step) makes a file safe to commit:
  - creator / lastsaveby of `Contents/content.hpf` -> `hwpx-docs`; the preview image is dropped;
  - author slots, whatever name they hold (the Hangul user name can be a real name): the track change authors of the header
    (`hh:trackChangeAuthor name`), the memo author (`hp:stringParam name="Author"` and the same name inside the `MEMO/...`
    command string of the field) -> `hwpx-docs`;
  - the PC user name (from the environment, see `private_patterns`) anywhere in a text part -> `hwpx-docs`;
  - a file path that holds a user folder (`C:\\Users\\<name>\\...`), in a text part or inside a binary part such as the original
    file path in an OLE object (ASCII or UTF-16): only the file name stays; in a binary part the folder text is replaced by
    underscores of the same length, so the sizes inside the file stay right (a name that is only a user name is replaced by
    letters of the same length);
`scan` reports what is still there: author slots that are not `hwpx-docs`, an e-mail address (example.* is fictional), the
patterns of `private_patterns`. Nothing personal is written in this source: the user name and home folder come from the
environment at run time.
"""
import os
import re
import zipfile

AUTHOR = 'hwpx-docs'
GENERIC_ACCOUNTS = {'user', 'users', 'admin', 'administrator', 'owner', 'guest', 'test', 'default', 'public'}
BACKSLASH = chr(92)
TEXT = ('.xml', '.txt', '.hpf', '.rdf', '.html', '.json')
EMAIL = re.compile(rb'[\w.+-]+@(?!example\.(?:com|org|net))[\w-]+\.[\w.]+')
# a Windows path with a user folder: C:\Users\<name>\...\file.ext (the folder names can hold spaces and non-ASCII letters)
USER_PATH = re.compile(r'([A-Za-z]:\\+[Uu]sers\\+)([^\\/:*?"<>|\r\n\x00]+\\+)*([^\\/:*?"<>|\r\n\x00]+)')
SLOT_NAME = re.compile(r'(<hh:trackChangeAuthor\b[^>]*?\bname=")([^"]*)(")')
SLOT_AUTHOR = re.compile(r'(<hp:stringParam name="Author"[^>]*>)([^<]*)(</hp:stringParam>)')


def private_patterns():
    """Strings that must not be in a committed file, in lower case, as bytes (UTF-8 and UTF-16). The Windows user name and the
    home folder come from the environment at run time (USERNAME, USER, USERPROFILE and the names in its path), plus extras
    from the environment variable HWPX_DOCS_PRIVATE (separated by `;`) or the untracked file `.private-patterns` (one per
    line, repo root), plus generic patterns (full-width at sign, user and AppData folders, drive paths)."""
    return _generic() + [x for n in _names() for x in (n.lower().encode('utf-8'), n.lower().encode('utf-16-le'))]


def _generic():
    return ['＠'.encode(), b'users' + BACKSLASH.encode(), b'c:/users', b'd:' + BACKSLASH.encode(), b'd:/', b'appdata']


def _names():
    names = {os.environ.get('USERNAME', ''), os.environ.get('USER', '')}
    home = os.environ.get('USERPROFILE', '') or os.path.expanduser('~')
    names |= {p for p in home.replace(BACKSLASH, '/').split('/') if p and ':' not in p and p.lower() not in ('users', 'home')}
    names |= {x for x in os.environ.get('HWPX_DOCS_PRIVATE', '').split(';') if x}
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.private-patterns')
    if os.path.exists(local):
        names |= {x.strip() for x in open(local, encoding='utf-8') if x.strip()}
    return sorted(n for n in names if len(n) >= 3 or (len(n) == 2 and not n.isascii()))     # a Korean given name has 2 letters


def _fill(n):
    return (AUTHOR.replace('-', '_') * (n // len(AUTHOR) + 1))[:n]


def _text_clean(t):
    """One text part: author slots, user paths, the user name."""
    t = SLOT_NAME.sub(lambda m: m.group(1) + AUTHOR + m.group(3), t)
    authors = {m.group(2) for m in SLOT_AUTHOR.finditer(t) if m.group(2) and m.group(2) != AUTHOR}
    t = SLOT_AUTHOR.sub(lambda m: m.group(1) + AUTHOR + m.group(3), t)
    for a in authors:                                       # the author inside the MEMO command string of the field
        t = t.replace('/' + a + '/', '/' + AUTHOR + '/')
    t = USER_PATH.sub(lambda m: m.group(3), t)
    names = _names()
    if names:                     # only in text between tags: a short account name ("user") is also part of attribute names and values
        rx = re.compile('|'.join(re.escape(n) for n in names), re.I)
        t = re.sub(r'>([^<]+)<', lambda m: '>' + rx.sub(AUTHOR, m.group(1)) + '<', t)
    return t


def _binary_clean(b):
    """A binary part (OLE object, picture): user paths and the user name, same length."""
    def keep_name(m, wide):
        s = m.group(0)
        txt = s.decode('utf-16-le') if wide else s.decode('latin-1')
        mm = USER_PATH.match(txt)
        if not mm:
            return s
        directory = txt[:mm.end() - len(mm.group(3))]
        out = directory[:2] + _fill(len(directory) - 3) + BACKSLASH + mm.group(3) + txt[mm.end():]    # `C:` + filler + `\` + name
        return out.encode('utf-16-le') if wide else out.encode('latin-1')
    b = re.sub(rb'(?:[A-Za-z]\x00:\x00(?:\\\x00)+[Uu]\x00s\x00e\x00r\x00s\x00(?:\\\x00)+)(?:[^\x00-\x1f\\/:*?"<>|]\x00)+(?:(?:\\\x00)+(?:[^\x00-\x1f\\/:*?"<>|]\x00)+)*',
               lambda m: keep_name(m, True), b)
    b = re.sub(rb'[A-Za-z]:\\+[Uu]sers\\+[\x20-\x7e]{1,260}', lambda m: keep_name(m, False), b)
    for n in _names():
        if len(n) < 4 or n.lower() in GENERIC_ACCOUNTS:   # "user", "admin" ... are also bytes of the embedded program's own data
            continue
        for enc in ('utf-8', 'utf-16-le'):
            raw = n.encode(enc)
            b = b.replace(raw, _fill(len(raw) // (2 if enc == 'utf-16-le' else 1)).encode(enc))      # exact case only
    return b


def sanitize(path):
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, 'w') as zo:
        for it in zi.infolist():
            if it.filename == 'Preview/PrvImage.png':
                continue
            data = zi.read(it.filename)
            if it.filename == 'Contents/content.hpf':
                data = re.sub(rb'(name="(?:creator|lastsaveby)" content="text">)[^<]*', rb'\1' + AUTHOR.encode(), data)
            if it.filename.lower().endswith(TEXT):
                try:
                    data = _text_clean(data.decode('utf-8')).encode('utf-8')
                except UnicodeDecodeError:
                    pass
            elif it.filename.startswith('BinData/') and not it.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                data = _binary_clean(data)
            zo.writestr(it, data, compress_type=it.compress_type)
    os.replace(tmp, path)


# Repository scan (`hd textstyle scan --repo`): every tracked file, its name, its text, the inside of an HWPX (every zip entry, UTF-8
# and UTF-16) and the text chunks of a PNG (tEXt, zTXt, iTXt, eXIf). The only allowed hits, each written here with its reason:
ALLOWED = {
    # (repo path, pattern label): reason
    ('lib/hwpx_docs/textstyle/privacy.py', 'generic'): 'the generic path patterns of this scanner (users\\, c:/users, d:/, appdata, ＠)',
}
# e-mail addresses at example.com / example.org / example.net are fictional (RFC 2606) and never reported (EMAIL above).


def _png_text(data):
    """The text chunks of a PNG, as bytes."""
    import zlib
    out, i = [], 8
    while i + 8 <= len(data):
        n = int.from_bytes(data[i:i + 4], 'big')
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if kind in (b'tEXt', b'iTXt', b'eXIf'):
            out.append(body)
        elif kind == b'zTXt':
            k = body.find(b'\x00')
            try:
                out.append(body[:k] + b' ' + zlib.decompress(body[k + 2:]))
            except zlib.error:
                out.append(body)
        i += 12 + n
    return b'\n'.join(out)


def _hits(data, names):
    """[(label, pattern)] of private patterns in `data` (bytes)."""
    low = data.lower()
    out = [('generic', p.decode('utf-8', 'replace')) for p in _generic() if p in low]
    out += [('private', n) for n in names if n.lower().encode('utf-8') in low or n.lower().encode('utf-16-le') in low]
    m = EMAIL.search(data)
    if m:
        out.append(('e-mail', m.group(0).decode('utf-8', 'replace')))
    return out


def scan_repo(root):
    """Findings of every file that git tracks under `root`: [(path, where, label, pattern)], ALLOWED left out."""
    import subprocess
    files = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True, check=True).stdout.decode('utf-8').split('\0')
    names = _names()
    found = []
    for rel in [f for f in files if f]:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        parts = [('name', rel.encode('utf-8'))]
        data = open(path, 'rb').read()
        if rel.lower().endswith('.hwpx'):
            with zipfile.ZipFile(path) as z:
                parts += [(e, z.read(e)) for e in z.namelist()]
                parts += [(e + ' (name)', e.encode('utf-8')) for e in z.namelist()]
        elif rel.lower().endswith('.png'):
            parts.append(('png text', _png_text(data)))
        else:
            parts.append(('text', data))
        for where, blob in parts:
            if where == 'Contents/content.hpf':
                blob = re.sub(rb'name="(?:creator|lastsaveby)" content="text">' + AUTHOR.encode(), b'', blob)
            for label, pat in _hits(blob, names):
                if (rel.replace(BACKSLASH, '/'), label) not in ALLOWED:
                    found.append((rel, where, label, pat))
    return found


def scan(path, fix=False):
    """Findings of the privacy scan of one HWPX: [(zip entry, what)]; fix=True runs `sanitize` first."""
    if fix:
        sanitize(path)
    found = []
    patterns = [(p, p.decode('ascii', 'replace')) for p in _generic()] + [
        (x, 'user name / private text') for n in _names() for x in (n.lower().encode('utf-8'), n.lower().encode('utf-16-le'))]
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            data = z.read(name)
            if name.lower().endswith(TEXT):
                t = data.decode('utf-8', 'replace')
                slots = [m.group(2) for m in SLOT_NAME.finditer(t)] + [m.group(2) for m in SLOT_AUTHOR.finditer(t)]
                found += [(name, f'author slot "{a}"') for a in slots if a != AUTHOR]
                if EMAIL.search(data):
                    found.append((name, 'e-mail address'))
            if name == 'Contents/content.hpf':        # the author names are not private once they say hwpx-docs
                data = re.sub(rb'name="(?:creator|lastsaveby)" content="text">' + AUTHOR.encode(), b'', data)
            for pat, label in patterns:
                if pat in data.lower():
                    found.append((name, label))
    return found
