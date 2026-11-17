---
name: hwpx-page
description: Page setup in HWPX — paper size, landscape, margins, gutter, columns, header and footer, page numbers, page borders, sections with their own setup, page and column breaks. Use for 한글 쪽 설정, 여백, 가로 방향, 다단, 머리말/꼬리말, 쪽 번호.
---

# HWPX page

`hd` = `python "${skillRoot}/lib/hd.py"`. Spec: `${skillRoot}/docs/spec.md` section "Document";
rules S01-S08, S12, S15-S18 in `${skillRoot}/docs/rules.md`; status in `docs/coverage.md` C4, C10.

```json
{"page": {"size": "A4", "landscape": false,
          "margin": {"left": 20, "right": 20, "top": 20, "bottom": 15, "header": 15, "footer": 15, "gutter": 0}},
 "columns": {"count": 2, "gap": 8, "line": "0.12mm solid", "type": "newspaper|balanced|parallel"},
 "header": ["머리말"], "footer": {"blocks": ["꼬리말"], "apply": "both|even|odd"},
 "page_number": {"pos": "bottom_center", "format": "digit", "side": "-"},
 "page_border": {"border": "0.4mm solid", "offset": 5, "text_border": "paper|content"},
 "body": [...]}
```

- `size`: A4 (Hangul's own 59528 x 84186 hu), A3, A5, B4, B5, LETTER, LEGAL or `[width, height]` mm.
- The body starts at top margin + header length (S05): to put the first line at 30 mm with a 10 mm header, set
  top 20.
- Several setups (portrait then landscape): `{"sections": [{"page": ..., "body": [...]}, ...]}`.
- Page break: block `{"page_break": true}` or `"page_break": true` on a paragraph or table block; column break:
  `"column_break": true`. Keep headings with their text: `"keep_next": true`.
- 공문 margins (시행규칙 서식): top 30, bottom 15, left 20, right 15 mm (skill hwpx-gongmun).

More page keys (`docs/spec.md` "More keys of the feature packages" > "Page"; rules PX01- in
`${skillRoot}/lib/hwpx_docs/pagex/rules.md`):
- odd / even pages: `header_odd`, `header_even`, `footer_odd`, `footer_even`;
- 바탕쪽: `master_pages` (`[{"type": "both|even|odd|last|optional", "body": [...]}]`);
- vertical writing: `text_direction` (`vertical`, `vertical_all`), `vertical_head`;
- line numbers `line_numbers`; 원고지 `manuscript`, `char_grid`, `line_grid`; 주석 모양 `note_shape`;
- hide on the first page `hide_first`; blocks `hide_page` (hide header, page number ... on one page) and `columns_here`
  (change the columns inside a page); a label sheet is a table block with `page.margin`.
- After a fix of the page flow, skill hwpx-readability (`hd pagefit`) checks where the pages break (only on request).
