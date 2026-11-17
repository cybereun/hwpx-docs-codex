"""Form objects (양식 개체, coverage C7.10): spec item <-> `hp:checkBtn|radioBtn|btn|comboBox|listBox|edit|scrollBar`.

Spec item (a run item, so it can stand in a paragraph beside text):
  {"form": {"type": "check|radio|button|combo|list|edit|scroll", "name": str, "caption": str, "checked": bool,
            "group": str (radio group), "items": [str | {"text", "value"}], "value": str (selected item),
            "text": str (edit), "multiline": bool, "readonly": bool, "max": int, "password": str, "align": "left|center|right",
            "number": bool, "border": bool, "color": "#RRGGBB", "fill": "#RRGGBB", "enabled": bool, "w": mm, "h": mm}}
Element names and attributes follow Hancom's open OWPML model (see rules.md F01-F07). No Hangul-made sample has been
read yet: rows are marked `model` until a Hangul render confirms them.
"""
import html
import re
import xml.etree.ElementTree as ET

from ..core.units import HU_PER, color, esc, hu

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
TAGS = {'check': 'checkBtn', 'radio': 'radioBtn', 'button': 'btn', 'combo': 'comboBox', 'list': 'listBox',
        'edit': 'edit', 'scroll': 'scrollBar'}
KINDS = {v: k for k, v in TAGS.items()}
BTN = ('check', 'radio', 'button')
VALUE = {'UNCHECKED': False, 'CHECKED': True, 'INDETERMINATE': 'mixed'}
ALIGN = {'left': 'LEFT', 'center': 'CENTER', 'right': 'RIGHT'}
FACE = '#F0F0F0'          # Windows control face, the default back colour of buttons (F03)
WHITE = '#FFFFFF'
MAXLEN = 2147483647        # Hangul's maxLength when the edit box has no limit
SHAPE_ATTRS = {'id', 'zOrder', 'numberingType', 'textWrap', 'textFlow', 'lock', 'dropcapstyle', 'href', 'groupLevel',
               'instid'}
COMMON = {'name', 'foreColor', 'backColor', 'groupName', 'tabStop', 'editable', 'tabOrder', 'enabled', 'borderTypeIDRef',
          'drawFrame', 'printable', 'command'}
OWN = {'check': {'caption', 'value', 'radioGroupName', 'triState', 'backStyle'},
       'combo': {'listBoxRows', 'listBoxWidth', 'editEnable', 'selectedValue'},
       'list': {'itemHeight', 'topIdx', 'selectedValue'},
       'edit': {'multiLine', 'passwordChar', 'maxLength', 'scrollBars', 'tabKeyBehavior', 'numOnly', 'readOnly', 'alignText'},
       'scroll': {'delay', 'largeChange', 'smallChange', 'min', 'max', 'page', 'value', 'type'}}
OWN['radio'] = OWN['button'] = OWN['check']
SCROLL = {'delay': '50', 'largeChange': '1', 'smallChange': '1', 'min': '0', 'max': '100', 'page': '10', 'value': '0',
          'type': 'HORIZONTAL'}
CHILDREN = {'sz', 'pos', 'outMargin', 'shapeComment', 'formCharPr', 'listItem', 'text'}


def mm(v):
    return round(int(v) / HU_PER['mm'], 2)      # 2 decimals: the builder gets the same hu back


def default_size(f):
    """(w, h) in mm of a form object with no size in the spec (10 pt text)."""
    kind = f.get('type', 'check')
    cap = str(f.get('caption', ''))
    text_w = sum(3.5 if ord(c) > 0x2E7F else 1.9 for c in cap)
    if kind in ('check', 'radio'):
        return round(5.5 + text_w, 1), 5.0
    if kind == 'button':
        return max(15.0, round(6 + text_w, 1)), 6.5
    if kind == 'list':
        return 30.0, max(15.0, 4.6 * len(f.get('items', [])) + 1)
    if kind == 'scroll':
        return 40.0, 4.0
    if kind == 'edit' and f.get('multiline'):
        return 40.0, 15.0
    return 30.0, 5.5


def items_of(f):
    out = []
    for i in f.get('items', []):
        out.append(i if isinstance(i, dict) else {'text': str(i), 'value': str(i)})
    return out


def xml(doc, f, ctx):
    """Spec form -> the element (one line of XML, no run around it)."""
    kind = f.get('type', 'check')
    if kind not in TAGS:
        raise ValueError(f'unknown form object type: {kind!r}')
    tag = TAGS[kind]
    w, h = default_size(f)
    w, h = hu(f.get('w', w)), hu(f.get('h', h))
    oid = doc.next_obj()
    solid = kind in ('edit', 'combo', 'list')
    # Hangul's own order (a file resaved by Hangul): the attributes of the type, the common attributes; children
    # formCharPr, list items or text, sz, pos, outMargin. It writes no shape attributes (id, zOrder, ...).
    own, body = '', ''
    if kind == 'button':
        own = f'caption="{esc(f.get("caption", ""))}" radioGroupName="" triState="0"'
    elif kind in BTN:
        state = {False: 'UNCHECKED', True: 'CHECKED', 'mixed': 'INDETERMINATE'}[f.get('checked', False)]
        own = (f'caption="{esc(f.get("caption", ""))}" value="{state}" '
               f'radioGroupName="{esc(f.get("group", "")) if kind == "radio" else ""}" '
               f'triState="{1 if f.get("checked") == "mixed" else 0}" backStyle="TRANSPARENT"')
    elif kind == 'combo':
        own = (f'listBoxRows="{int(f.get("rows", 10))}" listBoxWidth="0" editEnable="{1 if f.get("editable") else 0}" '
               f'selectedValue="{esc(f.get("value", ""))}"')
        body = ''.join(f'<hp:listItem displayText="{esc(i["text"])}" value="{esc(i["value"])}"/>' for i in items_of(f))
    elif kind == 'list':
        own = f'itemHeight="0" topIdx="4294967295" selectedValue="{esc(f.get("value", ""))}"'
        body = ''.join(f'<hp:listItem displayText="{esc(i["text"])}" value="{esc(i["value"])}"/>' for i in items_of(f))
    elif kind == 'edit':
        own = (f'multiLine="{1 if f.get("multiline") else 0}" passwordChar="{esc(f.get("password", ""))}" '
               f'maxLength="{int(f.get("max") or MAXLEN)}" scrollBars="{"VERTICAL" if f.get("multiline") else "NONE"}" '
               f'tabKeyBehavior="NEXT_OBJECT" numOnly="{1 if f.get("number") else 0}" '
               f'readOnly="{1 if f.get("readonly") else 0}" alignText="{ALIGN[f.get("align", "left")]}"')
        body = f'<hp:text>{esc(f.get("text", ""))}</hp:text>'
    else:
        own = 'delay="50" largeChange="1" smallChange="1" min="0" max="100" page="10" value="0" type="HORIZONTAL"'
    common = (f'name="{esc(f.get("name", ""))}" foreColor="{color(f.get("color"))}" '
              f'backColor="{color(f.get("fill"), WHITE if solid else FACE)}" groupName="" tabStop="1" '
              f'editable="1" tabOrder="{oid}" enabled="{0 if f.get("enabled") is False else 1}" borderTypeIDRef="0" '
              f'drawFrame="{0 if f.get("border") is False else 1}" printable="1" command=""')
    fc = '' if kind == 'scroll' else         f'<hp:formCharPr charPrIDRef="{doc.head.char_pr(ctx)}" followContext="0" autoSz="0" wordWrap="0"/>'
    tail = (f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
            'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/>')
    return f'<hp:{tag} {own} {common}>{fc}{body}{tail}</hp:{tag}>'


def piece(doc, p, ctx):
    """Builder hook (core.registry.block_handlers('run.form')): one run holding the form object, or None when `p` is not one."""
    if not isinstance(p.get('form'), dict):
        return None
    return f'<hp:run charPrIDRef="{doc.head.char_pr(ctx)}">{xml(doc, p["form"], ctx)}<hp:t/></hp:run>'


def parse(el):
    """Element (ElementTree element or XML text) -> spec form dict, or None when the spec cannot hold all of it
    (floating object, a child or attribute that the spec has no key for): the reader then keeps the raw XML."""
    if isinstance(el, str):
        el = ET.fromstring(_wrap(el))
    tag = el.tag.rsplit('}', 1)[-1]
    if tag not in KINDS:
        return None
    kind = KINDS[tag]
    kids = {c.tag.rsplit('}', 1)[-1]: c for c in el}
    if any(k not in CHILDREN for k in kids):
        return None
    if set(el.attrib) - SHAPE_ATTRS - COMMON - OWN[kind]:
        return None
    pos, sz = kids.get('pos'), kids.get('sz')
    if pos is None or sz is None or pos.get('treatAsChar') != '1':
        return None
    g = el.get
    f = {'type': kind}
    if g('name'):
        f['name'] = g('name')
    if g('foreColor', '#000000').upper() != '#000000':
        f['color'] = g('foreColor').upper()
    solid = kind in ('edit', 'combo', 'list')
    if g('backColor', '').upper() not in ('', WHITE if solid else FACE):
        f['fill'] = g('backColor').upper()
    if g('drawFrame') == '0':
        f['border'] = False
    if g('enabled') == '0':
        f['enabled'] = False
    if kind in BTN:
        if g('caption'):
            f['caption'] = g('caption')
        if g('value') in VALUE and VALUE[g('value')]:
            f['checked'] = VALUE[g('value')]
        if kind == 'radio' and g('radioGroupName'):
            f['group'] = g('radioGroupName')
    elif kind in ('combo', 'list'):
        if g('selectedValue'):
            f['value'] = g('selectedValue')
        if kind == 'combo' and g('editEnable') == '1':
            f['editable'] = True
        if kind == 'combo' and g('listBoxRows') not in (None, '10'):
            f['rows'] = int(g('listBoxRows'))
        li = [(c.get('displayText', ''), c.get('value', '')) for c in el if c.tag.endswith('listItem')]
        if li:
            f['items'] = [t if t == v else {'text': t, 'value': v} for t, v in li]
    elif kind == 'edit':
        t = kids.get('text')
        if t is not None and t.text:
            f['text'] = t.text
        for key, attr in (('multiline', 'multiLine'), ('readonly', 'readOnly'), ('number', 'numOnly')):
            if g(attr) == '1':
                f[key] = True
        if g('passwordChar'):
            f['password'] = g('passwordChar')
        if g('maxLength') not in (None, '0', str(MAXLEN)):
            f['max'] = int(g('maxLength'))
        al = {v: k for k, v in ALIGN.items()}.get(g('alignText', 'LEFT'), 'left')
        if al != 'left':
            f['align'] = al
    if kind == 'scroll' and {k: g(k) for k in OWN['scroll']} != SCROLL:
        return None                      # the spec has no keys for a scroll bar's range
    w, h = mm(sz.get('width')), mm(sz.get('height'))
    dw, dh = default_size(f)
    if abs(w - dw) > 0.01 or abs(h - dh) > 0.01:
        f['w'], f['h'] = w, h
    return f


def _wrap(text):
    """XML text of one `hp:` element -> parsable text (namespace declared on the root)."""
    return re.sub(r'^(\s*<[\w:]+)', lambda m: m.group(1) + f' xmlns:hp="{HP}"', text, count=1)


def read(reader, el):
    """Reader hook (core.registry.read_element): a form object in a run -> a run item {'form': spec}."""
    f = parse(el)
    return None if f is None else {'form': f, '_run': True}


# ---- reading and filling a finished file --------------------------------------------------------------------------
TAG_RE = re.compile(r'<hp:(checkBtn|radioBtn|btn|comboBox|listBox|edit|scrollBar)\b[^>]*?(?:/>|>.*?</hp:\1>)', re.S)


def scan(section_xml):
    """[(kind, spec dict or None, (start, end))] of the form objects in one section part."""
    return [(KINDS[m.group(1)], parse(_wrap(m.group(0))), m.span()) for m in TAG_RE.finditer(section_xml)]


def _set_attr(tag_xml, name, value):
    if re.search(rf'\s{name}="', tag_xml):
        return re.sub(rf'(\s{name}=")[^"]*(")', lambda m: m.group(1) + esc(value) + m.group(2), tag_xml, count=1)
    return tag_xml.replace(' ', f' {name}="{esc(value)}" ', 1)


def fill_one(el_xml, kind, value):
    """Element text of one form object with `value` set: check/radio: True/False; combo, list: the selected text
    (the item's value is used when the text matches an item); edit: the text. Returns None if the value is unusable."""
    head_end = el_xml.index('>') + 1
    head, rest = el_xml[:head_end], el_xml[head_end:]
    if kind in BTN:
        on = value if isinstance(value, bool) else str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on', 'checked', '☑', '✓', 'x')
        return _set_attr(head, 'value', 'CHECKED' if on else 'UNCHECKED') + rest
    if kind in ('combo', 'list'):
        items = [(html.unescape(m.group(1)), html.unescape(m.group(2)))
                 for m in re.finditer(r'<hp:listItem displayText="([^"]*)" value="([^"]*)"', rest)]
        v = str(value)
        sel = next((t for t, val in items if v in (t, val)), None if items else v)
        return None if sel is None else _set_attr(head, 'selectedValue', sel) + rest
    if kind == 'edit':
        if '<hp:text>' in rest or '<hp:text/>' in rest:
            rest = re.sub(r'<hp:text(?:/>|>.*?</hp:text>)', lambda m: f'<hp:text>{esc(value)}</hp:text>', rest, count=1, flags=re.S)
        else:
            rest = rest.replace('</hp:edit>', f'<hp:text>{esc(value)}</hp:text></hp:edit>')
        return head + rest
    return None


def _attrs(el_xml):
    head = el_xml[:el_xml.index('>') + 1]
    return {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'\s([\w:]+)="([^"]*)"', head)}


def fill_section(section_xml, values):
    """(new section XML, set of keys used). `values` = {key: value}; key = the object's name, or for radio buttons the
    group name with the caption of the button to select (the others of the group are cleared)."""
    used, out, last = set(), [], 0
    for m in TAG_RE.finditer(section_xml):
        kind, a = KINDS[m.group(1)], _attrs(m.group(0))
        new = None
        if kind == 'radio' and a.get('radioGroupName') in values:
            used.add(a['radioGroupName'])
            new = fill_one(m.group(0), kind, a.get('caption') == str(values[a['radioGroupName']]))
        elif a.get('name') and a['name'] in values:
            new = fill_one(m.group(0), kind, values[a['name']])
            if new is not None:
                used.add(a['name'])
        out.append(section_xml[last:m.start()])
        out.append(m.group(0) if new is None else new)
        last = m.end()
    out.append(section_xml[last:])
    return ''.join(out), used


def fill_file(src, dst, values):
    """Fill the form objects of a finished HWPX; returns the keys that matched nothing. Everything else is copied."""
    import zipfile
    missing = set(values)
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, 'w') as zo:
        for info in zi.infolist():
            data = zi.read(info.filename)
            if re.fullmatch(r'Contents/section\d+\.xml', info.filename):
                text, used = fill_section(data.decode('utf-8'), values)
                data, missing = text.encode('utf-8'), missing - used
            zo.writestr(info, data, compress_type=info.compress_type)
    return sorted(missing)


def listing(path):
    """[(section name, kind, attrs dict)] of every form object of a finished HWPX."""
    import zipfile
    out = []
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            if re.fullmatch(r'Contents/section\d+\.xml', n):
                for m in TAG_RE.finditer(z.read(n).decode('utf-8')):
                    out.append((n, KINDS[m.group(1)], _attrs(m.group(0))))
    return out
