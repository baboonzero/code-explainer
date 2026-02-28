#!/usr/bin/env bash
set -euo pipefail

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

echo "Runtime install complete."

