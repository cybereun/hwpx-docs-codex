"""Form objects of OWPML (button, check box, radio, combo box, edit) -> the `form` control of an HWP 5.0 file (rule HW60).

  form(w, el, level) -> [[tag, level, bytes], ...]    CTRL_HEADER `form` and the property record (tag 0x5b)

The property record holds the object's properties as text: items `Key:type:value` each followed by one space, `wstring:N:`
with N characters, `set:N:` with the N characters of the items inside it. The key order below is the one of the five
pairs of hwp2hwpx (button, check_button, radio_button, combo_box, editor); the reading side is owpmlobj.form.
"""
import struct

from . import owpmlmap as om
from .fo_body import b, cid, rec
from .fo_head import color, first, ln, num, pick

KINDS = {'btn': '+pbt', 'checkBtn': '+cbt', 'radioBtn': '+rbt', 'comboBox': '+cob', 'edit': '+edt'}


def item(key, typ, value):
    if typ == 'wstring':
        return f'{key}:wstring:{len(value)}:{value} '
    if typ == 'bool':
        return f'{key}:bool:{1 if value else 0} '
    return f'{key}:int:{int(value)} '


def group(key, items):
    body = ''.join(items)
    return f'{key}:set:{len(body)}:{body} '


def form(w, el, level):
    tag = ln(el)
    desc = first(el, 'shapeComment')
    fcp = first(el, 'formCharPr')
    colour = lambda v: color(v, 0) & 0xFFFFFF
    common = group('CommonSet', [
        item('Name', 'wstring', el.get('name', '')), item('ForeColor', 'int', colour(el.get('foreColor'))),
        item('BackColor', 'int', colour(el.get('backColor'))), item('GroupName', 'wstring', el.get('groupName', '')),
        item('TabStop', 'bool', b(el.get('tabStop'))), item('TabOrder', 'int', num(el.get('tabOrder'))),
        item('Enabled', 'bool', b(el.get('enabled'))), item('BorderType', 'int', num(el.get('borderTypeIDRef'))),
        item('DrawFrame', 'bool', b(el.get('drawFrame'))), item('Command', 'wstring', el.get('command', '')),
        item('Editable', 'bool', b(el.get('editable'))), item('Printable', 'bool', b(el.get('printable')))])
    chars = group('CharShapeSet', [
        item('CharShapeID', 'int', num(fcp.get('charPrIDRef')) if fcp is not None else 0),
        item('FollowContext', 'bool', b(fcp.get('followContext')) if fcp is not None else 0),
        item('AutoSize', 'bool', b(fcp.get('autoSz')) if fcp is not None else 0),
        item('WordWrap', 'bool', b(fcp.get('wordWrap')) if fcp is not None else 0)])
    if tag == 'btn':
        own = group('ButtonSet', [item('Caption', 'wstring', el.get('caption', ''))])
    elif tag in ('checkBtn', 'radioBtn'):
        value = pick(om.inverse(om.FORM_VALUE), el.get('value', 'UNCHECKED'), 'button value')
        items = [item('Caption', 'wstring', el.get('caption', ''))]
        if tag == 'radioBtn':
            items.append(item('RadioGroupName', 'wstring', el.get('radioGroupName', '')))
        items += [item('Value', 'int', value), item('TriState', 'bool', b(el.get('triState'))),
                  item('BackStyle', 'int', pick(om.inverse(om.FORM_BACK), el.get('backStyle', 'TRANSPARENT'), 'back style'))]
        own = group('ButtonSet', items)
    elif tag == 'comboBox':
        li = first(el, 'listItem')
        own = group('ComboBoxSet', [
            item('ListBoxRows', 'int', num(el.get('listBoxRows'))),
            item('Text', 'wstring', (li.get('value') or '') if li is not None else ''),
            item('ListBoxWidth', 'int', num(el.get('listBoxWidth'))), item('EditEnable', 'bool', b(el.get('editEnable')))])
    else:                                                                    # edit
        txt = first(el, 'text')
        own = group('EditSet', [
            item('Text', 'wstring', (txt.text or '') if txt is not None else ''), item('MultiLine', 'bool', b(el.get('multiLine'))),
            item('PasswordChar', 'wstring', el.get('passwordChar', '')), item('MaxLength', 'int', num(el.get('maxLength'))),
            item('ScrollBars', 'int', pick(om.inverse(om.FORM_SCROLL), el.get('scrollBars', 'NONE'), 'scroll bars')),
            item('TabKeyBehavior', 'int', pick(om.inverse(om.FORM_TAB), el.get('tabKeyBehavior', 'NEXT_OBJECT'), 'tab key')),
            item('Number', 'bool', b(el.get('numOnly'))), item('ReadOnly', 'bool', b(el.get('readOnly'))),
            item('AlignText', 'int', pick(om.inverse(om.ALIGN3), el.get('alignText', 'LEFT'), 'text align'))])
    # the pairs end the text with two spaces: the last item's own and the one that closes the list
    text = (common + chars + own).rstrip(' ') + '  '
    data = cid(KINDS[tag]) * 2 + struct.pack('<IH', len(text), len(text)) + text.encode('utf-16-le')
    return [rec('CTRL_HEADER', level, w.common(el, 'form', (desc.text or '') if desc is not None else '')),
            rec(0x5B, level + 1, data)]
