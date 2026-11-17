"""The detector: four levels over plain text. Rules come from the packs (packs/*/pack.json); nothing is hard-coded per kind.

  L1  patterns with a check (check digits, date, Luhn ...)           kind "patterns" with "check", or a shape that is rare
  L2  form context: the value that stands after a label (same line, or the next line), kind "labels" + "value"
  L3  names in prose: surname + given-name shape + a title or particle (kind "name", pattern group B)
  L4  sensitive sentences: category keywords (pack kr-sensitive-terms), only in strict mode
  K   user terms: HWPX_DOCS_PRIVATE (`;`), HWPX_PRIVACY_HOME/terms.txt, HWPX_PRIVACY_ORG/*.txt (one term per line, `re:` = regex)

`Detector.find(text)` returns non-overlapping `Span`s. Standard library only.
"""
import glob
import json
import os
import re

from . import validators

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = os.path.join(HERE, '..', '..', 'packs')
LAB_SEP = r'[ \t:：=|\]\'"\)]'


class Span:
    __slots__ = ('start', 'end', 'kind', 'label', 'numeric', 'text', 'disclose', 'ctx', 'level', 'score', 'cat')

    def __init__(self, start, end, kind, label, numeric, text, disclose, ctx, level, score, cat=''):
        self.start, self.end, self.kind, self.label, self.numeric, self.text = start, end, kind, label, numeric, text
        self.disclose, self.ctx, self.level, self.score, self.cat = disclose, ctx, level, score, cat

    def __repr__(self):
        return f'Span({self.kind},{self.text!r},L{self.level})'


def expand(pattern, lists):
    def sub(m):
        items = lists[m.group(1)]
        if len(items) == 1:
            return items[0]
        return '(?:' + '|'.join(re.escape(x) for x in sorted(items, key=lambda s: (-len(s), s))) + ')'
    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', sub, pattern)


def label_rx(label):
    if '\\' in label:
        return label.replace(' ', r'\s*')
    return r'\s*'.join(re.escape(c) for c in label if not c.isspace())


STRICT_SEP = r'(?:[ \t]*[:：=|\]\'"\t][ \t:：=|\]\'"]*|[ \t]{2,})'


class Fixed:
    """Fixed text of public blank forms (pack kr-fixed-text): words that are never a person's value, numbers that are public."""
    def __init__(self):
        self.tokens, self.numbers = set(), {}

    def load(self, pack):
        self.tokens |= set(pack.get('tokens', []))
        for k, v in pack.get('numbers', {}).items():
            self.numbers.setdefault(k, set()).update(v)

    def words_only(self, s):
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', s)
        return bool(words) and all(w in self.tokens for w in words)

    def public(self, kind, v, numeric):
        """True when this exact value is printed in a public blank form (digits for a number, the text without spaces otherwise)."""
        return (validators.digits(v) if numeric else ''.join(v.split())) in self.numbers.get(kind, ())


FIXED = Fixed()
LABEL_LINE = re.compile(r'^\s*(?:[①-⑳]|\d{1,2}[.)])|[:：]\s*$|\(\s{2,}\)|_{3,}|\s{6,}')


class Kind:
    def __init__(self, k, lists):
        self.id, self.label, self.group = k['id'], k['label'], k.get('group', '?')
        self.numeric, self.disclose = k.get('numeric', False), k.get('disclose', 'none')
        self.patterns = [(re.compile(expand(p['re'], lists)), p.get('check')) for p in k.get('patterns', [])]
        self.popts = [{'stop': set(lists.get(p['stoplist'], [])) if p.get('stoplist') else None, 'weak': p.get('weak', False),
                       'status': p.get('status', '')} for p in k.get('patterns', [])]
        self.check = k.get('check')
        self.stop = set(k.get('stop', []))
        self.stop_suffix = tuple(k.get('stop_suffix', []))
        self.rules = []
        labels = k.get('labels', [])
        if labels and k.get('value'):
            lab = '(?:' + '|'.join(label_rx(x) for x in sorted(labels, key=len, reverse=True)) + ')'
            val = '(?P<v>' + expand(k['value'], lists) + ')' + k.get('value_after', '')
            paren = r'(?:[ \t]*[\(（][^)）\n]{0,12}[\)）])?'
            # a free-text value (a name, an address ...) after a label needs a real separator, not one space: "신청인 같은 ..." is prose
            sep = STRICT_SEP if k.get('sep') == 'strict' else '(?=' + LAB_SEP + ')' + LAB_SEP + '*'
            # a number kind accepts a compound label (결제계좌번호, 휴대전화번호); a free-text kind needs a word boundary before the label
            bound = '' if k.get('numeric') else r'(?<![가-힣A-Za-z])'
            same = (bound + r'(?P<l>' + lab + ')' + paren + sep + val)
            # the label may end a longer header line ("요청자 소속", "결제계좌번호(수취인), 송금액($)"): the value is the next line
            nxt = (r'(?:^|\n)[^\n]{0,15}?' + bound + r'(?P<l>' + lab + r')[^\n]{0,24}\n+(?:[ \t]*\n)?[ \t]*(?P<v>'
                   + expand(k['value'], lists) + r')[ \t]*(?=\n|$)')
            self.rules = [re.compile(same), re.compile(nxt)]
        self.value_line = k.get('value_line', False)
        self.all_labels = list(k.get('labels', []))
        self.shape = None
        if k['id'] == 'name' and {'SURNAME1', 'SURNAME2'} <= set(lists):         # surname + given name: a name, even when forms print it as a sample
            self.shape = re.compile('^(?:' + expand('{{SURNAME2}}', lists) + '[가-힣]{1,2}|' + expand('{{SURNAME1}}', lists) + '[가-힣]{1,2})$')
        self.level = k.get('level', 'standard')
        self.require = re.compile(k['require']) if k.get('require') else None
        self.free = k.get('free', False)

    def plausible(self, v):
        """Reject a value that is itself a label or a stop word (a blank form has labels where the values go)."""
        s = v.strip()
        if s in self.stop or any(s.endswith(x) for x in self.stop_suffix):
            return False
        if self.require and not self.require.search(s):
            return False
        if self.free and FIXED.words_only(s) and not (self.shape and self.shape.match(s)):
            return False                                      # every word of it is fixed text of a public blank form
        if self.free and LABEL_LINE.search(s):
            return False                                      # a numbered line, a line ending in a colon, a blank "(    )": a label line
        if self.check and self.check in validators.CHECKS and not validators.CHECKS[self.check](s):
            return False
        return bool(s)


def load_lists_and_kinds(pack_dirs=None):
    kinds, meta = {}, {}
    dirs = pack_dirs or sorted(glob.glob(os.path.join(PACKS, '*')))
    enabled = os.environ.get('HWPX_PRIVACY_PACKS')
    for d in dirs:
        p = os.path.join(d, 'pack.json')
        if not os.path.exists(p):
            continue
        pack = json.load(open(p, encoding='utf-8'))
        if enabled and pack['name'] not in enabled.split(','):
            continue
        meta[pack['name']] = pack
        if 'tokens' in pack or 'numbers' in pack:
            FIXED.load(pack)
        for k in pack.get('kinds', []):
            if k['id'] in kinds:
                raise ValueError(f'kind "{k["id"]}" is in two packs')
            kinds[k['id']] = Kind(k, pack.get('lists', {}))
    return kinds, meta


class Detector:
    def __init__(self, pack_dirs=None):
        self.kinds, self.meta = load_lists_and_kinds(pack_dirs)
        self.terms = self._terms()
        self.look = next((p for p in self.meta.values() if 'non_personal_labels' in p), None)
        labs = sorted({x for k in self.kinds.values() for x in k.all_labels}, key=len, reverse=True)
        self._any_label = re.compile('(?<![가-힣A-Za-z])(?:' + '|'.join(label_rx(x) for x in labs) + ')') if labs else None
        self.term_rx, self.term_map = None, {}
        for p in self.meta.values():                      # dictionary of sensitive terms (no model needed)
            for top, subs in p.get('terms', {}).items():
                for sub, words in subs.items():
                    for w in words:
                        self.term_map.setdefault(w, (top, sub))
        if self.term_map:
            self.term_rx = re.compile('(?<![가-힣])(?:' + '|'.join(re.escape(w) for w in sorted(self.term_map, key=len, reverse=True)) + ')')
        self.skip = re.compile('|'.join(x for p in self.meta.values() for x in p.get('skip', [])) or r'(?!x)x')

    @staticmethod
    def _terms():
        out = [x for x in os.environ.get('HWPX_DOCS_PRIVATE', '').split(';') if x.strip()]
        from . import vault
        try:
            out += vault.Vault().data.get('terms', [])
        except Exception:
            pass
        files = [os.path.join(vault.home(), 'terms.txt')] + glob.glob(os.path.join(os.environ.get('HWPX_PRIVACY_ORG', '-'), '*.txt'))
        for f in files:
            if os.path.exists(f):
                out += [x.strip() for x in open(f, encoding='utf-8') if x.strip() and not x.startswith('#')]
        rx = []
        for t in out:
            try:
                rx.append(re.compile(t[3:] if t.startswith('re:') else re.escape(t), re.I))
            except re.error:
                pass
        return rx

    # ---- L1 / L2 / L3 / K ------------------------------------------------------------------------------------------
    def candidates(self, text, strict=False):
        out = []
        for kid, k in self.kinds.items():
            if k.level == 'strict' and not strict:
                continue                                        # a kind that only strict mode looks for (other numbers, family)
            for (rx, chk), opt in zip(k.patterns, k.popts):
                for m in rx.finditer(text):
                    g = 'v' if 'v' in rx.groupindex else 0
                    v = m.group(g)
                    if opt['stop'] is not None and v in opt['stop']:
                        continue                                   # an ordinary word that has the shape of a name
                    if chk == 'rrn7':
                        d = validators.digits(v)
                        if len(d) < 7 or validators.rrn_date(d[:6] + d[6] + '000000') is None:
                            continue
                    elif chk and chk in validators.CHECKS and not validators.CHECKS[chk](v):
                        continue
                    if FIXED.public(kid, v, k.numeric) or (k.group == 'B' and FIXED.words_only(v)):
                        continue                                   # printed in a public blank form (an office phone, a title): not a person's
                    level = 3 if k.group == 'B' else 1
                    score = (90 if chk else 70) - (10 if level == 3 else 0) - (15 if opt['weak'] else 0)
                    out.append(Span(m.start(g), m.end(g), kid, k.label, k.numeric, v, k.disclose, self._line(text, m.start(g)), level, score))
            for rx in k.rules:
                pos = 0
                while True:
                    m = rx.search(text, pos)
                    if not m:
                        break
                    v = m.group('v')
                    if not k.plausible(v) or FIXED.public(kid, v, k.numeric):
                        pos = m.start() + 1                      # not a value: look again right behind the start, the next label may begin inside it
                        continue
                    pos = m.end()
                    out.append(Span(m.start('v'), m.end('v'), kid, k.label, k.numeric, v, k.disclose, m.group('l'), 2,
                                    92 + min(len(m.group('l').replace(' ', '')), 20) / 100))      # the longer label is the more specific one
        for rx in self.terms:
            for m in rx.finditer(text):
                if m.group(0):
                    out.append(Span(m.start(), m.end(), 'private', '비공개', False, m.group(0), 'none', '', 5, 95))
        return out

    @staticmethod
    def _line(text, pos):
        a = text.rfind('\n', 0, pos) + 1
        b = text.find('\n', pos)
        return text[a:b if b >= 0 else len(text)]

    def personal_label(self, text):
        """True when a label text names a person's field (성명, 주민등록번호, 연락처, 주소 ...) of any kind."""
        return bool(self._any_label and self._any_label.search(text))

    def lookalike(self, text, s):
        """True when the number looks like an identifier but a strong non-personal signal says it is a product or document number.
        The safe side wins: a personal label next to it, or a valid RRN check digit, keeps it personal."""
        if not self.look or s.kind not in self.look['applies_to']:
            return False
        d = validators.digits(s.text)
        if len(d) != 13:
            return False
        win = text[max(0, s.start - self.look['window']):s.start]
        if any(p in win for p in self.look['personal_labels']):
            return False
        rrn_ok = (validators.rrn_checksum_ok(d) or validators.frn_checksum_ok(d)) and validators.rrn_date(d) is not None
        if rrn_ok:
            return False
        if any(p in win for p in self.look['non_personal_labels']):
            return True
        ean = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d[:12])) % 10
        ean_ok = (10 - ean) % 10 == int(d[12])
        return ean_ok and d[:3] in self.look['gs1_prefixes']

    def find(self, text, strict=False, extra=(), overlap=False):
        """Non-overlapping spans, the strongest first. `overlap=True` returns every candidate (a value with a check digit inside a longer
        label span too): the gate counts what is certain before one span hides another."""
        cands = [c for c in self.candidates(text, strict) if not self.lookalike(text, c)] + list(extra)
        if strict:
            cands += self.sensitive(text)
        if overlap:
            return sorted(cands, key=lambda s: s.start)
        cands.sort(key=lambda s: (-s.score, -(s.end - s.start), s.start))
        taken, out = [], []
        for s in cands:
            if s.end <= s.start or any(s.start < b and a < s.end for a, b in taken):
                continue
            taken.append((s.start, s.end))
            out.append(s)
        return sorted(out, key=lambda s: s.start)

    # ---- L4: dictionary terms (strict) ----------------------------------------------------------------------------------
    SENT = re.compile(r'[^\n.!?。]+(?:[.!?。]+|(?=\n)|$)')

    def sensitive(self, text):
        """Spans of dictionary terms (disease, drug, crime name, religion, party, union, disability type) in sentences that are not an
        instruction line of a form. Each one becomes a typed tag; the sentence around it stays readable."""
        out = []
        if not self.term_rx:
            return out
        for m in self.SENT.finditer(text):
            body = m.group(0).strip()
            if len(body) < 4 or self.skip.search(body):
                continue
            a = m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
            b = m.start() + len(m.group(0).rstrip())
            for t in self.term_rx.finditer(text, a, b):
                top, sub = self.term_map[t.group(0)]
                out.append(Span(t.start(), t.end(), 'term', top, False, t.group(0), 'none', '', 4, 100, cat=sub))
        return out
