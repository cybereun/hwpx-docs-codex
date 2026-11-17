"""Hangul COM jobs that make the samples and pairs of the objects2 package. Dev tool: needs Hangul 2024 and pywin32.
Not run by `hd selftest`. Run it ONLY in a Hangul window that the orchestrator scheduled:

    python -m hwpx_docs.objects2.corpus [group ...]        (cwd = lib/)

Groups: pic (C6.02), wrap (C6.12, C6.13), caption (C6.14), group (C6.08: only the two ungrouped shapes; the group itself
is hand-written XML, see rules OB13), textart (C6.11), probe (C8.01-C8.04: which control ids and actions exist). One hidden
Hangul per group (window never shown, never activated; set HWPX_DOCS_SECURITY_MODULE for the file-access module), Quit at the
end. Each job writes `fixtures/<job>.hwpx` (creator/lastsaveby `hwpx-docs`) and every try, property name and error goes to
`fixtures/corpus.log`; a failing step is logged and the batch goes on (after 1-2 saves Hangul may stop answering when other
Hangul windows run: run the failed job again, `python -m hwpx_docs.objects2.corpus` takes group names only). Jobs make new
files only (no Open). The pic_crop_*, polygon_A, curve_*, group_polys, connect_*, build_* fixtures are not made here: they were
written as OWPML, opened and saved again by Hangul (rules.md).
"""
from ..core import tmpdir
import os
import re
import struct
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, 'fixtures')
LOG = []


def log(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True)
    LOG.append(line)


def png(path, w=240, ht=160):
    """A small gradient picture (generic content)."""
    rows = b''.join(b'\x00' + b''.join(bytes([40 + x * 200 // w, 90 + y * 120 // ht, 170]) for x in range(w)) for y in range(ht))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, ht, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


# ---- COM helpers ------------------------------------------------------------------------------------------------------
def ctrls(h, cid='gso'):
    c, out = h.hwp.HeadCtrl, []
    while c:
        if c.CtrlID.strip() == cid:
            out.append(c)
        c = c.Next
    return out


def insert(h, ctrl_id='$rec', w=11339, hgt=5669):
    """Insert a drawing object at the caret (InsertCtrl with a ShapeObject set; found by probing, 2026-11-14)."""
    hw = h.hwp
    s = hw.HParameterSet.HShapeObject.HSet
    hw.HAction.GetDefault('DrawObjCreatorRectangle', s)
    s.SetItem('Width', w)
    s.SetItem('Height', hgt)
    h.guard()
    return hw.InsertCtrl(ctrl_id, s)


def picture(h):
    import uuid
    path = os.path.join(tmpdir.mkdtemp('hwpcom_'), uuid.uuid4().hex + '.png')
    png(path)
    h.guard()
    h.hwp.InsertPicture(path, True, 0, False, False, 0)
    return ctrls(h)[-1]


def setp(ctrl, sub=None, **items):
    """Set items of the ctrl's property set (or of its sub set `sub`), write them back. Logs the item names it could not set."""
    ps = ctrl.Properties
    tgt = ps.Item(sub) if sub else ps
    for k, v in items.items():
        try:
            tgt.SetItem(k, v)
        except Exception as e:
            log('  SETITEM FAIL', sub or '', k, repr(e)[:80])
    if sub:
        ps.SetItem(sub, tgt)
    ctrl.Properties = ps


def names(h, cls):
    """Item names of a parameter set class (introspection of the type library, written to the log)."""
    try:
        o = getattr(h.hwp.HParameterSet, cls)
        n = [a for a in dir(o) if not a.startswith('_') and a not in ('HSet', 'CLSID', 'CreateItemArray', 'coclass_clsid')]
        log('NAMES', cls, n)
        return n
    except Exception as e:
        log('NAMES FAIL', cls, repr(e)[:60])
        return []


def body(h):
    h.new()
    for i in range(3):
        h.para('개체 둘레 글입니다. ' * 6)


def save(h, name):
    path = os.path.join(FIX, name + '.hwpx')
    ok = h.save(path)
    if ok and os.path.exists(path):
        with zipfile.ZipFile(path) as z:
            items = {n: z.read(n) for n in z.namelist()}
        items['Contents/content.hpf'] = re.sub(rb'(name="(?:creator|lastsaveby)" content="text">)[^<]*', rb'\g<1>hwpx-docs',
                                               items['Contents/content.hpf'])
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:      # mimetype stays first, stored
            for n in sorted(items, key=lambda n: n != 'mimetype'):
                z.writestr(zipfile.ZipInfo(n) if n == 'mimetype' else n, items[n],
                           zipfile.ZIP_STORED if n == 'mimetype' else zipfile.ZIP_DEFLATED)
    log('SAVED' if ok else 'SAVE FAIL', name)


# ---- jobs: each is (name, function(h)) -------------------------------------------------------------------------------
def pic_job(sub, **items):
    def job(h):
        body(h)
        c = picture(h)
        if items:
            setp(c, sub, **items)
    return job


def pic_jobs(h):
    for n in ('HDrawImageAttr', 'HDrawImageScissoring', 'HDrawLineAttr', 'HCaption', 'HShapeObject'):
        names(h, n)
    return {
        'pic_base': pic_job(None),
        'pic_bright_A': pic_job('ShapeDrawImageAttr', Brightness=0), 'pic_bright_B': pic_job('ShapeDrawImageAttr', Brightness=40),
        'pic_contrast_A': pic_job('ShapeDrawImageAttr', Contrast=0), 'pic_contrast_B': pic_job('ShapeDrawImageAttr', Contrast=40),
        'pic_effect_gray': pic_job('ShapeDrawImageAttr', PicEffectTo=1), 'pic_effect_bw': pic_job('ShapeDrawImageAttr', PicEffectTo=2),
        'pic_border_B': pic_job('ShapeDrawLineAttr', Style=1, Width=100, Color=0),   # `Style` (capital S); 0 = no line
        'pic_border_W': pic_job('ShapeDrawLineAttr', Style=1, Width=300, Color=0),
        'pic_border_C': pic_job('ShapeDrawLineAttr', Style=1, Width=100, Color=255),
        'pic_border_D': pic_job('ShapeDrawLineAttr', Style=2, Width=100, Color=0),
        'pic_border_E': pic_job('ShapeDrawLineAttr', Style=3, Width=100, Color=0),
    }


def wrap_job(**items):
    def job(h):
        body(h)
        h.hwp.MovePos(2)                                    # to the start of the document
        c = insert(h)
        setp(c, **items)
    return job


def wrap_jobs(h):
    jobs = {}
    for n in range(4):                                       # the diff of the four files gives the code -> XML textWrap map
        jobs[f'rect_wrap_{n}'] = wrap_job(TreatAsChar=0, TextWrap=n)
    for name, (v, hz) in {'paper': (0, 0), 'page': (1, 1), 'para': (2, 3), 'para_column': (2, 2)}.items():
        jobs[f'rect_anchor_{name}'] = wrap_job(TreatAsChar=0, TextWrap=0, VertRelTo=v, HorzRelTo=hz, VertOffset=5000, HorzOffset=8000)
    jobs['rect_align_center'] = wrap_job(TreatAsChar=0, TextWrap=0, VertRelTo=1, HorzRelTo=1, VertAlign=1, HorzAlign=1)
    jobs['rect_flow_off'] = wrap_job(TreatAsChar=0, TextWrap=0, FlowWithText=0, AllowOverlap=0)
    return jobs


def caption_job(kind, attach):
    def job(h):
        body(h)
        c = picture(h) if kind == 'pic' else insert(h)
        if attach:
            try:
                h.hwp.SelectCtrl(c)
            except Exception as e:
                log('  SelectCtrl FAIL', repr(e)[:80])
            h.run('ShapeObjAttachCaption')
            h.text('그림 1 설명')
    return job


def caption_side_job(**items):
    def job(h):
        body(h)
        c = picture(h)
        h.run('ShapeObjAttachCaption')
        h.text('설명')
        c = ctrls(h)[-1]
        setp(c, 'ShapeCaption', **items)
    return job


def caption_jobs(h):
    jobs = {f'{k}_caption_{t}': caption_job(k, a) for k in ('pic', 'rect') for t, a in (('A', 0), ('B', 1))}
    for n in range(4):                                       # Side code -> side name, from the diff of the four files
        jobs[f'pic_caption_side_{n}'] = caption_side_job(Side=n)
    jobs['pic_caption_wide'] = caption_side_job(Width=12000, Gap=1500)
    return jobs


def group_job(grouped):
    def job(h):
        body(h)
        a, b = insert(h), insert(h, '$ell')
        setp(a, TreatAsChar=0, TextWrap=3, VertRelTo=0, HorzRelTo=0, VertOffset=4000, HorzOffset=4000)
        setp(b, TreatAsChar=0, TextWrap=3, VertRelTo=0, HorzRelTo=0, VertOffset=6000, HorzOffset=9000)
        if grouped:
            for how in ('SelectCtrl2', 'ShapeObjSelectAll', 'SelectAll'):
                try:
                    if how == 'SelectCtrl2':
                        h.hwp.SelectCtrl(a, 0)                      # (ctrl, option): both arguments are required
                        h.hwp.SelectCtrl(b, 1)                      # option 1: add to the selection (assumed; logged)
                    else:
                        h.run(how)
                    h.run('ShapeObjGroup')
                    log('  GROUP via', how)
                    break
                except Exception as e:
                    log('  GROUP FAIL', how, repr(e)[:80])
    return job


def group_jobs(h):
    return {'group_A': group_job(False), 'group_B': group_job(True)}


# ---- probe: which ids and actions exist (one Hangul per candidate: a bad id can crash Hangul) -----------------------
PROBE_IDS = {'connector': ['$col', '$cnl'], 'textart': ['$tar', '$txa', '$art'], 'polygon': ['$pol'], 'curve': ['$cur'],
             'ole': ['$ole']}
PROBE_ACTIONS = '''ProofreadingMark ProofreadMark InsertProofreadMark ProofreadSymbol CorrectionSign InsertCorrectionSign ProofSign
DrawObjTemplateLoad DrawObjTemplateSave InsertCorrectionMark DocCorrectionMark ProofreadingSymbols InsertTextart ConnectLineCreate
DrawObjCreatorConnectLine DrawObjCreatorConnector InsertOleObject OleCreation InsertObject InsertFile'''.split()


def probe_actions(h):
    for n in PROBE_ACTIONS:
        try:
            log('ACTION', n, 'OK' if h.hwp.CreateAction(n) is not None else 'none')
        except Exception as e:
            log('ACTION', n, 'ERR', repr(e)[:40])
    for n in ('HDrawTextart', 'HDrawConnectLine', 'HOleCreation', 'HDrawCoordInfo', 'HDrawEditDetail', 'HDrawLayOut'):
        names(h, n)


def run_group(title, make_jobs, only=None):
    from ..render.hwpcom import Hwp
    os.makedirs(FIX, exist_ok=True)
    with Hwp(visible=False) as h:
        jobs = make_jobs(h)
        for name, fn in jobs.items():
            if only and name not in only:
                continue
            h.hwp.Clear(1)
            try:
                fn(h)
                save(h, name)
            except Exception as e:
                log('JOB FAIL', name, repr(e)[:160])
            if h.killed:
                log('HANGUL KILLED at', name)
                break


def run_probe(h_unused=None):
    from ..render.hwpcom import Hwp
    os.makedirs(FIX, exist_ok=True)
    with Hwp(visible=False) as h:
        probe_actions(h)
    for kind, ids in PROBE_IDS.items():
        for cid in ids:
            try:
                with Hwp(visible=False) as h:
                    h.new()
                    h.text('abc')
                    insert(h, cid)
                    log('PROBE', kind, cid, 'inserted', len(ctrls(h)))
                    save(h, f'probe_{kind}_{cid[1:]}')
            except Exception as e:
                log('PROBE', kind, cid, 'FAIL', repr(e)[:100])


# ---- textart (글맵시): `TextArtCreate` makes it; ShapeDrawTextart of ctrl.Properties changes it (text cannot be set) ---
def textart(h, **items):
    hw = h.hwp
    ps = hw.HParameterSet.HDrawTextart
    hw.HAction.GetDefault('TextArtCreate', ps.HSet)
    h.guard()
    hw.HAction.Execute('TextArtCreate', ps.HSet)
    c = ctrls(h)[0]                  # a new object at the same caret place comes first in the control list
    if items:
        setp(c, 'ShapeDrawTextart', **items)
    return c


def textart_job(*variants):
    def job(h):
        body(h)
        for v in variants:
            textart(h, **v)
    return job


def textart_jobs(h):
    return {'ta_shapes': textart_job(*[{'Shape': i} for i in range(0, 36)]),
            'ta_align': textart_job(*[{'AlignType': i} for i in range(3)]),
            'ta_spacing': textart_job({}, {'CharSpacing': 150}, {'LineSpacing': 160}),
            'ta_shadow': textart_job({'ShadowType': 1, 'ShadowOffsetX': 20, 'ShadowOffsetY': 20}, {'ShadowType': 2}),
            'ta_font': textart_job({'FontName': '굴림'}, {'FontName': '바탕'})}


GROUPS = {'pic': pic_jobs, 'wrap': wrap_jobs, 'caption': caption_jobs, 'group': group_jobs, 'textart': textart_jobs}


def main(argv):
    what = argv or ['pic', 'wrap', 'caption', 'group', 'probe']
    for g in what:
        log('== group', g)
        if g == 'probe':
            run_probe()
        else:
            run_group(g, GROUPS[g])
    open(os.path.join(FIX, 'corpus.log'), 'a', encoding='utf-8').write('\n'.join(LOG) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
