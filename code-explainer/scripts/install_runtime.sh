#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Checking Python..."
python3 --version

echo "Checking Node/npm..."
node --version
npm --version

echo "Checking Git..."
git --version

echo "Installing local Node runtime packages..."
(cd "$SKILL_DIR" && npm install)

echo "Installing Mermaid CLI (mmdc)..."
npm install -g @mermaid-js/mermaid-cli

echo "Validating mmdc..."
mmdc --version

echo "Validating Excalidraw export bridge..."
(cd "$SKILL_DIR" && node "./scripts/mermaid_to_excalidraw.mjs" --help >/dev/null)

echo "Runtime install complete."
