---
name: hwpx-text
description: Text in HWPX — fonts, sizes, 자간/장평, paragraph spacing, indents, line breaks, links, footnotes, fields, equations; Markdown or HTML to HWPX (presets, --fallback); readability check (RD01-RD12). Use for 마크다운/HTML을 한글 문서로, 글자 모양, 문단 모양, 가독성.
---

# HWPX text

`hd` = `python "${skillRoot}/lib/hd.py"`. Spec keys: `${skillRoot}/docs/spec.md` sections
"Runs", "Char props", "Para props".

## Markdown and HTML

- Markdown: `hd md in.md out.hwpx [--preset <name|file.json>] [--fallback] [--keep]` (default preset
  `report-gongmun`). Exit 2 with `UNMAPPED line <n>: ...` = the preset has no style for that element: add it to the
  preset MAP, or rerun with `--fallback` (nearest preset style -> core feature -> plain text; one `FALLBACK` line
  each). Presets, extending them, new presets from an HWPX or an image: `${CLAUDE_SKILL_DIR}/references/presets.md`.
- HTML of any design: `hd html in.html out.hwpx [--spec out.json]`. It computes the CSS like a browser in print mode
  (cascade, specificity, inheritance, @media print, @page) and lists what it does not use as `UNSUPPORTED`. Judge
  the result against the browser print: `hd render html in.html out/` (Edge; outside a sandbox).
- The other way: `hd text in.hwpx --md` gives Markdown of an HWPX (skill hwpx-edit).

## Readability

`hd readability <file.hwpx|spec.json> [--fix fixed.json]` prints `RDnn <where>: <problem>` and `READABILITY ...`.
- A reproduction (image, HTML, an existing form) keeps the target's look: report the findings, change nothing
  (`hd html` does this).
- A new document (Markdown, a description) gets the safe fixes: word break, line spacing, contrast, cell margins,
  keep-with-next headings, repeated table headers (`hd md` applies them unless `--keep`). Tell the user the advice
  items (gaps in justified lines, small text, long lines, heading spacing).

## More text keys (`docs/spec.md` "More keys of the feature packages": "Text and styles", "Fields and references")

- Tab stops `tabs` (`[{"pos": mm, "type": "left|right|center|decimal", "leader": "dot"}]`, `\t` in the text); Hangul's style
  list `named_styles` (document) + `style` (block, cell, run; `next`, `type: char`); drop cap `dropcap` (block); 덧말 and
  한자 병기 `dutmal` (run); picture bullet `bullet_image`; `latin_break`, `word_break`. Rules TS01- in
  `${skillRoot}/lib/hwpx_docs/textstyle/rules.md`.
- Fields: cross-reference `xref` (run), table of contents `toc` (block), index `index_mark` (run) + `index` (block), form
  objects `form` (run; `hd form list|fill`), track changes `change` (run), 누름틀 `field`. Rules F01- in
  `${skillRoot}/lib/hwpx_docs/fields/rules.md`.
- Equations `{"equation": "a over b"}` (run, Hangul equation script).

## Facts (`docs/rules.md` H, W)

- Korean line break names are inverted: `word_break: "word"` = 어절 (break at spaces), `"char"` = 글자 (Hangul's
  default). Text that wraps only between words needs `"word"`.
- Negative indent = hanging: the first line starts at `left`, the wrapped lines at `left + |indent|`.
- `condense` (공백 최소값) changes where justified lines break.
- Write all Korean text that you make (not copied text) by skill `ko-writing` if it is installed; 공문 text by skill
  gongmun-style. This skill does layout.
