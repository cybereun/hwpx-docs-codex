# Interfaces of the package `lib/hwpx_docs` (core contract)

The spec (`spec.md`) is the only contract between front ends and the builder. Front ends write a spec; the builder
writes an HWPX; checks read an HWPX or a spec. A module calls only the functions in this table. Change a signature
here first, then in the code. Command line: `python lib/hd.py <command>` (`hd`), one command per module.

## core (build and read)

| module | function | input -> output |
|---|---|---|
| `core/build.py` | `write(spec, path, base='.')` | spec dict -> HWPX file; `base` = folder of relative picture paths |
| | `Doc` | composes `Header` + the mixins `text.TextMixin`, `table.TableMixin`, `objects.ObjectsMixin`, `page.PageMixin`; `Doc.klass(d)` applies spec `styles` to an item with `class` |
| | `hd build spec.json out.hwpx`, `hd build selftest` | |
| `core/read.py` | `read(path, out_json)` | HWPX -> spec dict (pictures saved next to `out_json`; unknown elements as raw `{"xml": ...}`) |
| | `DEF_CHAR`, `DEF_PARA`, `CHAR_KEYS` | Hangul default char/para props (keys absent from a spec have these values) |
| `core/units.py` | `hu`, `quad`, `color`, `line`, `image_size`, `PAPER`, `CHAR_KEYS`, `PARA_KEYS` | units, lines, colours, constants |
| `core/header.py` | `Header` | header.xml registries (fonts, char/para shapes, border fills, tabs, numbering) |
| `core/textfit.py` | `wrap(block, width_mm)`, `count_lines(block, width_mm)`, `chars(block)`, `widths(block, width_mm)` | real font widths (Windows GDI) and line layout |
| `core/layout.py` | `Layout(spec)`: `.paras`, `.cells`, `.tables`, `.lost`; `Para` | where each paragraph goes: box width, wrapped lines, cells, space Hangul drops |
| `core/registry.py` | `packages()`, `commands()`, `tests()`, `block_handlers(key)`, `read_element(reader, el)`, `draw_handlers(key)` | finds the `COMMANDS`, `selftest()`, `BLOCKS`, `READS` and `DRAWS` that feature packages register |

## Feature packages (self-registering)

A feature package `lib/hwpx_docs/<name>/` holds one feature. Its `__init__.py` gives its public interface (docstring),
its `hd` commands (`COMMANDS`) and its `selftest()`; core finds them (`core/registry.py`). It depends on core only,
never on another feature package. A new or changed feature edits only its own package (no change in `lib/hd.py`,
`selftest.py` or this file). `hd help` lists the registered commands.

| package | public interface |
|---|---|
| `edit/` | `edit.Doc(path)` (`slots`, `fill`, `set`, `replace`, `check`, `save`), `guard.report(original, edited, ...)`; `hd slots`, `hd edit`, `hd guard` |
| `convert/` | `convert.convert(pairs)`, `convert.plan(args)`, `convert.hangul_available()`; `hd convert` | HWP <-> HWPX, HWP/HWPX -> PDF by Hangul Open + SaveAs, one Hangul per batch; exit 3 = no Hangul. Uses only `render.hwpcom.run_jobs` (Hangul session) |
| `extract/` | `extract.extract(path, md=False)`; `hd text` |
| `hwp5/` | binary .hwp (HWP 5.0), no Hangul: `edit.Doc(path)` (`slots`, `labels`, `fill`, `set`, `replace`, `check`, `text`, `save`), `guard.report(original, edited, ..., render_dir=None)`, `tospec.read(path, out_json)`, `render.pages(path, out_dir, backend)`, `render.compare(before, after, out_dir, backend)`, `fmt.Package`, `cfb.read/patch/build`; `hd hwp <sub>` (exit 5 = UNSUPPORTED: `tohwpx`, `fromhwpx`, `build`; 3 = Hwp5Error). Pages through `registry.backend('specpages', 'preview')` (the spec straight to the preview, with Hangul's line starts `hangul_lines`, preview rules P19) and `render.hwpcom` (Hangul). Own rules HW01-HW28, coverage C15 in its folder. |
| `chart/` | `ooxml.chart_xml(spec)`, `ooxml.parse(xml, strict=True)`, `draw.svg(spec, x, y)`; spec block `chart` with `native: true` (reader adds `view` next to a whole `ooxml` part); `hd chart make|dump`. Own rules (CH01-CH11), spec keys, coverage rows, fixtures in its folder. |
| `pagefit/` | `model.load(path)`, `model.pages(spec, pic_dir)` (pages with items, fill, free mm), `check.check(spec, pic_dir, fill=85, last_lines=3)` -> (findings, pages), `fix.fix(spec, pic_dir, fill, break_fill, max_extra, max_shrink, last_lines)` -> log (the spec changes in place); `hd pagefit check|fix`. Block heights come from the preview through the registered backend `blocks` / `preview` (`preview/blocks.py section_atoms(spec, pic_dir)`); a section with columns, footnotes or floating objects comes from the preview's own flow through the backend `pagereport` / `preview` (`preview/report.py page_report(spec, pic_dir)`: pages with items, used and capacity; `flow.lay_out(spec, pic_dir, trace)` records what the flow placed); it sets only `keep_next`, `widow`, `page_break_before`, `page_break`, `after`. Own rules PF01-PF12 in its folder. |
| `fields/` | run items `{"form": {...}}` (check, radio, combo, edit, list, button, scroll), `{"xref": ...}`, `{"index_mark": ...}`, `{"change": ...}` (track changes); blocks `{"toc": ...}`, `{"index": ...}` (static 차례/색인 with `pages: "auto"`); `forms.parse/xml/fill_file/listing`; `hd form list|fill`. Own rules (F, X), coverage rows, fixtures in its folder. |
| `pagex/` | section keys `header_odd/even`, `footer_odd/even`, `master_pages`, `text_direction`, `vertical_head`, `line_numbers`, `manuscript`, `char_grid`, `line_grid`, `hide_first`, `note_shape` (hook `SECTION` build/read: `registry.section_hooks`); body blocks `hide_page`, `columns_here`; `hd pagex list|run` (Hangul pair samples). Own rules (PX01-PX13), spec, coverage, fixtures in its folder; the preview draws it in `preview/drawers/page_layout.py`. |

A package that adds a spec block or reads an OWPML element also sets `BLOCKS = {'spec-key': 'module:function'}` /
`READS = {'xml-tag': 'module:function'}` in its `__init__.py` (builder and reader call them through
`registry.block_handlers(key)` and `registry.read_element(reader, el)`); `BLOCKS['doc.header']` = fn(doc, header text) -> header text (a package adds to header.xml); extra zip parts go in `doc.parts`.
`DRAWS = {'spec-key': 'module:function'}`: how the preview draws the item, `fn(item, x, y) -> [SVG elements] | None`
(the item has `w`, `h` in mm; see "Preview drawers").

## Preview drawers (`lib/hwpx_docs/preview/drawers/`)

A new kind of object is drawn by adding one module to `preview/drawers/` (or `DRAWS` in its own package); nobody edits
`preview/layout.py`. Every module in the folder is imported once, by name, at the first lookup, and registers:

| call | for | drawer |
|---|---|---|
| `register(key, fn)` | a spec item `{key: {...}}`, as a block or as a run item | `fn(item, style)` |
| `register_inline(tag, fn)` | a raw element the reader kept as `{"xml": "<tag ...>"}` | `fn(xml, style)` |

`style` = the char style at that place (keys of `core.read.CHAR_KEYS`; `size` in pt). The drawer returns
`{"w": mm, "h": mm, "base": mm or None, "draw": draw}` or None; `draw(x, y)` returns SVG elements (lengths in mm, the
object's top-left corner at x, y) or None. `base` = top of the object to the text baseline (None: the bottom sits on
the baseline). An item with `"inline": false` and `"pos": {x, y, rel}` floats like a picture. None, or an object of a
type that no drawer knows (a dict with `w` and `h`, or a raw element with `hp:sz`), gives a dashed red box with the
type name and one line `PREVIEW NOT DRAWN <type> <w> x <h> mm on page <n>`: the preview never leaves a silent blank.

```python
# lib/hwpx_docs/preview/drawers/stamp.py: a {"stamp": {"w": 20, "h": 20, "text": "인"}} item as a red circle
from ..svg import f3
from . import register


def stamp(item, style):
    w, h = item['w'], item['h']

    def draw(x, y):
        return ['<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#C00000" stroke-width="0.5"/>'
                % (f3(x + w / 2), f3(y + h / 2), f3(min(w, h) / 2))]
    return {'w': w, 'h': h, 'base': None, 'draw': draw}


register('stamp', stamp)
```

Floating objects (a paragraph's `shapes`, a floating picture, a table with `pos`, an item with `"inline": false`) are
placed by the flow (rules P16): `rel` is the vertical reference (`paper`, `page` = the body area, `para` = the anchor
paragraph's top) and the horizontal one unless `hrel` gives it (`paper`, `page`, `column`, `para` = between the
paragraph's indents); `x`, `y` are offsets in mm and `halign` (`left`, `center`, `right`) places the object in its
horizontal reference first, `vpos` (`top`, `center`, `bottom`) in a `page` or `paper` reference (`valign` of a text box
is the text inside the box; a picture's `valign` is passed on as `vpos`). `wrap` `square` lets the text go on beside the object (`side`: `both_sides` (default),
`left_only`, `right_only`, `largest_only`), `top_and_bottom` moves it below; `behind_text` and `in_front_of_text` do
not move text. `layout.shape_at(shape, page, x, y, width, para_style)` gives the place on the page.

Four more hooks for features that are not objects (a module in `preview/drawers/` registers them the same way):

| call | called | fn gets | fn returns |
|---|---|---|---|
| `register_prepare(fn)` | once per document, after the reader and before the layout | `spec, pic_dir` (the folder of the pictures the reader saved) | nothing: it changes the spec in place (for example a paragraph key becomes a run item that a drawer draws: `drawers/bullet_image.py`) |
| `register_paint(kind, fn)` | for a fill that is a dict `{"type": kind, ...}` of a table cell, shape, paragraph box or page border | `ctx, page, fill, w, h` (box size in mm) | an SVG paint string (`#RRGGBB`, `url(#id)`); it may append `<defs>` to `page.svg` |
| `register_table_wrap(fn)` | for every table block, before the plain table layout | `ctx, block, style, width mm, layout_table, layout_para` | a list of atoms (`layout.A(h, emit)`: height in mm, `emit(x, y, page)`), or None = plain table |
| `register_page_layer(fn, z)` | once per page, after all pages are laid out; `z='under'` goes below the header and body (above the page border fill), `z='over'` on top | `ctx, page, info` | SVG elements (mm, page coordinates) |

`drawers.paint(ctx, page, fill, w, h)` is what the layout calls: a string fill comes back unchanged; a dict nobody paints
gives its `color` (or first of `colors`) and one line `PREVIEW NOT DRAWN fill <type>`. A table wrapper calls
`layout_table(ctx, table, style, width)` -> `(table width, atoms)` and `layout_para(ctx, block, style, width)` -> atoms
to build its own atoms (for example a caption paragraph and the table). Page `info`: `no` (printed page number), `index`
(page in the document, from 1), `section` (from 0), `first` (first page of its section), `is_last` (last page of its
section), `is_last_doc` (last page of the document), `odd` (by `no`), `size` (w, h mm), `margin` {left, right, top,
bottom, header, footer, gutter}, `body` (x0, y0, x1, y1 mm), `columns` {count, gap, width}, `spec` (the whole section
dict as the reader gives it, with every key it has: page, header, footer, page_border, and the keys feature packages
add). The page also has `page.lines` = `[baseline y mm, x mm, column index]` of every body text line placed on it (lines
inside tables, boxes and bordered paragraphs are not listed) and `page.marks` = the marks that drawers left: a drawer's
result may have `"marks": {"name", ...}` (for example a raw `hp:pageHiding` registered with `register_inline` returns
`{"w": 0, "h": 0, "draw": None, "marks": {"hide_header"}}`), and a layer reads `page.marks`. A layer that needs to lay
out blocks (a 바탕쪽, a header variant) calls the public `layout.layout_blocks(ctx, blocks, style, width_mm)` -> atoms
(`a.h` mm, `a.emit(x, y, page)`); `style` = `dict(core.read.DEF_CHAR)` or the char style it has.

```python
from ..layout import A
from . import register_paint, register_table_wrap, register_page_layer


def gradient(ctx, page, fill, w, h):           # {"type": "gradient", "colors": ["#FFFFFF", "#4472C4"]}
    gid = 'g%d' % len(page.svg)
    page.svg.append('<defs><linearGradient id="%s"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
                    '</linearGradient></defs>' % (gid, fill['colors'][0], fill['colors'][-1]))
    return 'url(#%s)' % gid


def caption(ctx, b, style, w, layout_table, layout_para):
    if 'caption' not in b['table']:
        return None                            # not mine: the plain table
    return layout_para(ctx, {'p': b['table']['caption']}, style, w) + layout_table(ctx, b['table'], style, w)[1]


def line_numbers(ctx, page, info):           # a number left of the body on every 10 mm
    x0, y0, x1, y1 = info['body']
    return ['<text x="%s" y="%s" font-size="2.5" text-anchor="end">%d</text>' % (x0 - 3, y, n)
            for n, y in enumerate(range(int(y0) + 10, int(y1), 10), 1)]


register_paint('gradient', gradient)
register_table_wrap(caption)
register_page_layer(line_numbers, 'over')
```

## feature writers (mixins of `core.build.Doc`)

| module | methods | XML |
|---|---|---|
| `text/text.py` | `run_xml`, `footnote` | runs: text, links, fields, notes, equations, bookmarks |
| `table/table.py` | `table` | `hp:tbl`, cells, merges, per-cell border fills |
| `objects/objects.py` | `shape`, `pic`; `chart_shapes(chart)` | `hp:rect`, `hp:ellipse`, `hp:line`, text boxes, `hp:pic`, charts as shapes |
| `page/page.py` | `section_xml` | `hp:secPr`: page, margins, columns, header/footer, page number, page border |

## front ends (text)

| module | function | input -> output |
|---|---|---|
| `text/markdown.py` | `load_preset(name_or_path)`, `check_preset()`, `scan(md)`, `spec(md, fallback, base_dir, log)`, `spec_from(meta, blocks, notes, base_dir)`, `css_layout(spec, text_width_mm)` | Markdown -> spec (presets, UNMAPPED, --fallback); CSS spacing -> Hangul spacing |
| `text/mdparse.py` | `parse(md)`, `segments(text)` | Markdown -> (meta, blocks) |
| `text/html_css.py` | `convert(html)` | any HTML -> (spec, Counter of UNSUPPORTED items) |
| `text/preset_from.py` | `draft(spec, name)` | spec of a sample -> draft preset dict |

## check and render

| module | function | input -> output |
|---|---|---|
| `check/readability.py` | `check(spec)`, `fix(findings)`, `report(findings)`, `report_only(spec)` | RD01-RD12 findings; safe fixes in place |
| `check/check_xml.py` | `Index(spec)`, `query(ix, q)`; `hd check file.hwpx checklist.md` | checklist rows -> OK / FAIL |
| `check/measure.py` | `hd measure image.png --page-mm 210` | lines, grid, ink box, text bands in mm |
| `check/hwpx_diff.py` | `diff(a, b)`; `hd diff dump|diff|sdiff` | XML difference of two HWPX files |
| `check/roundtrip.py` | `hd roundtrip out_dir a.hwpx ...` | HWPX -> spec -> HWPX -> render -> ink difference (Windows + Hangul) |
| `render/render.py` | `hwpx_pages(paths, out_dir, dpi=96, stems=None)` | HWPX files -> {path: [png] or None}; one Hangul per batch |
| | `html_pages(html, out_dir, dpi=96)`, `pdf_pages`, `to_png` | Edge print / PDF / image -> PNG (Windows) |
| `render/img.py` | `load`, `save_png`, `side_by_side`, `grid`, `overlay`, `compare`, `ink` | image = (w, h, rows of RGB bytes) |
| `render/hwpcom.py` | `Hwp()`, `run_jobs(items, job, timeout=90, retries=2)` | hidden Hangul session; never answers the file-access prompt |
| `selftest.py` | `hd selftest [--only m1,m2] [--fixtures DIR]` | `SELFTEST <module> PASS`, fixtures read -> build -> read |

## Rules for every module

- Python 3.10+ standard library only (ctypes and winreg on Windows); Hangul COM (pywin32) only in `render/hwpcom.py`.
- Each module with logic has a self-check run by `hd selftest` with no Hangul.
- One feature = one package with a small public interface; it uses core and the public interface of nothing else.
  Shared formats (spec schema, styles and classes, units, text widths, layout, XML writer) live once in core.
- The older modules are still listed in `lib/hd.py` COMMANDS and `selftest.py` TESTS; move each into its package
  when it changes next.
- Never write into the plugin folder (it is a read-only cache): outputs go to the user's folder or a temp folder.
- Print machine-readable result lines: `OPEN OK`, `HWPX WRITTEN`, `UNMAPPED`, `FALLBACK`, `UNSUPPORTED`, `RDnn`,
  `... PASS`.
