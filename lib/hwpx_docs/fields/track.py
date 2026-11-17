"""Track changes (변경 추적, C7.12): run item `{"change": {...}}` <-> tracked text in a run.

  {"change": {"type": "insert|delete|format", "t": text, "author": str, "date": ISO time, "id": int, "paraend": bool}}
  (the char keys of the item, for example "bold", apply to the text; for `format` they are the new look)
Body: `hp:t` holds `<hp:insertBegin Id TcId/>text<hp:insertEnd Id TcId paraend/>` (delete: `deleteBegin/End`); a format change is a
run with `charTcId`. Header: `hh:trackChanges` (one `hh:trackChange` per change: type Insert|Delete|CharShape, date, authorID,
hide, id, charshapeID for CharShape), `hh:trackChangeAuthors`, and the flags of `hh:trackchageConfig` (sic) 56 -> 57 (on).
Reader: core/read.py (`Refs.tracks`, `text_of`, `change`). Builder hooks: BLOCKS `run.change` and `doc.header` (core.registry).
"""
import re

from ..core.units import esc

KIND = {'insert': 'Insert', 'delete': 'Delete', 'format': 'CharShape'}
TAG = {'insert': 'insert', 'delete': 'delete'}
DATE = '2000-01-01T00:00:00Z'          # the date of a change with no "date" (fixed, so a build gives the same file)
AUTHOR = 'hwpx-docs'
FLAGS_ON = 57                          # Hangul writes 56 with tracking off, 57 with it on (fixture track_change.hwpx)


def change(doc, p, ctx):
    """Builder hook for the run item `change`."""
    c = p.get('change')
    if not isinstance(c, dict):
        return None
    kind = c.get('type', 'insert')
    if kind not in KIND:
        raise ValueError(f'unknown change type: {kind!r}')
    tracks = doc.__dict__.setdefault('tracks', [])
    tid = int(c.get('id') or 0) or max([t['id'] for t in tracks] + [0]) + 1
    own = {k: v for k, v in p.items() if k != 'change'}
    rec = {'id': tid, 'type': KIND[kind], 'date': c.get('date') or DATE, 'author': c.get('author') or AUTHOR}
    cid = doc.head.char_pr(ctx)
    text = esc(c.get('t', ''))
    if kind == 'format':
        base = {k: v for k, v in ctx.items() if k not in own}          # the look before the change (the paragraph's)
        rec['charshape'] = doc.head.char_pr(base)
        tracks.append(rec)
        return f'<hp:run charPrIDRef="{cid}" charTcId="{tid}"><hp:t>{text}</hp:t></hp:run>'
    tracks.append(rec)
    t = TAG[kind]
    end = f'paraend="{1 if c.get("paraend") else 0}"'
    return (f'<hp:run charPrIDRef="{cid}"><hp:t><hp:{t}Begin Id="{tid}" TcId="{tid}"/>{text}'
            f'<hp:{t}End Id="{tid}" TcId="{tid}" {end}/></hp:t></hp:run>')


def header(doc, text):
    """Builder hook `doc.header`: the tracked changes and their authors into header.xml; tracking is switched on."""
    tracks = sorted(getattr(doc, 'tracks', []), key=lambda t: t['id'])
    if not tracks:
        return text
    authors = []
    for t in tracks:
        if t['author'] not in authors:
            authors.append(t['author'])
    items = ''.join(
        f'<hh:trackChange type="{t["type"]}" date="{esc(t["date"])}" authorID="{authors.index(t["author"]) + 1}" hide="0" '
        f'id="{t["id"]}"' + (f' charshapeID="{t["charshape"]}"' if t['type'] == 'CharShape' else '') + '/>' for t in tracks)
    names = ''.join(f'<hh:trackChangeAuthor name="{esc(a)}" mark="1" id="{i + 1}"/>' for i, a in enumerate(authors))
    block = (f'<hh:trackChanges itemCnt="{len(tracks)}">{items}</hh:trackChanges>'
             f'<hh:trackChangeAuthors itemCnt="{len(authors)}">{names}</hh:trackChangeAuthors>')
    text = text.replace('</hh:refList>', block + '</hh:refList>', 1)
    return re.sub(r'(<hh:trackchageConfig flags=")\d+', rf'\g<1>{FLAGS_ON}', text, count=1)
