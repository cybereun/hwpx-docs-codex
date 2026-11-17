# HWPX and HWP side by side

Every task has one command for `.hwpx` and the same command for `.hwp` (HWP 5.0, the binary format). `hd` is `python lib/hd.py`.
Checked on real files (`hd selftest` covers the code paths; the real-file lines are in the table).

How a `.hwp` reaches a command that was made for `.hwpx`:

1. **Direct**: the command has a `.hwp` twin in `hd hwp ...` and `hd` runs it: `text`, `slots`, `edit`, `guard`, `read` (spec), `preview`.
   `hd edit in.hwp out.hwp` changes only the text and keeps every other byte of the file.
2. **Route**: `.hwp` -> temporary HWPX (`hd hwp tohwpx`) -> the `.hwpx` command -> a new `.hwp` (`hd hwp fromhwpx`). Used for `build`, `md`, `html`
   (an output named `.hwp`), `form fill`, `pagefit`, `readability`, `check`, `diff`, `secure --mask-private` and `text --md`. There is no second
   builder: the route reuses the same HWPX code. Nothing is written when the route stops, and it stops in two ways:
   - `UNSUPPORTED <what> <where>`: `tohwpx` or `fromhwpx` has no mapping for that element or value (a kind no tested file shows). The message and the exit code are the ones of `hd hwp tohwpx` / `hd hwp fromhwpx`.
   - `ERROR tohwpx|fromhwpx <ExceptionName>: <text>` (exit 3): the converter raised an exception. That is a bug, not a missing mapping: report it with the file.

| task | `.hwpx` | `.hwp` | how |
|---|---|---|---|
| make a new document | `hd build`, `hd md`, `hd html` (output `.hwpx`) | the same with an output named `.hwp`; `hd hwp build spec.json out.hwp` | route |
| read text, Markdown | `hd text in.hwpx [--md]` | `hd text in.hwp [--md]` | direct, route |
| list slots (paragraphs, cells, labels) | `hd slots` | `hd slots in.hwp` | direct |
| read as a spec (JSON) | `hd read` | `hd read in.hwp out.json` (exact: `hd hwp tohwpx`, then `hd read`) | direct |
| change text, fill a form, 누름틀, replace | `hd edit` | `hd edit in.hwp out.hwp` | direct |
| tick a check box written as ☐ | `hd edit --check 라벨` | the same | direct |
| fill form objects (check box, radio, combo) | `hd form fill` | `hd form list` works; `hd form fill` writes the check boxes, radio buttons and lists through `fromhwpx` (checked: `hd form fill check_button/from.hwp out.hwp --set CheckBox1=0`, then `hd form list out.hwp`); only an object or value that no file has shown stops with `UNSUPPORTED <element>` | route |
| add a paragraph, a row, a cell | `hd read` -> change the JSON -> `hd build` | `hd hwp tohwpx`, `hd read`, change, `hd build s.json out.hwp` | route |
| check the form after editing | `hd guard` | `hd guard a.hwp b.hwp` | direct |
| page pictures | `hd preview`, `hd render hwpx` | `hd preview in.hwp`, `hd hwp render [--backend hangul]` | direct |
| compare pages before and after | `hd render side`, `hd img compare` | `hd hwp compare a.hwp b.hwp dir` | `hd hwp` |
| fit the pages | `hd pagefit check`, `hd pagefit fix` | the same with `.hwp` | route |
| readability | `hd readability` | the same | route |
| fidelity checklist, XML difference | `hd check`, `hd diff` | the same | route |
| protection report | `hd secure --info` | the same | direct |
| hide personal numbers | `hd secure --mask-private` | the same | route |
| password, distribution document | `hd secure --password-env` | none: the step opens and saves the file type HWPX only; use the HWPX copy | - |
| convert | `hd convert` (Hangul) | `hd convert` (Hangul); no Hangul: `hd hwp tohwpx`, `hd hwp fromhwpx` | - |

Rules of the route: a protected `.hwp` (password, 배포용, DRM) and HWP 3 files are refused. The `.hwp` the route writes is a new file written from the
HWPX; for a received form where nothing but text changes, `hd edit` keeps the original bytes and is the better choice.
Open list: `hd hwp fromhwpx` stops with `UNSUPPORTED <element>` on an object or value that none of the tested files shows (form objects are written); see `lib/hwpx_docs/hwp5/coverage.md`.
