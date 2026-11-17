---
name: hwpx-docs
description: Create, read, edit, check, and preview Hancom HWPX documents. Use for HWPX/HWP forms, Korean office documents, or converting Markdown and HTML into HWPX.
---

# HWPX documents

Use the bundled HWPX engine and specialist guides in this skill package. This is a Codex adaptation of BlackBuddle/hwpx-docs; retain its attribution and AGPL license when redistributing the package.

## Resolve the package path

Keep the package directory available as `skillRoot`. It is the directory containing this `SKILL.md`. For the default global install, use:

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillRoot = Join-Path $codexHome 'skills\hwpx-docs'
```

For a shell, use `skillRoot="${CODEX_HOME:-$HOME/.codex}/skills/hwpx-docs"`. If installed somewhere else, set `skillRoot` to that package directory. In the specialist guides, `${skillRoot}` means this resolved directory.

Invoke the engine with `python "${skillRoot}/lib/hd.py" <command> ...`. Python 3.10 or newer is required. Build, read, edit, extract, and most checks use the standard library. Rendering through Hangul, HWP conversion, and password protection require the Windows/Hangul setup described in `skills/hwpx-security/SKILL.md`.

## Choose a specialist guide

Read `skills/hwpx-core/SKILL.md` for the common workflow, then read the relevant guide before a specialized task:

- `hwpx-text`: text styles, Markdown/HTML conversion, and text readability.
- `hwpx-table`: table dimensions, merges, borders, fills, and captions.
- `hwpx-objects`: shapes, text boxes, pictures, and charts.
- `hwpx-page`: page size, margins, columns, headers, footers, and page numbers.
- `hwpx-from-image`: reconstructing a form from an image.
- `hwpx-edit`: filling or revising a received HWPX while preserving its layout.
- `hwpx-gongmun` and `gongmun-style`: Korean official letters and their wording checks.
- `hwpx-security`: Hangul security prompts, passwords, distribution documents, and privacy masking.
- `hwpx-readability`: page fitting and readability changes only when the user asks for them.

## Core workflow

For a new document, create a JSON spec using measured sizes, build the HWPX, inspect the reported readability findings, and render or compare pages when visual fidelity matters. For an existing form, use the edit workflow so unrelated layout and document data remain intact. Do not apply the readability profile unless the user requests a readability or page-flow change. Follow the specialist guide for security prompts and any Hangul automation.

The package includes the source modules and references used by these guides. Keep `lib/`, `docs/`, `presets/`, `templates/`, and `skills/` together with this entrypoint.
