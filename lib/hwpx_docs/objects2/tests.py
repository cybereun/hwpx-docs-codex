"""Self-test of the objects2 package (no Hangul needed): `hd selftest --only objects2`.

Every object kind and extra key builds to XML that parses and reads back to the same spec; every Hangul-made fixture reads, builds
and reads to the same spec; the viewer draws the kinds (DRAWS and the picture effects of the preview).
"""
from ..core import tmpdir
import glob
import json
import os
import struct
import zipfile
from xml.dom import minidom

from ..core import build, read
from . import draw, pdraw, shapes
from .corpus import png

HERE = os.path.dirname(os.path.abspath(__file__))
LN = '0.12mm solid #000000'          # what the reader gives when a spec has no `line`
BOX = dict(w=40, h=20, line=LN)
OBJECTS = {
    'polygon': dict(kind='polygon', points=[[0, 20], [20, 0], [40, 20]], fill='#FFE699', **BOX),
    'polyline': dict(kind='polygon', points=[[0, 20], [20, 0], [40, 20]], closed=False, **BOX),
    'curve': dict(kind='curve', segs=[['curve', 0, 20, 0, 0], ['curve', 0, 0, 40, 0], ['curve', 40, 0, 40, 20], ['line', 40, 20, 0, 20]], **BOX),
    'connector': dict(kind='connector', type='elbow', arrow='both', **BOX, **{'from': [0, 0], 'to': [40, 20]}),
    'connector_ref': dict(kind='connector', type='arc', arrow='end', from_ref={'id': 5, 'idx': 2}, **BOX,
                          **{'from': [0, 0], 'to': [40, 20]}),
    'textart': dict(kind='textart', text='Hello', shape='WAVE1', align='center', char_space=110, w=60, h=15, font='함초롬바탕',
                    fill='#0000FF', shadow={'type': 'right_top', 'x': 20, 'y': 20}),
    'group': dict(kind='group', w=70, h=28, items=[dict(kind='polygon', points=[[0, 20], [20, 0], [40, 20]], x=0, y=0, **BOX),
                                                   dict(kind='ellipse', x=28, y=7, w=30, h=15, line=LN, fill='#9DC3E6')]),
}


def sec(path):
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.xml', '.hpf'))}
    for t in parts.values():
        minidom.parseString(t)
    return parts


def rt(spec, name):
    """spec -> hwpx -> spec; the XML parses."""
    tmp = tmpdir.mkdtemp('hwpx_docs_o2_')
    out = os.path.join(tmp, name + '.hwpx')
    build.write(spec, out, base=tmp)
    parts = sec(out)
    return read.read(out, os.path.join(tmp, name + '.json')), parts


def objs(spec):
    return [b[k] for b in spec['body'] if isinstance(b, dict) for k in ('object', 'pic') if k in b]


def run():
    kinds()
    extras()
    ole_and_proof()
    drawing()
    fixtures()


def ole_and_proof():
    """The compound file writer / reader, the OLE object and 교정 부호 (spec -> hwpx -> spec)."""
    from . import ole, proof
    assert len(ole.COMPOBJ) == 76
    for size in (0, 17, 3000, 5000, 40000):                          # mini stream and regular sectors
        payload = bytes(range(256)) * (size // 256) + bytes(size % 256)
        c = ole.cfb([('\x01CompObj', ole.COMPOBJ), ('\x01Ole10Native', ole.package('가.txt', payload))])
        got = ole.read_cfb(c)
        assert got['\x01CompObj'] == ole.COMPOBJ and ole.unpackage(got['\x01Ole10Native']) == ('가.txt', payload), size
    tmp = tmpdir.mkdtemp('hwpx_docs_o2o_')
    open(os.path.join(tmp, 'a.txt'), 'wb').write(b'hello ole\n' * 30)
    spec = {'body': [{'ole': {'src': 'a.txt'}}, {'ole': {'src': 'a.txt', 'w': 30, 'h': 20, 'inline': False, 'wrap': 'square',
                                                         'pos': {'x': 5, 'y': 6, 'rel': 'page'}, 'caption': 'file'}}, 'text']}
    out = os.path.join(tmp, 'o.hwpx')
    build.write(spec, out, base=tmp)
    parts = sec(out)
    assert 'binaryItemIDRef="ole1"' in parts['Contents/section0.xml'] and 'binaryItemIDRef="ole2"' in parts['Contents/section0.xml']
    with zipfile.ZipFile(out) as z:
        assert z.read('BinData/ole1.ole')[:4] == len(z.read('BinData/ole1.ole')[4:]).to_bytes(4, 'little')
    back = read.read(out, os.path.join(tmp, 'o.json'))
    o = [b['ole'] for b in back['body'] if 'ole' in b]
    assert len(o) == 2 and o[0] == {'src': 'a.txt'} or o[0]['src'] == 'a.txt', o
    assert o[1]['caption']['text'] == 'file' and o[1]['pos']['rel'] == 'page' and _close(o[1]['w'], 30), o[1]
    assert open(os.path.join(tmp, 'a.txt'), 'rb').read() == b'hello ole\n' * 30, 'the file comes back byte for byte'
    # an embedded OLE object of another program: part and element kept, name and cached bitmap found
    comp = b'\x01\x00\xfe\xff\x03\x0a\x00\x00\xff\xff\xff\xff' + bytes(16) + struct.pack('<I', 25) + b'Microsoft Excel Worksheet\x00' + bytes(4) \
        + struct.pack('<I', 12) + b'Excel.Sheet.\x00'
    dib = struct.pack('<IiiHHIIiiII', 40, 2, 2, 1, 24, 0, 16, 0, 0, 0, 0) + bytes([0, 0, 255, 0, 255, 0, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0])   # 2 x 2, 24 bit
    pres = (struct.pack('<III', 0xFFFFFFFF, 8, 4) + struct.pack('<IIII', 1, 0xFFFFFFFF, 0, 0) + struct.pack('<III', 100, 100, len(dib)) + dib)
    c = ole.cfb([('\x01CompObj', comp), ('\x02OlePres000', pres), ('Workbook', b'x' * 5000)], bytes(16))
    other = struct.pack('<I', len(c)) + c
    out2 = os.path.join(tmp, 'x.hwpx')
    with zipfile.ZipFile(out) as zi, zipfile.ZipFile(out2, 'w', zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            zo.writestr(it, other if it.filename == 'BinData/ole1.ole' else zi.read(it.filename))
    back = read.read(out2, os.path.join(tmp, 'x.json'))
    x = next(b['ole'] for b in back['body'] if 'ole' in b)
    assert x['label'] == 'Microsoft Excel Worksheet' and x['raw'] == 'ole1.ole' and x['view'] == 'ole1.ole.png' and x['xml'].startswith('<hp:ole'), x
    assert open(os.path.join(tmp, 'ole1.ole.png'), 'rb').read()[:8] == b'\x89PNG\r\n\x1a\n'
    out3 = os.path.join(tmp, 'y.hwpx')
    build.write(back, out3, base=tmp)
    with zipfile.ZipFile(out3) as z:
        assert z.read('BinData/ole1.ole') == other, 'the OLE part is written back unchanged'
    again = read.read(out3, os.path.join(tmp, 'y.json'))
    assert json.dumps(again, sort_keys=True) == json.dumps(back, sort_keys=True), 'stable'
    # 교정 부호: the four kinds; the text keeps its own style
    marks = {'body': [{'p': [{'proof': k, 'text': t} for k, t in (('lineattach', ''), ('attach', '가나'), ('delete', '다라'),
                                                              ('clipping', '마바'))] + ['끝']}]}
    back, parts = rt(marks, 'proof')
    assert back['body'][0]['p'][:4] == marks['body'][0]['p'][:4] and parts['Contents/section0.xml'].count('PROOFREADING_MARKS_') == 4
    try:
        rt({'body': [{'p': [{'proof': 'nope', 'text': 'x'}]}]}, 'badproof')
        raise AssertionError('unknown mark accepted')
    except ValueError:
        pass
    # the viewer: a mark is drawn with its text; the OLE object is a dashed box with the file name
    spec = {'body': [{'p': [{'proof': 'delete', 'text': '지움'}, {'proof': 'attach', 'text': '붙임'}]}, {'ole': {'src': 'a.txt', 'inline': False,
                                                                                                         'pos': {'x': 10, 'y': 10, 'rel': 'page'}}}]}
    proof.prepare(spec)
    r = spec['body'][0]['p']
    assert r[0] == {'proofmark': {'kind': 'delete', 'text': '지움'}} and r[1] == {'proofmark': {'kind': 'attach', 'text': '붙임'}}, r
    from ..preview import render_pages            # through the layout: the text and one red path per mark line
    pm = os.path.join(tmp, 'marks.hwpx')
    build.write({'body': [{'p': [{'proof': 'delete', 'text': '지움'}, ' 글 ', {'proof': 'clipping', 'text': '둘러'}]}]}, pm, base=tmp)
    svg = render_pages(pm)[0][2]
    assert svg.count('stroke="#FF0000"') == 4 and svg.count('<path') >= 4, svg[:300]      # delete: 2 lines; clipping: box and curl
    pdraw.prepare(spec, tmp)
    svg = ''.join(pdraw.svg_ole(spec['body'][1]['ole'], 1, 2))
    assert 'stroke-dasharray' in svg and '>OLE a.txt<' in svg and spec['body'][1]['ole']['w'] == 26.72, svg


def kinds():
    for name, o in OBJECTS.items():
        for inline in (True, False):
            o2 = dict(o, inline=True) if inline else dict(o, inline=False, pos={'x': 10, 'y': 5, 'rel': 'page', 'hrel': 'paper', 'halign': 'center'},
                                                         wrap='behind_text', side='left_only', caption='설명')
            back, parts = rt({'body': [{'object': o2}, 'text']}, name)
            got = objs(back)[0]
            want = dict(o2)
            if inline:
                want.pop('inline')
            elif 'caption' in want:
                want['caption'] = {'side': 'bottom', 'label': '', 'number': False, 'text': '설명'}
            norm = lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)
            assert norm(got) == norm(want) or _close(got, want), (name, inline, got, want)
    # the group keeps its two children in order, and a plain child (ellipse) comes back as a plain child
    back, _ = rt({'body': [{'object': OBJECTS['group']}]}, 'group')
    g = objs(back)[0]
    assert [c['kind'] for c in g['items']] == ['polygon', 'ellipse'] and g['items'][1]['x'] == 28, g
    # 36 shapes of 글맵시; an unknown one is an error
    assert len(shapes.SHAPES) == 36 and shapes.SHAPES[17] == 'WAVE2'
    try:
        rt({'body': [{'object': dict(OBJECTS['textart'], shape='NOPE')}]}, 'bad')
        raise AssertionError('unknown shape accepted')
    except ValueError:
        pass


def _close(a, b, tol=0.01):
    """Equal up to rounding of lengths (HWPUNIT -> mm)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= tol
    return a == b


def extras():
    """Picture effects, crop, border, caption; shape position / caption / text flow."""
    tmp = tmpdir.mkdtemp('hwpx_docs_o2p_')
    png(os.path.join(tmp, 'a.png'), 60, 40)
    pic = {'src': 'a.png', 'w': 30, 'h': 20, 'bright': 40, 'contrast': -20, 'effect': 'gray', 'crop': [10, 0, 25, 5],
           'border': '0.353mm dot #FF0000', 'caption': {'text': '설명', 'side': 'left', 'gap': 5, 'width': 25}}
    spec = {'body': [{'pic': pic}, {'pic': dict(pic, inline=False, pos={'x': 5, 'y': 7, 'rel': 'page', 'hrel': 'paper', 'valign': 'bottom'},
                                                  wrap='square', side='right_only', caption='그림 설명')}, 'text']}
    out = os.path.join(tmp, 'p.hwpx')
    build.write(spec, out, base=tmp)
    parts = sec(out)
    s = parts['Contents/section0.xml']
    assert 'bright="40" contrast="-20" effect="GRAY_SCALE"' in s and 'style="DOT"' in s and 'color="#FF0000"' in s, 'picture xml'
    assert s.count('<hp:caption ') == 2 and 'textFlow="RIGHT_ONLY"' in s and 'vertAlign="BOTTOM"' in s and 'horzRelTo="PAPER"' in s
    back = read.read(out, os.path.join(tmp, 'p.json'))
    a, b = [x['pic'] for x in back['body'] if 'pic' in x] if all('pic' in x for x in back['body'][:2]) else (None, None)
    pics = [i['pic'] for blk in back['body'] for i in (blk['p'] if isinstance(blk.get('p'), list) else [blk]) if isinstance(i, dict) and 'pic' in i]
    a, b = pics
    for k in ('bright', 'contrast', 'effect', 'border'):
        assert a[k] == pic[k], (k, a)
    assert _close(a['crop'], pic['crop'], 0.1) and a['caption']['side'] == 'left' and _close(a['caption']['width'], 25), a
    assert b['inline'] is False and b['pos']['hrel'] == 'paper' and b['pos']['valign'] == 'bottom' and b['side'] == 'right_only', b
    assert b['caption'] == {'side': 'bottom', 'label': '그림', 'number': True, 'text': '그림 설명'} or b['caption']['text'] == '그림 설명', b
    # a drawing object: position, flow, text flow, caption
    rect = {'type': 'rect', 'x': 10, 'y': 5, 'w': 30, 'h': 12, 'rel': 'page', 'hrel': 'column', 'halign': 'right', 'flow': True,
            'overlap': False, 'wrap': 'square', 'side': 'largest_only', 'caption': {'text': '상자', 'side': 'top'}}
    back, parts = rt({'body': [{'p': '본문', 'shapes': [rect]}]}, 'rect')
    sh = back['body'][0]['shapes'][0]
    for k in ('rel', 'hrel', 'halign', 'flow', 'overlap', 'wrap', 'side'):
        assert sh[k] == rect[k], (k, sh)
    assert sh['caption']['side'] == 'top' and sh['caption']['text'] == '상자', sh
    # no extra key: the XML is what core makes (no caption, BOTH_SIDES)
    _, parts = rt({'body': [{'p': '', 'shapes': [{'type': 'rect', 'x': 1, 'y': 1, 'w': 10, 'h': 10}]}]}, 'plain')
    assert 'hp:caption' not in parts['Contents/section0.xml'] and 'textFlow="BOTH_SIDES"' in parts['Contents/section0.xml']


def warp():
    """글맵시 text in the 36 measured shapes (textart_warp): every shape draws, the strips follow the measured corners."""
    from . import textart_data as td, textart_warp as tw
    assert sorted(td.QUADS) == sorted(shapes.SHAPES) and all(len(b) == 20 and all(len(q) == 4 for q in b) for b in td.QUADS.values())
    for name in shapes.SHAPES:
        out = tw.svg(dict(kind='textart', w=60, h=20, text='글맵시', shape=name), 10, 20)
        s = ''.join(out)
        assert s.count('<clipPath') == tw.N and s.count('<use') == tw.N and 'font-size' in s, name
    # the hexagon is an unwarped box with the corners cut: its top is flat in the middle; the parallelogram shifts the top to the right
    (t0, _), (t1, _) = tw.at(tw.nodes('PARALLELOGRAM'), 0.0), tw.at(tw.nodes('PARALLELOGRAM'), 1.0)
    assert t1[0] - t0[0] > 0.6 and abs(t0[1] - t1[1]) < 0.05, (t0, t1)
    top_a, _ = tw.at(tw.nodes('HEXAGON'), 0.5)
    assert top_a[1] < 0.1, top_a
    assert tw.ink_box('가나다')[1] < tw.ink_box('gjpq')[1], 'a descender gives more room below'
    s = ''.join(tw.svg(dict(kind='textart', w=60, h=20, text='Shadow', shape='WAVE2', shadow={'type': 'left_top', 'x': 20, 'y': 20}), 0, 0))
    assert 'translate(4 4)" fill="#000000"' in s, 'the black shadow, 20 % of the height right and down'
    assert tw.svg(dict(kind='textart', w=60, h=20, text='x', shape='NOPE'), 0, 0) is None


def drawing():
    warp()
    for name, o in OBJECTS.items():
        out = draw.svg(o, 10, 20)
        assert out and all(isinstance(x, str) and x.startswith('<') for x in out), name
    s = ''.join(draw.svg(OBJECTS['polygon'], 10, 20))
    assert '<polygon points="10,40 30,20 50,40"' in s and 'fill="#FFE699"' in s and 'stroke-width="0.12"' in s
    assert '<polyline' in ''.join(draw.svg(OBJECTS['polyline'], 0, 0))
    assert ' C' in ''.join(draw.svg(OBJECTS['curve'], 0, 0)) and ' L' in ''.join(draw.svg(OBJECTS['curve'], 0, 0)), 'Bezier and line'
    e = ''.join(draw.svg(OBJECTS['connector'], 0, 0))
    assert ' H' in e and e.count('<polygon') == 2, 'elbow with two arrow heads'
    assert '>Hello<' in ''.join(draw.svg(OBJECTS['textart'], 0, 0)) and draw.svg({'kind': 'nope'}, 0, 0) is None
    assert ''.join(draw.svg(OBJECTS['group'], 0, 0)).count('<polygon') == 1 and '<ellipse' in ''.join(draw.svg(OBJECTS['group'], 0, 0))
    # caption room: the object grows, the caption text is drawn under it
    o = dict(OBJECTS['polygon'], caption='설명')
    spec = {'body': [{'object': o}]}
    pdraw.prepare(spec, '.')
    g = spec['body'][0]['object']
    assert g['_box'] == (40, 20) and g['h'] > 20 and g['w'] == 40, g
    assert '>설명<' in ''.join(pdraw.svg_object(g, 0, 0)), 'an object caption has no number unless it asks for one'
    # an aligned floating object goes to the layout as a floating shape; halign, hrel and vpos (valign) are passed on (layout.shape_at)
    al = {'body': [{'object': dict(OBJECTS['polygon'], inline=False, pos={'x': 0, 'y': 0, 'rel': 'page', 'halign': 'center', 'valign': 'center'})},
                   {'ole': {'src': 'a.txt', 'inline': False, 'pos': {'rel': 'paper', 'valign': 'bottom'}}}]}
    pdraw.prepare(al, '.')
    sh, so = al['body'][0]['shapes'][0], al['body'][1]['shapes'][0]
    assert (sh['halign'], sh['vpos'], sh['rel'], sh['hrel']) == ('center', 'center', 'page', 'page') and 'object' not in al['body'][0], sh
    assert so['vpos'] == 'bottom' and so['rel'] == 'paper' and 'ole' not in al['body'][1], so
    # the caption of a rect: a label shape next to it (the text box keeps its own drawing by the layout)
    sp = {'body': [{'p': '', 'shapes': [{'type': 'rect', 'x': 10, 'y': 10, 'w': 30, 'h': 12, 'caption': {'text': '상자', 'side': 'top'}},
                                       {'type': 'ellipse', 'x': 10, 'y': 60, 'w': 30, 'h': 12, 'caption': '타원', 'text': '글'}]}]}
    pdraw.prepare(sp, '.')
    labs = [s for s in sp['body'][0]['shapes'] if s['type'] == 'object']
    assert len(labs) == 2 and labs[0]['y'] < 10 and labs[1]['y'] > 72 and labs[1]['x'] == 10, labs
    assert '>상자<' in ''.join(draw.svg({'kind': 'label', 'w': 30, 'h': 5, 'text': '상자'}, 0, 0))
    # picture effects in the viewer
    tmp = tmpdir.mkdtemp('hwpx_docs_o2d_')
    png(os.path.join(tmp, 'a.png'), 60, 40)
    spec = {'body': [{'pic': {'src': 'a.png', 'w': 30, 'h': 20, 'effect': 'bw', 'bright': 10, 'crop': [0, 0, 50, 0], 'border': '0.2mm solid #00FF00'}}]}
    pdraw.prepare(spec, tmp)
    item = spec['body'][0]['picfx']
    r = pdraw.picfx(item, {})
    svg = ''.join(r['draw'](5, 6))
    assert r['w'] == 30 and r['h'] == 20 and 'clip-path' in svg and 'feColorMatrix' in svg and 'discrete' in svg and 'stroke="#00FF00"' in svg, svg
    assert 'width="60"' in svg, 'a half-cropped picture is drawn twice as wide, clipped'


def fixtures():
    files = sorted(glob.glob(os.path.join(HERE, 'fixtures', '*.hwpx')))
    assert files, 'no objects2 fixtures'
    tmp = tmpdir.mkdtemp('hwpx_docs_o2f_')
    bad, seen = [], set()
    for f in files:
        n = os.path.splitext(os.path.basename(f))[0]
        if n.startswith('probe_'):
            continue
        a = read.read(f, os.path.join(tmp, n + '.a.json'))
        build.write(a, os.path.join(tmp, n + '.hwpx'), base=tmp)
        b = read.read(os.path.join(tmp, n + '.hwpx'), os.path.join(tmp, n + '.b.json'))
        norm = lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False).lower()       # core.read keeps the case of a picture's extension
        if norm(a) != norm(b):
            bad.append(n)
        for blk in a['body']:
            if isinstance(blk, dict):
                seen |= {k for k in ('object', 'pic', 'shapes') if k in blk}
        text = json.dumps(a, ensure_ascii=False)
        assert '"xml"' not in text, f'{n}: an object was kept as raw XML'
    assert not bad, f'{len(bad)} objects2 fixtures not stable: {bad[:8]}'
    assert {'object', 'shapes'} <= seen, seen
    # what the Hangul-made samples say (the pairs of rules.md)
    def one(n, key):
        spec = read.read(os.path.join(HERE, 'fixtures', n + '.hwpx'), os.path.join(tmp, n + '.json'))
        return next(x for blk in spec['body'] for x in ([blk] + (blk['p'] if isinstance(blk.get('p'), list) else [])) if isinstance(x, dict) and key in x)[key]
    assert one('pic_bright_B', 'pic')['bright'] == 40 and 'bright' not in one('pic_bright_A', 'pic')
    assert one('pic_contrast_B', 'pic')['contrast'] == 40
    assert one('pic_effect_gray', 'pic')['effect'] == 'gray' and one('pic_effect_bw', 'pic')['effect'] == 'bw'
    assert one('pic_border_C', 'pic')['border'].endswith('solid #FF0000') and one('pic_border_D', 'pic')['border'].split()[1] == 'dot'
    assert one('pic_crop_B', 'pic')['crop'] == [0.0, 0.0, 50.0, 0.0]
    assert [one(f'pic_caption_side_{i}', 'pic')['caption']['side'] for i in range(4)] == ['left', 'right', 'top', 'bottom']
    assert one('pic_caption_wide', 'pic')['caption']['width'] == 42.333 and one('pic_caption_B', 'pic')['caption']['number'] is True
    assert [one(f'rect_wrap_{i}', 'shapes')[0]['wrap'] for i in range(4)] == ['square', 'top_and_bottom', 'behind_text', 'in_front_of_text']
    assert [one(f'rect_anchor_{n}', 'shapes')[0].get('hrel', 'dflt') for n in ('paper', 'page', 'para', 'para_column')] == ['dflt', 'dflt', 'para', 'dflt']
    c = one('rect_align_center', 'shapes')[0]
    assert c['rel'] == 'page' and c['halign'] == 'center' and c['vpos'] == 'center' and 'valign' not in c, c
    assert one('rect_flow_off', 'shapes')[0]['flow'] is False
    assert one('ta_shapes', 'object')['kind'] == 'textart'
    names = [x['object']['shape'] for x in read.read(os.path.join(HERE, 'fixtures', 'ta_shapes.hwpx'), os.path.join(tmp, 't.json'))['body']
             if isinstance(x, dict) and 'object' in x]
    assert sorted(names) == sorted(shapes.SHAPES), 'all 36 글맵시 shapes read back'
    assert one('connect_stroke', 'object')['type'] == 'elbow' and one('connect_arc', 'object')['type'] == 'arc'
    assert one('curve_poly', 'object')['segs'][0][0] == 'line' and one('curve_bezier', 'object')['segs'][0][0] == 'curve'
    assert len(one('group_polys', 'object')['items']) == 2 and len(one('polygon_A', 'object')['points']) == 3
    print(f'  objects2 fixtures stable {len(files)}/{len(files)} (probe samples skipped)')
