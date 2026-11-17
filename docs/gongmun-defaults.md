# 공문 defaults against the official sources (M2.5)

Date: 2026-11-14. Files compared: `templates/gongmun.json` (page, styles, skeleton), `presets/report-gongmun.json`,
skill `hwpx-gongmun`, `examples/gongmun-notice/notice.json`.

## Sources (read 2026-11-14)

| id | source | what was read |
|---|---|---|
| E1 | 행정안전부 「2025 행정업무운영 편람」 (2025.12, posted 2026.01.02), https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000012&nttId=122878 | the HWPX attachment (13.0 MB; text extracted in a temp folder, not stored in the repo). §4 다 (항목 구분), §4 바 (규격 용지), §5 (문서의 구성 체계: 가 일반기안문, 나 두문, 다 본문, 라 결문), §6 다 (일반기안문 서식 and 작성방법) |
| E2 | 「행정업무의 운영 및 혁신에 관한 규정」 제7조 and its 시행규칙 (행정안전부령 제408호, 시행 2023.6.28.), as printed in the appendix of E1: 규정 제7조⑥; 시행규칙 제2조①, 제3조, 제4조, 제9조①, 별지 제1호서식 (<개정 2016. 7. 11.>), 별표 1, 별표 4 and the second table printed after it | the appendix of E1; the mirror https://www.nepla.ai/law/행정업무의-운영-및-혁신에-관한-규정-시행규칙 for the article text |

`law.go.kr` was in maintenance from 2026-11-13 21:00 to 2026-11-14 21:00 (KST), so the 시행규칙 text was not compared
with the law.go.kr page; the HWP file of 별지 제1호서식 (a binary download) was not opened. Both are open items
(see "Not verified"). The articles were read in two places (the E1 appendix and the mirror) and gave the same
sentences; they were not compared word by word.

## What the official sources state and what they do not

State: paper size (A4); the three parts of a 기안문 (두문, 본문, 결문) and their fields; the words that are not
written in the form; item symbols and 2타 steps; 붙임 and 끝 forms; the order and spelling of the 결문 fields.
Do not state for a 기안문: margins, font, font size, line spacing, line widths, paragraph spacing. The only margins,
fonts and sizes in the sources are in 별표 4 and its large-print variant, and those are the design standard of the
서식 (applications, certificates ...), not of a 기안문; the 편람 says for the body that line spacing and the spaces
above and below the items may be set freely (§4 다).

## Table

| # | item | official value (source) | ours | action |
|---|---|---|---|---|
| 1 | paper | 210 mm x 297 mm, A4, rectangle (규정 제7조⑥; E1 §4 바; 별지 제1호서식 foot line "210mm x 297mm(백상지 80g/㎡)") | A4 | OK |
| 2 | margins top / bottom / left / right | not stated for a 기안문. For 서식 only: 별표 4 = 20 / 10 / 20 / 20 mm; the large-print table = 20 / 10 / 15 / 15 mm | 30 / 15 / 20 / 15 mm, header and footer 10 mm | convention (kept) |
| 3 | body font | not stated for a 기안문 (서식: 돋움체, large print 맑은 고딕) | 휴먼명조 | convention (kept) |
| 4 | font sizes | not stated for a 기안문 (서식 별표 4: 10 pt base) | body 12, 행정기관명 22 bold, 발신명의 20 bold, 결문 9 | convention (kept) |
| 5 | line spacing, paragraph spacing | not stated; E1 §4 다: spaces above and below the items and the line spacing may be set freely, one blank line allowed | 160 %, 4 pt after | convention (kept) |
| 6 | lines (type, width) | not stated for a 기안문. The 별지 제1호서식 drawing in E2 uses solid 0.12 mm lines (informative drawing); 서식 별표 4 base 0.12 mm | 0.4 mm solid under 제목, 0.12 mm above the 결문 block | convention (kept) |
| 7 | alignment | not stated in text; the form drawing centres 행정기관명 and 발신명의 | both centred, rest left or justified | OK (convention matches the drawing) |
| 8 | 행정기관명 | the name of the agency of the drafting unit; the upper agency may be added when the name is not unique (규칙 제4조②1호; E1 §5 나 1)). Logo: left end of the 행정기관명 line, within 2 cm x 2 cm; slogan right above (E1 §5 나 4)) | `org` block, centred; no logo | OK; logo and slogan are optional and not in the template (documented in the skill) |
| 9 | 수신 | `수신` + 2타 + recipient + (처리 보조·보좌기관) in parentheses; many recipients: `수신자 참조`; none: `내부결재` (규칙 제4조②2호) | `수신  ○○○○(○○○○과장)` | OK |
| 10 | (경유) | blank when there is none; fixed sentences for one or more 경유 agencies (E1 §5 나 3)) | `(경유)` | OK |
| 11 | 제목 | `제목` + 2타 + short and clear (규칙 제4조③; E1 §5 다 1)) | `제목  ○○○○ ○○ 알림` | OK |
| 12 | 관련 문서 | agency name + 생산등록번호, then in parentheses the date and the title, then `호`: example `○○부 ○○○과-123(2025. 9. 20., “○○ 행사 관련 협조 요청”)호` (E1 §5 다 2)) | `관련: ○○○과-○○○(2026. ○. ○.)` | fixed: placeholder follows the example (agency name, title in quotation marks, `호`) in the template and the example |
| 13 | item symbols | `1.` `가.` `1)` `가)` `(1)` `(가)` `①` `㉮`; first level at the left base line, each next level 2타 to the right; one 1타 between symbol and text; one item only: no symbol; wrapped lines under the first letter of the text (rule) or at the base line, one way in a document; after `하` comes `거` ... (규칙 제2조①; E1 §4 다) | classes `l1` ... `l8`: left = 12 pt per level (2타 = one 한글 char = the 12 pt font size), hanging indent = measured mark width | OK |
| 14 | special marks | `□ ○ - ㆍ` when needed (규칙 제2조①; the rule text writes `ㆍ` as U+318D) | report preset marks `□ ○ - ·` (U+00B7) | OK (same marks; the dot code point differs and renders alike, kept) |
| 15 | 붙임 | after the last body line, directly or after one blank line; name and quantity; one: `붙임  ○○○계획서 1부.  끝.`; several: `붙임  1. ... 1부.` then `2. ... 1부.  끝.` (규칙 제4조④; E1 §5 다 3)) | `attach` and `attach_next` | OK |
| 16 | 끝 | 1 char (2타) after the last character, or after the last 붙임 line; at the right limit: next line, 1 char from the left base line; table end: below the table, or `이하 빈칸` in the next cell (규칙 제4조⑤; E1 §5 다 4)) | skill step 3 | OK |
| 17 | 발신명의 | the agency head, or the unit head for internal documents; none for an internal approval; `관인생략` / `서명생략` right of it (별표 1; E2 별지 작성방법 13) | `sender` block, centred, 20 pt bold; no 관인생략 mark | OK; the mark is optional, documented in the skill |
| 18 | 수신자란 (several recipients) | a separate line below the 발신명의, at the left base line (규칙 제4조②; E1 §5 나 2) 마)) | none in the template (only in the example) | fixed: optional `수신자` line added after 발신명의 |
| 19 | 기안자 / 검토자 / 협조자 / 결재권자 line | position or grade and signature only; the words 기안자, 검토자, 결재권자, `직위(직급) 서명` are not written; for 협조자 the word `협조자` is written, then position and signature; 전결 / 대결 marks in the signature cell (별지 제1호서식 비고; E1 §5 라 3)) | `기안자 ○○ ○○○    검토자 ... 결재권자 ...`; no 협조자 line | fixed: template line is `주무관 ○○○    ○○팀장 ○○○    ○○과장 ○○○`; `협조자 ○○ ○○○` line added; the example gets a 협조자 line with a name instead of an empty label |
| 20 | 시행 / 접수 | `시행 처리과명-연도별 일련번호(시행일)` and `접수 처리과명-연도별 일련번호(접수일)`; dates as numbers with full stops; hours and minutes for 민원 documents (별지 제1호서식 작성방법 7) | `시행 ○○○과-○○○ (2026. ○. ○.)    접수` | fixed: no space before the parenthesis; `접수` stays empty on the sending side |
| 21 | 우편번호, 주소, 홈페이지 | `우` + postal code + road address (+ building, floor, room in parentheses) / 홈페이지 address, example `www.mois.go.kr` (작성방법 8, 9). The note says the label words `도로명주소`, `홈페이지 주소` are not written | `우 ○○○○○  ○○시 ○○로 ○○ / 누리집 주소` | fixed: placeholders are an address with building and floor and a web address instead of the label words. The rule example writes `우30112` with no space; the form has `우` and the code in two cells, so the space is kept (convention) |
| 22 | 전화, 팩스 | labels `전화번호( )` and `팩스번호( )`, area code in parentheses, example `(044)205-0000`; internal documents may use the in-house number (작성방법 10) | `전화 ... 전송 ...` | fixed: labels `전화번호`, `팩스번호` (`전송` is not the official word), values in the form `(○○)○○○-○○○○` |
| 23 | 전자우편주소 | the address the agency gave to the civil servant (작성방법 11); the label words are not written | `전자우편` (a label) | fixed: placeholder is an address `○○○@○○○.go.kr` |
| 24 | 공개 구분 | `공개`, `부분공개( )`, `비공개( )`; the number of the 정보공개법 제9조제1항 clause in the parentheses (작성방법 12) | `공개`; example had `대시민 공개` | fixed in the example (`공개`); the template already had `공개` |
| 25 | 결문 font and size | not stated | 맑은 고딕 9 pt, 140 % | convention (kept) |
| 26 | 쪽 번호, header, footer | not stated for a 기안문 | none | convention (kept) |
| 27 | 개조식 보고서 preset `report-gongmun` | the sources define no 보고서 layout (the 편람 names the 간이기안문, 별지 제2호서식, for internal reports without a recipient) | A4, margins 20 / 15 / 20 / 20 mm, 함초롬 fonts, sizes and colours from the HTML design the preset was made from | convention (kept); not an official form |

Rows 12, 18, 19, 20, 21, 22, 23 and 24 changed files; the rest only record the comparison.

## Fixed in the repository

- `templates/gongmun.json`: 결문 block follows rows 18-23; 관련 line follows row 12.
- `examples/gongmun-notice/notice.json` and the `notice.hwpx`, `page1.png` built from it: same fixes.
- `skills/hwpx-gongmun/SKILL.md`: what is official and what is convention; the optional blocks; this table.
- New package `lib/hwpx_docs/gongmun/` (`hd gongmun-check <spec.json>`, rules GM01-GM05): checks the label words, 2타,
  전화번호/팩스번호 and the 시행 line of any 공문 spec. Its self-test (`hd selftest`, "gongmun") runs the check on the
  template and the example and builds them, so a change of the template that drops an official form fails there.
  The defaults stay data (`templates/gongmun.json`, this table); a fix of one touches that file and the package only.

## Not verified

- The 시행규칙 article text against the law.go.kr page (the site was in maintenance).
- The HWP file of 별지 제1호서식 on law.go.kr (binary; margins stored in it, if any, are unknown).
- The 2011 and older 편람 editions (old values of the 기안문 margins, if they ever stated any).
