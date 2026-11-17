"""The gates (plugin hooks): what a model may read, run and say. Decisions are made here; scripts/hook.py only carries the JSON.

  pre_read(path)        PreToolUse Read: refuse a document, a derived file, a picture of a document, the vault, a file with personal data
  pre_bash(command)     PreToolUse Bash: refuse raw dumps of a document and any way around the filter; `hd` / `pv.py` pass
  pre_grep(tool_input)  PreToolUse Grep: same file checks for the searched file or folder
  prompt(text)          UserPromptSubmit: block a prompt that holds personal data (the prompt is then not sent)

Every refusal says what to do instead and names kinds and counts, never a value. A refusal and every finding go to the audit log.
"""
import glob
import os
import re
import shlex
import time
import zipfile

from . import detect, engine, settings, vault as V

DOC_EXT = ('.hwp', '.hwpx', '.hwt', '.hml', '.owpml')
IMG_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff', '.emf', '.wmf', '.webp')
HD_RUN = re.compile(r'(?:^|[\\/\s])(?:hd(?:\.py)?|pv\.py)(?:\s|$)')
# only commands that take the inside of a document out are refused (v1: the gate refuses what is certain, a user's own work passes)
DUMP_CMDS = {'cat', 'type', 'head', 'tail', 'less', 'more', 'strings', 'xxd', 'hexdump', 'od', 'base64', 'certutil', 'unzip', '7z', '7za', '7zr',
             'tar', 'zipinfo', 'gc', 'get-content', 'expand-archive', 'select-string', 'sls', 'grep', 'egrep', 'rg', 'awk', 'sed', 'iconv',
             'format-hex', 'convertto-json', 'out-string', 'cmd', 'copy-item-to-zip'}
INLINE_CMDS = {'python', 'python3', 'py', 'node', 'perl', 'ruby', 'powershell', 'pwsh', 'php'}          # refused only with inline code that names a document
INLINE_FLAGS = ('-c', '-e', '-command', '-encodedcommand', '/c')
BYPASS = re.compile(r'HWPX_DOCS_ADDONS|HWPX_PRIVACY_\w+|hwpxpriv|hwpx_docs\.core\.addons', re.I)
VAULT_CMDS_USER_ONLY = re.compile(r'(?:\bvault|pv\.py\"?)\s+(?:consent|purge|add|enable|disable)\b')
CERTAIN_KINDS = {'rrn', 'frn', 'card', 'driving', 'bank', 'brn', 'passport', 'private'}     # numbers with a check or a label; a name or an address is never "certain"
ALLOW_WORD ='#허용'                       # a prompt that holds this word is let through (and logged): the user decided
SCAN_BYTES = 256_000                     # a file is scanned by its first 256 KB (the scan takes about 16 ms per KB); a larger file is asked about
GREP_SECONDS = 15                        # the time a folder scan for Grep may take
BASH_SECONDS = 15                        # the time the file checks of one Bash command may take (the hook time limit is 30 s)
WORKAROUND = (' This layer protects against slips in everyday work: do not work around the refusal with another tool or command; '
              'use the `hd` commands (they show tags instead of values) or `pv.py mask-copy`.')


ASK = '\x00ask:'                          # a verdict that starts with this asks the user instead of denying


def decode_text(raw):
    """The text of a file's bytes, or None for a binary. UTF-16 only with a byte-order mark or NUL bytes in every second place; else UTF-8
    (a cut inside the last character is fine), else cp949 (a Korean CSV from Excel). A cp949 file of even length is never read as UTF-16."""
    import codecs
    if not raw:
        return ''
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff') or (len(raw) >= 4 and (raw[1::2].count(0) > len(raw) // 6 or raw[0::2].count(0) > len(raw) // 6)):
        enc = 'utf-16-be' if (raw[:2] == b'\xfe\xff' or (raw[:2] != b'\xff\xfe' and raw[0::2].count(0) > raw[1::2].count(0))) else 'utf-16-le'
        return codecs.getincrementaldecoder(enc)('replace').decode(raw, final=False)
    if raw.count(b'\x00') > len(raw) // 20:
        return None                                                   # a binary
    try:
        return codecs.getincrementaldecoder('utf-8')().decode(raw, final=False)
    except UnicodeError:
        text = raw.decode('cp949', 'replace')                          # text in cp949 has (almost) no bytes that cp949 cannot read; a binary has many
        bad = text.count('\ufffd') + sum(1 for c in text if c < ' ' and c not in '\t\n\r\f')
        return text if bad <= len(text) // 50 else None


class Gate:
    def __init__(self):
        self.vault = V.Vault()
        self.det = detect.Detector()
        self.mode = settings.mode()

    # ---- file checks -------------------------------------------------------------------------------------------------
    def is_document(self, path):
        low = path.lower()
        if low.endswith(DOC_EXT):
            return True
        try:
            with open(path, 'rb') as f:
                head = f.read(8)
            if head == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return True                                           # an OLE file: HWP 5 (a renamed copy too)
            if head[:4] == b'PK\x03\x04' and os.path.getsize(path) < 200_000_000:
                with zipfile.ZipFile(path) as z:
                    names = z.namelist()
                    return any(n.startswith('Contents/section') for n in names) or 'Contents/content.hpf' in names
        except (OSError, zipfile.BadZipFile):
            pass
        return False

    def file_verdict(self, path, deep=True):
        """None = allowed, else the reason (a sentence that is safe to show)."""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return None
        home = os.path.abspath(V.home()).lower()
        if path.lower().startswith(home):
            return 'the vault folder of the privacy add-on is closed to the model; use `pv.py list` (it never shows values)'
        if self.is_document(path):
            return ('a Hangul document is not read directly: its text holds personal data that would leave this PC. '
                    'Use `hd text`, `hd slots`, `hd form list` (they show tags such as ⟪성명1⟫); for an .hwpx a covered copy is made with `pv.py mask-copy in out` '
                    '(an HWP 5 file is saved as .hwpx in Hangul first)')
        if self.vault.tainted(path):
            if self.path_is_text(path):
                return ('this file was made from a document with personal data (a dump, a text export). '
                        'Make a covered copy with `pv.py mask-copy <file> <out>` and read that')
            return ('this file (a picture or another binary) was made from a document with personal data and cannot be covered: it is not read directly. '
                    'Look at the document through `hd` (text, slots) or ask the user to look at it')
        low = path.lower()
        if low.endswith(IMG_EXT):
            if self.mode == 'strict' or 'bindata' in low.replace('\\', '/').split('/') or 'prvimage' in low:
                return 'a picture can hold a face, a signature or an ID card; in strict mode and for pictures from a document it is not read directly'
            return None
        if not deep:
            return None
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            raw = f.read(SCAN_BYTES)
        hits = self.scan_bytes(raw)
        if hits:
            return (f'the file holds personal data ({self.describe(hits)}). Make a covered copy with `pv.py mask-copy <file> <out>` and read that')
        if size > SCAN_BYTES:
            return ASK + (f'the file is larger than {SCAN_BYTES // 1000} KB: only its first part was checked for personal data. '
                          'Read it only if you know that it holds none')
        return None

    def scan_bytes(self, raw):
        """Counter of kinds found in a file's bytes (text) and a hit count for known vault values."""
        from collections import Counter
        c = Counter()
        text = decode_text(raw)
        if text is None:
            for value, _ in [(e['value'], 0) for e in self.vault.data['entries'].values() if len(e['value']) >= 4]:
                for enc in ('utf-8', 'utf-16-le'):
                    if value.encode(enc, 'ignore') in raw:
                        c['known'] += 1
            return c
        sess = engine.Session.__new__(engine.Session)
        sess.vault, sess.det, sess.mode = self.vault, self.det, 'standard'
        seen = set()
        for s in sess._spans(text, overlap=True):                         # before one span hides another: a list with a 주소 column
            if self.certain(s) and (s.start, s.end, s.kind) not in seen:      # makes the whole row one address span
                seen.add((s.start, s.end, s.kind))
                c[s.kind] += 1
        return c

    @staticmethod
    def path_is_text(path):
        try:
            with open(path, 'rb') as f:
                return decode_text(f.read(4096)) is not None
        except OSError:
            return False

    @staticmethod
    def certain(s):
        """A finding the gate may act on: a value with a check digit, a labelled value, or a value that the vault already holds. The weak
        shapes (a name that looks like a name) are only logged."""
        return s.kind in CERTAIN_KINDS and (s.level == 9 or s.score >= 90)

    @staticmethod
    def describe(counter):
        return ', '.join(f'{k} {n}' for k, n in counter.most_common(6))

    # ---- hooks -------------------------------------------------------------------------------------------------------
    def pre_read(self, path):
        r = self.file_verdict(path)
        return self._deny('Read', r, path)

    def pre_grep(self, ti):
        path = ti.get('path') or '.'
        if os.path.isfile(path):
            return self._deny('Grep', self.file_verdict(path), path)
        if os.path.isdir(path):
            t0, n = time.time(), 0
            for root, _, files in os.walk(path):
                for f in files:
                    p = os.path.join(root, f)
                    if self.is_document(p) or self.vault.tainted(p):
                        return self._deny('Grep', self.file_verdict(p), p)
                    n += 1
                    if time.time() - t0 > GREP_SECONDS or n > 300:
                        return self._deny('Grep', ASK + 'the folder is large: only some of its files were checked for personal data', path)
                    if os.path.getsize(p) < 1_000_000 and not f.lower().endswith(IMG_EXT):
                        r = self.file_verdict(p)
                        if r:
                            return self._deny('Grep', r, p)
        return None

    def pre_bash(self, cmd, cwd='.'):
        """Bash and PowerShell. Refused: a change of the add-on settings, the user-only vault commands, a command that dumps a document
        (unzip, cat, Get-Content, strings, Expand-Archive ...) or runs inline code that names one, and any file that Read would refuse."""
        t0 = time.time()
        if BYPASS.search(cmd):
            return self._deny('Bash', 'a command may not name the settings or the code of the privacy add-on (its environment variables and modules); the settings are changed by you, with `pv.py`, on a terminal', cmd)
        if VAULT_CMDS_USER_ONLY.search(cmd):
            return self._deny('Bash', 'this vault command is for you on a terminal (consent, purge, add, enable, disable); a model does not run it', cmd)
        for seg in re.split(r'&&|\|\||;|\||\r?\n', cmd):
            seg = seg.strip()
            if not seg:
                continue
            if HD_RUN.search(' ' + seg):
                continue                                              # hd / pv.py: output is masked by the filter
            try:
                toks = shlex.split(seg, posix=False)
            except ValueError:
                toks = seg.split()
            toks = [t.strip('"\'') for t in toks]
            first = os.path.basename(toks[0]).lower() if toks else ''
            first = first[:-4] if first.endswith('.exe') else first
            doc_mention = re.search(r'\.hwpx?\b|\.owpml\b', seg, re.I)
            inline = first in INLINE_CMDS and any(t.lower() in INLINE_FLAGS for t in toks[1:])
            if doc_mention and (first in DUMP_CMDS or inline or re.search(r'ZipFile|Compression|OpenRead|ReadAllBytes|ReadAllText|olefile|zipfile', seg)):
                return self._deny('Bash', 'a Hangul document is not opened with other tools (unzip, cat, Get-Content, python -c, strings ...): its text holds '
                                  'personal data. Use `hd text|slots|form list <file>` (masked), or `pv.py mask-copy`', cmd)
            for t in toks[1:]:
                if t.startswith('-') or t.startswith('>') or len(t) > 260:
                    continue
                t = os.path.expandvars(os.path.expanduser(t))             # ~ and $VAR (the shell would expand them)
                for p in glob.glob(t if os.path.isabs(t) else os.path.join(cwd, t)) if any(c in t for c in '*?[') else [t if os.path.isabs(t) else os.path.join(cwd, t)]:
                    if os.path.isfile(p) and first in DUMP_CMDS | INLINE_CMDS:
                        if time.time() - t0 > BASH_SECONDS:
                            return self._deny('Bash', ASK + 'the command names many files: only some of them were checked for personal data', cmd)
                        r = self.file_verdict(p)
                        if r:
                            return self._deny('Bash', r, p)
        return None

    def prompt(self, text):
        """UserPromptSubmit: only what is certain is refused (v1): a resident / foreigner number with a valid check digit and date, a card number
        (Luhn and a known first digit), an account number that carries its label. The word #허용 lets a prompt through (logged)."""
        from . import normalize
        found = {}
        for body in (text, normalize.simple(text)):
            for kind, n in self._prompt_hits(body).items():
                found[kind] = max(found.get(kind, 0), n)
        if found and ALLOW_WORD in text:
            self._audit('prompt-allow', kinds=found)
            return None
        if found:
            self._audit('prompt-block', kinds=found)
            return (f'The prompt holds personal data ({", ".join(f"{k} {n}" for k, n in found.items())}). It was not sent to the model. '
                    f'Remove the values (name the field instead); if you decide to send it anyway, add the word {ALLOW_WORD} to the prompt. '
                    'A document is read with `hd`, which shows tags instead of values.')
        return None

    def _prompt_hits(self, body):
        from collections import Counter
        from . import validators
        sess = engine.Session.__new__(engine.Session)
        sess.vault, sess.det, sess.mode = self.vault, self.det, 'standard'
        c = Counter()
        for s in sess._spans(body, overlap=True):
            d = validators.digits(s.text)
            if s.kind == 'rrn' and len(d) == 13 and validators.rrn_checksum_ok(d) and validators.rrn_date(d):
                c['rrn'] += 1
            elif s.kind == 'frn' and len(d) == 13 and validators.frn_checksum_ok(d) and validators.rrn_date(d):
                c['frn'] += 1
            elif s.kind == 'card' and validators.card(d):
                c['card'] += 1
            elif s.kind == 'bank' and s.level == 2:                  # an account number with its label ("계좌번호 ...")
                c['bank'] += 1
            elif s.disclose == 'known' and s.kind in ('rrn', 'frn', 'card', 'bank'):
                c[s.kind] += 1
        return c

    # ---- helpers -----------------------------------------------------------------------------------------------------
    def _deny(self, tool, reason, what):
        """(decision, reason) or None. A reason that starts with ASK is an `ask`."""
        if not reason:
            return None
        ask = reason.startswith(ASK)
        reason = reason[len(ASK):] if ask else reason
        self._audit('ask' if ask else 'deny', tool=tool, target=V.src_id(what) if os.path.exists(what) else '')
        reason = reason.rstrip()
        if not ask and not reason.endswith(('.', '!', '?')):
            reason += '.'                                                  # the refusal is a sentence, then the advice
        return ('ask' if ask else 'deny', reason + ('' if ask else WORKAROUND))

    @staticmethod
    def _audit(event, **kw):
        V.audit(event, **kw)
