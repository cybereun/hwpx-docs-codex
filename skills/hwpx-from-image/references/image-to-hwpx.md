# Reproduce a form from an image (or from a description)

Goal: an HWPX that Hangul opens with no prompt and that looks the same as the target. There are no per-form
templates. Every form is made from the same primitives (paragraphs, tables, shapes, pictures; `spec.md`), with
values that you MEASURE. Work in this order and keep every file in one work folder.

## 1. Get the target

1. Save the target image in the work folder. If it is not PNG or BMP, convert it:
   `hd render topng target.jpg target.png` (WinRT; prints the image DPI if it has one).
2. Find the paper size. Default A4 portrait (210 x 297 mm). If the image is wider than high, it is landscape
   (297 mm wide). If the image shows only a part of a page, find the scale from a known length, or ask the user.
3. A description without an image: write the checklist (section 4) from the words, then skip to step 3.

## 2. Measure

Run `hd measure target.png --page-mm 210`. It prints:
- `H` and `V` line segments with position, extent and thickness in mm,
- `GRID` (distinct x and y positions of lines), `COLS` and `ROWS` (their differences = table column widths and
  row heights),
- `INK` (bounding box of all dark pixels = text area, gives the page margins).

Interpret:
- Table: vertical lines with the same y range + horizontal lines with the same x range. Columns = differences of
  the x positions; rows = differences of the y positions. A grid position with no line through it = a merged cell
  (`cs`, `rs`). Big title glyphs can show as short V segments: ignore segments that are inside a text line.
- Thickness t: 0.1-0.15 mm = `0.12mm`; ~0.3 = `0.3mm`; ~0.4-0.5 = `0.4mm`; ~0.7 = `0.7mm`; two thin parallel lines
  = `double`. At 96 dpi one pixel is 0.26 mm, so prefer a 200-300 dpi image for line widths.
- A line or box that is not part of a grid = a shape (`line`, `rect`) with its x, y.
- Left margin = INK left edge (minus 1 mm if the leftmost element is a table: Hangul's default table outer margin,
  rules.md T07). Top: the first text line top is at top margin + header length (rules.md S05).

Font size from the image (no tool needed): measure the length L (mm) of one line of N Korean characters at 100 %
장평 and 0 자간: size_pt = L / N / 0.3528. (A Korean character is 1 em wide.) Check with a second line.
Font family: serif (명조/바탕: 휴먼명조, 함초롬바탕, 바탕) or sans (고딕/돋움: 맑은 고딕, 함초롬돋움, 굴림, 돋움);
heavy display titles are often HY헤드라인M. Fill colours: read the pixel colour of a shaded cell (render/img.py load).

## 3. Write the text

Copy the text exactly as the target shows it (spaces in "금    원" and "(서명 또는 인)" included). New text that you
write: follow skill `ko-writing`; for 공문 also skill `gongmun-style` (item symbols 1. 가. 1) 가) (1) (가) ① ㉮,
"끝." cases, 붙임, date/time/money) and check it with
`python <plugin>/skills/gongmun-style/scripts/check_gongmun.py <text file>`. This skill does layout only.

## 4. Fidelity checklist (write it BEFORE you build)

One row per visible element. Columns: id | element | query | expected | check method. `hd check`
reads the query and expected columns (queries are explained in its header). Template:

```markdown
| id | element | query | expected | method |
|---|---|---|---|---|
| F01 | paper | page.size | "A4" | XML |
| F02 | left margin | page.margin.left | 20 | XML + INK |
| F03 | title size | text("보조금 교부 신청서").size | 18 | XML + L/N rule |
| F04 | title bold | text("보조금 교부 신청서").bold | true | XML + look |
| F05 | title centred | text("보조금 교부 신청서").align | center | XML |
| F06 | form table columns | table[0].cols | [22, 28, 50, 28, 42] | XML + `hd measure` COLS |
| F07 | form table rows | table[0].heights | [10, 10, 10, 10, 18, 12, 40] | XML + `hd measure` ROWS |
| F08 | outer line | table[0].rows[0][0].border.top | 0.4mm solid #000000 | XML + `hd measure` t |
| F09 | label shading | text("성명").cell.fill | #F2F2F2 | XML + pixel colour |
| F10 | merged label | text("신").cell.rs | 3 | XML |
| F11 | check boxes | text("☐ 개인").size | 10 | XML |
| F12 | signature line text | text("(서명 또는 인)").align | center | XML |
| F13 | number of tables | count(table) | 1 | XML |
| F14 | page image | - | overlay: no offset > 0.5 mm | render + render/img.py overlay |
```

## 5. Build, render, compare, fix

1. Write `form.json` (spec.md). Start from the measured numbers; do not round them to "nice" values.
2. `hd build form.json form.hwpx`
3. `hd check form.hwpx checklist.md` until every row is OK.
4. `hd render hwpx form.hwpx out/` (Hangul page images; "OPEN OK" = Hangul opened it. Hangul can first ask for file
   access: the user answers "모두 허용"; the scripts never answer it).
5. Compare with the target at the same width:
   `hd render side side.png target.png out/form_p1.png` and
   `hd img overlay ov.png target.png out/form_p1.png` (black = both, red = only target, blue = only yours). Also run `hd measure` on the render and compare the GRID
   numbers with the target's.
6. Fix the spec where the overlay shows red/blue pairs (an offset) and repeat 2-5. Typical causes: a wrong top or
   left margin, the table outer margin (1 mm), a wrong font size or font family, line spacing, a wrong row height.
7. Deliver `form.hwpx` and the side-by-side PNG.

## 5b. Lessons from form tests (a 공문 notice page and a terms table, both from images)

- Do not reduce cell padding or font size to make text fit. Match the glyph HEIGHT first (font size), then the
  line WIDTH with 자간 (`spacing`, e.g. -5) or 장평 (`ratio`). Keep Hangul's default cell margins (1.8 / 0.5 mm) unless the
  image shows otherwise. Text that touches cell borders looks wrong at once.
- Copy every visible line break inside cells and paragraphs. If the width cannot be matched exactly, write the break
  (`\n`) where the image shows it.
- Check the space OUTSIDE tables too: distance from headings/underlines to the table, box sizes, title offset.
  Use the table `margin` for space after a table (rules.md W05).
- `word_break: "word"` for text that wraps between words (Korean BREAK_WORD); `condense` changes where justified
  lines break (rules.md H12, H26). Hanging indent: first line at `left` (H25).
- Iterate with numbers: `hd measure` on the target and the render, compare row lines and text-band tops, convert
  each mm difference into the spacing that precedes it (1 mm = 2.83 pt).
- If the image is not saved as a file, measure by eye on the shown picture (page width in px = 210 mm) and say that
  the comparison is by eye.
- Colours: read them from pixels; never add a fill that you cannot see (a guessed grey on label cells
  was wrong in a test). A bar that is darker at its edges is a gradient: use the mean colour of its profile until gradient
  fills are supported (coverage C5.09), not the brightest pixel.

## 6. When the target has something that the spec has no key for

1. Make the closest look with primitives (a shape, a table cell, a picture of the element).
2. If the user can give an HWPX that contains the element, run `hd read` on it: unknown elements come out as
   raw OWPML (`{"xml": ...}`) that the builder writes back as given.
3. Record the gap in `coverage.md` (do not add a per-form rule).
