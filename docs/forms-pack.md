# Forms pack format (add-on plugin `hwpx-docs-forms`)

A forms pack holds the layout rules of one family of official forms (for example the 별지 서식 of laws) as data.
It is not a copy of one form. The rules are measured on real forms (with a measuring tool outside this repository); each rule carries its
evidence as `n/N` (n forms follow it, out of N measured). The user picks a pack for one document. No pack is applied
by default, and the core plugin has no form-specific code.

## 1. Where things live

```
addons/hwpx-docs-forms/            the add-on plugin (installed on its own)
  .claude-plugin/plugin.json
  skills/hwpx-forms/SKILL.md       when to use, how to give a pack to `hd`
  scripts/pack.py                  apply | list | check | selftest (stdlib only, no import of the core)
  packs/<pack>/
    pack.json                      manifest: name, about, sample size, rules with evidence
    preset.json                    values: page, defaults, styles, tokens, optional
    parts.json                     parts: parameterised spec pieces
    pagefit.json                   optional pagefit profile for this pack
```

The core already takes a preset or a profile by path: `hd md --preset <file.json>` and
`hd pagefit ... --profile <file.json>`. A pack therefore needs no change in the core. The two things the core
cannot do (merge a preset into a JSON spec; expand parts) are done by `scripts/pack.py`, which writes an ordinary
spec. Then `hd build` runs as always.

```
python scripts/pack.py apply spec.json packs/<pack> -o full.json [--with opt1,opt2]
hd build full.json out.hwpx
hd pagefit fix out.hwpx fitted.hwpx --profile packs/<pack>/pagefit.json     # optional
```

## 2. `preset.json`

Keys of a spec base. Units as in `docs/spec.md` (mm for the page, pt for text).

| key | meaning |
|---|---|
| `page` | spec `page`: `size`, `landscape`, `margin` (left right top bottom header footer) |
| `defaults` | spec `defaults`: font, size, align, line |
| `styles` | named styles (`"class": "label"`): `title`, `formno`, `label`, `value`, `note`, `th`, `td` ... |
| `tokens` | named values for `${name}` in parts and in the spec: `label_fill` (name-cell shading), `line_thin`, `line_main`, `line_thick` (line widths), `formno_line` (style of the 서식 번호 line), `cell_pad` ... |
| `optional` | `{name: overlay}`: an overlay has the same keys (`page`, `defaults`, `styles`, `tokens`) and applies only with `--with name`. A rule that fewer than half of the forms follow lives here |

Merge order: the pack's `preset.json`, then the chosen overlays, then the spec itself. The spec always wins, key by
key (`page.margin.left` in the spec beats the pack). `page`, `defaults`, `styles` and `tokens` merge by key.

## 3. `parts.json`

A part is a spec piece with parameters.

```json
{
  "applicant-table": {
    "about": "신청인 table: 성명, 생년월일, 주소, 전화번호",
    "params": {"title": "신청인", "rows": 3, "name": null},
    "body": [{"table": {"cols": [24, 66, 24, 56], "border": "${line_thin}",
                        "rows": [[{"p": "${title}", "rs": 3, "fill": "${label_fill}", "align": "center"},
                                  {"p": "성명"}, "${name}", {"p": "(서명 또는 인)"}]]}}]
  }
}
```

- `params`: name -> default. `null` = required (a missing value stops with the name).
- `body`: one block or a list of blocks, spliced into the list where the part is used.
- Use a part anywhere a list of blocks is allowed (body, cell `blocks`, header, text box):
  `{"part": "applicant-table", "args": {"name": "홍길동"}}`.
- `${name}`: a string that is exactly `${name}` becomes the value of any type (number, list, object); inside a longer
  string it is text. Look-up order: part `args` and `params`, then `tokens`. An unknown name stops the build.
  `$${` is a literal `${`. Parts can use parts (depth 8).
- Part names (first pack): `receipt-box` (접수 칸: 접수번호, 접수일, 처리기간), `applicant-table` (신청인),
  `signature-line` (`년 월 일` + 신청인 + `(서명 또는 인)`), `to-address` (`○○○ 귀하`), `process-box` (처리 절차
  flow), `fee-box` (수수료), `paper-line` (`210mm×297mm[백상지 80g/㎡]`). A pack includes only parts that the
  measurement supports.

## 4. `pack.json` and the evidence rule

```json
{
  "name": "law-forms",
  "about": "별지 서식 of laws (law.go.kr), measured on 150 blank forms",
  "sample": {"forms": 150, "source": "law.go.kr flDownload, 2026-11-16", "measured": "a measuring tool outside this repository"},
  "rules": [
    {"id": "page.size", "path": "page.size", "value": "A4", "evidence": "142/150", "status": "default"},
    {"id": "table.label-fill", "path": "tokens.label_fill", "value": "#F2F2F2", "evidence": "61/120", "status": "default"},
    {"id": "page.margin.top", "path": "optional.tight.page.margin.top", "value": 10, "evidence": "52/150", "status": "optional"}
  ]
}
```

- `evidence` is `n/N`. A `default` rule needs `n*2 >= N`. A rule below half is `optional` (it lives under
  `preset.json` `optional`) or is left out. `pack.py check` stops on a violation.
- `path` points to the value in `preset.json`, so `check` also stops when the value and the manifest differ.
- A part is a rule too (`"id": "part.receipt-box"`): the evidence is the number of forms that have the part.
- Truth for a pack is the original .hwp: a form rebuilt from a spec with the pack is compared with the original
  .hwp page images (page count, ink difference per page). The pack is right when the pack result is closer to the
  original than the result without it, or equal.

Limit of a part: it is a table (or paragraph) of its own. In an official form the same parts are often rows of one
large grid, so a part gives the family's look (labels, lines, words) but not the exact grid of one form.

## 5. How a pack is made and checked

`addons/.../scripts/pack.py check <pack dir>` checks a pack: the evidence rule, path/value agreement, parts exist. The rules of a pack are counted on real forms and every `n/N` comes from that count, none is typed; that counting and the rebuild test below were done with a measuring tool outside this repository.

The rebuild test starts from the original .hwp read as a spec, keeps only the content (grid, merges, text, alignment) and
takes out what the pack claims (margins, face names, label fill, line widths, size and bold of the title and of the
서식 번호 line). `nopack` puts back the builder defaults; `pack` marks the roles (`title`, `formno`, `label`) and the
line tokens and merges the pack. Truth = Hangul's render of the original .hwp.

## 6. Commands of `scripts/pack.py`

| command | result |
|---|---|
| `apply <spec.json> <pack dir> -o <out.json> [--with a,b]` | merged and expanded spec (an ordinary spec for `hd build`) |
| `list <pack dir>` | one line per rule: `<id> <value> <n>/<N> <status>`; last line `PACK <name> <k> rules` |
| `check <pack dir>` | manifest and files agree, evidence rule holds, every used part exists; `PACK OK <name>` |
| `selftest` | expands a sample part and merges a sample preset; `PACK SELFTEST PASS` |

## 7. Core change

None. A pack is passed by path (`--preset`, `--profile`) or through `pack.py`. If the core takes a `--parts`
option later, it will be generic (a parts file by path) and have no form words.
