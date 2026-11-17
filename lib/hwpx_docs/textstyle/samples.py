"""Hangul COM sample maker of the textstyle package (needs Hangul + pywin32; run only in the agreed Hangul window).

  hd textstyle samples <phase> <out_dir> [name ...]

Phases:  explore   speculative COM calls (drop cap, user styles, picture bullets, 한자, 덧말); each job writes
                   <out_dir>/<name>.hwpx and prints what it found. Nothing is guessed: a job that makes no effect says so.
         fixtures  the minimal-difference pairs and samples of coverage.md rows C2.10, C3.03, C3.04 (to tests/fixtures).
         templates open each 스타일마당 template (.hwp) of the Hangul install and save it as HWPX (C9.05).
         resave    files built by hwpx-docs (user styles, 덧말, drop cap) -> Hangul Open -> SaveAs (a file Hangul wrote itself).

One Hangul (hidden, never activated, Quit at the end) runs the whole phase: the user answers the access prompt at
most once ("모두 허용"). The parameter orders below were measured in the exploring run of 2026-11-14
(rules.md TS01): COM TabItem = flat array of (pos HWPUNIT, leader, type) triples.
"""
from ..core import tmpdir
import os
import re
import shutil
import struct
import sys
import zipfile
import zlib

TAB_LEADER = {'none': 0, 'solid': 1, 'dot': 2, 'dash': 3, 'dash_dot': 4, 'dash_dot_dot': 5, 'long_dash': 6, 'circle': 7,
              'double_slim': 8, 'slim_thick': 9, 'thick_slim': 10, 'slim_thick_slim': 11}
TAB_TYPE = {'left': 0, 'right': 1, 'center': 2, 'decimal': 3}
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'tests', 'fixtures'))
PAIRS, SAMPLES, EXPLORE = {}, {}, {}


from .privacy import private_patterns, sanitize, scan   # noqa: F401,E402  (moved to privacy.py; kept here for the callers)


def _try(fn, *a, **k):
    """Result of fn, or 'ERR ...' (an exploring call may be refused by Hangul; the job goes on)."""
    try:
        return fn(*a, **k)
    except Exception as e:
        return 'ERR ' + repr(e)[:100]


def tab_shape(h, stops, auto_left=0, auto_right=0):
    """ParagraphShape of the current paragraph with custom tab stops: [(mm, type, leader)], mm = where the stop lies.
    COM takes twice that (rules.md TS01); Hangul then writes unit HWPUNIT for requests 10 + 30k mm, else unit CHAR (a stop
    5 times as far), so the positions used here are 5 + 15k mm (20, 35, 50, 65, 80, 95, 110)."""
    hw = h.hwp
    ps = hw.HParameterSet.HParaShape
    hw.HAction.GetDefault('ParagraphShape', ps.HSet)
    td = ps.TabDef
    td.AutoTabLeft, td.AutoTabRight = auto_left, auto_right
    td.CreateItemArray('TabItem', 3 * len(stops))
    for i, (mm, typ, lead) in enumerate(stops):
        td.TabItem.SetItem(3 * i, 2 * h.mm(mm))
        td.TabItem.SetItem(3 * i + 1, TAB_LEADER[lead])
        td.TabItem.SetItem(3 * i + 2, TAB_TYPE[typ])
    h.guard()
    return hw.HAction.Execute('ParagraphShape', ps.HSet)


def tab_line(h, text):
    for n, part in enumerate(text.split('\t')):
        if n:
            h.run('InsertTab')
        h.text(part)


def sample(fn):
    SAMPLES[fn.__name__] = fn
    return fn


def explore(fn):
    EXPLORE[fn.__name__] = fn
    return fn


# ---- C2.10 tabs: pairs and one sample --------------------------------------------------------------------------------
PAIRS.update({
    'tab_stop': (lambda h, v: (v and tab_shape(h, [(50, 'left', 'none')]), tab_line(h, '항목\t내용')), 0, 1),
    'tab_type_right': (lambda h, v: (tab_shape(h, [(50, v, 'none')]), tab_line(h, '항목\t1234.56')), 'left', 'right'),
    'tab_type_center': (lambda h, v: (tab_shape(h, [(50, v, 'none')]), tab_line(h, '항목\t1234.56')), 'left', 'center'),
    'tab_type_decimal': (lambda h, v: (tab_shape(h, [(50, v, 'none')]), tab_line(h, '항목\t1234.56')), 'left', 'decimal'),
    'tab_leader_dot': (lambda h, v: (tab_shape(h, [(95, 'right', v)]), tab_line(h, '목차\t12')), 'none', 'dot'),
    'tab_leader_solid': (lambda h, v: (tab_shape(h, [(95, 'right', v)]), tab_line(h, '목차\t12')), 'none', 'solid'),
    'tab_leader_dash': (lambda h, v: (tab_shape(h, [(95, 'right', v)]), tab_line(h, '목차\t12')), 'none', 'dash'),
    'tab_auto': (lambda h, v: (tab_shape(h, [(50, 'left', 'none')], auto_left=v, auto_right=v), tab_line(h, '항목\t내용')), 0, 1),
})


@sample
def tabs_custom(h):
    """One paragraph per tab form: two stops, a leader with a right tab, decimal figures."""
    for stops, text in (([(40, 'left', 'none'), (100, 'right', 'dot')], '제목\t본문\t12'),
                        ([(80, 'center', 'none')], '가운데\t정렬'),
                        ([(70, 'decimal', 'none')], '금액\t1,234.56'),
                        ([(120, 'right', 'solid'), (140, 'left', 'dash')], '차례\t3\t쪽')):
        tab_shape(h, stops)
        tab_line(h, text)
        h.run('BreakPara')


# ---- C2.09 Latin line break: all three values in one document, long words that straddle the line end --------------------
@sample
def latin_break(h):
    words = ' '.join(['Internationalization', 'extraordinarily', 'incomprehensibilities', 'characteristically',
                      'counterrevolutionaries', 'electroencephalograph'] * 3)
    for v in (0, 1, 2):                                     # COM BreakLatinWord: 0 word, 1 hyphen, 2 character
        h.act('ParagraphShape', 'HParaShape', BreakLatinWord=v)
        h.text(f'[{v}] ' + words)
        h.run('BreakPara')


# ---- C9.01 drop cap: pairs (none -> two lines, three lines, margin) and a sample with frame, fill and font ---------------------
def _dropcap(h, style, **kw):
    h.text(LONG)
    h.run('MoveLineBegin')
    if style:
        h.act('DropCap', 'HDropCap', style=style, **kw)


PAIRS.update({
    'dropcap_two': (lambda h, v: _dropcap(h, v, FaceName='함초롬바탕', Spacing=0), 0, 1),
    'dropcap_three': (lambda h, v: _dropcap(h, v, FaceName='함초롬바탕', Spacing=0), 0, 2),
    'dropcap_margin': (lambda h, v: _dropcap(h, v, FaceName='함초롬바탕', Spacing=0), 0, 3),
})


@sample
def dropcap_frame(h):
    _dropcap(h, 1, FaceName='함초롬돋움', FaceColor=h.rgb('#C00000'), LineColor=h.rgb('#FF0000'), LineStyle=1,
             LineWeight=113, Spacing=3)                    # LineWeight is HWPUNIT (113 = 0.4 mm), not an index (TS17)


# ---- C8.07 한자 병기: Hangul's 한자 입력 changes no text through COM (TS20), so the forms are typed as plain text ---------------
@sample
def hanja_forms(h):
    for text in ('대한민국(大韓民國)', '大韓民國(대한민국)', '大韓民國', '대한민국 大韓民國 만세'):
        h.text(text)
        h.run('BreakPara')


# ---- explore: drop cap, user styles, picture bullets, 한자, 덧말 ---------------------------------------------------------
LONG = '문단 첫 글자 장식 시험입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다. 다섯째 문장입니다. 여섯째 문장입니다.'


@explore
def dropcap_probe(h):
    """HDropCap: items style, FaceName, FaceColor, LineColor/Style/Weight, Spacing (action DropCap)."""
    for style in (0, 1, 2, 3):
        h.hwp.Clear(1)
        h.text(LONG)
        h.run('MoveLineBegin')
        r = _try(h.act, 'DropCap', 'HDropCap', style=style, FaceName='함초롬바탕', Spacing=0)
        yield f'dropcap_s{style}', r
    h.hwp.Clear(1)
    h.text(LONG)
    h.run('MoveLineBegin')
    r = _try(h.act, 'DropCap', 'HDropCap', style=1, FaceName='함초롬돋움', FaceColor=h.rgb('#FFFF00'), LineColor=h.rgb('#FF0000'),
             LineStyle=1, LineWeight=h.hwp.HwpLineWidth('0.4mm'), Spacing=3)
    yield 'dropcap_face', r


@explore
def style_probe(h):
    """Create a user style through COM: several action names with HStyleItem; success = a new hh:style in the file."""
    P = h.hwp.HParameterSet
    for action in ('StyleAdd', 'StyleNew', 'StyleEdit', 'StyleItem', 'StyleInsert', 'StyleCreate', 'AddStyle'):
        h.hwp.Clear(1)
        h.text('스타일 시험')
        try:
            si = P.HStyleItem
            h.hwp.HAction.GetDefault(action, si.HSet)
            si.NameLocal, si.NameEng, si.type = '시험스타일', 'TestStyle', 0
            r = h.hwp.HAction.Execute(action, si.HSet)
        except Exception as e:
            r = 'ERR ' + repr(e)[:80]
        yield f'style_{action}', r
    # apply built-in style numbers 0..22 one by one: the id of the style that Hangul writes for each
    for n in (1, 2, 12, 13, 14, 15, 17, 22):
        h.hwp.Clear(1)
        h.act('Style', 'HStyle', Apply=n)
        h.text('스타일 ' + str(n))
        yield f'style_apply_{n}', True


@explore
def bullet_image_probe(h):
    """HBulletShape (BulletImage, HasImage): a picture bullet through COM."""
    png = os.path.join(tmpdir.mkdtemp('ts_bullet_'), 'textstyle_bullet.png')
    open(png, 'wb').write(_png(16, 16))
    P = h.hwp.HParameterSet
    for tag, image in (('path', png), ('bytes', _png(16, 16))):
        h.hwp.Clear(1)
        h.run('PutBullet')
        h.text('그림 글머리표')
        try:
            bs = P.HBulletShape
            h.hwp.HAction.GetDefault('BulletShape', bs.HSet)
            bs.HasImage = 1
            bs.BulletImage = image
            r = h.hwp.HAction.Execute('BulletShape', bs.HSet)
        except Exception as e:
            r = 'ERR ' + repr(e)[:80]
        yield f'bulletimg_{tag}', r


@explore
def bullet_image_probe2(h):
    """HBulletShape.BulletImage is an HDrawImageAttr set: FileNameStr (+ Embedded), with HasImage = 1."""
    png = os.path.join(tmpdir.mkdtemp('ts_bullet_'), 'textstyle_bullet.png')
    open(png, 'wb').write(_png(16, 16))
    P = h.hwp.HParameterSet
    for tag, embedded in (('embedded', 1), ('linked', 0)):
        h.hwp.Clear(1)
        h.run('PutBullet')
        h.text('그림 글머리표')
        bs = P.HBulletShape
        h.hwp.HAction.GetDefault('BulletShape', bs.HSet)
        bs.HasImage = 1
        r = _try(lambda: (setattr(bs.BulletImage, 'FileNameStr', png), setattr(bs.BulletImage, 'Embedded', embedded),
                          h.hwp.HAction.Execute('BulletShape', bs.HSet))[-1])
        yield f'bulletimg2_{tag}', r


@explore
def hanja_probe(h):
    """한자 병기: HInputHanja option 0..5 on a selected word (and the text that results)."""
    for opt in range(6):
        h.hwp.Clear(1)
        h.text('대한민국 만세')
        h.run('MoveLineBegin')
        for _ in range(4):
            h.run('MoveSelRight')
        r = _try(h.act, 'InputHanja', 'HInputHanja', Hanja='大韓民國', Hangul='대한민국', option=opt)
        h.run('Cancel')
        yield f'hanja_opt{opt}', (r, h.hwp.GetTextFile('TEXT', ''))


@explore
def dutmal_probe(h):
    """덧말: InsertCtrl('tdut') on a selection (the earlier run: Hangul saved a section with no text); and Dutmal."""
    s = h.hwp.CreateSet('Dutmal')
    for k, v in (('SubText', '덧말'), ('PosType', 0), ('Option', 0), ('FSizeRatio', 50), ('StyleNo', 0), ('Alignment', 0)):
        s.SetItem(k, v)
    h.text('앞 본말 뒤')
    h.run('MoveLineBegin')
    for _ in range(2):
        h.run('MoveRight')
    for _ in range(2):
        h.run('MoveSelRight')
    r = _try(h.hwp.InsertCtrl, 'tdut', s)
    h.run('Cancel')
    yield 'dutmal_ctrl', (r, h.hwp.GetTextFile('TEXT', ''))


def _png(w, h_):
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes([200, 40, 40]) * w for _ in range(h_))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h_, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


# ---- resave: files built by hwpx-docs, opened and saved by Hangul (what COM cannot make) ------------------------------------
RESAVE = {
    'styles_user': {'named_styles': {
        '제목 가': {'size': 16, 'bold': True, 'align': 'center', 'after': 6, 'next': '본문 나', 'eng': 'MyTitle'},
        '본문 나': {'size': 11, 'line': 170, 'left': 5, 'eng': 'MyBody'},
        '강조': {'type': 'char', 'bold': True, 'color': '#C00000', 'eng': 'MyStrong'},
        '각주 다': {'size': 9, 'color': '#666666', 'align': 'right', 'next': '본문 나'}},
        'body': [{'style': '제목 가', 'p': '사용자 스타일 시험'},
                 {'style': '본문 나', 'p': ['본문 문단에 ', {'t': '강조 글자', 'style': '강조'}, ' 스타일을 적용합니다.']},
                 {'style': '각주 다', 'p': '오른쪽 작은 글씨'}, {'style': '개요 1', 'p': '기본 스타일 개요 1'}]},
    'dutmal_top': {'body': [{'p': ['앞 ', {'dutmal': {'main': '본말', 'sub': '덧말', 'pos': 'top'}}, ' 뒤 문장입니다.']}]},
    'dutmal_bottom': {'body': [{'p': ['앞 ', {'dutmal': {'main': '본말', 'sub': '덧말', 'pos': 'bottom'}}, ' 뒤 문장입니다.']}]},
    'dutmal_wide': {'body': [{'p': ['앞 ', {'dutmal': {'main': '가나', 'sub': '긴 덧말 글자', 'size': 60, 'align': 'left'}}, ' 뒤.']}]},
    'dutmal_ctrl': {'body': [{'p': ['앞 ', {'xml': '<hp:ctrl><hp:dutmal posType="TOP" szRatio="50" option="0" styleIDRef="0" align="CENTER">'
                                              '<hp:mainText>본말</hp:mainText><hp:subText>덧말</hp:subText></hp:dutmal></hp:ctrl>'},
                                    ' 뒤 문장입니다.']}]},
    'picbullet_built': {'body': [{'bullet_image': 'bullet.png', 'p': '그림 글머리표 첫째 문단'},
                                 {'bullet_image': 'bullet.png', 'p': '그림 글머리표 둘째 문단'}, {'p': '글머리표 없는 문단'}]},
    'dropcap_built': {'body': [{'dropcap': {'lines': 2}, 'p': LONG}, {'dropcap': {'lines': 3}, 'p': LONG},
                               {'dropcap': {'lines': 'margin'}, 'p': LONG},
                               {'dropcap': {'lines': 2, 'font': '함초롬돋움', 'color': '#C00000', 'frame': '0.4mm solid #FF0000',
                                            'fill': '#FFFF00'}, 'p': LONG}]},
}


# ---- runners -------------------------------------------------------------------------------------------------------
def _facts(path):
    """One line: what a saved file holds that this package cares about."""
    with zipfile.ZipFile(path) as z:
        hd = z.read('Contents/header.xml').decode('utf-8')
        sec = z.read('Contents/section0.xml').decode('utf-8')
    bits = [f'styles {len(re.findall("<hh:style ", hd))}', f'tabUnits {re.findall(r"<hh:tabItem [^>]*unit=.(\w+)", hd)}',
            f'dropcap {len(re.findall("dropcapstyle=.(?!None)", sec))}', f'dutmal {sec.count("<hp:dutmal")}',
            f'bulletImg {len(re.findall("useImage=.1", hd))}', f'text {len(re.findall("<hp:t>", sec))}']
    return ' '.join(bits)


def run_phase(phase, out_dir, names):
    from ..render.hwpcom import run_jobs
    os.makedirs(out_dir, exist_ok=True)
    if phase == 'explore':
        jobs = names or list(EXPLORE)
        def job(h, name):
            for tag, r in EXPLORE[name](h):
                p = os.path.join(out_dir, tag + '.hwpx')
                ok = h.save(p)
                print('EXPLORE', tag, 'result', r, 'saved', ok, _facts(p) if ok else '', flush=True)
                h.hwp.Clear(1)
            return True
    elif phase == 'fixtures':
        jobs = names or list(PAIRS) + list(SAMPLES)

        def job(h, name):
            if name in PAIRS:
                fn, a, b = PAIRS[name]
                todo = [(name + '_A', fn, a), (name + '_B', fn, b)]
            else:
                todo = [(name, lambda hh, _v: SAMPLES[name](hh), None)]
            for tag, fn, v in todo:
                h.hwp.Clear(1)
                fn(h, v)
                p = os.path.join(out_dir, tag + '.hwpx')
                if not h.save(p):
                    return False
                sanitize(p)
                print('FIXTURE', tag, _facts(p), flush=True)
            return True
    elif phase == 'templates':
        import glob
        root = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                            r'HNC\Office 2024\HOffice130\Shared\HwpTemplate\Style\ko-KR')
        files = {os.path.splitext(os.path.basename(f))[0]: f for f in sorted(glob.glob(os.path.join(root, '*', '*.hwp')))}
        jobs = names or list(files)

        def job(h, name):
            # The action StyleTemplate returns False (explored 2026-11-14), but Hangul opens a template (.hwp) as a document:
            # its styles are what the template applies. Open + SaveAs HWPX, read-only on the install folder.
            if not h.open(files[name], fmt='HWP'):
                return False
            p = os.path.join(out_dir, 'tpl_' + name + '.hwpx')
            ok = h.save(p)
            print('TEMPLATE', name, 'saved', ok, _facts(p) if ok else '', flush=True)
            return bool(ok)
    elif phase == 'resave':
        from ..core import build
        jobs = names or list(RESAVE)

        def job(h, name):
            built = os.path.join(tmpdir.mkdtemp('ts_resave_'), name + '.hwpx')
            open(os.path.join(os.path.dirname(built), 'bullet.png'), 'wb').write(_png(24, 24))      # for picbullet_built
            build.write(RESAVE[name], built, os.path.dirname(built))
            h.hwp.Clear(1)
            if not h.open(built):
                print('RESAVE', name, 'OPEN FAILED', flush=True)
                return False
            p = os.path.join(out_dir, name + '.hwpx')
            ok = h.save(p)
            if ok:
                sanitize(p)
            print('RESAVE', name, 'saved', ok, _facts(p) if ok else '', flush=True)
            return bool(ok)
    else:
        print('phase', phase, 'is not here: see the module header')
        return 2
    res = run_jobs(jobs, job)
    print('RESULT', {k: v for k, v in res.items()})
    return 0 if all(res.values()) else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    return run_phase(argv[0], argv[1], argv[2:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
