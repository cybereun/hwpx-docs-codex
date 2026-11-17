$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$destination = Join-Path $codexHome 'skills\hwpx-docs'

if (Test-Path -LiteralPath $destination) {
    throw "Skill already exists at $destination. Back it up or remove it before installing this package."
}

$parent = Split-Path -Parent $destination
New-Item -ItemType Directory -Force -Path $parent | Out-Null
New-Item -ItemType Directory -Path $destination | Out-Null

Get-ChildItem -LiteralPath $sourceRoot -Force |
    Where-Object { $_.Name -notin @('.git', 'site') } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force }

Write-Output "Installed hwpx-docs at $destination. Start a new Codex session to use it."
