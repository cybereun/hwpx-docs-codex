# Coverage of Hangul features

One row per item. **COM** = a corpus file made by Hangul COM (yes / no and how); **pair** = minimal-difference pair
(`P:`, shipped as `tests/fixtures/<name>_A.hwpx` / `_B.hwpx`) or sample (`S:`, `tests/fixtures/<name>.hwpx`);
**rule** = row in `rules.md`; **builder** = `core/build.py` + `core/read.py` support (spec key); **verified** = round
trip with Hangul rendering, ink difference 0.00 (`RT:` sample, `RTP:` pair B file). An item is open until all five are
filled or it has a written reason. Status 2026-11-14: corpus samples RT 24/24 = 0.00, pair B files RTP 106/107 = 0.00
(exception C7.09).

The rows below are about HWPX. The same commands take `.hwp` files (HWP 5.0): the table of both formats is `hwp-parity.md`, the `.hwp` checks are `lib/hwpx_docs/hwp5/coverage.md`.

## C1 글자 모양

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C1.01 | fonts per language (7) | yes | P:char_font, char_font2, char_font_latin | H05 | `font`, `font_<lang>` | RT:hoeuirok; RTP:char_font_latin | |
| C1.02 | size | yes | P:char_size | H07 | `size` | RTP:char_size | |
| C1.03 | 장평 | yes | P:char_ratio | H07 | `ratio` (1 or 7 values) | RTP:char_ratio | |
| C1.04 | 자간 | yes | P:char_spacing | H07 | `spacing` (1 or 7 values) | RTP:char_spacing | |
| C1.05 | 상대 크기 | yes | P:char_relsz | H22 | `rel_size` | RTP:char_relsz | |
| C1.06 | 글자 위치 | yes | P:char_offset | H22 | `offset` | RTP:char_offset | |
| C1.07 | bold | yes | P:char_bold | H07 | `bold` | RTP:char_bold | |
| C1.08 | italic | yes | P:char_italic | H07 | `italic` | RTP:char_italic | |
| C1.09 | underline type, colour, position | yes | P:char_underline, char_underline_pos/shape/color | H22 | `underline` (true, colour or {pos, shape, color}) | RTP:4 pairs | |
| C1.10 | strikeout | yes | P:char_strike, char_strike_shape/color | H22 | `strike` (true or {shape, color}) | RTP:3 pairs | |
| C1.11 | outline | yes | P:char_outline | H22 | `outline` | RTP:char_outline | |
| C1.12 | shadow | yes | P:char_shadow | H22 | `shadow` ({type, color, x, y}) | RTP:char_shadow | |
| C1.13 | emboss | yes | P:char_emboss | H22 | `emboss` | RTP:char_emboss | |
| C1.14 | engrave | yes | P:char_engrave | H22 | `engrave` | RTP:char_engrave | |
| C1.15 | superscript | yes | P:char_super | H22 | `sup` | RTP:char_super | |
| C1.16 | subscript | yes | P:char_sub | H22 | `sub` | RTP:char_sub | |
| C1.17 | text colour | yes | P:char_color | H07 | `color` | RTP:char_color | |
| C1.18 | shade colour | yes | P:char_shade | H22 | `shade` | RTP:char_shade | |
| C1.19 | emphasis mark | yes | P:char_emphasis | H22 | `emphasis` (e.g. dot_above) | RTP:char_emphasis | other mark names not sampled |
| C1.20 | kerning | yes | P:char_kerning, char_fontspace | H22 | `kerning`, `font_space` | RTP:2 pairs | |

## C2 문단 모양

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C2.01 | align justify/left/right/center | yes | P:para_align, para_align_right | H11 | `align` | RTP | |
| C2.02 | align distribute/divide | yes | P:para_align_distribute, para_align_divide | H11 | `align` distribute/divide | RTP | |
| C2.03 | left/right margin | yes | P:para_left, para_right | H08 | `left`, `right` (pt) | RTP | |
| C2.04 | indent / hanging | yes | P:para_indent | H08 | `indent` (negative = hanging) | RTP | |
| C2.05 | line spacing percent | yes | P:para_line_percent | H10 | `line` 160 | RTP | |
| C2.06 | line spacing fixed | yes | P:para_line_fixed | H10 | `line` {fixed: pt} | RTP | |
| C2.07 | between lines / at least | yes | P:para_line_between, para_line_atleast | H24 | `line` {between|at_least: pt} | RTP | |
| C2.08 | space before/after | yes | P:para_before_after | H08 | `before`, `after` | RTP | |
| C2.09 | line break unit | partial | P:para_break_latin, para_break_korean; S:latin_break (3 values) | H12, H24 | `latin_break`, `word_break` | RTP:para_break_latin; RT:latin_break 0.00 (word, hyphen, char differ in the render); M:form image test (Korean: BREAK_WORD = 어절) | |
| C2.10 | tabs (types, leaders) | yes (`TabDef.TabItem`, textstyle TS01) | P:tab_stop, tab_type_right/center/decimal, tab_leader_dot/solid/dash, tab_auto; S:tabs_custom, tabs_fields | S11; textstyle TS01-TS04 | `	` in text; `tabs` list or {stops, auto_left, auto_right} (`hh:tabPr`); reader | RT:17 files 0.00; preview draws stops and leaders | |
| C2.11 | paragraph border and fill | yes | S:paraborder | H13, H18 | `border`, `fill`, `border_offset`, `border_connect` | RT:paraborder | |
| C2.12 | widow/orphan | yes | P:para_widow | H12 | `widow` | RTP | |
| C2.13 | keep with next | yes | P:para_keep_next | H12 | `keep_next` | RTP | |
| C2.14 | keep lines | yes | P:para_keep_lines | H12 | `keep_lines` | RTP | |
| C2.15 | page break before | yes | P:para_page_break_before | H12 | `page_break_before` | RTP | |
| C2.16 | outline level | yes | P:para_outline | H24 | `outline_level` | RTP | |
| C2.17 | numbering | yes | P:number_add; S:numbering | H20 | `number`, `numberings` | RT:numbering | |
| C2.18 | bullets | yes | P:bullet_add; S:numbering | H20 | `bullet` | RT:numbering | |
| C2.19 | picture bullets | partial: `HeadingType 3` + `Bullet.HasImage` makes the bullet, no image loads | S:picbullet_built (built, saved by Hangul) | textstyle TS22 | `bullet_image: file`; reader saves the image | RT:picbullet_built 0.00; preview draws the image | needs a Hangul-made image bullet only to double-check |
| C2.20 | vertical align in the line | yes | P:para_valign | H24 | `line_valign` | RTP | |
| C2.21 | 공백 최소값, grid, auto spacing | yes | P:para_condense, para_snap, para_autospace | H24 | `condense`, `snap`, `autospace` | RTP | |

## C3 스타일

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C3.01 | 바탕글 and built-in styles | yes | S:blank | K08 | template keeps all styles | RT:all | |
| C3.02 | 개요 1-10 (apply a style) | yes | P:style_apply | H21 | look is copied (paraPr/charPr); `styleIDRef` stays 0 | RTP:style_apply | open: write `styleIDRef` of the named style |
| C3.03 | user styles | no (`StyleAdd` makes none): built file saved by Hangul | S:styles_user | textstyle TS10-TS12, TS19 | `named_styles`, `style` (block, run); reader | RT:styles_user 0.00 | a run keeps no style reference |
| C3.04 | style links paragraph/char | = C3.03 | S:styles_user | textstyle TS10, TS19 | `next`, `type: char` | RT:styles_user 0.00 (next names and the CHAR style kept by Hangul) | |

## C4 쪽

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C4.01 | paper size | yes | P:page_size_b5 | S03, S04 | `page.size` | RTP | |
| C4.02 | landscape | yes | P:page_landscape; S:landscape | S03 | `page.landscape` | RT:landscape | |
| C4.03 | margins, header, footer length | yes | P:page_margin_left, page_header_len | S05 | `page.margin` | RTP | |
| C4.04 | gutter | yes | P:page_gutter | S16 | `page.margin.gutter` | RTP | |
| C4.05 | page border/fill | yes | P:page_border | S15 | `page_border` (`text_border` paper or content; `page` is read as content) | RTP | |
| C4.06 | columns count/gap/line | yes | P:columns_two; S:columns2 | S06 | `columns` | RT:columns2 | |
| C4.07 | column type | yes | P:columns_type | S18 | `columns.type` | RTP | |
| C4.08 | section break | yes | S:sections | K04 | `sections` | RT:sections | |
| C4.09 | page number position/format | yes | P:page_number, page_number_pos, page_num_format | S08, S17 | `page_number` | RTP | |
| C4.10 | page number start | yes | P:page_num_start | S17 | `{"new_page_num": n}` | RTP | |
| C4.11 | header/footer both | yes | P:header_add, footer_add; S:headfoot | S07 | `header`, `footer` | RT:headfoot | |
| C4.12 | header/footer odd/even | yes (`p.type`) | P:pg_hf | PX01 | `header_odd`, `header_even`, `footer_odd`, `footer_even` + reader (`pagex/`) | RT 3 files | drawn; header rows within 1 px |
| C4.13 | 바탕쪽 | yes: types 0-4, `MasterPageFront` | P:pg_master | PX02, PX03 | `master_pages` + reader (`pagex/`) | RT 6 files + front | drawn; Hangul behavior: COM cannot set `pageDuplicate` (`MasterPageDuplicate` False, file keeps 0) |
| C4.14 | footnote | yes | P:footnote_add; S:footnote_doc | S09 | `{"footnote": ...}` | RT:footnote_doc | |
| C4.15 | endnote | yes | P:endnote_add | S19 | `{"endnote": ...}` | RTP | |
| C4.16 | note format/separator | yes (`HSecDef.FootnoteShape.*`) | P:pg_note | PX08 | `note_shape` + reader (`pagex/`) | RT 16 files | drawn (preview C13.12, rules P15) |
| C4.17 | hide header/footer/page number on a page | yes (`HPageHiding.Fields`) | P:pg_hide | PX04, PX09 | `hide_page` block, `hide_first`; reader raw / `hide_first` (`pagex/`) | RT 4 files | drawn |
| C4.18 | empty lines at the top of a page not shown (빈 줄 감춤) | yes (secd bit 19) | - | HW78 | `page.hide_empty_line` (spec, `hd hwp tospec`, `core/read.py`) | M: form 170142493 builds to 3 pages without it, 2 with it (Hangul 2024) | |

## C5 표

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C5.01 | merge | yes | P:merge_cols, merge_rows | T03 | `cs`, `rs` | RTP; RT:hoeuirok | |
| C5.02 | split | yes | P:table_split | T14 | grid with spans | RTP | |
| C5.03 | cell size | yes | P:col_width, row_height | T02 | `cols`, `heights` | RTP | |
| C5.04 | cell margin | yes | P:table_cellmargin | T06, T13 | `pad` (table, cell) | RTP | |
| C5.05 | cell border width/colour | yes | P:cell_border_width, cell_border_color, cell_border_none | H16 | `border`, `outline`, `hlines`, `vlines`, cell `border` | RTP | |
| C5.06 | all line types | yes: S:cell_line_types (15 types), cell_line_types_more (numbers 0-20) | P:cell_border_type (DOT) | H17, TB01 | all 18 type names | RT:cell_line_types, cell_line_types_more 0.00 | COM `Dash`/`Dot` swapped; wave = zigzag, 3D types = nothing in Hangul and in the preview (`table/coverage.md`) |
| C5.07 | diagonal | yes | P:cell_diagonal | H19 | `diag`, `diag_line` | RTP | |
| C5.08 | cell fill colour | yes | P:cell_fill | H15 | `fill` | RTP | |
| C5.09 | cell fill gradient | yes: S:cell_fill_gradient_com (FillAttr with the colour array) | - | TB02, TB03 | `fill: {type: gradient, ...}` + reader + preview | RT:cell_fill_gradient, cell_fill_gradient_com, cell_fill_gradient_angles 0.00; H-resave | 3 colours: Hangul draws black |
| C5.10 | cell fill picture | no: COM picture items change nothing; H-resave of the builder file | - | TB02, TB04 | `fill: {type: image, ...}` + reader + preview | RT:cell_fill_image 0.00; H-resave | |
| C5.11 | vertical align | yes | P:cell_valign | T08 | cell `valign` | RTP | |
| C5.12 | treat as char | yes | P:table_treat_as_char | T10 | `inline` | RTP | |
| C5.13 | floating position | yes: P:table_pos_* (31 files) | pos_base vs variant | T10, TB05, TB06 | `pos` (vrel, hrel, valign, halign, flow, overlap, hold, affect), `wrap`; reader; preview (paper or page) | RT:31 files 0.00; H-resave | square wrap does not move text in the preview |
| C5.14 | outer margin | yes | P:table_outmargin | T07, T13 | `margin` | RTP | |
| C5.15 | page break mode | yes | P:table_pagebreak | T13 | `page_break` | RTP | |
| C5.16 | repeat header row | yes | P:table_repeat_header | T13 | `repeat_header`, `header_rows` | RTP | |
| C5.17 | caption | yes: S:table_caption (COM actions) | - | TB07 | `caption` (4 sides, auto number) + reader + preview | RT:table_caption, caption_top, caption_left 0.00; H-resave | all 4 sides drawn in the preview |
| C5.18 | formula cells | yes: S:table_formula_sum, avg, param | - | TB09 | cell `formula` (string or {expr, format}) + reader | RT:3 files 0.00; H-resave: cell_formula | the builder does not calculate |
| C5.19 | cell protect | no: no COM action; H-resave of the builder file | - | TB08 | cell `protect`, `editable` + reader | RT:cell_protect 0.00; H-resave | COM typing is not blocked by `protect`; the window's own blocking not observed |
| C5.20 | nested table | yes | P:table_nested | T14 | cell `blocks` with a table | RTP | |

## C6 개체

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C6.01 | picture insert/size | yes | P:picture_add; S:picture_doc | G01, G02 | `pic` | RT:picture_doc | |
| C6.02 | picture crop/brightness/effects/border | yes (crop: XML + resave) | P:pic_bright, pic_contrast, pic_effect_*, pic_border_* | OB03-OB06 | `pic` keys `bright`, `contrast`, `effect`, `crop`, `border` | RT:pic_*; B:build_pics | rows: `lib/hwpx_docs/objects2/coverage.md` |
| C6.03 | text box | no (C07): resave | S:shapes_rt | S25 | shape `text` | RT:shapes_rt | |
| C6.04 | line | no: resave | S:shapes_rt | S25 | shape `line` | RT:shapes_rt | |
| C6.05 | rectangle, rounded | no: resave | S:shapes_rt | S25 | shape `rect`, `round` | RT:shapes_rt | |
| C6.06 | ellipse / arc, polygon, curve | no: resave | S:shapes_rt (ellipse) | S25 | `ellipse` | RT:shapes_rt | arc: COM `$arc` makes it, no builder key yet; polygon, curve: `object` kinds, `objects2/coverage.md` (C6.06) |
| C6.07 | arrow | no: resave | S:shapes_rt | S25 | `arrow` | RT:shapes_rt | |
| C6.08 | group | no (selection fails): XML + resave | S:group_polys | OB13 | `object` kind `group` | RT:group_polys; B:build_objects | rows: `lib/hwpx_docs/objects2/coverage.md` |
| C6.09 | equation | yes | P:equation_add | S21 | `{"equation": "a over b"}` | RTP | |
| C6.10 | chart | no | - | S25 | `chart` block drawn with shapes (bar, line) | examples/chart-report (OPEN OK, render checked) | native Hangul chart object (`native: true`): rows in `lib/hwpx_docs/chart/coverage.md` |
| C6.11 | 글맵시 | yes: `TextArtCreate` + `ShapeDrawTextart` | P:ta_shapes (36), ta_align, ta_spacing, ta_shadow, ta_font | OB12 | `object` kind `textart` | RT:ta_*; B:build_objects | rows: `lib/hwpx_docs/objects2/coverage.md` |
| C6.12 | object wrap | partial | S:shapes_rt (in front of text) | S25 | `wrap` | RT:shapes_rt; P:rect_wrap_0..3 | all four wraps sampled (OB01), `objects2/coverage.md` |
| C6.13 | anchor and position | partial | S:shapes_rt (paper) | S25 | `x`, `y`, `rel` | RT:shapes_rt; P:rect_anchor_*, rect_align_center | page, paragraph, column anchors, alignment, flow: `hrel`, `halign`, `vpos`, `flow` (OB02), `objects2/coverage.md` |
| C6.14 | caption | yes: `ShapeObjAttachCaption` + `ShapeCaption` | P:pic_caption_*, rect_caption_* | OB07, OB08 | `caption` on pic, shapes, objects | RT; B:build_pics, build_place | rows: `lib/hwpx_docs/objects2/coverage.md` |

## C7 기타

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C7.01 | hyperlink | yes (auto) | S:gongmun | S13 | `{"link": url, "t": text}` | RT:gongmun | |
| C7.02 | bookmark | yes | P:bookmark_add | S22 | `{"bookmark": name}` | RTP | |
| C7.03 | cross-reference | yes (`InsertCrossReference`) | S:xref_add (`lib/hwpx_docs/fields/fixtures`) | X01 | `{"xref": ...}` | raw | RT:xref_add | other target types need a Hangul sample made by hand |
| C7.04 | 덧말 | no (COM saves no text, TS14): built file saved by Hangul | S:dutmal_top, dutmal_bottom, dutmal_wide | textstyle TS14, TS15 | run item `{"dutmal": {main, sub, pos, size, align}}`; reader | RT:3 files 0.00; preview draws it | `option` values not explored |
| C7.05 | 글자 겹치기 | yes | P:compose_add | S24 | raw `xml` | RTP | |
| C7.06 | memo | yes | P:memo_add | S24 | raw `xml` | RTP | |
| C7.07 | table of contents | no (`MakeContents` server exception) | S:toc_made | X04, X05 | block `{"toc": ...}` (static entries, auto page numbers) | RT:toc_made | Hangul's own structure needs a sample made by hand |
| C7.08 | index | yes | S:index_mark_add, S:index_made | X02, X03 | `{"index_mark": ...}`, block `{"index": ...}` | RT | |
| C7.09 | 누름틀 | yes | P:field_add | S23, X06 | `{"field": name, "t": guide, "memo": ...}` | RTP: 0.00 with equal caret | closed: a caret in the field hides the guide text (settings.xml), not a builder difference |
| C7.10 | form objects | no (creators wait for a mouse drag); XML by model names, saved by Hangul | S:form_objects | F01-F09 | run item `{"form": {...}}`, `hd form fill` | RT:form_objects; preview drawn | F08: several combo/list items, newline in edit, frame: need a Hangul sample made by hand |
| C7.11 | date code | yes | P:datecode_add | S24 | raw `xml` | RTP | |
| C7.12 | track changes | no (by COM); sample made by hand | S:track_change (`lib/hwpx_docs/fields/fixtures`) | T01-T05 | `{"change": ...}` | RT:track_change 0.00 | limits: accept/reject, change bar |

## C8 입력

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C8.01 | connectors | no: XML + resave | S:connect_* | OB11 | `object` kind `connector` | RT; B:build_objects | rows: `lib/hwpx_docs/objects2/coverage.md` |
| C8.02 | freeform pen | no: XML + resave | S:curve_* | OB10 | `object` kind `curve` | RT; B:build_objects | |
| C8.03 | OLE object (embedded file) | no creator by COM: user sample | S:ole_file | OB17, OB19 | `{"ole": {"src": ...}}` | RT:ole_file; B:build_ole | rows: `lib/hwpx_docs/objects2/coverage.md` |
| C8.04 | 교정 부호 | no action found: user sample | S:proof_marks | OB17, OB18 | run item `{"proof": kind, "text": ...}` | RT:proof_marks; B:build_ole | kinds lineattach, attach, delete, clipping |
| C8.05 | 문자표 symbols stay plain Unicode | yes | S:sincheongseo, table_form, hoeuirok | H05 | text | RT | |
| C8.06 | 입력 도우미: date code | yes | P:datecode_add | S24 | raw `xml` | RTP | file name, 상용구: open |
| C8.07 | 한자, 한자 병기 | no effect of `InputHanja` (TS20); made by hand in Hangul (F9) | S:hanja_dialog (hand-made), hanja_forms (typed text) | textstyle TS20 | text; the 덧말 form = run item `dutmal` (C7.04) | RT:hanja_dialog, hanja_forms 0.00 | 3 text forms + 1 덧말 form recorded; the other 3 icon forms not saved |
| C8.08 | picture bullets | = C2.19 | | | | | |

## C9 서식

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C9.01 | drop cap | yes (`DropCap`, `HDropCap`) | P:dropcap_two, dropcap_three, dropcap_margin; S:dropcap_frame, dropcap_built | textstyle TS17 | block `dropcap` {lines 2/3/margin, font, color, frame, fill, gap}; run item; reader | RT:7 files 0.00 | preview draws it approximately (TS21) |
| C9.02 | 형광펜 | yes | P:char_markpen | S20 | `highlight` | RTP | |
| C9.03 | 글자 테두리/배경 | yes | P:char_border | H23 | `char_border`, `char_fill` | RTP | |
| C9.04 | 자간 steps | yes | = C1.04 | H07 | `spacing` | RTP | |
| C9.05 | 스타일마당 | no action (`StyleTemplate` False); Hangul opens the 25 ko-KR templates | n/a: table of every template in `lib/hwpx_docs/textstyle/templates.md` | textstyle TS18 | n/a (record); `named_styles` writes such a set | M: 25 templates opened and read | |
| C9.06 | 개요/문단 번호 모양 | yes | S:numbering, blank | H20 | `numberings` | RT:numbering | |
| C9.07 | level increase/decrease | yes | S:numbering | H20 | `number.level` | RT:numbering | |

## C10 쪽 (more)

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C10.01 | vertical writing | yes | P:pg_sec | PX05 | `text_direction`, `vertical_head` + reader (`pagex/`) | RT 2 files | drawn (renderer owner) |
| C10.02 | line numbers | yes | P:pg_sec | PX06 | `line_numbers` + reader (`pagex/`) | RT 3 files | drawn; open: restart values on several pages |
| C10.03 | columns change inside a page | yes (`BreakColDef` + `MultiColumn` ApplyTo 2) | S:cols_mid_S | PX10 | `columns_here` block; reader raw (`pagex/`) | RT cols_mid_S 0.00 | drawn (renderer owner) |
| C10.04 | 새 번호로 시작 | yes | P:page_num_start | S17 | `new_page_num` | RTP | footnote/figure restart: open |
| C10.05 | 현재 쪽만 감추기 | - | - | - | - | - | = C4.17 |
| C10.06 | 원고지 | yes (`WongojiFormat`, `CharGrid`, `LineGrid`) | P:pg_sec, S:wonggoji_grid_S | PX07 | `manuscript`, `char_grid`, `line_grid` + reader (`pagex/`) | RT flag and grid sample 0.00 | text in cells not drawn; Hangul draws no grid line in its page image |
| C10.07 | 라벨 | yes (`LabelTemplate` = locked table) | S:label_S | PX11 | table block + `page.margin` (`pagex/`) | RT | drawn |
| C10.08 | 바탕쪽 odd/even/first | - | - | - | - | - | = C4.13 |

## C11 보안 (post-step with Hangul COM only; no cryptography is reverse-engineered)

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C11.01 | 문서 암호 | yes (FilePassword, HPassword.string; then SaveAs) | - | - | `hd secure --password-env NAME` (`secure/post.py`) | M: real Hangul run 2026-11-14 (throwaway file and test password): `SECURE OK`, package shows 4 encrypted parts (aes256-cbc), `hd read` exit 4, preview placeholder | test password in a throwaway file only; password from an environment variable, never an argument |
| C11.02 | 배포용 문서 | yes (SaveAs, then FileSetSecurity: Password, NoPrint, NoCopy, in place on the saved file) | - | - | `hd secure --distribute [--no-print] [--no-copy]` | M: real Hangul run: `SECURE OK (distribution)`, same package marks as C11.01 | FileSetSecurity returns False on a document that was never saved. In HWPX the password and the distribution file look the same in the package (manifest, `GetFileInfo` is `UNKNOWN`/-1 for any HWPX); the NoPrint/NoCopy flags are inside the encrypted parts (not readable here). An HWP password file shows `GetFileInfo.Encrypted=2`, a distribution HWP shows 0 |
| C11.03 | 선택 글자 보호 | FindPrivateInfo / ProtectPrivateInfo / SetPrivateInfoPassword | - | - | - | S: probed 2026-11-14 on fake data, every call returned 0 / False for every pattern type (the document text stayed unchanged) | limit: Hangul's selective protection is not driven by COM here; it needs Hangul's encryption, which this plugin does not write. Use C11.04 (masking) or C11.01 for the whole document |
| C11.04 | 개인 정보 보호 | no (the COM calls of C11.03 do nothing) | - | - | `hd secure <in> <out> --mask-private` (`secure/mask.py`, no Hangul, no password) | M: self-test: resident / phone / e-mail / card numbers in section text become `*`, other text, attributes and the input stay | plain text replacement, not encryption: the hidden text is gone from the new file, also from `Preview/PrvText.txt`, and the preview picture becomes white (security review 2026-11-15); a number split over two runs is not found; a protected input is refused |
| C11.05 | 문서 보안 설정 | FileSecurity (IsActionEnable True, but Execute returns False), DocDRM and CertDRM (IsActionEnable False) | - | - | - | S: probed 2026-11-14 | limit: DRM needs a certificate or a DRM server of the user; not automatable and not changed (Hangul's own security settings stay untouched) |
| C11.06 | protected file in the reader | n/a | - | - | `core/protect.py`: `hd read|check|...` print `PROTECTED: ...` and exit 4; `hd secure --info`; preview draws a placeholder page (`preview/protected.py`) | M: self-test with a fake protected package; real password and distribution files checked | detection only (package marks); no decryption |

## C12 변환 (M2)

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C12.01 | HWP (binary) -> HWPX | yes (Open + SaveAs "HWPX") | - | - | `hd convert` (`convert/convert.py`) | M: 2 samples made in Hangul, reopened with no prompt | Hangul only; protected or damaged files may fail |
| C12.02 | HWPX -> HWP | yes (SaveAs "HWP") | - | - | `hd convert` | M: see C12.01 | |
| C12.03 | HWP/HWPX -> PDF | yes (SaveAs "PDF") | - | - | `hd convert` | M: see C12.01 | |
| C12.04 | batch with one Hangul | yes | - | - | `convert.convert(pairs)` via `run_jobs` | M | access prompt once per batch ("모두 허용") |

## C14 쪽 모양새 (pagefit: checks and fixes of the spec, no Hangul needed; a named profile, default `minimal`, `readable` for the reading rules)

Not a Hangul feature: the tool finds pages that look empty, cut or lonely and fixes the spec (spacing, keep rules, forced breaks;
never the text size). Page layout = the preview's block heights + the keep rules of Hangul (`lib/hwpx_docs/pagefit/rules.md` PF01-PF12).
Verified = page count and the bottom of the text of every page against Hangul's pages (plan of 4 chapters: 6 pages -> 4, the text
bottom of each page within 0.3 mm of Hangul's).

| id | item | COM | pair | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C14.01 | fill of each page, free space in mm | n/a | n/a | PF01 | `hd pagefit check` | M: model vs Hangul 0.2 mm (6 + 4 pages); columns, footnotes, objects: the preview's flow (page counts 5 -> 4, 6 -> 4, 6 -> 4 in Hangul) | the preview applies keep_next, keep_lines, widow and page_break_before since its rule P17 (pagefit PF01, PF25); with `page_break` cell it cuts a group of merged rows like any rows (rules P18; measured in Hangul: `merged_rows` 128 of 128), pagefit's `table_group` rule (PF02) still keeps such a group whole: open |
| C14.02 | heading alone at the bottom of a page | n/a | n/a | PF02 | `check` heading | M: Hangul keeps it with `keep_next` | |
| C14.03 | one line of a paragraph at the bottom or the top | n/a | n/a | PF03 | `check` orphan_end / orphan_start | M: `widow` (breakSetting widowOrphan) honoured by Hangul | |
| C14.04 | table cut after its header row | n/a | n/a | PF04 | `check` table; `fix` moves the table (`page_break_before`) | M: Hangul page 2 before / table on page 3 after | |
| C14.05 | short last page | n/a | n/a | PF05 | `check` last; `fix` pulls it back (spacing -3 pt at most) | M: 2 pages -> 1 in Hangul | |
| C14.06 | fix: keep rules | n/a | n/a | PF07 | `hd pagefit fix` (`keep_next`, `widow`) | M | |
| C14.07 | fix: forced breaks after an empty page | n/a | n/a | PF08 | `fix` | M: plan 6 -> 4 pages | |
| C14.08 | fix: free space into paragraph and table spacing | n/a | n/a | PF10, PF19 | `fix` (`after`, table margin below, +6 pt at most) | M: pages 100 % | text size never changes |
| C14.09 | reading units kept on one page (heading + first content, item + sub items, table + caption / introduction / notes, figure, box, 붙임, last paragraph + 끝. + 결문; weak: short section, numbered list) | n/a | n/a | PF15, PF16 | `check` unit; `fix` (keep_next, keep_lines, table `none`, a break before a unit that flags cannot hold) | M: 8 documents before and after, Hangul page counts equal, page bottoms within 1 mm | |
| C14.10 | long table: cut between rows, header repeated, parts of 3 rows at least | n/a | n/a | PF17 | `check` table_rows / table_head / table_cell; `fix` | M: 70-row table; merged rows not cut | |
| C14.14 | reading order: a table kept whole that waits for the next page while the text after it moves up; a header-like first row of a table over pages; a footnote in a cut table row | n/a | n/a | PF26-PF28 | `check` order; `fix` gives whole tables `hold` (holdAnchorAndSO), repeats a bold / filled first row, moves the cut above a row whose note goes on | M: a real plan and review document in Hangul (order 11 -> 0, header rows on pages 15-19, note on its row's page) | |
| C14.12 | profiles: the rules as a named style (`minimal`, `readable`, an own JSON file), skill `hwpx-readability` | n/a | n/a | PF22 | `--profile`, `hd pagefit profiles`, `skills/hwpx-readability` | T | |
| C14.13 | readable profile checked in Hangul on 7 documents: breaks go before the keep chain (PF23), a big table is cut between rows instead of leaving a gap (PF24), pages of footnote documents equal Hangul's (PF25) | n/a | n/a | PF23-PF25 | `fix`, `check`, `tables.split_gap_mm` | T; M | a gap stays when the notes under a table do not fit by a few mm; the preview flow does not carry a table with `keep_next` (pagefit corrects its pages) |
| C14.11 | pointers: `표 N` sentence on another page, footnote continuing, page number or direction in the text | n/a | n/a | PF18 | `check` ref / note / pageref (footnote continuation fixed when a paragraph move helps) | T | |

## Generic fallback

Any run element that the spec has no key for is kept as raw OWPML (`{"xml": "..."}`) by `core/read.py` and written
back as given by `core/build.py` (ids inside are not changed). This is how 글자 겹치기, memo and date code round-trip.

## Not applicable

Editing-only commands (쪽 복사/붙이기/지우기, undo, redo, find/replace) are not stored in the document.
