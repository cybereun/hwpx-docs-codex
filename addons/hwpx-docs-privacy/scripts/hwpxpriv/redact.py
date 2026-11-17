"""A redacted copy of an HWPX (group J, hidden places, and the values in the text). The input is never changed.

  redact(src, dst, session, images='placeholder')   -> {'text': n, 'hidden': n, 'images': n, 'binary': n, 'dropped': n}

What is done (rules in packs/doc-hidden/pack.json):
  section text      every detected or known value, also when it is split over two runs, becomes `■` (same length: the layout stays)
  summary           creator, last saved by, subject, description, keyword, dates -> `hwpx-docs` / fixed date (Contents/content.hpf)
  track changes     author names and dates (Contents/header.xml); memo author and date (sections)
  memos, hidden comments, field and bookmark names: all text becomes `■`
  pictures          images=placeholder (default): an 8 x 8 grey picture of the same type; strip: EXIF / PNG text chunks removed;
                    keep: untouched
  OLE and other binary parts: every known value and every pattern match, in ASCII and UTF-16, is overwritten by `#` (same length)
  BinData names     a name that holds a detected value or a non-ASCII letter is renamed (`BinData/image1.png`) in every part
  preview           Preview/PrvText.txt masked like the text; Preview/PrvImage.png replaced by a white picture
  scripts           Scripts/ parts and their manifest entries are dropped
  user paths        `C:\\Users\\name\\...` keeps the file name only
"""
import html
import json
import os
import re
import struct
import zipfile
import zlib

from . import docscan

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, '..', '..', 'packs', 'doc-hidden', 'pack.json'), encoding='utf-8'))
BLOCK = RULES['mask_char']
REPL = RULES['replacement']
IMG = tuple(RULES['bindata']['images'])


def _png(w=8, h=8, rgb=(190, 190, 190)):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def _bmp(w=8, h=8, rgb=(190, 190, 190)):
    row = (bytes(reversed(rgb)) * w)
    row += b'\x00' * (-len(row) % 4)
    body = row * h
    return (b'BM' + struct.pack('<IHHI', 54 + len(body), 0, 0, 54) + struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0) + body)


def strip_metadata(name, data):
    """EXIF and text chunks out of a JPEG or PNG (pixels untouched)."""
    if data[:3] == b'\xff\xd8\xff':                       # JPEG: drop APP1 (EXIF, XMP), APP13 (IPTC), COM
        out, i = [data[:2]], 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            mk = data[i + 1]
            if mk == 0xDA:                                # start of scan: the rest is image data
                break
            n = int.from_bytes(data[i + 2:i + 4], 'big')
            if mk not in (0xE1, 0xED, 0xFE, 0xE2):
                out.append(data[i:i + 2 + n])
            i += 2 + n
        out.append(data[i:])
        return b''.join(out)
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        out, i = [data[:8]], 8
        while i + 8 <= len(data):
            n = int.from_bytes(data[i:i + 4], 'big')
            if data[i + 4:i + 8] not in (b'tEXt', b'zTXt', b'iTXt', b'eXIf', b'tIME'):
                out.append(data[i:i + 12 + n])
            i += 12 + n
        return b''.join(out)
    return data


def _scrub_binary(data, needles, patterns):
    """Overwrite values inside a binary part, same length: needles (strings) and regexes, ASCII and UTF-16."""
    n = 0
    for s in needles:
        if len(s) < 2:
            continue
        for enc in ('utf-8', 'utf-16-le', 'cp949'):
            try:
                raw = s.encode(enc)
            except UnicodeEncodeError:
                continue
            c = data.count(raw)
            if c:
                n += c
                data = data.replace(raw, (b'#' if enc != 'utf-16-le' else b'#\x00') * (len(raw) // (2 if enc == 'utf-16-le' else 1)))
    for rx in patterns:
        for enc, step in (('latin-1', 1), ('utf-16-le', 2)):
            try:
                text = data.decode(enc, 'replace') if enc == 'latin-1' else data[:len(data) // 2 * 2].decode('utf-16-le', 'replace')
            except Exception:
                continue
            for m in rx.finditer(text):
                a, b = m.start() * step, m.end() * step
                data = data[:a] + (b'#' if step == 1 else b'#\x00') * (m.end() - m.start()) + data[b:]
                n += 1
    return data, n


def redact(src, dst, session, images='placeholder'):
    stats = {'text': 0, 'hidden': 0, 'images': 0, 'binary': 0, 'dropped': 0}
    session.learn(src)
    det = session.det
    hidden = [v for _, v in docscan.hidden_values(src)]
    needles = sorted({e['value'] for e in session.vault.data['entries'].values() if len(e['value']) >= 2} | set(hidden), key=len, reverse=True)
    rx_bin = [rx for k in det.kinds.values() for rx, chk in k.patterns if chk in ('rrn', 'frn', 'card', 'brn', 'driving')]
    with zipfile.ZipFile(src) as z:
        items = [(it, z.read(it.filename)) for it in z.infolist()]
    names = {}
    for it, data in items:                                           # BinData names with a value or a non-ASCII letter
        if it.filename.startswith(RULES['bindata']['dir']) and not it.filename.endswith('/'):
            base = it.filename[len(RULES['bindata']['dir']):]
            if not base.isascii() or any(n in base for n in needles) or det.find(base):
                ext = os.path.splitext(base)[1]
                kind = 'image' if ext.lower() in IMG else 'object'
                names[it.filename] = f'{RULES["bindata"]["dir"]}{kind}{len(names) + 1}{ext}'
    sections, flat = {}, []                                    # the covered sections first: the preview text is made from them
    for it, data in items:
        if re.fullmatch(r'Contents/section\d+\.xml', it.filename):
            xml, k = _redact_section(data.decode('utf-8'), session, needles)
            sections[it.filename] = xml
            stats['text'] += k
            flat += [''.join(t for _, _, t in g) for g in sorted(docscan.paragraphs(xml), key=lambda g: g[0][0] if g else 0)]
    out = []
    for it, data in items:
        name = it.filename
        if any(name.startswith(d) for d in RULES['drop']):
            stats['dropped'] += 1
            continue
        if name in sections:
            data = sections[name].encode('utf-8')
        if name.lower().endswith(('.xml', '.hpf', '.rdf', '.txt', '.json')) and name != 'Preview/PrvText.txt':
            try:
                t = data.decode('utf-8')
            except UnicodeDecodeError:
                t = None
            if t is not None:
                t, k = _hidden_text(name, t, needles)
                stats['hidden'] += k
                for old, new in names.items():
                    t = t.replace(old, new).replace(os.path.basename(old), os.path.basename(new))
                data = t.encode('utf-8')
        elif name == 'Preview/PrvText.txt':
            enc = 'utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'
            t = '\r\n'.join(x for x in flat if x.strip())[:max(1024, len(data) // 2)]      # made again from the covered text
            t, k = _mask_blocks(t, session, needles)
            data = t.encode(enc)
            stats['hidden'] += 1
        elif name == 'Preview/PrvImage.png':
            data = _png(1, 1, (255, 255, 255))
            stats['images'] += 1
        elif name.startswith(RULES['bindata']['dir']):
            ext = os.path.splitext(name)[1].lower()
            if ext in IMG:
                if images == 'placeholder':
                    data = _bmp() if ext == '.bmp' else _png()
                    stats['images'] += 1
                elif images == 'strip':
                    data = strip_metadata(name, data)
            else:
                data, k = _scrub_binary(data, needles, rx_bin)
                stats['binary'] += k
        out.append((it, names.get(name, name), data))
    with zipfile.ZipFile(dst, 'w') as zo:
        for it, name, data in out:
            info = zipfile.ZipInfo(name, it.date_time)
            info.compress_type = it.compress_type
            info.external_attr = it.external_attr
            zo.writestr(info, data)
    return stats


def _mask_blocks(text, session, needles):
    """Detected and known values in plain text -> `■`. Returns (text, count)."""
    spans = session._spans(text)
    spans = [s for s in spans]
    out, last = [], 0
    for s in spans:
        out.append(text[last:s.start])
        out.append(re.sub(r'\S', BLOCK, text[s.start:s.end]))
        last = s.end
    out.append(text[last:])
    t = ''.join(out)
    return t, len(spans)


def _redact_section(xml, session, needles):
    """Paragraph by paragraph: detect on the joined text of the runs, blank the characters in the run nodes."""
    groups = docscan.paragraphs(xml)
    edits, count = [], 0
    for g in groups:
        text = ''.join(t for _, _, t in g)
        if not text.strip():
            continue
        mask = [False] * len(text)
        for s in session._spans(text):
            for i in range(s.start, s.end):
                mask[i] = True
            count += 1
        for v in needles:                                          # known values that a pattern does not see
            if len(v) >= 2 and v in text:
                for m in re.finditer(re.escape(v), text):
                    for i in range(m.start(), m.end()):
                        mask[i] = True
        if not any(mask):
            continue
        pos = 0
        for a, b, t in g:
            piece = ''.join(BLOCK if mask[pos + i] and not c.isspace() else c for i, c in enumerate(t))
            pos += len(t)
            if piece != t:
                edits.append((a, b, html.escape(piece, quote=False)))
    for a, b, new in sorted(edits, reverse=True):
        xml = xml[:a] + new + xml[b:]
    return xml, count


def _hidden_text(name, t, needles):
    n = 0
    meta = RULES['meta']
    if name == meta['part']:
        for key in meta['keys']:
            t, k = re.subn(rf'(<opf:meta name="{key}"[^>]*>)[^<]+(<)', rf'\1{REPL}\2', t)
            n += k
        for key in meta['dates']:
            t, k = re.subn(rf'(<opf:meta name="{key}"[^>]*>)[^<]+(<)', rf'\g<1>{meta["date_value"]}\2', t)
            n += k
        for tag in meta['tags']:
            t, k = re.subn(rf'(<{tag}\b[^>]*>)[^<]+(<)', rf'\1{REPL}\2', t)
            n += k
        t = re.sub(r'<opf:item\b[^>]*Scripts/[^>]*/>', '', t)
    for a in RULES['attrs']:
        if re.fullmatch(a['part'].replace('*', r'\d*'), name) or name == a['part']:
            val = a.get('value', REPL)
            t, k = re.subn(a['re'], lambda m: m.group(1) + val + m.group(3), t)
            n += k
    for tag in RULES['wipe_text_in']:
        def wipe(m):
            return re.sub(r'(<hp:t\b[^>]*>)([^<]+)(</hp:t>)', lambda x: x.group(1) + re.sub(r'\S', BLOCK, x.group(2)) + x.group(3), m.group(0))
        t, k = re.subn(rf'<{tag}\b.*?</{tag}>', wipe, t, flags=re.S)
        n += k
    for tag, attr in RULES['name_attrs']:
        t, k = re.subn(rf'(<{tag}\b[^>]*?\b{attr}=")([^"]*)(")', lambda m: m.group(1) + re.sub(r'\S', BLOCK, m.group(2)) + m.group(3), t)
        n += k
    for p in RULES['paths']:
        rx = re.compile(p)
        t, k = rx.subn(lambda m: m.group(0).replace('/', '\\').rsplit('\\', 1)[-1], t)
        n += k
    return t, n
