"""`python scripts/pv.py calc "<expr>"`: a small safe expression language. No eval, no attribute access, no names except the functions below.

  numbers 12  3.5 | strings "text" | dates 2026-11-16 | tags ⟪주민번호1⟫ (the value comes from the vault) | ( ) | + - * / | < <= > >= == !=
  age(rrn, at)   exact age on a date        sex(rrn)   '남' / '여'        same(tag, tag)   do two tags hold the same value        count(a, b ...)

Comparison and arithmetic take numbers only: a value of the vault is text, and comparing it with a guess would read it digit by digit.
The value goes back as: a yes / no as it is (one bit); count of at least 5 values as it is; everything else as a new tag `⟪계산n⟫` (shown only as a
tag; use it in a writing command and the resolver puts the real result in).
"""
import datetime
import re

from . import validators as V

TOKEN = re.compile(r'\s*(?:(⟪[^⟫]+⟫)|(\d{4}-\d{2}-\d{2})|(\d+(?:\.\d+)?)|"([^"]*)"|([A-Za-z_]\w*)|(<=|>=|==|!=|[-+*/(),<>]))')


class CalcError(Exception):
    pass


class Raw(str):
    """A value of the vault (text) that remembers its kind."""
    kind = ''


def tokens(src):
    out, pos = [], 0
    while pos < len(src):
        if not src[pos:].strip():
            break
        m = TOKEN.match(src, pos)
        if not m:
            raise CalcError(f'cannot read the expression at character {pos + 1}')
        pos = m.end()
        tag, date, num, s, ident, op = m.groups()
        out.append(('tag', tag) if tag else ('date', date) if date else ('num', num) if num else ('str', s) if s is not None else
                   ('id', ident) if ident else ('op', op))
    return out


def _date(v):
    d = V.parse_date(str(v))
    if not d:
        raise CalcError('not a date')
    return d


def _rrn(v):
    d = V.digits(str(v))
    x = V.rrn_date(d)
    if not x:
        raise CalcError('not a registration number')
    return x


def f_age(rrn, at):
    y, m, d, _ = _rrn(rrn)
    a = _date(at)
    return a.year - y - ((a.month, a.day) < (m, d))


def f_same(a, b):
    """True when two tags hold the same value (both must be tags: a guess written into the expression would be an oracle)."""
    if not (isinstance(a, Raw) and isinstance(b, Raw)):
        raise CalcError('same() compares two tags')
    return V.digits(a) == V.digits(b) if V.digits(a) and V.digits(b) else str(a) == str(b)


FUNCS = {
    'age': f_age,
    'sex': lambda r: '남' if _rrn(r)[3] % 2 else '여',
    'same': f_same,
    'count': lambda *a: len(a),
}
AGG = {'count'}


class Parser:
    def __init__(self, toks, resolve):
        self.t, self.i, self.resolve = toks, 0, resolve
        self.agg = None

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, kind=None, val=None):
        k, v = self.peek()
        if k is None or (kind and k != kind) or (val and v != val):
            raise CalcError(f'expected {val or kind}')
        self.i += 1
        return v

    def expr(self):
        a = self.add()
        k, v = self.peek()
        if k == 'op' and v in ('<', '<=', '>', '>=', '==', '!='):
            self.i += 1
            b = self.add()
            a, b = _num(a), _num(b)
            return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '==': a == b, '!=': a != b}[v]
        return a

    def add(self):
        a = self.mul()
        while self.peek() in (('op', '+'), ('op', '-')):
            op = self.eat()
            b = self.mul()
            a = _num(a) + _num(b) if op == '+' else _num(a) - _num(b)
        return a

    def mul(self):
        a = self.prim()
        while self.peek() in (('op', '*'), ('op', '/')):
            op = self.eat()
            b = self.prim()
            a = _num(a) * _num(b) if op == '*' else _num(a) / _num(b)
        return a

    def prim(self):
        k, v = self.peek()
        if k == 'num':
            self.i += 1
            return float(v) if '.' in v else int(v)
        if k in ('str', 'date'):
            self.i += 1
            return v
        if k == 'tag':
            self.i += 1
            return self.resolve(v)
        if k == 'op' and v == '(':
            self.i += 1
            r = self.expr()
            self.eat('op', ')')
            return r
        if k == 'op' and v == '-':
            self.i += 1
            return -_num(self.prim())
        if k == 'id':
            self.i += 1
            if v not in FUNCS:
                raise CalcError(f'unknown function {v} (known: {", ".join(sorted(FUNCS))})')
            self.eat('op', '(')
            args = []
            if self.peek() != ('op', ')'):
                args.append(self.expr())
                while self.peek() == ('op', ','):
                    self.i += 1
                    args.append(self.expr())
            self.eat('op', ')')
            if v in AGG:
                self.agg = len(args)
            try:
                return FUNCS[v](*args)
            except TypeError:
                raise CalcError(f'wrong number of arguments for {v}')
        raise CalcError('unexpected end or symbol')


def _num(x):
    """Comparison and arithmetic take numbers only. A value of the vault is text: comparing it with a guess would be an oracle that reads the
    value digit by digit. Numbers come from age(), amount(), len(), count() and plain numbers in the expression."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return x
    raise CalcError('compare and calculate with numbers only: wrap a value in age(), amount(), len() or count()')


def evaluate(src, resolve):
    """(value, shown): shown is True when the value may be printed as it is."""
    p = Parser(tokens(src), resolve)
    v = p.expr()
    if p.i != len(p.t):
        raise CalcError('extra text after the expression')
    if isinstance(v, bool):
        return v, True
    if p.agg is not None and p.agg >= 5:
        return v, True
    return v, False
