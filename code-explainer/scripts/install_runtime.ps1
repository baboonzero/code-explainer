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

Write-Host "Installing Mermaid CLI (mmdc)..."
npm install -g @mermaid-js/mermaid-cli

Write-Host "Validating mmdc..."
mmdc --version

Write-Host "Optional: to enable the official Excalidraw bridge for development, run:"
Write-Host "  cd `"$SkillDir`""
Write-Host "  npm install --no-save @excalidraw/mermaid-to-excalidraw"

Write-Host "Runtime install complete."
