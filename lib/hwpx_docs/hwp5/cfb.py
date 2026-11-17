"""Compound file (CFB, "OLE2"): the container of an HWP 5.0 file. Read, patch in place, build new.

  read(data) -> Entry (the root; .children, .data of streams, .sid = directory index)
  streams(root) -> {'BodyText/Section0': Entry, ...}
  patch(data, {path: new bytes}) -> bytes     edit an existing file (rules HW03)
  build(root) -> bytes                        a new file (self-tests and synthesized documents only)

`patch` keeps every directory entry byte for byte except the start sector and the size of a changed stream (and of the
root entry when the mini stream grows): the red-black tree, class ids, state bits and times stay as Hangul wrote them.
Untouched streams keep their sectors. The sectors a changed stream gave up are zeroed, so the old text does not stay in
the file. New sectors reuse free ones first, then go at the end; the FAT, mini FAT and DIFAT grow when they must.
"""
import struct

SIG = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
FREE, ENDC, FATSECT, DIFSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFC, 0xFFFFFFFF
MS = 64                                         # mini sector size
STORAGE, STREAM, ROOT = 1, 2, 5


class Entry:
    def __init__(self, name, typ, data=b'', clsid=bytes(16), state=0, ctime=0, mtime=0):
        self.name, self.typ, self.data, self.clsid = name, typ, data, clsid
        self.state, self.ctime, self.mtime = state, ctime, mtime
        self.children, self.sid = [], None

    def add(self, child):
        self.children.append(child)
        return child

    def walk(self, path=''):
        for c in self.children:
            p = f'{path}/{c.name}' if path else c.name
            yield p, c
            yield from c.walk(p)


def streams(root):
    return {p: e for p, e in root.walk() if e.typ == STREAM}


class _File:
    """Parsed tables of a compound file (the part both read and patch need)."""

    def __init__(self, data):
        if data[:8] != SIG:
            raise ValueError('not a compound file')
        self.major = struct.unpack_from('<H', data, 26)[0]
        self.ss = 1 << struct.unpack_from('<H', data, 30)[0]
        self.base = 512 if self.ss == 512 else self.ss
        self.nfat, self.dir1 = struct.unpack_from('<II', data, 44)
        self.cut, self.mf1, self.nmf, self.dif1, self.ndif = struct.unpack_from('<IIIII', data, 56)
        self.data = data
        n = -(-(len(data) - self.base) // self.ss)
        self.sectors = [bytearray(data[self.base + i * self.ss:self.base + (i + 1) * self.ss].ljust(self.ss, b'\x00'))
                        for i in range(n)]
        per = self.ss // 4
        self.difat_secs, self.fat_secs = [], [v for v in struct.unpack_from('<109I', data, 76)][:self.nfat]
        s = self.dif1
        if self.ndif > len(self.sectors) or self.nfat > len(self.sectors):          # a file cannot have more table sectors than sectors
            raise ValueError('broken DIFAT')
        seen = set()
        for _ in range(self.ndif):
            if s >= len(self.sectors) or s in seen:                                  # a DIFAT sector that points back to one already read
                raise ValueError('broken DIFAT')
            seen.add(s)
            self.difat_secs.append(s)
            sec = self.sectors[s]
            self.fat_secs += struct.unpack_from('<%dI' % (per - 1), sec)
            s = struct.unpack_from('<I', sec, self.ss - 4)[0]
        self.fat_secs = self.fat_secs[:self.nfat]
        if any(f >= len(self.sectors) for f in self.fat_secs):
            raise ValueError('broken FAT')
        self.fat =[v for f in self.fat_secs for v in struct.unpack('<%dI' % per, self.sectors[f])]
        self.dir_chain = self.chain(self.dir1)
        d = b''.join(self.sectors[i] for i in self.dir_chain)
        self.dirents = [bytearray(d[i:i + 128]) for i in range(0, len(d), 128)]
        self.mf_chain = self.chain(self.mf1) if self.nmf else []
        self.minifat = [v for i in self.mf_chain for v in struct.unpack('<%dI' % per, self.sectors[i])]
        root = self.dirents[0]
        self.ms_chain = self.chain(struct.unpack_from('<I', root, 116)[0])
        self.mini = bytearray(b''.join(self.sectors[i] for i in self.ms_chain)[:self.size(0)])

    def chain(self, first):
        out, n, seen = [], first, set()
        while n < DIFSECT:
            if n in seen or n >= len(self.fat) or n >= len(self.sectors):
                raise ValueError('broken sector chain')
            seen.add(n)
            out.append(n)
            n = self.fat[n]
        return out

    def mini_chain(self, first):
        out, n, seen = [], first, set()
        while n < DIFSECT:
            if n in seen or n >= len(self.minifat):
                raise ValueError('broken mini sector chain')
            seen.add(n)
            out.append(n)
            n = self.minifat[n]
        return out

    def size(self, sid):
        v = struct.unpack_from('<Q', self.dirents[sid], 120)[0]
        return v & 0xFFFFFFFF if self.major == 3 else v

    def stream(self, sid):
        e, size = self.dirents[sid], self.size(sid)
        if size == 0:
            return b''
        first = struct.unpack_from('<I', e, 116)[0]
        if size < self.cut:
            return b''.join(bytes(self.mini[i * MS:(i + 1) * MS]) for i in self.mini_chain(first))[:size]
        return b''.join(bytes(self.sectors[i]) for i in self.chain(first))[:size]


def read(data):
    """Compound file bytes -> root Entry (ValueError when it is not one this module can read)."""
    f = _File(data)
    used = set()

    def make(sid):
        if sid in used or sid >= len(f.dirents):
            raise ValueError('broken directory tree')
        used.add(sid)
        e = f.dirents[sid]
        ln = struct.unpack_from('<H', e, 64)[0]
        typ = e[66]
        node = Entry(bytes(e[:max(ln - 2, 0)]).decode('utf-16-le', 'replace'), typ,
                     f.stream(sid) if typ == STREAM else b'', bytes(e[80:96]), struct.unpack_from('<I', e, 96)[0],
                     struct.unpack_from('<Q', e, 100)[0], struct.unpack_from('<Q', e, 108)[0])
        node.sid = sid
        child = struct.unpack_from('<I', e, 76)[0]
        if typ in (STORAGE, ROOT) and child != NOSTREAM:
            todo = [child]
            while todo:                                  # every node of the sibling tree
                j = todo.pop()
                if j == NOSTREAM:
                    continue
                node.children.append(make(j))
                todo += struct.unpack_from('<II', f.dirents[j], 68)
            node.children.sort(key=lambda c: key(c.name))
        return node
    return make(0)


def key(name):
    """CFB sibling order: shorter name first, then the upper-cased UTF-16 code units."""
    return (len(name.encode('utf-16-le')), name.upper())


# ---- patch an existing file ---------------------------------------------------------------------------------------------
def patch(data, changes):
    """Bytes of `data` with the streams in `changes` ({'BodyText/Section0': bytes}) replaced (rules HW03)."""
    f = _File(data)
    root = read(data)
    paths = {p: e.sid for p, e in root.walk() if e.typ == STREAM}
    for p in changes:
        if p not in paths:
            raise KeyError(f'no stream {p}')
    ss, per = f.ss, f.ss // 4
    fat, minifat, sectors, mini = f.fat, f.minifat, f.sectors, f.mini
    fat += [FREE] * (len(sectors) - len(fat))

    def new_sector():
        for i, v in enumerate(fat):
            if v == FREE and i < len(sectors):
                return i
        sectors.append(bytearray(ss))
        fat.extend([FREE] * (len(sectors) - len(fat)))     # the FAT may already list this sector (as free)
        return len(sectors) - 1

    def new_mini():
        for i, v in enumerate(minifat):
            if v == FREE and (i + 1) * MS <= len(mini):
                return i
        i = len(mini) // MS                              # the next mini sector after the end of the mini stream
        mini.extend(bytes(MS))
        minifat.extend([FREE] * (i + 1 - len(minifat)))  # the mini FAT may already list it (as free)
        return i

    def grow_chain(chain, n):
        """Make the regular chain `chain` (list, changed in place) at least n sectors long; returns it."""
        while len(chain) < n:
            s = new_sector()
            fat[s] = ENDC
            if chain:
                fat[chain[-1]] = s
            chain.append(s)
        return chain

    for p, new in changes.items():
        sid = paths[p]
        e = f.dirents[sid]
        old_size, first = f.size(sid), struct.unpack_from('<I', e, 116)[0]
        if old_size:                                     # give the old sectors back, zeroed
            if old_size < f.cut:
                for i in f.mini_chain(first):
                    mini[i * MS:(i + 1) * MS] = bytes(MS)
                    minifat[i] = FREE
            else:
                for i in f.chain(first):
                    sectors[i][:] = bytes(ss)
                    fat[i] = FREE
        start = ENDC
        if new and len(new) < f.cut:
            k = -(-len(new) // MS)
            got = []
            for _ in range(k):
                i = new_mini()
                minifat[i] = ENDC                        # taken (linked below)
                got.append(i)
            for n, i in enumerate(got):
                minifat[i] = got[n + 1] if n + 1 < k else ENDC
                mini[i * MS:(i + 1) * MS] = new[n * MS:(n + 1) * MS].ljust(MS, b'\x00')
            start = got[0]
        elif new:
            got = grow_chain([], -(-len(new) // ss))
            for n, i in enumerate(got):
                sectors[i][:] = new[n * ss:(n + 1) * ss].ljust(ss, b'\x00')
            start = got[0]
        struct.pack_into('<I', e, 116, start)
        struct.pack_into('<Q', e, 120, len(new))

    # the mini stream (data of the root entry) and the mini FAT
    ms_chain = grow_chain(list(f.ms_chain), -(-len(mini) // ss))
    for n, i in enumerate(ms_chain):
        sectors[i][:] = bytes(mini[n * ss:(n + 1) * ss]).ljust(ss, b'\x00')
    struct.pack_into('<I', f.dirents[0], 116, ms_chain[0] if ms_chain else ENDC)
    struct.pack_into('<Q', f.dirents[0], 120, len(mini))
    while len(minifat) % per:
        minifat.append(FREE)
    mf_chain = grow_chain(list(f.mf_chain), len(minifat) // per)
    for n, i in enumerate(mf_chain):
        sectors[i][:] = struct.pack('<%dI' % per, *minifat[n * per:(n + 1) * per])
    d = b''.join(bytes(x) for x in f.dirents)                 # same number of entries, same chain
    for n, i in enumerate(f.dir_chain):
        sectors[i][:] = d[n * ss:(n + 1) * ss]

    # FAT and DIFAT: enough sectors to describe every sector, themselves included
    fat_secs, dif_secs = list(f.fat_secs), list(f.difat_secs)
    while True:
        need_fat = -(-len(sectors) // per)
        need_dif = max(0, -(-(need_fat - 109) // (per - 1)))
        if len(fat_secs) >= need_fat and len(dif_secs) >= need_dif:
            break
        if len(fat_secs) < need_fat:
            s = new_sector()
            fat[s] = FATSECT
            fat_secs.append(s)
        else:
            s = new_sector()
            fat[s] = DIFSECT
            dif_secs.append(s)
    fat += [FREE] * (len(fat_secs) * per - len(fat))
    for n, i in enumerate(fat_secs):
        sectors[i][:] = struct.pack('<%dI' % per, *fat[n * per:(n + 1) * per])
    rest = fat_secs[109:]
    for n, i in enumerate(dif_secs):
        part = rest[n * (per - 1):(n + 1) * (per - 1)]
        nxt = dif_secs[n + 1] if n + 1 < len(dif_secs) else ENDC
        sectors[i][:] = struct.pack('<%dI' % len(part), *part).ljust(ss - 4, b'\xff') + struct.pack('<I', nxt)
    head = bytearray(data[:f.base])
    struct.pack_into('<I', head, 44, len(fat_secs))
    struct.pack_into('<III', head, 60, mf_chain[0] if mf_chain else ENDC, len(mf_chain),
                     dif_secs[0] if dif_secs else ENDC)
    struct.pack_into('<I', head, 72, len(dif_secs))
    struct.pack_into('<109I', head, 76, *(fat_secs[:109] + [FREE] * (109 - min(109, len(fat_secs)))))
    return bytes(head) + b''.join(bytes(s) for s in sectors)


# ---- build a new file ---------------------------------------------------------------------------------------------------
def build(root):
    """Root Entry -> compound file bytes (v3, 512-byte sectors). The sibling trees are balanced binary search trees
    whose deepest level is red when the tree is not perfect, so every path has the same number of black nodes."""
    ss, per, cut = 512, 128, 4096          # sector size, directory entries per sector, size below which a stream lives in the mini stream
    order = []

    def number(node):
        node.sid = len(order)
        order.append(node)
        for c in node.children:
            number(c)
    number(root)
    links = {n.sid: [NOSTREAM, NOSTREAM, NOSTREAM, 1] for n in order}      # left, right, child, colour (1 = black)

    def tree(nodes, depth, red):
        if not nodes:
            return NOSTREAM
        m = len(nodes) // 2
        lk = links[nodes[m].sid]
        lk[0], lk[1] = tree(nodes[:m], depth + 1, red), tree(nodes[m + 1:], depth + 1, red)
        lk[3] = 0 if depth == red else 1
        return nodes[m].sid
    for n in order:
        if n.children:
            sib = sorted(n.children, key=lambda c: key(c.name))
            k = len(sib)
            links[n.sid][2] = tree(sib, 0, -1 if (k + 1) & k == 0 else k.bit_length() - 1)
    sectors, fat = [], []

    def alloc(b):
        k = -(-len(b) // ss)
        if not k:
            return ENDC
        first = len(sectors)
        for i in range(k):
            sectors.append(b[i * ss:(i + 1) * ss].ljust(ss, b'\x00'))
            fat.append(first + i + 1 if i < k - 1 else ENDC)
        return first
    mini, minifat, start = bytearray(), [], {}
    for n in order:
        if n.typ == STREAM and 0 < len(n.data) < cut:
            k = -(-len(n.data) // MS)
            s = len(mini) // MS
            start[n.sid] = s
            mini += n.data.ljust(k * MS, b'\x00')
            minifat += [s + i + 1 for i in range(k - 1)] + [ENDC]
    for n in order:
        if n.typ == STREAM and len(n.data) >= cut:
            start[n.sid] = alloc(n.data)
    mf1 = alloc(struct.pack('<%dI' % len(minifat), *minifat).ljust(-(-len(minifat) // per) * ss, b'\xff')) if minifat else ENDC
    ms1 = alloc(bytes(mini)) if mini else ENDC

    def ent(n):
        nm = n.name.encode('utf-16-le')
        if len(nm) > 62:                                           # 31 UTF-16 units and the end mark fill the 64-byte name field
            raise ValueError(f'directory name {n.name[:40]!r} is longer than 31 characters')
        left, right, child, col = links[n.sid]
        first, size = (ms1, len(mini)) if n.typ == ROOT else (start.get(n.sid, ENDC), len(n.data)) if n.typ == STREAM else (0, 0)
        return (nm.ljust(64, b'\x00') + struct.pack('<HBB', len(nm) + 2, n.typ, col) + struct.pack('<III', left, right, child)
                + n.clsid + struct.pack('<IQQ', n.state, n.ctime, n.mtime) + struct.pack('<IQ', first, size))
    ents = [ent(n) for n in order]
    while len(ents) % 4:
        ents.append(bytes(64) + struct.pack('<HBB', 0, 0, 0) + struct.pack('<III', NOSTREAM, NOSTREAM, NOSTREAM) + bytes(36)
                    + struct.pack('<IQ', 0, 0))
    dir1 = alloc(b''.join(ents))
    nfat = ndif = 0
    while True:
        ndif = max(0, -(-(nfat - 109) // 127))
        if nfat * per >= len(sectors) + nfat + ndif:
            break
        nfat += 1
    fat_first = len(sectors)
    fat += [FATSECT] * nfat + [DIFSECT] * ndif
    fat += [FREE] * (nfat * per - len(fat))
    fb = struct.pack('<%dI' % len(fat), *fat)
    sectors += [fb[i * ss:(i + 1) * ss] for i in range(nfat)]
    fat_secs = [fat_first + i for i in range(nfat)]
    for i in range(ndif):
        part = fat_secs[109 + i * 127:109 + (i + 1) * 127]
        nxt = fat_first + nfat + i + 1 if i < ndif - 1 else ENDC
        sectors.append(struct.pack('<%dI' % len(part), *part).ljust(508, b'\xff') + struct.pack('<I', nxt))
    head = fat_secs[:109] + [FREE] * (109 - min(nfat, 109))
    hdr = (SIG + bytes(16) + struct.pack('<HHHHH', 0x3E, 3, 0xFFFE, 9, 6) + bytes(6)
           + struct.pack('<IIIIIIIII', 0, nfat, dir1, 0, cut, mf1, -(-len(minifat) // per), fat_first + nfat if ndif else ENDC, ndif)
           + struct.pack('<109I', *head))
    return hdr + b''.join(sectors)


def selftest():
    """Build a tree with storages, read it back, patch streams across the mini/regular boundary, read again."""
    import random
    rnd = random.Random(5)
    root = Entry('Root Entry', ROOT)
    root.add(Entry('FileHeader', STREAM, b'H' * 256))
    body = root.add(Entry('BodyText', STORAGE))
    for i in range(3):
        body.add(Entry(f'Section{i}', STREAM, bytes(rnd.randrange(256) for _ in range(300 + 5000 * i))))
    bins = root.add(Entry('BinData', STORAGE))
    bins.add(Entry('BIN0001.png', STREAM, bytes(rnd.randrange(256) for _ in range(9000))))
    root.add(Entry('PrvText', STREAM, '미리보기'.encode('utf-16-le')))
    root.add(Entry('\x05HwpSummaryInformation', STREAM, b'S' * 100))
    data = build(root)
    back = streams(read(data))
    want = streams(root)
    assert {p: e.data for p, e in back.items()} == {p: e.data for p, e in want.items()}, sorted(back)
    changes = {'BodyText/Section0': b'a' * 5000,             # mini -> regular
               'BodyText/Section1': b'b' * 100,              # regular -> mini
               'BodyText/Section2': b'c' * 20000,            # regular, longer
               'PrvText': '새 글'.encode('utf-16-le')}        # mini, shorter
    out = patch(data, changes)
    got = {p: e.data for p, e in streams(read(out)).items()}
    for p, d in changes.items():
        assert got[p] == d, p
    assert got['BinData/BIN0001.png'] == want['BinData/BIN0001.png'].data and got['FileHeader'] == b'H' * 256
    assert b'\xeb\xaf\xb8\xeb' not in out and '미리보기'.encode('utf-16-le') not in out      # old bytes are zeroed
    # directory entries keep their bytes except start and size
    f0, f1 = _File(data), _File(out)
    for a, b in zip(f0.dirents, f1.dirents):
        assert a[:116] == b[:116], 'directory entry changed'
    grow = {'PrvText': bytes(range(256)) * 15, '\x05HwpSummaryInformation': b'T' * 2000}      # the mini stream grows
    out2 = patch(out, grow)
    got = {p: e.data for p, e in streams(read(out2)).items()}
    for p, d in dict(changes, **grow).items():
        assert got[p] == d, p
    big = patch(data, {'BinData/BIN0001.png': bytes(8 * 1024 * 1024)})           # grows past 109 FAT sectors (DIFAT)
    assert _File(big).ndif >= 1 and streams(read(big))['BinData/BIN0001.png'].data == bytes(8 * 1024 * 1024)
    assert streams(read(patch(big, {'PrvText': b''})))['PrvText'].data == b''
    # build: a real-file layout (many siblings, a stream over 7 MB = DIFAT) reads back; the sibling trees are red-black trees
    many = Entry('Root Entry', ROOT)
    for i in range(37):
        many.add(Entry('s%02d' % i, STREAM, bytes([i]) * (i * 211)))
    sub = many.add(Entry('Sub', STORAGE))
    for i in range(6):
        sub.add(Entry('x%d' % i, STREAM, b'z' * (4000 + i * 50)))
    huge = bytes(range(256)) * 32768                                  # 8 MB: more than 109 FAT sectors
    many.add(Entry('big', STREAM, huge))
    blob = build(many)
    assert _File(blob).ndif >= 1 and len(_File(blob).fat_secs) > 109
    back = streams(read(blob))
    assert back['big'].data == huge and back['s36'].data == bytes([36]) * (36 * 211) and len(back) == 37 + 6 + 1
    f = _File(blob)

    def black_height(sid):                                           # raises when the red-black rules are broken
        if sid == NOSTREAM:
            return 1
        e = f.dirents[sid]
        left, right = struct.unpack_from('<II', e, 68)
        red = e[67] == 0
        for c in (left, right):
            assert not (red and c != NOSTREAM and f.dirents[c][67] == 0), 'red node with a red child'
        hl, hr = black_height(left), black_height(right)
        assert hl == hr, 'different black heights'
        return hl + (0 if red else 1)
    for sid in range(len(f.dirents)):
        e = f.dirents[sid]
        if e[66] in (STORAGE, ROOT) and struct.unpack_from('<I', e, 76)[0] != NOSTREAM:
            top = struct.unpack_from('<I', e, 76)[0]
            assert f.dirents[top][67] == 1, 'the top of a sibling tree is black'
            black_height(top)
    # a hostile file: a DIFAT sector that points to itself, or table counts above the sector count, is a ValueError, not a hang
    head = bytearray(SIG + bytes(504))
    struct.pack_into('<H', head, 30, 9)                                  # 512-byte sectors
    sec = bytearray(512)
    struct.pack_into('<I', sec, 508, 0)                                  # the DIFAT sector 0 points to sector 0
    for ndif, nfat in ((2, 1), (0xFFFFFFF0, 1), (0, 0xFFFFFFF0)):
        evil = bytearray(head)
        struct.pack_into('<I', evil, 44, nfat)
        struct.pack_into('<IIIII', evil, 56, 4096, 0xFFFFFFFE, 0, 0, ndif)
        bad = bytes(evil) + bytes(sec) * 2
        assert len(bad) < 2000
        try:
            read(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('a hostile compound file was read')
    print('CFB SELFTEST PASS')
