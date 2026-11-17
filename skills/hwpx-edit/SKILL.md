---
name: hwpx-edit
description: Change an existing HWPX or .hwp without breaking it — list its slots (paragraphs, table cells, labels), fill a received form by label, tick check boxes, replace words, then check structure, page drift and leftover text; also HWPX to text or Markdown. Use for 받은 양식 채우기, 신청서 작성, 기존 한글 문서 수정, 문구 바꾸기, 한글 문서 텍스트 추출.
---

# Edit an existing HWPX or HWP

`hd` = `python "${skillRoot}/lib/hd.py"`. A received form keeps its look only if nothing but the text
changes. These commands change text only; every table, style, picture and ZIP entry stays as it is.

1. `hd slots form.hwpx` -> one line per slot: `p3` (body paragraph), `t1.r2c4` (table 1, row 2, column 4),
   `o2` (header/footer/note/text box), with `[label]` when a short cell names that slot (the empty cell to its right,
   or below).
2. Write `values.json` with slot keys or labels: `{"성명": "가람", "t1.r3c2": "000-0000-0000", "p5": "새 문단"}`.
   `\n` = next line.
3. `hd edit form.hwpx filled.hwpx --values values.json [--set KEY=TEXT] [--replace OLD=NEW] [--check 동의함]`.
   An unknown key or label stops with `UNMATCHED` (nothing written) unless `--allow-missing`. It prints the guard.
4. Guard (also alone): `hd guard form.hwpx filled.hwpx [--forbid 옛기관명] [--require 새기관명] [--max-unchanged 0.35]`
   - STRUCTURE: same paragraphs, tables, cell grid, objects, styles.
   - BUDGET: a changed paragraph or cell that needs more lines -> its row or the body grows (pages can move).
     Shorten the text, or tell the user.
   - RESIDUE: forbidden words, missing required words, placeholders (○○, {{..}}, XXX, ___), unchanged sentences.
5. Render (skill hwpx-core; tell the user first that Hangul may ask once for file access) and compare with the
   original page.

Rules: never rebuild a received form from scratch to change its text (the look changes); never edit inside text
boxes or charts with `--set` unless the user asks (they are `o` slots); the edited paragraphs lose their line layout
cache, which Hangul rebuilds; the preview picture is replaced with a blank one so no old text stays in the file.

A received .hwp (HWP 5.0, not HWPX): the same commands and steps with the file name changed, no Hangul unless you ask for `--backend hangul` — `hd slots form.hwp`,
`hd edit form.hwp filled.hwp --values values.json`, `hd guard form.hwp filled.hwp --render pages/`.
`hd edit` changes text only and keeps every other byte of the file. In a paragraph
with a 누름틀 the value goes inside the field. The guard also draws both files (`COMPARE PAGE n TEXT` = only text changed,
`FORM` = lines or boxes moved: the form changed; `pages/<name>_compare.html` shows where). Password, 배포용, DRM and
한글 97 files are refused. To add rows or paragraphs (`hd edit` never does): `hd hwp tohwpx f.hwp f.hwpx`, `hd read f.hwpx s.json`,
change the JSON, `hd build s.json out.hwp` (no Hangul; stops with `UNSUPPORTED <element>` only for an object or value the .hwp writer does not know).
`hd preview f.hwp out/` draws a .hwp with no Hangul, and so do `hd hwp compare` and `hd guard --render` unless
you give `--backend hangul` (Windows; Hangul then opens a safe copy with the scripts blanked and the linked pictures removed, and may ask once for file access).
A macro (script) of the received .hwp stays in the edited file; `hd edit f.hwp out.hwp ... --drop-scripts` blanks it (for a file you do not trust).
Form objects of a .hwp (check boxes, radio buttons, lists): `hd form list f.hwp` works; `hd form fill f.hwp out.hwp` writes through the same route
(`UNSUPPORTED <element>` only for an object or value that is not known).

Other tools:
- `hd text in.hwpx [--md] [-o out.md]` — text or Markdown (tables as Markdown tables, footnotes as [^n]).
- A whole new document in the same look: read it as a spec (`hd read`) or make a preset (skill hwpx-text).
- Form objects (check boxes, radio buttons, lists, edit boxes made with Hangul's 양식 개체): `hd form list in.hwpx`, then
  `hd form fill in.hwpx out.hwpx --set name=value [...]` (`hd edit` does not change them). Spec key `form`: `docs/spec.md`
  "Fields and references".
- Hide personal data in a received file before it goes out: `hd secure in.hwpx out.hwpx --mask-private` (skill hwpx-security).
