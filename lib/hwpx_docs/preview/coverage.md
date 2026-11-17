# Coverage C13: page preview (package `preview`; `hd preview`, `hd render hwpx f --backend preview`)

No Hangul and no third-party program. Pipeline: `core/read.py` spec -> layout in mm (real font widths, `core/textfit.py`) ->
SVG pages -> HTML -> PNG (Edge print, `render.render.html_pages`). Layout rules: `rules.md` (P01-P10).

| id | item | drawn | note |
|---|---|---|---|
| C13.01 | paragraph: char shape (font per language, size, 장평, 자간, bold, italic, colour, shade, underline, strike, sup/sub), align (justify, center, right, distribute), indent, spacing, line spacing (percent, fixed, at least, between), 어절/글자 line break | yes | RT corpus below; 자간/장평 and the other char shapes have no Hangul reference of their own yet (open: widen with the `_B` pairs) |
| C13.02 | tables: grid, merges, per-cell border (line types, double lines), fill, diagonals, margins, valign, nested | yes | row height = max(`cellSz`, content); borders drawn per grid line (stronger side wins); merged rows (`rs`) in a `page_break` cell table are cut at a page end like rows, a cell that crosses the cut goes on in the rest (rules P18, Hangul `merged_rows` 128 of 128; kps-ai, delegation: P20) |
| C13.03 | shapes (rect, ellipse, line with arrow, text box), pictures (inline and floating), page border, columns, header/footer, page number, footnote, numbering/bullets | yes | floating objects are placed by `paper`/`page` (the body area)/`para` (the anchor paragraph's top, moving with it), `hrel` and `halign`; `square` text goes on beside them and `top_and_bottom` moves it below, also text placed before the anchor on the page (rules P16, self-test PREVIEW WRAP; table_pos_* of the table session against Hangul). A table or picture in the paragraph of its text (`same_para`, rules S26) is anchored to that text; `side` = `textFlow`. Open: square wrap in cells, boxes, headers and after a column change; a floating object of a feature package (chart ...) in the paragraph of its text still gets an empty line of its own |
| C13.04 | pages: break, sections (own page size, landscape), start page number | yes | page count equals Hangul on all 28 corpus pages |
| C13.05 | not drawn / open | no | hatch fills, 글자 효과 (outline, shadow, emboss, engrave), 강조점, the exact default tab stop (Hangul 17 mm in `tabs_fields`, preview 14.1 mm; custom stops and leaders are drawn, rules P12), `condense`. (Cell gradient and picture fills: `table/draw.py`; picture crop and effects: `drawers/objects2.py`.) |
| C13.08 | 글자 겹치기 (`hp:compose`: circle, box, rhombus, reversed), 글자 테두리 and 글자 배경 (char border fill) | yes | `drawers/compose.py`; char border per side (reader `{side: line}`); no Hangul reference page of their own yet (compose_add_B, char_border_B) |
| C13.09 | anything else that takes room (an object of an unknown type, a raw element with `hp:sz`, a picture whose file is missing) | placeholder | dashed red box with the type name + one line `PREVIEW NOT DRAWN <type> <w> x <h> mm on page <n>`; never a silent blank. New kinds: a module in `drawers/` (docs/interfaces.md "Preview drawers") |
| C13.10 | 사용자 탭 and tab leaders (C2.10); 단 설정 나누기 inside a section (C10.03) | yes | rules P12, P13; self-tests PREVIEW TABS, PREVIEW COLUMNS; column change against Hangul (cols_mid_S, page session): ink 45.8 / coarse 5.8; tabs: no Hangul page yet (tabs_custom) |
| C13.12 | 주석 모양 (C4.16, section `note_shape`): note number format, prefix, suffix, user character, superscript in the note, start, numbering continuous / on_section / on_page (footnotes); separator line type, width, colour, length; spacing between / below / above; endnotes after the text at the end of the document or section; footnotes under each column, under all columns or under the last one; beneath_text; the body keeps room for its footnotes | yes | rules P15; self-test PREVIEW NOTES; footnote_doc against Hangul: line and first note exact, ink 33.3 -> 29.6; the six nt_* Hangul samples of the page session (on_page, the three places in columns, beneath_text, a long note split over two pages) have the same rows and lines as Hangul; the rest of their ink difference is the space width P08 |
| C13.11 | 세로쓰기 (C10.01: vertical, vertical_all, vertical_head): text, Latin/digits/brackets, upright tables and pictures, horizontal header, footer, page number and page border | yes | `preview/vertical.py`, rules P14; 9 Hangul samples of the page session: ink mean 42.2 -> 23.9, coarse 17.5 -> 6.1 after the full cells and 。、 of P08 (vt_media 8.7 ... vt_all_mixed 36.3); page number centre within 0.1 mm of Hangul (vt_pages); vertical_head writes header, footer and page number down the page; floating pictures and tables stand upright with offsets on the turned page (vt2_* samples of the page session: positions within 0.2 mm; ink 24.9-26.0 after P08) |
| C13.13 | equations (`hp:equation`, spec run `equation`): fractions, roots, scripts, big operators with limits, brackets, matrices, cases, piles, accents, symbols, styles | yes | `drawers/equation.py` + `equation/` (rules E01-E23, rows in `equation/coverage.md`); every command of the Hangul help is drawn (`ladder`, `sladder`, `longdiv`, `phantom`, matrix column mode too); a script that fails is shown as text with a warning line. Fidelity against Hangul pages (27 samples, mean ink 40.3, coarse 13.3): see `equation/coverage.md` |
| C13.06 | needs | - | fonts are measured with Windows GDI and drawn by Edge: without the Hangul fonts the lines break differently; without Windows the width is an estimate and no PNG is made (SVG and HTML are still written) |
| C13.07 | Hangul chart objects (`hp:chart`, spec `chart` with `native`): column, bar, line, combo, pie, stacked; title (empty = "차트 제목", a pie: its series name), axis titles, legend right/left/top/bottom/none, value labels, min/max, gridlines; a part kept whole (`ooxml`) is drawn from the `view` that the chart package reads from it | yes | Hangul's default chart style (rules P10; drawn by the chart package, `chart/draw.py`, registered as DRAWS). Whole-page fidelity of all 23 chart fixtures: below (mean ink 18.35). Open: colours 5 and 6 of the palette, scatter/area/doughnut parts (frame only), the axis step rule is fitted on 7 charts |

Fidelity against Hangul pages (2026-11-15, after rules P08 and the footer place of P06; 23 corpus pages, 96 dpi; `python -m hwpx_docs.preview.tests fidelity`; before: mean 17.78 / 6.00). `ink` =
`hd img compare` (percent of 4 px blocks that have ink in one image only; glyph edges differ because Hangul draws hinted
bitmap glyphs, so 0 is not reachable for text); `coarse` = the same with 12 px blocks (layout: 3 mm).

| page | ink | coarse |
|---|---|---|
| blank_p1 | 0.00 | 0.00 |
| bogoseo_p1 | 19.17 | 3.41 |
| box_doc_p1 | 10.68 | 7.14 |
| columns2_p1 | 11.80 | 4.72 |
| footnote_doc_p1 | 15.08 | 4.14 |
| gongmun_bodo_p1 | 11.68 | 3.04 |
| gyehoekseo_p1 | 18.37 | 3.23 |
| headfoot_p1 | 15.31 | 3.16 |
| headfoot_p2 | 24.10 | 16.33 |
| hoeuirok_p1 | 19.09 | 5.62 |
| landscape_p1 | 4.66 | 1.51 |
| numbering_p1 | 18.32 | 1.42 |
| pagebreak_p1 | 16.96 | 4.17 |
| pagebreak_p2 | 18.58 | 4.17 |
| paraborder_p1 | 19.62 | 2.49 |
| picture_doc_p1 | 2.28 | 1.95 |
| sections_p1 | 7.53 | 0.00 |
| sections_p2 | 10.64 | 0.00 |
| shapes_rt_handwritten_p1 | 17.65 | 9.20 |
| shapes_rt_p1 | 17.65 | 9.20 |
| sincheongseo_p1 | 7.82 | 5.98 |
| table_form_p1 | 14.09 | 1.08 |
| tabs_fields_p1 | 18.97 | 0.00 |
| **mean** | **13.91** | **4.00** |

Examples (`examples/*/page1.png` = Hangul 2024 page 1, 96 dpi: all six rendered again by Hangul on 2026-11-15 with the
security module are pixel for pixel the same; 2026-11-15, after P08), ink / coarse12: application-form 9.24 / 5.85,
chart-report 10.17 / 2.10, facility-checklist 12.59 / 2.49, gongmun-notice 14.01 / 3.89, meeting-minutes 9.87 / 0.76,
report-markdown 15.62 / 5.02 (its text uses 글꼴에 어울리는 빈칸, so its spaces stay 0.3 em); **mean 11.92 / 3.35**
(before P08 22.06 / 5.79).

Other Hangul pages (2026-11-15, before -> after P08 and the vertical cells of P14; mean ink / coarse12): chart fixtures
23 pages 18.35 / 10.81 -> 18.08 / 10.81; table session fixtures 43 pages 17.04 / 5.42 -> 9.69 / 2.51; footnote samples
nt_* 8 pages 36.08 / 15.86 -> 12.42 / 2.73; vertical vt_* 9 pages 42.21 / 17.53 -> 23.92 / 6.08; vt2_* 4 pages
42.48 / 13.12 -> 25.20 / 2.65; no page worse.

Chart fixtures (`lib/hwpx_docs/chart/fixtures`, whole page 1 against Hangul pages made by one Hangul batch, 2026-11-14),
ink / coarse12: combo 12.69 / 4.62, pie 9.51 / 3.53, the 10 `_A` files and `default` (Hangul's default chart, drawn
from `view`) 17.90 / 10.32 each (same page), color_B 16.75 / 9.09, direction_B 15.10 / 8.52, legend_B 24.14 / 19.04,
legend_none_B 20.20 / 18.26, series_name_B 17.84 / 10.37, stack_B 19.52 / 9.69, title_B 18.20 / 10.22, type_B
20.63 / 7.69, value_B 28.15 / 17.83, axis_title_B 22.36 / 16.34; **mean 18.35 / 10.81**. The Hangul pages are kept
outside the repository (make them again with one Hangul batch when the user allows it).

Open:
- The five 공문 samples (`gongmun`, `gongmun_gongo`, `gongmun_gyeoljae`, `gongmun_sihaeng`, `gongmun_tongji`) were scrubbed of real names
  after the first reference pages were made, so their references are not shipped; make them again with
  `hd render hwpx <fixture> <dir> --backend hangul` (one Hangul batch, one "모두 허용").
- Widen with the 106 `_B` pairs: two Hangul batches (106 and 27 files) got no answer to the file-access prompt (nobody at the PC).
