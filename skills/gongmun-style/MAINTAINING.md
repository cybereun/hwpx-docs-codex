# MAINTAINING.md — how to keep gongmun-style correct

Language of files: English (ASD-STE100) with Korean examples. Version history is at the end.

## 1. Scope
- In scope: the TEXT of Korean official documents: tone and endings, words, sentence patterns, grammar and spacing, notation inside the text (date, time, money, units, punctuation).
- Out of scope: layout (page, fonts, sizes, borders, block positions). That belongs to an HWPX layout skill. This skill only keeps the shared ids in `references/structure.md` and `references/levels.json`.
- Design decisions (2026-11-14): text only; the skill files do the work, and Python is optional help, not the product.

## 2. File map and id schemes
| File | Ids | Content |
|---|---|---|
| SKILL.md | – | procedure and the most-used rules (keep under about 1,800 tokens) |
| references/phrases.md | PH01-PH136 (with gaps) | patterns by document type and purpose, address words, stock phrases |
| references/wording.md | EN1-EN14, W01-W11, P001-P412, T003-T046, A001-A016, X001-X016 (all with gaps) | endings, principles, word tables, §7 replacement rule (when to keep a word) |
| references/grammar.md | G01-G53 | content, spelling, spacing, grammar, plain Korean, reader's side |
| references/notation.md | N01-N19 | notation |
| references/checklist.md | items 1-21 (with 6a, 10a, 12a, 17a) | final check |
| references/structure.md, levels.json | HEAD_*/BODY_*/TAIL_*, L1-L8, E1-E6, A1-A2 | shared contract with the HWPX layout skill: never rename |
| references/sources.md | S01-S23 | sources with license basis, pending checks |
| scripts/check_gongmun.py, scripts/test/ | – | optional checker and its samples |
| evals/ | – | test cases (prompt, case.yaml, graders) |
Never reuse or renumber an id. Add new ids after the last one. Removed ids leave a gap; list them in the version history (do not keep empty rows: every row must cite a free source).

## 3. How to add or change a rule
1. Critique first, then test, then apply. Ask who judges, what the rule misses, what it conflicts with; try it on 5-20 concrete cases (expected result vs. result of the rule); apply only the version that passes, and record the test in the rule's section.
2. Find a source that is free to reuse (§7 license rule). Prefer, in this order: statute or 시행규칙 (law.go.kr), the newest 행정업무운영 편람 (mois.go.kr), 고시 (한글 맞춤법), pages marked 공공누리 제1유형, older editions and the S11 list. Two sources when possible. If no free source states the rule, write it in this skill's own words and mark it "convention".
3. Add the source to `sources.md` (URL, title, publisher, date or edition, which rules use it).
4. Write the rule as one line with a wrong -> right example and the source id with section or page. If no source states it, write "convention".
5. Rules grow by principle, not by word. Never add a per-word exception list. If a new case is not covered, change the general rule (one sentence or one example).
6. If a rule conflicts with another file, fix both in the same change. Known overlaps: N13 and G22 (units), N12 and G19 (quotation marks), EN3 and G50 (endings).
7. If the rule changes a common pattern, update the short form in SKILL.md "Most-used rules".

## 4. How to add a word row (wording.md)
- Columns: id | term | replacement | group | check | source | note. Groups: ZH (Chinese-character word), JP (Japanese-style), FO (foreign), TR (translation style, all registers), TG (translation style or stock 공문 form, checked in 공문 text only), AU (overbearing), DS (discriminatory).
- Korean syllables merge with endings: a regex for a verb stem must list the merged forms (`보여[지진집져졌질]`, `[하한할함합했]`), or it misses `보여집니다`, `아니한`. Test each new row on a true sentence and on a sentence with the same letters in another meaning.
- `term` is plain text, or a Python regex after `re:`. Never put `|` in a cell (use `[...]`).
- Set `check` = Y only when the term has no common other meaning. Examples of N: `동조` (= agree), `적기` (= enemy plane), `정수` (= integer), `통보`, `소관` (common and context-dependent).
- The replacement cell may only hold words that pass the §7 rule (same meaning, not harder for the reader, same context). If an official list proposes a word that fails, write the passing alternative or "keep `<word>`" and put the official proposal in the note cell with "§7".
- After the change, run `python scripts/check_gongmun.py --selftest`. All samples must say `ok`. If a new row is a known false hit, add the false-hit sentence to `scripts/test/sample_edge.md`.

## 5. Periodic checks
| When | What |
|---|---|
| Before each release, and when law.go.kr is reachable | Do the pending checks in `sources.md` ("Pending verification"). |
| Every year, January | Look for a new 행정업무운영 편람 on mois.go.kr (the 2025 edition was posted 2026-01-02). Diff its §3 "공공언어 바로 쓰기 참고사항" word lists against wording.md §3b. |
| Every year | Check 국립국어원 "다듬은 말" and new public-language lists; add pairs that pass §7. |
| After a reviewer's correction | Critique and test it (§3 step 1); then add it as a general rule with the date; mark it convention unless an official source agrees. |

## 6. Tests
- Checker: `python scripts/check_gongmun.py --selftest` (4 samples: good, edge, bad, bad_end).
- Writing quality: the cases in `evals/` (skill-creator method, or `claude plugin eval . --allow-tools Write,Edit,Bash` from this folder). These are real model runs and cost tokens.

### Eval record
- Cases: `evals/cooperation-request-external`, `evals/citizen-notice-water`, `evals/internal-report-training` (22 graders).
- Iteration 1 (2026-11-14, Sonnet 5.5, 1 run each): with skill 79% pass, without 44% (+35 points); cost +12,700 tokens (+18%) and +6 s per run. Failures fixed afterwards: comma after a connective ending, `향후` left in a heading, `「 」` for an event name, colon after `수신`/`제목`, a guessed 수신 처리부서. A grader that required `홈페이지 -> 누리집` was replaced by an invented-facts check. Iteration 2 not run yet.

## 7. Open items
- License rule: cite only sources free to reuse (government works without a restriction mark, statutes and 고시, 공공누리 제1유형). Do not add rules or examples from 공공누리 제2-4유형 publications (for example the 국립국어원 guides S07-S09); see `sources.md`.
- Free sources that could restore some removed rows: the 2012 문체부 행정용어 순화어 874개 list (S21 attachments; a 고시, viewer shows images only), 법제처 「알기 쉬운 법령 정비기준」, 국립국어원 "다듬은 말" announcements published as 공공누리 제1유형 press releases.
- S11 1993 list (8,644 pairs, 4,101 "순화된 용어만 사용"): not imported as a whole; old and partly obsolete. v2.6 cites it only for pairs that this skill picked and checked (§3d). Automatic selection by frequency failed (homographs: `접수`, `평가`, `조제` matched other words), so pick by hand.
- No official numeric sentence-length limit and no official 개조식 ending list were found.

## 8. Version history
- 2026-11-14 v2.6 (rebuild from free sources): rules and patterns lost in v2.5 were written again in this skill's own words with new examples, based on S01 (§3 1.가.3) translation style, §3 3.가 overbearing words, §6 기안 rules), S05, S11, S22, S23 or marked convention. New: EN12-EN14; T017-T046 (translation style, needless causative, stock 공문 forms; T014 widened); A007-A016; G36 (double negation); PH102-PH136 (openings, opinion request, change, cancel, correction, linking, address words, refusal with appeal notice, titles, report lines, press release lead and quotes, notice order, conditions and consequences, stock phrases); word pairs P277-P390 picked one by one from this skill's own candidate list (§3d; S11 or S01 cited when it has the same pair or plain word). Miss check: the term list of the v2.5 removed rows was compared afterwards; a missed word was added only when a free pool also has it (P391-P393 from S01, P409 and P412 from S11, T046 from S01 §3 3.가.1)); 18 missed words with no free source and `장애우` were left out. Replacements are plain common words or the free source's word; no coined replacement found only in S07-S09 (`반짝 매장`, `예약 부도` removed for that reason). Tested: every new checked row on true and false sentences; selftest samples extended; no new finding on the 6 iteration-1 eval outputs. S22 and S23 (행정절차법 제26조, 행정심판법 제27조, 행정소송법 제20조) were checked against the current text on 국회법률정보시스템 on 2026-11-14 (law.go.kr was down for maintenance); PH112 now states the 90-day and outer limits. Counts: wording.md rows 242 -> 404 (162 added: 64 cite a free source, 98 convention); phrases.md 47 -> 82 (35 added: 16 free source, 19 convention); grammar.md +1 (G36); checked word rows 182 -> 336.
- 2026-11-14 v2.5 (license cleanup): rows that cited only 공공누리 제3-4유형 sources (S07-S09) were re-based on free sources (S01, S05, S10, S11, S13, S15, S21) and rewritten, or removed. Removed ids: W07; EN5, EN7, EN9, EN10; P063, P065, P067-P071, P074, P076, P084, P088, P201-P205, P207-P222, P224-P228, P230-P233, P240, P243, P250, P253, P256, P260, P262-P264, P269, P270, P272; T001, T002, T005-T009, T011-T013, T015, T016; A002, A004-A006; X017; PH04, PH05, PH15, PH17, PH21-PH25, PH31, PH37, PH44-PH49, PH54, PH56-PH59, PH64-PH70, PH76, PH78, PH80, PH83, PH84, PH89, PH92-PH95, PH97-PH100. New: PH19, PH101, S21. sources.md has a license column.
- 2026-11-14 v2.4: reader = 수신처 (several: least expert; citizens or 공개: general public; no sender-internal abbreviations). Keep a word when this reader understands it and no plain word says the same; else a same-meaning plain word, or keep with a gloss. Tested before use: first wording failed 7/14, 수신처-only failed 3/6, final rule passed 20/20 (wording.md §7). Publication check: absolute paths, private references and quotes removed.
- 2026-11-14 v2.3: per-word cautions folded into one general rule in wording.md §7; checker caution tagging removed; `프로젝트`, `리스크`, `인프라`, `모니터링`, `거버넌스`, `바우처`, `스타트업` kept.
- 2026-11-14 v2.2: replacement rule made required (meaning, not harder, context); about 50 replacement cells rewritten; `로그인`, `해커톤`, `토크 콘서트`, `보합세` kept.
- 2026-11-14 v2.1: `홈페이지 -> 누리집` optional; review of all replacements; `창업기획자` (S17) and `가사근로자` (S18) added.
- 2026-11-14 v2: text-writer rebuild: phrases.md, grammar.md, checklist.md, 2025 편람 word list (P101-P190), more word pairs (P201-P276), ending rules EN6-EN11, `알려 드립니다` spacing.
- 2026-11-14 v1.1: review; checker false hits fixed (12), selftest added.
- 2026-11-14 v1: first version (structure, notation, wording, sources, checker).
