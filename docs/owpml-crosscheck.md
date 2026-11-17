# rules.md checked against Hancom's OWPML model (M2.8)

Date: 2026-11-14. Source of the model: GitHub `hancom-io/hwpx-owpml-model` (Apache-2.0, last push 2023-10-24,
default branch `main`), read with `gh api` (293 class and base files; nothing is copied or shipped; only element
names, attribute names, enum values and defaults were compared). KS X 6101 itself: only the catalogue page is free
(e-나라표준인증, established 2011-12-30, revised 2015, 2018, 2024); the full text is behind a viewer, not read.
Hancom's format page lists HWP 5.0 / HWPML 3.0 documents, not the HWPX element tables.

How the model was read: each `Class/**/*.cpp` has `ReadAttribute` (attribute names, enum list per attribute) and
`InitMap` (child element names); `Class/enumdef.h` has the enum lists; `Document.cpp`, `Handler.cpp` and
`Base/NamespacePrefix.cpp` have the package parts, the `hp:switch` handling and the namespaces. The model is from
2023: it knows Hangul 2016-2022 features. It says nothing about layout results, Hangul behaviour on faulty files,
or measured sizes.

Status:
- **OK** = our names and values agree with the model (the model may list more values: the rule row got them).
- **DIFF** = a statement or a value disagrees. Both are kept in `rules.md` with the evidence of each.
- **NOT IN MODEL** = the model has nothing on it (behaviour, layout measurement, Hangul COM, HTML comparison).

Corpus against model (script over the 238 shipped fixtures, 2026-11-14): 0 element names outside the model,
0 enum values outside the model's lists, 1 attribute outside the model: `hh:paraPr textDir` (Hangul 2024 writes it
in every file; the 2023 model has no such attribute). The model's child-element lists are maps, not a serialization
order; element order stays corpus-based (H01, H15, G01).

## Result

OK 54, DIFF 6, NOT IN MODEL 37 (97 rows: K 8, H 26, S 25, T 15, G 2, W 11, C 10). DIFF rows: H17, S04, S15, T06,
T07, T08. A row marked "OK (... NOT IN MODEL)" counts as OK: its names agree and only a detail is outside the model.

Builder against model (own check, 2026-11-14): the same script over the 238 fixtures read and written again by
the builder (`read` -> `build`): 0 element names, 0 enum values outside the model; only `hh:paraPr textDir`. The
per-element attribute counts are in the second table below (taken from the draft of the session `[PC] HWPX 스킬`,
branch `claude/m2-main-session`, commit 073dbab, and re-counted here against the model).

## Table of rules

| rule | our statement | the model says | status |
|---|---|---|---|
| K01 | parts: mimetype, version.xml, header, sections, content.hpf, settings.xml, container.xml/.rdf, manifest.xml, PrvText | reads `mimetype`, `version.xml`, `META-INF/container.xml`, `META-INF/manifest.xml`; `settings.xml` = `ha:HWPApplicationSetting`, container.rdf = `rdf:Description`; no preview classes | OK (Preview parts NOT IN MODEL) |
| K02 | mimetype first and stored; also opens otherwise | finds `mimetype` by name in the ZIP directory (`FindZipItem`), so order does not matter | OK |
| K03 | every section in the manifest | sections are found through `opf:manifest` + `opf:spine` of content.hpf | OK |
| K04 | `Contents/sectionN.xml`, manifest item + `itemref`, `hh:head secCnt` | `hh:head` attributes `version`, `secCnt`; `opf:item` id/href/media-type; `opf:itemref` id/idref/linear | OK |
| K05 | `opf:item id media-type isEmbeded`; `hashkey` optional | `opf:item` has id, href, media-type, `isEmbeded` (same spelling); no `hashkey` | OK |
| K06 | XML must be well-formed | expat parser; no statement on faults | NOT IN MODEL |
| K07 | `hp:linesegarray` optional | `hp:p` children: `hp:run`, `hp:linesegarray`; `hp:lineseg` attributes textpos, vertpos, vertsize, textheight, baseline, spacing, horzpos, horzsize, flags | OK |
| K08 | start from a Hangul-made empty document | not a format fact | NOT IN MODEL |
| H01 | refList order: fontfaces, borderFills, charProperties, tabProperties, numberings, bullets, paraProperties, styles, memoProperties | `hh:refList` children in this order, then `hh:trackChanges`, `hh:trackChangeAuthors` | OK |
| H02 | ids: borderFill from 1; charPr/paraPr/tabPr from 0; Hangul renumbers | only the attribute `id`; no start values | NOT IN MODEL |
| H03 | `itemCnt` off by one is accepted | `hh:fontfaces` has `itemCnt`; no tolerance rule | NOT IN MODEL |
| H04 | missing id references: other formatting | attributes `charPrIDRef`, `borderFillIDRef`, `paraPrIDRef`, `styleIDRef` exist; no fault rule | NOT IN MODEL |
| H05 | 7 fontfaces and 7 fontRef languages; symbols use the SYMBOL font | `lang` = HANGUL/LATIN/HANJA/JAPANESE/OTHER/SYMBOL/USER; `hh:fontRef` hangul, latin, hanja, japanese, other, symbol, user; also `fontCnt`, `hh:font type` = REP/TTF/HFT | OK (symbol-font behaviour NOT IN MODEL) |
| H06 | `typeInfo` panose-like values; generic values render the same | `hh:typeInfo` familyType (FCAT_*), serifStyle, weight, proportion, contrast, strokeVariation, armStyle, letterform, midline, xHeight | OK |
| H07 | charPr height, textColor, shadeColor, ratio, spacing, relSz, offset, italic, bold, underline, strikeout | all present; `height` default 1000 (= 10 pt) in the constructor; `useFontSpace`, `useKerning`, `symMark`, `borderFillIDRef` too | OK |
| H08 | paraPr margins in `hp:switch`: case = real hu, default = 2 x | `hp:switch/case/default` handled in `Handler.cpp`: a `case` is taken when its `hp:required-namespace` is one the reader supports (HwpUnitChar 2016 is registered), else `default`; `hc:left/right/prev/next/intent` have `value` and `unit` = CHAR/HWPUNIT; the 2 x factor is not stated | OK (mechanism); 2 x NOT IN MODEL |
| H09 | a paraPr without `hp:default` opens | follows from H08: a reader that supports HwpUnitChar never needs `default`; a reader that does not would read no margin | OK |
| H10 | lineSpacing type PERCENT/FIXED/AT_LEAST/BETWEEN_LINES, value | same four types; plus attribute `unit` = CHAR/HWPUNIT (default HWPUNIT) | OK (`unit` added to the row) |
| H11 | align horizontal 6 values; `hc:intent` = hanging | `hh:align horizontal` = JUSTIFY/LEFT/RIGHT/CENTER/DISTRIBUTE/DISTRIBUTE_SPACE, `vertical` = BASELINE/TOP/CENTER/BOTTOM | OK |
| H12 | breakSetting: keepWithNext, keepLines, pageBreakBefore, widowOrphan, breakNonLatinWord; KEEP_WORD = 글자 단위 (render test) | same attributes; also `breakLatinWord` = KEEP_WORD/HYPHENATION/BREAK_WORD and `lineWrap` = BREAK/SQUEEZE/KEEP; `breakNonLatinWord` = KEEP_WORD/BREAK_WORD, default KEEP_WORD; the meaning of the names is not stated | OK (names); meaning only from the render test |
| H13 | `hh:border borderFillIDRef offset* connect` | same, plus `ignoreMargin`; offsets without units | OK |
| H14 | a new paragraph copies the border | Hangul editing behaviour | NOT IN MODEL |
| H15 | borderFill child order: slash, backSlash, left, right, top, bottom, diagonal, fillBrush | same order in the child map; attributes `threeD`, `shadow`, `centerLine` (NONE/VERTICAL/HORIZONTAL/CROSS), `breakCellSeparateLine` | OK |
| H16 | 16 width strings with a space | the same 16 strings, exactly | OK |
| H17 | 12 line types | 18 types: the 12 plus WAVE, DOUBLEWAVE, THICK3D, THICKREV3D, 3D, REV3D | DIFF (list was incomplete; row extended) |
| H18 | a NONE side keeps width and colour | each border has type, width, colour always; no rule | NOT IN MODEL |
| H19 | `hh:slash type="CENTER"`, `hh:backSlash` | `type` = NONE/CENTER/CENTER_BELOW/CENTER_ABOVE/ALL, plus `Crooked`/`isCrooked`, `isCounter` | OK (values added) |
| H20 | bullet: id char useImage; numbering: 10 paraHead; heading type + idRef + level | `hh:bullet` id, char, useImage, checkedChar; `hh:numbering` id, start; `hh:paraHead` level, align (LEFT/CENTER/RIGHT), useInstWidth, autoIndent, widthAdjust, textOffsetType (PERCENT/HWPUNIT), textOffset, numFormat, charPrIDRef, checkable; `hh:heading type` = NONE/OUTLINE/NUMBER/BULLET | OK (the count 10 and `^N` text NOT IN MODEL) |
| H21 | second `hp:switch` for the heading (namespace 2016/paragraph) | namespace `.../2016/paragraph` is registered as supported; `hh:heading` is a plain child of `hh:paraPr` | OK |
| H22 | more charPr items (relSz, offset, underline pos/shape/colour, outline, shadow, emboss, engrave, supscript, subscript, symMark) | all present; underline type NONE/BOTTOM/CENTER/TOP; outline type NONE/SOLID/DOT/THICK/DASH/DASH_DOT/DASH_DOT_DOT; shadow type NONE/DROP/CONTINUOUS with colour, offsetX, offsetY; symMark 13 values | OK |
| H23 | charPr `borderFillIDRef` | present | OK |
| H24 | paraPr valign, condense, snapToGrid, breakLatinWord, autoSpacing, outline heading, line types | present (`hh:autoSpacing eAsianEng eAsianNum`, `hh:paraPr` tabPrIDRef, condense, fontLineHeight, snapToGrid, suppressLineNumbers, checked); corpus also has `textDir` (not in the 2023 model) | OK |
| H25 | hanging indent: first line at left, others at left + abs(indent) | `hc:intent` value only | NOT IN MODEL |
| H26 | `condense` shrinks spaces | `condense` attribute exists (default 0) | OK |
| S01 | first run: `hp:secPr`, `hp:ctrl/hp:colPr` | `hp:run` children include `hp:secPr`, `hp:ctrl`; `hp:ctrl` children include `hp:colPr` | OK |
| S02 | first-run charPr = first text run charPr | layout effect | NOT IN MODEL |
| S03 | pagePr width/height portrait; landscape NARROWLY/WIDELY | `hp:pagePr landscape` = WIDELY/NARROWLY, `width`, `height`, `gutterType` | OK |
| S04 | A4 = 59528 x 84186 hu in Hangul 2024; COM gives 59527 x 84189 | constructor default 59528 x 84188 (A4 rounded: 210 mm = 59527.6, 297 mm = 84188.2) | DIFF (three heights; keep the corpus value 84186 for a file that must match Hangul; 84188 is the exact A4) |
| S05 | `hp:margin header footer gutter left right top bottom` in hu | same seven attributes; defaults header = footer = 4252 hu (15 mm), gutter 0 | OK (layout meaning NOT IN MODEL) |
| S06 | colPr type, colCount, sameSz, sameGap, colLine | `hp:colPr` type NEWSPAPER/BALANCED_NEWSPAPER/PARALLEL, `layout` LEFT/RIGHT/MIRROR, colCount, sameSz, sameGap; `hp:colLine` type/width/colour; child `hp:colSz` | OK (`layout`, `hp:colSz` added) |
| S07 | header/footer: applyPageType BOTH/EVEN/ODD, subList textWidth/textHeight | `hp:header`/`hp:footer` id, applyPageType BOTH/EVEN/ODD; `hp:subList` textWidth, textHeight, vertAlign, lineWrap, textDirection | OK |
| S08 | pageNum pos, formatType, sideChar | same; `pos` 11 values (NONE, TOP_LEFT ... INSIDE_BOTTOM); `formatType` 22 values | OK |
| S09 | footNote number, suffixChar, instId; `autoNum numType="FOOTNOTE"` | `hp:footNote` flag, number, userChar, prefixChar, suffixChar, instId; `hp:autoNum` num, numType = PAGE/FOOTNOTE/ENDNOTE/PICTURE/TABLE/EQUATION/TOTAL_PAGE | OK |
| S10 | a run is a sequence of t, ctrl, tbl, pic ... | `hp:run` children list (t, ctrl, tbl, pic, equation, line, rect, ellipse, compose, markpen, chart ...) | OK |
| S11 | `<hp:tab width leader type/>` in `hp:t` | `hp:tab` width, leader, type; `hp:t` children: tab, lineBreak, hypen, nbSpace, fwSpace, markpenBegin/End ... | OK |
| S12 | `hp:p pageBreak`, `columnBreak` | `hp:p` id, paraPrIDRef, styleIDRef, pageBreak, columnBreak, merged, paraTcId | OK |
| S13 | hyperlink: fieldBegin HYPERLINK + parameters + fieldEnd | `hp:fieldBegin` id, type (HYPERLINK among 36 values), name, editable, dirty, zorder, fieldid; `hp:fieldEnd` beginIDRef, fieldid; `hp:parameters`; parameter names/values (Command, Path, Category ...) are not listed | OK (parameter values NOT IN MODEL) |
| S14 | empty paragraph = one empty run | all run children are optional | NOT IN MODEL |
| S15 | `pageBorderFill textBorder="PAPER or PAGE"` | `textBorder` = CONTENT/PAPER; `fillArea` = PAPER/PAGE/BORDER; `type` BOTH/EVEN/ODD; `headerInside`, `footerInside`; `hp:offset` left/right/top/bottom | DIFF (PAGE is a `fillArea` value, not a `textBorder` value; row, spec.md and builder fixed) |
| S16 | gutter in `hp:margin gutter` | also `pagePr gutterType` = LEFT_ONLY/LEFT_RIGHT/TOP_BOTTOM | OK (`gutterType` added) |
| S17 | formatType DIGIT, ROMAN_CAPITAL; `newNum num numType="PAGE"` | same enums; `hp:startNum` pageStartsOn, page, pic, tbl, equation | OK |
| S18 | colPr type PARALLEL | listed | OK |
| S19 | endNote like footNote | `hp:endNote` same class as `hp:footNote` | OK |
| S20 | `markpenBegin color` / `markpenEnd` inside `hp:t` | both are children of `hp:t` and of `hp:run`; `markpenBegin color` | OK |
| S21 | equation: version, baseLine, baseUnit, font, script | `hp:equation` version, baseLine, textColor, baseUnit, lineMode (LINE/CHAR/NULL), font; child `hp:script` | OK |
| S22 | `hp:bookmark name` | present | OK |
| S23 | click-here field: CLICK_HERE, editable, fieldid, Command text | type CLICK_HERE listed; `editable`; Command string and Prop are parameter values, not listed | OK (parameter text NOT IN MODEL) |
| S24 | field types SUMMERY (sic), MEMO; compose | SUMMERY (same spelling), MEMO, DATE, DOC_DATE, PATH ... ; `hp:compose` circleType (CHAR/SHAPE_*), composeType (SPREAD/OVERLAP), charPrCnt, composeText, child `hp:charPr prIDRef`; 4294967295 = none is not stated | OK (value NOT IN MODEL) |
| S25 | drawing objects: lineShape, rect ratio, drawText, pt0-pt3, center/ax1/ax2, startPt/endPt | `hp:lineShape` colour, width, style, endCap, headStyle, tailStyle, headfill, tailfill, headSz, tailSz, outlineStyle, alpha; `hp:rect ratio`; `hp:drawText` lastWidth, name, editable + `hp:textMargin`, `hp:subList`; `hc:pt0-3`, `hc:center/ax1/ax2/start1/end1/start2/end2`, `hc:startPt/endPt` | OK |
| T01 | tbl rowCnt, colCnt, cellSpacing, borderFillIDRef, pageBreak, repeatHeader, textWrap; sz, pos, outMargin, inMargin, tr | same; also `noAdjust`; `textWrap` = SQUARE/TOP_AND_BOTTOM/BEHIND_TEXT/IN_FRONT_OF_TEXT; children also caption, shapeComment, cellzoneList, label | OK |
| T02 | `cellSz` = outer size; COM takes inner size | `hp:cellSz width height`; no inner/outer statement | NOT IN MODEL |
| T03 | merged cell: cellSpan, cellAddr; covered cells not written | `hp:cellSpan colSpan rowSpan`, `hp:cellAddr colAddr rowAddr` | OK |
| T04 | rowCnt mismatch or empty tr: not opened | no fault rule | NOT IN MODEL |
| T05 | a cell without cellSz opens | `hp:tc` children cellAddr, cellSpan, cellSz, cellMargin, subList; `cellSz` default 0 x 0 | OK |
| T06 | table inMargin default 510/510/141/141 hu | `hp:inMargin`, `hp:cellMargin` left/right/top/bottom, default 0 each; `hp:tc hasMargin` | DIFF (0 in the model, 510/141 is what Hangul writes for a new table; keep the Hangul values) |
| T07 | outMargin default 283 hu | `hp:outMargin` default 0 | DIFF (same; 283 is what Hangul writes) |
| T08 | cell `subList vertAlign` TOP/CENTER/BOTTOM, default CENTER | `vertAlign` = TOP/CENTER/BOTTOM, constructor default TOP | DIFF (Hangul writes CENTER for a new table cell; the model assumes TOP when the attribute is absent; both kept) |
| T09 | each cell has its own borderFill | `hp:tc borderFillIDRef` | OK |
| T10 | `hp:pos treatAsChar`, vertRelTo PARA, horzRelTo COLUMN, horzAlign | `hp:pos` treatAsChar, affectLSpacing, flowWithText, allowOverlap, holdAnchorAndSO, vertRelTo (PAPER/PAGE/PARA), horzRelTo (PAPER/PAGE/COLUMN/PARA), vertAlign, horzAlign (LEFT/CENTER/RIGHT/INSIDE/OUTSIDE), vertOffset, horzOffset | OK |
| T11 | COM table in a paragraph with text | COM behaviour | NOT IN MODEL |
| T12 | cell paragraphs take only the char style | builder fix | NOT IN MODEL |
| T13 | tbl pageBreak CELL/TABLE/NONE, repeatHeader, `tc header` | same | OK |
| T14 | nested table = `hp:tbl` in a cell paragraph | `hp:tc` > `hp:subList` > `hp:p` > `hp:run` > `hp:tbl` | OK |
| T15 | `hp:sz width="0" height="0"` accepted | `hp:sz` width, height (+ widthRelTo, heightRelTo, protect); no range | NOT IN MODEL |
| G01 | pic children: offset, orgSz, curSz, flip, rotationInfo, renderingInfo, `hc:img`, imgRect, imgClip, inMargin, imgDim, effects, sz, pos, outMargin, shapeComment | all are children of `hp:pic`; also lineShape, caption, parameterset, metaTag; attribute `reverse`; `hc:img` binaryItemIDRef, bright, contrast, effect (REAL_PIC/GRAY_SCALE/BLACK_WHITE), alpha | OK (order stays corpus-based) |
| G02 | builder writes orgSz = curSz = sz | sizes only as attributes | NOT IN MODEL |
| W01-W11 | browser (Edge) against Hangul measurements | not a format topic | NOT IN MODEL (11 rows) |
| C01-C10 | Hangul COM automation | not a format topic | NOT IN MODEL (10 rows) |

Rows that keep two answers (our evidence and the model):
- S04: `84186` (Hangul 2024 blank file, a page width/height 1 hu off moves centred text) against `84188` (model default
  and exact A4). Builder keeps copying the Hangul value (S04 evidence).
- T06, T07, T08: the model's constructor defaults are what a reader assumes when the attribute is absent; Hangul
  writes its own UI defaults into every new table (510/510/141/141, 283, CENTER). The builder writes the Hangul values.
- H17: the corpus has only the types it was asked for (12 of 18); the six more come from the model alone and are
  not rendered yet.
- H12: the model lists the names of the two break modes; only the render test (imagetest1) shows which name breaks
  where. Keep the corpus meaning.
- S15: no conflict with the corpus (all samples have `textBorder="PAPER"`); only our claim that `PAGE` is allowed
  has no support.

## Builder output against the model (attribute names)

Question: does the builder write an attribute name that the model does not know? Method of the draft (session
`[PC] HWPX 스킬`, commit 073dbab): build one document with every builder feature (char and para shapes, table with
merges and per-cell lines, text box, ellipse, line with arrow, picture, native chart, equation, footnote, link,
columns, header/footer, page number, page border), collect the attributes of each element in `section0.xml` and
`header.xml`, and compare them with the attributes of the model class and its base classes
(`AbstractShapeObjectType`, `AbstractShapeComponentType`, `AbstractDrawingObjectType`, `Core/marginAtt`). The
column "model has" was counted again here from the model (base classes included); "we write" is the draft's count.

| element | model class | model has | we write | not in the model |
|---|---|---|---|---|
| hp:p | Para/PType | 7 | 6 | 0 (`paraTcId` not written) |
| hp:run | Para/RunType | 3 | 1 | 0 (`charTcId`, `paraTcId` not written) |
| hp:tbl | Para/TableType + AbstractShapeObjectType | 14 | 14 | 0 |
| hp:tc, hp:cellAddr, hp:cellSpan, hp:cellSz | Para/tc, cellAddr, cellSpan, cellSz | 7, 2, 2, 2 | 7, 2, 2, 2 | 0 |
| hp:cellMargin, hp:outMargin | Para/cellMargin, outMargin + Core/marginAtt | 4, 4 | 4, 4 | 0 |
| hp:pic | Para/PictureType + shape bases | 11 | 11 | 0 |
| hp:rect, hp:ellipse, hp:line | RectangleType, EllipseType, LineType + drawing bases | 11, 13, 11 | 11, 13, 11 | 0 |
| hp:chart | Para/ChartType + AbstractShapeObjectType | 8 | 8 | 0 |
| hp:equation | Para/EquationType + AbstractShapeObjectType | 13 | 13 | 0 |
| hp:sz, hp:pos | Para/sz, ASOPos | 5, 11 | 5, 11 | 0 |
| hp:secPr, hp:pagePr, hp:colPr | SectionDefinitionType, pagePr, ColumnDefType | 10, 4, 6 | 10, 4, 6 | 0 |
| hh:charPr | Head/CharShapeType | 8 | 8 | 0 |
| hh:paraPr | Head/ParaShapeType | 7 | 8 | 1: `textDir` |
| hh:borderFill, hh:fontface | BorderFillType, FontfaceType | 5, 2 | 5, 2 | 0 |
| hh:font | Head/font | 5 | 4 | 0 (`binaryItemIDRef` not written) |

Result: every attribute name that the builder writes is in the model, except `hh:paraPr textDir`. Hangul 2024 writes
`textDir` on every paraPr (all 238 Hangul-saved files in `tests/fixtures`); the published model (2023) is older than
Hangul 2024's format. The builder keeps it (rule: follow what Hangul writes).

Correction to the draft: it said the model has 16 attributes on `hp:p`; the model has 7 (`id`, `paraPrIDRef`,
`styleIDRef`, `pageBreak`, `columnBreak`, `merged`, `paraTcId`). Attributes the builder does not write take Hangul's
defaults, as the round trips show; for `hp:p` that is one attribute, not ten.
