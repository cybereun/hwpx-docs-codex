"""Parser of the Hangul equation script: text -> tree. Grammar from the public Hangul help pages and the equation
file-format document (rules E01-E08 in rules.md):

  * Spaces only separate terms; they are not drawn (`~` is a space, backtick a quarter space, `{ }` groups, `" "` quotes).
  * `^` `_` (also `sup` `sub`, `from` `to`) attach to the previous atom, also across a space; their operand is a group or the
    rest of the word up to a space, a backtick, a tilde or the next `^` `_`.
  * `a over b`, `atop`, `choose`, `lsub`, `lsup` are infix: they take the word before and the word after.
  * `sqrt x`, `root n of x`, accents (`hat x`), `not x`, `bigg x` take the next word or group.
  * `left ( ... right )`, `matrix{a & b # c & d}` (+ p/b/d), `cases{..}`, `pile{..}`, `eqalign{..}`; `rm` `it` `bold` `scale n`
    change the style of the rest of the group.

Tree: tuples with the tag first.
  ('row', [node]) ('txt', text, style) ('sp', em) ('frac', num, den, bar) ('sqrt', body, index) ('script', base, sub, sup)
  ('big', glyph, limits_above_below, is_text) ('lr', open, close, body) ('grid', kind, rows, aligns) ('acc', kind, body)
  ('longdiv', divisor, quotient, rows) ('phantom', node) ('colspec', kind, body)
  ('not', node) ('bigg', node) ('rel', arrow, top, bottom) ('binom', a, b) ('lscript', base, sub, sup) ('color', rgb, body)
  ('br',) ('tab',) ('unsup', name)
style = {'rm': bool, 'bold': bool, 'scale': percent}
"""
import re
from . import symbols as sy

BASE_STYLE = {'rm': False, 'bold': False, 'scale': 100}
INFIX = {'over', 'atop', 'choose', 'lsub', 'lsup'}
SCRIPT_END = set(' \t\r\n^_`~#&{}"')
WORD_END = set(' \t\r\n#&}')
MULTI = ('<->', '>>>', '<<<', '->', '<-', '<=', '>=', '!=', '==', '<<', '>>')
SINGLE = {'-': '−', '*': '∗', "'": '′'}
GRID_KINDS = {'matrix': ('', ''), 'pmatrix': ('(', ')'), 'bmatrix': ('[', ']'), 'dmatrix': ('|', '|')}
FUNC_PREFIX = sorted((f for f in sy.FUNCTIONS if len(f) >= 2), key=len, reverse=True)
LETTERS = re.compile(r'[A-Za-z]+')
NUMBER = re.compile(r'\d+(?:\.\d+)?')
EMPTY = ('row', [])


def txt(ch, st):
    return ('txt', ch, st)


class Parser:
    def __init__(self, s):
        self.s, self.i, self.warns, self.unsup = s, 0, [], []

    # ---- helpers ---------------------------------------------------------------------------------------------------
    def warn(self, msg):
        if msg not in self.warns:
            self.warns.append(msg)

    def skip_ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def at_word(self, w):
        m = LETTERS.match(self.s, self.i)
        return bool(m) and m.group().lower() == w

    # ---- sequence (a group body or the whole script) ---------------------------------------------------------------
    def seq(self, st, brace=False, stop_right=False):
        words = [[]]
        closed = not brace
        while self.i < len(self.s):
            c = self.s[self.i]
            if c.isspace():
                self.i += 1
                if words[-1]:
                    words.append([])
                continue
            if c == '}':
                self.i += 1
                if brace:
                    closed = True
                    break
                self.warn('unmatched }')
                continue
            if stop_right and self.at_word('right'):
                break
            if c in '^_':
                self.i += 1
                self.attach(words, c, self.script_operand(st))
                continue
            out = self.atom(st)
            if isinstance(out, dict):                  # style change
                st = out
                continue
            for node in out:
                if node[0] == 'sc':                    # sub / sup / from / to as a word: attach to the previous atom
                    self.attach(words, node[1], node[2])
                else:
                    words[-1].append(node)
        if not closed:
            self.warn('missing }')
        return ('row', self.infix(words))

    def attach(self, words, kind, operand):
        tgt = words[-1] if words[-1] else next((w for w in reversed(words[:-1]) if w), None)
        if tgt is None:
            self.warn('script with no base')
            tgt = words[-1]
            tgt.append(EMPTY)
        base = tgt[-1]
        if base[0] == 'script':
            _, b, sub, sup = base
            if kind == '_' and sub is None:
                tgt[-1] = ('script', b, operand, sup)
                return
            if kind == '^' and sup is None:
                tgt[-1] = ('script', b, sub, operand)
                return
        tgt[-1] = ('script', base, operand if kind == '_' else None, operand if kind == '^' else None)

    def infix(self, words):
        """Words -> flat node list; `over`, `atop`, `choose`, `lsub`, `lsup` combine the word before and the word after."""
        terms = []                                    # each: a list of nodes, or an ('inf', name) marker
        for w in words:
            cur = []
            for n in w:
                if n[0] == 'inf':
                    if cur:
                        terms.append(cur)
                    terms.append(n)
                    cur = []
                else:
                    cur.append(n)
            if cur:
                terms.append(cur)
        out, k = [], 0
        while k < len(terms):
            t = terms[k]
            if not isinstance(t, tuple):
                out.append(t)
                k += 1
                continue
            prev = out.pop() if out else []
            has_next = k + 1 < len(terms) and not isinstance(terms[k + 1], tuple)
            nxt = terms[k + 1] if has_next else []
            k += 2 if has_next else 1
            a, b = ('row', prev), ('row', nxt)
            name = t[1]
            if name == 'over':
                node = ('frac', a, b, True)
            elif name == 'atop':
                node = ('frac', a, b, False)
            elif name == 'choose':
                node = ('binom', a, b)
            elif name == 'lsub':
                node = ('lscript', a, b, None)
            else:
                node = ('lscript', a, None, b)
            out.append([node])
        return [n for t in out for n in t]

    # ---- operands --------------------------------------------------------------------------------------------------
    def group(self, st):
        """`{ ... }` -> row. The caller is at the `{`."""
        self.i += 1
        return self.seq(st, brace=True)

    def word(self, st, ends=WORD_END):
        """Next group, or the atoms up to a space (with their scripts)."""
        self.skip_ws()
        if self.i >= len(self.s) or self.s[self.i] == '}':
            self.warn('missing operand')
            return EMPTY
        if self.s[self.i] == '{':
            return self.group(st)
        if self.s[self.i] == '"':
            return ('row', self.atom(st))
        words = [[]]
        while self.i < len(self.s) and self.s[self.i] not in ends:
            c = self.s[self.i]
            if ends is SCRIPT_END and words[0] and c.isalpha() and c.isascii() and not (self.i and self.s[self.i - 1].isalpha()):
                w = LETTERS.match(self.s, self.i).group().lower()       # a script operand ends before a command word (E02)
                if w in sy.STRUCT or w in sy.BIGOPS:
                    break
            if c in '^_':
                self.i += 1
                self.attach(words, c, self.script_operand(st))
                continue
            out = self.atom(st)
            if isinstance(out, dict):
                st = out
                continue
            for node in out:
                if node[0] == 'sc':
                    self.attach(words, node[1], node[2])
                elif node[0] != 'inf':
                    words[0].append(node)
        return ('row', words[0])

    def script_operand(self, st):
        self.skip_ws()
        if self.i >= len(self.s):
            self.warn('missing script operand')
            return EMPTY
        return self.word(st, ends=SCRIPT_END)

    # ---- one lexical item ------------------------------------------------------------------------------------------
    def atom(self, st):
        """Next token -> list of nodes, or a new style dict for rm / it / bold / scale."""
        s, c = self.s, self.s[self.i]
        if c == '{':
            return [self.group(st)]
        if c == '"':
            j = s.find('"', self.i + 1)
            j = len(s) if j < 0 else j
            text = s[self.i + 1:j]
            self.i = min(j + 1, len(s))
            return [txt(ch, st) if ch != ' ' else ('sp', 0.5) for ch in text]
        if c == '#':
            self.i += 1
            return [('br',)]
        if c == '&':
            self.i += 1
            return [('tab',)]
        if c == '~':
            self.i += 1
            return [('sp', 1.0)]
        if c == '`':
            self.i += 1
            return [('sp', 0.25)]
        m = NUMBER.match(s, self.i)
        if m:
            self.i = m.end()
            return [txt(m.group(), dict(st, rm=True))]
        m = LETTERS.match(s, self.i)
        if m:
            if self.i and s[self.i - 1].isascii() and s[self.i - 1].isalpha():      # inside a run: a plain letter (E01)
                self.i += 1
                return [txt(s[self.i - 1], st)]
            return self.letters(m.group(), st)
        for op in MULTI:
            if s.startswith(op, self.i):
                self.i += len(op)
                return [txt(sy.SYMBOLS.get(op, op), dict(st, rm=True))]
        self.i += 1
        return [txt(SINGLE.get(c, c), dict(st, rm=True))]

    def letters(self, run, st):
        """A run of Latin letters: a keyword, a function name followed by letters, or single italic letters."""
        low = run.lower()
        if run in sy.FUNCTIONS or low in sy.BIGOPS or low in sy.STRUCT or sy.symbol(run):
            self.i += len(run)
            return self.keyword(run, st)
        for f in FUNC_PREFIX:                           # logx -> log x
            if run.startswith(f):
                self.i += len(f)
                return [txt(f, dict(st, rm=True))]
        self.i += 1
        return [txt(run[0], st)]

    # ---- keywords --------------------------------------------------------------------------------------------------
    def keyword(self, name, st):
        low = name.lower()
        if low == 'lim':
            return [('big', name, True, True)]
        if name in sy.FUNCTIONS:
            return [txt(name, dict(st, rm=True))]
        if low in sy.BIGOPS:
            g, lim = sy.BIGOPS[low]
            return [('big', g, lim, False)]
        if low in sy.UNSUPPORTED:
            self.unsup.append(name.upper())
            return [('unsup', name.upper())]
        if low in INFIX:
            return [('inf', low)]
        if low in ('sub', 'sup', 'from', 'to'):
            return [('sc', '_' if low in ('sub', 'from') else '^', self.word(st, ends=SCRIPT_END))]
        if low in ('rm', 'it', 'bold', 'rmbold'):
            return dict(st, rm=low in ('rm', 'rmbold') or (st['rm'] and low == 'bold'),
                        bold=low in ('bold', 'rmbold') or (st['bold'] and low == 'rm'))
        if low == 'scale':
            self.skip_ws()
            m = NUMBER.match(self.s, self.i)
            if not m:
                self.warn('scale needs a number')
                return dict(st)
            self.i = m.end()
            return dict(st, scale=float(m.group()))
        if low == 'sqrt':
            return [('sqrt', self.word(st), None)]
        if low == 'root':
            idx = self.word(st)
            self.skip_ws()
            if self.at_word('of'):
                self.i += 2
            else:
                self.warn('root without of')
            return [('sqrt', self.word(st), idx)]
        if low in sy.ACCENTS:
            return [('acc', low, self.word(st))]
        if low == 'not':
            return [('not', self.word(st))]
        if low == 'bigg':
            return [('bigg', self.word(st))]
        if low == 'binom':
            return [('binom', self.word(st), self.word(st))]
        if low == 'rel':
            return [('rel', self.word(st), self.word(st), self.word(st))]
        if low == 'buildrel':
            return [('rel', self.word(st), self.word(st), None)]
        if low == 'color':
            rgb, body = self.word(st), self.word(st)
            return [('color', rgb, body)]
        if low == 'left':
            return [self.lr(st)]
        if low == 'right':
            self.warn('right without left')
            self.bracket()
            return []
        if low in GRID_KINDS or low in ('cases', 'pile', 'lpile', 'rpile', 'eqalign', 'ladder', 'sladder'):
            rows, aligns = self.grid(st)
            return [('grid', low, rows, aligns)]
        if low == 'longdiv':                              # longdiv{divisor}{quotient}{dividend # row # row ...}
            dv, q = self.word(st), self.word(st)
            return [('longdiv', dv, q, self.grid(st)[0])]
        if low == 'phantom':
            return [('phantom', self.word(st))]
        if low in ('col', 'lcol', 'rcol'):                # a column of a matrix: col{a # b}
            return [('colspec', low, self.word(st))]
        if low == 'of':
            return []
        g = sy.symbol(name)
        if g:
            return [txt(g, dict(st, rm=True))]
        return [txt(name, st)]

    def bracket(self):
        self.skip_ws()
        if self.i >= len(self.s):
            return ''
        m = LETTERS.match(self.s, self.i)
        if m and m.group() in sy.BRACKETS:
            self.i = m.end()
            return sy.BRACKETS[m.group()]
        ch = self.s[self.i]
        self.i += 1
        return sy.BRACKETS.get(ch, ch)

    def lr(self, st):
        op = self.bracket()
        body = self.seq(st, stop_right=True)
        cl = ''
        if self.at_word('right'):
            self.i += 5
            cl = self.bracket()
        else:
            self.warn('left without right')
        return ('lr', op, cl, body)

    def grid(self, st):
        """`{ a & b # c & d }` -> rows of cells (each cell a row node)."""
        self.skip_ws()
        if self.i >= len(self.s) or self.s[self.i] != '{':
            self.warn('missing { after matrix or cases')
            return [], None
        row = self.group(st)
        specs = [n for n in row[1] if n[0] == 'colspec']
        if specs:                                           # matrix{ col{a#b} lcol{c#d} }: one group per column
            cols = []
            for n in specs:
                cells, cur = [], []
                for m in n[2][1]:
                    if m[0] == 'br':
                        cells.append(('row', cur))
                        cur = []
                    elif m[0] != 'tab':
                        cur.append(m)
                cells.append(('row', cur))
                cols.append(cells)
            nrow = max(len(c) for c in cols)
            rows = [[c[r] if r < len(c) else EMPTY for c in cols] for r in range(nrow)]
            return rows, [{'col': 'center', 'lcol': 'left', 'rcol': 'right'}[n[1]] for n in specs]
        rows, cells, cur = [], [], []
        for n in row[1]:
            if n[0] == 'br':
                cells.append(('row', cur))
                rows.append(cells)
                cells, cur = [], []
            elif n[0] == 'tab':
                cells.append(('row', cur))
                cur = []
            else:
                cur.append(n)
        cells.append(('row', cur))
        rows.append(cells)
        return rows, None


def parse(script):
    """Script text -> (tree, warnings, unsupported words). The tree is ('row', [...])."""
    p = Parser(script)
    tree = p.seq(dict(BASE_STYLE))
    return tree, p.warns, p.unsup
