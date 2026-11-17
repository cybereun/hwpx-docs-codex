"""Self-test of the equation renderer (no Hangul, no Edge): script -> tree, tree -> sizes and SVG, the call from the preview.

  hd selftest                                          runs run() (through preview.selftest)
  python -m hwpx_docs.preview.equation.tests fidelity  sample pages against Hangul's pages (needs Edge and fixtures/ref)
"""
from ...core import tmpdir
import json
import os
import sys

from . import render
from .parse import parse

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, 'fixtures')


def samples():
    with open(os.path.join(FX, 'samples.json'), encoding='utf-8') as f:
        return json.load(f)


def flat(n):
    """Tree -> compact text, to compare structure."""
    t = n[0]
    if t == 'row':
        return ''.join(flat(x) for x in n[1])
    if t == 'txt':
        return n[1]
    if t == 'frac':
        return '(%s/%s)' % (flat(n[1]), flat(n[2]))
    if t == 'script':
        return '%s[_%s^%s]' % (flat(n[1]), flat(n[2]) if n[2] else '', flat(n[3]) if n[3] else '')
    if t == 'sqrt':
        return 'sqrt(%s%s)' % (flat(n[1]), ',' + flat(n[2]) if n[2] else '')
    if t == 'big':
        return '<%s>' % n[1]
    if t == 'lr':
        return 'LR%s%s(%s)' % (n[1], n[2], flat(n[3]))
    if t == 'grid':
        return '%s{%s}' % (n[1], ';'.join(','.join(flat(c) for c in r) for r in n[2]))
    if t == 'acc':
        return '%s(%s)' % (n[1], flat(n[2]))
    if t == 'sp':
        return '_' if n[1] >= 1 else "'"
    return t


def parse_test():
    cases = {
        '1 over 2': '(1/2)',
        'E=mc^2': 'E=mc[_^2]',
        'a_1^2': 'a[_1^2]',
        'x^2+1': 'x[_^2+1]',                                   # the operand runs to the next space (E02)
        'x^2 +1': 'x[_^2]+1',
        'a+b over c': '(a+b/c)',                               # an infix command takes the word before and after (E03)
        'a + b over c': 'a+(b/c)',
        '{a+b} over {c}': '(a+b/c)',
        'sqrt{x^2 +1}': 'sqrt(x[_^2]+1)',
        'root 3 of x': 'sqrt(x,3)',
        'int _1 ^2 {3x^2}dx': '<∫>[_1^2]3x[_^2]dx',            # a script attaches across a space (E02)
        'int from 0 to 3 x': '<∫>[_0^3]x',
        'sum_{n=1}^N 1 over n': '<∑>[_n=1^N](1/n)',
        'LEFT( a over b RIGHT)': 'LR()((a/b))',
        'logx+sinx': 'logx+sinx',
        'a~b': 'a_b',
        'pmatrix{a & b # c & d}': 'pmatrix{a,b;c,d}',
        'cases{x # y}': 'cases{x;y}',
        'bar x': 'bar(x)',
        'alpha beta': 'αβ',
    }
    for src, want in cases.items():
        tree, warns, unsup = parse(src)
        got = flat(tree)
        assert got == want, (src, got, want)
    assert flat(parse('LADDER{2&12#3&7&}')[0]) == 'ladder{2,12;3,7,}'
    assert flat(parse('pmatrix{col{a#b} rcol{c#d}}')[0]) == 'pmatrix{a,c;b,d}'
    assert parse('phantom{ab}')[0][1][0][0] == 'phantom'
    assert parse('LONGDIV{6}{422}{2532#24}')[0][1][0][0] == 'longdiv'
    assert flat(parse('rm ab it cd')[0]) == 'abcd'
    t = parse('rm ab it cd')[0][1]
    assert [n[2]['rm'] for n in t] == [True, True, False, False]
    print('EQUATION PARSE PASS', len(cases), 'cases')


def layout_test():
    e1 = render('1 over 2')
    e0 = render('1')
    assert e1.ok and e1.h > 1.6 * e0.h, (e1.h, e0.h)             # a fraction is about two lines high
    assert e1.svg.count('<line') == 1 and '<text' in e1.svg
    es = render('x^2')
    assert es.w > render('x').w and es.a > render('x').a        # a superscript widens and rises
    sm = render('sum_{k=1}^n k')
    assert sm.h > 2 * render('k').h * 0.9 and '∑' in sm.svg      # limits above and below
    assert render('E=mc^2', 14).w > render('E=mc^2', 10).w * 1.35      # width follows the size
    br = render('LEFT( 1 over 2 RIGHT)')
    assert br.ok and '<path' in br.svg and br.w > e1.w
    mt = render('bmatrix{1 & 2 # 3 & 4}')
    assert mt.ok and mt.svg.count('<text') >= 4
    ld = render('LADDER{2&12&28#2&6&14#3&7&}')
    assert ld.ok and ld.svg.count('<line') == 3, ld.svg.count('<line')            # two rungs and the vertical line through them
    dv = render('LONGDIV{6}{422}{2532#24#13#12#12#12#0}')
    assert dv.ok and dv.svg.count('<line') == 4 and '<path' in dv.svg       # the bar and three underlines, and the bracket
    assert render('LONGDIV{6}{422}{2532#24#~13#~12#~~12#~~12#~~~0}').svg == dv.svg       # blanks give the same layout
    ph = render('a phantom{bcd} e')
    assert ph.ok and ph.w > render('a e').w and ph.svg.count('<text') == 2     # room, but nothing drawn
    assert not render('{' * 4000 + 'x').ok                       # a failure: the caller shows the text and a warning
    for bad in ('', '{{{', '}}}', '^', '_2', 'sqrt', 'over', 'left', 'matrix', 'a over', '"unclosed'):
        e = render(bad)                                          # never raises
        assert isinstance(e.ok, bool)
    for s in samples():
        e = render(s['script'], s.get('size', 10))
        assert e.ok and e.w > 0 and e.h > 0 and e.svg, (s['name'], e.warns)
    print('EQUATION LAYOUT PASS', len(samples()), 'samples')


def hook_test():
    """The preview draws an equation run as vector shapes, and a script it cannot draw as text (with a warning)."""
    from ...core import build
    from .. import render_pages
    out = os.path.join(tmpdir.mkdtemp('hwpx_eq_t_'), 'e.hwpx')
    build.write({'body': [{'p': ['값 ', {'equation': {'script': 'a over b', 'size': 10}}, ' 끝']},
                          {'p': [{'equation': {'script': '{' * 4000 + 'QQ', 'size': 10}}]}]}, out)
    svg = render_pages(out)[0][2]
    assert '<g transform' in svg and '<line' in svg, 'equation drawn'
    assert 'QQ' in svg, 'fallback text'
    print('EQUATION HOOK PASS')


def fidelity_test():
    """Four samples against Hangul's pages (needs Edge): each must stay within 6 points of fixtures/fidelity.json."""
    from ...render import render as rr
    if not any(os.path.exists(p) for p in rr.EDGE):
        print('EQUATION FIDELITY SKIP (no Edge)')
        return
    with open(os.path.join(FX, 'fidelity.json'), encoding='utf-8') as f:
        want = json.load(f)
    quick = ('frac', 'func', 'integral', 'brackets')
    got = {n[3:]: d for n, d, c in fidelity(quick)}
    for n in quick:
        assert got[n] <= want[n]['ink'] + 6, (n, got[n], want[n])
    print('EQUATION FIDELITY PASS', {k: round(v, 1) for k, v in got.items()})


def run():
    parse_test()
    layout_test()
    hook_test()
    fidelity_test()


def fidelity(names=None):
    """Sample pages -> [(name, ink, coarse)] against fixtures/ref/<name>_page1.png (needs Edge)."""
    from ...render import img
    from .. import render_files
    out = tmpdir.mkdtemp('hwpx_eq_f_')
    rows = []
    for s in samples():
        n = 'eq_' + s['name']
        ref = os.path.join(FX, 'ref', n + '_page1.png')
        if (names and s['name'] not in names) or not os.path.exists(ref):
            continue
        render_files(os.path.join(FX, n + '.hwpx'), out, 96)
        own = os.path.join(out, n + '_p1.png')
        a, b = img.load(ref), img.load(own)
        rows.append((n, img.compare(a, b), img.compare(a, b, cell=12)))
    return rows


if __name__ == '__main__':
    if sys.argv[1:] == ['fidelity']:
        rows = fidelity()
        for n, d, c in rows:
            print('%-24s ink %.2f  coarse %.2f' % (n, d, c))
        if rows:
            print('mean ink %.2f coarse %.2f' % (sum(r[1] for r in rows) / len(rows), sum(r[2] for r in rows) / len(rows)))
    else:
        run()
