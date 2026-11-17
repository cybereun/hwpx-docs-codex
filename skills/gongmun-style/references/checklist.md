# checklist.md — final check of 공문 text

Go through the list in order after the draft is done. Fix each item, then read the whole text once more. The ids point to the rule files. This list checks the text only (words, sentences, notation); layout is for the HWPX skill.

## A. Reader and purpose
1. Who reads it: the 수신처 (several: the least expert one; citizens or 공개 구분 `공개`: the general public)? Ending style and kept words follow that (wording.md EN1-EN11, §7; phrases.md §0). Citizens: no noun endings (`~함`, `~바람`, `~할 것`, `있음`). No office-internal abbreviations.
2. Is the purpose in the first sentence (notice, request, reply, report)? Is the basis or related document given first when there is one (PH01-PH03)?
3. Does the title name the content and the kind of document (`… 협조 요청`, `… 알림`, `… 결과 보고`), with no foreign words and no stock word alone (`○○ 관련 건`) (PH35, PH36, PH113, PH114)?

## B. Facts
4. 6하 원칙: who, when, where, what, how, why are all there (G01).
5. Every number has its unit and scope: how many, of which rank, per team or in total, attendee or helper (G02).
6. Dates, times, amounts, names and document numbers are copied exactly from the source. Weekdays match the dates.
6a. Conditions and consequences are concrete: a date instead of `기한 내`, the real legal consequence instead of `불이익`, `엄벌` (PH123, PH124).

## C. Sentences
7. One or two facts per sentence; no paragraph-long sentence; split at `~인바`, `~하며,`, `~하여,` and link with `이에`, `이에 따라` (W03, PH20, PH109). No comma right after a connective ending (`-며,`, `-고,`, `-오니,`, `-하여,`) (PH108).
8. Subject and predicate match; joined parts are of the same kind; no needed part is dropped (G30-G35).
9. A notice and a request with their own details are separate sentences; one short `~하오니 … 바랍니다` link is fine (PH107).
10. Active voice; no needless passive or causative (`~에 의해`, `~되어지다`, `보여지다`, `~ 중에 있다`, `개선시키다`), no translation style (`~에 있어서`, `~을 필요로 하다`, `회의를 가졌다`), no stock forms (`~코자`, `~토록`, `~하는 바입니다`) (G45, W05-W08, T table, PH79-PH91, PH126-PH135).
10a. No double negation and no stacked hedges (`~하지 않을 수 없다`, `~이 바람직할 것으로 판단됨`) (G36, EN14).
11. Nouns are not stacked; particles and verbs are written (`태풍피해복구철저 -> 태풍 피해 철저히 복구`) (PH41, G44).

## D. Words
12. Hard Chinese-character words, Japanese-style words and foreign words are replaced (wording.md §3, §3b, §3c, §3d; G40-G43), in titles, headings and item labels too, and also when the user's request used them (`금번`, `익일`, `향후`, `송부`, `만전`, `요망`). Words marked "recommended" are optional.
12a. Core rule: a word stays when this reader understands it and no plain word says the same; if the reader may not understand it, a same-meaning plain word replaces it, or it stays with a gloss when none exists. Sense of the sentence decides multi-sense words. Roman letters only in parentheses. wording.md §7.
13. Abbreviations and Roman letters: Hangul first, original in parentheses at first use (G41, G18).
14. No overbearing words (`만전을 기할`, `철저를 기하여`, `확행`, `통보 바람`, `치하`, `영접`, `불가`, `엄금`, `-하라`) and no discriminatory words (wording.md EN12, §5-§6, G50-G53). Address words: the receiving office by name or `귀 기관`, your own office as `우리 기관` (PH111).
15. The reader's act and the office's act use the right word (`제출` vs `접수`, `신청` vs `접수`) (G32, PH26).

## E. Notation and spelling
16. Date `2026. 11. 14.`, weekday `2026. 11. 14.(토)`, time `14:00`, range `14:00~16:00`, money `금113,560원(금일십일만삼천오백육십원)` where a formal amount is needed, amounts for the public in 만 units (N02-N08, G46).
17. Label colon `일시: …`, but `수신`, `제목`, `붙임` take two spaces and no colon; quotes `“ ”` / `‘ ’`; `「 」` only for law names, event names in `‘ ’` (N08, G19, structure.md §5).
17a. No bold or emoji in the text; no invented facts (purpose, names, dates): use `○○` (G01).
18. Spacing: the G29 quick lists (`시`, `후`, `내`, `중`, `간`, `여부`, `관련`, `이상`, `등`, `및`, `데`, `바` are spaced; `-간` (period), `-경`, `-쯤`, `-여`, `제-`, `-하다`, `뿐` are attached); unit nouns spaced after 만/천/억/`-여` (`10만 톤`, `50여 명`), may attach after plain digits (`108명`) (G20-G29, N13).
19. Spelling: 두음 법칙, `-률/-율`, 사이시옷, loanword spelling, `알려 드립니다` (G10-G17).

## F. Tools (optional)
20. If Python is available, run `python scripts/check_gongmun.py <file>` from this skill's folder (add `--internal` for an internal report). Read each finding and check the meaning before you change a word.
21. If a Korean writing-style skill (for example `ko-writing`) is installed, apply its rules on empty praise, translation style, dead metaphor, hedges, English and emoji; ignore its findings on fixed 공문 endings, item symbols and short sentences.
