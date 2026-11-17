"""Make the pagex samples with Hangul COM (Hangul 2024). Needs Windows, Hangul and pywin32. Run only in an agreed Hangul window.

  python -m hwpx_docs.pagex.make_samples list
  python -m hwpx_docs.pagex.make_samples run [name ...] [--out DIR] [--png DIR]

One hidden Hangul for the whole batch (new documents and SaveAs only, no file is opened, so no access prompt), Quit at the end.
A group baseline `<group>_A.hwpx` and one `<name>_B.hwpx` per variant go to `fixtures/` (or --out); `creator` and `lastsaveby`
are set to `hwpx-docs`. With --png DIR the Hangul page images are written as `<name>_p<N>.png` (not committed).
Rules: rules.md. Texts are generic.
"""
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


# ---- COM helpers (h = render.hwpcom.Hwp) ---------------------------------------------------------------------------
def pages3(h):
    h.text('첫째 쪽')
    h.run('BreakPage')
    h.text('둘째 쪽')
    h.run('BreakPage')
    h.text('셋째 쪽')


def hf(h, kind, text, typ=0):
    """Header/footer: `typ` is the typed property `type` of HHeaderFooter (0 both, 1 even, 2 odd)."""
    hw = h.hwp
    p = hw.HParameterSet.HHeaderFooter
    hw.HAction.GetDefault('HeaderFooter', p.HSet)
    p.HSet.SetItem('HeaderFooterStyle', 0)
    p.HSet.SetItem('HeaderFooterCtrlType', 0 if kind == 'header' else 1)
    p.type = typ
    h.guard()
    hw.HAction.Execute('HeaderFooter', p.HSet)
    h.text(text)
    h.run('CloseEx')


def master(h, typ, text, front=False, **kw):
    hw = h.hwp
    p = hw.HParameterSet.HMasterPage
    hw.HAction.GetDefault('MasterPage', p.HSet)
    p.type = typ
    for k, v in kw.items():
        setattr(p, k, v)
    h.guard()
    hw.HAction.Execute('MasterPage', p.HSet)
    h.text(text)
    if front:
        h.run('MasterPageFront')                  # the set item `Front` has no effect; the action does (PX03)
    h.run('CloseEx')


def sec(h, **items):
    """PageSetup with HSecDef items (dots reach sub sets: 'FootnoteShape.NumberFormat')."""
    return h.act('PageSetup', 'HSecDef', **items)


def with_note(h):
    h.text('각주 본문')
    h.run('InsertFootnote')
    h.text('각주 내용')
    h.run('CloseEx')
    h.run('MoveDocEnd')
    h.run('BreakPara')
    h.text('미주 본문')
    h.run('InsertEndnote')
    h.text('미주 내용')
    h.run('CloseEx')
    h.run('MoveDocEnd')


def hide(h, fields):
    hf(h, 'header', '머리말')
    hf(h, 'footer', '꼬리말')
    h.act('PageNumPos', 'HPageNumPos', DrawPos=h.hwp.PageNumPosition('BottomCenter'), NumberFormat=h.hwp.NumberFormat('Digit'),
          SideChar=ord('-'))
    h.text('첫째 쪽')
    h.run('BreakPage')
    h.text('둘째 쪽')
    if fields:
        p = h.hwp.HParameterSet.HPageHiding
        h.hwp.HAction.GetDefault('PageHiding', p.HSet)
        p.Fields = fields
        h.hwp.HAction.Execute('PageHiding', p.HSet)
    h.run('BreakPage')
    h.text('셋째 쪽')


def cols_mid(h, to=None):
    """Column change inside a page: `BreakColDef` starts a new column definition in a new paragraph (a second colPr);
    `MultiColumn` with ApplyTo 2 then sets its count (ApplyTo 5 sets the section's own, 0/1/3/4 fail)."""
    h.text('앞쪽 한 단 본문')
    h.run('BreakPara')
    h.run('BreakColDef')
    if to is not None:
        hw = h.hwp
        p = hw.HParameterSet.HColDef
        hw.HAction.GetDefault('MultiColumn', p.HSet)
        p.Count = 2
        p.SameSize = 1
        p.SameGap = h.mm(8)
        p.type = 0
        p.HSet.SetItem('ApplyClass', 832)
        p.HSet.SetItem('ApplyTo', to)
        hw.HAction.Execute('MultiColumn', p.HSet)
    h.text('뒤쪽 본문 가나다라마바사 ' * 30)


def label(h, cols=2, rows=5):
    """`LabelTemplate` makes a locked table (rows x cols) at the page origin; `LabelAdd` returns False (PX11)."""
    hw = h.hwp
    p = hw.HParameterSet.HLabel
    hw.HAction.GetDefault('LabelTemplate', p.HSet)
    p.PageWidth, p.PageLen, p.Landscape = h.mm(210), h.mm(297), 0
    p.LeftMargin, p.TopMargin = h.mm(5), h.mm(10)
    p.BoxWidth, p.BoxLength = h.mm(100), h.mm(50)
    p.LabelCols, p.LabelRows, p.PageCnt = cols, rows, 1
    h.guard()
    hw.HAction.Execute('LabelTemplate', p.HSet)
    h.text('라벨 첫 칸')


def body(h, text='본문 가나다라마바사 ' * 12):
    h.text(text)


FN = lambda **kw: (lambda h: (with_note(h), sec(h, **{f'FootnoteShape.{k}': v for k, v in kw.items()})))      # noqa: E731
EN = lambda **kw: (lambda h: (with_note(h), sec(h, **{f'EndnoteShape.{k}': v for k, v in kw.items()})))       # noqa: E731

# group -> (baseline function, {variant name: function})
GROUPS = {
    'pg_hf': (pages3, {
        'hf_odd': lambda h: (hf(h, 'header', '홀수쪽 머리말', 2), pages3(h)),
        'hf_even': lambda h: (hf(h, 'header', '짝수쪽 머리말', 1), pages3(h)),
        'hf_oddeven': lambda h: (hf(h, 'header', '홀수쪽 머리말', 2), hf(h, 'header', '짝수쪽 머리말', 1),
                                 hf(h, 'footer', '홀수쪽 꼬리말', 2), hf(h, 'footer', '짝수쪽 꼬리말', 1), pages3(h)),
    }),
    'pg_master': (pages3, {
        'master_both': lambda h: (master(h, 0, '바탕쪽 양쪽'), pages3(h)),
        'master_com1': lambda h: (master(h, 1, '바탕쪽 COM1'), pages3(h)),
        'master_com2': lambda h: (master(h, 2, '바탕쪽 COM2'), pages3(h)),
        'master_com3': lambda h: (master(h, 3, '바탕쪽 COM3'), pages3(h)),
        'master_com4': lambda h: (master(h, 4, '바탕쪽 COM4'), pages3(h)),
        'master_three': lambda h: (master(h, 0, '양쪽'), master(h, 1, 'COM1'), master(h, 2, 'COM2'), pages3(h)),
        'master_front': lambda h: (master(h, 0, '앞으로', front=True), pages3(h)),
    }),
    'pg_note': (lambda h: with_note(h), {
        'note_digit_circled': FN(NumberFormat=1), 'note_digit_roman': FN(NumberFormat=2),
        'note_fix': FN(PrefixChar=ord('['), Suffix=ord(']')), 'note_super_off': FN(SuperScript=0),
        'note_start': FN(NewNumber=3), 'note_restart1': FN(Restart=1), 'note_restart2': FN(Restart=2),
        'note_place1': FN(PlaceAt=1), 'note_place2': FN(PlaceAt=2), 'note_beneath': FN(BeneathText=1),
        'note_line_type': FN(LineType=2), 'note_line_width': FN(LineWidth=3), 'note_line_len': FN(LineLength=0),
        'note_space': FN(SpaceAboveLine=400, SpaceBelowLine=300, SpaceBetweenNotes=200),
        'end_digit_roman': EN(NumberFormat=2), 'end_place1': EN(PlaceAt=1), 'end_restart': EN(Restart=1),
    }),
    'pg_hide': (lambda h: hide(h, 0), {f'hide_{n}': (lambda f: lambda h: hide(h, f))(f)
                                       for n, f in (('header', 1), ('footer', 2), ('master', 4), ('border', 8), ('fill', 16),
                                                    ('pagenum', 32), ('all', 63))}),
    'pg_cols': (lambda h: cols_mid(h), {'cols_mid': lambda h: cols_mid(h, 2), 'cols_sec': lambda h: cols_mid(h, 5)}),
    'pg_sec': (body, {
        'vertical': lambda h: (body(h), sec(h, TextDirection=1)),
        'vertical_head': lambda h: (body(h), sec(h, TextDirection=1, TextVerticalWidthHead=1)),
        'linenum': lambda h: (body(h), sec(h, ShowLineNumbers=1, LineNumberCountBy=1, LineNumberDistance=h.mm(10),
                                           LineNumberStart=1, LineNumberRestart=0)),
        'linenum_b': lambda h: (body(h), sec(h, ShowLineNumbers=1, LineNumberCountBy=5, LineNumberDistance=h.mm(5),
                                             LineNumberStart=3, LineNumberRestart=1)),
        'linenum_c': lambda h: (body(h), sec(h, ShowLineNumbers=1, LineNumberCountBy=1, LineNumberDistance=h.mm(10),
                                             LineNumberStart=1, LineNumberRestart=2)),
        'wonggoji': lambda h: (body(h), sec(h, WongojiFormat=1)),
        'wonggoji_grid': lambda h: (body(h), sec(h, WongojiFormat=1, CharGrid=h.mm(8), LineGrid=h.mm(8))),
    }),
    'pg_label': (lambda h: h.text('빈 문서'), {'label': label, 'label_3x8': lambda h: label(h, 3, 8)}),
}


def anonymize(path):
    """creator / lastsaveby -> hwpx-docs (a Hangul file has the user name there)."""
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, 'w') as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == 'Contents/content.hpf':
                data = re.sub(rb'(name="(?:creator|lastsaveby)" content="text">)[^<]*', rb'\g<1>hwpx-docs', data)
            zo.writestr(it, data, compress_type=it.compress_type)
    shutil.move(tmp, path)


def run(names, out, png=None):
    from ..render.hwpcom import Hwp
    from ..render import img
    todo = []                                   # (file stem, function)
    for g, (base, variants) in GROUPS.items():
        picked = [n for n in variants if not names or n in names or g in names]
        if picked:
            todo.append((f'{g}_A', base))
            todo += [(f'{n}_B', variants[n]) for n in picked]
    os.makedirs(out, exist_ok=True)
    print(f'HANGUL BATCH (pagex): {len(todo)} files, new documents, one Hangul, hidden', flush=True)
    with Hwp() as h:
        h.hwp.XHwpWindows.Item(0).Visible = False
        for stem, fn in todo:
            h.hwp.Clear(1)
            try:
                fn(h)
                path = os.path.join(out, stem + '.hwpx')
                ok = h.save(path)
                if ok or os.path.exists(path):
                    anonymize(path)
                if png:
                    os.makedirs(png, exist_ok=True)
                    for b in h.page_images(os.path.join(png, stem), fmt='bmp'):
                        if os.path.exists(b):
                            img.save_png(b[:-4] + '.png', img.load(b))
                            os.remove(b)
                print('SAMPLE', stem, 'OK' if ok else 'SAVE FAIL', 'pages', h.hwp.PageCount, flush=True)
            except Exception as e:                                   # one failed sample does not stop the batch
                print('SAMPLE', stem, 'ERR', repr(e)[:200], flush=True)
            if h.killed:
                print('HANGUL KILLED; stop')
                break


def main(argv):
    if not argv or argv[0] == 'list':
        for g, (_, v) in GROUPS.items():
            print(g, ' '.join(v))
        return 0
    out, png, names, i = os.path.join(HERE, 'fixtures'), None, [], 1
    while i < len(argv):
        if argv[i] == '--out':
            out, i = argv[i + 1], i + 1
        elif argv[i] == '--png':
            png, i = argv[i + 1], i + 1
        else:
            names.append(argv[i])
        i += 1
    run(names, out, png)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
