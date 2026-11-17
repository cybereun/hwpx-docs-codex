# notation.md — date, time, money, numbers, units, punctuation

Rule ids `N01...` are used by `scripts/check_gongmun.py`. Source ids (S01...) are in `sources.md`.
"convention" = no official source states it. "(1 source)" = only one source found.
Law name: 「행정업무의 운영 및 혁신에 관한 규정」 (규정 = S03), its 시행규칙 (S02), 「2025 행정업무운영 편람」 (S01), 한글 맞춤법 문장 부호 (S05), 국립국어원 온라인가나다 (S06).

| Id | Rule | Good | Bad | Source |
|---|---|---|---|---|
| N01 | Use Arabic numerals in documents unless there is a special reason. | `3개`, `2026` | `삼 개` | S03 제7조④, S01 §4 가.1) |
| N02 | Date: numerals, drop 연·월·일, put a period after each part (including the last one). One space after each period. No leading zero in month and day. | `2026. 11. 14.` | `2026년 11월 14일`, `2026.11.14.`, `2026. 11. 14`, `2026. 11. 04.` | S03 제7조⑤, S01 §4 가.2) and §3 나.9), S05 마침표 |
| N03 | Weekday: in parentheses right after the last period, no space. | `2026. 11. 14.(토)` | `2026. 11. 14. (토)` | S01 §3 나.9), S06-Q4 |
| N04 | Time: 24-hour clock, numerals, drop 시·분, put a colon between hour and minute, no spaces. Two digits for the hour (S01 shows `07:09`). | `14:00`, `07:09` | `오후 2시`, `2:00 PM`, `14 : 00` | S03 제7조⑤, S01 §4 가.3), S05 쌍점 |
| N05 | Date and time together: one space between the date and the time. | `2026. 11. 14. 14:00` | `2026. 11. 14.14:00` | convention (S06-Q2 says the rule is not explicit; word-unit spacing) |
| N06 | Range mark `~`: attach to both sides. A short second date is fine. | `2026. 11. 14.~11. 20.`, `14:00~16:00` | `2026. 11. 14. ~ 11. 20.` | S01 §3 나.8), S05 물결표, S06-Q3 |
| N07 | Money: Arabic numerals, then the amount in Hangul in parentheses. Write `금` before the number. No space inside. How to write the Hangul amount: read the number by 만 groups (억, 만, then the rest) and write each digit with its place (천, 백, 십); write `일` for a 1 in any place, as the official example does (`일십일만`). Use it where a formal amount is needed (contracts, payments, budgets in 기안문); for the public in running text write `2,134만 5천 원` (G46). | `금113,560원(금일십일만삼천오백육십원)`, `금1,250,000원(금일백이십오만원)` | `금 11만 3,560원`, `113,560원` (when a formal amount is needed), `금21,345천원` | S02 제2조②, S01 §4 가.4); writing `일` before every place: derived from the S02 example |
| N08 | Colon `:` attaches to the word before it and has one space after it (label: value). No space before it. | `일시: 2026. 11. 14.` | `일시 : 2026. 11. 14.` | S01 §3 나.8), S05 쌍점, S06-Q5 |
| N09 | Parentheses attach to the word before; the opening mark attaches to the next word. A particle follows the last letter before the bracket. | `인공지능(AI)을`, `19일(토)은` | `인공지능 (AI)` | S05 괄호, S01 §3 |
| N10 | Use parentheses for a foreign word or Chinese characters only when it is needed to give the meaning. | `인공지능(AI)` first use | repeated at every use | S03 제7조① |
| N11 | 가운뎃점 `ㆍ` joins words of equal rank, no spaces. Do not use it inside a word that is in the dictionary as one word. | `상ㆍ중ㆍ하위권`, `국내외`, `시도`, `민관`, `초중고`, `출퇴근` | `국내ㆍ외`, `시ㆍ도`, `초ㆍ중ㆍ고` | S05, S01 §3 가운뎃점 table. The 규정 uses `ㆍ` (U+318D), the 편람 uses `·` (U+00B7); both are accepted, use one in a document (convention) |
| N12 | Quotation marks: “ ” for a direct quote or a title of a related document; ‘ ’ for a quote inside a quote or a thought. Opening mark attaches to the next word. | `“○○ 행사 관련 협조 요청”` | `"..."` mixed with `“ ”` in one document | S05 따옴표, S01 §5 다.2); one style per document: convention |
| N13 | Unit nouns after a number. After a number with a Hangul number unit (만, 천, 억) or with `-여`, space the unit noun: `296억 달러`, `10만 톤`, `3천 명`, `23만 개`, `50여 명`, `60여 개국`. After plain Arabic digits it may attach (한글 맞춤법 제43항 다만): `28건`, `15세`, `108명`, `50회`, `2대`; money `금113,560원(…)` and 붙임 quantities `1부` stay attached. Use one form per document. | `10만 톤`, `3천 명`, `총 28건`, `108명`, `계획서 1부.` | `10만톤`, `3천명`, `50여명`, `1 부` in one place and `1부` in another | S01 §3 나.3), S05 제43항, S06-Q7 |
| N14 | A Hangul numeral and its unit noun are written with a space. | `열 개`, `삼십 cm` | `열개` | S05 제43항, S06-Q7 |
| N15 | Big numbers in Hangul words are spaced by 만 unit (제44항). In Arabic numerals, use a comma every 3 digits for money. | `금113,560원` | `금113560원` | S05 제44항 (Hangul form); comma for money: S02 제2조② example |
| N16 | `-` (붙임표) links related terms or a number sequence, no spaces. | `원-달러 환율`, `○○-123` | `원 - 달러` | S05 붙임표 |
| N17 | Ellipsis: six dots `……` in principle; `…` or `...` allowed. Attach to the word before. | `…` | – | S05 줄임표 |
| N18 | Paper size A4: 210 mm × 297 mm. | – | – | S03 제7조⑥ |
| N19 | Names: `.` is 마침표 (온점 also allowed), `,` is 쉼표 (반점 also allowed). The 규정 text still says 온점. | – | – | S05, S03 |

## Notes
- The 편람 itself has small slips (one sample date `2025. 9.20.`). Follow the rule text, not the slip. [S01]
- `~` spacing: S05 gives `9월 15일~9월 25일`; S01 §3 나.8) and S06-Q3 say attach. Some guides show a spaced form; do not use it.
- Special reason for another date style: S03 제7조⑤ allows it ("특별한 사유가 있으면 다른 방법으로 표시할 수 있다"). General register docs (not 공문) may use `2026년 11월 14일`.
- Not covered by any source found: 연호 form, 이상/이하 after unit, 취소선 (strikethrough).
