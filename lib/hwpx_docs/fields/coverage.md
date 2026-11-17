# Coverage rows of the fields package

Same columns as `docs/coverage.md`, plus the preview. State 2026-11-14 (one Hangul window). RT = Hangul-made or
Hangul-saved file -> spec -> build -> Hangul render, ink difference 0.00 (`hd roundtrip`).

| id | item | COM | sample / pair | rule | builder | reader | preview | verified | open |
|---|---|---|---|---|---|---|---|---|---|
| C7.03 | cross-reference | yes (`InsertCrossReference`, only `Command`) | S:xref_add | X01 | run item `{"xref": ...}` | raw OWPML (no loss) | none (Hangul fills in the number): written limit | RT:xref_add 0.00 | types other than the default (heading, figure, ...) and number/text content: need a Hangul sample made by hand |
| C7.07 | table of contents | no (`MakeContents` server exception) | S:toc_made (built by `toc`, saved by Hangul) | X04, X05 | block `{"toc": ...}` static entries, `pages: "auto"` | plain paragraphs | drawn (plain text and dotted tab) | RT:toc_made 0.00 | Hangul's own 차례 structure (styles, hyperlinks): needs a Hangul sample made by hand |
| C7.08 | index | yes (`IndexMark`, `MakeIndex`) | S:index_mark_add, S:index_made | X02, X03 | run item `{"index_mark": ...}`, block `{"index": ...}` | mark: raw OWPML; list: plain paragraphs | mark not printed; list drawn | RT:index_mark_add, RT:index_made 0.00 | |
| C7.09 | 누름틀 guide text | yes | P:field_add | X06 (S23) | `{"field": ...}` | yes | drawn (existing) | ink 0.00 with equal caret (was 81 %: caret in the field hides the guide) | none |
| C7.10 | form objects: check, radio, button, combo, list, edit, scroll | no (creators wait for a mouse drag); XML written by model names, Hangul saved it | S:form_objects | F01-F09 | run item `{"form": {...}}` | yes (raw when the spec cannot hold it) | drawn (all 7 types) | RT:form_objects 0.00; builder text = Hangul text | F08: several combo/list items, newline in edit, frame: need a Hangul sample made by hand |
| C7.10 fill | form objects filled | - | - | F09 | - | - | - | selftest; Hangul render of a filled file shows the new states (checked, unchecked, radio chosen, edit text) | `hd form fill`; `hd edit` itself is not changed (edit depends on core only) |
| C7.12 | track changes | no (see X07) | S:track_change (made by hand) | T01-T05 | run item `{"change": ...}`, hooks `run.change`, `doc.header` | core/read.py (`Refs.tracks`, `text_of`, `change`) | drawn (red underline/strike) | RT:track_change 0.00; built file 0.00 | accept/reject, change bar, wrap inside a long piece |
