---
name: hwpx-table
description: Tables in HWPX — column widths, row heights, merged cells, per-cell lines and fills, cell margins, header rows repeated on each page, space around tables. Use for 한글 표 만들기, 셀 병합, 테두리, 표 양식.
---

# HWPX tables

`hd` = `python "${skillRoot}/lib/hd.py"`. Spec: `${skillRoot}/docs/spec.md` section "Table";
rules T01-T15 and W04-W06 in `${skillRoot}/docs/rules.md`.

## Write a table

```json
{"table": {"cols": [30, 60, 80], "heights": [9, 9, 9], "border": "0.12mm solid", "outline": "0.4mm solid",
  "header_rows": 1, "repeat_header": true, "margin": 0,
  "rows": [[{"p": "구분", "fill": "#F2F2F2", "bold": true, "align": "center"}, {"p": "내용", "cs": 2}],
           ["1", "가", {"p": "세로 병합", "rs": 2}],
           ["2", "나"]]}}
```

- Rows list cells like HTML: a cell takes the next free grid position; `cs`/`rs` span columns/rows.
- `cols` and `heights` are outer cell sizes in mm; their sum is the table size. Hangul grows a row to fit its text.
- Cell `border` sets the grid lines around that cell (a later cell wins on a shared line). Line widths snap to
  Hangul's list (0.1 ... 5 mm).
- Keep Hangul's default cell margins (1.8 / 0.5 mm) unless the target shows otherwise; text near a line reads badly
  (readability RD07).
- Repeated looks: spec `styles` + cell `"class": "head"`.
- Space before or after a block table: use the table `margin` (top, bottom) or a `gap` block; Hangul ignores the
  anchor paragraph's `before` (rule W05).
- Long tables: `header_rows` + `repeat_header` (readability RD10). A table is treated as a character (`inline` true) unless it has
  `pos`, `wrap`, `side`, `hold`, `header_rows`, `page_break: "cell"` or is about as high as a page: those flow and Hangul cuts them
  between pages. Write `"inline": false` to make any table flow, `"inline": true` to keep a tall one as a character (rule TB11).

## More table features (rules TB01-TB11 in `${skillRoot}/lib/hwpx_docs/table/rules.md`)

- Cell `fill`: a colour, a gradient `{"type": "gradient", "kind": "linear", "angle": 90, "colors": [a, b]}` (give 2 colours; Hangul
  draws 3 black) or a picture `{"type": "image", "src": "a.png", "mode": "tile"}`.
- Table `caption`: `{"text": "제목", "side": "bottom"}` (auto number "표 1"). Floating table: `pos` with `rel` / `vrel` / `hrel`,
  `halign`, `valign`, `wrap`. Cell `protect`, and `formula` (`=SUM(?1:?3)`; the shown result goes in `p`, the builder does not calculate).
- Line types in `border`: 18 names, the last six (`wave doublewave thick3d thickrev3d 3d rev3d`) are drawn solid in the preview.
- Text beside a square-wrapped floating table: `side` (`both_sides`, `left_only`, `right_only`, `largest_only`); a floating
  table that shares its paragraph with text: `same_para` (reader rule S26). All table keys: `docs/spec.md` "Table" and its
  list "More table keys".
- A long table on a page: skill hwpx-readability (`hd pagefit`) cuts it between rows with the header repeated (on request).

## Check

`hd build`, then `hd check out.hwpx checklist.md` with rows such as `table[0].cols`, `table[0].heights`,
`text("구분").cell.fill` (query forms: skill hwpx-from-image), then render (skill hwpx-core).
