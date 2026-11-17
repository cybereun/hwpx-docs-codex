---
name: hwpx-forms
description: Apply a measured forms pack (page, fonts, label shading, lines, parts such as 접수 칸, 신청인 표, 서명란, 귀하, 처리 절차) when making an official Korean form (별지 서식, 신청서, 신고서) in HWPX. Use only when the user asks for a pack or a form "in the style of" an official form family.
---

# Forms pack (optional)

Resolve `skillRoot` using the main Codex skill. `hd` is the command defined in hwpx-core. `PACK` = `${skillRoot}/addons/hwpx-docs-forms/packs/<pack>`
(`ls ${skillRoot}/addons/hwpx-docs-forms/packs`; no pack there = nothing to apply, build the form with hwpx-core alone).
Format: `docs/forms-pack.md` of hwpx-docs. A pack is applied only when the user picks it.

1. `python "${skillRoot}/addons/hwpx-docs-forms/scripts/pack.py" list "$PACK"`: rules with evidence `n/N`. Tell the user what the pack sets.
2. Write the spec of the form (hwpx-core, `docs/spec.md`). Use parts: `{"part": "applicant-table", "args": {...}}`.
   Your own page, defaults and styles in the spec win over the pack.
3. `python "${skillRoot}/addons/hwpx-docs-forms/scripts/pack.py" apply spec.json "$PACK" -o full.json [--with optional-name]`, then
   `hd build full.json out.hwpx`.
4. Page fit: `hd pagefit fix out.hwpx fitted.hwpx --profile "$PACK/pagefit.json"` when the pack has that file.
5. If the user has the original .hwp, compare page count and page images with it. The original is right.
