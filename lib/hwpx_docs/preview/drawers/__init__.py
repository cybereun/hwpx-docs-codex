"""Drawers of the preview: one module per kind of object registers how to draw it; layout.py only dispatches.

Every module in this folder is imported once (by name) the first time a drawer is looked up. A module calls:
  register(key, fn)          a spec item {key: {...}} (a block or a run item), for example "chart"
  register_inline(tag, fn)   a raw OWPML element that the reader kept as {"xml": "<tag ...>"}, for example "hp:compose"
fn(item, style) -> {"w": mm, "h": mm, "draw": draw, "base": mm or None} or None
  item   the spec dict of the object (register) or the raw XML text (register_inline)
  style  the char style at that place (keys of core.read.CHAR_KEYS: font, size in pt, color, bold, ...)
  w, h   the room the object takes on the page, in mm
  base   distance from the object's top to the text baseline (None: the object's bottom sits on the baseline)
  draw(x, y) -> [SVG elements, lengths in mm, the object's top-left corner at (x, y)], or None at draw time
None (from fn or from draw) = "cannot draw it": the preview draws a dashed box with the type name and prints one line
"PREVIEW NOT DRAWN <type> <w> x <h> mm on page <n>". A feature package may instead register DRAWS in its own
__init__.py (core/registry.py, fn(item, x, y) -> [SVG elements] | None, the item has w and h); this file wraps those.
Placement: an item with "inline": false and "pos" {x, y, rel} floats like a picture; otherwise it sits on the line.

Three more hooks (docs/interfaces.md "Preview drawers"):
  register_paint(kind, fn)            a fill {"type": kind, ...} (gradient, image) of a cell, shape, paragraph or page border
  register_table_wrap(fn)             a table block drawn another way (caption, a table with `pos`)
  register_page_layer(fn, z)          SVG under or over the body of every page (바탕쪽, line numbers, 원고지 grid)
"""
import functools
import importlib
import pkgutil

from ...core import registry

_BLOCK, _INLINE = {}, {}
_loaded = []


def register(key, fn):
    _BLOCK[key] = fn


def register_inline(tag, fn):
    _INLINE[tag] = fn


def unregister(key=None, tag=None):
    _BLOCK.pop(key, None)
    _INLINE.pop(tag, None)


def _load():
    if not _loaded:
        _loaded.append(True)
        for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
            importlib.import_module(f'{__name__}.{m.name}')


@functools.lru_cache(maxsize=None)
def _package(key):
    """DRAWS of feature packages for `key`, wrapped as a drawer of this folder (None when no package has it)."""
    hs = tuple(registry.draw_handlers(key))
    if not hs:
        return None

    def fn(item, style):
        if not ('w' in item and 'h' in item):
            return None

        def draw(x, y):
            for h in hs:
                out = h(item, x, y)
                if out is not None:
                    return out
            return None
        return {'w': item['w'], 'h': item['h'], 'draw': draw, 'base': None}
    return fn


def block(key):
    """Drawer fn(item, style) of a spec key, or None."""
    _load()
    return _BLOCK.get(key) or _package(key)


def inline(tag):
    """Drawer fn(xml, style) of a raw element tag, or None."""
    _load()
    return _INLINE.get(tag)


def key_of(d):
    """The key of `d` whose value is a dict that a drawer draws, or None."""
    return next((k for k, v in d.items() if isinstance(v, dict) and block(k)), None)


# ---- fills, table wrappers, page layers ----------------------------------------------------------------------------
_PAINT, _WRAP, _LAYER = {}, [], {'under': [], 'over': []}


def register_paint(kind, fn):
    """fn(ctx, page, fill, w, h) -> SVG paint string for a fill {"type": kind, ...}; it may append <defs> to page.svg."""
    _PAINT[kind] = fn


def paint(ctx, page, fill, w, h):
    """A fill value (cell, shape, paragraph, page border) -> the SVG paint to use. A string (colour) comes back as it is;
    a dict goes to the drawer registered for fill["type"] ('gradient', 'image', ...). A dict that nobody paints gives its
    first colour (or none) and one line "PREVIEW NOT DRAWN fill <type>"."""
    if not isinstance(fill, dict):
        return fill
    _load()
    fn = _PAINT.get(fill.get('type'))
    if fn:
        return fn(ctx, page, fill, w, h)
    print('PREVIEW NOT DRAWN fill %s %.1f x %.1f mm on page %s' % (fill.get('type'), w, h, getattr(page, 'no', '?')))
    return fill.get('color') or (fill.get('colors') or [None])[0]


def register_table_wrap(fn, first=False):
    """fn(ctx, block, style, width, layout_table, layout_para) -> [atoms] or None ("not mine"). first: asked before the
    wrappers registered so far (a wrapper for a special case, like the tables of 세로쓰기)."""
    _WRAP.insert(0, fn) if first else _WRAP.append(fn)


def table_wrap(ctx, b, style, w, layout_table, layout_para):
    """Atoms of a table block from the first wrapper that takes it (captions, a table with `pos`, ...), or None (the
    plain table path)."""
    _load()
    for fn in _WRAP:
        atoms = fn(ctx, b, style, w, layout_table, layout_para)
        if atoms is not None:
            return atoms
    return None


def register_page_layer(fn, z='under'):
    """fn(ctx, page, info) -> [SVG elements] drawn under (z='under') or over (z='over') the body of every page."""
    _LAYER[z].append(fn)


def page_layers(z):
    _load()
    return list(_LAYER[z])


_PREPARE = []


def register_prepare(fn):
    """fn(spec, pic_dir): change the spec in place before the layout (a paragraph-level feature that the layout has no hook for
    becomes run items that a drawer draws; pic_dir holds the pictures that the reader saved)."""
    _PREPARE.append(fn)


def prepare(spec, pic_dir):
    _load()
    for fn in _PREPARE:
        fn(spec, pic_dir)


def unregister_hooks(paint_kind=None, wrap=None, layer=None):
    """Remove one fill painter, table wrapper or page layer (self-tests)."""
    _PAINT.pop(paint_kind, None)
    for lst in [_WRAP] + list(_LAYER.values()):
        while wrap in lst:
            lst.remove(wrap)
        while layer in lst:
            lst.remove(layer)
