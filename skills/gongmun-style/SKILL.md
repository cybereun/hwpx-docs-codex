---
name: gongmun-style
description: 공문 글쓰기 규칙(어투·단어·문장·표기). 공문·기안문·시행문·회신·보고서·보도자료·안내문·공고문 문장 쓰기, 공문체·공문 어투, 개조식, 행정 용어 순화, 날짜·시간·금액 표기, 띄어쓰기. Use whenever Korean official text is written, checked or replied to in 공문 tone.
---

# gongmun-style — the text of Korean official documents

This skill writes the TEXT of a 공문: tone, words, sentences, and notation inside the text. Layout (page, fonts, boxes, block positions) belongs to the HWPX skill; it reads `references/structure.md` and `references/levels.json` from here.
Sources: 행정안전부 「2025 행정업무운영 편람」 (S01) and 2011 edition (S10), 「행정업무의 운영 및 혁신에 관한 규정」 and 시행규칙, 한글 맞춤법 (고시), 행정절차법·행정심판법 (appeal notice), 국가기록원 순화어 목록 (S11), 문체부 보도자료 (공공누리 제1유형). Only sources that are free to reuse are cited; every rule in `references/` cites a source id or says "convention" (this skill's own judgment).

## Procedure
1. **Reader and type.** The reader is the 수신처. Several 수신처: write for the least expert one. To citizens, or 공개 구분 `공개`: write for the general public. Never assume the 수신처 knows your office's own abbreviations. Also fix the type (기안문/시행문, 회신, 내부결재, 보고서, 보도 자료, 안내문/공고문). Reader and type set the ending style (`references/phrases.md` §0, `references/wording.md` EN1-EN11) and which words stay (step 4).
2. **Facts.** Collect who, when, where, what, how, why, numbers with units, the basis (law, related document). If a fact is missing, ask the user or leave `○○`; never invent a number, date, name, document number, recipient department or purpose.
3. **Draft with patterns.** Take the title, opening and request sentences from `references/phrases.md` for that type and purpose. One or two facts per sentence.
4. **Words and grammar.** Core rule: keep a word (loanword, Chinese-character word, field term) when this reader understands it and no plain word says the same; if the reader may not understand it, use a plain word of the same meaning, or keep it with a gloss at first use when none exists. Pick the word for the sense in the sentence. Not being native Korean is never a reason by itself; Roman letters only in parentheses after Hangul (`통합 인증(SSO)`). The tables in `references/wording.md` list candidates; its §7 explains the rule; fix grammar and spacing (`references/grammar.md`); write dates, times and amounts by `references/notation.md`. If a Korean writing-style skill (for example `ko-writing`) is installed, apply it too, except its rules that conflict with 공문 form (fixed endings, item symbols, short sentences).
5. **Check.** Go through `references/checklist.md` item by item. If Python is available, also run `python scripts/check_gongmun.py <file>` from this skill's folder (`--internal` for an internal report; `--register general` for a non-공문 file) and judge each finding by its meaning.

## Most-used rules
- **Endings by reader.** Other offices, companies, citizens: `~합니다`, `~바랍니다`, `~하시기 바랍니다`, `~해 주시기 바랍니다`, `~해 주십시오`, `~알려 드립니다`. Never `~바람`, `~요망`, `~할 것`, `있음`, `불가함`, `-하라`, `엄금` to them. One ending style per body. Internal 보고서/결재: 개조식 lines (`~함.`, `~임.`, noun phrase) with full particles. 보도 자료: plain `~다`. [EN1-EN14, PH50]
- **Opening.** Basis first: `관련: ○○부 ○○과-123(2026. 11. 3.)` or `「○○법」 제○조에 따라 …`. Then the purpose: `○○을 다음과 같이 알려 드립니다.` / `○○에 협조하여 주시기 바랍니다.` No basis: start with the act (`○○ 교육생을 다음과 같이 모집합니다.`). [PH01-PH19, PH102-PH106]
- **Title.** Content + kind: `○○ 행사 참석 협조 요청`, `2026년 ○○ 교육 계획 알림`, `○○ 결과 보고`; not `○○ 관련 건`. [PH35, PH36, PH113, PH114]
- **Stock phrases.** `만전을 기할 -> 최선을 다할`, `철저를 기하여 -> 철저히 하여`, `확행 바랍니다 -> 꼭 하시기 바랍니다`, `적의 조치 -> 적절한 조치`, `~에 의거하여 -> ~에 따라`, `시행코자 -> 시행하고자`, `통보 바람 -> 알려 주시기 바랍니다`, `엄수할 것 -> 꼭 지켜 주시기 바랍니다`, `~하지 않을 수 없습니다 -> ~해야 합니다`. [PH71-PH101, PH126-PH136]
- **Words.** `금일 -> 오늘`, `금번 -> 이번`, `상기 -> 위의`, `익일 -> 다음 날`, `송부 -> 보냄`, `감안 -> 고려`, `제고 -> 높임`, `용이 -> 쉬움`, `제반 -> 여러`, `향후 -> 앞으로`, `통보 -> 알림`, `가이드라인 -> 지침`, `우천 시 -> 비가 오면`, `매뉴얼 -> 설명서 / 업무 지침` (by context), `테스트 베드 -> 시험대`. Replace them in titles, headings and item labels too (`향후 계획 -> 추진 계획`), and also when the user's own request uses them. Kept with a gloss for citizens: `송달`; kept: `스타트업`, `로그인`, `홈페이지`, `세미나`. [wording.md §3-§3d, §7, G41]
- **Sentences.** Split at `~인바`, `~하며,`; link with `이에`. No comma right after a connective ending: `개최하며, 축제를 -> 개최하며 축제를`, `모집하오니, 재학생이 -> 모집하오니 재학생이`. Active voice, no `~에 의해`, `~에 있어서`, `~되어지다`, `보여지다`, `개선시키다`, `회의를 가졌다`. The reader `제출`s, the office `접수`s. [G30-G45, PH20, PH107-PH110, wording.md §4]
- **Notation.** `2026. 11. 14.(토)`, `14:00`, `14:00~16:00`, `일시: …`, `금113,560원(금일십일만삼천오백육십원)` for a formal amount, `2,134만 5천 원` for the public, `10만 톤`, `50여 명`, `총 28건`. Event and project names in `‘ ’` or no marks; `「 」` only for laws. Labels `수신`, `제목`, `붙임` take two spaces, no colon (`수신  내부결재`). [N02-N13, G19, G22, G46, structure.md §5]
- **Spacing.** Spaced: `계약 시`, `승인 후`, `기한 내`, `추진 중`, `기관 간`, `연체 여부`, `15세 이상`, `및`, `등`. Attached: `2개월간`, `20일경`, `제4장`, `재교육`, `것뿐`, `그동안`. [G20-G29]

## Tone only (chat replies, notices without layout)
When only the 공문 tone is wanted (for example in chat replies), apply the endings, words and sentence rules above. Do not add 수신, 제목, item symbols, 붙임 or `끝.`. Keep everyday notation (`오전 11시 40분` is fine). Example: `오늘 점심 메뉴를 다음과 같이 알려 드립니다. 메뉴는 김치찌개로 정하였습니다. 11시 40분까지 식당 앞에 모여 주시기 바랍니다.`

## References (stable file names)
- `references/phrases.md` — sentence patterns by document type and purpose, titles, address words, stock phrases (PH01-PH136).
- `references/wording.md` — ending rules (EN), word tables P (2025 편람 list, 1993 list S11, pairs selected by this skill), T (translation style, stock forms), A (overbearing), X (discriminatory).
- `references/grammar.md` — content rules, spelling, spacing, sentence grammar, plain Korean, reader's side (G01-G53).
- `references/notation.md` — date, time, money, numbers, units, punctuation (N01-N19).
- `references/checklist.md` — the final check, in order.
- `references/structure.md`, `references/levels.json` — block ids, item levels L1-L8, `끝.`/붙임 cases (shared with the HWPX skill; do not rename ids).
- `references/sources.md` — every source with URL, date and the rules from it.
- `scripts/check_gongmun.py` — optional checker; `--selftest` must say `ok` after any table change.
- `MAINTAINING.md` — how to update this skill.

## Limits
- Statutes were read from mirrors while `law.go.kr` was down (2026-11-14); check exact wording there before you quote an article.
- No official source fixes a list of 개조식 endings or a sentence-length number; those rules are marked "convention".
