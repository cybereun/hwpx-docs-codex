"""Profiles of pagefit: the readability rules as a named style that the user switches on (rules PF22).

A profile is a JSON object; `profiles/minimal.json` (what `hd pagefit` does with no profile: the first version, the least change) and
`profiles/readable.json` (reading units kept whole, long tables cut between rows, full pages) ship with the package; a user profile is
any JSON file with the same keys. `load(None | name | path | dict)` gives the whole profile (every key filled from `minimal`), checked.

  {"name": "mine", "description": "...", "extends": "readable",          # optional: start from a built-in profile or a file
   "check": {"kinds": [...], "fill": 85, "last_lines": 3},
   "fix": {"keep":      {"headings": true, "widow": true},
           "units":     {"strong": [...kinds], "weak": [...kinds], "section_ratio": 0.4, "list_ratio": 0.5, "item_ratio": 0.8,
                         "heading_lines": 8},
           "tables":    {"cut_between_rows": false, "repeat_header": false, "min_rows": 0, "header_only_fix": true,
                         "split_gap_mm": 0, "split_min_ratio": 0.33, "free_heights": false, "hold_whole": false},
           "breaks":    {"remove_after_empty": true, "break_fill": 70, "heading_before_break": true, "pull_up": false, "unit_break": false,
                         "chain_start": true, "chain_max": 6},
           "notes":     {"move_paragraph": false},
           "last_page": {"pull_back": true, "last_lines": 3, "max_shrink": 3},
           "spacing":   {"fill": true, "tables": false, "max_extra": 6, "safety": 1.5, "safety_flow": 8}}}

Only the keys you write change; the others stay as in `extends` (or `minimal`). Unit kinds: heading, item, table, figure, box, attach,
tail (strong), section, list (weak). Finding kinds of `check`: unit, table_rows, table_head, table_cell, table, ref, note, order,
pageref, heading, orphan_end, orphan_start, empty, last, skipped. A wrong key or value stops with a message that names it.
`tables.repeat_header` also gives a table that goes over a page a repeated first row when that row looks like a header (fill or bold);
`tables.hold_whole` turns on `hold` (개체와 조판 부호를 항상 같은 쪽에 놓기) for every table kept whole that fits on a page (rules PF26).
"""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT_KINDS = ('heading', 'item', 'table', 'figure', 'box', 'attach', 'tail', 'section', 'list')
STRONG_KINDS = ('heading', 'item', 'table', 'figure', 'box', 'attach', 'tail')
WEAK_KINDS = ('section', 'list')
FINDING_KINDS = ('unit', 'table_rows', 'table_head', 'table_cell', 'table', 'ref', 'note', 'order', 'pageref', 'heading', 'orphan_end',
                 'orphan_start', 'empty', 'last', 'skipped')

# key -> default (= `minimal`); the type of the default is the type a value must have (a number may be an int or a float)
DEFAULT = {
    'name': 'minimal', 'description': '',
    'check': {'kinds': ['empty', 'heading', 'orphan_end', 'orphan_start', 'table', 'order', 'last', 'skipped'], 'fill': 85.0,
              'last_lines': 3},
    'fix': {
        'keep': {'headings': True, 'widow': True},
        'units': {'strong': [], 'weak': [], 'section_ratio': 0.4, 'list_ratio': 0.5, 'item_ratio': 0.8, 'heading_lines': 8},
        'tables': {'cut_between_rows': False, 'repeat_header': False, 'min_rows': 0, 'header_only_fix': True,
                   'split_gap_mm': 0.0, 'split_min_ratio': 0.33, 'free_heights': False, 'hold_whole': False},
        'breaks': {'remove_after_empty': True, 'break_fill': 70.0, 'heading_before_break': True, 'pull_up': False, 'unit_break': False,
                   'chain_start': True, 'chain_max': 6},
        'notes': {'move_paragraph': False},
        'last_page': {'pull_back': True, 'last_lines': 3, 'max_shrink': 3.0},
        'spacing': {'fill': True, 'tables': False, 'max_extra': 6.0, 'safety': 1.5, 'safety_flow': 8.0},
    },
}
LISTS = {('check', 'kinds'): FINDING_KINDS, ('fix', 'units', 'strong'): STRONG_KINDS, ('fix', 'units', 'weak'): WEAK_KINDS}
# the keyword arguments of check() and fix() -> where they live in a profile (a call can still override one value)
KW = {'fill': ('check', 'fill'), 'last_lines': ('check', 'last_lines'), 'min_rows': ('fix', 'tables', 'min_rows'),
      'section_ratio': ('fix', 'units', 'section_ratio'), 'list_ratio': ('fix', 'units', 'list_ratio'),
      'break_fill': ('fix', 'breaks', 'break_fill'), 'max_extra': ('fix', 'spacing', 'max_extra'),
      'max_shrink': ('fix', 'last_page', 'max_shrink'), 'safety': ('fix', 'spacing', 'safety'),
      'safety_flow': ('fix', 'spacing', 'safety_flow')}


def builtin():
    """{name: path} of the profiles that ship with the package."""
    d = os.path.join(HERE, 'profiles')
    return {f[:-5]: os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.json')} if os.path.isdir(d) else {}


def _read(ref):
    """A profile reference -> its JSON object: a dict, a built-in name or a path."""
    if isinstance(ref, dict):
        return ref
    names = builtin()
    path = names.get(ref) if ref in names else ref
    if not os.path.isfile(str(path)):
        raise ValueError(f'unknown profile "{ref}": built-in profiles are {", ".join(names) or "none"}; or give the path of a JSON file')
    try:
        return json.load(open(path, encoding='utf-8'))
    except ValueError as e:
        raise ValueError(f'profile {path} is not valid JSON: {e}') from None


def _merge(base, extra, path=()):
    """`extra` over `base`, key by key; a key that `base` does not know stops with its path."""
    out = copy.deepcopy(base)
    for k, v in extra.items():
        where = '.'.join(path + (k,))
        if k in ('extends',):
            continue
        if k not in base:
            raise ValueError(f'profile key "{where}" is not known (known here: {", ".join(base)})')
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f'profile key "{where}" must be an object')
            out[k] = _merge(base[k], v, path + (k,))
        else:
            out[k] = _check_value(path + (k,), base[k], v)
    return out


def _check_value(path, default, v):
    where = '.'.join(path)
    if path in LISTS:
        if not isinstance(v, list) or any(x not in LISTS[path] for x in v):
            raise ValueError(f'profile key "{where}" must be a list of: {", ".join(LISTS[path])}')
        return list(v)
    if isinstance(default, bool):
        if not isinstance(v, bool):
            raise ValueError(f'profile key "{where}" must be true or false')
    elif isinstance(default, (int, float)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f'profile key "{where}" must be a number of 0 or more')
        return type(default)(v) if isinstance(default, int) and float(v).is_integer() else v
    elif isinstance(default, str) and not isinstance(v, str):
        raise ValueError(f'profile key "{where}" must be text')
    return v


def load(ref=None, **kw):
    """The whole profile: `ref` None (= minimal), a built-in name, a path or a dict; `extends` names the profile it starts from.
    Keyword arguments (fill, last_lines, min_rows, break_fill, max_extra, max_shrink, safety, safety_flow, section_ratio, list_ratio)
    override single values (a command line option)."""
    prof = copy.deepcopy(DEFAULT)
    if ref is not None:
        raw = _read(ref)
        chain, seen = [raw], set()
        while isinstance(chain[0].get('extends'), (str, dict)):
            key = chain[0]['extends']
            if isinstance(key, str):
                if key in seen:
                    raise ValueError(f'profile "extends" loops at "{key}"')
                seen.add(key)
            chain.insert(0, _read(key))
        for part in chain:
            prof = _merge(prof, part)
    for k, v in kw.items():
        if v is None:
            continue
        if k not in KW:
            raise TypeError(f'unknown option {k}')
        cur = prof
        for key in KW[k][:-1]:
            cur = cur[key]
        cur[KW[k][-1]] = _check_value(KW[k], cur[KW[k][-1]], v)
    return prof
