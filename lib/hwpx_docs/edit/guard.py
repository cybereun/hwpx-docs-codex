"""Checks after an edit of an existing HWPX: structure, text budget (page drift) and residue.

  hd guard <original.hwpx> <edited.hwpx> [--forbid WORD ...] [--require WORD ...] [--max-unchanged 0.35]
  hd guard --selftest

STRUCTURE  the same sections, paragraphs, tables (rows, columns), cell grid (address, span, size), drawing objects
           and header.xml (styles). An edit that changes them is no longer "the same form".
BUDGET     for each paragraph whose text changed: its line count before -> after in its own box (real font
           widths and the spec layout of core/textfit.py and core/layout.py). More lines make a row or the body grow:
           the pages after it move (page drift).
RESIDUE    forbidden words that are still there, required words that are missing, placeholders that are left
           (○○, {{...}}, XXX, ___), and the share of the original's long sentences (20+ characters) that are still
           in the edited text (with --max-unchanged, for a full rewrite).
Prints one GUARD line per finding and "GUARD OK" or "GUARD FAIL <n>" (exit code 1).
"""
from ..core import tmpdir
import os
import re
import sys
import zipfile

from ..core import layout, read, textfit

PLACEHOLDER = re.compile(r'○{2,}|\{\{[^}]*\}\}|XXX+|_{3,}')


def structure(path):
    """Fingerprint: per section the paragraph count, cell grid and object counts; plus header.xml."""
    out = []
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n))
        for n in names:
            x = z.read(n).decode('utf-8')
            grid = list(zip(re.findall(r'<hp:cellAddr\b[^>]*>', x), re.findall(r'<hp:cellSpan\b[^>]*>', x),
                            re.findall(r'<hp:cellSz\b[^>]*>', x)))
            out.append((n, x.count('<hp:p '), re.findall(r'<hp:tbl\b[^>]*?rowCnt="(\d+)"[^>]*?colCnt="(\d+)"', x),
                        grid,
                        sum(x.count(f'<hp:{o} ') for o in ('pic', 'rect', 'ellipse', 'line', 'container', 'ole',
                                                           'chart', 'equation'))))
        header = z.read('Contents/header.xml') if 'Contents/header.xml' in z.namelist() else b''
    return out, header


def texts(path):
    tmp = tmpdir.mkdtemp('hwpx_docs_g_')
    return layout.Layout(read.read(path, os.path.join(tmp, 's.json'))).paras


def report(original, edited, forbid=(), require=(), max_unchanged=None, out=print):
    fails = 0
    s1, h1 = structure(original)
    s2, h2 = structure(edited)
    same = s1 == s2
    if not same:
        fails += 1
        for a, b in zip(s1, s2):
            for what, i in (('paragraphs', 1), ('tables', 2), ('cell grid', 3), ('objects', 4)):
                if a[i] != b[i]:
                    out(f'GUARD STRUCTURE {a[0]}: {what} changed')
        if len(s1) != len(s2):
            out(f'GUARD STRUCTURE sections {len(s1)} -> {len(s2)}')
    if h1 != h2:
        out('GUARD STRUCTURE header.xml (styles) changed')
        fails += 1
    if same:
        out('GUARD STRUCTURE same paragraphs, tables, cell grid, objects')
    p1, p2 = texts(original), texts(edited)
    if same and len(p1) == len(p2):
        body_pt = 0.0
        for a, b in zip(p1, p2):
            if a.text == b.text:
                continue
            grow = len(b.lines) - len(a.lines)
            if grow > 0:
                size = b.props.get('size', 10)
                line = b.props.get('line', 160)
                pt = grow * size * (line if isinstance(line, (int, float)) else 160) / 100
                kind = 'row grows' if b.cell else 'body grows'
                out(f'GUARD BUDGET {b.where}: {len(a.lines)} -> {len(b.lines)} lines, {kind} by '
                    f'{pt * textfit.PT_MM:.1f} mm "{b.text.strip()[:30]}"')
                if not b.cell:
                    body_pt += pt
                fails += 1
        if body_pt:
            out(f'GUARD BUDGET body text {body_pt * textfit.PT_MM:.1f} mm longer: later pages can move')
    new_text = '\n'.join(p.text for p in p2)
    for w in forbid:
        if w in new_text:
            out(f'GUARD RESIDUE forbidden "{w}" x{new_text.count(w)}')
            fails += 1
    for w in require:
        if w not in new_text:
            out(f'GUARD RESIDUE required "{w}" missing')
            fails += 1
    for m in sorted(set(PLACEHOLDER.findall(new_text))):
        out(f'GUARD RESIDUE placeholder "{m}" left')
        fails += 1
    if max_unchanged is not None:
        old = [s.strip() for p in p1 for s in re.split(r'(?<=[.!?。])\s+|\n', p.text) if len(s.strip()) >= 20]
        kept = sum(1 for s in old if s in new_text)
        ratio = kept / len(old) if old else 0.0
        if ratio > max_unchanged:
            out(f'GUARD RESIDUE {kept} of {len(old)} long original sentences unchanged ({ratio:.0%} > '
                f'{max_unchanged:.0%})')
            fails += 1
    out('GUARD OK' if not fails else f'GUARD FAIL {fails}')
    return fails


def selftest():
    from ..core import build
    from . import edit
    d = tmpdir.mkdtemp('hwpx_docs_guard_')
    src = os.path.join(d, 'a.hwpx')
    build.write({'body': [{'table': {'cols': [30, 40], 'rows': [['성명', ''], ['비고', '○○○']]}},
                          '이 문단은 원래 문장으로 스무 글자를 넘게 쓴 문장입니다.']}, src)
    lines = []
    doc = edit.Doc(src)
    doc.fill({'성명': '가람 ' * 20})                      # far too long for a 40 mm cell
    dst = doc.save(os.path.join(d, 'b.hwpx'))
    fails = report(src, dst, forbid=['원래'], require=['없는말'], max_unchanged=0.3, out=lines.append)
    text = '\n'.join(lines)
    assert 'GUARD STRUCTURE same' in text and 'row grows' in text, text
    assert 'forbidden "원래"' in text and 'required "없는말"' in text and 'placeholder "○○○"' in text, text
    assert 'long original sentences unchanged' in text and fails == 5, (fails, text)
    lines = []
    assert report(src, src, out=lines.append) == 1 and 'placeholder' in lines[-2]      # only the ○○○ is left
    print('GUARD SELFTEST PASS')


def main(args):
    if args and args[0] == '--selftest':
        return selftest()

    def many(flag):
        return [args[i + 1] for i, a in enumerate(args) if a == flag]
    mx = float(args[args.index('--max-unchanged') + 1]) if '--max-unchanged' in args else None
    return 1 if report(args[0], args[1], many('--forbid'), many('--require'), mx) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
