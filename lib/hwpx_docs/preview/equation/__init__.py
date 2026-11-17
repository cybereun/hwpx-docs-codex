"""Hangul equation script -> drawing, for the page preview (no Hangul, no third-party program).

Public interface (one function):
  equation.render(script, size_pt=10.0, color='#000000', min_line=0.265) -> Eq
    Eq.w, Eq.h  size in mm        Eq.a  baseline distance from the top in mm (Eq.d = h - a)
    Eq.svg      SVG fragment in mm, origin at the top-left corner of the drawing (lines are at least `min_line` thick)
    Eq.ok       False when part of the script could not be drawn (unknown command, unmatched brace ...); the caller then
                writes the script as text and prints `Eq.warns`
    Eq.warns    list of messages
Files: symbols.py (command and symbol tables), parse.py (script -> tree), layout.py (tree -> boxes -> SVG), tests.py
(self-test and fidelity against Hangul pages), rules.md (E01-E20, grammar and measured metrics), coverage.md (commands drawn
and not drawn), fixtures/ (sample scripts, Hangul reference pages). A fix to equations touches this folder only.
Clean-room: grammar from the public Hangul help and the equation file-format document; shapes and metrics measured from
Hangul's own pages; no other renderer's code, identifiers or tables.
"""
from .layout import Ctx, lay, shift, to_svg
from .parse import parse

PT_MM = 25.4 / 72
TOP_GAP = 0.75          # em between the top of Hangul's line and the top of the equation (rules E18)


class Eq:
    __slots__ = ('w', 'h', 'a', 'd', 'svg', 'ok', 'warns')

    def __init__(self, w=0.0, a=0.0, d=0.0, svg='', ok=True, warns=None):
        self.w, self.a, self.d, self.h, self.svg, self.ok, self.warns = w, a, d, a + d, svg, ok, warns or []


def render(script, size_pt=10.0, color='#000000', min_line=0.265):
    """Equation script -> Eq (see the module text). Never raises: a failure gives ok=False and a warning."""
    try:
        tree, warns, unsup = parse(script or '')
        cx = Ctx(color)
        box = lay(tree, size_pt * PT_MM, cx)
        warns = warns + cx.warns + ['unsupported: ' + w for w in unsup]
        hard = bool(unsup) or any(w.startswith('not drawn') for w in cx.warns)
        svg = to_svg(shift(box.p, 0.0, box.a), min_line)
        return Eq(box.w, box.a, box.d, svg, ok=not hard, warns=warns)
    except Exception as e:                                    # a broken script must not stop the page
        return Eq(0.0, 0.0, 0.0, '', ok=False, warns=['equation error: %s' % e])


def selftest():
    from . import tests
    tests.run()
