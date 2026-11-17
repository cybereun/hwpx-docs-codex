# wording.md — words, sentence endings, plain-Korean replacements

Source ids (S01...) are in `sources.md`; every row cites a source that is free to reuse (government work, 고시 or law, or 공공누리 제1유형), or says "convention". "convention" = no official source states it; the row is this skill's own judgment (for word pairs: the dictionary meaning, checked by §7). Example sentences marked "written for this skill" are not from a source.
Machine use: `scripts/check_gongmun.py` reads the table rows below. A row is read when its first cell matches `P###`, `T###`, `A###` or `X###` and its `check` cell is `Y`. Keep the column order. Column "term" is the exact text searched, or a Python regex after `re:`. P, A and X terms must start a word (no Hangul or digit right before them); T terms attach to the noun before. Do not put `|` inside a cell (use `[...]` in a regex instead of `a|b`). After you change a row, run `python scripts/check_gongmun.py --selftest`.

## 1. Principles (W-rules)
| Id | Rule | Good / Bad | Source |
|---|---|---|---|
| W01 | Write in Hangul and follow the language norms. Put Chinese characters or foreign words in parentheses only when needed for the meaning, or for a hard or new technical term. | `인공지능(AI)` first use only | S15 (국어기본법 제14조①, 시행령 제11조), S03 제7조① |
| W02 | Make the content short and clear. Do not use abbreviations or technical terms that are not in general use. | – | S03 제7조②, S10 p.179 |
| W03 | Short sentences: one or two pieces of information per sentence; split several pieces into several sentences or items. No official number limit exists. Convention used by the checker: warn over 100 characters per sentence. | one long sentence -> 3 sentences | S01 §6 나.2) 나)(2), S10 p.179; limit: convention |
| W04 | Put the conclusion first, then the reason. Use concrete words, not abstract general ones. | – | S01 §6 나.2) 나)(3)-(4), S10 p.179 |
| W05 | Prefer active voice; remove needless passive and causative forms. | `내외부 사정에 의해 변경될` -> `내외부 사정으로 변경될`; `환기를 시켜야 한다` -> `환기를 해야 한다` | S01 §3 1.가.3) |
| W06 | Do not stack passives (`-되어지다`). | `프로그램이 마무리되어진다` -> `프로그램을 마무리한다` | S01 §3 1.가.3) |
| W08 | Avoid translation-style phrases (table T below). | `일부가 도로로 사용 중에 있으나` -> `일부가 도로로 사용되고 있으나` | S01 §3 1.가.3) |
| W09 | Sentence endings: see section 2. | – | S01 §3 3.가.1), S10 p.184 |
| W10 | Do not use overbearing or discriminatory words (tables A, X). | `“……”라며 치하했다` -> `“……”라고 말했다` | S01 §3 3., S13 |
| W11 | Use the 순화 words (tables P) when a plain word with the same meaning exists (§7). The 편람 tells offices to use them. | `금일` -> `오늘` | S01 §3 다.2), S10 p.111, S12 |

## 2. Sentence endings
| Id | Where | Form | Source |
|---|---|---|---|
| EN1 | Body of a 공문 sent to another office or to the public | Polite predicate: `~합니다`, `~바랍니다`, `~하시기 바랍니다`, `~해 주시기 바랍니다`, `~요청합니다`, `~알려 드립니다` (auxiliary verb spaced in principle; `알려드립니다` is allowed) | S01 §3 3.가.1), S01 §4 다.3) and §6 다.1) samples, S10 p.184, S05 제47항 |
| EN2 | Item line (항목) in a 공문 | Short noun phrase or `항목: 내용` form (`일시: 2026. 11. 14.`) | S01 §4 examples |
| EN3 | Avoid in a 공문 for other offices or the public: `~바람`, `~요망`, `~할 것`, `~음` as a command | `전화로 문의 바람` -> `전화로 문의하기 바랍니다`; `작성할 것` -> `작성해 주시기 바랍니다`; `통보 바람` -> `알려 주시기 바랍니다`; `엄수할 것` -> `꼭 지켜 주시기 바랍니다` | S01 §3 3.가.1), S10 p.184, S11 |
| EN4 | Itemized lines for internal use | Allowed: S01 asks to cut sentences short and write by items. No official source lists the endings (`~함`, `~임`, noun phrase): convention. Check with `--internal` (EN3 is then not reported). | S01 §6 나.2) 나)(2); endings: convention |
| EN6 | `~할 것` as an order | -> `~해 주시기 바랍니다` / `~해 주십시오` | S01 §3 3.가.1) |
| EN8 | Noun endings `~음` (`있음`) in text to citizens | -> full predicate (`있습니다`); S01 notes that `~음` endings read as orders | S01 §3 3.가.1) |
| EN11 | Period after a noun-ending line | A line that ends in a noun or a noun form of a verb takes a period in principle; leaving it out is allowed. Use one way per document. Headings and item labels take none. | S05 (문장 부호: 마침표) |
| EN12 | Plain orders (`-하라`, `-하시오`, `~하지 말 것`, `엄금`) in text to other offices or the public | -> `~해 주십시오`, `~하지 마십시오`, `~하시기 바랍니다` (`무단 출입을 엄금함` -> `허가 없이 들어가지 마십시오`). In a 보도 자료, report the content of an order, not its plain imperative words (`“즉시 보완하라”고 지시했다` -> `즉시 보완하도록 지시했다`; do not soften `지시` to `당부`: same meaning, §7). Examples written for this skill. Checker: T034, T046, A011, A012. | S01 §3 3.가.1) (orders read as 고압적); `-하라`: convention |
| EN13 | One ending style per body | Sentences in the body all use the same level (하십시오체 in an outgoing 공문, plain `~다` in a 보도 자료). Noun-phrase endings stand only in item lines (EN2). Do not mix `~합니다.` and `~함.` sentences in one paragraph. | S01 §3 3.가.1); mixing rule: convention |
| EN14 | Stacked hedges | Say a judgment once and plainly: `~하는 것이 바람직할 것으로 판단됨` -> `~하는 것이 좋겠습니다`; `~할 것으로 사료됩니다` -> `~할 것으로 봅니다` (keep the meaning: a judgment stays a judgment, not an order). Keep one hedge only when the fact is truly uncertain (`~할 수 있습니다`). Examples written for this skill. | S01 §6 나.2) 가) (no vague words, G03); P062 (`사료`); stacking: convention |
Rule of thumb: text that citizens read uses full predicates (EN1, EN3); text read inside the office may use itemized lines (EN4). Basis: S01 §3 3.가 (국민의 입장에서 표현하기), S01 §6 나.2).

## 3. 순화 table (P) — plain words for hard words
Columns: id | term | replacement | group | check | source | note. Groups: ZH = Chinese-character word, JP = Japanese-style word, FO = foreign loanword. `check` = Y means `check_gongmun.py` reports the term.
Source A = S11 (국가기록원 OLD&NEW, from the 1993 관보 list). Rows that the 2025 편람 list also has cite S01.

| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| P001 | 금번 | 이번 | ZH | Y | S11, S01 | A; also in the 2025 list |
| P002 | 금일 | 오늘 | ZH | Y | S11 | A |
| P003 | 금년 | 올해 | ZH | Y | S11 | A |
| P004 | 향후 | 앞으로 | ZH | Y | S11 | A |
| P005 | re:상기(?![시하되]) | 위의, 위에 적은 | ZH | Y | S11, S01 | A; not `상기하다/상기시키다` (= recall) |
| P006 | 필히 | 꼭, 반드시 | ZH | Y | S11 | A |
| P007 | 의거 | 따라, 따라서 | ZH | Y | S11 | A; `의거하여` -> `따라` |
| P008 | 요망 | rewrite as `~하시기 바랍니다` (`바람` alone is ambiguous) | ZH | Y | S11 | A; §7 |
| P009 | 감안 | 고려, 생각 | ZH | Y | S11 | A |
| P010 | 기히 | 이미, 앞서 | ZH | Y | S11 | A |
| P011 | 수차 | 여러 차례 | ZH | N | S11 | A; `수차례` is one word, so not checked |
| P012 | 송부 | 보냄, 보내다 | ZH | Y | S11 | A |
| P013 | 조속히 | 빨리 | ZH | Y | S11 | A (`조속하다` -> `빠르다`) |
| P014 | 익일 | 다음 날 | ZH | Y | S01 | 2025 list |
| P015 | 소요 | 드는, 걸리는 | ZH | Y | S11 | A (병행 사용) |
| P016 | 구비 | 갖춤, 갖추다 | ZH | Y | S11 | A (병행 사용) |
| P017 | 하기 | 아래 | ZH | N | S11 | A; `하기` is also a plain verb form, not checked |
| P018 | 가급적 | 되도록 | ZH | Y | S11 | A |
| P019 | 가부 | 찬반 (votes), 옳고 그름 (right or wrong) | ZH | N | S11 | A gives only 옳고 그름; 찬반 for votes is this skill's judgment (§7) |
| P020 | 개소 | 곳, 군데 | ZH | N | S11 | A; clashes with `개소식` |
| P021 | 견지 | 관점 (見地); 굳게 지키다, 유지하다 (堅持) | ZH | N | S11 | A covers 見地 only (§7) |
| P022 | 금회 | 이번 | ZH | Y | S11, S01 | A |
| P023 | 금후 | 앞으로 | ZH | Y | S11 | A |
| P024 | 내지 | `A에서 B까지` (range) or `A 또는 B` (choice); ask if unclear | ZH | Y | S11 | A; §7 |
| P025 | 명일 | 내일 | ZH | Y | S11 | A |
| P026 | 불비 | 못 갖춤 | ZH | N | S11 | A |
| P027 | 별첨 | 붙임 | ZH | Y | S11 | A (따로 붙임); the official 공문 term is `붙임` (S02 제4조④) |
| P028 | 부득이 | 하는 수 없이 | ZH | N | S11 | A; common and accepted |
| P029 | 사전에 | 미리 | ZH | N | S11 | A |
| P030 | 소정의 | 정해진 | ZH | Y | S11 | A (`소정 기일 내` -> `정한 날짜 안에`) |
| P031 | 수령 | 받음 | ZH | N | S11 | A |
| P032 | 시건 | 잠금 | ZH | Y | S11, S01 | A (`시건장치` -> `잠금장치`) |
| P033 | 전항 | 앞 조항 | ZH | N | S11 | A |
| P034 | 차기 | 다음 | ZH | Y | S11, S01 | A |
| P035 | 취하 | keep in legal text; `철회` in plain text | ZH | N | S11 | A; §7 |
| P036 | 하달 | 알리다 | ZH | Y | S11 | A |
| P037 | re:시달(?!리) | 알리다 | ZH | Y | S11 | A; not `시달리다` |
| P038 | re:해태(?=[하한함]) | 게을리함 | ZH | Y | S11, S14 | A + 법제처 2023; not the name `해태` |
| P039 | 회신 | keep `회신` (standard, easy) | ZH | N | S11 | A proposes 답 보냄; fails the "not harder" test (§7) |
| P040 | 경유하다 | 거치다 | ZH | N | S11 | A; `경유` is an official field name |
| P041 | 교부 | `내줌`, `발급` in plain text; keep `교부금`, `교부세` and legal `교부` | ZH | N | S11 | A; §7 |
| P042 | 기재 | 씀, 써넣음 | ZH | N | S11 | A |
| P043 | 수신인 | 받는 이 | ZH | Y | S11 | A |
| P044 | 지양 | 하지 않음, 피함 | ZH | N | S11 | A |
| P045 | 협조 | keep `협조` (standard; `도움` changes the meaning) | ZH | N | S11 | A; `협조자` is an official field name; §7 |
| P046 | 일체 | 모든 것, 모두 | ZH | N | S11 | A |
| P047 | 당월 | 그 달 | ZH | Y | S11 | A |
| P048 | 가용 | 쓸 수 있는 | ZH | Y | S01 | 2025 list |
| P049 | 금명간 | 오늘내일 사이, 곧 | ZH | Y | S11 | A |
| P050 | 익월 | 다음 달 | ZH | Y | S01 | 2025 list |
| P051 | 익년 | 다음 해 | ZH | Y | S01 | 2025 list |
| P052 | 동법 | 같은 법 | ZH | Y | S01 | 2025 list |
| P053 | 동조 | 같은 조 | ZH | N | S01 | 2025 list; clashes with `동조하다` (= agree), not checked |
| P054 | 동항 | 같은 항 | ZH | Y | S01 | 2025 list |
| P055 | re:당해(?=\s?[연년기사법업조]) | 그, 해당 | ZH | Y | S01 | 2025 list (`당해 연도`, `당해 기관`); not `사고를 당해` |
| P056 | re:적의\s?조치 | 적절한 조치 | ZH | Y | S01, S11 | 2025 list; A (`적의한` -> `적절한`); not `적의 공격` (enemy) |
| P057 | 지득 | 알게 됨, 앎 | ZH | Y | S11 | A (`지득하다` -> `알게 되다`) |
| P058 | 차년도 | 다음 해, 다음 연도 | ZH | Y | S01 | 2025 list |
| P059 | 불상의 | 알 수 없는 | ZH | Y | S01 | 2025 list; `불상` alone is also a Buddha statue |
| P060 | 패용 | 달기 | ZH | Y | S01 | 2025 list |
| P061 | 성료 | 성공적으로 마침 | ZH | Y | S01 | 2025 list |
| P062 | re:사료[되됨하] | 생각함, 생각하다 | ZH | Y | S11 | A (`사료하다/되다` -> `생각하다/되다`) |
| P064 | 업데이트 | 갱신 (documents); keep `업데이트` or `최신화` (software) | FO | Y | S11 | A gives 수정 자료, 갱신; §7 |
| P066 | 매뉴얼 | 설명서 (device), 업무 지침 (procedure) | FO | Y | S11 | A gives 지도서, 설명서; §7 |
| P072 | 거버넌스 | spell out the meaning (`민관 협력`, `관리`), or keep it for expert readers | FO | N | S01 | 2025 list gives 민관 협력, 협치, 관리, 정책; §7 |
| P073 | 리스크 | `위험` in general text; keep `리스크` in finance and risk management | FO | Y | S01 | 2025 list (위험, 손실 우려); §7 |
| P075 | 교육을 실시 | 교육을 함 | ZH | Y | S11 | A (`실시` -> `행함`, 병행 사용) |
| P077 | 고수부지 | 둔치 | JP | Y | S11 | A |
| P078 | 구좌 | 계좌 | JP | Y | S11 | A |
| P079 | 노견 | 갓길 | JP | Y | S11 | A |
| P080 | 불입 | 납입 | JP | Y | S11, S01 | A; 2025 list |
| P081 | 다반사 | 예삿일, 흔한 일 | JP | Y | S11 | A (병행 사용) |
| P082 | 거래선 | 거래처 | JP | Y | S11 | A |
| P083 | 도합 | 모두, 합하여 | JP | Y | S11 | A (`도합하여` -> `모두 합하여`) |
| P085 | 가불 | 미리 받은 돈, 우선 지급금 | JP | N | S11 | A (`가불금`) |
| P086 | 고참 | 선임 | JP | N | S11 | A |
| P087 | 잔고 | 잔액 | JP | N | S11 | A |
| P089 | 옵서버 | 참관인 | FO | Y | S14 | 법제처 2023 |
| P090 | 네티즌 | `누리꾼` (recommended, not required) | FO | N | S16 | 문체부 2011; §7 |
Not confirmed in any free source: `제반` -> `모든` (S01 gives `여러`, P140), `가부` -> `찬반` (this skill's judgment, P019). Do not present them as official.

## 3b. 2025 편람 "필수 개선 행정 용어" (S01 §3, 2025.12)
Newest official list; prefer it when it differs from older lists. Same columns as section 3.
| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| P101 | 일할 계산 | 날수에 따라 계산, 하루 단위로 나누어 계산 | ZH | Y | S01 | S01 also gives `날짜 계산`: reads as date arithmetic (§7) |
| P102 | 차폐 | 가림 (screens, fences); keep `차폐` in safety and technical text | ZH | Y | S01 | `차폐 시설` -> `가림 시설`; §7 |
| P103 | 득하 | 받다, 얻다 | ZH | Y | S01 | `허가를 득하여` -> `허가를 받아` |
| P104 | 불인정 | 인정되지 않음 | ZH | Y | S01 | |
| P105 | 내수진작 | 국내 수요를 높임 | ZH | Y | S01 | |
| P106 | 가격 투찰 | 가격 제시 | ZH | Y | S01 | |
| P107 | 가일층 | 한층 더, 더한층 | ZH | Y | S01 | |
| P108 | 거양 | 올리다 | ZH | Y | S01 | `거양하다` |
| P109 | re:경주하(?=[여고며는기]) | 기울이다, 쏟다, 다하다 | ZH | Y | S01 | `노력을 경주하여`; not the city name |
| P110 | 계도 | 알려 주다 (verb `계도하다`); keep `계도 기간` with a gloss | ZH | Y | S01 | §7 |
| P111 | 계리 | 회계 처리 | ZH | Y | S01 | |
| P112 | 기망 | keep in legal text; `속이다` in plain text | ZH | Y | S01 | §7 |
| P113 | 긴요 | 아주 중요하다 | ZH | Y | S01 | |
| P114 | 내구 연한 | 사용 연한, 사용 가능 기간 | ZH | Y | S01 | |
| P115 | re:동[년월일](?=[에의은도]) | 같은 해, 같은 달, 같은 날 | ZH | Y | S01 | `동년`, `동월`, `동일(同日)`; `동일하다` (= same) is not this word |
| P116 | 만전을 기할 | 최선을 다할 | ZH | Y | S01 | `만전을 기할 예정이다` |
| P117 | 부기 | 덧붙여 적다 (`부기하다`); keep `부기등기` | ZH | Y | S01 | §7 |
| P118 | 별건 | 다른 건, 딴 건 | ZH | Y | S01 | |
| P119 | 불식 | 없애다 | ZH | Y | S01 | |
| P120 | 불시에 | 갑자기, 예고 없이 | ZH | Y | S01 | |
| P121 | 불요 | 필요 없음 | ZH | Y | S01 | |
| P122 | 단차 | 높이 차이, 높낮이 차이 | ZH | Y | S01 | |
| P123 | 첨두시 | 가장 붐빌 때, 수요가 최고일 때 | ZH | Y | S01 | |
| P124 | 사역 | 채용 | ZH | N | S01 | clashes with other meanings of `사역` |
| P125 | 상이한 | 다른 | ZH | Y | S01 | |
| P126 | 상존 | 늘 있음 | ZH | Y | S01 | |
| P127 | 상회 | 웃돌다 | ZH | Y | S01 | `상회하다`; `하회하다` -> `밑돌다` (P128) |
| P128 | 하회 | 밑돌다 | ZH | Y | S01 | |
| P129 | 송달 | keep in legal text; for citizens `송달(서류를 법에 따라 보내는 일)`; `보내다` only when no legal service is meant | ZH | Y | S01 | §7 |
| P130 | 서훈된 자 | 훈장을 받은 사람 | ZH | Y | S01 | |
| P131 | 수범 사례 | 모범 사례, 잘된 사례 | ZH | Y | S01 | |
| P132 | 수의 시담 | 가격 협의; keep in procurement documents | ZH | Y | S01 | §7 |
| P133 | 수취 | 받음 | ZH | Y | S01 | |
| P134 | 시찰 | 살펴보다 | ZH | Y | S01 | `시찰하다` |
| P135 | 시현 | 나타내다, 나타내 보이다 | ZH | Y | S01 | `시현하다` |
| P136 | 양도양수 | keep `양도·양수` in legal text; `넘겨주고 넘겨받음` in plain text | ZH | Y | S01 | §7 |
| P137 | 여입 결의 | 회수 결정; keep in accounting documents | ZH | Y | S01 | §7 |
| P138 | 예산 지변 과목 | 예산 과목 | ZH | Y | S01 | |
| P139 | 예찰 | 미리 살피기 | ZH | Y | S01 | |
| P140 | 제반 | 여러 | ZH | Y | S01 | |
| P141 | 용이 | 쉽다 | ZH | Y | S01 | `용이하다` |
| P142 | 이격 | 벌어짐, 떨어짐 | ZH | Y | S01 | |
| P143 | 이첩 | 넘기다 | ZH | Y | S01 | `이첩하다` |
| P144 | 자동제세동기 | 자동 심장 충격기 | ZH | Y | S01 | |
| P145 | 적기 | 알맞은 시기, 제철 | ZH | N | S01 | `적기` also = enemy plane; not checked |
| P146 | 적시 | 제때 | ZH | N | S01 | `적시하다` (= point out) is another word; not checked |
| P147 | 정수 | 정원 | ZH | N | S01 | `정수` (= integer, purified water) clashes; not checked |
| P148 | 존치 | 그대로 두다 | ZH | Y | S01 | `존치하다` |
| P149 | 제고 | 높이다 | ZH | Y | S01, S11 | `제고하다` |
| P150 | 초도순시 | 첫 시찰, 첫 둘러보기 | ZH | Y | S01 | |
| P151 | 채납 | keep `기부채납` (legal term); `받음` elsewhere | ZH | Y | S01 | §7 |
| P152 | 천명 | 밝히다 | ZH | Y | S01 | `천명하다` |
| P153 | 취명 | 울림, 울리다 | ZH | Y | S01 | `사이렌 취명` |
| P154 | 추서 | 훈장을 내리다 | ZH | Y | S01 | `추서하다` |
| P155 | re:타(?=\s?[기부지업시법])  | 다른 | ZH | N | S01 | `타 기관`, `타 부서` -> `다른 기관`, `다른 부서`; not checked (too many other words start with 타) |
| P156 | 편취 | keep in legal text; `속여 빼앗다` in plain text | ZH | Y | S01 | §7 |
| P157 | 현출 | 두드러짐 | ZH | Y | S01 | |
| P158 | 확행 | 꼭 하시기 바랍니다 | ZH | Y | S01 | `확행 바랍니다` |
| P159 | 행선지 | 목적지 | ZH | Y | S01 | |
| P160 | 기 시행 | 이미 시행한 | ZH | Y | S01 | `기 ( )` -> `이미 ( )`, `기존의 ( )` |
| P161 | 브로슈어 | 안내서, 소책자 | FO | Y | S01 | |
| P162 | 키스 앤드 라이드 | 환승 정차 구역 | FO | Y | S01 | |
| P163 | 뉴노멀 | 새 일상, 새 기준 | FO | Y | S01 | |
| P164 | As-is | 개선 전 | FO | Y | S01 | |
| P165 | To-be | 개선 후 | FO | Y | S01 | |
| P166 | Bottom-up | 상향식 | FO | Y | S01 | |
| P167 | 규제 샌드박스 | keep the program name; gloss once `(신기술 시험을 위한 규제 특례)` | FO | Y | S01 | S01 proposes 규제 유예: narrower meaning (§7) |
| P168 | 그린 모빌리티 | 친환경 이동 수단 | FO | Y | S01 | |
| P169 | 니즈 | 수요, 요구 | FO | Y | S01 | S01 also gives `바람`: ambiguous (§7) |
| P170 | 킥오프 | 첫 회의, 첫 기획 회의 | FO | Y | S01 | |
| P171 | 세션 | 시간, 회차 (time block); 분과 (subgroup) | FO | Y | S01 | S01 also gives `부문`, `부분`: different meaning (§7) |
| P172 | 스왑 | 교환; in finance keep `통화 스와프` | FO | Y | S01 | §7 |
| P173 | 소버린 AI | 자국 인공 지능, 독자 인공 지능 | FO | Y | S01 | |
| P174 | 스크린 도어 | 안전문 | FO | Y | S01 | |
| P175 | 스타트업 | keep `스타트업`; when a law's defined group is meant, use that law's term (e.g. `초기창업기업`, S17) | FO | N | S01 | S01 proposes 창업 초기 기업, 새싹 기업: `창업 초기 기업` is broader (any new business), `새싹 기업` reads harder (§7). Design decision 2026-11-14. |
| P176 | 시너지 | (동반) 상승 효과 | FO | Y | S01 | |
| P177 | 아웃리치 | 현장 지원 활동 (`거리 상담` only for street counseling) | FO | Y | S01 | |
| P178 | 액셀러레이터 | 창업기획자 (legal term, S17) | FO | Y | S01, S17 | S01 proposes a long phrase; §7 |
| P179 | 액션 플랜 | 실행 계획, 세부 계획 | FO | Y | S01 | |
| P180 | 밸류 업 | 가치 향상 | FO | Y | S01 | |
| P181 | 업스킬링 | 역량 강화 | FO | Y | S01 | |
| P182 | 윈윈 | 상생 | FO | Y | S01 | `윈윈 전략` -> `상생 전략` |
| P183 | 쿼터 | 한도량, 할당량 | FO | Y | S01 | |
| P184 | 로컬 브랜드 | 지역 상표, 지역 대표 상표 | FO | Y | S01 | |
| P185 | 클러스터 | 산학 협력 지구, 협력 지구 (regions); keep `클러스터` in IT text | FO | Y | S01 | §7 |
| P186 | 태스크포스 | 전담팀, 특별팀 | FO | Y | S01 | also `T/F`, `TF` |
| P187 | 테스트 베드 | 시험대, 시범 공간, 실증 공간 (not `시험장` = exam hall) | FO | Y | S01 | §7 |
| P188 | 허브 | 중심, 중심지, 거점 | FO | Y | S01 | |
| P189 | 헬스케어 | 건강 관리 | FO | Y | S01 | |
| P190 | MOU | 업무 협약, 양해 각서 | FO | Y | S01 | abbreviations: write Korean, English in parentheses if needed (G41): AI -> 인공 지능(AI), ICT -> 정보 통신 기술(ICT), IoT -> 사물 인터넷(IoT), R&D -> 연구 개발(R&D), B2B -> 기업 간 거래(B2B), ODA -> 공적 개발 원조(ODA), IR -> 기업 설명회(IR) |

## 3c. More pairs from the 1993 list (S11)
Pairs from the 국가기록원 list that are still useful and pass §7. Many of these words also have other meanings, so several rows are `check` N: read them, the checker does not report them.
| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| P206 | 마스터 플랜 | 종합 계획, 기본 설계 | FO | Y | S11 | A (병행 사용); also `마스터플랜` |
| P223 | 체크리스트 | 점검표 | FO | Y | S11 | A (점검표, 대조표) |
| P229 | 슬로건 | 표어 | FO | Y | S11 | A (표어, 강령) |
| P234 | 가료 | 치료 | ZH | Y | S11 | A (`가료하다` -> `치료하다`) |
| P235 | 개산 | 어림셈, 대략 계산 | ZH | N | S11 | A |
| P236 | re:게[첩첨] | 내붙임, 써 붙임 | ZH | Y | S11 | A |
| P237 | 견양 | 서식, 보기 | ZH | Y | S11 | A |
| P238 | 계류 | 검토 중, 진행 중 (`계류 중`) | ZH | N | S11 | A; also mooring of a ship |
| P239 | 내용 연수 | 사용 가능 햇수; keep `내용연수` in accounting | ZH | Y | S11 | A; §7 |
| P241 | 부락 | 마을 | ZH | Y | S11 | A (병행 사용) |
| P242 | 불출 | 내줌 | ZH | Y | S11 | A |
| P244 | 일부인 | 날짜 도장 | ZH | Y | S11 | A |
| P245 | 임석 | 현장 참석, 참석 | ZH | Y | S11 | A |
| P246 | 하구언 | 강어귀 둑 | ZH | Y | S11 | A |
| P247 | 통보 | 알림; `통보 바람` -> `알려 주시기 바랍니다` | ZH | N | S11 | A |
| P248 | 소관 | 맡은 | ZH | N | S11 | A (병행 사용) |
| P249 | 당초 | 애초, 맨 처음 (not `기존` = existing) | ZH | N | S11 | A (병행 사용); §7 |
| P251 | 유관기관 | 관계 기관 | ZH | Y | S11 | A |
| P252 | 도출 | 찾아내다, 이끌어 내다 | ZH | N | S11 | A (병행 사용) |
| P254 | 기일을 엄수 | 날짜를 지켜 | ZH | Y | S11 | A (`기일 엄수하여` -> `날짜 지키어`) |
| P255 | 면밀히 | 자세히 | ZH | Y | S11 | A (병행 사용) |
| P257 | 미연에 | 미리 | ZH | Y | S11 | A (`미연에 방지하다` -> `미리 막다`) |
| P258 | 소기의 | 기대한, 기대했던 | ZH | Y | S11 | A |
| P259 | 첩부 | 붙임, 붙이다 | ZH | Y | S11 | A (`첩부하다` -> `붙이다`) |
| P261 | 동봉 | 함께 보냄 | ZH | N | S11 | A (병행 사용) |
| P265 | 일환으로 | ~의 하나로 | ZH | Y | S11 | A |
| P266 | 해소 | 풀다; `없애다` only for removable things | ZH | N | S11 | A (풀다, 없애다, 병행 사용); §7 |
| P267 | 수여하 | 주다, 드리다 | ZH | N | S11 | A (병행 사용); keep `훈장을 수여하다` in formal awards |
| P268 | 하는 자 | 하는 사람, 하는 이 (notices about individuals); keep `자` in law (it includes 법인) | ZH | N | S11 | A; §7 |
| P271 | 찌라시 | 선전지, 낱장 광고지 | JP | Y | S11 | A |
| P273 | 대절 | 전세 | JP | N | S11 | A (`대절하다` -> `전세 내다`) |
| P274 | 보합세 | keep `보합세` in finance (`주춤세` = slowing, a different meaning) | JP | N | S11 | A proposes 주춤세, 멈춤세; §7 |
| P275 | 가처분 | keep in legal text; `임시 처분` in plain text | JP | N | S11 | A; §7 |
| P276 | 수취인 | 받는 이 | JP | Y | S11 | A |
Amounts for the public: write the usual 만 form (`21,345천원` -> `2,134만 5천 원`, S01 §3 1.가.3)). Hangul first for Chinese characters and Roman letters (G18).

For hard words not in these tables, look them up in S11 (국가기록원 OLD&NEW, 8,644 pairs from 1993; 4,101 marked "순화된 용어만 사용"). The 1993 list is old: prefer the 2025 list above, and check every pair against §7.

## 3d. Pairs selected by this skill (v2.6, 2026-11-14)
Words often seen in 공문 that a general reader may not know, picked one by one by this skill. For each pair: the plain word has the same dictionary meaning in the sense given, the pair passes §7, and the word has no common other meaning when `check` is Y (else a regex limits it). Source S11 = the 1993 list gives the same plain word (A); S01 = the 2025 편람 uses the plain word; "convention" = this skill's own pair. The 국립국어원 guides with restrictive licenses (sources.md, "Not used") were not used to pick or word these pairs. The replacement is a candidate: §7 still decides each use (an expert 수신처 may keep the word).

| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| P277 | re:금반(?!지) | 이번 | ZH | Y | S11 | A; not `금반지` |
| P278 | 작금 | 요즈음, 최근 | ZH | Y | S11 | A |
| P279 | 차제에 | 이번 기회에 | ZH | Y | convention | |
| P280 | 일응 | 우선, 일단 | ZH | Y | S11 | A |
| P281 | 첨언 | 덧붙임, 덧붙여 말함 | ZH | Y | S11 | A |
| P282 | 차후 | 앞으로, 다음에 | ZH | Y | S11 | A |
| P283 | 여타 | 그 밖의, 다른 | ZH | Y | S11 | A |
| P284 | 개진 | 밝힘, 말함 (`의견을 개진` -> `의견을 밝힘`) | ZH | Y | S11 | A |
| P285 | re:산적(?=[해하한된되]) | 많이 쌓여 있음 (`과제가 산적해 있다` -> `과제가 많이 쌓여 있다`) | ZH | Y | convention | not `산적` (bandit, a dish) |
| P286 | 지대한 | 큰, 매우 큰 | ZH | Y | convention | |
| P287 | 괄목할 | 놀랄, 눈에 띄는 (`괄목할 만한 성과` -> `눈에 띄는 성과`) | ZH | Y | S11 | A (놀랄 만한) |
| P288 | re:주지(?=[하시해한]) | 널리 알림 (`직원에게 주지시켜` -> `직원에게 널리 알려`) | ZH | Y | convention | not `주지` (head monk) |
| P289 | 숙지 | 잘 알아 둠, 익혀 둠 | ZH | Y | S11 | A (자세히 앎) |
| P290 | re:도모(?=[하해한했할함합]) | write the main verb (`협력을 도모하고자` -> `협력하고자`), 꾀함 | ZH | Y | convention | |
| P291 | re:매진[하한할함합해] | 힘쓰다, 온 힘을 다하다 | ZH | Y | S11 | A; not `매진되다` (= sold out) |
| P292 | re:진작(?=[하시을]) | 북돋움 (`사기 진작` -> `사기를 북돋움`) | ZH | Y | S11 | A; not the adverb `진작` (= earlier) |
| P293 | 일익을 | 한몫을 (`일익을 담당하다` -> `한몫을 하다`) | ZH | Y | convention | |
| P294 | 만반의 | 모든, 빈틈없는 | ZH | Y | convention | |
| P295 | 전술한 | 앞에서 말한 | ZH | Y | S11 | A |
| P296 | re:후술[하할한함합했] | 뒤에서 말할, 아래에서 설명할 | ZH | Y | convention | |
| P297 | re:도래(?=[하한했할함합]) | 다가옴, 닥침 (`기한이 도래하면` -> `기한이 되면`) | ZH | Y | S11 | A |
| P298 | 미비 | 갖추지 못함, 빠짐 (`서류 미비 시` -> `서류를 다 갖추지 않으면`) | ZH | Y | convention | |
| P299 | 공란 | 빈칸 | ZH | Y | S11 | A |
| P300 | re:[좌우]측 | 왼쪽, 오른쪽 | ZH | Y | S11 | A (`좌측` -> `왼쪽`) |
| P301 | 여하에 따라 | `~에 따라` (`결과 여하에 따라` -> `결과에 따라`) | ZH | Y | convention | |
| P302 | 적치 | 쌓아 둠 (`적치물` -> `쌓아 둔 물건`) | ZH | Y | convention | |
| P303 | 거행 | 엶, 치름 (`기념식을 거행한다` -> `기념식을 연다`) | ZH | Y | S11 | A (올리다, 하다) |
| P304 | 왕림 | 와 주심 (`왕림하여 주시기 바랍니다` -> `와 주시기 바랍니다`) | ZH | Y | S11 | A (오셔서) |
| P305 | 절취선 | 자르는 선 | ZH | Y | S01, S11 | S01 서식 설계 기준 6.가 writes `자르는 선` |
| P306 | re:내방(?=[하한했객]) | 방문, 찾아옴 (`내방객` -> `방문객`) | ZH | Y | S11 | A; not `내방` (inner room) |
| P307 | re:당 (?=[기부][관서]) | 우리 기관, 이 기관 (your own office) | ZH | Y | convention | like G26 (`본` -> `이`); address words: PH111 |
| P308 | 행락 | 나들이 (`행락객` -> `나들이객`) | ZH | Y | S11 | A (놀이) |
| P309 | 수순 | 순서, 절차 | JP | Y | S11 | A |
| P310 | 견출지 | 찾음표, 이름표 | JP | Y | S11 | A (찾음표) |
| P311 | 노임 | 임금, 품삯 | JP | Y | S11 | A (품삯) |
| P312 | 망년회 | 송년회 | JP | Y | convention | |
| P313 | 수속 | 절차 (`출국 수속` -> `출국 절차`) | JP | Y | S11 | A |
| P314 | 시말서 | 경위서 | JP | Y | S11 | A |
| P315 | 언도 | 선고 | JP | Y | S11 | A; `선고` is the legal term |
| P316 | 할증료 | 추가 요금, 웃돈 | JP | Y | S11 | A (웃돈, 추가금) |
| P317 | 구랍 | 지난해 12월 | JP | Y | S11 | A (지난해 섣달) |
| P318 | 궐석 | 결석; keep `궐석 재판` in law | JP | Y | S11 | A |
| P319 | 매상 | 매출, 판매액 | JP | Y | convention | |
| P320 | 엑기스 | 진액, 농축액 | JP | Y | convention | |
| P321 | 우천 | 비 (`우천 시 취소` -> `비가 오면 취소`) | JP | Y | convention | |
| P322 | 잔업 | 시간 외 근무 | JP | Y | S11 | A (시간외 일) |
| P323 | 차압 | 압류 | JP | Y | S11 | A; `압류` is the legal term |
| P324 | 인프라 | 기반 시설 (roads, networks), 기반 (general) | FO | Y | convention | keep for an expert 수신처 (§7) |
| P325 | 가이드라인 | 지침 | FO | Y | convention | |
| P326 | 로드맵 | 단계별 추진 계획, 이행 계획 | FO | Y | convention | |
| P327 | 컨설팅 | 자문, 상담 | FO | Y | convention | |
| P328 | 모니터링 | 점검, 관찰, 감시 (by context) | FO | Y | convention | keep for an expert 수신처 (§7) |
| P329 | 피드백 | 의견, 반응, 보완 의견 | FO | Y | convention | |
| P330 | 이슈 | 쟁점, 현안 | FO | Y | S11, convention | A gives 논쟁거리, 논점 |
| P331 | 벤치마킹 | 우수 사례 조사, 본받기 | FO | Y | convention | |
| P332 | 인센티브 | 성과급 (pay), 혜택, 우대 (by context) | FO | Y | convention | |
| P333 | 프로세스 | 절차, 과정 | FO | Y | convention | |
| P334 | 매칭 | 연결, 짝 맺기; `매칭 펀드` -> `대응 자금` | FO | Y | convention | §7 example |
| P335 | 원스톱 | 한곳에서 한 번에 (`원스톱 서비스` -> `통합 처리 서비스`) | FO | Y | convention | |
| P336 | 핫라인 | 직통 전화, 직통 연락망 | FO | Y | S11 | A |
| P337 | 랜드마크 | 상징물, 대표 건물 | FO | Y | convention | |
| P338 | 트렌드 | 흐름, 경향 | FO | Y | convention | |
| P339 | 가이드 | 안내, 안내서, 안내인 (by context) | FO | Y | S11 | A (안내(원), 길잡이) |
| P340 | 팸플릿 | 소책자, 안내 책자 | FO | Y | convention | |
| P341 | 리플릿 | 안내장, 홍보물 | FO | Y | convention | A gives 광고 쪽지 (narrower: §7) |
| P342 | 이벤트 | 행사 | FO | Y | S11 | A |
| P343 | 오리엔테이션 | 예비 교육, 안내 교육 | FO | Y | S11 | A |
| P344 | re:컨트롤\s?타워 | 총괄 기구, 사령탑 | FO | Y | convention | |
| P345 | re:[어아]젠다 | 의제, 과제 | FO | Y | convention | spelling: `어젠다` |
| P346 | 키오스크 | 무인 단말기 (무인 안내기, 무인 주문기) | FO | Y | convention | |
| P347 | 노하우 | 비결, 기술, 경험 | FO | Y | S11 | A |
| P348 | 데드라인 | 마감, 마감 기한 | FO | Y | convention | |
| P349 | 스케줄 | 일정 | FO | Y | convention | |
| P350 | 미팅 | 회의, 만남 | FO | Y | S11 | A (모임) |
| P351 | re:오픈(?=[하한했식\s]) | 개장, 개업, 개통, 공개 (by context) | FO | Y | S11 | A (열기) |
| P352 | 리뉴얼 | 새 단장 | FO | Y | convention | |
| P353 | 웨비나 | 온라인 세미나, 화상 발표회 | FO | Y | convention | |
| P354 | re:라운드\s?테이블 | 원탁회의 | FO | Y | convention | |
| P355 | 페스티벌 | 축제 | FO | Y | convention | event names stay (§7) |
| P356 | 심포지엄 | 학술 토론회 | FO | Y | convention | |
| P357 | 퍼실리테이터 | 회의 진행자 | FO | Y | convention | |
| P358 | 모더레이터 | 사회자, 좌장 | FO | Y | convention | |
| P359 | 레퍼런스 | 참고 자료 (documents), 수행 실적 (contracts) | FO | Y | convention | |
| P360 | 컨센서스 | 합의, 공감대 | FO | Y | convention | |
| P361 | 이니셔티브 | 구상 (a plan), 주도권 (the lead) | FO | Y | convention | program names stay (§7) |
| P362 | 파일럿 | 시범 (`파일럿 사업` -> `시범 사업`) | FO | Y | convention | |
| P363 | 프로토타입 | 시제품, 시험 모형 | FO | Y | convention | keep in technical text |
| P364 | re:[솔설]루션 | 해결책, 해법; for a product, say what it is (`보안 프로그램`) | FO | Y | convention | spelling: G14 |
| P365 | re:워킹\s?그룹 | 실무단, 실무 협의체 | FO | Y | convention | |
| P366 | 패키지 | 묶음, 일괄 (`패키지 상품` -> `묶음 상품`, `패키지 지원` -> `일괄 지원`) | FO | Y | S11 | A (한 묶음) |
| P367 | 마인드 | 의식, 자세 | FO | Y | convention | |
| P368 | 데스크 | 창구, 안내소 (`안내 데스크` -> `안내 창구`) | FO | Y | convention | A gives 책상 (another sense) |
| P369 | 원팀 | 한 팀, 한마음 | FO | Y | convention | |
| P370 | 아카이브 | 기록 보관소, 자료 보관 | FO | Y | convention | |
| P371 | 네트워크 | 연결망, 관계망; 통신망 (IT) | FO | Y | convention | |
| P372 | 네트워킹 | 교류, 친교 | FO | Y | convention | |
| P373 | 리스트 | 목록, 명단 | FO | Y | convention | |
| P374 | re:타[깃겟] | 대상, 목표 | FO | Y | convention | spelling: `타깃` |
| P375 | 미션 | 임무, 과제 | FO | Y | convention | |
| P376 | 노쇼 | 예약 불이행, 예약하고 오지 않음 | FO | Y | convention | |
| P377 | 굿즈 | 기념품, 상품 | FO | Y | convention | |
| P378 | 셧다운 | 일시 중단, 업무 정지 | FO | Y | convention | |
| P379 | 언택트 | 비대면 | FO | Y | convention | |
| P380 | 버스킹 | 거리 공연 | FO | Y | convention | |
| P381 | re:플리\s?마켓 | 벼룩시장 | FO | Y | convention | event names stay (§7) |
| P382 | re:팝업\s?스토어 | 임시 매장 | FO | Y | convention | |
| P383 | 케어 | 돌봄 (`방문 케어` -> `방문 돌봄`); `스킨 케어` -> `피부 관리` | FO | Y | convention | care for people |
| P384 | 실버 | 노인, 어르신 (`실버 세대` -> `노년층`) | FO | Y | convention | |
| P385 | 리워드 | 보상 | FO | Y | convention | |
| P386 | 마일스톤 | 주요 단계, 중간 목표 | FO | Y | convention | |
| P387 | 프레젠테이션 | 발표 | FO | Y | convention | |
| P388 | 앰배서더 | 홍보 대사 | FO | Y | convention | |
| P389 | 플랫폼 | say what it is (`온라인 플랫폼` -> `온라인 서비스`, `협력 플랫폼` -> `협력의 장`); `승강장` at a station | FO | N | convention | keep in IT text; A gives 열차승강장 (one sense) |
| P390 | 리빙랩 | keep with a gloss at first use (`리빙랩(주민이 함께 지역 문제를 풀어 보는 실험 사업)`) | FO | N | convention | no same-meaning plain word (§7) |
| P391 | 다운로드 | 내려받기 | FO | Y | S01 | S01 uses both `다운로드` and `내려받기` |
| P392 | 업로드 | 올리기 | FO | Y | S01 | S01 uses `업로드`; `올리기` is a plain common word |
| P393 | 이메일 | 전자우편 | FO | Y | S01 | S01 uses `전자우편` (22 times); like G18 |
| P409 | re:소정\s?양식 | 정해진 서식 | ZH | Y | S11 | A (`소정의` -> `정해진`); like P030 |
| P412 | re:진위\s?여부 | 진위, 참인지 거짓인지 (`여부` repeats the meaning) | ZH | Y | S11 | A (`진위를 가리다` -> `참과 거짓을 가리다`) |
P391-P393, P409 and P412 were added after a miss check (2026-11-14): the term list of the rows removed in v2.5 was compared with this table. A missed word was added only when it was also found in a free pool (S01, S10, S11, statutes); the source cell names that pool. Missed words with no free source were left out (ids P394-P408, P410, P411, P413 not used). Only terms were compared; no replacement, order or grouping was taken.

## 4. Translation-style and stock-form table (T)
Same columns as section 3. Group TR = checked in every register; TG = checked in 공문 text only (stock 공문 forms that are normal elsewhere).
The rule behind TR rows: S01 §3 1.가.3) "외국어를 번역한 느낌이 나는 표현을 피하고 … 과도한 피동이나 사동 표현을 쓰지 않는다". Which forms count is this skill's judgment ("convention" unless S01 gives the form). All examples from T017 on are written for this skill. A row with `check` N is advice: read it; the form is often correct.

| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| T003 | 에 의해 | `~으로`, or the actor as subject | TR | Y | S01 | S01 §3 1.가.3): `내외부 사정에 의해` -> `내외부 사정으로` |
| T004 | 에 의하여 | `~에 따라`, `~으로` | TR | Y | S01, S11 | same rule; `의거하여` -> `따라` (P007) |
| T010 | 에 위치한 | 에 있는, 자리 잡은 | TR | Y | S11 | A (`위치한` -> `자리잡은, 있는`) |
| T014 | re:되어[지진집져졌질] | `되다` forms: `되어진다` -> `된다`, `되어집니다` -> `됩니다` | TR | Y | S01 | double passive (`마무리되어진다` -> `마무리한다`) |
| T017 | re:에(?:게)? 있어서 | `에서`, `~할 때` (`업무 처리에 있어서` -> `업무를 처리할 때`) | TR | Y | S01, convention | not `본사가 서울에 있어서 가깝다` (= because it is in) |
| T018 | re:[함음됨]에 있어(?!서) | `~할 때`, `~하는 데` (`계약함에 있어 유의할 점` -> `계약할 때 유의할 점`) | TR | Y | S01, convention | |
| T019 | re:[을를] 필요로 [하한할함합했] | `이/가 필요하다` (`협조를 필요로 하는 업무` -> `협조가 필요한 업무`) | TR | Y | convention | keep in a quoted statute |
| T020 | re:보여[지진집져졌질] | `보이` (`효과가 클 것으로 보여집니다` -> `효과가 클 것으로 보입니다`) | TR | Y | S01 | double passive, like `마무리되어진다` |
| T021 | re:잊혀[지진집져졌질] | `잊히` (`잊혀진 기록` -> `잊힌 기록`) | TR | Y | S01 | double passive |
| T022 | re:[이가] 요구[되된됩됐될] | `이/가 필요하다`, `~해야 한다` (`신속한 대응이 요구됩니다` -> `빨리 대응해야 합니다`) | TR | Y | convention | |
| T023 | re:회를 가[졌지진질집져] | `열다`, `하다` (`간담회를 가졌다` -> `간담회를 열었다`) | TR | Y | convention | events ending in `-회`: 간담회, 설명회, 토론회, 협의회 |
| T024 | re:의를 가[졌지진질집져] | `하다` (`회의를 가졌다` -> `회의를 하였다`, `협의를 가진 후` -> `협의한 후`) | TR | Y | convention | `의의를 가진다` -> `의의가 있다` |
| T025 | re:시간을 가[졌지진질집져] | the act itself (`의견을 나누는 시간을 가졌다` -> `의견을 나누었다`) | TR | Y | convention | |
| T026 | re:에 다름 아[니닌닙] | `~이다`, `~과 같다` (`예산 낭비에 다름 아니다` -> `예산 낭비이다`) | TR | Y | convention | |
| T027 | re:(?<![그이])(?<!이 )중에 있[다으습었] | `~고 있다` (`검토 중에 있습니다` -> `검토하고 있습니다`) | TR | Y | S01 | S01 §3 1.가.3): `사용 중에 있으나` -> `사용되고 있으나`; not `목록 중에 있다` (= among) |
| T028 | re:에 대[하해한] | often `을/를` or `에` (`자료에 대하여 검토한 결과` -> `자료를 검토한 결과`) | TR | N | convention | keep when it means "about" (`계획에 대한 의견`) |
| T029 | re:[을를] 통[해하] | `으로`, `에서` when it names a tool or a place (`홈페이지를 통해 신청` -> `홈페이지에서 신청`) | TR | N | convention | keep for a process or a go-between (`협의를 통해`, `대리인을 통해`) |
| T030 | 로부터 | `에게서`, `에서`, or the giver as subject (`주민으로부터 민원이 제기되었다` -> `주민이 민원을 냈다`) | TR | N | convention | keep for a start point (`시행일로부터`) |
| T031 | re:지 않을 수 없 | `~해야 한다`, `~할 수밖에 없다` (`다시 검토하지 않을 수 없습니다` -> `다시 검토해야 합니다`) | TR | Y | convention | double negation (G36) |
| T032 | re:[개해소설][선소개득]시[키켜켰] | `~하다` (`제도를 개선시키다` -> `제도를 개선하다`, `갈등을 해소시켜` -> `갈등을 해소하여`) | TR | Y | S01 | needless causative (S01: `환기를 시켜야` -> `환기를 해야`); 개선, 해소, 소개, 설득 |
| T033 | re:(?<![^간]소)화시[키켜켰] | `~화하다` (`활성화시키다` -> `활성화하다`, `강화시켜` -> `강화하여`) | TR | Y | S01 | needless causative; keep only when `-화하다` cannot take that object |
| T034 | re:하라(?![가-힣]) | `~해 주십시오`, `~하시기 바랍니다` (EN12) | TG | Y | S01, convention | S01 §3 3.가.1); in a quote, report the content (EN12) |
| T035 | re:(?<=[가-힣])토록(?=\s?하) | `~하도록` (`제출토록 하시기 바랍니다` -> `제출하여 주시기 바랍니다`) | TG | Y | convention | |
| T036 | 코자 | `~하고자` (`시행코자 합니다` -> `시행하고자 합니다`) | TG | Y | convention | |
| T037 | 는 바입니다 | `~합니다` (`협조를 부탁드리는 바입니다` -> `협조를 부탁드립니다`) | TG | Y | convention | |
| T038 | 에 즈음하여 | `~을 맞아` (`개관 10주년에 즈음하여` -> `개관 10주년을 맞아`) | TG | Y | convention | |
| T039 | re:[을를] 요[하한함합할했] | `이/가 필요하다` (`주의를 요하는 구간` -> `주의가 필요한 구간`) | TR | Y | convention | |
| T040 | re:에 한[하해](?:여)? | `~만` (`신청자에 한하여 지급` -> `신청한 사람에게만 지급`) | TG | Y | convention | keep in a quoted statute |
| T041 | re:[을를] 위시[한하해] | `~을 비롯한` | TR | Y | convention | |
| T042 | re:[을를] 불문하고 | `~와 관계없이`, `~이든 아니든` (`나이를 불문하고` -> `나이와 관계없이`) | TG | Y | convention | |
| T043 | re:지 아니[하한할함합했] | `~지 않다` (`제출하지 아니한 경우` -> `제출하지 않은 경우`) | TG | Y | convention | keep in a quoted statute |
| T044 | 에 소재한 | `~에 있는` | TR | Y | convention | like T010 |
| T045 | re:[인한는]바(?=[,\s]) | end the sentence; start the next with `이에`, `따라서` (PH109) | TG | Y | convention | `~하였는바,` / `~인바` |
| T046 | re:[하마]시오(?![가-힣]) | `~하십시오`, `~해 주십시오` (`주의하시오` -> `주의하십시오`, `들어가지 마시오` -> `들어가지 마십시오`) | TG | Y | S01 | 하오체 order; S01 §3 3.가.1) asks for 하십시오체 (EN12) |

## 5. Harsh or overbearing words (A)
| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| A001 | 치하하 | 말하다, 감사를 전하다 (avoid the word `치하하다`) | AU | Y | S01 | S01 §3 3.가.2): `“……”라며 치하했다` -> `“……”라고 말했다` |
| A003 | 신청이 불가 | 신청할 수 없습니다 | AU | Y | S11, S01 | A (`불가` -> `안 됨`, `불가능` -> `할 수 없음`); S01 §3 (`불인정될 수 있음` -> `인정되지 않을 수 있음`) |
| A007 | re:영접[하한했할함합] | 맞이하다 | AU | Y | S01 | S01 §3 3.가.2) |
| A008 | 하명 | 지시 | AU | Y | S11 | A |
| A009 | re:훈시(?!\s?규정) | 말씀, 당부 | AU | Y | S11 | A; keep the legal term `훈시 규정` |
| A010 | re:하사(?=[하한했]) | 주다, 전달하다 (`격려금을 하사하였다` -> `격려금을 전달하였다`) | AU | Y | convention | not `하사` (rank) |
| A011 | 엄금 | `~하지 마십시오` (`흡연 엄금` -> `담배를 피우지 마십시오`) | AU | Y | S11, S01 | A (`하지 말 것`); polite form: EN12 |
| A012 | re:촉수\s?엄금 | 손대지 마십시오 | AU | Y | convention | EN12 |
| A013 | re:엄[단벌] | name the legal consequence (`엄벌에 처함` -> `「○○법」 제○조에 따라 처벌받을 수 있습니다`) | AU | Y | S11, convention | A (`엄단하다` -> `엄하게 다스리다`); vague threat: G03, PH124 |
| A014 | re:의법\s?[조처][치리벌] | 법에 따라 처리, 법에 따라 처벌 | AU | Y | convention | `의법 조치`, `의법 처리` |
| A015 | 불허 | 허가하지 않음, `~할 수 없습니다` | AU | Y | S11 | A |
| A016 | re:[철정신완공][저확중벽정][을를] 기[하할해했] | `~히 하다` (`안전 관리에 철저를 기하여` -> `안전 관리를 철저히 하여`, `정확을 기하기 위해` -> `정확히 하기 위해`) | AU | Y | S01, convention | same stock form as `만전을 기할` (P116, S01); 철저, 정확, 신중, 완벽, 공정 |

## 6. Discriminatory words (X) — from 문체부 press releases
| Id | term | replacement | group | check | source | note |
|---|---|---|---|---|---|---|
| X001 | re:결손\s?가정 | 한부모가정 | DS | Y | S13 | 2007; also in S01 §3 3.나.1) |
| X002 | 미망인 | 고 ○○○의 부인 | DS | Y | S13 | 2007, 2008 |
| X003 | 귀머거리 | 청각장애인 | DS | Y | S13 | 2007 |
| X004 | 벙어리 | 언어장애인 | DS | Y | S13 | 2007 |
| X005 | 가정부 | 가사근로자 (official, S18), 가사도우미 (plain) | DS | Y | S13, S18 | 2007 (also 식모, 파출부); §7 |
| X006 | 간호원 | 간호사 | DS | Y | S13 | 2007 |
| X007 | 청소부 | 환경미화원 (street cleaning), 청소 노동자 (buildings) | DS | Y | S13 | 2007; §7 |
| X008 | 집사람 | 아내, 배우자 | DS | Y | S13 | 2007, 2008 |
| X009 | 학부형 | 학부모 | DS | Y | S13, S01 | 2007, 2008; S01 §3 3.나.1) |
| X010 | 처녀작 | 첫 작품 | DS | Y | S13 | 2008 (also 처녀항해 -> 첫 항해) |
| X011 | 편모 | 한부모 | DS | Y | S13 | 2008 (also 편부) |
| X012 | 영부인 | 대통령의 부인 | DS | Y | S13 | 2008 |
| X013 | 안내양 | 안내원 | DS | Y | S13 | 2007 |
| X014 | 잡상인 | 허가 없이 물건을 파는 사람 | DS | Y | S13 | 2007 proposes 상인 (too broad: §7) |
| X015 | 노가다 | 일용직 건설노동자 | DS | Y | S13 | 2007 |
| X016 | 시집가 | 결혼하다 | DS | Y | S13 | 2007 (`시집가다/시집갔다`) |Also: do not write personal facts the text does not need, and do not single out a group (`청소년 OOO(여, 18세)` -> `청소년 OOO(18세)`). Source: S01 §3 3.나.

## 7. When to keep a word (the replacement rule)
**Who is the reader (design decision, 2026-11-14, after critique and test).** The reader is the 수신처. If there are several 수신처 (`수신자 참조`), write for the least expert one. If the document goes to citizens, or its 공개 구분 is `공개` (the original may be posted under 「공공기관의 정보공개에 관한 법률」 제8조의2, S20), write for the general public. Never assume the 수신처 knows the sender's own office abbreviations or project nicknames.

**Core rule (design decision, 2026-11-14, after critique and test).** Keep a word as it is (a loanword, a Chinese-character word or a field term) when this reader understands it and no plain word says the same thing in this sentence. If this reader may not understand it, replace it with a plain word of the same meaning; if no such word exists, keep it and add a short gloss at first use. For a word with several senses, choose the word for the sense in this sentence. Not being native Korean is never a reason by itself. Roman letters stand only in parentheses after Hangul (`통합 인증(SSO)`, S15).
Test of the rule (14 + 6 cases, 2026-11-14): the first wording ("keep it when the meaning only comes across with it") was writer-centred and failed 7 of 14 cases (`거버넌스`, `인프라`, `테스트 베드`, `아웃리치` kept for citizens; `송달`, `해커톤` kept without a gloss; `세션` sense ignored). Judging by the 수신처 alone failed 3 of 6 (several recipients, public disclosure, Roman letters). The rule above passes all 20.

How to judge, all three required:
1. **Same meaning.** The new word is not broader, narrower or vaguer. `스타트업` is not `창업 초기 기업` (any new shop); `로그인` is not `접속`; `해커톤` is not a debate; `모멘텀` is not `국면`.
2. **Not harder for this reader.** The new word is at least as familiar to the reader defined above. Known words stay: `협조`, `회신`, `프로젝트`, `토크 콘서트`, `세미나`, `워크숍`, `포럼`, `콘텐츠`, `캠페인`, `비전`; `테스트 베드 -> 시험장` fails (read as exam hall); a field term the 수신처 uses daily stays in a document to that 수신처 (`기부채납` to a road-policy office).
3. **Same context.** Terms of law, accounting, finance, procurement and technical fields stay in documents of that field (`송달`, `기부채납`, `하는 자` (includes 법인), `내용연수`, `보합`, `차폐`); names of laws, programs, events, products and form fields stay (`규제 샌드박스`, `○○ 바우처`, 결문 `홈페이지`).

Applying it:
- A word with several senses: choose the replacement for the sense in this sentence (`세션`: `시간` or `분과`; `매칭 펀드`: `대응 자금`; `내지`: `~에서 ~까지` or `또는`; `견지`: `관점` or `굳게 지키다`). If the sense is unclear, keep the word or ask.
- A kept word the reader may not know: add a short gloss at first use: `송달(서류를 법에 따라 보내는 일)`, `해커톤(…을 짧은 기간에 함께 만드는 행사)`.
- When a law already gives a Korean term, use it: `창업기획자` (S17), `가사근로자` (S18).
- The replacement cells in §3-§6 hold only candidates that usually pass; the rule above still decides each use. Do not add a new exception row per word: a new case falls under this rule.
Basis: judgments are this skill's own (convention); no per-word data on how well each 다듬은 말 is understood exists (S19 has only survey summaries).
