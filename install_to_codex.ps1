param(
    [string]$CodexHome = "$HOME/.codex"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $repoRoot "code-explainer"
$dst = Join-Path $CodexHome "skills/code-explainer"

if (-not (Test-Path $src)) {
    throw "Source skill folder not found: $src"
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null

Copy-Item -Path (Join-Path $src "SKILL.md") -Destination $dst -Force
Copy-Item -Path (Join-Path $src "agents") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "scripts") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "references") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "assets") -Destination $dst -Recurse -Force

Write-Host "Installed code-explainer to $dst"
Write-Host "Restart Codex to pick up the new skill."

