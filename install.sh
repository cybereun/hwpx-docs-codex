#!/usr/bin/env sh
set -eu

source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
codex_home=${CODEX_HOME:-"$HOME/.codex"}
destination="$codex_home/skills/hwpx-docs"

if [ -e "$destination" ]; then
  printf 'Skill already exists at %s. Back it up or remove it before installing this package.\n' "$destination" >&2
  exit 1
fi

mkdir -p "$(dirname "$destination")"
mkdir "$destination"
tar --exclude='./.git' --exclude='./site' -cf - -C "$source_root" . | tar -xf - -C "$destination"
printf 'Installed hwpx-docs at %s. Start a new Codex session to use it.\n' "$destination"
