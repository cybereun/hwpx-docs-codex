# pagex spec keys

Section keys (in a `sections` item; at the top of the spec they count for section 0, like `header`). Lengths in mm.

| key | value | XML |
|---|---|---|
| `header_odd`, `header_even`, `footer_odd`, `footer_even` | blocks, or `{"blocks": [...], "style": {...}}` | `hp:header` / `hp:footer` `applyPageType` ODD / EVEN |
| `master_pages` | list of `{"type": "both\|even\|odd\|last\|optional", "body": [blocks], "page": n, "duplicate": bool, "front": bool}` | `Contents/masterpageN.xml`, `hp:masterPage` in `hp:secPr` |
| `text_direction` | `"vertical"` / `"vertical_all"` / `"horizontal"`; with `vertical_head`: 1 | `hp:secPr textDirection`, `textVerticalWidthHead` |
| `line_numbers` | `{"count_by": 1, "distance": 10, "start": 1, "restart": 0}` | `hp:visibility showLineNumber`, `hp:lineNumberShape` |
| `manuscript`, `char_grid`, `line_grid` | `1`; grid cell sizes in mm | `hp:grid wonggojiFormat`, `charGrid`, `lineGrid` |
| `hide_first` | `{"header": true, "footer": true, "master_page": true, "page_number": true, "empty_line": true, "border": "hide_first", "fill": "hide_first"}` | `hp:visibility` |
| `note_shape` | `{"footnote": {...}, "endnote": {...}}`; keys `format` (DIGIT, CIRCLED_DIGIT ... lower case), `prefix`, `suffix`, `user_char`, `superscript`, `line` ("0.12mm solid #000000"), `line_length` (mm or `"default"` = Hangul's 5 cm; `"column"` is accepted as the same), `between`, `below`, `above` (mm), `numbering` (continuous, on_section, on_page), `start`, `place`, `beneath_text` | `hp:footNotePr` / `hp:endNotePr` |

Body blocks (a paragraph that also holds the control):

| key | value | XML |
|---|---|---|
| `hide_page` | list of `header, footer, master_page, border, fill, page_number`, or `true` (all); plus `"p"` text | `hp:pageHiding` |
| `columns_here` | `{"count": 2, "gap": 8, "line": "0.12mm solid", "type": "newspaper\|balanced\|parallel"}`; plus `"p"` text | `hp:colPr` (second one) |

The reader writes the same keys, except `hide_page` and `columns_here`: it keeps those controls as raw `{"xml": ...}` run items.
