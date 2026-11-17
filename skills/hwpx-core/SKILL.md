---
name: hwpx-core
description: Make, read and check HWPX (OWPML, KS X 6101) documents that 한컴오피스 한글 opens — JSON spec to HWPX builder, HWPX to spec reader, build-check loop, page renders. Use for 한글 문서/hwpx 만들기, hwp 파일, 한글 양식, reading or editing an HWPX as data. Other hwpx-* skills add text, tables, objects, page, forms from images, 공문.
---

# HWPX core

`hd` below = `python "${skillRoot}/lib/hd.py"` (Python 3.10+, standard library only).

Every document is made from the same primitives (page, paragraphs, runs, tables, shapes, pictures), written by one
builder from a JSON spec. There are no per-form templates in code. The XML forms come from files saved by Hangul
2024 and are checked by round trips. Spec format: `${skillRoot}/docs/spec.md`.

## Which skill

| input or task | skill |
|---|---|
| fonts, paragraph spacing, links, notes, Markdown or HTML input, readability | hwpx-text |
| tables (merges, lines, fills, sizes) | hwpx-table |
| boxes, lines, text boxes, pictures, charts | hwpx-objects |
| page size, margins, columns, header/footer, page numbers | hwpx-page |
| an image of a form, "make it the same as this" | hwpx-from-image |
| fill or change a received HWPX (keep its look), HWPX to text or Markdown | hwpx-edit |
| 공문 (기안문, 시행문), 개조식 보고서 | hwpx-gongmun (text rules: gongmun-style) |
| Hangul's file-access prompt, passwords | hwpx-security |
| "읽기 좋게", 쪽 넘김 줄이기, 표 안 끊기게, 쪽 꽉 차게 (only when asked) | hwpx-readability |

## Build and check (every time)

1. Write `spec.json` (`docs/spec.md`). Use measured values (mm, pt), not guesses. Repeated looks: `styles` + `class`.
2. `hd build spec.json out.hwpx` — it also prints the readability findings (`RDnn ...`, `READABILITY ...`).
3. A new document: apply the safe fixes (`hd readability spec.json --fix spec.json`, then build again) and tell
   the user the advice items. A reproduction: report the findings, change nothing (skill hwpx-text).
4. Windows + Hangul only: `hd render hwpx out.hwpx pages/` -> `OPEN OK <file> pages <n>` and `pages/out_p<N>.png`.
   Before it, tell the user in one line: how many files, and that Hangul may ask once for file access ("모두 허용").
5. Compare with the target (`hd render side`, `hd img overlay`), fix, repeat. Give the user the HWPX and a PNG.

Read an existing file: `hd read in.hwpx spec.json` (unknown elements come out as raw `{"xml": ...}` and are written
back as given). Change the JSON, then `hd build`. To change only the text of a received file, use skill hwpx-edit
instead: it keeps every other byte.

## Facts that matter most (`${skillRoot}/docs/rules.md`)

- Table `cols`/`heights` are outer cell sizes. A block table starts 1 mm right of the text area (outer margin):
  `"margin": 0` aligns it with the text.
- Body text starts at top margin + header length. Default page: A4, margins 20/20/20/15, header/footer 15 mm.
- Paragraph spacing is in pt; line spacing 160 % = 1.6 x font size per line.
- ○ □ ☐ ※ · are SYMBOL characters: `font` sets all 7 language fonts, so they follow it.
- Never answer Hangul's file-access prompt by code and never change Hangul security settings (skill hwpx-security).

## Files

- `docs/spec.md` (spec), `docs/rules.md` (XML rules + evidence), `docs/coverage.md` (every Hangul feature C1-C14;
  its builder column names the spec key of each feature), `docs/interfaces.md` (functions of each module). The keys of the
  feature packages (`master_pages`, `text_direction`, `dropcap`, `named_styles`, `toc`, `form`, `object` ...) are in
  `docs/spec.md` section "More keys of the feature packages"; each skill lists the keys of its area.
- `lib/hwpx_docs/` modules core, text, table, objects, page, edit, extract, render, check (a feature package registers
  its own commands and self-test: `docs/interfaces.md`); `hd selftest` runs every self-test and
  the 271 fixture round trips (`tests/fixtures`).
