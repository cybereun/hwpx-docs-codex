# hwpx-docs-codex

Codex skill port of [BlackBuddle/hwpx-docs](https://github.com/BlackBuddle/hwpx-docs), a toolkit for creating, reading, editing, checking, and previewing Hancom HWPX documents.

The upstream HWPX engine, documentation, examples, templates, and specialist skill guides are included. The Codex entrypoint routes HWPX requests to the relevant guide and keeps the runtime files together so commands work after installation.

## Install

Install this repository as a single global Codex skill at `~/.codex/skills/hwpx-docs` (or `$CODEX_HOME/skills/hwpx-docs` when `CODEX_HOME` is set). On Windows, run `install.ps1` from the cloned repository. On macOS or Linux, run `bash install.sh`.

You can also clone the repository directly into the skill directory:

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillDir = Join-Path $codexHome 'skills\hwpx-docs'
New-Item -ItemType Directory -Force -Path (Split-Path $skillDir -Parent) | Out-Null
git clone https://github.com/cybereun/hwpx-docs-codex.git $skillDir
```

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/cybereun/hwpx-docs-codex.git "${CODEX_HOME:-$HOME/.codex}/skills/hwpx-docs"
```

Start a new Codex session after installing. Python 3.10+ is required. HWPX creation and reading use the Python standard library; Hangul rendering, HWP conversion, and password protection have additional Windows/Hangul requirements described in the skill guides.

## Included workflows

The root `SKILL.md` is the Codex entrypoint. Detailed upstream guides remain in `skills/` and cover core documents, text, tables, objects, page setup, form reconstruction, editing, official letters, security, and readability. Keep the package together: the guides refer to the included `lib/`, `docs/`, `presets/`, and `templates/` directories.

## License and attribution

This is a derivative distribution of BlackBuddle/hwpx-docs. It retains the upstream `AGPL-3.0-or-later` licensing terms and attribution; see [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE). The Codex-specific packaging does not transfer ownership of upstream material.
