"""The engine of the add-on: pseudonymize what a command prints, resolve tags before a command writes.

The core (hwpx_docs/core/addons.py) calls two entry points, both given the argument list of the `hd` call:

  output_filter(argv) -> object f; f(text) -> text, f.finish()      every text that the command shows (stdout, stderr, errors)
  write_resolver(argv) -> (argv2, cleanup)                          tags in the arguments and in text input files -> real values

A tag is `⟪성명1⟫`; only a registration number shows age band and sex (`⟪주민번호1｜1980년대·남⟫`). The id (`주민번호1`) is all that the
resolver needs, so `⟪주민번호1⟫` works too.
Mode (the "mode" key of the settings file; the variable HWPX_PRIVACY_MODE=strict can only raise it): `standard` (default: identifiers, names,
contacts, hidden places) and `strict` (also birth date, age, school, employer, family, dictionary terms and every typed form value). There is no `off`.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from collections import Counter

from . import docscan, normalize, settings, validators, vault as vaultmod
from .detect import Detector, Span

OPEN, CLOSE, SEP = '⟪', '⟫', '｜'
# a tag, also a little broken by the model: spaces inside, a double angle bracket 《》 for ⟪⟫, an ASCII bar for ｜
TAG = re.compile('[⟪《]\\s*([^｜⟫》|\\n]{1,40}?)\\s*(?:[｜|][^⟫》\\n]*)?[⟫》]')
PARTICLE = '이나|이다|으로|은|는|이|가|을|를|와|과|로|나|다|아|야'
TAGP = re.compile(TAG.pattern + '(?:(' + PARTICLE + ')(?![가-힣]))?')
TEXT_INPUT = ('.json', '.md', '.html', '.txt', '.csv')
RENDER_CMDS = ('render', 'preview')                          # commands that draw a document: they get a covered copy


def is_render(argv):
    """`hd render ...`, `hd preview ...`, and what `hd preview x.hwp` becomes (`hwp render`)."""
    return bool(argv) and (argv[0] in RENDER_CMDS or (argv[0] == 'hwp' and len(argv) > 1 and argv[1] in RENDER_CMDS))


def has_tag(text):
    return bool(TAG.search(text))


class PrivacyError(Exception):
    """A message that is safe to print (never holds a value)."""


class Session:
    """State of one `hd` call: detector, vault, what was masked."""
    _det = None
    learning = False                                         # class default: the gates build a Session without __init__

    def __init__(self, argv):
        self.argv = argv
        self.mode = settings.mode()
        if Session._det is None:
            Session._det = Detector()
        self.det = Session._det
        self.vault = vaultmod.Vault()
        self.consent = vaultmod.consents()
        self.counts = Counter()
        self.docs = [a for a in argv[1:] if not a.startswith('-') and docscan.sniff(a)]      # by content, not by the extension
        self.t0 = time.time()
        self.learning = False

    # ---- known values ------------------------------------------------------------------------------------------------
    def known_spans(self, text):
        """Exact values that the vault already holds (a value that a pattern would miss in another layout)."""
        k = self._known()
        out = []
        for m in re.finditer(r'\d(?:[\s.-]?\d)+', text):                 # numbers: compare by digits, any separators
            run, digs = m.group(0), []
            pos = [i for i, c in enumerate(run) if c.isdigit()]
            digits = ''.join(run[i] for i in pos)
            for ln in k['lens']:
                for i in range(0, len(digits) - ln + 1):
                    tid = k['num'].get(digits[i:i + ln])
                    if tid and (i == 0 or ln >= 7):                      # a short number inside a longer one is not the value
                        a, b = pos[i], pos[i + ln - 1] + 1
                        out.append(Span(m.start() + a, m.start() + b, self.vault.get(tid)['kind'], self.vault.get(tid)['label'], True,
                                        run[a:b], 'known', tid, 9, 99))
        for ch in set(text) & set(k['lit']):
            for m in k['lit'][ch].finditer(text):
                tid = k['map'][m.group(0)]
                e = self.vault.get(tid)
                out.append(Span(m.start(), m.end(), e['kind'], e['label'], False, m.group(0), 'known', tid, 9, 99))
        # a value cut at the end of a line (a listing that shows 60 characters): the first characters of a known value are the value
        if k['tail'] is not None:
            for m in k['tail'].finditer(text):
                tid = k['tailmap'][m.group(0)]
                e = self.vault.get(tid)
                out.append(Span(m.start(), m.end(), e['kind'], e['label'], False, m.group(0), 'known', tid, 9, 98))
        for m in re.finditer(r'\d(?:[\s.-]?\d)+(?=[\'"]?[ \t]*(?:\n|$))', text):
            run = m.group(0)
            pos = [i for i, c in enumerate(run) if c.isdigit()]
            digits = ''.join(run[i] for i in pos)
            for ln in range(min(len(digits), k['maxnum'] - 1), 5, -1):
                tid = k['numpre'].get(digits[-ln:])
                if tid:
                    out.append(Span(m.start() + pos[-ln], m.start() + pos[-1] + 1, self.vault.get(tid)['kind'], self.vault.get(tid)['label'],
                                    True, run[pos[-ln]:pos[-1] + 1], 'known', tid, 9, 98))
                    break
        return out

    def _known(self):
        n = (len(self.vault.data['entries']), self.mode)
        if getattr(self, '_kn', None) and self._kn['n'] == n:
            return self._kn
        num, lit, map_ = {}, {}, {}
        for tid, e in self.vault.data['entries'].items():
            if e['kind'] == 'term' and self.mode != 'strict':
                continue                                     # sensitive text is masked in strict mode only
            v = e['value'].strip()
            d = ''.join(c for c in v if c.isdigit())
            if e.get('numeric') and len(d) >= 6:
                num[d] = tid
            elif len(v) >= 2 and e['kind'] != 'meta' or (e['kind'] == 'meta' and len(v) >= 4):
                lit.setdefault(v[0], []).append(v)
                map_[v] = tid
        numpre = {d[:ln]: tid for d, tid in num.items() for ln in range(6, len(d))}
        tailmap = {v[:ln]: tid for v, tid in map_.items() if len(v) >= 6 for ln in range(4, len(v))}
        tail = (re.compile('(?<![가-힣A-Za-z0-9])(?:' + '|'.join(re.escape(x) for x in sorted(tailmap, key=len, reverse=True))
                           + ')(?=[\'"]?[ \t]*(?:\n|$))') if tailmap else None)
        self._kn = {'n': n, 'num': num, 'lens': sorted({len(x) for x in num}, reverse=True), 'numpre': numpre, 'tail': tail,
                    'tailmap': tailmap, 'maxnum': max((len(x) for x in num), default=0),
                    'lit': {c: re.compile('|'.join(re.escape(x) for x in sorted(vs, key=len, reverse=True))) for c, vs in lit.items()},
                    'map': map_}
        return self._kn

    # ---- masking -----------------------------------------------------------------------------------------------------
    def mask(self, text, learn_source=None):
        """Return `text` with every detected value replaced by its tag. New values go into the vault."""
        if not text:
            return text
        if re.search('[ᄀ-ᇿ]', text):                       # decomposed jamo: one form
            text = unicodedata.normalize('NFC', text)
        for _ in range(2):                                   # second pass: nothing may be left (the first pass can expose a neighbour)
            spans = self._spans(text)
            if not spans:
                break
            out, last = [], 0
            for s in spans:
                out.append(text[last:s.start])
                out.append(self.display(s, learn_source))
                last = s.end
            out.append(text[last:])
            text = ''.join(out)
        return text

    def _spans(self, text, strict=None, overlap=False):
        strict = self.mode == 'strict' if strict is None else strict
        shadow = TAG.sub(lambda m: '\x00' * len(m.group(0)), text)          # a tag is never detected again
        norm, idx = normalize.mapped(shadow)                                # odd input (full width, zero width, O for 0 ...) in one shape
        extra = [] if self.learning else self.known_spans(norm)           # while learning, the index of known values is not rebuilt per cell
        spans = self.det.find(norm, strict=strict, extra=extra, overlap=overlap)
        out = []
        for s in spans:
            a, b = idx[s.start], idx[s.end - 1] + 1                         # back to the original text
            raw = shadow[a:b]
            if '\x00' in raw:
                continue
            s.start, s.end, s.text = a, b, raw
            out.append(s)
        return out

    def display(self, s, source=None):
        if s.disclose == 'known':                            # an exact value that the vault already holds
            tid = s.ctx
            e = self.vault.get(tid)
        elif s.kind == 'term':                               # a dictionary term: a typed tag, the sentence around it stays readable
            tid = self.vault.add('term', s.label, s.text, False, source or self.src(), [], '', {'cat': s.cat})
            e = self.vault.get(tid)
        else:
            fn = validators.DISCLOSE.get(s.disclose, validators.d_none)
            d = fn(s.text, s.ctx, fine=self._fine(s.kind))
            tid = self.vault.add(s.kind, s.label, s.text, s.numeric, source or self.src(), d['attrs'], d['status'])
            e = self.vault.get(tid)
        if source:
            self.vault.add(e['kind'], e['label'], e['value'], e.get('numeric', False), source)
        self.counts[e['kind']] += 1
        if tid in self.consent['tags'] or e['kind'] in self.consent['types']:
            vaultmod.audit('reveal', tag=tid, kind=e['kind'])
            return e['value']
        if e['kind'] == 'term':
            return f'{OPEN}{tid}{SEP}{e["cat"]}{CLOSE}'
        attrs = [txt for _, txt in e.get('attrs', [])]
        fields = [tid] + (['·'.join(attrs)] if attrs else []) + ([e['status']] if e.get('status') else [])
        return OPEN + SEP.join(fields) + CLOSE

    def _fine(self, kind):
        c = self.consent['types'].get(kind)
        return bool(c and c.get('fine'))

    def src(self):
        return vaultmod.src_id(self.docs[0]) if self.docs else None

    # ---- learning a document ----------------------------------------------------------------------------------------
    def learn(self, path):
        """Read a document once (before the command runs) and put every personal value in the vault, so the same value is masked
        wherever it shows: in `hd text`, in an error, in a dump. Returns the number of new vault entries."""
        kind = docscan.sniff(path)
        if not kind:
            return 0
        n0 = len(self.vault.data['entries'])
        src = vaultmod.src_id(path)
        rows = docscan.slots(path)
        folder = os.environ.get('HWPX_PRIVACY_TEMPLATES')
        tpl, new = docscan.entered(path, rows, folder) if folder and os.path.isdir(folder) else (None, [])
        every = os.environ.get('HWPX_PRIVACY_FIELDS') == 'all' or self.mode == 'strict'
        grid = _grid(rows)
        self.learning = True
        try:
            self._learn_rows(rows, new, every, grid, src, path, kind)
        finally:
            self.learning = False
        return len(self.vault.data['entries']) - n0

    def _learn_rows(self, rows, new, every, grid, src, path, kind):
        for r in rows:
            text = r['text'].strip()
            if not text:
                continue
            labels = [r['label']] if r['label'] else []
            labels += grid.get(r['key'], [])                           # the label to the left and the header above the cell
            # a value typed into a form (it differs from the blank form) is masked whatever its shape when its label names a person's
            # field (성명, 주민, 연락처, 주소 ...); strict masks every typed value
            personal = any(self.det.personal_label(x) for x in labels)
            cand = (r in new and (every or personal)) or (every and r['label'])
            for lab in dict.fromkeys(labels) or ['']:
                self.mask((lab + '\n' if lab else '') + text + '\n', learn_source=src)
            if cand and not self._covered(text) and not _boilerplate(text):
                self.vault.add('field', '입력', text, False, src, [], '')
        if kind == 'hwp':                                          # the summary of an HWP: title, subject, author, last author ...
            for value in docscan.hwp_summary(path):
                self.vault.add('meta', '메타', value, False, src, [], '')
        if kind == 'hwpx':
            for text in docscan.hwpx_texts(path):
                self.mask(text, learn_source=src)
            for kind, value in docscan.hidden_values(path):
                self.vault.add('meta', '메타', value, False, src, [], '')

    def _covered(self, text):
        """True when `text` is already one tag after masking (nothing more to add for it)."""
        prev, self.learning = self.learning, False
        try:
            return bool(TAG.fullmatch(self.mask(text).strip()))
        finally:
            self.learning = prev


CELL = re.compile(r'^(s\d+\.)?t(\d+)\.r(\d+)c(\d+)$')


def _grid(rows):
    """{slot key: [text of the nearest non-empty cell to the left, of the nearest one above]} for the cells of every table."""
    cells = {}
    for r in rows:
        m = CELL.match(r['key'])
        if m and r['text'].strip():
            cells[(m.group(1), m.group(2), int(m.group(3)), int(m.group(4)))] = (r['key'], r['text'].strip())
    out = {}
    for (s, t, row, col), (key, text) in cells.items():
        found = []
        for c in range(col - 1, max(0, col - 8), -1):
            if (s, t, row, c) in cells:
                found.append(cells[(s, t, row, c)][1])
                break
        for rr in range(row - 1, max(0, row - 8), -1):
            if (s, t, rr, col) in cells:
                found.append(cells[(s, t, rr, col)][1])
                break
        out[key] = [x for x in found if len(x) <= 24]
    return out


def _boilerplate(text):
    t = text.strip()
    return len(t) < 2 or t in ('○', '◯', '☐', '☑', '□', '해당없음', '해당 없음', '없음', '-', 'O', 'X')


from .ioflow import Filter, cleanup_stale, output_filter, resolve_text, write_resolver  # noqa: E402,F401  (entry points of the add-on)
