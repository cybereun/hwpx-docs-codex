# pagex coverage (rows of docs/coverage.md that this package owns)

Status 2026-11-14 after the Hangul window. **COM** = Hangul sample made by COM; **pair** = minimal-difference pair
(`fixtures/`, made by `hd pagex run`); **rule** = `rules.md`; **builder** = spec key + reader (`spec.md`); **verified** = Hangul
renders the built file like the Hangul-made one (`hd roundtrip`, ink difference 0.00); **preview** = drawn by the preview
(`preview/drawers/page_layout.py`), with the ink difference against the Hangul page image where one exists (sparse pages: the
number is high for a few glyphs).

| id | item | COM | pair | rule | builder | verified | preview |
|---|---|---|---|---|---|---|---|
| C4.12 | header/footer odd/even | yes (`p.type` 1 even, 2 odd) | pg_hf (3) | PX01 | `header_odd` `header_even` `footer_odd` `footer_even` + reader | RT 3 files 0.00 | drawn (hf_oddeven ink 36; text rows within 1 px) |
| C4.13 = C10.08 | master page (both, odd, even, last, optional) | yes: types 0-4, `MasterPageFront` | pg_master (7) | PX02, PX03 | `master_pages` + reader | RT 6 files + front 0.00 | drawn (master_three ink 10-12; com3 p3 2.8; com4 p1 5.6). Hangul behavior: `pageDuplicate` (겹침) cannot be set by COM: `MasterPageDuplicate` returns False with one and with two master pages and the file keeps `pageDuplicate="0"` (probe 2026-11-14, `masters_dup`); the builder writes `1` from the OWPML model, no Hangul file shows it |
| C4.16 | note format and separator line | yes (`HSecDef.FootnoteShape.*`) | pg_note (16) | PX08 | `note_shape` + reader | RT 16 files 0.00 | NOT drawn: the notes are drawn in `flow.py finish()` (fixed "n)" and a 50 mm line); it must read `sec['note_shape']` (rule PX08). Hand-off to the renderer owner |
| C4.17 = C10.05 | hide header/footer/page number on a page | yes (`HPageHiding.Fields` bits 1-32) | pg_hide (7) | PX04, PX09 | `hide_page` block, `hide_first`; reader raw / `hide_first` | RT 4 files 0.00 | drawn (hide_all page 2 = Hangul rows); the flow's own footer is 44 px too high and its page number 7 px (flow.py finding) |
| C10.01 | vertical writing | yes (`TextDirection=1`) | pg_sec (2) | PX05 | `text_direction`, `vertical_head` + reader | RT 2 files 0.00 | drawn by the preview (`preview/vertical.py`, renderer owner; lines within 0.3 mm) |
| C10.02 | line numbers | yes | pg_sec (3) | PX06 | `line_numbers` + reader | RT 3 files 0.00 | drawn (numbers within 1 px of Hangul). Open: restart 0/1/2 on several pages |
| C10.03 | columns change inside a page | yes (`BreakColDef` + `MultiColumn` ApplyTo 2) | S:cols_mid_S | PX10 | `columns_here` block; reader raw | RT cols_mid_S (two columns) 0.00 | drawn by the preview (renderer owner; Hangul starts the setting 1.8 mm lower) |
| C10.06 | manuscript paper | yes (`WongojiFormat`, `CharGrid`, `LineGrid`) | pg_sec, S:wonggoji_grid_S | PX07 | `manuscript`, `char_grid`, `line_grid` + reader | RT flag and wonggoji_grid_S 0.00 | text in cells not drawn (one line `PREVIEW NOT DRAWN manuscript grid`). Hangul behavior: its page image (`CreatePageImage`, `wonggoji_grid_S`) shows the characters spread over 8 mm cells and no grid line, so there is nothing more to draw |
| C10.07 | label | yes (`LabelTemplate`) | S:label_S | PX11 | table block + `page.margin` (no label key) | RT 0.00 | drawn (text of the first cell; cells have no border) |

Open: the preview note shape (C4.16). Hangul behavior, not a limit of this package: 겹침 (`pageDuplicate`) and the 원고지 grid lines (see the rows above).
