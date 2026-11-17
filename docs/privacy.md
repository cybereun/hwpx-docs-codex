# Privacy layer (add-on plugin `hwpx-docs-privacy`)

In the Codex port, activate this add-on with the bundled `pv.py enable` and use the protected `hd` CLI. The Claude Code hook behavior described below applies to the upstream plugin. See the [Codex instructions](../addons/hwpx-docs-privacy/README.md) for the supported paths.

Goal: what a document holds about a person does not reach the model. The model sees tags (pseudonyms); the values stay in a local vault
and come back when a document is written. The layer is an add-on: the core plugin has two generic hook points and nothing else; a user
who does not install the add-on carries no code, no hook and no startup tokens of it.

## 1. Three layers

```
core (hwpx-docs)                 lib/hwpx_docs/core/addons.py + 10 lines in lib/hd.py     two generic hook points, no privacy words
add-on (hwpx-docs-privacy)       scripts/hwpxpriv/*.py                                     engine, vault, gates, hidden places
packs (data inside the add-on)   packs/<pack>/pack.json                                    rules and tests per kind, one folder each
```

### 1.1 Core hook points (`core/addons.py`)

With no settings file and `HWPX_DOCS_ADDONS` unset the module returns at once: no import, no change of output (`hd selftest` ALL PASS, tested
with and without). An add-on folder holds `hwpx-addon.json`:

| key | contract |
|---|---|
| `output_filter` | `function(argv) -> f`; `f(text) -> text`; optional `f.finish()`. While a command runs, file descriptors 1 and 2 go to temporary files (so child processes and the error report are covered); the collected text is passed through `f` and then shown. An exception or `SystemExit` of the command is reported through the same filter (`addons.report`): the report is masked like any other output (by the same rules, so as far as they find the value). |
| `write_resolver` | `function(argv) -> (argv2, cleanup)`; runs before the command; it may replace arguments (here: tags -> real values, also in text input files through a temporary copy that `cleanup` deletes). An exception stops the call with exit code 2 and its message. |

**Fail closed.** The mode (`standard`, `strict`) is read from the same file (`"mode"`); the environment variable `HWPX_PRIVACY_MODE=strict` can raise it, a variable cannot lower it, and there is no `off`: you switch the layer off with `pv.py disable` on a terminal (the SessionStart hook then leaves it off, and no hook refuses a call, until `pv.py enable`). The SessionStart hook keeps the other keys of the file (`mode`). `hd` finds add-ons in the user's fixed settings file `%LOCALAPPDATA%\hwpx-docs\addons.json`
(`{"addons": [folder], "enforce": true}`; `~/.config/hwpx-docs/addons.json` elsewhere; `HWPX_DOCS_ADDONS_CONFIG` names another file). The add-on's
SessionStart hook writes it (`pv.py enable` writes it too), so the layer is on for every `hd` call, a direct `python lib/hd.py` call and a
plain terminal included, whether or not a hook ran. The environment variable `HWPX_DOCS_ADDONS` only adds folders (a test override; it cannot
switch an enforced add-on off). With `enforce: true` an add-on that cannot be loaded (folder gone, file broken, start-up error) stops the call:
`PRIVACY ADDON NOT LOADED ...`, nothing runs, no document text is shown, exit code 2. A broken settings file, a path that is not a file, a list that is not a list, an empty list and an add-on without a filter or a resolver count as enforce with an add-on that cannot be loaded. To switch the
layer off the user runs `pv.py disable` on a terminal or deletes the file. The gate refuses a command that names the variables and modules of the add-on (`HWPX_DOCS_ADDONS`, `HWPX_PRIVACY_*`) and the vault commands `consent`, `purge`, `add`, `enable`, `disable`; a command that deletes or overwrites the settings file, or moves `LOCALAPPDATA`, is not recognised (8).

### 1.2 The add-on

| file | job |
|---|---|
| `engine.py` | `Session` (masking, known values), `learn` (a document is read once before the command: slots, labels to the left and above a cell, form diff against blank templates, hidden values) |
| `ioflow.py` | the two entry points. `output_filter`: masks what the command shows and, when it ends, every readable text file that it names and that the command wrote or changed (`hd text -o`, `hd read doc spec.json`, md / html / svg / txt / py exports; the content decides, not the extension; found by comparing the files before and after the command, no clock is compared); a picture, another binary or a text part that appears next to an output (the parts that `hd read` writes beside the spec) is closed to the Read gate, a neighbour is never rewritten (another process may work in that folder); a message that names a covered copy shows the file the user named; a final document (HWP, HWPX by content) keeps real values; the audit log holds ids of file names, never the names. `write_resolver`: tags -> real values with the Korean particle fixed to the real word (`⟪성명1⟫은` -> `박하준은`, `김하늘이`, `…와/과`, `(으)로`, `(이)다`); a tag in a path argument (with a separator or a listed extension, or a bare or glued tag such as `⟪성명1⟫`, `x⟪성명1⟫`) is refused; text with a space and a value `KEY=TEXT` are not paths, so a path argument that has a space and neither a separator nor a listed extension (`-o "⟪성명1⟫ 메모"`) is still resolved: the file gets the real name as its name, and its content is neither masked nor closed (next stage); a drawing command (`render`, `preview`) gets a covered copy of the document, so a picture shows no value that the detector finds (an HWP must be converted first). Temporary copies live in `<vault home>\tmp` and are removed when the command ends; the folder of a command that was killed is removed by the next call (its process id is kept in the folder; a folder without one after an hour) |
| `settings.py` | the fixed settings file (`enable`, `disable`) |
| `detect.py` | the detector, four levels (below), rules from the packs |
| `validators.py` | check digits (RRN, FRN, Luhn, business and corporate number, driving region, IPv4, date) and the attribute disclosers |
| `normalize.py` | one shape for odd input: full-width, zero-width, look-alike characters, decomposed jamo, Korean numerals and O/l swaps inside long number runs |
| `vault.py` | the vault (DPAPI via ctypes, standard library), audit log, consents |
| `redact.py`, `docscan.py` | covered copy of an HWPX, hidden places (group J) |
| `calc.py` | `pv.py calc`: a small expression language, no `eval`; the functions `age`, `sex`, `same`, `count` |
| `gates.py`, `scripts/hook.py` | the hooks |
| `cli.py`, `scripts/pv.py` | the vault commands: `pv.py list|forget|purge|audit|add|calc|scan|mask-copy|consent|enable|disable|status|selftest`. They are not `hd` commands: the core has two hook points for add-ons and no more |

## 2. Tags

`⟪<kind><n>｜<attributes>⟫`, short: `⟪주민번호1｜1980년대·남⟫` (a registration number shows age band and sex, nothing else does), `⟪성명2⟫`, `⟪전화번호1⟫`, `⟪질환1｜정신·행동⟫`.
The resolver also accepts a tag that the model wrote a little broken: spaces inside, `《 》` for `⟪ ⟫`, an ASCII bar.
The id (`주민번호1`) is the key; the same value has the same tag inside the vault (coreference kept; phone numbers compare by their digits).
`fine` (birth year instead of the age band) is shown for registration numbers only after a consent with `--fine`.

## 3. Detector

1. L1 patterns with a check (RRN date + checksum, Luhn, business number checksum, driving region, IPv4, date).
2. L2 form context: the value after a label on the same line, on the next line, to the right of a label cell, or under a header cell.
   The longer (more specific) label wins when two kinds share a value ("지갑 주소" is a wallet, not an address).
3. L3 names in prose: surname + given name + title or particle; shape-only matches are checked against the stop list.
4. L4 dictionary terms (strict mode): disease, drug, crime name, religion, party, union, disability type (3.2).
5. K user words: `HWPX_DOCS_PRIVATE`, `pv.py add --stdin`, organization terms.
Standard looks for groups A-D, B and J (identifiers, names, contact, finance, hidden places); strict adds E (other ID numbers), F (birth date, age, nationality, school, employer), G (family), the dictionary terms and every typed form value (`"level": "strict"` in a pack).
A label that is only part of a longer phrase ("신청인 성명 ...") does not hide the label inside it: a rejected match is searched again from the next character.
Unknown shapes are the weak point of every rule-based detector, so there are four more nets: normalization (above), tolerant shapes (an
RRN-shaped number with a wrong checksum is still masked; partial numbers near a label), the vault (a value seen once is masked everywhere, with
any separator), and form diff (`HWPX_PRIVACY_TEMPLATES`: everything typed into a blank form is masked whatever its shape).
False-positive guard: pack `kr-fixed-text` holds the fixed words and public numbers of the 153 public blank forms (tool
`make_fixedtext.py` of the archived tools); a value made only of such words, or a number printed in a blank form, is not a person's.

### 3.1 Look-alike numbers

A wrong mask is the safe failure, but it hides values the model may need. Pack `kr-lookalike` lets an RRN-shaped 13-digit number through only
when a strong non-personal signal is present and no personal one is: a label such as 제품번호, 바코드, 주문번호, 일련번호, 법인등록번호 in the 30
characters before it (or a valid EAN-13 with a GS1 prefix) **and** the RRN check digit fails and no personal label (주민등록번호, 생년월일 ...) is near.
A valid RRN check digit always wins. Corporate registration numbers and business numbers of corporations (middle digits 80-89) are public and
not masked; a business number of a person is. A look-alike that happens to pass the RRN check digit (about 1 in 10) stays masked.

### 3.2 Sensitive terms (strict mode, no model)

Pack `kr-sensitive-terms` is a dictionary (disease by KCD chapter, drug ingredient, crime name by class, religion, party, union, disability type).
A hit becomes a typed tag, `⟪질환1｜정신·행동⟫`, and the sentence around it stays editable. Instruction lines of forms ("진단서 사본을 첨부하여
제출") are skipped by the `skip` list of the pack. A sensitive sentence without a dictionary term is left readable (decision v1). Names and numbers
inside a sentence with a term are learned first, so the same person is masked everywhere else.

### 3.3 Cut values

Some listings cut a long text (`hd slots` shows 60 characters). The first characters of a known value at the end of a line (4 or more
characters, 6 or more digits) are masked as the value.

### 3.4 `pv.py calc`

Four functions: `age(rrn, at)`, `sex(rrn)`, `same(tag, tag)`, `count(...)`. Comparison and arithmetic take numbers only; a value of the vault is
text, and comparing it with a guess would read it digit by digit (`same` takes two tags, never a literal). A yes / no result is shown; `count` of
5 or more values is shown; everything else becomes a tag. A yes / no result is one bit: repeated calls can still narrow a value (an age by changing
the date), so every calc is in the audit log; the layer limits this, it does not make it zero.

## 4. Pack format

```json
{"name": "kr-contact", "about": "...", "version": 1,
 "lists": {"SIDO": ["서울특별시", "..."]},                         // {{SIDO}} in a regex = alternation (one item = raw)
 "kinds": [{"id": "phone", "label": "전화번호", "group": "C", "numeric": true, "disclose": "phone",
            "patterns": [{"re": "...", "check": "luhn", "stoplist": "COMMON", "weak": true}],   // L1 / L3
            "labels": ["전화번호", "연락처"], "value": "regex of the value after a label",         // L2
            "free": true, "require": "regex the value must contain",
            "tests": {"pos": [["text", "expected value"]], "neg": ["text"]}}]}
```

A kind needs `tests`; `pack_test.py` of the archived tools runs them (`PACKTEST ALL PASS`). A pack with `terms` is the dictionary of 3.2. A kind with `"level": "strict"` is looked for in strict mode only.
A new country or kind is a new folder; the engine does not change. Environment: `HWPX_PRIVACY_PACKS` (comma list) limits the packs.

## 5. Hidden places (group J) and covered copy

`pv.py mask-copy in.hwpx out.hwpx` writes a copy for the model or for a render. Rules in `packs/doc-hidden`:
summary (creator, last saved by, subject, description, keyword, dates), track-change authors and dates, memo author and date, text of memos and
hidden comments, field and bookmark names, user paths, pictures (placeholder of the same type; `--images strip` keeps the picture and removes EXIF
and PNG text chunks), OLE and other binary parts (every known value and number pattern overwritten, ASCII and UTF-16, same length), BinData names
renamed in every part, `PrvText.txt` masked, `PrvImage.png` white, `Scripts/` dropped. The text itself: every detected or known value becomes
`■` of the same length, also when a value is split over runs. Only HWPX is covered: `pv.py mask-copy` of an HWP or of a binary (a picture) says no and writes nothing (an HWP is saved as .hwpx first); a text file is copied masked (UTF-8 or cp949).

## 6. Hooks

The gate refuses what is certain; a user's own work passes (measured: `PRIVACY GATE false-denials`).

| event | tool | decision |
|---|---|---|
| SessionStart | | writes the fixed settings file (and, as a second way, the export of `HWPX_DOCS_ADDONS` to `CLAUDE_ENV_FILE`); after `pv.py disable` it writes nothing and tells the user that the layer is off; when the file cannot be written it tells the user (systemMessage) and the calls of Read, Bash, PowerShell, Monitor and Grep are denied until the file exists |
| PreToolUse | Read | deny: a Hangul document (also a renamed copy: sniffed), a binary file made from one by `hd`, a picture from a document (all pictures in strict), the vault folder, a file that holds a certain value (valid RRN / FRN, card, labelled account, driving licence, passport, business number of a person, or a value of the vault; the file is read as UTF-8, else as cp949 (a CSV from Excel), as UTF-16 only with a byte-order mark or NUL bytes; a binary is only checked for vault values; every candidate counts before one span hides another, so a list with a 주소 column, whose rows become one address span, is still refused). A text file that `hd` wrote (spec, text export) was masked in place and passes |
| PreToolUse | Bash, PowerShell, Monitor | deny: a command that dumps a document (unzip, cat, strings, grep, Get-Content, Expand-Archive, Select-String, `[IO.Compression.ZipFile]`, python / powershell with inline code that names one), a file that Read would refuse given to a dump command (`~` and `$VAR` are expanded first), a command that names the variables or modules of the add-on, `pv.py consent|purge|add|enable|disable`. `hd` and `pv.py` pass (masked); ls, cp, git, wc, Test-Path ... pass |
| PreToolUse | Grep | same checks for the searched file or folder (a matching line would be sent) |
| UserPromptSubmit | | block only: RRN / FRN with a valid check digit and date, a card (Luhn and a known first digit), an account that carries its label (after normalization). The prompt is not sent; the word `#허용` in the prompt lets it through (logged) |
There is no PostToolUse hook: output that exists cannot be taken back, so a second scan would only be a log. A hook that fails for any reason (unreadable input, an exception) ends with exit code 2, so the call is not let through; the hook command falls back from `python` to `py -3` and ends with `|| exit 2` when neither exists. The file checks of one Bash command are stopped after 15 s and answered with `ask` (the hook limit is 30 s; a hook that the host stops at its limit is not an exit 2: the call then runs, the host's rule). A file is scanned by its first 256 KB (a value found in it is `deny`); a larger file without a value, or a large folder, is answered with `ask`. A refusal gives its reason and says not to work around it with another tool: use the `hd` and `pv.py` commands. A crash inside a gate denies (fail closed). Every refusal names kinds and counts, never a value.

## 7. No local model

Government PCs are weak and often cannot install a model runtime, so every part works with no local model; there is no model adapter.
Consent (`pv.py consent <tag|type:kind> [--fine]`) works only from a terminal, asks for `yes`, is logged, and is refused for a command that a model runs.
Not built (next milestone, only when the user asks): meaning checker, batch policy and review page with learning, scoped saved decisions, per-person
limit on quasi-identifiers, whole-sentence masking, long pseudonyms with usage features, blocking the screen and browser tools.

## 8. Limits (read this)

**What this layer is.** It prevents slips in everyday work: a document read by habit, a value that a command prints, a file that is opened without a
thought. It is not a boundary against a model or a user who works around it on purpose, and it cannot stop a command or a script that someone built
to get the data. What is known and not coded in v1 (a hook could close some of it; it is left to the next milestone):
- A command written to avoid the gate's text check: quoting and variable tricks that build a file name (`unzip -p doc2.hw""px ...`, `f=doc.hw; unzip ${f}px`),
  a program the gate does not know (`bsdtar`, `jar`, `zcat`, `busybox`, `wsl ...`, `bash -c '...'`), a command chain where `hd` appears only in a comment
  or after `&`, a file made earlier in the same command line (`cp doc.hwpx x.zip && unzip -p x.zip ...`), a copy of a derived file under another name: `cp` of a closed file, or `cp -r` of the folder that `hd read` wrote, is also a normal everyday copy, not only a deliberate bypass; the copy is not closed and is read when it holds no certain value.
- A script that the model writes with the Write tool and runs: the gate reads the command, not the script. A process that runs as the same user can also read the
  vault (DPAPI protects it from other accounts, not from the same user) and the consent file.
- Settings that the environment can move: `HWPX_DOCS_ADDONS_CONFIG` and `LOCALAPPDATA` name the settings file, so a command that sets them runs `hd` without
  the layer; the vault home holds the consent file as plain JSON and a command that can write there can grant itself a reveal. A Bash or PowerShell command can also delete or overwrite `addons.json`: the gate matches the variable names, not the file.
- Tools the hooks do not cover: Write and Edit (they can change the settings, the add-on folder or the consent file), MCP tools (file readers, terminals), Glob
  (file names), screen tools and a browser with `file://`.
- Names of files: a file name is never masked. Do not put a person's name into a file name: it shows in listings, and a name inside a name is not found by the detector.
- Yes / no answers of `pv.py calc` can be combined: `age(...)` with two dates tells the birthday by bisection. Every calc is logged; the layer limits this, it does not make it zero.
- File ids in the vault and the audit log are an unsalted sha1 of the file name: a guessed name can be confirmed against them (the log never holds the name).
- A folder argument: files in it that another process changes during the command are taken as written by the command (masked in place); files next to an output are only closed, never rewritten. On a drive whose file times tick in 2 s steps (FAT32) a file that was overwritten with the same size within one step looks unchanged.
- What the cloud provider keeps (retention, training) is outside the add-on.

- Hooks cover the tools Read, Grep, Bash, PowerShell and Monitor (PreToolUse) and the prompt. Another tool that reads files (an MCP file server, a browser with `file://`) is not
  covered, and neither are screen tools (a screenshot of a document window); blocking those is for the next milestone. A model with a shell
  could write a script that opens a document and run it; the Bash gate reads the command text, not the script. For a hard guarantee also deny
  `Read(**/*.hwp*)` and the folder in the permission settings, or work in a sandbox without the documents.
- The filter covers `hd` and its child processes (and the error report of a command). Text that another program prints is not filtered.
- Detection is rule-based. A value in an unknown layout, an unlabeled name in prose without a title, or a heavy misspelling can pass. The nets
  above reduce this; `HWPX_PRIVACY_TEMPLATES` and `strict` reduce it more. Measure on your own forms (`tools/privacy`).
- The coarse attributes of a tag are information by design (age band and sex of a registration number).
- DPAPI protects the vault from other Windows users, not from a program that runs as the same user. Other systems: a key file (or passphrase).
- The prompt gate finds only certain identifiers (valid RRN / card, labelled account); a name, a phone or an address typed in a prompt is not found.
- A final document keeps real values; the vault is global, so a model could write a tag of another document into a document.

## 9. Results (fake people only, one development machine)

| test | result |
|---|---|
| leak, 151 documents (the government forms of a folder and HWPX examples filled by `fill.py`, 685 planted values; includes a name after a compound label and a second name in prose): every read command, error message, derived file (`text -o`, `tospec`, `slots --json`, `read`), drawing, Grep, Bash, PowerShell, a direct `python lib/hd.py` with only the settings file, enforce with a missing add-on | standard: `PRIVACY LEAK 0/685 canaries`; hooks `6579/6579` (includes the CSV layouts: cp949, UTF-8, UTF-16, and lists with a 주소 column in cp949, UTF-8 and tab form, one or two rows, even and odd length) |
| same with blank templates; strict mode (every second document) | `0/351` and `0/358`; hooks `3334/3334` each |
| cases found by the review of signal 6 (exception report, mode variable, enforce with no filter, output by content, tag in a file name, pictures of `hd read`, hook failure and large file, settings file not writable, Monitor, renamed copy, audit names, compound label) | `PRIVACY SIGNAL6 28/28` in every run |
| cases found by the review of signal 7 (cp949 CSV, written files by before / after comparison, text neighbours of an output, title and subject, mode key kept, tag in any path and not in a value, Bash time budget, stale temporary folders, mask-copy of an HWP or a binary, `disable`, a cut prefix, a vanished file, the preview message) | `PRIVACY SIGNAL7 18/18` in every run |
| typo canaries (full-width, dots, spaces, zero-width, O for 0; RRN, phone, card, business no., licence) written into forms | `PRIVACY LEAK typo 0/190` in every run |
| gate on a user's own work (ls, git, cp, wc, python, Get-ChildItem, Copy-Item, Test-Path, reading a README, prompts without a certain value) | `PRIVACY GATE false-denials 0/2477 benign calls` (templates run 0/1254, strict 0/1261) |
| detection, label and prose layouts written for the test (strict mode, 40 people) | recall 1.000 per kind; partly circular, see below |
| typo set, 6 number kinds | `PRIVACY TYPO recall 1.000 (1200/1200)` |
| false positives, guard learned from half of the 153 blank forms, counted on the other half | 20 hits in 14 of 76 blank forms: name 17, money 1, RRN-shaped sample number 1, office phone 1 (measured before the signal-7 change; after the name shape `surname + 1 syllable` was added, `make_fixedtext.py --half even --check` counts 1 false positive in 76 forms, the same as before) |
| strict mode, dictionary terms | planted sentences with a dictionary term 4/5 (the one without a term is left readable by decision); hits in blank forms: words such as 징계, 폭행, 기초생활 in explanatory text |
| look-alikes (EAN-13, ISBN-13, serial, order, 법인등록번호 ...) | `fp 0.034 (19/560)`, all of them numbers that also pass the RRN check digit; personal numbers `leak 0/160` |
| round trip (tag edit = real edit; `--set`, `--values` file, `hd md`; particles fixed) | `75/75 records equal` |
| Hangul 2024, hidden, background | 3/3 outputs open with equal page count; 3/3 covered copies open with the same page count as the original |
| hidden places | `0/8 places` hold a planted value; the package keeps 10 of 10 parts |
| `pv.py` commands (incl. enable, disable) | `PRIVACY CLI 27/27 checks` |
| speed | 16 pages/s (about 100 pages in 6 s), 42 MB peak, about 240 ms added per `hd` call |
| plugin | `claude plugin validate` passes; always-on cost about 125 tokens (the same figure for the version before this change), 890 when the skill runs |

The recall table is partly circular: the labels in the test layouts come from the packs' own label lists. The honest numbers are the leak test on
filled forms (values placed where real forms have them, including cells with no label, a narrative paragraph and a cut listing) and the
hold-out false-positive count. Fake people are random: they are not real, and no real data was used. Not verified: a live Claude Code session
with the plugin loaded (the hooks were driven with the hook JSON protocol).

## 10. Tests

In the repository, `tools/privacy/`:

| tool | job |
|---|---|
| `gen.py` | fake people with valid check digits (no real person) |
| `fill.py` | fills fake people into the government forms of a folder (`--gov`) and the HWPX examples, outside the repository |
| `leak_test.py` | `PRIVACY LEAK 0/<n> canaries`, `PRIVACY HOOKS <ok>/<n>`, `PRIVACY GATE false-denials`, `PRIVACY LEAK typo` (`--mode strict`, `--templates DIR`, `--every N`) |

Kept outside the repository (the clean-up decision; hashes were checked when they moved; run them with `HWPX_DOCS_REPO` set to the checkout): `pack_test.py` (`PACKTEST ALL PASS`), `detect_eval.py` (recall, typo recall, hold-out false positives), `roundtrip_test.py`
(tag edit = real edit, Hangul opens the output), `hidden_test.py` (every hidden place), `lookalike_test.py`, `cli_test.py` (`pv.py` commands),
`perf_test.py`, `make_fixedtext.py` and `make_stoplist.py` (learn the false-positive guards from blank forms, hold-out `--half even --check`),
`run_all_leak.sh` (the leak test three times).
