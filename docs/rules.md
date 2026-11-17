# HWPX (OWPML) rules, verified with Hangul 2024

Every row comes from a Hangul-made file in `corpus/` or from a test with a written result. Evidence keys:
- `S:<name>` = corpus sample made by Hangul COM; shipped as `tests/fixtures/<name>.hwpx`.
- `P:<name>` = minimal-difference pair (A = before, B = after one change); shipped as
  `tests/fixtures/<name>_A.hwpx` and `<name>_B.hwpx`.
- `RT:<name>` = round trip (Hangul file -> spec -> builder -> Hangul pages; ink difference 0.00 for every sample).
- `F:<id>` = fault test (one broken thing, opened in Hangul).
- `M:<what>` = a measurement on rendered pages (300 dpi unless stated).
- `W:<doc>` = a browser-vs-Hangul measurement on 7 HTML reports (Edge print vs Hangul pages, `hd measure`).
RT, F, M and W records are development records; they are not shipped. `hd selftest` repeats the read -> build ->
read check on all fixtures with no Hangul.
- `Model:` notes in a row come from the check against Hancom's published OWPML model (`hancom-io/hwpx-owpml-model`,
  2023); the table of all rows is `owpml-crosscheck.md`. Where the model and our evidence differ, the row keeps both.

Units: 1 HWPUNIT (hu) = 1/7200 in. 1 pt = 100 hu. 1 mm = 283.465 hu. Font size: `height` = pt x 100.
The builder (`core/build.py`) applies all rows. The spec format is in `spec.md`.

## 1. Package (ZIP)

| id | rule | evidence |
|---|---|---|
| K01 | Entries: `mimetype` (`application/hwp+zip`), `version.xml`, `Contents/header.xml`, `Contents/section0.xml` (and `section1.xml` ...), `Contents/content.hpf`, `settings.xml`, `META-INF/container.xml`, `META-INF/container.rdf`, `META-INF/manifest.xml`, `Preview/PrvText.txt`. `Preview/PrvImage.png` is optional. | S:blank; RT:all (builder writes no PrvImage) |
| K02 | Write `mimetype` first and STORED (Hangul does). Hangul also opens it when it is not first or is deflated. | S:blank; F:F15, F16 (open OK, ink_diff 0) |
| K03 | `content.hpf` manifest MUST list every section file. A missing section item: Hangul does not open the file. | F:F17 (open FAIL) |
| K04 | Several sections: `Contents/sectionN.xml`, one manifest item and one spine `itemref` each, `hh:head secCnt="N"`. | S:sections; RT:sections |
| K05 | Pictures: `BinData/imageN.<ext>`, manifest item `id="imageN" media-type="image/png" isEmbeded="1"`. Hangul writes a `hashkey` attribute; it is not necessary. | P:picture_add; RT:picture_doc (no hashkey, 0.00) |
| K06 | All XML parts MUST be well-formed. A raw `&` in text: Hangul does not open the file. A duplicated attribute: Hangul opens it but loses content. | F:F09 (FAIL); F:F14 (open OK, ink_diff 41) |
| K07 | `hp:linesegarray` (layout cache) is optional. Hangul makes the layout again; the pages are the same. | RT:all (builder writes none); test original_nols (0.00) |
| K08 | Start from a Hangul-made empty document (`core/template/`) and add items after its items. This keeps the Hangul styles (바탕글, 개요 1-10, 쪽 번호, 머리말, 각주 ...) for the user. | S:blank |

## 2. Header reference lists (`Contents/header.xml`)

| id | rule | evidence |
|---|---|---|
| H01 | Order in `hh:refList`: fontfaces, borderFills, charProperties, tabProperties, numberings, bullets, paraProperties, styles, memoProperties. `hh:bullets` is not in an empty document; add it before paraProperties. Model: the list continues with `hh:trackChanges`, `hh:trackChangeAuthors` after memoProperties. | S:numbering |
| H02 | Ids: borderFill starts at 1; charPr, paraPr, tabPr start at 0; numbering and bullet start at 1. The empty document has borderFill 1-2, charPr 0-6, paraPr 0-19, tabPr 0-2, numbering 1. Hangul renumbers ids on each save, so ids are not stable between files. | S:blank; P:char_font2 |
| H03 | `itemCnt` one too big: Hangul opens the file with no change. Write the correct count. | F:F01 |
| H04 | A reference to a missing charPr or borderFill id: Hangul opens the file, but the text or cell shows other formatting. | F:F02 (3.09), F12 (1.77) |
| H05 | Fonts: one `hh:fontface` per language (HANGUL, LATIN, HANJA, JAPANESE, OTHER, SYMBOL, USER); `hh:charPr/hh:fontRef` has one font id per language. Characters such as ○ □ ☐ ※ · use the SYMBOL font, not the HANGUL font. Set all 7 languages, or the symbols change shape. | RT:hoeuirok (○ changed until all 7 were kept) |
| H06 | `hh:font/hh:typeInfo` (panose-like values) does not change the rendering: generic values are sufficient. | test: gongmun_sihaeng typeInfo swap (no change) |
| H07 | charPr: `height` = pt x 100; `textColor`; `shadeColor` (`none` or colour); `hh:ratio` (장평 %), `hh:spacing` (자간 %), `hh:relSz`, `hh:offset` per language; `<hh:italic/>` then `<hh:bold/>` (empty elements); `hh:underline type="BOTTOM|NONE"`; `hh:strikeout shape="SOLID|NONE"`. | P:char_size, char_bold, char_italic, char_underline, char_strike, char_color, char_spacing, char_ratio |
| H08 | paraPr margins and spacing are in `hp:switch`: `hp:case` (namespace `.../2016/HwpUnitChar`) holds the real value in hu, `hp:default` holds 2 x the value. 10 pt left margin = case 1000, default 2000. Model: a `hp:case` is read when the reader supports the namespace in its `hp:required-namespace` (HwpUnitChar 2016), else `hp:default`; `hc:left` and the other margin values have `value` and `unit` (CHAR or HWPUNIT). The model does not state the 2 x factor. | P:para_left, para_right, para_indent, para_before_after; M: 10 pt moved the text 42 px at 300 dpi = 10.08 pt |
| H09 | Hangul also reads a paraPr with no `hp:default` branch, or a plain `hh:margin` with the case values (no `hp:switch`). The builder writes both branches, as Hangul does. | F:F03, F13 (0.00) |
| H10 | Line spacing: `hh:lineSpacing type="PERCENT" value="160"` (same in both branches); `type="FIXED"` value in hu, doubled in `hp:default`. Also AT_LEAST, BETWEEN_LINES. Model: the same four types, and an attribute `unit` (CHAR or HWPUNIT, default HWPUNIT). | P:para_line_percent, para_line_fixed |
| H11 | `hh:align horizontal`: JUSTIFY, LEFT, RIGHT, CENTER, DISTRIBUTE, DISTRIBUTE_SPACE. Indent: `hc:intent` (negative = hanging). | P:para_align, para_align_right, para_indent |
| H12 | `hh:breakSetting`: keepWithNext, keepLines, pageBreakBefore, widowOrphan, breakNonLatinWord. Korean line break is the OPPOSITE of the names: `KEEP_WORD` breaks inside words (글자 단위, Hangul's default), `BREAK_WORD` breaks between words (어절 단위). Spec: `word_break` "char" (default) / "word". Model: the same two names, but it does not say which one breaks where (our meaning is from the render test); it also lists `breakLatinWord` (KEEP_WORD, HYPHENATION, BREAK_WORD) and `lineWrap` (BREAK, SQUEEZE, KEEP). | P:para_keep_next; S:blank; verify/imagetest1 (render: "정확/한" with KEEP_WORD, "정확한/표현" with BREAK_WORD) |
| H25 | Negative indent (hanging): the FIRST line starts at `left`, the other lines at `left + |indent|`. For "○ text" with the mark at 4.9 mm and wrapped lines at 12.7 mm: left = 4.9 mm, indent = -7.8 mm. | verify/imagetest1 v1 -> v2 |
| H26 | `condense` (공백 최소값 %) lets justified lines shrink spaces and so changes where lines break; forms made in Hangul often use it (a measured 공문 form: 30). | M:form image test |
| H13 | Paragraph border/fill: `hh:border borderFillIDRef offsetLeft..offsetBottom connect`; offsets in hu, NOT doubled (2 mm = 566). | S:paraborder |
| H14 | A new paragraph copies the border of the paragraph before it (Hangul editing). In XML each paragraph names its own paraPr, so only the builder decides this. | S:gongmun (COM), RT:gongmun |
| H15 | borderFill child order: slash, backSlash, leftBorder, rightBorder, topBorder, bottomBorder, diagonal, then `hc:fillBrush/hc:winBrush faceColor hatchColor alpha` (only when filled). | P:cell_fill, cell_diagonal |
| H16 | Line width is a string from a fixed list with a space: `0.1 mm`, `0.12 mm`, `0.15 mm`, `0.2 mm`, `0.25 mm`, `0.3 mm`, `0.4 mm`, `0.5 mm`, `0.6 mm`, `0.7 mm`, `1.0 mm`, `1.5 mm`, `2.0 mm`, `3.0 mm`, `4.0 mm`, `5.0 mm`. `0.4mm` (no space): Hangul opens the file but draws another width. | P:cell_border_width; F:F04 (4.62) |
| H17 | Line types: NONE, SOLID, DOT, DASH, DASH_DOT, DASH_DOT_DOT, LONG_DASH, CIRCLE, DOUBLE_SLIM, SLIM_THICK, THICK_SLIM, SLIM_THICK_SLIM. An unknown type: drawn as another type. Model: 18 types, the 12 above plus WAVE, DOUBLEWAVE, THICK3D, THICKREV3D, 3D, REV3D (these six are not rendered in the corpus yet). | P:cell_border_type; S:table_form (DOUBLE_SLIM); F:F05 |
| H18 | A NONE side keeps its width and colour, and Hangul uses them where the next side meets it (corner length). Keep them in a round trip. | RT:paraborder (0.09 -> 0.00 after the fix) |
| H19 | Diagonal lines: `hh:slash type="CENTER"` (/), `hh:backSlash type="CENTER"` (\), line style in `hh:diagonal`. Model: `type` NONE, CENTER, CENTER_BELOW, CENTER_ABOVE, ALL (+ `isCrooked`, `isCounter`). | P:cell_diagonal; S:table_form |
| H20 | Bullets: `hh:bullet id char useImage="0"` + one `hh:paraHead level="0"`; paragraph `hh:heading type="BULLET" idRef level`. Numbering: `hh:numbering` with 10 `hh:paraHead level="1".."10"` (1-based), text `^1.` (`^N` = number of level N), `numFormat` DIGIT, HANGUL_SYLLABLE, CIRCLED_DIGIT ...; paragraph `hh:heading type="NUMBER" idRef level` (0-based). | P:bullet_add, number_add; RT:numbering |
| H21 | A paraPr can hold a second `hp:switch` for the heading (namespace `.../2016/paragraph`, OUTLINE levels 8-10). Read both switches. | S:blank (paraPr 16-18) |

| H22 | More charPr: `hh:relSz` (상대 크기 %) and `hh:offset` (글자 위치 %) per language; `hh:underline type="BOTTOM|TOP|CENTER" shape=<line type> color`; `hh:strikeout shape color`; `hh:outline type="SOLID"` (외곽선); `hh:shadow type="DROP|CONTINUOUS" color offsetX offsetY` (%); empty `hh:emboss`, `hh:engrave`, `hh:supscript`, `hh:subscript` after `hh:shadow` (in this order); attributes `symMark` (강조점, e.g. DOT_ABOVE), `useKerning`, `useFontSpace`, `shadeColor`. | P:char_relsz, char_offset, char_underline_pos/shape/color, char_strike_shape/color, char_outline, char_shadow, char_emboss, char_engrave, char_super, char_sub, char_emphasis, char_kerning, char_fontspace, char_shade |
| H23 | 글자 테두리/배경: charPr `borderFillIDRef` to a borderFill with sides/fill (2 = none). | P:char_border |
| H24 | More paraPr: `hh:align vertical="BASELINE|TOP|CENTER|BOTTOM"` (줄 안 세로 정렬); `condense` (공백 최소값 %); `snapToGrid`; `breakLatinWord="KEEP_WORD|HYPHENATION|BREAK_WORD"`; `hh:autoSpacing eAsianEng eAsianNum`; `hh:heading type="OUTLINE" idRef="0" level` (개요 level, numbers from the section's outline shape). BETWEEN_LINES and AT_LEAST values are hu, doubled in `hp:default`. Corpus only: Hangul 2024 writes `textDir` on every `hh:paraPr`; the 2023 model has no such attribute. | P:para_valign, para_condense, para_snap, para_break_latin, para_autospace, para_outline, para_line_between, para_line_atleast, para_align_distribute, para_align_divide, para_widow, para_keep_lines, para_page_break_before |

## 3. Section (`Contents/sectionN.xml`)

| id | rule | evidence |
|---|---|---|
| S01 | The first paragraph's first run holds `hp:secPr` and `hp:ctrl/hp:colPr`. Without secPr Hangul opens the file with its default page setup. | S:blank; F:F10 (56.08) |
| S02 | That first run uses the same charPr as the paragraph's first text run. A bigger charPr there makes the first line taller (all lines move down ~2 px at 96 dpi). | RT:sincheongseo, gongmun_tongji (fixed) |
| S03 | `hp:pagePr width height` are always the portrait size; landscape = `landscape="NARROWLY"`, portrait = `WIDELY`. | P:page_landscape |
| S04 | Hangul's A4 in a new document is 59528 x 84186 hu. COM `MiliToHwpUnit(210/297)` gives 59527 x 84189. A page width 1 hu different moves centred and justified text by a sub-pixel (glyphs change at the edges). Copy exact values. Model: its default page is 59528 x 84188 (A4 rounded: 297 mm = 84188.2 hu), a third value next to Hangul's 84186 and COM's 84189; keep 84186 for a file that must match a Hangul 2024 file. | S:blank; RT:gongmun_sihaeng (0.70 -> 0.03) |
| S05 | `hp:margin header footer gutter left right top bottom` in hu. The body starts at top + header from the paper top; the footer is inside the bottom margin. | P:page_margin_left, page_header_len; M: first text line at 35.2 mm for top 20 + header 15 |
| S06 | Columns: `hp:colPr type="NEWSPAPER|BALANCED_NEWSPAPER" colCount sameSz sameGap`; separator `<hp:colLine type width color/>` inside colPr. Model: `colPr layout` = LEFT, RIGHT, MIRROR; child `hp:colSz` for unequal widths. | P:columns_two; S:columns2 |
| S07 | Header/footer: `hp:ctrl/hp:header` (or `hp:footer`) `applyPageType="BOTH|EVEN|ODD"` + `hp:subList textWidth (body width) textHeight (header length)`. It can be in any paragraph (it applies from that page on). | P:header_add, footer_add; S:tabs_fields |
| S08 | Page number: `hp:ctrl/hp:pageNum pos="BOTTOM_CENTER|TOP_RIGHT|..." formatType="DIGIT" sideChar="-"` (`- 1 -`). | P:page_number, page_number_pos |
| S09 | Footnote: in the text run, `hp:ctrl/hp:footNote number suffixChar="41" instId` + subList; the note paragraph starts with a run that holds `hp:ctrl/hp:autoNum numType="FOOTNOTE"`, in the SAME charPr as the note text; Hangul puts one space before the note text. | P:footnote_add; RT:footnote_doc |
| S10 | A run is a sequence of `hp:t`, `hp:ctrl`, `hp:tbl`, `hp:pic` ... in document order. Text, then a control, then more text can be one run. | S:footnote_doc |
| S11 | Tab: `<hp:tab width="0" leader="0" type="0"/>` inside `hp:t`. | S:tabs_fields |
| S12 | Page break: `hp:p pageBreak="1"`; column break: `columnBreak="1"`. Section break = a new section file. | P:page_break; S:sections |
| S13 | Hyperlink: run with `hp:ctrl/hp:fieldBegin type="HYPERLINK" fieldid="627600491"` + `hp:parameters` (Command `http\://...;1;0;0;`, Path, Category HWPHYPERLINK_TYPE_URL, TargetType, DocOpenType), run(s) with the link text (Hangul gives them a blue underlined charPr), run with `hp:ctrl/hp:fieldEnd beginIDRef fieldid`. Hangul makes this by itself when the user types a web address. | S:gongmun (auto), RT:gongmun |
| S14 | An empty paragraph keeps one run with no children (`<hp:run charPrIDRef="N"/>`); its charPr sets the height of the empty line. | S:blank, RT:all |
| S15 | Page border/fill: secPr `hp:pageBorderFill type="BOTH" borderFillIDRef textBorder="PAPER|CONTENT" headerInside footerInside fillArea="PAPER|PAGE|BORDER"` + `hp:offset` (hu, default 1417 = 5 mm). EVEN and ODD entries stay at borderFill 1. Model: `textBorder` is CONTENT or PAPER; `PAGE` belongs to `fillArea` (this row said `PAPER|PAGE` before 2026-11-14 and spec `text_border: page` wrote it; the corpus has only `PAPER`). | P:page_border |
| S16 | Gutter: `hp:margin gutter` (hu). Model: `hp:pagePr gutterType` = LEFT_ONLY, LEFT_RIGHT, TOP_BOTTOM. | P:page_gutter |
| S17 | Page number format `formatType` DIGIT, ROMAN_CAPITAL, ...; 새 번호로 시작 = run `hp:ctrl/hp:newNum num numType="PAGE"`. | P:page_num_format, page_num_start |
| S18 | Column types: `hp:colPr type="NEWSPAPER|BALANCED_NEWSPAPER|PARALLEL"`. | P:columns_type |
| S19 | Endnote: `hp:ctrl/hp:endNote` with the same structure as S09 (`autoNum numType="ENDNOTE"`). | P:endnote_add |
| S20 | 형광펜 (highlight) is not a char shape: `<hp:t><hp:markpenBegin color="#FFFF00"/>text<hp:markpenEnd/></hp:t>`. | P:char_markpen |
| S21 | Equation: run `hp:equation ... version="Equation Version 60" baseLine baseUnit (hu) font="HancomEQN"` + sz + pos (treatAsChar=1) + outMargin 56/56/0/0 + shapeComment + `hp:script` (Hangul equation script, e.g. `a over b`). Hangul makes the size again. | P:equation_add |
| S22 | Bookmark: run `hp:ctrl/hp:bookmark name`. | P:bookmark_add |
| S23 | 누름틀 (click-here field): run with `hp:fieldBegin type="CLICK_HERE" name editable="1" fieldid="627272811"` + parameters Prop=9, Command `Clickhere:set:<len(body)>:<body> ` with body `Direction:wstring:<n>:<guide> HelpState:wstring:<n>:<memo> `, Direction, HelpState; run with the guide text; run with `hp:fieldEnd`. A Hangul-made file whose caret (`settings.xml`) is in the field does not print the guide text; with the caret elsewhere, Hangul and the builder print it the same (ink 0.00; fields/rules.md X06, coverage C7.09 closed). | P:field_add; RT:field_add (81 %) |
| S24 | Date code: `fieldBegin type="SUMMERY"` (sic) + Command `$createtime` + the date text + fieldEnd. Memo: `fieldBegin type="MEMO"` with a subList. 글자 겹치기: run `hp:compose circleType composeType composeText` + 10 `hp:charPr prIDRef` (4294967295 = none). The builder keeps these as raw XML (`{"xml": ...}`). | P:datecode_add, memo_add, compose_add; RT (0.00) |
| S25 | Drawing objects (`hp:rect`, `hp:ellipse`, `hp:line`): offset, orgSz, curSz (0 0 = not resized), flip, rotationInfo, renderingInfo, `hp:lineShape color width (hu) style headStyle tailStyle ...`, `hc:fillBrush`, `hp:shadow`, optional `hp:drawText` (subList + textMargin) = text box, geometry (`hc:pt0..pt3` rect, `hc:center/ax1/ax2/...` ellipse, `hc:startPt/endPt` line), sz, pos, outMargin, shapeComment. Rect `ratio` = corner rounding %. The run that holds them ends with `<hp:t/>`. Hangul keeps hand-written objects in this form when it saves again. | S:shapes_rt (resave of a hand-written file); RT:shapes_rt (0.00) |
| S26 | A block table or floating picture (`hp:pos treatAsChar="0"`) is a run of the paragraph it is anchored to, and that paragraph can also hold text. Spec: the reader gives the object as its own block before the text block and marks it `"same_para": true`; the builder writes such a block's run into the next paragraph (before its text), so the round trip keeps one paragraph. `textWrap` -> `wrap`; `textFlow` (BOTH_SIDES, LEFT_ONLY, RIGHT_ONLY, LARGEST_ONLY: on which side of a square-wrapped object the text goes) -> `side` in lower case, given only when it is not BOTH_SIDES (tables, pictures, rect / ellipse / line). | P:table_pos_resaved_square (an anchor paragraph of its own); builder round trip self-test; the preview uses both (preview rules P16) |

## 4. Tables (`hp:tbl`)

| id | rule | evidence |
|---|---|---|
| T01 | `hp:tbl rowCnt colCnt cellSpacing borderFillIDRef pageBreak="CELL" repeatHeader textWrap="TOP_AND_BOTTOM"` + `hp:sz` (width = sum of columns, height = sum of rows) + `hp:pos` + `hp:outMargin` + `hp:inMargin` + `hp:tr`*. The run that holds the table ends with `<hp:t/>`. | S:hoeuirok |
| T02 | `hp:cellSz width height` is the OUTER cell size (border to border), cell margins included. COM `TableCreate` ColWidth/RowHeight take the INNER size; Hangul adds 1020 hu (2 x 510) to the width and 282 hu to the height. | P:col_width, row_height (before and after the corpus fix); M: table 170 mm wide = text area |
| T03 | Merged cells: the top-left cell has `hp:cellSpan colSpan rowSpan` and the summed `cellSz`; the covered cells are NOT written. `hp:cellAddr colAddr rowAddr` = grid position. | P:merge_cols, merge_rows; S:hoeuirok, table_form |
| T04 | `rowCnt` that does not match the `hp:tr` count, or an empty `hp:tr`: Hangul does not open the file. A colSpan past the last column: Hangul opens a damaged table. | F:F06, F18 (FAIL); F:F08 (88.64, 2 pages) |
| T05 | A cell with no `hp:cellSz`: Hangul opens it and makes the size again. | F:F07 (0.00) |
| T06 | Cell margins: table `hp:inMargin` (default 510, 510, 141, 141 hu = 1.8, 1.8, 0.5, 0.5 mm); a cell with its own margins has `hasMargin="1"` and `hp:cellMargin`. Model: a missing margin attribute is 0; 510/141 is what Hangul writes for a new table. | S:hoeuirok |
| T07 | Table outer margin `hp:outMargin` default 283 hu (1 mm) on all sides: a block table starts 1 mm right of the text area. Model: a missing `hp:outMargin` value is 0; 283 is what Hangul writes. | M: table left edge at 20.6 mm with left margin 20 mm (96 dpi) |
| T08 | Cell vertical align: `hp:subList vertAlign="TOP|CENTER|BOTTOM"` (default CENTER). Horizontal align is the paragraph align of the cell text. Model: the same three values, but its default for an absent attribute is TOP; Hangul writes CENTER for a new table, so write the value. | P:cell_valign, cell_halign |
| T09 | Each cell has its own borderFill with 4 sides. A table outline gives the edge cells borderFills with thick outer sides. Two cells on one grid line can have different sides; Hangul draws both (the stronger one shows). | P:table_outline |
| T10 | `hp:pos treatAsChar="1"` = table in the text line (moves like a character, cannot split over pages); `0` = block table (`vertRelTo="PARA" horzRelTo="COLUMN"`, `horzAlign` LEFT/CENTER/RIGHT). | P:table_treat_as_char; S:gongmun_gyeoljae |
| T11 | COM: a table created in a paragraph that already has text becomes treatAsChar=0 in its own paragraph. Create inline tables in an empty paragraph. In XML (builder) any paragraph can hold an inline table. | S:gongmun_tongji |
| T12 | Cell paragraphs take only the char style of the table's paragraph, not its spacing or indents. | RT:sincheongseo (builder fix) |
| T13 | `hp:tbl pageBreak="CELL|TABLE|NONE"`, `repeatHeader="1|0"`; header rows have `hp:tc header="1"`. Table cell margins of the whole table = `hp:inMargin`; one-sided outer margin = `hp:outMargin left`. | P:table_pagebreak, table_repeat_header, table_cellmargin, table_outmargin |
| T14 | Split cells and nested tables need no special XML: a split gives a finer grid with spans; a nested table is a `hp:tbl` in a cell paragraph. | P:table_split, table_nested; RT (0.00) |
| T15 | COM `TableCreate` with TableProperties set writes `hp:sz width="0" height="0"`; Hangul accepts it. | P:table_pagebreak (A) |

## 5. Pictures (`hp:pic`)

| id | rule | evidence |
|---|---|---|
| G01 | `hp:pic` children: offset, orgSz, curSz, flip, rotationInfo, renderingInfo (3 identity matrices), `hc:img binaryItemIDRef`, imgRect (4 points), imgClip, inMargin, imgDim, effects, sz, pos, outMargin, shapeComment. COM `InsertPicture` makes `treatAsChar="1"`. | P:picture_add; RT:picture_doc |
| G02 | The builder writes orgSz = curSz = sz = the target size; Hangul draws the image in that box. | RT:picture_doc (0.00) |

## 6. Hangul rejects or repairs when ...

Not opened (Open returns False; in the UI a damaged-file message): K03 missing section in manifest, K06 XML not well-formed, T04 rowCnt mismatch or empty row.
Opened but changed: H04 missing ids, H16 width without space, H17 unknown line type, T04 colSpan past the end, S01 no secPr, K06 duplicate attribute.
Opened with no change: H03 itemCnt off by one, H09 no `hp:default`, K02 mimetype order/compression, T05 no cellSz, H06 any typeInfo, K07 no linesegarray.

## 6b. HTML (browser) look -> Hangul (measured with `hd measure` on Edge and Hangul pages of 7 HTML reports)

| id | rule | evidence |
|---|---|---|
| W01 | HTML shows a run of spaces as one space: collapse spaces, or the line is wider (date line 15 mm in HTML, 31 mm in Hangul). | W:report (before/after) |
| W02 | The browser uses the font's own space width: set `font_space` (useFontSpace="1"); with it the line widths match (docno line 20.3-84.2 vs 20.4-84.4 mm). | W:report |
| W03 | Hangul paragraph = before + lines x size x line% + after, text at the top of the line. CSS: neighbour margins overlap (the bigger counts), the line extra is split above and below the text. Use after = 0 and before_i = max(after_(i-1), before_i) + hl_i - hl_(i-1), hl = size x (line% - 100) / 2. | measured pitches: l0 lines 8.2 mm (Hangul) vs 7.48 mm (CSS) before the fix |
| W04 | In a table cell Hangul leaves out the line extra of the last line (one 10.5 pt line at 145 % + 3.5/3.5 pt padding = 6.2 mm); a CSS cell has padding + full line boxes + border. Write explicit row heights from the CSS model (header 8.0 vs 8.1 mm, rows 9.8 vs 9.8 mm after the fix). | W:report |
| W05 | Hangul places a block table at the top of its anchor paragraph and ignores that paragraph's "before"; the "before" of the paragraph after a tall table is also lost. Put these gaps in the table's outer margin (`margin` top/bottom). | summary box 3.7 mm too high, date line 0.6 mm under the box before the fix |
| W06 | A CSS border lies inside the cell box; Hangul draws it centred on the cell edge. For thick borders add half the width to the cell padding and to the row height. | title box 28.6 vs 28.9 mm after the fix |
| W07 | Edge prints with `--print-to-pdf` only outside the Bash sandbox (inside it Edge exits 0 and writes no file). A printed HTML page that is one long block has no top/bottom margin on page 2 and later: compare element sizes and gaps, not page breaks. | `hd render` html runs |
| W08 | Explicit row heights need the browser's line count of each cell. An estimate (Korean 1 em, other 0.55 em) is too high for Latin text and wide titles (title box 10 mm too high; rows too high, so the page breaks moved). Measure the real advance widths with GDI (`core/textfit.py`): rows then match within ~0.13 mm each and the page breaks match. | W:review report 16/16 pages, p13 same rows |
| W09 | CSS `word-break: keep-all` still breaks before an opening bracket after a Hangul letter ("30건 / (D1~D30)"); Hangul 어절 (BREAK_WORD) breaks only at spaces. One line can wrap differently; there is no Hangul setting for it. | W:review report p1 table row 1 |
| W10 | Hangul sets the break rule per paragraph, CSS per element (`td code { word-break: break-all }`). Use the rule of most of the paragraph's text (`text/html_css.py`). | W:review report: 3 lines -> 2 lines like Edge |
| W11 | An HTML page with `@page { margin: 0 }` and a padded `.page` box prints the padding only on the first page top and the last page bottom: Edge pages 2+ have no margins, so the HTML print has fewer pages. Keep the HWPX A4 margins; compare content, not page counts. | W:4 of 6 reports: HWPX +1 page |

## 7. Hangul COM (for making samples; not used by the builder)

| id | rule | evidence |
|---|---|---|
| C01 | Start a NEW hidden instance (`DispatchEx`), take its PID from `XHwpWindows.Item(0).WindowHandle`, never `GetActiveObject`, `Quit` at the end. | scripts/render/hwpcom.py |
| C02 | Hangul's file-access security prompt ("한글을 이용하여 위 파일에 접근하려는 시도...") can appear on Open, SaveAs and InsertPicture (seen for paths that existed before, and at random after many files). Scripts never click or answer it: during Open() the watchdog leaves it visible for the user ("모두 허용" once per batch, one Hangul per batch) and closes it (= deny) only after `prompt_wait` s with no answer; the batch then stops. hwpcom saves to a new unique temp path and copies. The prompt goes away only by the user's own setup: Hancom's official automation security module, opt-in (`HWPX_DOCS_SECURITY_MODULE`; the registry is only read; README "접근 허용 창 없애기"). The plugin never ships, downloads or registers the DLL and never writes the registry. | corpus runs; popup image in %TEMP%/hwpcom_popup_*.bmp; module test 2026-11-14 (orchestrator): RegisterModule True, no prompt, no window |
| C03 | `SaveAs` of an unmodified new document writes no file: type a character and delete it first. | S:blank |
| C04 | `CreatePageImage(path, page, dpi, 24, "bmp")` works; `"png"` writes no file. With the caret in a table cell it writes only the cell image: leave the table first. | corpus runs; test t4 |
| C05 | Parameter names: `HParaShape` LeftMargin/RightMargin/Indentation/PrevSpacing/NextSpacing take 2 x hu (H08). `HCellBorderFill`/`HBorderFill` left colour is `BorderCorlorLeft` (Hangul's spelling). `HwpLineType("Dash")` gives DOT in XML. Header/footer: `HSet.SetItem("HeaderFooterStyle", 0)`, `SetItem("HeaderFooterCtrlType", 0|1)`. MultiColumn needs `HSet.SetItem("ApplyClass", 832)` and `SetItem("ApplyTo", 6)`. | corpus/make_corpus.py; gen_py type library |
| C06 | Table cells: `TableCellBlock`, `TableCellBlockExtend`, `TableRightCell`, `TableLowerCell`, `TableColBegin`, `TableColPageUp`, `TableMergeCell`, `TableCellAlign<H><V>` (also sets the horizontal align). Cell position: `GetTableCellAddr(0|1)`, `KeyIndicator()`. `MovePos(3, 0, 0)` = end of document. | test t4; corpus/make_corpus.py |
| C07 | `DrawObjCreatorTextBox` waits for a mouse drag (no object); `InsertCtrl("gso", ...)` makes nothing. Text boxes and shapes come from XML written by hand and saved again by Hangul (`make_corpus.py resave`), see S25. | test t3; S:shapes_rt |
| C08 | Item names that differ from the action table: `HEqEdit.string` (lower case), `HBookMark.name`, `HHeaderFooter` items only through `HSet.SetItem`. No set `HTextArt` exists. `Dutmal`, gradient `FillAttr`, `TrackChange` and `ApplyPageType` gave no change. | corpus/make_corpus.py batch 2 |
| C09 | The hidden document window can become visible after some actions ("빈 문서 2 - 한글"); hwpcom hides it again. Closing it kills the COM server. | batch 2 run |
| C10 | A file saved by Hangul stores the caret position (settings.xml). If it is in a table cell, `CreatePageImage` writes only that cell: `hd render` moves the caret to the top first. | RT pairs (22 tables fixed) |
