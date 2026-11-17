---
name: hwpx-readability
description: Make an HWPX easier to read across pages on request - no turning back to finish an item, tables not cut, full pages (읽기 좋게, 쪽 넘김 줄이기, 표 안 끊기게, 가독성, 쪽 꽉 차게). Not part of normal document creation.
---

# HWPX readability (pagefit)

`hd` = `python "${skillRoot}/lib/hd.py"`. Use it only when the user asks for it ("읽기 좋게", "쪽 넘김 줄이기", "표 안 끊기게",
"가독성", "쪽 꽉 차게"). Never run it after a normal build (md2hwpx, hd build) on your own: this is the user's reading style.

## Profile = the style

| profile | what it does |
|---|---|
| `readable` | use this for the requests above: reading units (heading + first content, item + sub items, table or figure with caption / introduction / notes, summary box, 붙임, last paragraph + 끝. + 결문) stay on one page; a long table is cut between rows with the header repeated and 3 rows at least in each part; pointers ("표 3 참조", page numbers) and footnotes that go on are reported; free space goes into paragraph and table spacing; a page break always goes before the heading and introduction that keep with a table (Hangul does not carry a heading over a break); a table of a third of a page or more that would leave 40 mm or more empty above it is cut between rows (header repeated) instead of moved whole; fixed row heights stay (freeing them made text lines overlap in Hangul) |
| `minimal` | the least change (heading keeps with the next paragraph, no single lines, forced breaks after a mostly empty page, short last page); what `hd pagefit` does with no `--profile` |
| own file | `--profile my.json`: copy `lib/hwpx_docs/pagefit/profiles/readable.json`, keep `"extends": "readable"` and write only the keys that change (format: `lib/hwpx_docs/pagefit/profile.py`); `hd pagefit profiles [name]` prints a profile in full |

Ask the user once whether they have their own profile file; if not, use `readable`.

## Steps

1. Check: `hd pagefit check <file.hwpx|spec.json> --profile readable`. Show the findings (page numbers, what makes the reader turn the page, how empty a page is) in the user's language.
2. Fix into a NEW file, never over the original: `hd pagefit fix <in> <out.hwpx> --profile readable` (prints before, the changes, after). Text, text size and the order of the content never change; only keep flags, page breaks and paragraph / table spacing do.
3. Check in Hangul when it is installed: `hd render hwpx <out.hwpx> <dir>` (hidden Hangul, one batch) and compare the page count with the one `fix` printed. The page layout of `pagefit` follows Hangul within 1 mm on the documents measured; footnote pages are less exact.
4. Report what is left: a page that stays empty (a unit that does not fit the free space), a sentence that points at a table on another page, a pointer to a page number ("3쪽", "다음 쪽": the numbers may have moved), a footnote that goes on, a table without header rows. These need the user's decision, not a bigger change.

Limits: vertical-writing sections are skipped; the preview, not Hangul, computes the pages (steps 1-2), so step 3 is the proof.
