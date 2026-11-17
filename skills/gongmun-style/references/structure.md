# structure.md — 공문 structure, item symbols, "끝." marks

Stable ids. Other skills (for example the HWPX skill) refer to these ids by name. Do not rename them.
Source ids (S01...) are in `sources.md`. "convention" = no official source states it.
Law name: the 규정 is now 「행정업무의 운영 및 혁신에 관한 규정」 (old name: 「행정 효율과 협업 촉진에 관한 규정」). Same for its 시행규칙.

## 1. Blocks of a 기안문 (공문)  [S01 §5, S02 제4조①~⑥]
Rule: "기안문은 두문, 본문 및 결문으로 구성한다." (S02 제4조①)

| Block id | Part | Content | Rule / source |
|---|---|---|---|
| HEAD_ORG | 두문 | 행정기관명 (organization name, top) | S02 제4조②, S01 §5 |
| HEAD_RECIPIENT | 두문 | 수신란: `수신  ○○○장관(○○○과장)`; no recipient: `수신  내부결재`; many: `수신  수신자 참조` and list the 수신자 in TAIL_SENDER area | S02 제4조②, S01 §5 나.2) |
| HEAD_VIA | 두문 | (경유): blank if none. One: "이 문서의 경유기관의 장은 ○○○이고 최종 수신기관의 장은 ○○○입니다." | S01 §5 나.3), S03 제15조 |
| BODY_TITLE | 본문 | 제목: short and clear, so the reader knows the content. Layout `제목  ○○○` | S01 §5 다.1) |
| BODY_CONTENT | 본문 | 내용: opening sentence, then the item list (BODY_ITEMS) | S01 §5 |
| BODY_ITEMS | 본문 | 항목 list (section 2) | S02 제2조① |
| BODY_ATTACH | 본문 | 붙임 lines (section 4) | S02 제4조④ |
| BODY_END | 본문 | "끝." mark (section 3) | S02 제4조⑤ |
| TAIL_SENDER | 결문 | 발신 명의 (organization head) | S02 제4조⑥ |
| TAIL_SIGN | 결문 | 기안자, 검토자, 협조자, 결재권자: 직위(직급) and signature | S02 제4조⑥ |
| TAIL_NUMBERS | 결문 | 생산등록번호, 시행일, 접수등록번호, 접수일 | S02 제4조⑥ |
| TAIL_ADDRESS | 결문 | 우편번호, 주소, 홈페이지 | S02 제4조⑥ |
| TAIL_CONTACT | 결문 | 전화, 팩스, 전자우편, 공개 구분 | S02 제4조⑥ |

Order of blocks: HEAD_ORG, HEAD_RECIPIENT, HEAD_VIA, BODY_TITLE, BODY_CONTENT (with BODY_ITEMS), BODY_ATTACH, BODY_END, TAIL_*. (BODY_END follows the last text of BODY_CONTENT or BODY_ATTACH.)
Related document in the body: `○○부 ○○○과-123(2025. 9. 20., “○○ 행사 관련 협조 요청”)호`. [S01 §5 다.2)]

## 2. Item-symbol levels  [S02 제2조①, S01 §4 다]
Rule: order `1. → 가. → 1) → 가) → (1) → (가) → ① → ㉮`. First item starts at the left base line (왼쪽 기본선). Each next level moves 2타 to the right of the level above. "2타 = 한글 1자 = 영문·숫자 2자 = 스페이스 2번". One 1타 space between the symbol and the item text. [S01 §4 다]

| Level id | Symbol (first item) | 2nd item | Indent (타) | Indent (한글 chars) | Indent (em, derived) | Source |
|---|---|---|---|---|---|---|
| L1 | `1.` | `2.` | 0 | 0 | 0 | S01 §4 다, S02 제2조① |
| L2 | `가.` | `나.` | 2 | 1 | 1 em | same |
| L3 | `1)` | `2)` | 4 | 2 | 2 em | same |
| L4 | `가)` | `나)` | 6 | 3 | 3 em | same |
| L5 | `(1)` | `(2)` | 8 | 4 | 4 em | same |
| L6 | `(가)` | `(나)` | 10 | 5 | 5 em | same |
| L7 | `①` | `②` | 12 | 6 | 6 em | same |
| L8 | `㉮` | `㉯` | 14 | 7 | 7 em | same |

- The official unit is 타 (character cells), not pt or mm. Indent in pt or mm = (number of 한글 chars) × (font size in pt). This formula is derived from "2타 = 한글 1자"; no source gives a pt or mm value. Mark as **convention (derived)**.
- Inside one Hangul level, after the 14th item (하., 하), (하), ㉻) continue with 거., 거), (거) ..., then 너. ... (S02 제2조①). This is about the number of items in a level, not about levels deeper than L8.
- Special symbols `□ ○ - ㆍ` are allowed "필요한 경우" (S02 제2조①). Do not use symbols that are hard to type or convert electronically (S01 §4 다).
- One item only: do not write an item symbol. [S02 제2조①, S01 §4 다]
- Item text that wraps: align the 2nd line to the first letter of the item text (원칙), or start at the left base line (무방). Use one way in the whole document. [S01 §4 다]
- A blank line between the opening sentence and the first item is allowed. [S01 §4 다 example]
- Item style `항목명: 내용` (for example `일시: 2026. 11. 14. 14:00`) is the form in the S01 examples. [S01 §4 다 example]

## 3. "끝." mark cases  [S02 제4조⑤ (amended 2021.1.21), S01 §5 다.4)]
Rule text writes "끝" without a period; the S01 examples write "끝." Use "끝." (S01 examples). "한 글자 띄우고" = 2타 (S01) = two spaces.

| Case id | Situation | Where to write "끝." | Example | Source |
|---|---|---|---|---|
| E1 | Body ends with text (no 붙임) | After the last character, 2 spaces, then `끝.` | `…주시기 바랍니다.  끝.` | S02 제4조⑤, S01 |
| E2 | Last line reaches the right limit | Next line, at the left base line, 2 spaces, then `끝.` | `  끝.` | S02 제4조⑤ |
| E3 | Body ends with a table and the last cell is filled | Below the table at the left base line, 2 spaces, then `끝.` | `  끝.` | S02 제4조⑤ |
| E4 | Table ends before the last row or cell | No `끝.`. Write `이하 빈칸` in the cell after the last filled cell | `이하 빈칸` | S02 제4조⑤ |
| E5 | The document has 붙임 | `끝.` goes after the 붙임 line (last 붙임 item), not after the body | `붙임  1. 계획서 1부.` / `2. 서류 1부.  끝.` | S02 제4조⑤ |
| E6 | Draft by 문서관리카드 | `끝.` may be omitted | – | S02 제21조 |

## 4. 붙임 (attachment)  [S02 제4조④, S01 §5 다.3)]
Rule: after the last line of the body, write `붙임`, then the name and quantity of each attachment. Two or more attachments: separate them with item symbols (S02 제2조①).

| Case id | Situation | Form (∨ = 1타) | Source |
|---|---|---|---|
| A1 | One attachment (no number) | `붙임∨∨○○○계획서 1부.∨∨끝.` | S01 §5 다.3) |
| A2 | Two or more attachments | `붙임∨∨1.∨○○○계획서 1부.` then next line `2.∨○○○서류 1부.∨∨끝.` (2nd line aligned under the first item) | S01 §5 다.3) |

- 붙임 comes right after the body or after one blank line (both allowed in S01).
- No colon after 붙임 in the S01 examples. Secondary blog (not official) says the same.
- "별첨" is in no official source. Use only "붙임".

## 5. 수신, 경유, 제목 (short form)
| Field | Rule | Example | Source |
|---|---|---|---|
| 수신 | 수신 + 2 spaces + recipient + (처리 부서) in parentheses | `수신  행정안전부장관(정보공개과장)` | S02 제4조②, S01 §5 나.2) |
| 수신 (no recipient) | `수신  내부결재` | – | S01 §5 나.2) |
| 수신 (many) | `수신  수신자 참조`; list in 결문 | – | S01 §5 나.2) |
| 경유 | blank if none | see HEAD_VIA | S01 §5 나.3) |
| 제목 | `제목  ○○○`; short and clear; no sentence end period | `제목  2026년 문서관리 교육 계획 알림` | S01 §5 다.1); no-period: convention |

Layout beyond these rules (fonts, sizes, borders, margins): not stated here. See the HWPX skill.
