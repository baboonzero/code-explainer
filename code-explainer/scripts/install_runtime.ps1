param()

$ErrorActionPreference = "Stop"

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

Write-Host "Runtime install complete."

