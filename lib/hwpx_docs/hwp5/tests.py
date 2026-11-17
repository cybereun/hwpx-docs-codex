"""Self-test of hwp5 on a document it builds (no fixture, no Hangul); `hd hwp selftest DIR` also runs every .hwp in DIR.

The built document has what a received form has: a section with A4 page, body paragraphs with their line layout,
a 2 x 2 table whose labels are 성명 / 연락처, check boxes (☐), a click-here field, PrvText and PrvImage. The test edits it,
checks it with the guard (same form, row growth, a tampered cell, residue), reads it as a spec and draws it.
"""
import os
import struct
import sys

from ..core import tmpdir
from . import cfb, fmt

VERSION = 0x05000300                     # 5.0.3.0


def rec(tag, level, data):
    return [tag, level, data]


def ext_ctrl(code, cid):
    return struct.pack('<H', code) + cid[::-1].encode('latin-1') + bytes(8) + struct.pack('<H', code)


def text_bytes(*parts):
    out = b''
    for p in parts:
        out += p if isinstance(p, bytes) else p.encode('utf-16-le')
    return out + struct.pack('<H', 13)


def lineseg(width_hu, lines=1):
    return b''.join(struct.pack('<IiiiiiiiI', 0, i * 1600, 1000, 1000, 850, 600, 0, width_hu, 0x60000) for i in range(lines))


def para(level, text, shape=0, segw=42520, lines=1, ctrl_mask=0):
    n = len(text) // 2
    head = struct.pack('<IIHBBHHHI', n, ctrl_mask, 0, 0, 0, 1, 0, lines, 0)
    return [rec(0x42, level, head), rec(0x43, level + 1, text), rec(0x44, level + 1, struct.pack('<II', 0, shape)),
            rec(0x45, level + 1, lineseg(segw, lines))]


def docinfo():
    T = fmt.T
    faces = [rec(T['FACE_NAME'], 0, b'\x00' + struct.pack('<H', 5) + '함초롬바탕'.encode('utf-16-le')) for _ in range(7)]
    none_side = struct.pack('<BBI', 0, 1, 0)
    solid = struct.pack('<BBI', 1, 1, 0)
    bf1 = struct.pack('<H', 0) + none_side * 4 + none_side + struct.pack('<I', 0)
    bf2 = struct.pack('<H', 0) + solid * 4 + none_side + struct.pack('<I', 0)
    cs = (struct.pack('<7H', *[0] * 7) + bytes([100] * 7) + bytes(7) + bytes([100] * 7) + bytes(7)
          + struct.pack('<iIbb', 1000, 0, 0, 0) + struct.pack('<IIII', 0, 0, 0xFFFFFFFF, 0xB2B2B2) + struct.pack('<HI', 2, 0))
    ps = struct.pack('<Iiiiiii', 1 << 8, 0, 0, 0, 0, 0, 160) + struct.pack('<HHH', 0, 0, 1) + bytes(8) + struct.pack('<III', 0, 0, 160)
    ids = struct.pack('<18i', 0, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 0, 0, 1, 1, 0, 0, 0)
    style = struct.pack('<H', 3) + '바탕글'.encode('utf-16-le') + struct.pack('<H', 6) + b'Normal'.decode().encode('utf-16-le') \
        + struct.pack('<BBhHH', 0, 0, 1042, 0, 0)
    recs = ([rec(T['DOCUMENT_PROPERTIES'], 0, struct.pack('<7H3I', 1, 1, 1, 1, 1, 1, 1, 0, 0, 0)),
             rec(T['ID_MAPPINGS'], 0, ids)] + faces + [rec(T['BORDER_FILL'], 0, bf1), rec(T['BORDER_FILL'], 0, bf2),
                                                        rec(T['CHAR_SHAPE'], 0, cs), rec(T['TAB_DEF'], 0, struct.pack('<II', 0, 0)),
                                                        rec(T['PARA_SHAPE'], 0, ps), rec(T['STYLE'], 0, style)])
    return fmt.unrecords(recs)


def section():
    T = fmt.T
    out = []
    p0 = text_bytes(ext_ctrl(2, 'secd'), ext_ctrl(2, 'cold'))
    out += para(0, p0, ctrl_mask=1 << 2)
    out.append(rec(T['CTRL_HEADER'], 1, b'secd'[::-1] + bytes(18) + struct.pack('<H', 0) + bytes(8)))
    out.append(rec(T['PAGE_DEF'], 2, struct.pack('<10I', 59528, 84186, 8504, 8504, 5668, 4252, 4252, 4252, 0, 0)))
    out.append(rec(T['CTRL_HEADER'], 1, b'cold'[::-1] + struct.pack('<HH', 1 << 2, 0)))
    out += para(0, text_bytes('아래 표에 적어 주십시오.'))
    out += para(0, text_bytes(ext_ctrl(11, 'tbl ')), ctrl_mask=1 << 11)
    attr = (2 << 3) | (2 << 8) | (1 << 13) | (1 << 21)
    out.append(rec(T['CTRL_HEADER'], 1, b'tbl '[::-1] + struct.pack('<IiiIIi4hIih', attr, 0, 0, 42520, 5670, 0,
                                                                     283, 283, 283, 283, 1, 0, 0)))
    out.append(rec(T['TABLE'], 2, struct.pack('<IHHH4H2HH', 2 | 4, 2, 2, 0, 510, 510, 141, 141, 2, 2, 2)))
    cells = [('성명', 0, 0, 8504), ('', 1, 0, 34016), ('연락처', 0, 1, 8504), ('○○○', 1, 1, 34016)]
    for t, col, row, w in cells:
        out.append(rec(T['LIST_HEADER'], 2, struct.pack('<iIHHHHII4HHI', 1, 1 << 5, col, row, 1, 1, w, 2835,
                                                         510, 510, 141, 141, 2, w - 1020)))
        out += para(2, text_bytes(t), segw=w - 1020)
    out += para(0, text_bytes('☐ 동의함  ☐ 동의하지 않음'))
    clk = text_bytes('성함: ', ext_ctrl(3, '%clk'), struct.pack('<8H', 4, 0, 0, 0, 0, 0, 0, 4))
    out += para(0, clk, ctrl_mask=(1 << 3) | (1 << 4))
    out.append(rec(T['CTRL_HEADER'], 1, b'%clk'[::-1] + struct.pack('<IBH', 0, 0, 0) + struct.pack('<IH', 0, 0)))
    out += para(0, text_bytes('이 문단은 원래 문장으로 스무 글자를 넘게 쓴 문장입니다.'))
    last = out[-4]
    last[2] = struct.pack('<I', struct.unpack_from('<I', last[2])[0] | 0x80000000) + last[2][4:]   # last in its list
    return fmt.unrecords(out)


def build(path, prv='미리보기 옛 글'):
    fh = fmt.SIGNATURE.ljust(32, b'\x00') + struct.pack('<II', VERSION, fmt.COMPRESSED) + bytes(256 - 40)
    root = cfb.Entry('Root Entry', cfb.ROOT)
    root.add(cfb.Entry('FileHeader', cfb.STREAM, fh))
    root.add(cfb.Entry('DocInfo', cfb.STREAM, fmt.deflate(docinfo())))
    body = root.add(cfb.Entry('BodyText', cfb.STORAGE))
    body.add(cfb.Entry('Section0', cfb.STREAM, fmt.deflate(section())))
    root.add(cfb.Entry('PrvText', cfb.STREAM, prv.encode('utf-16-le')))
    from .edit import gif_white
    root.add(cfb.Entry('PrvImage', cfb.STREAM, gif_white(4, 6)))
    with open(path, 'wb') as f:
        f.write(cfb.build(root))
    return path


def check_file(path, out=print):
    """Checks that need no Hangul on any .hwp: rewrite with no change = same streams; one replaced letter keeps every
    other record; the guard sees the same form; the spec reads and the pages draw. Returns the number of failures."""
    from . import edit, guard
    fails = 0
    d = tmpdir.mkdtemp('hwp5_fx_')
    try:
        doc = edit.Doc(path)
    except Exception as e:                          # protected, HWP 3, track changes ...
        out(f'HWP5 SKIP {os.path.basename(path)}: {str(e)[:80]}')
        return 0
    same = os.path.join(d, 'same.hwp')
    pk = fmt.Package(path)
    for s in pk.sections:
        pk.put_records(s, pk.records(s))
    pk.save(same)
    a, b = fmt.Package(path), fmt.Package(same)
    if any(a.stream(p) != b.stream(p) for p in a.streams):
        out(f'HWP5 FAIL {os.path.basename(path)}: rewrite changed a stream')
        fails += 1
    text = doc.text()
    ch = next((c for c in text if '가' <= c <= '힣'), None)
    if ch:
        doc.replace(ch, '가' if ch != '가' else '나')
        dst = doc.save(os.path.join(d, 'edited.hwp'))
        lines = []
        guard.report(path, dst, out=lines.append)
        if not any('GUARD STRUCTURE same' in x for x in lines):
            out(f'HWP5 FAIL {os.path.basename(path)}: ' + '; '.join(lines))
            fails += 1
        for s in fmt.Package(dst).sections:
            recs = fmt.Package(dst).records(s)
            for p in fmt.paragraphs(recs):
                n = struct.unpack_from('<I', recs[p.head][2])[0] & 0x7FFFFFFF
                t = recs[p.parts[0x43]][2] if 0x43 in p.parts else None
                if (len(t) // 2 if t is not None else 1) != n:
                    out(f'HWP5 FAIL {os.path.basename(path)}: char count of a paragraph')
                    fails += 1
                    break
    try:
        from . import tospec
        tospec.read(path, os.path.join(d, 'spec.json'), placeholders=True)
    except Exception as e:
        out(f'HWP5 FAIL {os.path.basename(path)}: spec {type(e).__name__} {e}')
        fails += 1
    out(f'HWP5 {"OK" if not fails else "FAIL"} {os.path.basename(path)}')
    return fails


def owpml_para(level, text, mask=0, last=False, segw=42520):
    """A paragraph with a 24-byte PARA_HEADER as Hangul 2018+ writes it (the converter reads the instance id and the merge flag)."""
    head = struct.pack('<IIHBBHHHIH', len(text) // 2 | (0x80000000 if last else 0), mask, 0, 0, 0, 1, 0, 1, 0x1234, 0)
    return [rec(0x42, level, head), rec(0x43, level + 1, text), rec(0x44, level + 1, struct.pack('<II', 0, 0)),
            rec(0x45, level + 1, lineseg(segw))]


def owpml_section(extra=()):
    """A section as Hangul writes one: the section definition (page, notes, borders), columns, a text paragraph, a 1 x 1 table."""
    T = fmt.T
    out = owpml_para(0, text_bytes(ext_ctrl(2, 'secd'), ext_ctrl(2, 'cold')), mask=1 << 2)
    out.append(rec(T['CTRL_HEADER'], 1, b'dces' + struct.pack('<IHHHIHHHHHH', 0, 1134, 0, 0, 8000, 1, 0, 0, 0, 0, 0) + bytes(19)))
    out.append(rec(T['PAGE_DEF'], 2, struct.pack('<10I', 59528, 84188, 8504, 8504, 5668, 4252, 4252, 4252, 0, 0)))
    out += [rec(T['FOOTNOTE_SHAPE'], 2, struct.pack('<IHHHHiHHHBBI', 0, 0, 0, 41, 1, -1, 850, 567, 283, 1, 1, 0)) for _ in range(2)]
    out += [rec(T['PAGE_BORDER_FILL'], 2, struct.pack('<I4hH', 1, 1417, 1417, 1417, 1417, 1)) for _ in range(3)]
    out.append(rec(T['CTRL_HEADER'], 1, b'cold'[::-1] + struct.pack('<HHHBBI', 0x1004, 0, 0, 0, 0, 0)))
    out += owpml_para(0, text_bytes('안녕하세요 hello'))
    out += owpml_para(0, text_bytes(ext_ctrl(11, 'tbl ')), mask=1 << 11)
    out.append(rec(T['CTRL_HEADER'], 1, b'tbl '[::-1] + struct.pack('<IiiIIi4HIH', 1 | 2 << 3 | 2 << 8 | 1 << 13 | 1 << 21, 0, 0,
                                                                     30000, 3000, 0, 141, 141, 141, 141, 7, 0)))
    out.append(rec(T['TABLE'], 2, struct.pack('<IHHH4HHHH', 6, 1, 1, 0, 510, 510, 141, 141, 1, 1, 0)))
    out.append(rec(T['LIST_HEADER'], 2, struct.pack('<iIHHHHII4HHI', 1, 0x20, 0, 0, 1, 1, 30000, 3000, 510, 510, 141, 141, 1, 30000)))
    out += owpml_para(2, text_bytes('칸 글'), last=True, segw=28980)
    out += list(extra)
    out += owpml_para(0, text_bytes(), last=True)
    return fmt.unrecords(out)


def owpml_build(path, extra=(), docinfo_extra=()):
    fh = fmt.SIGNATURE.ljust(32, b'\x00') + struct.pack('<II', 0x05010100, fmt.COMPRESSED) + bytes(256 - 40)
    root = cfb.Entry('Root Entry', cfb.ROOT)
    root.add(cfb.Entry('FileHeader', cfb.STREAM, fh))
    root.add(cfb.Entry('DocInfo', cfb.STREAM, fmt.deflate(docinfo() + fmt.unrecords(list(docinfo_extra)))))
    body = root.add(cfb.Entry('BodyText', cfb.STORAGE))
    body.add(cfb.Entry('Section0', cfb.STREAM, fmt.deflate(owpml_section(extra))))
    with open(path, 'wb') as f:
        f.write(cfb.build(root))
    return path


def owpml_selftest(d):
    """HWP -> HWPX record by record (owpml.py): the package, the header, the section (text, table), reading it back with
    core.read, and the stop on a record it has no mapping for (never a silent drop)."""
    import zipfile
    from ..core import read as core_read
    from . import owpml
    src = owpml_build(os.path.join(d, 'owpml.hwp'))
    dst = os.path.join(d, 'owpml.hwpx')
    assert owpml.convert(src, dst) == []
    z = zipfile.ZipFile(dst)
    names = z.namelist()
    assert names[0] == 'mimetype' and z.read('mimetype') == b'application/hwp+zip', names
    for part in ('version.xml', 'Contents/header.xml', 'Contents/section0.xml', 'Contents/content.hpf', 'settings.xml',
                 'META-INF/container.xml', 'Preview/PrvText.txt'):
        assert part in names, (part, names)
    head, sec = z.read('Contents/header.xml').decode(), z.read('Contents/section0.xml').decode()
    assert '<hh:fontfaces itemCnt="7">' in head and '<hh:borderFills itemCnt="2">' in head and '<hh:charPr id="0" height="1000"' in head
    assert '<hp:tbl ' in sec and '<hp:t>칸 글</hp:t>' in sec and '안녕하세요 hello' in sec and 'colCnt="1"' in sec, sec[:600]
    assert z.read('Preview/PrvText.txt').decode().startswith('\r\n안녕하세요 hello\r\n<칸 글>'), z.read('Preview/PrvText.txt')
    spec = core_read.read(dst, os.path.join(d, 'owpml_spec.json'))
    import json
    flat = json.dumps(spec, ensure_ascii=False)
    assert '"table"' in flat and '칸 글' in flat and '안녕하세요 hello' in flat, flat[:400]      # the table sits in a paragraph (inline)
    # a control and a DocInfo record the converter has no mapping for: it stops and says where
    bad = owpml_build(os.path.join(d, 'owpml_bad.hwp'),
                      extra=owpml_para(0, text_bytes(ext_ctrl(11, 'zzzz')), mask=1 << 11)
                      + [rec(fmt.T['CTRL_HEADER'], 1, b'zzzz'[::-1] + bytes(8))])
    try:
        owpml.convert(bad, os.path.join(d, 'owpml_bad.hwpx'))
        raise AssertionError('an unknown control was converted')
    except owpml.Unsupported as e:
        assert str(e).startswith("UNSUPPORTED control 'zzzz' BodyText/Section0 record"), str(e)
    bad = owpml_build(os.path.join(d, 'owpml_bad2.hwp'), docinfo_extra=[rec(0x7F, 0, b'12')])
    try:
        owpml.convert(bad, os.path.join(d, 'owpml_bad2.hwpx'))
        raise AssertionError('an unknown DocInfo record was converted')
    except owpml.Unsupported as e:
        assert str(e) == 'UNSUPPORTED 0x7F DocInfo', str(e)
    # values measured in Hangul 2024 (rules HW53): compatibility bits, image fill modes, shape CTRL_DATA, cross reference commands
    from . import owpmlmap, owpmlobj, owpmlshape
    assert [len(w) for w in owpmlmap.COMPAT_FLAGS] == [12, 24, 7, 11, 1] and owpmlmap.COMPAT_FLAGS[1][17] == 'applyTabPosBasedOnSegment'
    assert owpmlmap.IMG_MODES[5] == 'TOTAL' and owpmlmap.IMG_MODES[14] == 'RIGHT_BOTTOM' and len(owpmlmap.IMG_MODES) == 16
    assert owpmlshape.shape_data(bytes(6), '') == ('', None)
    link = bytes.fromhex('1b02010000006f0200806f020100000065020100' '0300' '410042004300')       # the link `ABC`
    assert owpmlshape.shape_data(link, '')[0] == 'ABC'
    assert owpmlshape.shape_data(bytes.fromhex('1b02010000006f0200806f0200000000'), '')[1].at == {'cnt': 0, 'name': 539}
    try:
        owpmlshape.shape_data(bytes.fromhex('1b02010000006f0200806f02010000007777010000'), '')
        raise AssertionError('an unknown shape CTRL_DATA was read')
    except owpml.Unsupported:
        pass
    refs = owpmlobj.crossref_params('?#1;1;1;0;0;', '')
    assert [e.text for e in refs][2:] == ['TARGET_PICTURE', 'OBJECT_TYPE_NUMBER', 'false', 'HWPHYPERLINK_JUMP_CURRENTTAB']
    try:
        owpmlobj.crossref_params('?#1;7;0;1;0;', '')
        raise AssertionError('a cross reference type without a name was read')
    except owpml.Unsupported:
        pass


def hostile_selftest(d, dst):
    """Hostile input: a deflate bomb, cell spans past the table, a long BinData extension, a name too long for
    a directory entry, a failed write. `dst` = a .hwp that has a table (see `build`)."""
    import types
    import zipfile
    try:
        fmt.inflate(fmt.deflate(bytes(100000)), limit=1000)
        raise AssertionError('a deflate bomb was inflated')
    except fmt.Hwp5Error:
        pass
    assert fmt.inflate(fmt.deflate(b'abc' * 100), limit=300) == b'abc' * 100
    pk = fmt.Package(dst)                                   # a cell that spans 65535 x 65535: the span stays inside the 2 x 2 table
    recs = pk.records('BodyText/Section0')
    i = next(i for i, r in enumerate(recs) if r[0] == fmt.T['LIST_HEADER'] and r[1] == 2)
    lh = bytearray(recs[i][2])
    struct.pack_into('<HH', lh, 12, 65535, 65535)
    recs[i][2] = bytes(lh)
    pk.put_records('BodyText/Section0', recs)
    from . import tospec
    spec = tospec.read(pk.save(os.path.join(d, 'span.hwp')), os.path.join(d, 'span.json'))
    cell = next(b['table'] for b in spec['body'] if 'table' in b)['rows'][0][0]
    assert isinstance(cell, dict) and cell.get('cs', 1) <= 2 and cell.get('rs', 1) <= 2, cell
    pk = fmt.Package(dst)                                   # Hangul writes the height of a row in one cell only; the others hold 0
    recs = pk.records('BodyText/Section0')
    heads = [i for i, r in enumerate(recs) if r[0] == fmt.T['LIST_HEADER'] and r[1] == 2]      # the 4 cells: (0,0) (0,1) (1,0) (1,1)
    for i, h in ((heads[2], 8464), (heads[3], 0)):
        lh = bytearray(recs[i][2])
        struct.pack_into('<i', lh, 20, h)
        recs[i][2] = bytes(lh)
    pk.put_records('BodyText/Section0', recs)
    spec = tospec.read(pk.save(os.path.join(d, 'tall.hwp')), os.path.join(d, 'tall.json'))
    heights = next(b['table'] for b in spec['body'] if 'table' in b)['heights']
    assert abs(heights[1] - 8464 / 283.465) < 0.01, heights
    from . import fromowpml, fo_body
    big = os.path.join(d, 'big.zip')                        # a package part larger than the limit is refused before it is read
    with zipfile.ZipFile(big, 'w') as z:
        z.writestr('Contents/header.xml', b'x' * 1000)
    src = object.__new__(fromowpml.Source)
    src.zip = zipfile.ZipFile(big)
    old, fmt.MAX_INFLATE = fmt.MAX_INFLATE, 100
    try:
        src.read('Contents/header.xml')
        raise AssertionError('a part over the limit was read')
    except fromowpml.Unsupported:
        pass
    finally:
        fmt.MAX_INFLATE = old
    fake = types.SimpleNamespace(items={'a': ('BinData/x.' + 'p' * 40, 'image/png')}, linked=set(), ver=(5, 1, 1, 0), has=lambda h: True,
                                 read=lambda h: b'', dst=dst)
    try:
        fo_body.BinTable(fake)
        raise AssertionError('a long BinData extension was accepted')
    except fromowpml.Unsupported:
        pass
    root = cfb.Entry('Root Entry', cfb.ROOT)
    root.add(cfb.Entry('N' * 40, cfb.STREAM, b'x'))
    try:
        cfb.build(root)
        raise AssertionError('a 40-character directory name was written')
    except ValueError:
        pass
    out = os.path.join(d, 'keep.bin')
    with open(out, 'wb') as f:
        f.write(b'old')
    before = sorted(os.listdir(d))
    try:
        with fmt.atomic(out) as tmp, open(tmp, 'wb') as f:
            f.write(b'half')
            raise RuntimeError('write failed')
    except RuntimeError:
        pass
    assert open(out, 'rb').read() == b'old' and sorted(os.listdir(d)) == before, 'a failed write left a file behind'
    with fmt.atomic(out) as tmp, open(tmp, 'wb') as f:
        f.write(b'new')
    assert open(out, 'rb').read() == b'new' and sorted(os.listdir(d)) == before


def selftest():
    from . import edit, guard
    cfb.selftest()
    from . import docinfo                                  # border type 2 = dot, 3 = dash, 6 = long dash; underline shape 1 = dot, 2 = dash
    assert [docinfo.line(t, 3, 0).split()[1] for t in (2, 3, 4, 6)] == ['dot', 'dash', 'dash_dot', 'long_dash']
    assert docinfo.UNDER_SHAPES[:3] == ['solid', 'dot', 'dash']
    d = tmpdir.mkdtemp('hwp5_t_')
    src = build(os.path.join(d, 'form.hwp'))
    doc = edit.Doc(src)
    keys = {r['key']: r for r in doc.slots()}
    assert keys['t1.r1c2']['label'] == '성명' and keys['t1.r2c2']['text'] == '○○○', keys
    assert doc.fill({'성명': '가람', '연락처': '000-0000-0000', '없는칸': 'x'}) == ['없는칸']
    assert doc.check('동의함') and doc.replace('적어', '써') == 1
    assert doc.set('p5', '홍길동')                     # into the empty click-here field
    dst = doc.save(os.path.join(d, 'filled.hwp'))
    back = edit.Doc(dst)
    t = back.text()
    assert '가람' in t and '000-0000-0000' in t and '☑ 동의함' in t and '아래 표에 써 주십시오.' in t, t
    s = back.sections[0]
    p5 = s.slots['p5'][0]
    codes = [fmt.Units.code(it[0]) for it in s.units(p5).items]
    assert codes.index(3) < [i for i, c in enumerate(codes) if c >= 32][-1] < codes.index(4), codes   # inside the field
    recs = s.recs
    for p in s.paras:                                  # edited paragraphs: no line layout, counts right
        hd = recs[p.head][2]
        if 'p5' == p.key or p.kind == 'cell' and p.cell['col'] == 1:
            assert fmt.T['PARA_LINE_SEG'] not in p.parts and struct.unpack_from('<H', hd, 16)[0] == 0
        n = struct.unpack_from('<I', hd)[0] & 0x7FFFFFFF
        txt = recs[p.parts[0x43]][2] if 0x43 in p.parts else None
        assert (len(txt) // 2 if txt is not None else 1) == n
    pk = fmt.Package(dst)
    assert '미리보기 옛 글' not in pk.stream('PrvText').decode('utf-16-le') and pk.stream('PrvImage')[:6] == b'GIF89a'
    lines = []
    fails = guard.report(src, dst, forbid=['써'], require=['없는말'], max_unchanged=0.3, out=lines.append)
    text = '\n'.join(lines)
    assert 'GUARD STRUCTURE same' in text and 'forbidden "써"' in text and 'required "없는말"' in text, text
    assert 'long original sentences unchanged' in text and fails == 3, (fails, text)
    long = edit.Doc(src)
    long.set('t1.r1c2', '가나다라마바사 ' * 30)
    lines = []
    guard.report(src, long.save(os.path.join(d, 'long.hwp')), out=lines.append)
    assert any('row grows' in x for x in lines), lines
    tam = fmt.Package(dst)                             # a cell made wider by hand: the guard must see it
    recs = tam.records('BodyText/Section0')
    i = next(i for i, r in enumerate(recs) if r[0] == fmt.T['LIST_HEADER'])
    lh = bytearray(recs[i][2])
    struct.pack_into('<I', lh, 16, struct.unpack_from('<I', lh, 16)[0] + 283)
    recs[i][2] = bytes(lh)
    tam.put_records('BodyText/Section0', recs)
    lines = []
    guard.report(src, tam.save(os.path.join(d, 'tampered.hwp')), out=lines.append)
    assert any('cell or list' in x for x in lines), lines
    from . import tospec
    spec = tospec.read(dst, os.path.join(d, 'spec.json'))
    tbl = next(b['table'] for b in spec['body'] if 'table' in b)
    cell = tbl['rows'][0][0]
    assert [round(c) for c in tbl['cols']] == [30, 120] and (cell if isinstance(cell, str) else cell['p']) == '성명', tbl
    assert spec['page']['size'] == 'A4' and spec['page']['margin']['left'] == 30.0
    assert check_file(src, out=lambda *_: None) == 0
    from ..core import registry
    if registry.backend('pages', 'preview') is not None:
        from . import render
        found = []
        assert render.compare(src, dst, os.path.join(d, 'cmp'), backend='preview', out=found.append) == 0, found
        assert any(x.startswith('COMPARE PAGE 1 TEXT') for x in found), found
        found = []
        assert render.compare(src, os.path.join(d, 'long.hwp'), os.path.join(d, 'cmp'), backend='preview',
                              out=found.append) >= 1, found
        assert any(' FORM ' in x for x in found), found
    hostile_selftest(d, src)
    owpml_selftest(d)
    from . import fromowpml, residue, safecopy
    fromowpml.selftest()
    safecopy.selftest(d)
    residue.selftest()
    residue.integration(d)
    print('HWP5 SELFTEST PASS')


def main(args):
    if not args:
        selftest()
        return 0
    fails = 0
    for root in args:
        files = [root] if os.path.isfile(root) else sorted(
            os.path.join(r, f) for r, _, fs in os.walk(root) for f in fs if f.lower().endswith('.hwp'))
        for f in files:
            fails += check_file(f)
    print('HWP5 FILES', 'OK' if not fails else f'FAIL {fails}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
