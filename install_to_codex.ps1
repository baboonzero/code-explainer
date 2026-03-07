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
if (Test-Path (Join-Path $src "package.json")) {
    Copy-Item -Path (Join-Path $src "package.json") -Destination $dst -Force
}
if (Test-Path (Join-Path $src "package-lock.json")) {
    Copy-Item -Path (Join-Path $src "package-lock.json") -Destination $dst -Force
}
Copy-Item -Path (Join-Path $src "agents") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "scripts") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "references") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $src "assets") -Destination $dst -Recurse -Force

Write-Host "Installed code-explainer to $dst"
Write-Host "Run npm install inside the installed skill folder if local Node dependencies are not present."
Write-Host "Restart Codex to pick up the new skill."
