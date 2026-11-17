"""Identical list entries of the header are written once (rule HW83).

Hangul 2024 saves a HWPX as .hwp with every border fill, character shape and paragraph shape once: a list entry equal to an earlier
one is dropped and its number is replaced in every reference. It goes in steps, as the references of the entries move: border
fills first (5 of 153 forms had equal ones), then the character shapes and paragraph shapes, which can become equal once their
border fill number is the same (form 158604727: a paragraph shape that differed only in a duplicate border fill).

  dedupe(head, ver, bin_ref) -> {'borderFillIDRef': {old: new}, 'charPrIDRef': ..., 'paraPrIDRef': ...}   (head is changed in place)
  remap(root, maps)                                                                                      (a section tree)
"""
from .fo_head import border_fill, char_shape, first, kids, para_shape


def remap(root, maps):
    """Replace the numbers of the dropped entries in every attribute that names a list entry."""
    for el in root.iter():
        for attr, table in maps.items():
            v = el.get(attr)
            if v is not None and v in table:
                el.set(attr, table[v])


def _step(items, key, first_id):
    """Keep the first of equal entries. Returns (kept elements, {old id: new id}) with ids as strings."""
    seen, kept, mapping = {}, [], {}
    for el in items:
        k = key(el)
        old = el.get('id')
        if k in seen:
            mapping[old] = seen[k]
            continue
        new = str(first_id + len(kept))
        seen[k] = new
        kept.append(el)
        if new != old:
            mapping[old] = new
    return kept, mapping


def dedupe(head, ver, bin_ref):
    ref = first(head, 'refList')
    maps = {}
    for list_name, item_name, attr, key in (
            ('borderFills', 'borderFill', 'borderFillIDRef', lambda e: border_fill(e, bin_ref, ver)),
            ('charProperties', 'charPr', 'charPrIDRef', lambda e: char_shape(e, ver)),
            ('paraProperties', 'paraPr', 'paraPrIDRef', lambda e: para_shape(e, ver))):
        holder = first(ref, list_name)
        if holder is None:
            continue
        items = kids(holder, item_name)
        if not items:
            continue
        base = int(items[0].get('id', 0))
        kept, mapping = _step(items, key, base)
        if len(kept) != len(items) or mapping:
            for el in items:
                if el not in kept:
                    holder.remove(el)
            for el in kept:
                el.set('id', mapping.get(el.get('id'), el.get('id')))
            holder.set('itemCnt', str(len(kept)))
            maps[attr] = mapping
            remap(head, {attr: mapping})            # the later lists of the header refer to this one
    return maps
