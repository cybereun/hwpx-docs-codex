"""Is the edited .hwp still the same form? Compare the original and the edited file (rules HW15-HW18).

  hd hwp guard <original.hwp> <edited.hwp> [--forbid WORD ...] [--require WORD ...] [--max-unchanged 0.35]
               [--render out_dir] [--backend preview|hangul]

STRUCTURE  every stream but the sections, PrvText and PrvImage keeps its bytes (DocInfo: fonts, char / para shapes,
           borders, styles); in each section the record tree (tag, level) is the same once the text records of a
           paragraph (PARA_TEXT, PARA_CHAR_SHAPE, PARA_LINE_SEG, PARA_RANGE_TAG) are set aside; every other record
           keeps its bytes (tables, cells, sizes, objects, fields), PARA_HEADER except its counts; an edited paragraph
           keeps its controls (fields, objects) in order and uses only char shapes it had.
BUDGET     each paragraph whose text changed: lines before (Hangul's own layout cache) -> lines after (estimated with
           the real font widths, core.textfit, in the width Hangul used); more lines make a row or the body grow.
RESIDUE    forbidden words left, required words missing, placeholders left (○○, {{...}}, XXX, ___), share of the
           original long sentences still there (--max-unchanged).
RENDER     with --render: the pages before and after (render.compare): page count, and which pages changed where.
Prints one GUARD line per finding and "GUARD OK" or "GUARD FAIL <n>" (exit code 1).
"""
import re
import struct
import sys
from collections import Counter

from ..core import textfit
from . import docinfo, fmt

PLACEHOLDER = re.compile(r'○{2,}|\{\{[^}]*\}\}|XXX+|_{3,}')
TEXT_PARTS = set(fmt.PARA_PARTS)
FREE_STREAMS = {'PrvText', 'PrvImage'}
HU_MM = 25.4 / 7200


def skeleton(recs):
    return [(t, lvl) for t, lvl, _ in recs if t not in TEXT_PARTS]


def header_core(d):
    """PARA_HEADER without the fields an edit may change: char count (bit 31 kept), tab / line-break bits, counts."""
    b = bytearray(d)
    if len(b) >= 18:
        struct.pack_into('<I', b, 0, struct.unpack_from('<I', b, 0)[0] & 0x80000000)
        struct.pack_into('<I', b, 4, struct.unpack_from('<I', b, 4)[0] & ~((1 << fmt.TAB) | (1 << fmt.LINE_BREAK)))
        b[12:18] = bytes(6)
    return bytes(b)


def place(p):
    if p.kind == 'cell':
        c = p.cell
        return f'table {c["table"]} cell r{c["row"] + 1}c{c["col"] + 1}'
    return 'body paragraph' if p.kind == 'body' else 'other paragraph'


class Side:
    def __init__(self, path):
        self.pk = fmt.Package(path)
        self.secs = {s: self.pk.records(s) for s in self.pk.sections}
        self.paras = {s: fmt.paragraphs(r) for s, r in self.secs.items()}

    def texts(self):
        return [(s, p, fmt.read_units(self.secs[s], p)) for s in self.pk.sections for p in self.paras[s]]


def structure(a, b, out):
    fails = 0
    sa, sb = set(a.pk.streams), set(b.pk.streams)
    if sa != sb:
        out(f'GUARD STRUCTURE streams added {sorted(sb - sa)} removed {sorted(sa - sb)}')
        fails += 1
    for name in sorted(sa & sb):
        if name in FREE_STREAMS or name in a.secs:
            continue
        if a.pk.stream(name) != b.pk.stream(name):
            what = ' (fonts, char / para shapes, borders, styles)' if name == 'DocInfo' else ''
            out(f'GUARD STRUCTURE {name} changed{what}')
            fails += 1
    for s in a.pk.sections:
        ra, rb = a.secs[s], b.secs.get(s)
        if rb is None:
            continue
        if skeleton(ra) != skeleton(rb):
            out(f'GUARD STRUCTURE {s}: record tree changed (paragraphs, tables, cells or objects added or removed)')
            fails += 1
            continue
        xa = [r for r in ra if r[0] not in TEXT_PARTS]
        xb = [r for r in rb if r[0] not in TEXT_PARTS]
        kinds = Counter()
        for (t, _, da), (_, _, db) in zip(xa, xb):
            if t == fmt.T['PARA_HEADER']:
                if header_core(da) != header_core(db):
                    kinds['paragraph shape or style'] += 1
            elif da != db:
                kinds[{fmt.T['TABLE']: 'table', fmt.T['LIST_HEADER']: 'cell or list (size, span, margin, border)',
                       fmt.T['CTRL_HEADER']: 'control ' + fmt.ctrl_id(da).strip()}.get(t, 'object record 0x%X' % t)] += 1
        for k, n in kinds.items():
            out(f'GUARD STRUCTURE {s}: {k} changed x{n}')
            fails += 1
        for pa, pb in zip(a.paras[s], b.paras[s]):
            ua, ub = fmt.read_units(ra, pa), fmt.read_units(rb, pb)
            ca = [u[0] for u in ua.items if not ua.is_char(u) and ua.code(u[0]) not in (fmt.TAB, fmt.LINE_BREAK)]
            cb = [u[0] for u in ub.items if not ub.is_char(u) and ub.code(u[0]) not in (fmt.TAB, fmt.LINE_BREAK)]
            if ca != cb:
                out(f'GUARD STRUCTURE {s}: {place(pa)}: controls (fields, objects) changed')
                fails += 1
            new_shapes = {u[1] for u in ub.items} - {u[1] for u in ua.items}
            if new_shapes:
                out(f'GUARD STRUCTURE {s}: {place(pa)}: char shapes {sorted(new_shapes)} it did not use')
                fails += 1
    if not fails:
        out('GUARD STRUCTURE same streams, styles, record tree, tables, cells, objects and fields')
    return fails


def line_segs(recs, p):
    if fmt.T['PARA_LINE_SEG'] not in p.parts:
        return []
    d = recs[p.parts[fmt.T['PARA_LINE_SEG']]][2]
    return [struct.unpack_from('<IiiiiiiiI', d, k) for k in range(0, len(d) - 35, 36)]


def budget(a, b, out):
    """Paragraphs that changed: Hangul's lines before -> estimated lines after (same width, real fonts)."""
    fails, body_mm = 0, 0.0
    try:
        di = docinfo.DocInfo(a.pk)
    except Exception:                                # a DocInfo this reader does not know: no budget
        out('GUARD BUDGET skipped (DocInfo not read)')
        return 0
    for s in a.pk.sections:
        ra, rb = a.secs[s], b.secs.get(s)
        if rb is None or skeleton(ra) != skeleton(rb):
            continue
        for pa, pb in zip(a.paras[s], b.paras[s]):
            ua, ub = fmt.read_units(ra, pa), fmt.read_units(rb, pb)
            ta, tb = ua.text(), ub.text()
            if ta == tb:
                continue
            segs = line_segs(ra, pa)
            if not segs:
                continue
            width = max(x[7] for x in segs) * HU_MM
            shape = Counter(u[1] for u in ub.items).most_common(1)[0][0]
            cp = di.chars[shape] if shape < len(di.chars) else {}
            pp_id = struct.unpack_from('<H', rb[pb.head][2], 8)[0]
            pp = di.paras[pp_id] if pp_id < len(di.paras) else {}
            sp = cp.get('spacing', 0)
            blk = dict(font=cp.get('font', '함초롬바탕'), font_latin=cp.get('font_latin'), size=cp.get('size', 10),
                       bold=cp.get('bold', False), spacing=sp[0] if isinstance(sp, list) else sp,
                       word_break=pp.get('word_break', 'word'), latin_break=pp.get('latin_break', 'word'))
            n_old = len(segs)
            grow = 0
            for k, t in enumerate(tb.split('\n')):        # a line break starts a new line
                old_part = ta.split('\n')
                est_new = textfit.count_lines(dict(blk, p=t), width)
                est_old = textfit.count_lines(dict(blk, p=old_part[k]), width) if k < len(old_part) else 0
                grow += est_new - est_old
            grow -= max(0, len(ta.split('\n')) - len(tb.split('\n')))
            if grow > 0:
                step = sum(x[2] + x[5] for x in segs) / len(segs) * HU_MM
                kind = 'row grows' if pb.kind == 'cell' else 'body grows' if pb.kind == 'body' else 'box grows'
                out(f'GUARD BUDGET {s} {place(pb)}: {n_old} -> {n_old + grow} lines, {kind} by {grow * step:.1f} mm '
                    f'"{tb.strip()[:30]}"')
                if pb.kind == 'body':
                    body_mm += grow * step
                fails += 1
    if body_mm:
        out(f'GUARD BUDGET body text {body_mm:.1f} mm longer: later pages can move')
    return fails


def residue(a, b, forbid, require, max_unchanged, out):
    fails = 0
    old_text = '\n'.join(u.text() for _, _, u in a.texts())
    new_text = '\n'.join(u.text() for _, _, u in b.texts())
    for w in forbid:
        if w in new_text:
            out(f'GUARD RESIDUE forbidden "{w}" x{new_text.count(w)}')
            fails += 1
    if forbid:                                              # the other streams too (history, summary, field strings ...)
        from . import residue
        for w, where in residue.hits(b.pk, forbid).items():
            where = [x for x in where if not (x == 'PrvText' and w in new_text)]       # the preview is a copy of the body: said once
            if not where:
                continue
            out(f'GUARD RESIDUE forbidden "{w}" also in {", ".join(where[:4])}{" ..." if len(where) > 4 else ""} (not the body text)')
            fails += 1
        if residue.history(b.pk):
            out(f'GUARD NOTE the revision history ({", ".join(residue.history(b.pk))}) keeps old versions of the text')
    for w in require:
        if w not in new_text:
            out(f'GUARD RESIDUE required "{w}" missing')
            fails += 1
    for m in sorted(set(PLACEHOLDER.findall(new_text))):
        out(f'GUARD RESIDUE placeholder "{m}" left')
        fails += 1
    if max_unchanged is not None:
        old = [x.strip() for x in re.split(r'(?<=[.!?。])\s+|\n', old_text) if len(x.strip()) >= 20]
        kept = sum(1 for x in old if x in new_text)
        ratio = kept / len(old) if old else 0.0
        if ratio > max_unchanged:
            out(f'GUARD RESIDUE {kept} of {len(old)} long original sentences unchanged ({ratio:.0%} > {max_unchanged:.0%})')
            fails += 1
    return fails


def report(original, edited, forbid=(), require=(), max_unchanged=None, render_dir=None, backend='preview', out=print):
    a, b = Side(original), Side(edited)
    fails = structure(a, b, out)
    fails += budget(a, b, out)
    fails += residue(a, b, forbid, require, max_unchanged, out)
    if render_dir:
        from . import render
        fails += render.compare(original, edited, render_dir, backend=backend, out=out)
    out('GUARD OK' if not fails else f'GUARD FAIL {fails}')
    return fails


def main(args):
    def many(flag):
        return [args[i + 1] for i, x in enumerate(args) if x == flag]
    if len(args) < 2:
        print(__doc__)
        return 2
    mx = float(args[args.index('--max-unchanged') + 1]) if '--max-unchanged' in args else None
    rd = (many('--render') or [None])[0]
    be = (many('--backend') or ['preview'])[0]
    return 1 if report(args[0], args[1], many('--forbid'), many('--require'), mx, rd, be) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
