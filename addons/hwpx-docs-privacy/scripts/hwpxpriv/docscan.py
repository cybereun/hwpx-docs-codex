"""Read an HWPX as flat text (paragraph per line, in document order) and list its hidden places. Standard library only.

hwpx_texts(path)    -> [text of every part that holds text: sections, preview text, summary]
hidden_values(path) -> [(place, value)] author names, memo and hidden-comment text, field and bookmark names, user paths
"""
import html
import re
import zipfile

P_TOKEN = re.compile(r'<(/?)hp:p\b[^>]*?(/?)>|<hp:t\b[^>]*?(?:/>|>(.*?)</hp:t>)', re.S)
INNER = re.compile(r'<[^>]*>')
PLACEHOLDER = {'hwpx-docs', ''}
USER_PATH = re.compile(r'[A-Za-z]:\\+[Uu]sers\\+[^\\/:*?"<>|\r\n\x00]+(?:\\+[^\\/:*?"<>|\r\n\x00]+)*')


def paragraphs(xml):
    """[(start, end, text)] of every `hp:t` text node in document order, grouped per paragraph: [[(start, end, text)...], ...]."""
    stack, groups = [], []
    for m in P_TOKEN.finditer(xml):
        if m.group(0).startswith('<hp:p') or m.group(0).startswith('</hp:p'):
            close, selfc = m.group(1), m.group(2)
            if selfc:
                continue
            if close:
                if stack:
                    groups.append(stack.pop())
            else:
                stack.append([])
        elif m.group(3) is not None and stack:
            if '<' in m.group(3):
                continue                                   # a text node with inner elements: handled by the caller's fallback
            stack[-1].append((m.start(3), m.end(3), html.unescape(m.group(3))))
    groups += [g for g in stack if g]
    return groups


def hwpx_texts(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if re.fullmatch(r'Contents/section\d+\.xml', name):
                xml = z.read(name).decode('utf-8', 'replace')
                groups = sorted(paragraphs(xml), key=lambda g: g[0][0] if g else 0)
                out.append('\n'.join(''.join(t for _, _, t in g) for g in groups))
            elif name == 'Preview/PrvText.txt':
                raw = z.read(name)
                enc = 'utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'
                out.append(raw.decode(enc, 'replace'))
    return out


def hidden_values(path):
    vals = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            low = name.lower()
            if not low.endswith(('.xml', '.hpf', '.rdf', '.txt')):
                continue
            t = z.read(name).decode('utf-8', 'replace')
            if name == 'Contents/content.hpf':
                for m in re.finditer(r'<opf:meta name="(creator|lastsaveby|description|keyword|company|manager|author|title|subject)"[^>]*>([^<]*)<', t):
                    vals.append((m.group(1), html.unescape(m.group(2))))
                for m in re.finditer(r'<(?:dc:creator|dc:description|dc:title|dc:subject|opf:title)[^>]*>([^<]+)<', t):
                    vals.append(('title' if 'title' in m.group(0)[:12] else 'meta', html.unescape(m.group(1))))
            for m in re.finditer(r'<hh:trackChangeAuthor\b[^>]*?\bname="([^"]*)"', t):
                vals.append(('trackauthor', html.unescape(m.group(1))))
            for m in re.finditer(r'<hp:stringParam name="Author"[^>]*>([^<]*)<', t):
                vals.append(('memoauthor', html.unescape(m.group(1))))
            for m in re.finditer(r'<hp:(hiddenComment|memo|memogroup)\b.*?</hp:\1>', t, re.S):
                for tm in re.finditer(r'<hp:t\b[^>]*>([^<]+)</hp:t>', m.group(0)):
                    vals.append(('hidden', html.unescape(tm.group(1))))
            for m in USER_PATH.finditer(t):
                vals.append(('path', m.group(0)))
    return [(k, v) for k, v in vals if v.strip() not in PLACEHOLDER and len(v.strip()) >= 2 and not (k in ('title', 'subject') and _public_name(v))]


def _public_name(v):
    """A title or subject that is only fixed text of public blank forms ("민원 신청서") is a form name, not a value: it is not learned."""
    from . import detect
    return detect.FIXED.words_only(v)


def sniff(path):
    """'hwpx' (a zip with the sections of a Hangul document), 'hwp' (an OLE file: HWP 5) or None. By content: a renamed copy is found too."""
    import os
    try:
        if not os.path.isfile(path):
            return None
        with open(path, 'rb') as f:
            head = f.read(8)
        if head[:4] == b'PK\x03\x04':
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            return 'hwpx' if any(n.startswith('Contents/section') for n in names) or 'Contents/content.hpf' in names else None
        if head == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            return 'hwp'
    except (OSError, zipfile.BadZipFile):
        pass
    return None


def slots(path):
    """[{key, kind, label, text}] of a Hangul document through the core (only inside `hd`: the core is importable there), else []."""
    import sys
    kind = sniff(path)
    if not kind:
        return []
    mod = 'hwpx_docs.edit.edit' if kind == 'hwpx' else 'hwpx_docs.hwp5.edit'
    was = mod in sys.modules
    try:
        import importlib
        return importlib.import_module(mod).Doc(path).slots()
    except Exception:
        return []
    finally:
        if not was:
            sys.modules.pop(mod, None)                         # runpy runs this module next: no "found in sys.modules" warning


def hwp_summary(path):
    """The text properties of `\\x05HwpSummaryInformation` (title, subject, author, keywords, comments, last author; a title that is only fixed form text is left out) of an HWP."""
    import struct
    import sys
    was = 'hwpx_docs.hwp5.fmt' in sys.modules
    try:
        from hwpx_docs.hwp5 import fmt
        e = fmt.Package(path).streams.get('\x05HwpSummaryInformation')
        data = e.data if e is not None else b''
        off = struct.unpack_from('<I', data, 44)[0]
        n = struct.unpack_from('<I', data, off + 4)[0]
        out = []
        for i in range(min(n, 30)):
            pid, po = struct.unpack_from('<II', data, off + 8 + 8 * i)
            typ = struct.unpack_from('<I', data, off + po)[0]
            if typ == 0x1F:
                ln = struct.unpack_from('<I', data, off + po + 4)[0]
                v = data[off + po + 8:off + po + 8 + ln * 2].decode('utf-16-le', 'replace').rstrip('\x00')
            elif typ == 0x1E:
                ln = struct.unpack_from('<I', data, off + po + 4)[0]
                v = data[off + po + 8:off + po + 8 + ln].decode('cp949', 'replace').rstrip('\x00')
            else:
                continue
            if pid in (2, 3, 4, 5, 6, 8) and len(v.strip()) >= 2 and v.strip() not in PLACEHOLDER and not (pid in (2, 3) and _public_name(v.strip())):
                out.append(v.strip())
        return out
    except Exception:
        return []
    finally:
        if not was:
            sys.modules.pop('hwpx_docs.hwp5.fmt', None)


def template_index(folder):
    """{path: {key: text}} of the blank forms in a folder (cached per process)."""
    import hashlib
    import json
    import os
    from . import vault
    if folder in _TPL:
        return _TPL[folder]
    files = sorted(os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs if f.lower().endswith(('.hwp', '.hwpx')))
    stamp = hashlib.sha1(json.dumps([(p, os.path.getsize(p), int(os.path.getmtime(p))) for p in files]).encode('utf-8')).hexdigest()
    cache = os.path.join(vault.home(), 'templates-' + hashlib.sha1(os.path.abspath(folder).encode('utf-8')).hexdigest()[:12] + '.json')
    try:                                                   # blank forms are public: the index is a plain cache, rebuilt when a file changes
        c = json.load(open(cache, encoding='utf-8'))
        if c['stamp'] == stamp:
            _TPL[folder] = c['index']
            return c['index']
    except (OSError, ValueError, KeyError):
        pass
    out = {p: {s['key']: s['text'] for s in slots(p) if s['text'].strip()} for p in files}
    try:
        json.dump({'stamp': stamp, 'index': out}, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    except OSError:
        pass
    _TPL[folder] = out
    return out


_TPL = {}


def entered(path, rows, folder):
    """Slots whose text is not in the blank form (best matching template in `folder`): the values that a person typed.
    A form with no template: (None, [])."""
    idx = template_index(folder)
    cur = {r['key']: r['text'] for r in rows if r['text'].strip()}
    best, score = None, 0.0
    for p, tpl in idx.items():
        if not tpl:
            continue
        same = sum(1 for k, t in tpl.items() if cur.get(k) == t)
        s = same / len(tpl)
        if s > score:
            best, score = p, s
    if best is None or score < 0.8:
        return None, []
    tpl = idx[best]
    return best, [r for r in rows if r['text'].strip() and tpl.get(r['key']) != r['text']]
