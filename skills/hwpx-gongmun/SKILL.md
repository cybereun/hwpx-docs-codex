---
name: hwpx-gongmun
description: Korean official documents as HWPX — 공문 (기안문, 시행문, 내부결재) from a data template with the 행정업무운영 편람 item levels, and 개조식 보고서 from Markdown. Use for 공문 만들기, 기안문, 시행문, 공고문, 보도자료, 통지서, 개조식 보고서를 한글 파일로. Text rules come from skill gongmun-style.
---

# 공문 and 개조식 보고서

`hd` = `python "${skillRoot}/lib/hd.py"`. Layout only: the wording, item symbols, dates, 붙임 and `끝.`
follow skill gongmun-style (`${skillRoot}/skills/gongmun-style/`). Check the text with
`python "${skillRoot}/skills/gongmun-style/scripts/check_gongmun.py" <text file>`.

## 공문 (기안문, 시행문, 내부결재)

1. Copy `${skillRoot}/templates/gongmun.json` (A4, top 30, bottom 15, left 20, right 15 mm; named styles;
   a skeleton body). Replace every ○○ and delete the blocks that you do not need: the `수신자` line only stays with
   `수신자 참조`, the `협조자` line only with a 협조자. Official: the A4 size, the fields and their order, the label
   words. Convention (the 편람 states no margin, font, size or line value for a 기안문): margins, 휴먼명조 12 pt,
   the sizes and lines. The table is `${skillRoot}/docs/gongmun-defaults.md`.
2. Items: one block per item with `"class": "l1"` ... `"l8"` and the symbol written in the text:
   L1 `1.` L2 `가.` L3 `1)` L4 `가)` L5 `(1)` L6 `(가)` L7 `①` L8 `㉮` (levels.json). Each level starts 2타 further
   right; wrapped lines align to the first letter of the item text (the class indents are measured for 휴먼명조
   12 pt; for another font or size measure `hd textwidth "가. " --font <face> --size <pt>` and set `indent`).
   A level with one item has no symbol. 가나다... continues with 거너더... after 하.
3. 붙임 and `끝.` (levels.json A1-A2, E1-E6): `끝.` goes 2 spaces after the last text; with 붙임 after the last
   붙임 line; after a table whose last cell is filled, on its own line below the table; a table that ends early
   gets `이하 빈칸` in the next cell and no `끝.`.
4. 결문 (closing block), official order and words: 발신명의 (centred; `관인생략` or `서명생략` may stand right of it), `수신자`
   line, then `직위 이름` for each signer WITHOUT the words 기안자, 검토자, 결재권자 (`협조자 직위 이름` keeps its word;
   `전결` or `대결` go in the signer's cell), `시행 처리과명-연도별 일련번호(시행일)    접수 ...(접수일)`, `우 우편번호 도로명주소 /
   홈페이지`, `전화번호 (지역번호)...  팩스번호 (지역번호)... / 전자우편주소 / 공개` (`공개`, `부분공개( )` or `비공개( )` with the
   정보공개법 제9조제1항 clause number). Not in the template and optional: the agency logo (2 cm x 2 cm, left end of the
   행정기관명 line) and a slogan right above it.
5. `hd gongmun-check spec.json` (official fields and wording, GM01-GM05), `hd build`, `hd readability`, render (skill
   hwpx-core), check the text with check_gongmun.py.

Hangul-made 공문 samples to read as a start (`hd read <file> spec.json`): `${skillRoot}/tests/fixtures/`
`gongmun.hwpx` (기안문), `gongmun_sihaeng.hwpx` (시행문, several 수신), `gongmun_gyeoljae.hwpx` (결재란),
`gongmun_gongo.hwpx` (공고문), `gongmun_bodo.hwpx` (보도자료), `gongmun_tongji.hwpx` (통지서).

## 개조식 보고서

Markdown -> `hd md report.md report.hwpx` (preset `report-gongmun`: title box, chapter bars, □ ○ - · items, grid
tables). Markdown subset and presets: skill hwpx-text (`references/presets.md`).
