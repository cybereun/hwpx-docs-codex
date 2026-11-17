"""Make the Hangul samples of the table package (C5.06, C5.09, C5.10, C5.13, C5.17-C5.19). NEEDS HANGUL.

  hd table-samples window <out_dir>      one hidden Hangul, one batch, Quit at the end:
      lines     table with one cell per Hangul line type                      -> <out_dir>/lines.hwpx
      names     COM parameter-set item names (what FillAttr, TableProperties ... accept) -> printed
      actions   formula / caption / protect actions: which ones run            -> <out_dir>/act_<name>.hwpx
      grad      gradient and picture fill, several ways with COM               -> <out_dir>/fill_<n>.hwpx + "FILL <n> gradation|imgBrush|none"
      pos       floating table: one property at a time, from the base table    -> <out_dir>/pos_<name>.hwpx
      resave    hand-built tables (spec in BUILT below) opened in Hangul, drawn to PNG and saved again
                                                                              -> <out_dir>/built/<name>.hwpx, resaved/<name>.hwpx, png/
  hd table-samples build <out_dir>       only the hand-built files (no Hangul)
  hd table-samples fixtures <window_dir> copy the useful files of a window run into table/fixtures/ (creator -> hwpx-docs)
  hd table-samples window2 <out_dir>     second Hangul batch: formula, protect behaviour, gradient/picture by COM again, line type
                                         numbers, the hand-built files again (gradient angles), then the round trip (read ->
                                         build -> Hangul render, ink difference) of every fixture of this package

Hangul rules (RULES.md rule 7, rule 3 of the M3 brief): the window stays hidden, nothing is activated, Quit at the end;
the file-access prompt, if it comes, is answered by the user only ("모두 허용"). Run it in the window that the orchestrator
schedules, never in parallel with another Hangul user.
"""
import json
import os
import re
import sys
import zipfile

from ..core import build
from ..render import img

LANGS = ['Hangul', 'Latin', 'Hanja', 'Japanese', 'Other', 'Symbol', 'User']
COLOR = dict(L='BorderCorlorLeft', R='BorderColorRight', T='BorderColorTop', B='BorderColorBottom')   # Hangul's own spelling
LINE_NAMES = ['None', 'Solid', 'Dash', 'Dot', 'DashDot', 'DashDotDot', 'LongDash', 'Circle', 'Double', 'DoubleSlim',
              'SlimThick', 'ThickSlim', 'SlimThickSlim', 'ThinThick', 'ThickThin', 'ThinThickThin', 'Wave', 'DoubleWave',
              'Thick3D', 'ThickReverse3D', 'Slim3D', 'SlimReverse3D']

# hand-built tables for the resave job: the builder's guess of each form (model: Hancom OWPML), checked by Hangul
BUILT = {
    'fill_gradient': {'body': [{'table': {'cols': [40, 40, 40], 'heights': [20], 'rows': [[
        {'p': 'linear', 'fill': {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'colors': ['#FFFFFF', '#3366CC']}},
        {'p': 'radial', 'fill': {'type': 'gradient', 'kind': 'radial', 'center': [50, 50], 'colors': ['#FFFFFF', '#CC3333']}},
        {'p': 'square', 'fill': {'type': 'gradient', 'kind': 'square', 'center': [50, 50], 'colors': ['#FFFF00', '#006600']}}]]}}]},
    'fill_image': {'body': [{'table': {'cols': [60, 60], 'heights': [30], 'rows': [[
        {'p': 'tile', 'fill': {'type': 'image', 'src': 'fill.png', 'mode': 'tile'}},
        {'p': 'total', 'fill': {'type': 'image', 'src': 'fill.png', 'mode': 'total'}}]]}}]},
    'caption_bottom': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                           'caption': {'text': '아래 캡션'}}}]},
    'caption_top': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                        'caption': {'text': '위 캡션', 'side': 'top'}}}]},
    'caption_left': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                         'caption': {'text': '왼쪽', 'side': 'left', 'width': 20}}}]},
    'cell_protect': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [[
        {'p': '보호', 'protect': True}, '일반']]}}]},
    'pos_paper': {'body': ['본문 첫 줄', {'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                                  'pos': {'x': 60, 'y': 120, 'rel': 'paper'}}}]},
    'pos_page_right_bottom': {'body': ['본문 첫 줄', {'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                                              'pos': {'x': 0, 'y': 0, 'rel': 'page', 'halign': 'right',
                                                                      'valign': 'bottom'}}}]},
    'pos_square': {'body': ['본문 ' * 60, {'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']], 'wrap': 'square',
                                                   'pos': {'x': 0, 'y': 5, 'rel': 'para', 'hrel': 'column', 'halign': 'right',
                                                           'flow': True, 'overlap': False}}}]},
    'caption_right': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [['가', '나']],
                                          'caption': {'text': '오른쪽', 'side': 'right', 'width': 20}}}]},
    'cell_protect_control': {'body': [{'table': {'cols': [40, 40], 'heights': [10], 'rows': [['보호 아님', '일반']]}}]},
    # every line type at 1 mm, to look at wave and 3D lines at a high dpi (window 4)
    'lines_wide': {'body': [{'table': {'cols': [28] * 6, 'heights': [14] * 3, 'border': 'none', 'rows': [
        [{'p': t, 'border': f'1.0mm {t} #000000'} for t in row]
        for row in (('solid', 'dot', 'dash', 'dash_dot', 'dash_dot_dot', 'long_dash'),
                    ('circle', 'double', 'slim_thick', 'thick_slim', 'slim_thick_slim', 'wave'),
                    ('doublewave', 'thick3d', 'thickrev3d', '3d', 'rev3d', 'solid'))]}}]},
    'cell_formula': {'body': [{'table': {'cols': [30, 30], 'heights': [10, 10, 10, 10], 'rows': [
        ['10', '1'], ['20', '2'], ['30', '3'],
        [{'p': '60', 'formula': {'expr': '=SUM(?1:?3)', 'format': '%g,'}},
         {'p': '2.00', 'formula': {'expr': '=AVG(?1:?3)', 'format': '%.2f,'}}]]}}]},
    # gradient direction: what angle means (first colour red, last blue); window 2 renders it
    'fill_gradient_angles': {'body': [{'table': {'cols': [28] * 6, 'heights': [20, 20], 'rows': [
        [{'p': str(a), 'fill': {'type': 'gradient', 'kind': 'linear', 'angle': a, 'colors': ['#FF0000', '#0000FF']}}
         for a in (0, 45, 90, 135, 180, 270)],
        [{'p': 'conic', 'fill': {'type': 'gradient', 'kind': 'conical', 'center': [50, 50], 'colors': ['#FF0000', '#0000FF']}},
         {'p': 'r 0,0', 'fill': {'type': 'gradient', 'kind': 'radial', 'center': [0, 0], 'colors': ['#FF0000', '#0000FF']}},
         {'p': '3 col', 'fill': {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'colors': ['#FF0000', '#00FF00', '#0000FF']}},
         {'p': 'step 20', 'fill': {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'step': 20,
                                   'colors': ['#FF0000', '#0000FF']}},
         {'p': 'sc 80', 'fill': {'type': 'gradient', 'kind': 'linear', 'angle': 90, 'step_center': 80,
                                 'colors': ['#FF0000', '#0000FF']}},
         {'p': 'sq 25', 'fill': {'type': 'gradient', 'kind': 'square', 'center': [25, 25], 'colors': ['#FF0000', '#0000FF']}}]]}}]},
}


def fill_png(path):
    """A small generic gradient picture (blue to teal) for the picture-fill samples."""
    img.save_png(path, (24, 24, [b''.join(bytes([40 + 8 * x, 90 + 4 * y, 170]) for x in range(24)) for y in range(24)]))


def build_all(out_dir):
    """Build the BUILT specs into <out_dir>/built (no Hangul). Returns {name: path}."""
    d = os.path.join(out_dir, 'built')
    os.makedirs(d, exist_ok=True)
    fill_png(os.path.join(d, 'fill.png'))
    out = {}
    for name, spec in BUILT.items():
        out[name] = os.path.join(d, name + '.hwpx')
        build.write(spec, out[name], base=d)
    return out


# ---- COM helpers (hwp = the Hangul COM object, h = render.hwpcom.Hwp) -------------------------------------------
def make_table(h, widths, heights, **props):
    """Table at the cursor; widths/heights are OUTER mm (COM wants INNER: minus 1020 / 282 hu, rules T02)."""
    hw = h.hwp
    t = hw.HParameterSet.HTableCreation
    hw.HAction.GetDefault('TableCreate', t.HSet)
    t.Rows, t.Cols, t.WidthType, t.HeightType = len(heights), len(widths), 2, 1
    t.CreateItemArray('ColWidth', len(widths))
    for i, w in enumerate(widths):
        t.ColWidth.SetItem(i, h.mm(w) - 1020)
    t.CreateItemArray('RowHeight', len(heights))
    for i, v in enumerate(heights):
        t.RowHeight.SetItem(i, h.mm(v) - 282)
    bad = []
    for k, v in props.items():
        try:
            setattr(t.TableProperties, k, v)
        except Exception:
            bad.append(k)
    h.guard()
    hw.HAction.Execute('TableCreate', t.HSet)
    return bad


def goto(h, r, c):
    h.run('Cancel')
    h.run('TableColBegin')
    h.run('TableColPageUp')
    for _ in range(r):
        h.run('TableLowerCell')
    for _ in range(c):
        h.run('TableRightCell')


def cell_text(h, r, c, text):
    goto(h, r, c)
    h.text(text)


def leave_table(h):
    h.run('Cancel')
    h.hwp.MovePos(3, 0, 0)


def cell_lines(h, r, c, kind):
    """All four sides of a cell with line type `kind` (a name of hwp.HwpLineType), 0.4 mm."""
    hw = h.hwp
    goto(h, r, c)
    h.run('TableCellBlock')
    it = {}
    for side, name in dict(L='Left', R='Right', T='Top', B='Bottom').items():
        it['BorderType' + name] = hw.HwpLineType(kind)
        it['BorderWidth' + name] = hw.HwpLineWidth('0.4mm')
        it[COLOR[side]] = h.rgb('#000000')
    h.act('CellBorderFill', 'HCellBorderFill', **it)
    h.run('Cancel')


def names_of(obj):
    """Item names of a COM parameter set (type library); 'ERR ...' when Hangul gives none."""
    try:
        ti = obj._oleobj_.GetTypeInfo()
        ta = ti.GetTypeAttr()
        return sorted({ti.GetNames(ti.GetFuncDesc(i).memid)[0] for i in range(ta.cFuncs)})
    except Exception as e:
        return 'ERR ' + repr(e)[:100]


def xml_has(path, *needles):
    with zipfile.ZipFile(path) as z:
        t = ''.join(z.read(n).decode('utf-8') for n in z.namelist() if n.startswith('Contents/') and n.endswith('.xml'))
    return [n for n in needles if n in t]


# ---- the jobs -------------------------------------------------------------------------------------------------
def job_lines(h, out):
    ok = {}
    for n in LINE_NAMES:
        try:
            ok[n] = h.hwp.HwpLineType(n)
        except Exception:
            ok[n] = None
    print('LINETYPES', json.dumps(ok))
    good = [n for n in LINE_NAMES if ok[n] is not None]
    cols = 4
    h.hwp.Clear(1)
    make_table(h, [40] * cols, [12] * ((len(good) + cols - 1) // cols))
    for i, n in enumerate(good):
        cell_text(h, i // cols, i % cols, n)
    for i, n in enumerate(good):
        cell_lines(h, i // cols, i % cols, n)
    leave_table(h)
    print('SAVE lines', h.save(os.path.join(out, 'lines.hwpx')), good)


def job_names(h):
    ps = h.hwp.HParameterSet
    print('NAMES HCellBorderFill', names_of(ps.HCellBorderFill))
    print('NAMES FillAttr', names_of(ps.HCellBorderFill.FillAttr))
    print('NAMES HShapeObject', names_of(ps.HShapeObject))
    print('NAMES TableProperties', names_of(ps.HTableCreation.TableProperties))
    print('NAMES HFieldCtrl', names_of(ps.HFieldCtrl))
    print('NAMES HWP', names_of(h.hwp))


def job_actions(h, out):
    """Run actions that take no dialog; the ones that return True are saved to look at their XML."""
    def run(name, prep):
        h.hwp.Clear(1)
        prep()
        try:
            r = h.run(name)
        except Exception as e:
            r = 'ERR ' + repr(e)[:60]
        print('ACTION', name, r)
        if r is True:
            leave_table(h)
            h.save(os.path.join(out, f'act_{name}.hwpx'))

    def nums():
        make_table(h, [30, 30], [10] * 4)
        for r in range(3):
            cell_text(h, r, 0, str(10 * (r + 1)))
        goto(h, 3, 0)
        h.run('TableCellBlock')

    def one():
        make_table(h, [60], [15])
        cell_text(h, 0, 0, '셀')
        goto(h, 0, 0)
        h.run('TableCellBlock')
    for n in ('TableFormulaSumAuto', 'TableFormulaAvgAuto', 'TableFormulaProdAuto', 'TableFormulaSum', 'TableFormulaAvg',
              'TableFormulaProd'):
        run(n, nums)
    for n in ('TableAttachCaption', 'ShapeObjAttachCaption', 'InsertCaption', 'TableCaption', 'ShapeObjCaption',
              'ShapeObjAttachCaptionTop', 'ShapeObjAttachCaptionBottom'):
        run(n, one)
    for n in ('TableCellProtect', 'CellProtect', 'TableProtectCell', 'TableCellLock', 'TableCellBlockProtect', 'TableProtect'):
        run(n, one)


def job_fills(h, out):
    """Gradient and picture fills through FillAttr, in several spellings; a file counts when the XML has the brush."""
    hw = h.hwp
    fa = names_of(hw.HParameterSet.HCellBorderFill.FillAttr)
    print('FILLATTR names', fa)
    png = os.path.join(out, 'fill.png')
    fill_png(png)
    try:
        types = {k: hw.BrushType(k) for k in ('GradBrush', 'NullBrush|GradBrush', 'ImageBrush', 'NullBrush|ImageBrush')}
    except Exception as e:
        types = {}
        print('BRUSHTYPE ERR', e)
    print('BRUSHTYPES', types)
    variants = []
    for tname in ('GradBrush', 'NullBrush|GradBrush'):
        for gt in (1, 2):
            variants.append(('grad', tname, {'FillAttr.type': types.get(tname), 'FillAttr.GradationType': gt,
                                             'FillAttr.GradationAngle': 90, 'FillAttr.GradationCenterX': 50,
                                             'FillAttr.GradationCenterY': 50, 'FillAttr.GradationStep': 50}))
    for tname in ('ImageBrush', 'NullBrush|ImageBrush'):
        variants.append(('img', tname, {'FillAttr.type': types.get(tname), 'FillAttr.FileName': png,
                                        'FillAttr.Embedded': 1, 'FillAttr.PicEffect': 0}))
    for i, (kind, tname, items) in enumerate(variants):
        hw.Clear(1)
        make_table(h, [60], [15])
        cell_text(h, 0, 0, '셀')
        goto(h, 0, 0)
        h.run('TableCellBlock')
        bad = []
        ps = hw.HParameterSet.HCellBorderFill
        hw.HAction.GetDefault('CellBorderFill', ps.HSet)
        for k, v in items.items():
            try:
                obj = ps
                parts = k.split('.')
                for p in parts[:-1]:
                    obj = getattr(obj, p)
                setattr(obj, parts[-1], v)
            except Exception:
                bad.append(k)
        h.guard()
        try:
            hw.HAction.Execute('CellBorderFill', ps.HSet)
        except Exception as e:
            bad.append('EXEC ' + repr(e)[:50])
        h.run('Cancel')
        leave_table(h)
        path = os.path.join(out, f'fill_{i}.hwpx')
        h.save(path)
        print('FILL', i, kind, tname, 'setattr errors', bad, 'xml has', xml_has(path, 'hc:gradation', 'hc:imgBrush'))


def job_pos(h, out):
    """Floating table: the base table (TreatAsChar 0) and one property at a time. Values 0..n: the XML tells the meaning."""
    def one(name, **props):
        h.hwp.Clear(1)
        h.text('본문 첫 줄')
        h.run('BreakPara')
        bad = make_table(h, [30, 30], [10], TreatAsChar=0, **props)
        h.text('셀')
        leave_table(h)
        print('POS', name, props, 'setattr errors', bad, h.save(os.path.join(out, f'pos_{name}.hwpx')))
    one('base')
    for k, vals in (('TextWrap', range(6)), ('HorzRelTo', range(4)), ('VertRelTo', range(3)), ('HorzAlign', range(5)),
                    ('VertAlign', range(5))):
        for v in vals:
            one(f'{k}{v}', **{k: v})
    one('offset', HorzOffset=h.mm(30), VertOffset=h.mm(20))
    for k in ('AllowOverlap', 'FlowWithText', 'AffectSpacing', 'HoldAnchorObj'):
        one(k + '1', **{k: 1})
        one(k + '0', **{k: 0})


def job_resave(h, out, only=None, dpi=96):
    """Open each hand-built file, draw its page, save it again: Hangul's own form of what the builder wrote."""
    files = {n: p for n, p in build_all(out).items() if only is None or n in only}
    os.makedirs(os.path.join(out, 'resaved'), exist_ok=True)
    os.makedirs(os.path.join(out, 'png'), exist_ok=True)
    for name, path in files.items():
        h.hwp.Clear(1)
        if not h.open(path):
            print('RESAVE', name, 'OPEN FAIL')
            continue
        h.run('Cancel')
        h.hwp.MovePos(2, 0, 0)
        stem = os.path.join(out, 'png', name)
        for bmp in h.page_images(stem, dpi=dpi, fmt='bmp'):
            if os.path.exists(bmp):
                img.save_png(bmp[:-4] + '.png', img.load(bmp))
                os.remove(bmp)
        print('RESAVE', name, 'saved', h.save(os.path.join(out, 'resaved', name + '.hwpx')))


def select_block(h, r, c, rs=1, cs=1):
    goto(h, r, c)
    h.run('TableCellBlock')
    if rs > 1 or cs > 1:
        h.run('TableCellBlockExtend')
        for _ in range(cs - 1):
            h.run('TableRightCell')
        for _ in range(rs - 1):
            h.run('TableLowerCell')


# ---- window 2: what window 1 did not settle ---------------------------------------------------------------------------
def job2_names(h):
    ps = h.hwp.HParameterSet
    allnames = names_of(ps)
    print('PARAMSETS', [n for n in allnames if re.search(r'Cell|Table|Formula|Caption|Field|Prot|Brush|Fill|Shape', n)]
          if isinstance(allnames, list) else allnames)
    so = ps.HShapeObject
    for sub in ('ShapeTableCell', 'ShapeCaption', 'ShapeDrawFillAttr'):
        try:
            print('NAMES', sub, names_of(getattr(so, sub)))
        except Exception as e:
            print('NAMES', sub, 'ERR', repr(e)[:80])
    fa = ps.HCellBorderFill.FillAttr
    for sub in ('GradationColor', 'GradationBrush', 'ImageBrush'):
        try:
            print('NAMES FillAttr.' + sub, names_of(getattr(fa, sub)))
        except Exception as e:
            print('NAMES FillAttr.' + sub, 'ERR', repr(e)[:80])


def job2_formula(h, out):
    """Formula cells: block sum / average with the numbers selected (with and without the empty cell below), then the
    parameter-set route (HFieldCtrl.Command)."""
    hw = h.hwp
    for name in ('TableFormulaSumAuto', 'TableFormulaAvgAuto', 'TableFormulaSum', 'TableFormulaAvg', 'TableFormulaProd'):
        for variant, rows in (('num', 3), ('numdest', 4)):
            hw.Clear(1)
            make_table(h, [30, 30], [10] * 4)
            for r in range(3):
                cell_text(h, r, 0, str(10 * (r + 1)))
                cell_text(h, r, 1, str(r + 1))
            select_block(h, 0, 0, rows, 2)
            try:
                ret = h.run(name)
            except Exception as e:
                ret = 'ERR ' + repr(e)[:50]
            leave_table(h)
            path = os.path.join(out, f'formula_{name}_{variant}.hwpx')
            h.save(path)
            print('FORMULA', name, variant, ret, 'xml has', xml_has(path, 'FORMULA', '=SUM', '=AVG', 'Formula'))
    for action in ('TableFormula', 'InsertFieldFormula', 'FieldFormula'):
        hw.Clear(1)
        make_table(h, [30, 30], [10] * 4)
        for r in range(3):
            cell_text(h, r, 0, str(10 * (r + 1)))
        goto(h, 3, 0)
        try:
            ps = hw.HParameterSet.HFieldCtrl
            hw.HAction.GetDefault(action, ps.HSet)
            ps.Command = '=SUM(A1:A3)'
            h.guard()
            ret = hw.HAction.Execute(action, ps.HSet)
        except Exception as e:
            ret = 'ERR ' + repr(e)[:60]
        leave_table(h)
        path = os.path.join(out, f'formula_param_{action}.hwpx')
        h.save(path)
        print('FORMULA param', action, ret, 'xml has', xml_has(path, 'FORMULA', '=SUM'))


def job2_protect(h, out):
    """Cell protect: does Hangul block typing in a protect="1" cell? (the hand-built file, one cell protected)"""
    files = build_all(out)
    hw = h.hwp
    hw.Clear(1)
    if not h.open(files['cell_protect']):
        print('PROTECT open FAIL')
        return
    for r, c in ((0, 0), (0, 1)):
        goto(h, r, c)
        h.text('ZZ')
    try:
        txt = hw.GetTextFile('TEXT', '')
    except Exception as e:
        txt = 'ERR ' + repr(e)[:60]
    print('PROTECT text after typing ZZ in the protected cell and in the other:', repr(txt))


def job2_gradient(h, out):
    """Gradient and picture fill by FillAttr with the colour array and the picture name items window 1 did not set."""
    hw = h.hwp
    fill_png(os.path.join(out, 'fill.png'))
    png = os.path.join(out, 'fill.png')
    for i, kind in enumerate(('grad_array', 'grad_array_null', 'img_str', 'img_filename')):
        hw.Clear(1)
        make_table(h, [60], [15])
        cell_text(h, 0, 0, '셀')
        select_block(h, 0, 0)
        ps = hw.HParameterSet.HCellBorderFill
        hw.HAction.GetDefault('CellBorderFill', ps.HSet)
        fa = ps.FillAttr
        err = []
        try:
            if kind.startswith('grad'):
                fa.type = hw.BrushType('NullBrush|GradBrush' if kind.endswith('null') else 'GradBrush')
                fa.GradationType = 1
                fa.GradationAngle = 90
                fa.GradationCenterX = 50
                fa.GradationCenterY = 50
                fa.GradationStep = 50
                fa.GradationColorNum = 2
                fa.CreateItemArray('GradationColor', 2)
                fa.GradationColor.SetItem(0, h.rgb('#FF0000'))
                fa.GradationColor.SetItem(1, h.rgb('#0000FF'))
            else:
                fa.type = hw.BrushType('ImageBrush')
                setattr(fa, 'FileNameStr' if kind == 'img_str' else 'filename', png)
                fa.Embedded = 1
                fa.DrawFillImageType = 0
        except Exception as e:
            err.append(repr(e)[:80])
        h.guard()
        try:
            hw.HAction.Execute('CellBorderFill', ps.HSet)
        except Exception as e:
            err.append('EXEC ' + repr(e)[:60])
        h.run('Cancel')
        leave_table(h)
        path = os.path.join(out, f'fill2_{kind}.hwpx')
        h.save(path)
        print('FILL2', kind, err, 'xml has', xml_has(path, 'hc:gradation', 'hc:imgBrush'))


def job2_lines(h, out):
    """Line type numbers set directly (no name): which XML types do 0..20 give?"""
    hw = h.hwp
    hw.Clear(1)
    cols = 7
    make_table(h, [24] * cols, [12] * 3)
    for k in range(21):
        goto(h, k // cols, k % cols)
        h.run('TableCellBlock')
        it = {}
        for side, name in dict(L='Left', R='Right', T='Top', B='Bottom').items():
            it['BorderType' + name] = k
            it['BorderWidth' + name] = hw.HwpLineWidth('0.4mm')
            it[COLOR[side]] = h.rgb('#000000')
        h.act('CellBorderFill', 'HCellBorderFill', **it)
        h.run('Cancel')
    leave_table(h)
    path = os.path.join(out, 'lines2.hwpx')
    print('SAVE lines2', h.save(path))
    with zipfile.ZipFile(path) as z:
        s, hd = z.read('Contents/section0.xml').decode(), z.read('Contents/header.xml').decode()
    bf = {re.search(r'id="(\d+)"', b).group(1): b for b in re.findall(r'<hh:borderFill .*?</hh:borderFill>', hd, re.S)}
    for k, ref in enumerate(re.findall(r'<hp:tc [^>]*borderFillIDRef="(\d+)"', s)):
        print('LINES2', k, re.findall(r'<hh:leftBorder type="(\w+)"', bf[ref]))


def window2(out):
    from ..render.hwpcom import Hwp
    os.makedirs(out, exist_ok=True)
    with Hwp(timeout=90) as h:
        job2_names(h)
        job2_formula(h, out)
        job2_protect(h, out)
        job2_gradient(h, out)
        job2_lines(h, out)
        job_resave(h, out)         # the hand-built files again (now with the gradient angle study)
    from ..check import roundtrip      # round trip of every fixture of this package: Hangul file -> spec -> builder -> render
    files = sorted(os.path.join(FIXTURES, f) for f in os.listdir(FIXTURES) if f.endswith('.hwpx'))
    roundtrip.main(os.path.join(out, 'rt'), files)


def cell_texts(path):
    """{(row, col): text} of the first table of an HWPX."""
    with zipfile.ZipFile(path) as z:
        s = z.read('Contents/section0.xml').decode('utf-8')
    out = {}
    for tc in re.findall(r'<hp:tc .*?</hp:tc>', s, re.S):
        a = re.search(r'colAddr="(\d+)" rowAddr="(\d+)"', tc)
        out[(int(a.group(2)), int(a.group(1)))] = ''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', tc))
    return out


def job4_protect(h, out):
    """Is typing blocked in a protect="1" cell? Several ways to get the caret into the table of the hand-built file (the
    caret is not in a cell after Open); each: type ZZ in cell (0, 0), move right, type YY, save, read the cell texts back.
    cell_protect has (0, 0) protected; cell_protect_control has no protected cell (typing must work there)."""
    files = build_all(out)
    hw = h.hwp
    ways = {'moveright': lambda: (hw.MovePos(2, 0, 0), h.run('MoveRight')),
            'selcell': lambda: (hw.MovePos(2, 0, 0), h.run('ShapeObjTableSelCell')),
            'colbegin': lambda: (hw.MovePos(2, 0, 0), h.run('TableColBegin')),
            'docend_cell': lambda: (hw.MovePos(2, 0, 0), h.run('TableColBegin'), h.run('TableColPageUp'))}
    for way, enter in ways.items():
        for name in ('cell_protect', 'cell_protect_control'):
            hw.Clear(1)
            if not h.open(files[name]):
                print('PROTECT', way, name, 'open FAIL')
                continue
            res = []
            try:
                res.append(enter())
                h.run('Cancel')
                res.append(h.text('ZZ'))
                res.append(h.run('TableRightCell'))
                res.append(h.text('YY'))
            except Exception as e:
                res.append('ERR ' + repr(e)[:60])
            leave_table(h)
            path = os.path.join(out, f'protect_{way}_{name}.hwpx')
            h.save(path)
            print('PROTECT', way, name, 'calls', [r if not isinstance(r, tuple) else r[-1] for r in res], 'cells', cell_texts(path))


def job5_protect(h, out):
    """Window 4 never got the caret into the table (the control without protect failed too). More ways: SetPos to the cell
    sublists (list ids 1, 2, ...), and from the end of the document one step left (into the last cell). A way counts when the
    control file takes the text in a cell."""
    files = build_all(out)
    hw = h.hwp
    ways = {f'setpos{k}': (lambda k=k: hw.SetPos(k, 0, 0)) for k in (1, 2, 3)}
    ways['end_left'] = lambda: (hw.MovePos(3, 0, 0), h.run('MoveLeft'))
    ways['end_left2'] = lambda: (hw.MovePos(3, 0, 0), h.run('MoveLeft'), h.run('MoveLeft'))
    ways['begin_down'] = lambda: (hw.MovePos(2, 0, 0), h.run('MoveDown'))
    for way, enter in ways.items():
        for name in ('cell_protect', 'cell_protect_control'):
            hw.Clear(1)
            if not h.open(files[name]):
                print('PROTECT5', way, name, 'open FAIL')
                continue
            try:
                got = enter()
                h.run('Cancel')
                in_table = h.run('TableColBegin')          # True only when the caret is in a table cell
                h.text('ZZ')
            except Exception as e:
                got, in_table = 'ERR ' + repr(e)[:50], None
            leave_table(h)
            path = os.path.join(out, f'protect5_{way}_{name}.hwpx')
            h.save(path)
            print('PROTECT5', way, name, 'enter', got, 'in_table', in_table, 'cells', cell_texts(path))


def window5(out):
    from ..render.hwpcom import Hwp
    os.makedirs(out, exist_ok=True)
    with Hwp(timeout=90) as h:
        job5_protect(h, out)


def window4(out):
    """Fourth batch: typing into a protected cell, and Hangul's own look of every line type at 1 mm and of a right caption at 300 dpi."""
    from ..render.hwpcom import Hwp
    os.makedirs(out, exist_ok=True)
    with Hwp(timeout=90) as h:
        job4_protect(h, out)
        for k in range(5):                      # text flow beside a square-wrapped table (hp:tbl textFlow): COM TextFlow 0..4
            h.hwp.Clear(1)
            h.text('본문 첫 줄')
            h.run('BreakPara')
            bad = make_table(h, [30, 30], [10], TreatAsChar=0, TextWrap=0, TextFlow=k)
            h.text('셀')
            leave_table(h)
            path = os.path.join(out, f'pos_TextFlow{k}.hwpx')
            h.save(path)
            with zipfile.ZipFile(path) as z:
                flow = re.search(r'textFlow="(\w+)"', z.read('Contents/section0.xml').decode()).group(1)
            print('TEXTFLOW', k, 'setattr errors', bad, '->', flow)
        job_resave(h, out, only=('lines_wide', 'caption_right'), dpi=300)


NEW_IN_WINDOW2 = ('table_formula_sum', 'table_formula_avg', 'table_formula_param', 'cell_fill_gradient_com',
                  'cell_line_types_more', 'cell_fill_gradient_angles')


def window3(out):
    """Third, short batch: the hand-built files again (now with a formula cell), then the round trip of the fixtures that came
    from window 2."""
    from ..render.hwpcom import Hwp
    os.makedirs(out, exist_ok=True)
    with Hwp(timeout=90) as h:
        job_resave(h, out)
    from ..check import roundtrip
    roundtrip.main(os.path.join(out, 'rt'), [os.path.join(FIXTURES, n + '.hwpx') for n in NEW_IN_WINDOW2])


def window(out):
    from ..render.hwpcom import Hwp
    os.makedirs(out, exist_ok=True)
    with Hwp(timeout=90) as h:           # one hidden Hangul; Quit in __exit__
        job_names(h)
        job_lines(h, out)
        job_actions(h, out)
        job_fills(h, out)
        job_pos(h, out)
        job_resave(h, out)


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def anonymize(src, dst):
    """Copy an HWPX with creator and lastsaveby set to `hwpx-docs` (Hangul writes the Windows user name there)."""
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, 'w') as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == 'Contents/content.hpf':
                data = re.sub(rb'(name="(?:creator|lastsaveby)" content="text">)[^<]*', rb'\1hwpx-docs', data)
            zo.writestr(item, data)


def pick_fixtures(win):
    """Copy the useful files of a `window` run into table/fixtures/ (anonymized). Returns the names."""
    os.makedirs(FIXTURES, exist_ok=True)
    pairs = [('lines.hwpx', 'cell_line_types'), ('act_TableCaption.hwpx', 'table_caption'),
             ('resaved/fill_gradient.hwpx', 'cell_fill_gradient'), ('resaved/fill_image.hwpx', 'cell_fill_image'),
             ('resaved/caption_top.hwpx', 'table_caption_top'), ('resaved/caption_left.hwpx', 'table_caption_left'),
             ('resaved/cell_protect.hwpx', 'cell_protect'), ('resaved/pos_paper.hwpx', 'table_pos_resaved_paper'),
             ('resaved/pos_page_right_bottom.hwpx', 'table_pos_resaved_page_right_bottom'),
             ('resaved/pos_square.hwpx', 'table_pos_resaved_square'),
             # window 2
             ('formula_TableFormulaSumAuto_num.hwpx', 'table_formula_sum'), ('formula_TableFormulaAvgAuto_numdest.hwpx',
                                                                            'table_formula_avg'),
             ('formula_param_TableFormula.hwpx', 'table_formula_param'), ('fill2_grad_array.hwpx', 'cell_fill_gradient_com'),
             ('lines2.hwpx', 'cell_line_types_more'), ('resaved/fill_gradient_angles.hwpx', 'cell_fill_gradient_angles'),
             # window 4
             ('resaved/caption_right.hwpx', 'table_caption_right'), ('resaved/lines_wide.hwpx', 'cell_line_types_wide')]
    for f in sorted(os.listdir(win)):          # all of them: a variant whose XML equals pos_base shows that COM item has no effect
        if f.startswith('pos_') and f.endswith('.hwpx'):
            pairs.append((f, 'table_' + f[:-5]))
    names = []
    for src, name in pairs:
        if os.path.exists(os.path.join(win, src)):
            anonymize(os.path.join(win, src), os.path.join(FIXTURES, name + '.hwpx'))
            names.append(name)
    return names


def main(argv):
    if len(argv) >= 2 and argv[0] == 'fixtures':
        print('FIXTURES', ' '.join(pick_fixtures(argv[1])))
        return 0
    if len(argv) >= 2 and argv[0] == 'window5':
        window5(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == 'window4':
        window4(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == 'window3':
        window3(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == 'window2':
        window2(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == 'window':
        window(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == 'build':
        for n, p in build_all(argv[1]).items():
            print('BUILT', n, p)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
