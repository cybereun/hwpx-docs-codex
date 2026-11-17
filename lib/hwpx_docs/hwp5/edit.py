"""Edit an existing .hwp (HWP 5.0) in place: change text only, keep everything else (rules HW06-HW10).

  hd hwp slots <in.hwp> [--json slots.json]
  hd hwp edit <in.hwp> <out.hwp> [--values values.json] [--set KEY=TEXT ...] [--replace OLD=NEW ...]
              [--check LABEL ...] [--mark ☑] [--allow-missing] [--drop-scripts]
  hd hwp text <in.hwp>

Slots and labels work as in `hd edit` (HWPX): p<N> body paragraph, t<T>.r<R>c<C> table cell (Hangul's cell address
+ 1), o<N> other paragraph (caption, text box, header/footer, note); s<S>. in front in section S > 1. A label is the
text of a short cell; its value slot is the cell to its right, or the cell below when the right one is filled.

What changes: PARA_TEXT, PARA_CHAR_SHAPE and the PARA_HEADER counts of the edited paragraphs, their line layout cache
(PARA_LINE_SEG is removed; Hangul lays them out again), PrvText (the body and cell text) and PrvImage (a blank image of
the same size and format). Every other record keeps its bytes; every other stream keeps its bytes and sectors (cfb.patch).
"""
import json
import os
import re
import struct
import sys
import zlib
from collections import Counter

from ..edit.edit import BOXES, EMPTY, norm                   # the same label rules as `hd edit`
from . import fmt


def loose(label):
    """norm() without a leading item mark: "○ 사 업 명 :" and "사업명" meet."""
    return norm(label).lstrip('○◯●□■◇◆▶►-·•ㆍ')


class Section:
    def __init__(self, pk, index):
        self.name, self.index, self.pk = pk.sections[index], index, pk
        self.recs = pk.records(self.name)
        self.pending = {}           # PARA_HEADER index -> (Para, Units) of edits not yet in the records
        self.rescan()

    def rescan(self):
        self.paras = fmt.paragraphs(self.recs)
        pre = f's{self.index + 1}.' if self.index else ''
        self.slots, nb, no = {}, 0, 0
        for p in self.paras:
            if p.kind == 'cell':
                c = p.cell
                key = f'{pre}t{c["table"]}.r{c["row"] + 1}c{c["col"] + 1}'
            elif p.kind == 'other':
                no += 1
                key = f'{pre}o{no}'
            else:
                nb += 1
                key = f'{pre}p{nb}'
            p.key = key
            self.slots.setdefault(key, []).append(p)

    def units(self, p):
        """The paragraph's units: the edited ones when an edit is waiting (flush), else read from the records."""
        return self.pending[p.head][1] if p.head in self.pending else fmt.read_units(self.recs, p)

    def text(self, key):
        return '\n'.join(self.units(p).text() for p in self.slots[key])

    def write(self, p, units):
        """Keep the edit; flush() puts every waiting edit into the records at once (a long document stays fast)."""
        self.pending[p.head] = (p, units)
        return p

    def flush(self):
        if not self.pending:
            return
        self.recs = fmt.apply_edits(self.recs, self.pending)
        self.pending = {}
        self.rescan()


class Doc:
    def __init__(self, path):
        self.path = path
        self.pk = fmt.Package(path)
        bad = self.pk.unsupported()
        if bad:
            raise fmt.Hwp5Error(f'UNSUPPORTED: {path} is a {", ".join(bad)} document; edit it in Hangul')
        self.sections = [Section(self.pk, i) for i in range(len(self.pk.sections))]
        self.changed = set()

    def where(self, key):
        return next((s for s in self.sections if key in s.slots), None)

    def slots(self):
        """[{key, kind, label, text}] in document order; label = the label whose value slot this is."""
        labels = {v: k for k, v in self.labels().items()}
        return [{'key': key, 'kind': ps[0].kind, 'label': labels.get(key), 'text': s.text(key)}
                for s in self.sections for key, ps in s.slots.items()]

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
                right, below = grid.get((t, r, col + c['cs'])), grid.get((t, r + c['rs'], col))

                def empty(cell):
                    return cell is not None and EMPTY.fullmatch(s.text(cell[0]))
                pick = right if empty(right) else below if empty(below) else None
                if pick is not None:
                    out[lab] = pick[0]
        return out

    def text(self):
        return '\n'.join(s.units(p).text() for s in self.sections for p in s.paras)

    # ---- edits
    def _set_para(self, s, p, text):
        """Set the text of paragraph p (HW07): in a paragraph with a field (누름틀) the first field's content takes it
        and the text around the field stays; else the longest run of text (between controls) takes it, in its most
        used char shape, and the other runs are emptied. Objects, fields and other controls stay where they are."""
        u = s.units(p)
        if u.text() == text:
            return p
        segs = u.segments()
        tab = u.tab_raw()
        codes = [u.code(it[0]) for it in u.items]
        start = codes.index(3) if 3 in codes else None            # a field (누름틀): its content is the value
        end = codes.index(4, start) if start is not None and 4 in codes[start:] else None
        if end is not None:
            inside = [it for it in u.items[start + 1:end] if u.is_char(it)]
            shape = Counter(it[1] for it in inside).most_common(1)[0][0] if inside else u.items[start][1]
            u.splice(start + 1, end, fmt.Units.make(text, shape, tab))
        elif segs:
            size = [sum(1 for it in u.items[a:b] if u.is_char(it)) for a, b in segs]
            a, b = segs[size.index(max(size))]
            shapes = Counter(it[1] for it in u.items[a:b] if u.is_char(it)) or Counter([u.items[a][1]])
            new = fmt.Units.make(text, shapes.most_common(1)[0][0], tab)
            for x, y in reversed(segs):
                u.splice(x, y, new if (x, y) == (a, b) else [])
        else:                       # no text yet: before the paragraph end
            at = len(codes) - 1 if codes[-1] == fmt.PARA_END else len(codes)
            u.splice(at, at, fmt.Units.make(text, u.items[min(at, len(u.items) - 1)][1], tab))
        self.changed.add(s.name)
        return s.write(p, u)

    def set(self, key, value):
        s = self.where(key)
        if s is None:
            return False
        n = len(s.slots[key])
        lines = str(value).split('\n')
        if len(lines) > n:
            lines = lines[:n - 1] + ['\n'.join(lines[n - 1:])]
        lines += [''] * (n - len(lines))
        for k, text in enumerate(lines):
            self._set_para(s, s.slots[key][k], text)
        s.flush()
        return True

    def fill(self, values):
        """values: {slot key or label: text}. Returns the keys that matched nothing."""
        labels = self.labels()
        relaxed = {}
        for lab, key in labels.items():
            relaxed.setdefault(loose(lab), key)
        missing = []
        for k, v in values.items():
            key = k if self.where(k) else labels.get(norm(k)) or relaxed.get(loose(k))
            if key is None or not self.set(key, v):
                missing.append(k)
        return missing

    def replace(self, old, new):
        """Replace text everywhere: inside a run of text in place (each new character takes the char shape of the
        first character it replaces); across a control the paragraph text is set again (as `set`). -> count."""
        if not old:
            return 0
        n = 0
        for s in self.sections:
            k = 0
            while k < len(s.paras):
                p = s.paras[k]
                u = s.units(p)
                hit = 0
                for a, b in reversed(u.segments()):
                    t = u.seg_text(a, b)
                    if old not in t:
                        continue
                    items, pos, tab = [], 0, u.tab_raw()
                    seg = u.items[a:b]
                    cu = [len(x.encode('utf-16-le', 'surrogatepass')) // 2 for x in t.split(old)]
                    olen = len(old.encode('utf-16-le', 'surrogatepass')) // 2
                    unit = 0                                  # item index inside seg (one item per code unit or control)
                    for j, piece_len in enumerate(cu):
                        items += seg[unit:unit + piece_len]
                        unit += piece_len
                        if j < len(cu) - 1:
                            items += fmt.Units.make(new, seg[unit][1], tab)
                            unit += olen
                            hit += 1
                    u.splice(a, b, items)
                if not hit and old in u.text():
                    text = u.text()
                    n += text.count(old)
                    self._set_para(s, p, text.replace(old, new))
                elif hit:
                    n += hit
                    self.changed.add(s.name)
                    s.write(p, u)
                k += 1
            s.flush()
        return n

    def check(self, label, mark='☑'):
        """Mark the box (☐ or □) right before `label`. -> True if a box was marked."""
        rx = re.compile('[' + BOXES + r']\s*' + re.escape(label))
        for s in self.sections:
            for p in s.paras:
                u = s.units(p)
                chars = [fmt.Units.text_of([it]) if (u.is_char(it) or u.code(it[0]) in (fmt.TAB, fmt.LINE_BREAK)) else ''
                         for it in u.items]
                m = rx.search(''.join(chars))
                if not m:
                    continue
                pos = 0
                for i, c in enumerate(chars):
                    if pos == m.start() and c and c in BOXES:
                        u.splice(i, i + 1, fmt.Units.make(mark, u.items[i][1]))
                        self.changed.add(s.name)
                        s.write(p, u)
                        s.flush()
                        return True
                    pos += len(c)
        return False

    def save(self, dst):
        for s in self.sections:
            s.flush()
        for s in self.sections:
            if s.name in self.changed:
                self.pk.put_records(s.name, s.recs)
        if self.changed:
            body = '\r\n'.join(t if p.kind == 'body' else f'<{t}>' for s in self.sections for p in s.paras
                               if p.kind != 'other' for t in [s.units(p).text()] if t)     # cells as <text>, as Hangul writes
            if 'PrvText' in self.pk.streams:
                self.pk.put('PrvText', body[:1024].encode('utf-16-le', 'surrogatepass'))
            if 'PrvImage' in self.pk.streams:
                self.pk.put('PrvImage', blank_image(self.pk.streams['PrvImage'].data))
        return self.pk.save(dst)


# ---- a blank preview image of the same size and format ----------------------------------------------------------------------
def blank_image(old):
    """White image with the size and format (GIF, BMP or PNG) of `old`; an unknown format gives a 1 x 1 white GIF."""
    if old[:4] == b'\x89PNG':
        w, h = struct.unpack('>II', old[16:24])

        def chunk(t, d):
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        raw = (b'\x00' + b'\xff' * 3 * w) * h
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    if old[:2] == b'BM' and len(old) >= 26:
        w, h = struct.unpack_from('<ii', old, 18)
        w, h = abs(w), abs(h)
        row = (w * 3 + 3) // 4 * 4
        size = 54 + row * h
        return (b'BM' + struct.pack('<IHHI', size, 0, 0, 54) + struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, row * h,
                                                                           2835, 2835, 0, 0) + b'\xff' * row * h)
    w, h = struct.unpack_from('<HH', old, 6) if old[:3] == b'GIF' and len(old) >= 10 else (1, 1)
    return gif_white(w, h)


def gif_white(w, h):
    """GIF of w x h white pixels. LZW with a clear code after every two pixels keeps the codes 3 bits wide."""
    codes, n = [4], w * h                                  # 4 = clear, 5 = end, 0 = white
    for i in range(n):
        codes.append(0)
        if i % 2 == 1 and i + 1 < n:
            codes.append(4)
    codes.append(5)
    acc = nbits = 0
    out = bytearray()
    for c in codes:
        acc |= c << nbits
        nbits += 3
        while nbits >= 8:
            out.append(acc & 255)
            acc >>= 8
            nbits -= 8
    if nbits:
        out.append(acc & 255)
    blocks = b''.join(bytes([len(out[i:i + 255])]) + out[i:i + 255] for i in range(0, len(out), 255))
    return (b'GIF89a' + struct.pack('<HHBBB', w, h, 0x80, 0, 0) + b'\xff\xff\xff\x00\x00\x00'
            + b'\x2c' + struct.pack('<HHHHB', 0, 0, w, h, 0) + b'\x02' + blocks + b'\x00\x3b')


def main(args):
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == 'text':
        print(Doc(args[1]).text())
        return 0
    if cmd == 'slots':
        rows = Doc(args[1]).slots()
        if '--json' in args:
            path = args[args.index('--json') + 1]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)
            print('SLOTS WRITTEN', path, len(rows))
        for r in rows:
            lab = f' [{r["label"]}]' if r['label'] else ''
            print(f'{r["key"]:<12} {r["kind"]:<5}{lab} {r["text"][:60]!r}')
        return 0
    if cmd != 'edit' or len(args) < 3:
        print(__doc__)
        return 2
    src, dst, rest = args[1], args[2], args[3:]

    def many(flag):
        if rest[-1:] == [flag]:
            raise SystemExit(f'{flag} needs a value')
        return [rest[i + 1] for i, a in enumerate(rest) if a == flag]
    doc = Doc(src)
    values = {}
    for path in many('--values'):
        with open(path, encoding='utf-8') as f:
            values.update(json.load(f))
    for kv in many('--set'):
        k, _, v = kv.partition('=')
        values[k] = v.replace('\\n', '\n')
    missing = doc.fill(values) if values else []
    for m in missing:
        print('UNMATCHED', m)
    if missing and '--allow-missing' not in rest:
        print('NOT WRITTEN: fix the keys or add --allow-missing')
        return 1
    for kv in many('--replace'):
        old, _, new = kv.partition('=')
        print('REPLACED', repr(old), doc.replace(old, new))
    mark = (many('--mark') or ['☑'])[0]
    for lab in many('--check'):
        print('CHECKED' if doc.check(lab, mark) else 'NO BOX', lab)
    if os.path.abspath(src) == os.path.abspath(dst):
        print('NOT WRITTEN: write to a new file (the original is the guard reference)')
        return 1
    from . import safecopy
    macros = safecopy.scripts_in(doc.pk)
    if '--drop-scripts' in rest and macros:
        safecopy.blank_scripts(doc.pk)
        print('SCRIPT DROPPED', ', '.join(macros))
    doc.save(dst)
    print('HWP WRITTEN', dst)
    olds = [kv.partition('=')[0] for kv in many('--replace')]
    if olds:                                              # the old word can stand outside the body text
        from . import residue
        out_pk = fmt.Package(dst)
        for w, where in residue.hits(out_pk, olds).items():
            print(f'RESIDUE "{w}" is still in {", ".join(where[:4])}{" ..." if len(where) > 4 else ""} (not the body text: --replace does not change it)')
        if residue.history(out_pk):
            print(f'NOTE the revision history ({", ".join(residue.history(out_pk))}) keeps old versions of the text')
    if macros and '--drop-scripts' not in rest:
        # hwpx-docs adds no script; the macro is the received document's own and stays (dropping it would take the author's work
        # away). Hangul asks before a macro runs (HW109); `--drop-scripts` blanks it for a file that is not trusted.
        print(f'NOTE the file keeps the macro of the original ({macros[0]}); add --drop-scripts to blank it')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
