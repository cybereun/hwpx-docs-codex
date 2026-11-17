"""Check an HWPX file against a fidelity checklist (references/image-to-hwpx.md, section 4).

  python check_xml.py <file.hwpx> <checklist.md>

Checklist rows are Markdown table rows: | id | element | query | expected | ... (more columns are ignored).
Prints one line per row: "<id> OK" or "<id> DIFF <actual>"; exit code 1 if any DIFF.

Queries run on the spec that hwpx2spec.py reads from the file, with inherited values resolved:
  page.size / page.landscape / page.margin.left ...       page setup of section 1 (section[2].page... for others)
  text("회의명").size                                       effective prop of the first text that contains the words:
      font size bold italic color align left indent before after line ... (char and para props, rules.md),
      cell.fill cell.valign cell.cs cell.rs cell.border.top  (when the text is in a table cell)
  table[0].cols / table[0].heights / table[0].border / table[0].rows  (tables in document order, nested ones too)
  count(table) / count(shape) / count(page_break)
Expected: number (tolerance 0.3, or write "12 ±0.5"), true/false, text (no case), or a JSON list
(numbers compared one by one with the tolerance).
"""
from ..core import tmpdir
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from ..core import read as hwpx2spec

DEF = dict(hwpx2spec.DEF_CHAR, **hwpx2spec.DEF_PARA)
INHERIT = (set(hwpx2spec.CHAR_KEYS) | set(hwpx2spec.DEF_PARA)) - {'page_break_before'}


class Index:
    def __init__(self, spec):
        self.spec = spec
        self.texts, self.tables, self.shapes, self.breaks = [], [], [], 0
        secs = spec.get('sections') or [spec]
        for s in secs:
            for part in ('header', 'footer'):
                hf = s.get(part)
                if hf:
                    self.blocks(hf['blocks'] if isinstance(hf, dict) else hf, dict(DEF), None)
            self.blocks(s.get('body', []), dict(DEF), None)

    def blocks(self, blocks, ctx, cell):
        for b in blocks:
            if isinstance(b, str):
                b = {'p': b}
            c = dict(ctx)
            c.update({k: v for k, v in b.items() if k not in ('p', 'table', 'shapes', 'pic')})
            if b.get('page_break'):
                self.breaks += 1
            for sh in b.get('shapes', []):
                self.shapes.append(sh)
                if isinstance(sh.get('text'), list):
                    self.blocks(sh['text'], dict(c), None)
                elif sh.get('text'):
                    self.texts.append((sh['text'], c, None))
            if 'table' in b:
                self.table(b['table'], {k: v for k, v in c.items() if k in hwpx2spec.CHAR_KEYS or k in DEF})
            p = b.get('p')
            if isinstance(p, str):
                for line in p.split('\n'):
                    self.texts.append((line, c, cell))
            elif isinstance(p, list):
                for r in p:
                    if isinstance(r, str):
                        self.texts.append((r, c, cell))
                    elif 't' in r:
                        rc = dict(c)
                        rc.update({k: v for k, v in r.items() if k != 't'})
                        self.texts.append((r['t'], rc, cell))
                    elif 'table' in r:
                        self.table(r['table'], c)

    def table(self, t, ctx):
        self.tables.append(t)
        base = dict(DEF)
        base.update({k: v for k, v in ctx.items() if k in hwpx2spec.CHAR_KEYS})
        for row in t['rows']:
            cells = row['cells'] if isinstance(row, dict) else row
            for cell in cells:
                cell = {'p': cell} if isinstance(cell, str) else cell
                cc = dict(base)
                cc.update({k: v for k, v in cell.items() if k in INHERIT})
                if 'blocks' in cell:
                    self.blocks(cell['blocks'], cc, cell)
                else:
                    self.blocks([{'p': cell.get('p', '')}], cc, cell)


def get(obj, path):
    for part in re.findall(r'[^.\[\]]+|\[\d+\]', path):
        if part.startswith('['):
            obj = obj[int(part[1:-1])]
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
        if obj is None:
            return None
    return obj


def query(ix, q):
    q = q.strip().strip('`')
    m = re.fullmatch(r'count\((table|shape|page_break)\)', q)
    if m:
        return {'table': len(ix.tables), 'shape': len(ix.shapes), 'page_break': ix.breaks}[m.group(1)]
    m = re.fullmatch(r'text\("(.+?)"\)\.(.+)', q)
    if m:
        needle, prop = m.groups()
        for text, props, cell in ix.texts:
            if needle in text:
                if prop.startswith('cell.'):
                    if cell is None:
                        return 'not in a cell'
                    v = get(cell, prop[5:])
                    if v is None:
                        v = {'valign': 'center', 'cs': 1, 'rs': 1}.get(prop[5:])
                    return v
                return props.get(prop, DEF.get(prop))
        return 'text not found'
    m = re.fullmatch(r'table\[(\d+)\]\.(.+)', q)
    if m:
        i = int(m.group(1))
        return get(ix.tables[i], m.group(2)) if i < len(ix.tables) else 'no such table'
    m = re.fullmatch(r'section\[(\d+)\]\.(.+)', q)
    if m:
        secs = ix.spec.get('sections') or [ix.spec]
        return get(secs[int(m.group(1)) - 1], m.group(2))
    secs = ix.spec.get('sections') or [ix.spec]
    return get(secs[0], q)


def same(actual, expected):
    e = expected.strip()
    tol = 0.3
    m = re.fullmatch(r'(.+?)\s*±\s*([\d.]+)', e)
    if m:
        e, tol = m.group(1), float(m.group(2))
    try:
        ev = json.loads(e)
    except ValueError:
        ev = e
    if isinstance(ev, bool) or isinstance(actual, bool):
        return bool(actual) == (ev if isinstance(ev, bool) else str(ev).lower() == 'true')
    if isinstance(ev, (int, float)) and isinstance(actual, (int, float)):
        return abs(actual - ev) <= tol
    if isinstance(ev, list) and isinstance(actual, list) and len(ev) == len(actual):
        return all(same(a, json.dumps(x) + f' ±{tol}') if isinstance(x, (int, float)) else same(a, json.dumps(x))
                   for a, x in zip(actual, ev))
    return str(actual).lower() == str(ev).lower()


def rows(md):
    for line in open(md, encoding='utf-8'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if not line.strip().startswith('|') or len(cells) < 4 or set(cells[0]) <= set('-: ') or cells[0].lower() == 'id':
            continue
        yield cells[0], cells[2], cells[3]


def main(hwpx, md):
    spec = hwpx2spec.read(hwpx, os.path.join(tmpdir.mkdtemp(), 'spec.json'))
    ix = Index(spec)
    bad = 0
    for rid, q, exp in rows(md):
        try:
            act = query(ix, q)
        except Exception as e:
            act = f'error {e}'
        if same(act, exp):
            print(rid, 'OK')
        else:
            bad += 1
            print(rid, 'DIFF', json.dumps(act, ensure_ascii=False) if not isinstance(act, str) else act)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
