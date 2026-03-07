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

echo "Installing Mermaid CLI (mmdc)..."
npm install -g @mermaid-js/mermaid-cli

echo "Validating mmdc..."
mmdc --version

echo "Optional: to enable the official Excalidraw bridge for development, run:"
echo "  cd \"$SKILL_DIR\""
echo "  npm install --no-save @excalidraw/mermaid-to-excalidraw"

echo "Runtime install complete."
