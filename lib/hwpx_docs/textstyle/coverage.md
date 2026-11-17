# Coverage rows of the text style package

Columns as in `docs/coverage.md`; rule ids TS01- are in `rules.md`. Status 2026-11-14 (Hangul windows 1 and 2 done).

| id | item | COM | pair / sample | rule | builder | verified | note |
|---|---|---|---|---|---|---|---|
| C2.09 | line break unit | partial | P:para_break_latin, para_break_korean; S:latin_break (3 values) | H12, H24 | `latin_break`, `word_break` | RTP:para_break_latin; RT:latin_break 0.00 (word, hyphen, char differ in the render); M:form image test (Korean: BREAK_WORD = 어절) | |
| C2.10 | tabs (types, leaders) | yes (`TabDef.TabItem`, textstyle TS01) | P:tab_stop, tab_type_right/center/decimal, tab_leader_dot/solid/dash, tab_auto; S:tabs_custom, tabs_fields | S11; textstyle TS01-TS04 | `	` in text; `tabs` list or {stops, auto_left, auto_right} (`hh:tabPr`); reader | RT:17 files 0.00; preview draws stops and leaders | |
| C2.19 | picture bullets | partial: `HeadingType 3` + `Bullet.HasImage` makes the bullet, no image loads | S:picbullet_built (built, saved by Hangul) | textstyle TS22 | `bullet_image: file`; reader saves the image | RT:picbullet_built 0.00; preview draws the image | needs a Hangul-made image bullet only to double-check |
| C3.03 | user styles | no (`StyleAdd` makes none): built file saved by Hangul | S:styles_user | textstyle TS10-TS12, TS19 | `named_styles`, `style` (block, run); reader | RT:styles_user 0.00 | a run keeps no style reference |
| C3.04 | style links paragraph/char | = C3.03 | S:styles_user | textstyle TS10, TS19 | `next`, `type: char` | RT:styles_user 0.00 (next names and the CHAR style kept by Hangul) | |
| C7.04 | 덧말 | no (COM saves no text, TS14): built file saved by Hangul | S:dutmal_top, dutmal_bottom, dutmal_wide | textstyle TS14, TS15 | run item `{"dutmal": {main, sub, pos, size, align}}`; reader | RT:3 files 0.00; preview draws it | `option` values not explored |
| C8.07 | 한자, 한자 병기 | no effect of `InputHanja` (TS20); made by hand in Hangul (F9) | S:hanja_dialog (hand-made), hanja_forms (typed text) | textstyle TS20 | text; the 덧말 form = run item `dutmal` (C7.04) | RT:hanja_dialog, hanja_forms 0.00 | 3 text forms + 1 덧말 form recorded; the other 3 icon forms not saved |
| C8.08 | picture bullets | = C2.19 | | | | | |
| C9.01 | drop cap | yes (`DropCap`, `HDropCap`) | P:dropcap_two, dropcap_three, dropcap_margin; S:dropcap_frame, dropcap_built | textstyle TS17 | block `dropcap` {lines 2/3/margin, font, color, frame, fill, gap}; run item; reader | RT:7 files 0.00 | preview draws it approximately (TS21) |
| C9.05 | 스타일마당 | no action (`StyleTemplate` False); Hangul opens the 25 ko-KR templates | n/a: table of every template in `lib/hwpx_docs/textstyle/templates.md` | textstyle TS18 | n/a (record); `named_styles` writes such a set | M: 25 templates opened and read | |
