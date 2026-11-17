---
name: hwpx-privacy
description: Work on Hangul documents (HWP/HWPX) that hold personal data without the data that the layer finds reaching the model (rule-based; it is a guard against slips, not a boundary). Use when the user mentions 개인정보, 주민번호, 가명, 마스킹, privacy, or when a document to read or fill holds names, numbers, addresses or sensitive sentences.
---

# Privacy layer (the model sees pseudonyms for what the rules find)

Resolve `skillRoot` using the main Codex skill. `hd` is its command. `pv` = `python "${skillRoot}/addons/hwpx-docs-privacy/scripts/pv.py"`. An `hd` call prints tags instead of the
personal data that its rules find (rule-based: an odd layout can pass), for example `⟪성명1⟫`, `⟪주민번호1｜1980년대·남⟫`, `⟪질환1｜정신·행동⟫`. The real value stays in a local vault.

Before reading, run `pv status` and require active protection and the DPAPI backend for real personal data. If disabled, ask the user to enable it in their terminal.

1. Read a document only with `hd text|slots|form list|read <file>`. Codex does not have the upstream Claude Code hook. Keep originals and restored files out of direct reads, uploads and previews.
   Text files that `hd` names as output (`-o`, the spec json) are written already masked; other files that `hd` writes next to them (the parts of `hd read`) may include sensitive content. Keep them out of direct reads and previews.
2. Write with tags. Give a tag where the real value belongs: `hd edit in.hwpx out.hwpx --set "성명=⟪성명1⟫"`, or a spec / values / md file that
   holds tags. The tag is turned into the real value just before the file is written, and a particle after it is fixed to the real word
   (`⟪성명1⟫은`). An unknown tag is an error. Keep real personal values out of prompts.
3. The same value has the same tag in one vault. For an exact answer ask the vault: `pv calc "age(⟪주민번호1⟫, 2026-11-16) >= 19"` (also `sex`,
   `same`, `count`). A result that is not a yes / no becomes a new tag `⟪계산1⟫`.
4. To see layout, `hd render` / `hd preview` an HWPX: the picture is drawn from a covered copy. An HWP is converted first (`hd hwp tohwpx`).
   A covered copy to keep: `pv mask-copy in.hwpx out.hwpx`.
5. Do not guess a masked value. If the task needs the hidden content itself, say so and ask the user to reveal that item on a terminal
   (`pv consent <tag>`); you cannot do it yourself.
6. `pv list` (tags, never values), `pv audit` (what was masked, blocked, revealed), `pv status`.
Modes (settings file; `HWPX_PRIVACY_MODE=strict` raises it): `standard` (default: identifiers, names, contact, finance, pictures, metadata), `strict` (also dictionary
terms such as diseases and crime names, other ID numbers, birth date, age, school, employer, family names, every typed form value).
When a tool call is refused, do not work around it with another tool or command: use `hd` and `pv`. Do not put a person's name into a file name.
