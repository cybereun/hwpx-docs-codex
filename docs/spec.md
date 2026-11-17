# Spec format (input of `core/build.py`)

A spec is JSON. `hd read any.hwpx out.json` shows the spec of any Hangul file: use it to learn
the format, or to start from an existing document. Units: page, table, shape and picture lengths in **mm**; text
lengths (size, indent, spacing) in **pt**. A string with a unit also works: `"12pt"`, `"3.5mm"`, `"1cm"`, `"96px"`, `"500hu"`.
Colours: `"#RRGGBB"` (or `"#RGB"`), `"none"`. Lines: `"<width> <type> <colour>"`, for example `"0.4mm solid #000000"`,
`"0.12mm dash"`, `"0.5mm double"`, `"none"`. Types: solid, dash, dot, dash_dot, dash_dot_dot, long_dash, circle,
double (= double_slim), slim_thick, thick_slim, slim_thick_slim, none. Widths snap to Hangul's list (rules.md H16).

## Document

```json
{
  "title": "문서 제목",
  "defaults": {"font": "함초롬바탕", "size": 10, "align": "justify", "line": 160},
  "page": {"size": "A4", "landscape": false,
           "margin": {"left": 20, "right": 20, "top": 20, "bottom": 15, "header": 15, "footer": 15, "gutter": 0}},
  "columns": {"count": 2, "gap": 8, "line": "0.12mm solid", "type": "newspaper|balanced|parallel"},
  "page_border": {"border": "0.4mm solid", "fill": "#FFFFFF", "offset": 5, "text_border": "paper|content"},
  "header": [blocks] | {"blocks": [...], "apply": "both|even|odd", "style": {char/para props}},
  "footer": same as header,
  "page_number": {"pos": "bottom_center", "format": "digit", "side": "-"},
  "numberings": [{"levels": [{"text": "^1.", "format": "DIGIT"}, ...]}],
  "body": [blocks]
}
```
Named styles (like CSS classes): `"styles": {"item1": {"left": 0, "indent": -15.2, "after": 4}, "red": {"color":
"#C00000"}}`; a block, a table cell or a run takes them with `"class": "item1"` or `"class": "item1 red"` (left to
right; the item's own props win; an unknown name stops the build). They are spec shorthand: the HWPX gets the
props, not a Hangul style entry (coverage C3.03).

Several sections (for example portrait then landscape): `{"sections": [{"page": ..., "body": [...]}, ...]}`; each
section can have its own page, columns, header, footer, page_number. `size` is `A4` (Hangul's 59528 x 84186 hu), A3,
A5, B4, B5, LETTER, LEGAL or `[width, height]` in mm. The body starts at top + header (rules.md S05).

## Blocks (items of `body`, cell `blocks`, header/footer, note text, text box text)

| block | meaning |
|---|---|
| `"text"` | one paragraph with the inherited style |
| `{"p": "text", ...props}` | paragraph; `\n` makes more paragraphs with the same props; `\t` is a tab |
| `{"p": [runs], ...props}` | paragraph made of runs (below) |
| `{"table": {...}, ...props}` | table in its own paragraph (props of that paragraph: align, before, after, char style of the cells) |
| `{"pic": {"src": "a.png", "w": 40, "h": 30, "inline": true}}` | picture (path relative to the spec file) |
| `{"shapes": [shape, ...], "p": "optional text"}` | floating drawing objects anchored to this paragraph |
| `{"gap": 6}` | empty paragraph exactly 6 pt high |
| `{"chart": {...}}` | bar or line chart drawn with drawing objects (below) |
| `{"page_break": true}` | next paragraph starts a new page (or `"page_break": true` on a paragraph); `"column_break": true` |

## Runs (items of a `p` list)

| run | meaning |
|---|---|
| `"text"` or `{"t": "text", ...char props}` | text (char props override the paragraph's) |
| `{"t": "text", "highlight": "#FFFF00"}` | 형광펜 |
| `{"link": "http://...", "t": "shown text"}` | hyperlink |
| `{"footnote": "text" or [blocks]}`, `{"endnote": ...}` | note (text style = run style + `footnote_style`, default size 9) |
| `{"page_num": true}` | current page number (in a header or footer) |
| `{"new_page_num": 1}` | 새 번호로 시작 |
| `{"field": "name", "t": "guide", "memo": "help"}` | 누름틀 |
| `{"bookmark": "name"}` | bookmark |
| `{"equation": "a over b"}` | equation (Hangul equation script) |
| `{"table": {...}}` / `{"pic": {...}}` | inline table / picture (moves like a character) |
| `{"tab": true}` | tab |
| `{"xml": "<hp:...>"}` | raw OWPML run content, written as given |

## Char props (paragraph, run, cell, table defaults; children inherit)

`font` (all 7 languages) and `font_latin`, `font_hanja`, `font_japanese`, `font_other`, `font_symbol`, `font_user`;
`size` (pt); `bold`, `italic`; `color`; `shade` (background of the characters); `spacing` (자간 %), `ratio` (장평 %),
`rel_size` (%), `offset` (%) — one number or 7 numbers; `underline` (true, a colour, or `{"pos": "bottom|top|center",
"shape": "solid|dash|...", "color"}`); `strike` (true or `{"shape", "color"}`); `outline`; `shadow` (`{"type":
"drop|continuous", "color", "x", "y"}`); `emboss`; `engrave`; `sup`; `sub`; `emphasis` (`"dot_above"` ...); `kerning`;
`font_space`; `char_border` (line spec), `char_fill` (colour).
Characters ○ □ ☐ ※ · ◇ are SYMBOL characters: `font` sets them too; `font_symbol` changes only them.

## Para props (paragraph, cell, table/cell defaults; children inherit the text style keys)

`align` (justify, left, right, center, distribute, divide); `left`, `right`, `indent` (pt; negative indent = hanging:
the first line starts at `left`, the wrapped lines at `left + |indent|`; for "○ text" with the mark at 14 pt and the
wrapped lines at 36 pt: `"left": 14, "indent": -22`); `before`, `after` (pt); `line` (percent number, or
`{"fixed": pt}`, `{"at_least": pt}`, `{"between": pt}`); `keep_next`, `keep_lines`, `page_break_before`, `widow`;
`word_break` (`char` = 글자, Hangul's default; `word` = 어절: use it when the target wraps only between words),
`latin_break` (word, hyphen, char); `line_valign` (baseline, top, center, bottom); `condense` (공백 최소값 %: spaces
may shrink, so more words fit on a justified line); `snap`; `autospace`; `border` (line spec for all sides or `{"top": ..., "bottom": ...}`),
`fill`, `border_offset` (mm, 1 or 4 values), `border_connect`; `bullet` (character, Hangul bullet); `number` (level,
or `{"list": i, "level": n}` = Hangul automatic number from `numberings`); `outline_level` (개요 0-9); `tabs`
(`[{"pos": mm, "type": "left|right|center|decimal", "leader": "none|dot|..."}]`).

## Table

```json
{"table": {
  "cols": [28, 57, 28, 57],                  // column widths, mm (outer cell sizes; sum = table width)
  "heights": [10, 10, 90],                   // row heights, mm (optional; Hangul grows a row to fit its text)
  "border": "0.12mm solid #000000",          // all grid lines
  "outline": "0.4mm solid",                  // outer edge (optional)
  "hlines": {"1": "0.5mm double"},           // whole horizontal line above row 1 (optional)
  "vlines": {"2": "none"},                   // whole vertical line left of column 2 (optional)
  "cell": {"valign": "center", "align": "left", "size": 10},   // defaults for every cell
  "pad": [1.8, 1.8, 0.5, 0.5],               // cell margins l r t b, mm (Hangul default)
  "margin": [1, 1, 1, 1],                    // outer margin, mm (Hangul default 1 mm: the table starts 1 mm right of the text area)
  "inline": false, "align": "left|center|right", "pos": {"x": 20, "y": 50, "rel": "paper"},
  "page_break": "cell|table|none", "repeat_header": true, "header_rows": 1,
  "rows": [
    [{"p": "회의명", "fill": "#E7E6E6", "bold": true, "align": "center"}, {"p": "값", "cs": 3}],
    ["a", "b", {"p": "c", "rs": 2, "valign": "top"}, "d"],
    {"style": {"size": 9}, "cells": ["e", "f", "g"]}
  ]
}}
```
Rows list cells like HTML: a cell takes the next free grid position; `cs`/`rs` span columns/rows and the covered
positions are skipped. A cell is a string or a dict with `p` (text, `\n` = more paragraphs) or `blocks`, `cs`, `rs`,
`fill`, `border` (line spec or `{"top", "bottom", "left", "right"}`; it sets the grid lines around the cell, a later
cell wins on a shared line), `valign` (top, center, bottom), `pad`, `diag` (slash, back, both) + `diag_line`, and any
char/para props. Cells inherit the char style of the table block, not its paragraph spacing.

More table keys (package `table`, rules TB01-TB09 in `lib/hwpx_docs/table/rules.md`; drafts until Hangul shows them):
- cell `fill`: a colour, `{"type": "gradient", "kind": "linear|radial|conical|square", "angle": 90, "center": [x%, y%],
  "step": 50, "step_center": 50, "colors": ["#FFFFFF", "#3366CC"]}` or `{"type": "image", "src": "a.png", "mode": "tile|total|center|zoom|..."}`.
  Hangul draws a gradient with 3 colours black: give 2.
- cell `protect` (셀 보호), `editable`.
- cell `formula` (계산식): `"=SUM(A1:A3)"` or `{"expr": "=SUM(?1:?3)", "format": "%g,"}` (Hangul's block-sum form); the shown
  result goes in `p`. The builder does not calculate.
- line types (`border`, `outline`, `hlines`, ...): `solid dash dot dash_dot dash_dot_dot long_dash circle double slim_thick
  thick_slim slim_thick_slim wave doublewave thick3d thickrev3d 3d rev3d none` (Hangul draws `wave` and `doublewave` as zigzags and the four 3D types as nothing; the preview does the same).
- table `caption`: `{"text": "제목", "label": "표", "number": true, "side": "bottom|top|left|right", "gap": mm, "width": mm}`
  or a string (text after "표 <auto number>").
- table `pos` (floating): `{"x", "y" (mm), "rel": "paper|page|para"}` or `"vrel"` + `"hrel"` (`column` too); `"valign"`
  (top, center, bottom), `"halign"` (left, center, right), `"flow"` (follow the text), `"overlap"`, `"hold"`, `"affect"`;
  with `"wrap": "square|top_and_bottom|behind_text|in_front_of_text"`; `"side"`: `both_sides|left_only|right_only|largest_only` (text flow
  beside a square-wrapped table).

## Shape (items of `shapes`)

```json
{"type": "rect", "x": 20, "y": 50, "w": 80, "h": 30, "rel": "paper|page|para",
 "line": "0.4mm solid #000000", "fill": "#EAF1FB", "round": 20,
 "text": "글상자 글" or [blocks], "pad": 1, "valign": "center",
 "wrap": "in_front_of_text|behind_text|top_and_bottom|square"}
{"type": "ellipse", "x": 20, "y": 120, "w": 40, "h": 25, "line": "0.3mm solid #C00000"}
{"type": "line", "x": 70, "y": 125, "x2": 190, "y2": 125, "line": "0.25mm dash", "arrow": "end|start|both"}
```
`x`, `y` are from the paper (or page/paragraph) top-left corner, in mm. Use shapes for anything that is not text or a
table grid: free boxes, rules, circles, stamps, check marks.

## Chart (block `chart`)

```json
{"chart": {"type": "bar|line", "w": 165, "h": 64, "title": "연도별 선정 수", "unit": "개",
           "categories": ["2021년", "2022년"], "series": [{"name": "선정", "values": [23, 45], "color": "#4472C4"}],
           "max": 200, "ticks": 5, "labels": true, "font": "맑은 고딕", "size": 9},
 "size": 2, "line": {"fixed": 2}}
```
The builder draws the chart with drawing objects (grid, axes, bars or lines with markers, value labels, legend) anchored
to the block's paragraph; the text after it goes below. It is vector and editable in Hangul, but it is not a Hangul
chart object (coverage C6.10). Example: `examples/chart-report/report.json`.
With `"native": true` the block makes a real Hangul chart object (bar, hbar, line, pie, combo): keys in
`lib/hwpx_docs/chart/spec.md`.

## More keys of the feature packages (version 0.3.0)

One line per key: the value, then a short example. The full rules and the XML are in the package named in each heading
(`lib/hwpx_docs/<package>/spec.md` where it exists, and `rules.md`). `hd read` writes the same keys (round trip) unless a
line says otherwise. The self-test checks that every spec key of the builder column of `docs/coverage.md` (C1-C11) is in
this file.

### Text and styles (package `textstyle`, rules TS01-)

| key | value | example |
|---|---|---|
| `tabs` (paragraph) | list of `{"pos": mm, "type": "left\|right\|center\|decimal", "leader": line type}` or `{"stops": [...], "auto_left": bool, "auto_right": bool}`; `\t` in the text jumps | `{"p": "항목\t1,234.5", "tabs": [{"pos": 100, "type": "decimal", "leader": "dot"}]}` |
| `named_styles` (document) | `{name: {para and char props, "type": "para\|char", "eng": English name, "next": name}}`: entries of Hangul's style list | `"named_styles": {"본문 가": {"size": 11, "line": 170, "next": "본문 가"}}` |
| `style` (block, cell block, run) | a name of `named_styles` or a built-in style (`바탕글`, `개요 1` ...) | `{"style": "본문 가", "p": "글"}` |
| `next`, `type` (inside a named style) | the style after Enter; `char` for a character style | `"강조": {"type": "char", "bold": true}` |
| `dropcap` (block) | `{"lines": 2\|3\|"margin", "font", "color", "frame": line, "fill", "gap"}`; the first character of `p` | `{"dropcap": {"lines": 2}, "p": "문단 첫 글자 장식"}` |
| `dutmal` (run item) | `{"main", "sub", "pos": "top\|bottom", "size": %, "align"}` (덧말; also the 한자 병기 form) | `{"dutmal": {"main": "本末", "sub": "본말"}}` |
| `bullet_image` (paragraph) | picture file next to the spec; `bullet` stays the fallback character | `{"bullet_image": "dot.png", "p": "항목"}` |
| `latin_break`, `word_break` (paragraph) | `word\|hyphen\|char`; `char\|word` | `{"latin_break": "hyphen"}` |

### Page (package `pagex`, rules PX01-)

Section keys (top of the spec = section 0, or in a `sections` item):

| key | value | example |
|---|---|---|
| `header_odd`, `header_even`, `footer_odd`, `footer_even` | blocks, or `{"blocks": [...], "style": {...}}` | `"header_odd": ["홀수 쪽 머리말"]` |
| `master_pages` | list of `{"type": "both\|even\|odd\|last\|optional", "body": [blocks], "page": n, "duplicate": bool, "front": bool}` (바탕쪽) | `"master_pages": [{"type": "both", "body": [{"p": "대외비"}]}]` |
| `text_direction`, `vertical_head` | `"vertical"`, `"vertical_all"`, `"horizontal"`; `vertical_head: 1` = the header stays horizontal | `"text_direction": "vertical"` |
| `line_numbers` | `{"count_by": 1, "distance": mm, "start": 1, "restart": 0\|1\|2}` | `"line_numbers": {"count_by": 5}` |
| `manuscript`, `char_grid`, `line_grid` | `1` = 원고지; grid cell sizes in mm | `"manuscript": 1` |
| `hide_first` | `{"header", "footer", "master_page", "page_number", "empty_line": bool, "border", "fill": "hide_first"}` | `"hide_first": {"page_number": true}` |
| `note_shape` | `{"footnote": {...}, "endnote": {...}}` with `format`, `prefix`, `suffix`, `user_char`, `superscript`, `line`, `line_length`, `between`, `below`, `above`, `numbering` (continuous, on_section, on_page), `start`, `place`, `beneath_text` | `"note_shape": {"footnote": {"format": "circled_digit", "numbering": "on_page"}}` |

Body blocks: `hide_page` (list of `header, footer, master_page, border, fill, page_number`, or `true`; with `p`) hides them on
the page of that paragraph: `{"hide_page": ["page_number"], "p": "글"}`. `columns_here` (`{"count", "gap", "line", "type"}`, with
`p`) changes the columns inside a page: `{"columns_here": {"count": 2, "gap": 8}, "p": "여기부터 두 단"}`. The reader keeps these
two as raw `{"xml": ...}` run items. A label sheet is a table block with `page.margin` (no key of its own).

### Tables (package `table`, rules TB01-)

`caption`, `formula`, `protect`, `editable`, gradient and picture `fill`, floating `pos` with `side`, and the line types: see
"More table keys" above. A table in the text flow (no `pos`) also takes `hold`: true = 개체와 조판 부호를 항상 같은 쪽에 놓기
(`holdAnchorAndSO`): a table kept whole goes to the next page together with its paragraph, so the text after it cannot move up
before it (`{"table": {..., "page_break": "none", "hold": true}}`; rules TB05, pagefit PF26).

### Objects (package `objects2`, rules OB01-)

| key | value | example |
|---|---|---|
| `bright`, `contrast` (pic) | -100 ... 100 | `{"pic": {"src": "a.png", "w": 30, "h": 20, "bright": 40}}` |
| `effect` (pic) | `real`, `gray`, `bw` | `"effect": "gray"` |
| `crop` (pic) | [left, top, right, bottom] in % of the picture | `"crop": [0, 0, 50, 0]` |
| `border` (pic) | line string | `"border": "0.35mm dot #FF0000"` |
| `caption` (pic, shape, object, ole) | string, or `{"text", "label", "number", "side", "gap", "width"}` | `"caption": "그림 설명"` |
| `pos` extras (pic, shape, object, table) | `hrel` (paper, page, column, para), `halign` (left, center, right, inside, outside), `vpos` for a shape (top, center, bottom, inside, outside; `valign` is the text inside a text box), `flow`, `overlap` | `{"type": "rect", "hrel": "column", "halign": "right", ...}` |
| `side` | `both_sides`, `left_only`, `right_only`, `largest_only`: where text goes beside a square-wrapped object | `"side": "left_only"` |
| `same_para` (block) | true: the floating table or picture is a run of the next paragraph (reader rule S26) | `{"pic": {...}, "same_para": true}` |
| `object` (block) | `{"kind": "polygon\|curve\|connector\|textart\|group", "w", "h", "inline", "pos", "wrap", "side", "line", "fill", "caption", ...}` | `{"object": {"kind": "polygon", "w": 40, "h": 30, "points": [[0, 30], [20, 0], [40, 30]]}}` |
| `polygon` | `points` [[x, y], ...], `closed` | as above |
| `curve` | `segs` [[`line`\|`curve`, x1, y1, x2, y2], ...] (펜으로 그린 선) | `{"object": {"kind": "curve", "w": 40, "h": 20, "segs": [["line", 0, 0, 40, 20]]}}` |
| `connector` | `type` straight\|elbow\|arc, `arrow` none\|end\|both, `from`, `to`, `from_ref` / `to_ref` | `{"object": {"kind": "connector", "w": 40, "h": 20, "type": "elbow"}}` |
| `textart` | `text`, `shape` (one of 36 Hangul 글맵시 shapes, e.g. WAVE1), `font`, `align`, `char_space`, `line_space`, `shadow` | `{"object": {"kind": "textart", "w": 60, "h": 15, "text": "글맵시", "shape": "WAVE1"}}` |
| `group` | `items`: children with `x`, `y` inside the group | `{"object": {"kind": "group", "w": 60, "h": 30, "items": [...]}}` |
| `ole` (block) | `{"src": file to embed, "w", "h", "inline", "pos", "wrap", "side", "caption"}` | `{"ole": {"src": "data.xlsx"}}` |
| `proof` (run item) | `{"proof": "lineattach\|attach\|delete\|clipping", "text": "marked text"}` (교정 부호) | `{"proof": "delete", "text": "지울 말"}` |

### Equations and charts (packages `preview/equation`, `chart`)

| key | value | example |
|---|---|---|
| `equation` (run item) | Hangul equation script | `{"equation": "x = {-b +- sqrt {b^2 -4ac}} over {2a}"}` |
| `native` (chart) | true = a Hangul chart object (`lib/hwpx_docs/chart/spec.md`): `type` bar, hbar, line, pie, combo, area, scatter | `{"chart": {"native": true, "type": "pie", "categories": [...], "series": [...]}}` |
| `stacked`, `lines`, `x_min`, `x_max` | area stacked; scatter: `categories` are the x numbers, `lines` joins the points | `{"type": "scatter", "categories": [1, 2, 3], "lines": true}` |
| `axis` (series), `y2_title`, `y2_min`, `y2_max` | `"secondary"`: the series uses a second value axis on the right | `{"name": "비율", "values": [3, 5], "axis": "secondary"}` |

### Fields and references (package `fields`, rules F01-)

| key | value | example |
|---|---|---|
| `xref` (run item) | `{"target": bookmark or caption, "ref_type": "TARGET_TABLE\|...", "content": "OBJECT_TYPE_PAGE\|...", "link": bool}` (상호 참조) | `{"xref": {"target": "mark1", "ref_type": "TARGET_TABLE", "content": "OBJECT_TYPE_PAGE"}}` |
| `toc` (block) | `{"levels": 3, "title": "차례", "pages": "auto" or {heading: page}, "indent": mm}` | `{"toc": {"levels": 2, "pages": "auto"}}` |
| `index_mark` (run item) | a word, or `{"first", "second"}` | `{"index_mark": "사과"}` |
| `index` (block) | `{"title": "찾아보기", "pages": "auto" or {word: page}}` | `{"index": {"pages": "auto"}}` |
| `form` (run item) | `{"type": "check\|radio\|button\|combo\|list\|edit\|scroll", "name", "caption", "checked", "group", "items", "value", "text", "w", "h", ...}`; `hd form fill` sets values | `{"form": {"type": "check", "name": "agree", "caption": "동의함"}}` |
| `change` (run item, track change) | `{"type": "insert\|delete\|format", "t": text, "author", "date": ISO time, "id", "paraend"}` | `{"change": {"type": "insert", "t": "새 글", "author": "hwpx-docs"}}` |
| `field`, `memo` | 누름틀 (see Runs) | `{"field": "성명", "t": "이름을 쓰세요", "memo": "필수"}` |

`hd read` gives `xref` and `index_mark` back as raw `{"xml": ...}` run items and `toc` / `index` as the paragraphs they made
(checked: build, then read). 글자 겹치기, 메모, 날짜 코드: no key yet; the reader keeps them as raw `{"xml": ...}` and the builder writes them as given.

## Space around block tables (rules.md W05)

Hangul ignores the `before` of the paragraph that holds a block table and the `before` of the paragraph after a tall
table. Put that space in the table `margin` (top, bottom), or use a `gap` block.
