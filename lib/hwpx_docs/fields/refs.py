"""References: cross-reference (상호 참조, C7.03), index mark and index (색인, C7.08), table of contents (차례, C7.07).

Run items (spec, inside a paragraph `p` list):
  {"xref": {"target": "mark1", "ref_type": "TARGET_TABLE", "content": "OBJECT_TYPE_PAGE", "link": false}}
      `hp:fieldBegin type="CROSSREF"` + `hp:fieldEnd`; Hangul fills in the shown number or page itself.
  {"index_mark": {"first": "Apple", "second": "pie"}}  or  {"index_mark": "Apple"}
      `hp:ctrl/hp:indexmark` (invisible in print).
Blocks (generated static paragraphs, as Hangul's 차례 만들기 / 찾아보기 만들기 write them):
  {"toc": {"levels": 3, "title": "차례", "pages": "auto" | {heading text: page}, "indent": 5}}
  {"index": {"title": "찾아보기", "pages": "auto" | {first key: page}}}
`pages: "auto"` builds the document once, lets the preview renderer (through core.registry.backend('pages', 'preview'))
tell on which page each heading or mark stands, and builds again. Without the renderer the page number is left out.
"""
from ..core import tmpdir
import html
import re

from ..core import registry
from ..core.units import esc

FIELDID = 628650598
HEAD = '<hp:ctrl><hp:fieldBegin id="{fid}" type="CROSSREF" name="" editable="0" dirty="0" zorder="-1" fieldid="%d">' % FIELDID


def xref(doc, p, ctx):
    """Builder hook for the run item `xref`."""
    x = p.get('xref')
    if not isinstance(x, (dict, str)):
        return None
    x = {'target': x} if isinstance(x, str) else x
    target = str(x.get('target', ''))
    fid = 1300000000 + doc.next_obj()
    cid = doc.head.char_pr(ctx)
    params = ['<hp:booleanParam name="Fiexde">1</hp:booleanParam>', '<hp:integerParam name="Prop">0</hp:integerParam>']
    if target:
        params.append(f'<hp:stringParam name="Command">{esc(target)}</hp:stringParam>')
    params += [f'<hp:stringParam name="RefPath">{esc(target.replace(":", chr(92) + ":"))};</hp:stringParam>',
               f'<hp:stringParam name="RefType">{esc(x.get("ref_type", "TARGET_TABLE"))}</hp:stringParam>',
               f'<hp:stringParam name="RefContentType">{esc(x.get("content", "OBJECT_TYPE_PAGE"))}</hp:stringParam>',
               f'<hp:booleanParam name="RefHyperLink">{"true" if x.get("link") else "false"}</hp:booleanParam>',
               '<hp:stringParam name="RefOpenType">HWPHYPERLINK_JUMP_CURRENTTAB</hp:stringParam>']
    return (f'<hp:run charPrIDRef="{cid}">{HEAD.format(fid=fid)}<hp:parameters cnt="{len(params)}" name="">{"".join(params)}'
            f'</hp:parameters></hp:fieldBegin></hp:ctrl></hp:run>'
            f'<hp:run charPrIDRef="{cid}"><hp:ctrl><hp:fieldEnd beginIDRef="{fid}" fieldid="{FIELDID}"/></hp:ctrl><hp:t/></hp:run>')


def index_mark(doc, p, ctx):
    """Builder hook for the run item `index_mark`."""
    m = p.get('index_mark')
    if not isinstance(m, (dict, str)):
        return None
    m = {'first': m} if isinstance(m, str) else m
    second = f'<hp:secondKey>{esc(m["second"])}</hp:secondKey>' if m.get('second') else ''
    return (f'<hp:run charPrIDRef="{doc.head.char_pr(ctx)}"><hp:ctrl><hp:indexmark><hp:firstKey>{esc(m.get("first", ""))}'
            f'</hp:firstKey>{second}</hp:indexmark></hp:ctrl><hp:t/></hp:run>')


# ---- generated lists ----------------------------------------------------------------------------------------------
def text_of(p):
    return p if isinstance(p, str) else ''.join(x if isinstance(x, str) else str(x.get('t', '')) for x in p or []
                                                if isinstance(x, (str, dict)) and not (isinstance(x, dict) and 'index_mark' in x and 't' not in x))


def bodies(spec):
    for sec in spec.get('sections') or [spec]:
        for b in sec.get('body', []):
            yield b


def headings(spec, levels):
    return [(int(b['outline_level']) + 1, text_of(b.get('p', '')).strip()) for b in bodies(spec)
            if isinstance(b, dict) and b.get('outline_level') is not None and int(b['outline_level']) < levels
            and text_of(b.get('p', '')).strip()]


def marks(spec):
    """[(first, second, paragraph text)] of every index mark in a top-level paragraph, in order."""
    out = []
    for b in bodies(spec):
        runs = b.get('p') if isinstance(b, dict) else None
        if not isinstance(runs, list):
            continue
        for r in runs:
            if isinstance(r, dict) and r.get('index_mark'):
                m = r['index_mark']
                m = {'first': m} if isinstance(m, str) else m
                out.append((m.get('first', ''), m.get('second', ''), text_of(runs).strip()))
    return out


def page_texts(path):
    """Text of every page of `path` as the preview draws it, or None when no renderer is registered."""
    fn = registry.backend('pages', 'preview')
    if fn is None:
        return None
    return [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))) for s in fn(path)]


def find_page(pages, text, start=0):
    """Index (0-based) of the first page from `start` that holds `text` (or its first 8 characters), else None."""
    key = re.sub(r'\s+', ' ', text).strip()
    for k in (key, key[:8]):
        if not k:
            return None
        for i in range(start, len(pages)):
            if k.replace(' ', '') in pages[i].replace(' ', ''):
                return i
    return None


def _width(doc):
    spec = doc.spec
    sec = (spec.get('sections') or [spec])[0]
    page = dict(spec.get('page', {}), **sec.get('page', {}))
    m = page.get('margin', {})
    return 210.0 - float(m.get('left', 30)) - float(m.get('right', 30))


def _pages(doc, wanted):
    """{key: page number} for the (key, text) pairs in `wanted`, by a first build and the preview renderer."""
    import os
    from ..core import build
    spec = dict(doc.spec)
    spec.pop('_toc_pass', None)
    tmp = os.path.join(tmpdir.mkdtemp('hwpx_docs_refs_'), 'pass.hwpx')
    build.write(dict(spec, _toc_pass=True), tmp)
    pages = page_texts(tmp)
    if not pages:
        return {}
    out, at = {}, 0
    for key, text in wanted:
        i = find_page(pages, text, at)
        if i is not None:
            out[key], at = i + 1, i
    return out


def _entry(text, page, indent, width, ctx_style=None):
    runs = [text] + ([{'tab': True}, str(page)] if page else [])
    b = {'p': runs, 'tabs': [{'pos': width, 'type': 'right', 'leader': 'dot'}], 'left': indent}
    return b


def toc(doc, b, ctx, extra, pending_break):
    """Builder hook for the block `toc`: static entries (heading, dotted tab, page number)."""
    c = b['toc']
    c = {} if c is True else c
    if not isinstance(c, dict):
        return None
    hs = headings(doc.spec, int(c.get('levels', 3)))
    pages = c.get('pages', 'auto')
    mask = bool(doc.spec.get('_toc_pass'))          # first pass: same room, no heading text to find on the list page
    if mask:
        pages = {i: 1 for i in range(len(hs))}
    elif pages == 'auto':
        pages = _pages(doc, [(i, t) for i, (_, t) in enumerate(hs)])
    else:
        pages = {i: pages.get(t) for i, (_, t) in enumerate(hs) if pages.get(t)}
    width = float(c.get('width', _width(doc)))
    blocks = []
    if c.get('title', '차례'):
        blocks.append({'p': c.get('title', '차례'), 'align': 'center', 'bold': True, 'size': 14})
    blocks += [_entry('#' * len(t) if mask else t, pages.get(i), (lv - 1) * float(c.get('indent', 5)), width)
               for i, (lv, t) in enumerate(hs)]
    return doc.blocks_xml(blocks, ctx, extra)


def index(doc, b, ctx, extra, pending_break):
    """Builder hook for the block `index`: group letter, first key, second key with page number."""
    c = b['index']
    c = {} if c is True else c
    if not isinstance(c, dict):
        return None
    ms = marks(doc.spec)
    mask = bool(doc.spec.get('_toc_pass'))
    pages = c.get('pages', 'auto')
    if mask:
        pages = {i: 1 for i in range(len(ms))}
    elif pages == 'auto':
        got = _pages(doc, [(i, m[2]) for i, m in enumerate(ms)])
        pages = {i: got.get(i) for i in range(len(ms))}
    else:
        pages = {i: pages.get(m[0]) for i, m in enumerate(ms)}
    tree = {}
    for i, (first, second, _) in enumerate(ms):
        if mask:
            first, second = '#' * len(first), '#' * len(second) if second else ''
        tree.setdefault(first, {}).setdefault(second, []).append(pages.get(i))
    width = float(c.get('width', _width(doc)))

    def pg(lst):
        ps = sorted({p for p in lst if p})
        return ', '.join(str(p) for p in ps)

    blocks = []
    if c.get('title', '찾아보기'):
        blocks.append({'p': c.get('title', '찾아보기'), 'align': 'center', 'bold': True, 'size': 14})
    group = None
    for first in sorted(tree, key=lambda k: (k.upper() if k.isascii() else '~' + k)):
        g = first[:1].upper()
        if g != group:
            group = g
            blocks.append({'p': f'({g})', 'bold': True})
        subs = tree[first]
        own = subs.pop('', [])
        if own or not subs:
            blocks.append(_entry(first, pg(own), 0, width))
        else:
            blocks.append({'p': first})
        blocks += [_entry(second, pg(subs[second]), 4, width) for second in sorted(subs)]
    return doc.blocks_xml(blocks, ctx, extra)
