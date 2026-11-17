# Presets: Markdown and HTML front ends

A preset is the design of one family of documents as data: `presets/<name>.json`. A front end reads a source text
and writes a spec (`docs/spec.md`) with the values of the preset. The builder does not know presets.
`hd` = `python <plugin>/lib/hd.py` (the SKILL.md gives the full path).

| source | command | preset |
|---|---|---|
| Markdown | `hd md in.md out.hwpx [--preset <name or file.json>] [--fallback] [--keep]` | default `report-gongmun` |
| HTML (any design) | `hd html in.html out.hwpx [--spec out.json]` | none: the CSS of the file (computed like a browser in print mode) |

Shipped preset: `report-gongmun` (개조식 보고서: title box, chapter bars, □ ○ - · items, grid tables; CSS values).
A 공문 is not a Markdown preset: write a spec from `templates/gongmun.json` (skill hwpx-gongmun).

## 1. Preset file

Keys (names as in `text/mdparse.py`):

| key | meaning |
|---|---|
| `name`, `about` | name and source of the design |
| `LAYOUT` | `css`: the values are CSS values of an HTML design; `css_layout()` gives the browser's spacing (rules.md W01-W11). `hangul`: the values are Hangul's own (a preset made from an HWPX) |
| `FONT` | short font key -> Hangul face name (`"batang": "함초롬바탕"`) |
| `BORDER` | CSS width -> Hangul line width (`"0.5pt": "0.12mm"`) |
| `PAGE` | `width_mm`, `height_mm`, `left_mm`, `right_mm`, `top_mm`, `bottom_mm` |
| `TEXT` | style name -> `font size bold color align left indent before after line` (pt, %; `word_break` optional). With LAYOUT `css`, `left`/`indent` are CSS padding-left/text-indent |
| `BOX` | box name -> `sides` (top, right, bottom, left: `[width, colour]` or null), `fill`, `pad` (pt: top, right, bottom, left) |
| `THIN`, `THICK`, `CELL_PAD`, `HEAD_FILL`, `BLANK_ROW_PT`, `BAR_WIDTH_PT`, `LIST_MARK` | table lines, cell margins, header fill, empty-row height, chapter bar width, list marks by level |
| `MAP` | Markdown element -> style name for the elements of section 2 (null = UNMAPPED) |

`text/markdown.py` needs these TEXT roles: docno title subtitle date summary chapter attach item sub l0 l1 l2 note
para th td code end gap, and these BOX roles: title summary bar chapter attach code. `--preset` checks this and
stops with "PRESET ... IS NOT COMPLETE" and the missing roles.

## 2. UNMAPPED and --fallback

The Markdown parser (`text/mdparse.py`) has no block for these elements:

| element (MAP key) | example | --fallback (first one that applies) |
|---|---|---|
| `h5`, `h6` | `##### text` | preset style `sub` |
| `blockquote` (after the first body block) | `> text` | preset style `note` |
| `list3` (list level 4 or deeper) | 6 or more spaces + `- ` | preset style `l2` |
| `star_list` | `* item`, `+ item` | preset list style `l0` |
| `image` | `![alt](a.png)` | core picture (96 dpi, at most the text width) |
| `footnote` | `text[^1]` + `[^1]: note` | core footnote |
| `link` | `[text](url)` | core hyperlink |
| `italic` | `*text*`, `_text_` | core italic run |
| `hr` | `***`, `___` | left out (like `---`) |
| `html` | `<br>`, `<span>` | text without the tags |

- Default mode: the front end prints `UNMAPPED line <n>: <element>: <text>` for each one, then
  `STOP: preset "<name>" has no style for these ...`, and exits with code 2. It writes no file.
- `--fallback`: it uses the nearest preset style, else a core feature, else plain text, and prints
  `FALLBACK line <n>: <element> -> <style|core|plain> <value>` for each one.
- A preset can map an element: `"MAP": {"blockquote": "note"}`. A mapped element is not UNMAPPED and has no log line.
- HTML (`hd html`): CSS gives every style, so nothing is UNMAPPED. A property, selector or element that it does not
  use prints `UNSUPPORTED <what> (<count>)`.

## 3. Extend a preset

1. Copy `presets/report-gongmun.json` from the plugin to your own folder (the plugin folder is replaced when the
   plugin updates). Set `name` and `about`. Use it with `--preset <path>.json`.
2. To give an UNMAPPED element its own look: add a style to `TEXT` (copy the nearest one, change the values), then
   set `MAP[<element>]` to the style name. Example: `"quote": {..., "left": 20, "color": "#555555"}` and
   `"MAP": {"blockquote": "quote"}`.
3. To change a look: change the values in `TEXT` or `BOX`. Units: pt for text, mm for the page.
4. Run `hd md --selftest`, then convert a sample with `--preset <path>.json`, render it
   (`hd render hwpx out.hwpx out/`) and compare it with the target.

## 4. New preset from an HWPX or an image

1. Get a sample: a Hangul HWPX of the design, or a spec made from an image (skill hwpx-from-image).
2. `hd preset-from <sample.hwpx | spec.json> <new>.json --name <new>`. The draft lists each distinct text style as
   s1..sN with `_count` and `_example`, and `_tables` (cell fills, lines, margins). LAYOUT is `hangul`.
3. Rename each `sN` to its role (section 1) from its example text: the biggest centred bold style = `title`, item
   lines (1., 가.) = list levels, body = `para`, table text = `td`. A role that the sample does not show: copy the
   nearest style and record "assumed" in `about`.
4. Set `BOX`, `CELL_PAD`, `HEAD_FILL` from `_tables`. Set `MAP`. Delete every key and field that starts with `_`.
5. Check: convert the sample text as Markdown with `--preset <new>.json`, render it, compare it with the sample
   (`hd img diff a.png b.png`, overlay in skill hwpx-from-image). Correct the values until no offset is larger than
   0.5 mm.

## 5. Self-test

`hd md --selftest [out_dir]` (default: a new temp folder) checks, with a Markdown that has h4, a body blockquote, a
picture, a 4-level list, a code block and a footnote:

- default mode: UNMAPPED = blockquote, picture, list level 4, footnote (reference and definition); h4 and the code
  block are mapped;
- `--fallback`: 5 FALLBACK lines; picture block 25.4 mm wide (96 px); footnote run; blockquote in style `note`;
  list level 4 in style `l2`; no placeholder left;
- a preset with `MAP.blockquote` set: the blockquote is not UNMAPPED;
- it writes `selftest.hwpx` (its path is printed). Render it with `hd render hwpx <that path> <out_dir>`: expected
  `OPEN OK ... pages 1`.
