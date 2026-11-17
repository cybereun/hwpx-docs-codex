"""교정 부호 (proofreading marks, C8.04): the run item `{"proof": kind, "text": text}` <-> a field `PROOFREADING_MARKS_<KIND>` around the text.

kind: "lineattach" (LINEATTACH, the mark sits at the start of the line, no text inside), "attach" (ATTACH), "delete" (DELETE),
"clipping" (CLIPPING). The field is `hp:ctrl/hp:fieldBegin type="PROOFREADING_MARKS_<KIND>" editable="0" dirty="1" zorder fieldid`
with `Prop` 0 and `Command` `$Revision<Kind>;`, then the text, then `hp:ctrl/hp:fieldEnd`. The key is `text` (not `t`): an item with
`t` is a plain text run for the builder. Reader: core.read (PROOF_FIELDS); builder: the run handler below (BLOCKS key `run.proof`).
Rules OB18.
"""
from ..core.units import esc

# kind -> (field type suffix, command name, fieldid)
KINDS = {'lineattach': ('LINEATTACH', 'LineAttach', 623192641), 'attach': ('ATTACH', 'Attach', 623192673),
         'delete': ('DELETE', 'Delete', 623192676), 'clipping': ('CLIPPING', 'Clipping', 623192643)}


def run(doc, piece, ctx):
    """Builder handler of the run item `proof`: the XML of one run."""
    if piece['proof'] not in KINDS:
        raise ValueError(f'unknown 교정 부호 kind {piece["proof"]!r}; one of {sorted(KINDS)}')
    typ, cmd, fid = KINDS[piece['proof']]
    doc.proofs = getattr(doc, 'proofs', 0) + 1
    oid = 1750000000 + doc.next_obj()
    text = piece.get('text', '')
    return (f'<hp:run charPrIDRef="{doc.head.char_pr(ctx)}"><hp:ctrl><hp:fieldBegin id="{oid}" type="PROOFREADING_MARKS_{typ}" name="" '
            f'editable="0" dirty="1" zorder="{doc.proofs}" fieldid="{fid}"><hp:parameters cnt="2" name=""><hp:integerParam name="Prop">0'
            f'</hp:integerParam><hp:stringParam name="Command">$Revision{cmd};</hp:stringParam></hp:parameters></hp:fieldBegin></hp:ctrl>'
            + (f'<hp:t>{esc(text)}</hp:t>' if text else '')
            + f'<hp:ctrl><hp:fieldEnd beginIDRef="{oid}" fieldid="{fid}"/></hp:ctrl><hp:t/></hp:run>')


def prepare(node, pic_dir=None):
    """Preview: the run item `proof` becomes `{"proofmark": {"kind", "text"}}`, which the drawer below draws (the text and the mark)."""
    if isinstance(node, list):
        for x in node:
            prepare(x)
    elif isinstance(node, dict):
        kind = node.get('proof')
        if isinstance(kind, str) and 'text' in node:
            node.pop('proof')
            node['proofmark'] = {'kind': kind, 'text': node.pop('text')}
        for v in node.values():
            if isinstance(v, (list, dict)):
                prepare(v)


# ---- the marks as Hangul draws them (render of proof_marks.hwpx at 500 dpi, 10 pt text: 1 em = 69.5 px) ------------------------
# Coordinates in em, x from the left edge of the marked text (X0) or its right edge (X1), y from the middle of the glyphs (YC =
# 0.42 em above the baseline). Red, 0.058 em wide, round ends.
RED = '#FF0000'
STROKE = 0.058


def mark_paths(kind, x0, x1, yc, em):
    """SVG path data (mm) of the mark `kind` around a text from x0 to x1 (mm) whose glyph middle is at yc; em = font size in mm."""
    def P(x, y, right=False):
        return f'{(x1 if right else x0) + x * em:.3f},{yc + y * em:.3f}'
    if kind == 'lineattach':                       # a hook in front of the line that runs down to the next line
        return [f'M{P(-0.547, -0.532)} Q{P(-0.317, -0.273)} {P(0, -0.245)}',
                f'M{P(0, 0.115)} C{P(-0.317, 0.115)} {P(-0.46, 0.245)} {P(-0.46, 0.504)} L{P(-0.518, 1.007)}']
    if kind == 'attach':                           # a bracket under the text
        return [f'M{P(0.33, 0.46)} L{P(0.33, 0.69)} Q{P(0.33, 0.835)} {P(0.475, 0.835)} L{P(-0.475, 0.835, True)} '
                f'Q{P(-0.33, 0.835, True)} {P(-0.33, 0.69, True)} L{P(-0.33, 0.46, True)}']
    if kind == 'delete':                           # two lines through the text
        return [f'M{P(0, -0.13)} L{P(0.14, -0.13, True)}', f'M{P(0, 0.07)} L{P(0.14, 0.07, True)}']
    if kind == 'clipping':                         # a rounded box with a curl at its top right corner
        r = 0.26
        return [f'M{P(-0.03 + r, -0.475)} L{P(0.14 - r, -0.475, True)} Q{P(0.14, -0.475, True)} {P(0.14, -0.475 + r, True)} '
                f'L{P(0.14, 0.575 - r, True)} Q{P(0.14, 0.575, True)} {P(0.14 - r, 0.575, True)} L{P(-0.03 + r, 0.575)} '
                f'Q{P(-0.03, 0.575)} {P(-0.03, 0.575 - r)} L{P(-0.03, -0.475 + r)} Q{P(-0.03, -0.475)} {P(-0.03 + r, -0.475)}',
                f'M{P(0.18, -0.26, True)} C{P(0.30, -0.30, True)} {P(0.34, -0.44, True)} {P(0.26, -0.46, True)} '
                f'C{P(0.18, -0.48, True)} {P(0.20, -0.34, True)} {P(0.34, -0.38, True)} '
                f'C{P(0.44, -0.42, True)} {P(0.50, -0.55, True)} {P(0.43, -0.58, True)} '
                f'C{P(0.36, -0.60, True)} {P(0.37, -0.48, True)} {P(0.50, -0.52, True)} '
                f'C{P(0.55, -0.54, True)} {P(0.60, -0.62, True)} {P(0.66, -0.66, True)}']
    return []


def mark(item, st):
    """Drawer of `proofmark` (preview): the text with the mark, as an object on the line (fn(item, style) of preview/drawers)."""
    import html
    from ..preview.measure import BASE, PT, cwidth, eff_size, fam, face
    ch = item.get('text', '')
    em = eff_size(st, 0) * PT
    ws = [cwidth(c, st) * PT for c in ch]
    w = sum(ws)
    h, base = em, BASE * em                      # the object is as high as the font size; the baseline sits at 0.85 of it
    bold = ' font-weight="bold"' if st.get('bold') else ''

    def draw(x, y):
        out = []
        if ch:
            xs, cx = [], x
            for k in ws:
                xs.append(f'{cx:.3f}')
                cx += k
            out.append(f'<text x="{" ".join(xs)}" y="{y + base:.3f}" font-family="{html.escape(fam(face(st, 0)), quote=True)}" '
                       f'font-size="{em:.3f}" fill="{st["color"]}"{bold}>{html.escape(ch, quote=False)}</text>')
        yc = y + base - 0.42 * em
        for d in mark_paths(item.get('kind'), x, x + w, yc, em):
            out.append(f'<path d="{d}" fill="none" stroke="{RED}" stroke-width="{STROKE * em:.3f}" stroke-linecap="round" stroke-linejoin="round"/>')
        return out
    return {'w': w, 'h': h, 'draw': draw, 'base': base}
