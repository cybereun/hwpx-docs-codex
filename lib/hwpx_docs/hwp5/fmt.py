"""HWP 5.0 file layer: FileHeader, streams, records, paragraphs and the text of a paragraph (rules HW01-HW09).

  Package(path)                 .version, .flags, .sections (stream paths), .records(path), .put_records(path, recs),
                                .stream(path), .put(path, bytes), .save(dst) (cfb.patch: only changed streams move)
  records(b) / unrecords(recs)  record stream <-> [[tag, level, payload], ...]
  paragraphs(recs)              [Para] in document order: kind body / cell / other, the cell address, the table number
  Units(text, shapes)           the paragraph as code units with their char shape ids; .text(), .encode()

Written from the public format document; see the notice in __init__.py.
"""
import contextlib
import os
import re
import struct
import tempfile
import zlib

from ..core import protect
from . import cfb

SIGNATURE = b'HWP Document File'
# FileHeader attribute bits (offset 36)
COMPRESSED, PASSWORD, DISTRIBUTION, DRM = 0x1, 0x2, 0x4, 0x10
REFUSE = {0x2: 'password', 0x4: 'distribution (배포용)', 0x10: 'DRM', 0x100: 'certificate encryption',
          0x400: 'certificate DRM', 0x2000: 'private information security'}
UNSUPPORTED = {0x4000: 'track changes (변경 추적)'}

T = dict(DOCUMENT_PROPERTIES=0x10, ID_MAPPINGS=0x11, BIN_DATA=0x12, FACE_NAME=0x13, BORDER_FILL=0x14, CHAR_SHAPE=0x15,
         TAB_DEF=0x16, NUMBERING=0x17, BULLET=0x18, PARA_SHAPE=0x19, STYLE=0x1A,
         PARA_HEADER=0x42, PARA_TEXT=0x43, PARA_CHAR_SHAPE=0x44, PARA_LINE_SEG=0x45, PARA_RANGE_TAG=0x46,
         CTRL_HEADER=0x47, LIST_HEADER=0x48, PAGE_DEF=0x49, FOOTNOTE_SHAPE=0x4A, PAGE_BORDER_FILL=0x4B,
         SHAPE_COMPONENT=0x4C, TABLE=0x4D, SHAPE_COMPONENT_LINE=0x4E, SHAPE_COMPONENT_RECTANGLE=0x4F,
         SHAPE_COMPONENT_ELLIPSE=0x50, SHAPE_COMPONENT_ARC=0x51, SHAPE_COMPONENT_POLYGON=0x52,
         SHAPE_COMPONENT_CURVE=0x53, SHAPE_COMPONENT_OLE=0x54, SHAPE_COMPONENT_PICTURE=0x55,
         SHAPE_COMPONENT_CONTAINER=0x56, CTRL_DATA=0x57, EQEDIT=0x58,
         DOC_DATA=0x1B, COMPATIBLE_DOCUMENT=0x1E, LAYOUT_COMPATIBILITY=0x1F, TRACK_CHANGE_FLAGS=0x20,
         MEMO_SHAPE=0x5C, MEMO_LIST=0x5D, FORBIDDEN_CHAR=0x5E, TRACK_CHANGE=0x60, TRACK_CHANGE_AUTHOR=0x61)
PARA_PARTS = (T['PARA_TEXT'], T['PARA_CHAR_SHAPE'], T['PARA_LINE_SEG'], T['PARA_RANGE_TAG'])

# PARA_TEXT control characters (HW05): size in code units
EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}       # object / section / field start ...: 8 units
INLINE = {4, 5, 6, 7, 8, 9, 19, 20}                                  # field end, tab ...: 8 units
TAB, LINE_BREAK, PARA_END = 9, 10, 13                                # other codes below 32: 1 unit


class Hwp5Error(ValueError):
    pass


class Unsupported(Exception):
    """A record or control without a mapping (.hwp -> .hwpx). Message: `UNSUPPORTED <what> <place>`."""

    def __init__(self, what, place=''):
        super().__init__(f'UNSUPPORTED {what} {place}'.strip())


@contextlib.contextmanager
def atomic(dst):
    """A new temporary file next to `dst` (mkstemp: never a file that is there already); it becomes `dst` when the block ends
    well and is removed when it does not, so a failed write leaves nothing half-written."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dst)), prefix='.hd_', suffix='.tmp')
    os.close(fd)
    try:
        yield tmp
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


MAX_INFLATE = 512 << 20                                      # the most a stream or a package part may hold after inflating


def inflate(b, limit=MAX_INFLATE):
    """Raw-deflated bytes -> bytes; more than `limit` (a deflate bomb is about 1000:1) is a Hwp5Error."""
    d = zlib.decompressobj(-15)
    out = d.decompress(b, limit + 1)
    if len(out) > limit or d.unconsumed_tail:
        raise Hwp5Error(f'a stream inflates to more than {limit >> 20} MB')
    return out + d.flush()


def deflate(b):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(b) + c.flush()


def records(b):
    out, i = [], 0
    while i + 4 <= len(b):
        h = struct.unpack_from('<I', b, i)[0]
        i += 4
        tag, lvl, size = h & 0x3FF, (h >> 10) & 0x3FF, h >> 20
        if size == 0xFFF:
            size = struct.unpack_from('<I', b, i)[0]
            i += 4
        if i + size > len(b):
            raise Hwp5Error('record runs past the end of the stream')
        out.append([tag, lvl, bytes(b[i:i + size])])
        i += size
    if i != len(b):
        raise Hwp5Error('stray bytes after the last record')
    return out


def unrecords(recs):
    out = bytearray()
    for tag, lvl, d in recs:
        if len(d) >= 0xFFF:
            out += struct.pack('<II', tag | lvl << 10 | 0xFFF << 20, len(d))
        else:
            out += struct.pack('<I', tag | lvl << 10 | len(d) << 20)
        out += d
    return bytes(out)


def ctrl_id(payload):
    """'tbl ', 'gso ', 'secd', '%clk' ... of a CTRL_HEADER (stored as a little-endian number of 4 characters)."""
    return payload[:4][::-1].decode('latin-1') if len(payload) >= 4 else ''


class Package:
    """An HWP 5.0 file: its compound file, FileHeader and record streams."""

    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        if self.data[:8] != cfb.SIG:
            if self.data.startswith(b'HWP Document File V'):
                raise Hwp5Error(f'UNSUPPORTED: {path} is an HWP {self.data[19:23].decode("latin-1")} file (한글 97 and '
                                f'older); open it in Hangul and save it as HWP 5 or HWPX')
            raise Hwp5Error(f'{path}: not an HWP 5.0 file (no compound file signature)')
        self.root = cfb.read(self.data)
        self.streams = cfb.streams(self.root)
        fh = self.streams.get('FileHeader')
        if fh is None or not fh.data.startswith(SIGNATURE):
            raise Hwp5Error(f'{path}: not an HWP 5.0 file (no FileHeader)')
        self.version = struct.unpack_from('<I', fh.data, 32)[0]
        self.flags = struct.unpack_from('<I', fh.data, 36)[0]
        bad = [n for bit, n in REFUSE.items() if self.flags & bit]
        if bad:
            raise protect.ProtectedDocument(
                f'PROTECTED: {path} is a {" / ".join(bad)} document. hwpx-docs does not decrypt. Open it in Hangul and '
                f'save an unprotected copy, then run the command again.')
        self.compressed = bool(self.flags & COMPRESSED)
        self.sections = sorted((p for p in self.streams if re.fullmatch(r'BodyText/Section\d+', p)),
                               key=lambda p: int(p[16:]))
        # A track-change document (flag 0x4000) keeps its whole text, with the deleted parts and the PARA_RANGE_TAG marks, in
        # ViewText/Section<n> (a plain deflate stream of records); BodyText holds a shorter form. Hangul 2024 writes the HWPX
        # from ViewText (2 files: 2814 records against 775, 232 range tags against none; HW53).
        view = sorted((p for p in self.streams if re.fullmatch(r'ViewText/Section\d+', p)), key=lambda p: int(p[16:]))
        if self.flags & 0x4000 and len(view) == len(self.sections):
            self.sections = view
        self.changed = {}
        self._recs = {}

    def unsupported(self):
        """Names of document kinds that `edit` refuses (HW02)."""
        return [n for bit, n in UNSUPPORTED.items() if self.flags & bit]

    def version_text(self):
        v = self.version
        return f'{v >> 24 & 255}.{v >> 16 & 255}.{v >> 8 & 255}.{v & 255}'

    def stream(self, path):
        """Stream bytes, inflated if it is a compressed record stream."""
        if path in self.changed:
            return self.changed[path]
        d = self.streams[path].data
        if self.compressed and (path == 'DocInfo' or path.startswith(('BodyText/', 'ViewText/'))):
            return inflate(d)
        return d

    def put(self, path, data):
        self.changed[path] = data
        self._recs.pop(path, None)

    def records(self, path):
        if path not in self._recs:
            self._recs[path] = records(self.stream(path))
        return self._recs[path]

    def put_records(self, path, recs):
        self.changed[path] = unrecords(recs)
        self._recs[path] = recs

    def save(self, dst):
        out = {}
        for path, d in self.changed.items():
            if self.compressed and (path == 'DocInfo' or path.startswith(('BodyText/', 'ViewText/'))):
                d = deflate(d)
            out[path] = d
        data = cfb.patch(self.data, out) if out else self.data
        with atomic(dst) as tmp, open(tmp, 'wb') as f:
            f.write(data)
        return dst


# ---- paragraphs ---------------------------------------------------------------------------------------------------------
class Para:
    """A paragraph of a record stream. `head` = index of its PARA_HEADER; `parts` = {tag: index} of its own
    PARA_TEXT / PARA_CHAR_SHAPE / PARA_LINE_SEG / PARA_RANGE_TAG; kind = 'body', 'cell' or 'other' (a caption, text
    box, header/footer, note ...); cell = {'table', 'row', 'col', 'rs', 'cs', 'w', 'h'} for a table cell."""

    def __init__(self, head, level, kind, cell=None, list_index=None):
        self.head, self.level, self.kind, self.cell, self.list = head, level, kind, cell, list_index
        self.parts = {}
        self.objects = []          # control ids of the objects it holds ('tbl ', 'gso ', ...)


def paragraphs(recs):
    """Paragraphs in document order with the list (cell, caption, text box, ...) each one belongs to (HW04)."""
    out, ntab = [], 0
    lists = {}                      # level -> [remaining paragraphs, kind, cell, list index]
    ctrl_at = {}                    # level -> [ctrl id, table number, TABLE seen]
    para_at = {}                    # level -> the last paragraph at that level
    for i, (tag, lvl, d) in enumerate(recs):
        for table in (ctrl_at, lists, para_at):
            for L in [k for k in table if k > lvl]:
                del table[L]
        if tag == T['CTRL_HEADER']:
            cid = ctrl_id(d)
            if cid == 'tbl ':
                ntab += 1
            ctrl_at[lvl] = [cid, ntab if cid == 'tbl ' else None, False]
            if lvl - 1 in para_at:
                para_at[lvl - 1].objects.append(cid)
        elif tag == T['TABLE'] and lvl - 1 in ctrl_at:
            ctrl_at[lvl - 1][2] = True
        elif tag == T['LIST_HEADER']:
            n = struct.unpack_from('<h', d, 0)[0] if len(d) >= 2 else 0
            owner = ctrl_at.get(lvl - 1)
            if owner and owner[0] == 'tbl ' and owner[2] and len(d) >= 32:
                col, row, cs, rs = struct.unpack_from('<4H', d, 8)
                w, h = struct.unpack_from('<II', d, 16)
                lists[lvl] = [n, 'cell', {'table': owner[1], 'row': row, 'col': col, 'rs': rs or 1, 'cs': cs or 1,
                                          'w': w, 'h': h, 'list': i}, i]
            else:
                lists[lvl] = [n, 'other', None, i]
        elif tag == T['PARA_HEADER']:
            lst = lists.get(lvl)
            if lvl == 0:
                p = Para(i, lvl, 'body')
            elif lst is not None and lst[0] > 0:
                p = Para(i, lvl, lst[1], lst[2], lst[3])
                lst[0] -= 1
            else:
                p = Para(i, lvl, 'other')
            out.append(p)
            para_at[lvl] = p
        elif tag in PARA_PARTS and lvl - 1 in para_at:
            para_at[lvl - 1].parts.setdefault(tag, i)
    return out


# ---- the text of one paragraph ------------------------------------------------------------------------------------------
def unit_size(code):
    return 8 if code in EXTENDED or code in INLINE else 1


class Units:
    """A paragraph as a list of [raw bytes, char shape id, original position]: one entry per character (one UTF-16
    code unit) or per control (2 or 16 bytes). Edits change the list; encode() gives PARA_TEXT and PARA_CHAR_SHAPE."""

    def __init__(self, text, shapes):
        self.items = []
        cs = [struct.unpack_from('<II', shapes, k) for k in range(0, len(shapes) - 7, 8)] or [(0, 0)]
        i, n, k = 0, len(text) // 2, 0
        while i < n:
            c = struct.unpack_from('<H', text, i * 2)[0]
            size = unit_size(c) if c < 32 else 1
            while k + 1 < len(cs) and cs[k + 1][0] <= i:
                k += 1
            self.items.append([text[i * 2:(i + size) * 2], cs[k][1], i])
            i += size
        if not self.items:                                   # a paragraph with no PARA_TEXT: only its end
            self.items.append([struct.pack('<H', PARA_END), cs[0][1], 0])
        self.first_shape = cs[0][1]

    @staticmethod
    def code(raw):
        return struct.unpack_from('<H', raw)[0]

    def is_char(self, it):
        return self.code(it[0]) >= 32

    def text(self, objects=''):
        """Plain text: tab -> \\t, line break -> \\n, other controls -> `objects` (default nothing)."""
        out = []
        for raw, _, _ in self.items:
            c = self.code(raw)
            if c >= 32:
                out.append(raw)
            elif c == TAB:
                out.append('\t'.encode('utf-16-le'))
            elif c == LINE_BREAK:
                out.append('\n'.encode('utf-16-le'))
            elif c != PARA_END and objects:
                out.append(objects.encode('utf-16-le'))
        return b''.join(out).decode('utf-16-le', 'replace')

    def segments(self):
        """[(start item, end item)] of runs of characters, tabs and line breaks (no other control inside)."""
        out, a = [], None
        for k, (raw, _, _) in enumerate(self.items):
            c = self.code(raw)
            if c >= 32 or c in (TAB, LINE_BREAK):
                if a is None:
                    a = k
            else:
                if a is not None:
                    out.append((a, k))
                a = None
        if a is not None:
            out.append((a, len(self.items)))
        return out

    def seg_text(self, a, b):
        return Units.text_of(self.items[a:b])

    @staticmethod
    def text_of(items):
        out = []
        for raw, _, _ in items:
            c = Units.code(raw)
            out.append(raw if c >= 32 else ('\t' if c == TAB else '\n').encode('utf-16-le'))
        return b''.join(out).decode('utf-16-le', 'surrogatepass')

    @staticmethod
    def make(text, shape, tab_raw=None):
        """Items for new text: \\t -> a tab control (a copy of `tab_raw` or a zero one), \\n -> a line break."""
        out = []
        tab = tab_raw or struct.pack('<8H', TAB, 0, 0, 0, 0, 0, 0, TAB)
        for ch in text:
            if ch == '\t':
                out.append([tab, shape, None])
            elif ch == '\n':
                out.append([struct.pack('<H', LINE_BREAK), shape, None])
            elif ch == '\r':
                continue
            else:
                b = ch.encode('utf-16-le', 'surrogatepass')
                out += [[b[j:j + 2], shape, None] for j in range(0, len(b), 2)]
        return out

    def tab_raw(self):
        return next((raw for raw, _, _ in self.items if self.code(raw) == TAB), None)

    def splice(self, a, b, new_items):
        self.items[a:b] = new_items

    def length(self):
        return sum(len(raw) // 2 for raw, _, _ in self.items)

    def encode(self):
        """-> (PARA_TEXT bytes or None for an empty paragraph, PARA_CHAR_SHAPE bytes, code units)."""
        text = b''.join(raw for raw, _, _ in self.items)
        pairs, pos = [], 0
        for raw, shape, _ in self.items:
            if not pairs or pairs[-1][1] != shape:
                pairs.append((pos, shape))
            pos += len(raw) // 2
        if not pairs:
            pairs = [(0, self.first_shape)]
        n = len(text) // 2
        empty = n == 1 and self.code(text) == PARA_END
        return (None if empty else text), b''.join(struct.pack('<II', *p) for p in pairs), n

    def position_map(self):
        """old code-unit position -> new position (for range tags): the new place of the first item that came from
        a position at or after it."""
        olds, pos = [], 0
        for raw, _, orig in self.items:
            if orig is not None:
                olds.append((orig, pos))
            pos += len(raw) // 2
        total = pos

        def f(x):
            for o, p in olds:
                if o >= x:
                    return p
            return total
        return f

    def controls(self):
        return {self.code(raw) for raw, _, _ in self.items if self.code(raw) < 32}


def read_units(recs, p):
    text = recs[p.parts[T['PARA_TEXT']]][2] if T['PARA_TEXT'] in p.parts else b''
    shapes = recs[p.parts[T['PARA_CHAR_SHAPE']]][2] if T['PARA_CHAR_SHAPE'] in p.parts else b''
    return Units(text, shapes)


def apply_edits(recs, edits):
    """{PARA_HEADER index: (Para, Units)} -> the new record list, in one pass over the records."""
    put, drop = {}, set()
    for head, (p, units) in edits.items():
        put[head] = para_records(recs, p, units)
        drop.update(p.parts.values())
    out = []
    for i, r in enumerate(recs):
        if i in put:
            out += put[i]
        elif i not in drop:
            out.append(r)
    return out


def para_records(recs, p, units):
    """[PARA_HEADER, PARA_TEXT?, PARA_CHAR_SHAPE, PARA_RANGE_TAG?] of the edited paragraph p."""
    text, shapes, n = units.encode()
    head = bytearray(recs[p.head][2])
    nch = struct.unpack_from('<I', head, 0)[0]
    struct.pack_into('<I', head, 0, (nch & 0x80000000) | n)
    mask = struct.unpack_from('<I', head, 4)[0]
    ctl = units.controls()
    for c in (TAB, LINE_BREAK):                           # the bits of the controls an edit can add or remove
        mask = mask | (1 << c) if c in ctl else mask & ~(1 << c)
    struct.pack_into('<I', head, 4, mask)
    struct.pack_into('<H', head, 12, len(shapes) // 8)
    new = {}
    if text is not None:
        new[T['PARA_TEXT']] = text
    new[T['PARA_CHAR_SHAPE']] = shapes
    if T['PARA_RANGE_TAG'] in p.parts:
        f = units.position_map()
        rt = recs[p.parts[T['PARA_RANGE_TAG']]][2]
        items = []
        for k in range(0, len(rt) - 11, 12):
            a, b, tag = struct.unpack_from('<III', rt, k)
            a2, b2 = f(a), f(b)
            if b2 > a2:
                items.append(struct.pack('<III', a2, b2, tag))
        if items:
            new[T['PARA_RANGE_TAG']] = b''.join(items)
        struct.pack_into('<H', head, 14, len(items))
    struct.pack_into('<H', head, 16, 0)                  # no line layout: Hangul lays the paragraph out again
    lvl = p.level + 1
    order = [T['PARA_TEXT'], T['PARA_CHAR_SHAPE'], T['PARA_RANGE_TAG']]
    return [[recs[p.head][0], recs[p.head][1], bytes(head)]] + [[t, lvl, new[t]] for t in order if t in new]
