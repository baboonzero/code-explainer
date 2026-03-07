param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillDir = Split-Path -Parent $ScriptDir

Write-Host "Checking Python..."
python --version

Write-Host "Checking Node/npm..."
node --version
npm --version

Write-Host "Checking Git..."
git --version

Write-Host "Installing local Node runtime packages..."
Push-Location $SkillDir
npm install
Pop-Location

Write-Host "Installing Mermaid CLI (mmdc)..."
npm install -g @mermaid-js/mermaid-cli

Write-Host "Validating mmdc..."
mmdc --version

Write-Host "Validating Excalidraw export bridge..."
Push-Location $SkillDir
node ".\\scripts\\mermaid_to_excalidraw.mjs" --help | Out-Null
Pop-Location

Write-Host "Runtime install complete."
