"""Feature packages register themselves; nothing else is edited to add or change one.

A sub-package of hwpx_docs can define in its __init__.py:
  COMMANDS = {'name': ('module', [prefix args], 'usage line')}   -> `hd name ...` runs hwpx_docs.<package>.<module>
  def selftest(): ...                                              -> `hd selftest` runs it as "SELFTEST <package>"
The __init__.py is imported by every `hd` call, so it imports nothing heavy at the top.
"""
import importlib
import pkgutil

ROOT = __package__.rpartition('.')[0]          # 'hwpx_docs'


def packages():
    """(name, package) of every sub-package of hwpx_docs, by name."""
    root = importlib.import_module(ROOT)
    for m in sorted(pkgutil.iter_modules(root.__path__), key=lambda m: m.name):
        if m.ispkg:
            yield m.name, importlib.import_module(f'{ROOT}.{m.name}')


def commands():
    """{command: (package.module, prefix args, usage line)}; a name registered twice stops."""
    out = {}
    for name, pkg in packages():
        for cmd, (mod, pre, usage) in getattr(pkg, 'COMMANDS', {}).items():
            if cmd in out:
                raise ValueError(f'command "{cmd}" registered by {out[cmd][0]} and {name}.{mod}')
            out[cmd] = (f'{name}.{mod}', list(pre), usage)
    return out


def tests():
    """{package: selftest function}."""
    return {name: pkg.selftest for name, pkg in packages() if callable(getattr(pkg, 'selftest', None))}


def backend(kind, name):
    """Function of the backend `name` of kind `kind` (for example kind "render", name "preview"), or None.
    A package lists them in its __init__.py: BACKENDS = {'render': {'preview': 'module:function'}}."""
    for pname, pkg in packages():
        ref = getattr(pkg, 'BACKENDS', {}).get(kind, {}).get(name)
        if ref:
            return _resolve(pname, ref)
    return None


# ---- hooks of the builder and the reader (a package that adds a spec block or reads an OWPML element) -------------
# In the package __init__.py (strings 'module:function' so that nothing heavy is imported at the top):
#   BLOCKS = {'spec-key': 'section:block'}   builder: fn(doc, block, ctx, extra, pending_break) -> [paragraph xml] |
#                                            a substitute block (dict, for example a fallback) | None ("not mine")
#   READS = {'xml-tag': 'section:read'}      reader: fn(reader, element) -> block item dict | None
#   DRAWS = {'spec-key': 'draw:svg'}         viewer (preview): fn(item, x, y) -> [SVG elements, lengths in mm, top-left
#                                            corner at x, y; the item has w and h in mm] | None ("cannot draw it")
# The package may keep extra zip parts in `doc.parts` ({'Chart/chart1.xml': bytes}); core.build.write stores them.
def _resolve(name, ref):
    mod, _, fn = ref.partition(':')
    return getattr(importlib.import_module(f'{ROOT}.{name}.{mod}'), fn)


def block_handlers(key):
    """Builder handlers of every package for the spec key `key`."""
    return [_resolve(n, p.BLOCKS[key]) for n, p in packages() if key in getattr(p, 'BLOCKS', {})]


#   SECTION = {'build': 'mod:fn', 'read': 'mod:fn'}   section level keys. build: fn(doc, sec, index, secpr, ctrls, ctx, text_w, mg)
#                                            -> (secpr, ctrls); read: fn(reader, root, sec) fills the section dict
def section_hooks(kind):
    """Section hooks of every package: kind 'build' or 'read'."""
    return [_resolve(n, p.SECTION[kind]) for n, p in packages() if kind in getattr(p, 'SECTION', {})]


def draw_handlers(key):
    """Viewer handlers of every package for the spec key `key`."""
    return [_resolve(n, p.DRAWS[key]) for n, p in packages() if key in getattr(p, 'DRAWS', {})]


#   POST = {'pic': 'mod:fn', 'shape': 'mod:fn'}   builder: fn(doc, spec, xml, *args) -> xml; changes the XML that core made of a
#                                            picture (spec = the pic dict) or a rect / ellipse / line (spec = the shape dict)
#   EXTRAS = {'pic': 'mod:fn', 'shape': 'mod:fn'}  reader: fn(reader, el, d); adds keys to the spec dict d that core.read made
def post_xml(kind, doc, spec, xml, *args):
    for n, p in packages():
        if kind in getattr(p, 'POST', {}):
            xml = _resolve(n, p.POST[kind])(doc, spec, xml, *args)
    return xml


def read_extras(kind, reader, el, d):
    for n, p in packages():
        if kind in getattr(p, 'EXTRAS', {}):
            _resolve(n, p.EXTRAS[kind])(reader, el, d)


def read_element(reader, el):
    """Run element -> block item of the first package whose reader accepts it, else None."""
    tag = el.tag.rsplit('}', 1)[-1]
    for name, pkg in packages():
        if tag in getattr(pkg, 'READS', {}):
            item = _resolve(name, pkg.READS[tag])(reader, el)
            if item is not None:
                return item
    return None
