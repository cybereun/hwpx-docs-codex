---
name: hwpx-from-image
description: Reproduce a form exactly from an image or a description as an HWPX — measure lines, grid and text bands in mm, write a fidelity checklist, build, render in Hangul, overlay and fix until no offset is over 0.5 mm. Use for 이 양식 그대로 만들어줘, 이미지 보고 한글 문서로, 서식 재현, HWP form from image.
---

# Form from an image

`hd` = `python "${skillRoot}/lib/hd.py"`. Full procedure, checklist template and lessons:
`${CLAUDE_SKILL_DIR}/references/image-to-hwpx.md`. Read it before you start.

Short form:
1. Save the target as PNG (`hd render topng target.jpg target.png`); find the paper size (default A4 portrait).
2. `hd measure target.png --page-mm 210` -> H/V lines, GRID, COLS/ROWS (table widths, heights), INK (margins),
   text bands. Font size from a line of N Korean characters L mm long: size_pt = L / N / 0.3528.
3. Copy the text exactly; new text by skill `ko-writing` (공문: gongmun-style).
4. Write the checklist (one row per visible element) BEFORE the spec; `hd check out.hwpx checklist.md` reads it.
5. `hd build form.json form.hwpx`, `hd check`, `hd render hwpx form.hwpx out/`, then
   `hd render side side.png target.png out/form_p1.png` and `hd img overlay ov.png target.png out/form_p1.png`.
   Fix the spec where red/blue pairs show an offset; repeat.
6. `hd readability form.hwpx`: report the findings to the user; do not change the target's look.
7. Give the user the HWPX and the side-by-side PNG.

Rules from tests: match glyph height first (font size), then line width with 자간/장평, never by smaller cell
margins; copy every visible line break; never add a fill that you cannot see; a gradient bar = its mean colour.
No per-form templates: every form uses the same spec primitives (`docs/spec.md`); an element with no spec key ->
closest primitives, or `hd read` an HWPX that has it (raw XML passes through), and note the gap.
