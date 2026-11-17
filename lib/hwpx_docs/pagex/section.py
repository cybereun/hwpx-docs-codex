"""Section and page features beyond `page/page.py`: builder hook (`build`) and reader hook (`read`).

  build(doc, sec, index, secpr, ctrls, ctx, text_w, mg) -> (secpr, ctrls)   registered as SECTION['build']
  read(reader, root, sec)                                                  registered as SECTION['read']

Spec keys of a section (a key at the top of the spec counts for section 0, like `header`): see spec.md in this folder.
Rules: rules.md (PX01-PX12).
"""
import functools
import os
import re
import xml.etree.ElementTree as ET
from ..core.units import TEMPLATE, esc, hu, line, read as read_text
from ..core.read import NS, mm, line_str

MASTER_TYPES = {'both': 'BOTH', 'even': 'EVEN', 'odd': 'ODD', 'last': 'LAST_PAGE', 'optional': 'OPTIONAL_PAGE'}
DIRECTIONS = {'horizontal': 'HORIZONTAL', 'vertical': 'VERTICAL', 'vertical_all': 'VERTICALALL'}
VIS_KEYS = {'header': 'hideFirstHeader', 'footer': 'hideFirstFooter', 'master_page': 'hideFirstMasterPage',
            'page_number': 'hideFirstPageNum', 'empty_line': 'hideFirstEmptyLine'}
# note shape: (xml element, attribute, spec key, kind); kinds: str, int, bool, len (mm), len1 (mm or "default" = -1: Hangul draws 5 cm; "column" is read as the same), enum (lower case)
NOTE_ATTRS = (('autoNumFormat', 'type', 'format', 'enum'), ('autoNumFormat', 'userChar', 'user_char', 'str'),
              ('autoNumFormat', 'prefixChar', 'prefix', 'str'), ('autoNumFormat', 'suffixChar', 'suffix', 'str'),
              ('autoNumFormat', 'supscript', 'superscript', 'bool'),
              ('noteLine', 'length', 'line_length', 'len1'),
              ('noteSpacing', 'betweenNotes', 'between', 'len'), ('noteSpacing', 'belowLine', 'below', 'len'),
              ('noteSpacing', 'aboveLine', 'above', 'len'),
              ('numbering', 'type', 'numbering', 'enum'), ('numbering', 'newNum', 'start', 'int'),
              ('placement', 'place', 'place', 'enum'), ('placement', 'beneathText', 'beneath_text', 'bool'))


def set_attr(xml, el, attr, value):
    """Set attribute `attr` of the first `hp:<el>` in `xml`."""
    pat = re.compile(rf'(<hp:{el}\b[^>]*?\s{attr}=")[^"]*(")')
    new, n = pat.subn(lambda m: m.group(1) + esc(value) + m.group(2), xml, count=1)
    if not n:
        raise ValueError(f'secPr has no hp:{el} with attribute {attr}')
    return new


def pick(sec, spec, index, key):
    """The key of the section, or (section 0) of the spec."""
    return sec.get(key, spec.get(key) if index == 0 else None)


@functools.lru_cache(maxsize=1)
def ns_decl():
    """Namespace declarations of the template section (Hangul copies them into every part)."""
    return re.search(r'<hs:sec ([^>]*)>', read_text(os.path.join(TEMPLATE, 'Contents', 'section0.xml'))).group(1)


# ---- builder -------------------------------------------------------------------------------------------------------
def master_xml(doc, m, ctx, text_w, text_h, n):
    """One `Contents/masterpageN.xml` (Hangul writes the root without a prefix, with all namespace declarations)."""
    kind = MASTER_TYPES[str(m.get('type', 'both')).lower()]
    body = doc.sublist(m.get('body') or [{'p': ''}], ctx, 'TOP', text_w, text_h)
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><masterPage {ns_decl()} id="masterpage{n}" type="{kind}" '
            f'pageNumber="{int(m.get("page", 0))}" pageDuplicate="{int(bool(m.get("duplicate")))}" '
            f'pageFront="{int(bool(m.get("front")))}">{body}</masterPage>')


def note_xml(xml, tag, shape):
    """Apply a note shape dict ({'format': 'circled_digit', 'suffix': ')', ...}) to `hp:<tag>` of the secPr."""
    sub = re.search(rf'<hp:{tag}>.*?</hp:{tag}>', xml, re.S).group(0)
    new = sub
    for el, attr, key, kind in NOTE_ATTRS:
        if key in shape:
            v = shape[key]
            v = (-1 if v in ('default', 'column') else hu(v)) if kind in ('len', 'len1') else int(bool(v)) if kind == 'bool' \
                else str(v).upper() if kind == 'enum' else v
            new = set_attr(new, el, attr, v)
    if 'line' in shape:
        for attr, v in zip(('type', 'width', 'color'), line(shape['line'])):
            new = set_attr(new, 'noteLine', attr, v)
    return xml.replace(sub, new)


def build(doc, sec, index, secpr, ctrls, ctx, text_w, mg):
    get = lambda k: pick(sec, doc.spec, index, k)           # noqa: E731
    for kind in ('header', 'footer'):                       # PX01: odd / even header and footer, one control each
        for apply in ('odd', 'even'):
            hf = get(f'{kind}_{apply}')
            if hf:
                blocks = hf.get('blocks') if isinstance(hf, dict) else hf
                hctx = dict(ctx, **(hf.get('style', {}) if isinstance(hf, dict) else {}))
                n = sum(('<hp:header ' in c) + ('<hp:footer ' in c) for c in ctrls) + 1
                ctrls.append(f'<hp:ctrl><hp:{kind} id="{n}" applyPageType="{apply.upper()}">'
                             f'{doc.sublist(blocks, hctx, "TOP" if kind == "header" else "BOTTOM", text_w, mg[kind])}'
                             f'</hp:{kind}></hp:ctrl>')
    if get('text_direction'):                               # PX05
        secpr = set_attr(secpr, 'secPr', 'textDirection', DIRECTIONS[get('text_direction')])
    if get('vertical_head'):                                # PX05: textVerticalWidthHead (COM TextVerticalWidthHead)
        secpr = set_attr(secpr, 'secPr', 'textVerticalWidthHead', int(get('vertical_head')))
    ln = get('line_numbers')                                # PX06
    if ln:
        ln = dict({'count_by': 1, 'start': 1, 'restart': 0, 'distance': 0}, **ln)
        secpr = set_attr(secpr, 'visibility', 'showLineNumber', 1)
        for attr, key, conv in (('restartType', 'restart', int), ('countBy', 'count_by', int), ('distance', 'distance', hu),
                                ('startNumber', 'start', int)):
            secpr = set_attr(secpr, 'lineNumberShape', attr, conv(ln[key]))
    if get('manuscript'):                                   # PX07
        secpr = set_attr(secpr, 'grid', 'wonggojiFormat', int(get('manuscript')))
    for key, attr in (('char_grid', 'charGrid'), ('line_grid', 'lineGrid')):    # PX07: grid cell size (mm)
        if get(key):
            secpr = set_attr(secpr, 'grid', attr, hu(get(key)))
    vis = get('hide_first') or {}                           # PX04
    for k, attr in VIS_KEYS.items():
        if k in vis:
            secpr = set_attr(secpr, 'visibility', attr, int(bool(vis[k])))
    for k in ('border', 'fill'):
        if k in vis:
            secpr = set_attr(secpr, 'visibility', k, str(vis[k]).upper())
    ns = get('note_shape') or {}                            # PX08
    for key, tag in (('footnote', 'footNotePr'), ('endnote', 'endNotePr')):
        if key in ns:
            secpr = note_xml(secpr, tag, ns[key])
    masters = get('master_pages')                           # PX02, PX03
    if masters:
        ph = int(re.search(r'<hp:pagePr [^>]*\bheight="(\d+)"', secpr).group(1))
        text_h = ph - mg['top'] - mg['bottom'] - mg['header'] - mg['footer']
        refs = ''
        for m in masters:
            n = sum(1 for k in doc.parts if k.startswith('Contents/masterpage'))
            doc.parts[f'Contents/masterpage{n}.xml'] = master_xml(doc, m, ctx, text_w, text_h, n).encode('utf-8')
            doc.manifest.append((f'masterpage{n}', f'Contents/masterpage{n}.xml'))
            refs += f'<hp:masterPage idRef="masterpage{n}"/>'
        secpr = set_attr(secpr, 'secPr', 'masterPageCnt', len(masters))
        secpr = secpr.replace('</hp:secPr>', refs + '</hp:secPr>')
    return secpr, ctrls


# ---- reader --------------------------------------------------------------------------------------------------------
def master_part(reader, idref):
    """Root element of the master page part that the manifest lists under `idref`."""
    hpf = ET.fromstring(reader.z.read('Contents/content.hpf'))
    for it in hpf.iter('{%s}item' % NS['opf']):
        if it.get('id') == idref:
            from ..core.read import safe_xml      # colours of a received file are checked before the preview draws them
            return safe_xml(reader.z.read(it.get('href')))
    raise ValueError(f'master page {idref} is not in the manifest')


def read_note(sp, tag, default):
    """Note shape of `hp:<tag>` in `sp`: the keys whose value differs from `default`."""
    el = sp.find(f'hp:{tag}', NS)
    out = {}
    for e, attr, key, kind in NOTE_ATTRS:
        v = el.find(f'.//hp:{e}', NS).get(attr)
        v = ('default' if v == '-1' else mm(v)) if kind in ('len', 'len1') else int(v) if kind == 'int' \
            else bool(int(v)) if kind == 'bool' else v.lower() if kind == 'enum' else v
        if v != default.get(key):
            out[key] = v
    ln = line_str(el.find('hp:noteLine', NS))
    if ln != default.get('line'):
        out['line'] = ln
    return out


@functools.lru_cache(maxsize=1)
def default_notes():
    secpr = re.search(r'<hp:secPr.*?</hp:secPr>', read_text(os.path.join(TEMPLATE, 'Contents', 'section0.xml')), re.S).group(0)
    sp = ET.fromstring(f'<hs:sec {ns_decl()}>{secpr}</hs:sec>').find('hp:secPr', NS)
    return {k: read_note(sp, t, {}) for k, t in (('footnote', 'footNotePr'), ('endnote', 'endNotePr'))}


def read(reader, root, sec):
    sp = root.find('.//hp:secPr', NS)
    if sp.get('textDirection') != 'HORIZONTAL':
        sec['text_direction'] = {v: k for k, v in DIRECTIONS.items()}[sp.get('textDirection')]
    if sp.get('textVerticalWidthHead', '0') != '0':
        sec['vertical_head'] = int(sp.get('textVerticalWidthHead'))
    vis = sp.find('hp:visibility', NS)
    if vis is not None:
        if vis.get('showLineNumber') == '1':
            ln = sp.find('hp:lineNumberShape', NS)
            sec['line_numbers'] = {'restart': int(ln.get('restartType')), 'count_by': int(ln.get('countBy')),
                                   'distance': mm(ln.get('distance')), 'start': int(ln.get('startNumber'))}
        hf = {k: True for k, a in VIS_KEYS.items() if vis.get(a) == '1'}
        hf.update({k: vis.get(k).lower() for k in ('border', 'fill') if vis.get(k) != 'SHOW_ALL'})
        if hf:
            sec['hide_first'] = hf
    g = sp.find('hp:grid', NS)
    if g is not None:
        if g.get('wonggojiFormat') not in (None, '0'):
            sec['manuscript'] = int(g.get('wonggojiFormat'))
        sec.update({k: mm(g.get(a)) for k, a in (('char_grid', 'charGrid'), ('line_grid', 'lineGrid')) if g.get(a, '0') != '0'})
    notes = {k: d for k, t in (('footnote', 'footNotePr'), ('endnote', 'endNotePr'))
             if (d := read_note(sp, t, default_notes()[k]))}
    if notes:
        sec['note_shape'] = notes
    masters = []
    for ref in sp.findall('hp:masterPage', NS):
        m = master_part(reader, ref.get('idRef'))
        d = {'type': {v: k for k, v in MASTER_TYPES.items()}[m.get('type')],
             'body': reader.paragraphs(m.find('hp:subList', NS))}
        if m.get('pageNumber', '0') != '0':
            d['page'] = int(m.get('pageNumber'))
        d.update({k: True for k, a in (('duplicate', 'pageDuplicate'), ('front', 'pageFront')) if m.get(a) == '1'})
        masters.append(d)
    if masters:
        sec['master_pages'] = masters
    # headers and footers: BOTH stays `header` / `footer`; odd and even go to their own keys
    for kind in ('header', 'footer'):
        sec.pop(kind, None)
    for ctrl in root.findall('hp:p/hp:run/hp:ctrl', NS):
        for c in ctrl:
            tag = c.tag.rsplit('}', 1)[-1]
            if tag in ('header', 'footer'):
                ap = c.get('applyPageType')
                sec[tag if ap == 'BOTH' else f'{tag}_{ap.lower()}'] = reader.paragraphs(c.find('hp:subList', NS))
