"""덧말 (hp:dutmal): run item `{"dutmal": {"main": "본말", "sub": "덧말", "pos": "top|bottom", "size": 50, "align": "center"}}`.
Written as `<hp:dutmal posType szRatio option styleIDRef align><hp:mainText/><hp:subText/></hp:dutmal>` in the run (the
names and enums are the OWPML model's; textstyle/rules.md TS14-TS15)."""
from ..core.units import esc

ALIGNS = ('JUSTIFY', 'LEFT', 'RIGHT', 'CENTER', 'DISTRIBUTE', 'DISTRIBUTE_SPACE')
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def xml(d):
    d = d if isinstance(d, dict) else {}
    align = str(d.get('align', 'center')).upper()
    if align not in ALIGNS:
        raise ValueError(f'dutmal align {align!r}: one of {", ".join(a.lower() for a in ALIGNS)}')
    return (f'<hp:dutmal posType="{"BOTTOM" if str(d.get("pos", "top")).lower() == "bottom" else "TOP"}" '
            f'szRatio="{int(d.get("size", 50))}" option="{int(d.get("option", 0))}" styleIDRef="0" align="{align}">'
            f'<hp:mainText>{esc(str(d.get("main", "")))}</hp:mainText><hp:subText>{esc(str(d.get("sub", "")))}</hp:subText></hp:dutmal>')


def run(doc, piece, ctx):
    """Builder: a run item with the key `dutmal`."""
    if 'dutmal' not in piece:
        return None
    cid = doc.head.char_pr({**ctx, **{k: v for k, v in piece.items() if k != 'dutmal'}})
    return f'<hp:run charPrIDRef="{cid}">{xml(piece["dutmal"])}<hp:t/></hp:run>'


def read(reader, el):
    """Reader: hp:dutmal -> run item (the reader puts it in the paragraph's runs)."""
    def txt(tag):
        e = el.find(HP + tag)
        return ''.join(e.itertext()) if e is not None else ''
    d = {'main': txt('mainText'), 'sub': txt('subText')}
    if el.get('posType') == 'BOTTOM':
        d['pos'] = 'bottom'
    if el.get('szRatio') not in (None, '50'):
        d['size'] = int(el.get('szRatio'))
    if el.get('align') not in (None, 'CENTER'):
        d['align'] = el.get('align').lower()
    if el.get('option') not in (None, '0'):
        d['option'] = int(el.get('option'))
    return {'_run': True, 'dutmal': d}
