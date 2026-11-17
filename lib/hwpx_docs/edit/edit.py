"""Edit an existing HWPX in place: change text only, keep everything else as it is.

  hd slots <in.hwpx> [--json slots.json]
  hd edit <in.hwpx> <out.hwpx> [--values values.json] [--set KEY=TEXT ...] [--replace OLD=NEW ...]
          [--check LABEL ...] [--mark ☑] [--allow-missing]
  hd edit --selftest

Slots (every paragraph that the section holds, numbered in document order, 1-based):
  p<N>              body paragraph N            (s<S>.p<N> in section S > 1)
  t<T>.r<R>c<C>     table T, cell at row R, column C (Hangul's cell address + 1); all paragraphs of the cell
  o<N>              other paragraph: header/footer, note, text box
A label is the text of a short table cell. Its value slot is the cell to its right in the same row, or the cell
below when the right one is filled and the below one is empty. Keys of values.json are slot keys or labels.
"\n" in a value = a new line (the cell's next paragraph, or a line break in the last one).

What changes: the text of the edited paragraphs (the run with the most text keeps its style; the other runs of that
paragraph are emptied), the line layout cache (hp:linesegarray) of those paragraphs only (Hangul rebuilds it), and
Preview/PrvText.txt + Preview/PrvImage.png (they would still show the old text). The section XML outside the edited
paragraphs keeps its bytes; every other ZIP entry keeps its content, name, date and compression.
"""
from ..core import tmpdir
import json
import os
import re
import sys
import zipfile
from html import escape, unescape

TAG = re.compile(r'<(/?)([A-Za-z][\w.-]*(?::[\w.-]+)?)((?:\s[^<>]*?)?)(/?)>')
OBJECTS = {'hp:tbl', 'hp:pic', 'hp:rect', 'hp:ellipse', 'hp:line', 'hp:arc', 'hp:polygon', 'hp:curve',
           'hp:connectLine', 'hp:container', 'hp:ole', 'hp:chart', 'hp:equation', 'hp:textart'}
BOXES = '☐□'
EMPTY = re.compile(r'[\s○◯_·.\-:]*')


class Para:
    def __init__(self, start, cell, nested):
        self.start, self.end, self.cell, self.nested = start, None, cell, nested
        self.ts = []            # [start, end, selfclosing]: content range of a direct hp:t (tag range if self-closing)
        self.runs = []          # [tag start, tag end, selfclosing, close tag start]: direct hp:run elements
        self.lsa = None         # [start, end] of the direct hp:linesegarray
        self.objects = False    # holds a table, picture or drawing object


def attr(attrs, name):
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def scan(xml):
    """Section XML -> paragraphs in document order (offsets into xml)."""
    stack, paras, ntab = [], [], 0
    for m in TAG.finditer(xml):
        close, name, attrs, selfc = m.group(1) == '/', m.group(2), m.group(3) or '', m.group(4) == '/'
        if close:
            while stack:
                n, obj = stack.pop()
                if n == name:
                    break
            if name == 'hp:p':
                obj.end = m.end()
            elif name == 'hp:t':
                obj[1] = m.start()
            elif name == 'hp:linesegarray':
                obj[1] = m.end()
            elif name == 'hp:run' and obj is not None:
                obj[3] = m.start()
            continue
        # the paragraph that directly holds this tag (no sub list opened after it)
        owner = None
        for n, obj in reversed(stack):
            if n == 'hp:subList':
                break
            if n == 'hp:p':
                owner = obj
                break
        obj = None
        if name == 'hp:p':
            cell, nested = None, False
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == 'hp:subList':
                    if i > 0 and stack[i - 1][0] == 'hp:tc':
                        cell = stack[i - 1][1]
                    else:
                        nested = True
                    break
            obj = Para(m.start(), cell, nested)
            paras.append(obj)
            if selfc:
                obj.end = m.end()
        elif name == 'hp:t' and owner is not None:
            if selfc:
                owner.ts.append([m.start(), m.end(), True])
            else:
                obj = [m.end(), None, False]
                owner.ts.append(obj)
        elif name == 'hp:linesegarray' and owner is not None and not selfc:
            obj = [m.start(), None]
            owner.lsa = obj
        elif name == 'hp:run' and owner is not None:
            obj = [m.start(), m.end(), selfc, None]
            owner.runs.append(obj)
        elif name == 'hp:tbl':
            ntab += 1
            obj = {'n': ntab}
        elif name == 'hp:tc':
            tbl = next((o for n, o in reversed(stack) if n == 'hp:tbl'), {'n': 0})
            obj = {'table': tbl['n'], 'row': 0, 'col': 0, 'rs': 1, 'cs': 1}
        elif name in ('hp:cellAddr', 'hp:cellSpan'):
            tc = next((o for n, o in reversed(stack) if n == 'hp:tc'), None)
            if tc is not None:
                for key, a in (('col', 'colAddr'), ('row', 'rowAddr'), ('cs', 'colSpan'), ('rs', 'rowSpan')):
                    if attr(attrs, a) is not None:
                        tc[key] = int(attr(attrs, a))
        if name in OBJECTS and owner is not None:
            owner.objects = True
        if not selfc:
            stack.append([name, obj])
    return paras


def t_text(raw):
    raw = re.sub(r'<hp:lineBreak\s*/>', '\n', raw)
    raw = re.sub(r'<hp:tab\b[^>]*/>', '\t', raw)
    return unescape(re.sub(r'<[^>]+>', '', raw))


def para_text(xml, p):
    return ''.join('' if sc else t_text(xml[a:b]) for a, b, sc in p.ts)


def norm(label):
    return re.sub(r'[\s:：*※()（）\[\]]', '', label)


class Section:
    def __init__(self, name, xml, index):
        self.name, self.xml, self.index = name, xml, index
        self.rescan()

    def rescan(self):
        self.paras = scan(self.xml)
        pre = f's{self.index + 1}.' if self.index else ''
        self.slots = {}         # key -> [Para]
        nb = no = 0
        for p in self.paras:
            if p.cell is not None:
                c = p.cell
                key = f'{pre}t{c["table"]}.r{c["row"] + 1}c{c["col"] + 1}'
            elif p.nested:
                no += 1
                key = f'{pre}o{no}'
            else:
                nb += 1
                key = f'{pre}p{nb}'
            self.slots.setdefault(key, []).append(p)

    def text(self, key):
        return '\n'.join(para_text(self.xml, p) for p in self.slots[key])


class Doc:
    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.infos = z.infolist()
            self.data = {i.filename: z.read(i) for i in self.infos}
        names = sorted((n for n in self.data if re.fullmatch(r'Contents/section\d+\.xml', n)),
                       key=lambda n: int(re.search(r'\d+', n).group()))
        self.sections = [Section(n, self.data[n].decode('utf-8'), i) for i, n in enumerate(names)]
        self.changed = set()

    def where(self, key):
        return next((s for s in self.sections if key in s.slots), None)

    def slots(self):
        """[{key, kind, label, text}] in document order; label = the label whose value slot this is."""
        out = []
        labels = {v: k for k, v in self.labels().items()}
        for s in self.sections:
            for key, ps in s.slots.items():
                if not any(p.ts or p.runs for p in ps):
                    continue
                kind = 'cell' if ps[0].cell is not None else 'other' if ps[0].nested else 'body'
                out.append({'key': key, 'kind': kind, 'label': labels.get(key), 'text': s.text(key)})
        return out

    def labels(self):
        """normalised label -> slot key of its value cell."""
        out = {}
        for s in self.sections:
            grid = {}
            for key, ps in s.slots.items():
                c = ps[0].cell
                if c is not None:
                    grid[(c['table'], c['row'], c['col'])] = (key, c)
            for (t, r, col), (key, c) in grid.items():
                text = s.text(key).strip()
                lab = norm(text)
                if not lab or len(lab) > 15 or EMPTY.fullmatch(text) or lab in out:
                    continue
                right = grid.get((t, r, col + c['cs']))
                below = grid.get((t, r + c['rs'], col))
                def empty(cell):
                    return cell is not None and EMPTY.fullmatch(s.text(cell[0]))
                pick = right if empty(right) else below if empty(below) else None   # filled cells are no values
                if pick is not None:
                    out[lab] = pick[0]
        return out

    # ---- edits
    def _apply(self, s, edits):
        for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
            s.xml = s.xml[:a] + new + s.xml[b:]
        s.rescan()
        self.changed.add(s.name)

    def _para_edits(self, s, p, text):
        """Edits that set the text of paragraph p (the run with the most text keeps its style)."""
        if para_text(s.xml, p) == text or not (p.ts or p.runs):
            return []
        raw = escape(text, quote=False).replace('\n', '<hp:lineBreak/>').replace(
            '\t', '<hp:tab width="0" leader="0" type="0"/>')
        if not p.ts:                    # an empty paragraph has a run with no hp:t: put one into its first run
            a, b, sc, close = p.runs[0]
            edits = [(a, b, s.xml[a:b - 2].rstrip() + f'><hp:t>{raw}</hp:t></hp:run>')] if sc else \
                [(close, close, f'<hp:t>{raw}</hp:t>')]
            return edits + ([(p.lsa[0], p.lsa[1], '')] if p.lsa else [])
        lens = [0 if sc else len(t_text(s.xml[a:b])) for a, b, sc in p.ts]
        keep = lens.index(max(lens))
        edits = []
        for i, (a, b, sc) in enumerate(p.ts):
            if i == keep:
                edits.append((a, b, f'<hp:t>{raw}</hp:t>') if sc else (a, b, raw))
            elif not sc and a != b:
                edits.append((a, b, ''))
        if p.lsa:
            edits.append((p.lsa[0], p.lsa[1], ''))
        return edits

    def set(self, key, value):
        s = self.where(key)
        if s is None:
            return False
        ps = [p for p in s.slots[key] if p.ts or p.runs]
        if not ps:
            return False
        lines = str(value).split('\n')
        if len(lines) > len(ps):
            lines = lines[:len(ps) - 1] + ['\n'.join(lines[len(ps) - 1:])]
        lines += [''] * (len(ps) - len(lines))
        edits = [e for p, text in zip(ps, lines) for e in self._para_edits(s, p, text)]
        if edits:
            self._apply(s, edits)
        return True

    def fill(self, values):
        """values: {slot key or label: text}. Returns the keys that matched nothing."""
        labels = self.labels()
        missing = []
        for k, v in values.items():
            key = k if self.where(k) else labels.get(norm(k))
            if key is None or not self.set(key, v):
                missing.append(k)
        return missing

    def replace(self, old, new):
        """Replace text everywhere; in place when it lies in one run, else the paragraph is rewritten. -> count."""
        n = 0
        for s in self.sections:
            while True:
                hit = None
                for p in s.paras:
                    for a, b, sc in p.ts:
                        raw = s.xml[a:b]
                        if not sc and '<' not in raw and old in unescape(raw):
                            hit = [(a, b, escape(unescape(raw).replace(old, new), quote=False))]
                            if p.lsa:                   # the text length changed: drop the layout cache
                                hit.append((p.lsa[0], p.lsa[1], ''))
                            n += unescape(raw).count(old)
                            break
                    if hit:
                        break
                    text = para_text(s.xml, p)
                    if old in text:
                        hit = self._para_edits(s, p, text.replace(old, new))
                        n += text.count(old)
                        break
                if not hit:
                    break
                self._apply(s, hit)
                if old in new:
                    break                       # avoid an endless loop when the new text holds the old one
        return n

    def check(self, label, mark='☑'):
        """Mark the box (☐ or □) right before `label`. -> True if a box was marked."""
        rx = re.compile('[' + BOXES + r']\s*' + re.escape(label))
        for s in self.sections:
            for p in s.paras:
                m = rx.search(para_text(s.xml, p))
                if not m:
                    continue
                base = 0
                for a, b, sc in p.ts:
                    t = '' if sc else t_text(s.xml[a:b])
                    if base <= m.start() < base + len(t):
                        raw = s.xml[a:b]
                        for j, ch in enumerate(raw):    # the raw offset of that box (raw text may hold entities)
                            if ch in BOXES and len(t_text(raw[:j])) == m.start() - base:
                                self._apply(s, [(a + j, a + j + 1, mark)])
                                return True
                    base += len(t)
        return False

    def save(self, dst):
        body = '\r\n'.join(para_text(s.xml, p) for s in self.sections for p in s.paras
                           if p.cell is None and not p.nested and p.ts)
        new = {s.name: s.xml.encode('utf-8') for s in self.sections if s.name in self.changed}
        if self.changed:
            new['Preview/PrvText.txt'] = body[:1024].encode('utf-8')
            if 'Preview/PrvImage.png' in self.data:
                new['Preview/PrvImage.png'] = blank_png(self.data['Preview/PrvImage.png'])
        tmp = dst + '.tmp'
        with zipfile.ZipFile(tmp, 'w') as zo:
            for info in self.infos:
                zo.writestr(info, new.get(info.filename, self.data[info.filename]))
        os.replace(tmp, dst)
        return dst


def blank_png(old):
    """A white PNG of the old preview's size (the old one would still show the old text)."""
    import struct
    import zlib
    w, h = (struct.unpack('>II', old[16:24]) if old[:8] == b'\x89PNG\r\n\x1a\n' else (1, 1))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + b'\xff' * (3 * w) for _ in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def selftest():
    from ..core import build, read
    d = tmpdir.mkdtemp('hwpx_docs_edit_')
    src = os.path.join(d, 'form.hwpx')
    build.write({'body': [
        {'p': ['신청서 ', {'t': '(제1호)', 'bold': True}]},
        {'table': {'cols': [30, 60, 30, 50], 'rows': [
            ['성명', '', '연락처', '○○○-○○○○'],
            ['주소', {'p': '', 'cs': 3}],
            [{'p': '동의', 'rs': 1}, {'p': '☐ 동의함    ☐ 동의하지 않음', 'cs': 3}]]}},
        '담당자: 홍길동 & 김철수']}, src)
    doc = Doc(src)
    lab = doc.labels()
    assert lab.get('성명') == 't1.r1c2' and lab.get('연락처') == 't1.r1c4' and lab.get('주소') == 't1.r2c2', lab
    keys = [x['key'] for x in doc.slots()]
    assert 'p1' in keys and 'p3' in keys and 't1.r3c2' in keys, keys
    missing = doc.fill({'성명': '가람', '연락처': '000-0000-0000', 'p1': '참가 신청서', '주소': '가람시\n중앙로 100',
                        '없는칸': 'x'})
    assert missing == ['없는칸'], missing
    assert doc.check('동의함') and not doc.check('없는항목')
    assert doc.replace('홍길동', '한누리') == 1
    out = doc.save(os.path.join(d, 'out.hwpx'))
    spec = read.read(out, os.path.join(d, 'out.json'))
    b = spec['body']
    rows = b[1]['table']['rows']
    text = json.dumps(spec, ensure_ascii=False)
    assert b[0]['p'] == '참가 신청서' or b[0]['p'][0] == '참가 신청서', b[0]
    assert '가람' in text and '000-0000-0000' in text and '☑ 동의함    ☐ 동의하지 않음' in text, text[:400]
    assert '한누리 & 김철수' in text and '홍길동' not in text
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as z:
        assert a.read('Contents/header.xml') == z.read('Contents/header.xml')
        assert [i.filename for i in a.infolist()] == [i.filename for i in z.infolist()]
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED
    assert len(rows) == 3 and len(b) == 3, 'structure kept'
    # a Hangul-saved file: only the edited paragraphs lose their line layout cache
    fx = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tests', 'fixtures', 'table_form.hwpx')
    if os.path.exists(fx):
        doc = Doc(fx)
        before = doc.sections[0].xml.count('<hp:linesegarray>')
        first_cell = next(x for x in doc.slots() if x['kind'] == 'cell')
        n_par = len(doc.sections[0].slots[first_cell['key']])
        doc.set(first_cell['key'], '바뀐 글')
        after = doc.sections[0].xml.count('<hp:linesegarray>')
        assert before - after == n_par, (before, after, n_par)
    print('EDIT SELFTEST PASS')


def main(args):
    if args and args[0] == '--selftest':
        return selftest()
    if args and args[0] == 'slots':
        doc = Doc(args[1])
        rows = doc.slots()
        if '--json' in args:
            json.dump(rows, open(args[args.index('--json') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        for r in rows:
            lab = f' [{r["label"]}]' if r['label'] else ''
            print(f'{r["key"]:<14}{lab} {r["text"][:60]!r}')
        print('SLOTS', len(rows))
        return 0
    src, dst = args[0], args[1]
    doc = Doc(src)

    def many(flag):
        if args[-1:] == [flag]:
            raise SystemExit(f'{flag} needs a value')
        return [args[i + 1] for i, a in enumerate(args) if a == flag]
    values = json.load(open(args[args.index('--values') + 1], encoding='utf-8')) if '--values' in args else {}
    values.update(dict(x.split('=', 1) for x in many('--set')))
    missing = doc.fill(values)
    for x in many('--replace'):
        old, new = x.split('=', 1)
        print('REPLACED', doc.replace(old, new), repr(old))
    mark = args[args.index('--mark') + 1] if '--mark' in args else '☑'
    for lab in many('--check'):
        if not doc.check(lab, mark):
            missing.append(f'check:{lab}')
    for k in missing:
        print('UNMATCHED', k)
    if missing and '--allow-missing' not in args:
        print('STOP: nothing written (use --allow-missing to write anyway)')
        return 2
    print('EDITED', len(doc.changed), 'section(s) ->', doc.save(dst))
    from . import guard
    guard.report(src, dst)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
