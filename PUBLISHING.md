# Publishing and Distribution

## Publish to GitHub

From repository root:

```bash
git add .
git commit -m "feat: add proof-backed Excalidraw exports"
git push -u origin main
```

## What To Verify Before Publishing

1. The repo-level docs match the shipped skill contract.
2. `code-explainer/SKILL.md` reflects the current pipeline and proof path.
3. `python code-explainer/scripts/self_audit.py` passes.
4. `install_to_codex.ps1` copies the current package cleanly.
5. `meta/excalidraw_report.json` is part of the output contract and the self-audit proves editable scene generation.

Recommended:

```bash
cd code-explainer
pwsh ./scripts/install_runtime.ps1
python scripts/self_audit.py
```

If you want a scored artifact before publishing, also run the local `audit-skill` against `code-explainer/`.

## Install Verification

Install locally into Codex:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_to_codex.ps1
```

Then restart Codex and confirm the installed copy appears at:

```text
~/.codex/skills/code-explainer
```

## Downstream Dependency Note

Users need:

- Python `3.10+`
- Node.js `18+` and npm
- Git

Recommended for higher-fidelity diagram rendering:

- Mermaid CLI (`@mermaid-js/mermaid-cli`)

Even without live LLM access, the proof path still works through `CODE_EXPLAINER_MOCK_LLM=true`. The deterministic Excalidraw scene generator is now the default production path, so the repo does not need to ship the official bridge dependency in its default install surface. If a developer wants to experiment with the official bridge anyway, they can install it locally with `npm install --no-save @excalidraw/mermaid-to-excalidraw` and enable `--enable-official-excalidraw-bridge true`.

## GitHub Distribution

Suggested install paths for other developers:

Using the Skills CLI:

```bash
npx skills add https://github.com/<your-org-or-user>/code-explainer --skill code-explainer
```

Using Codex system installer tooling:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo <your-org-or-user>/code-explainer \
  --path code-explainer
```

## Discoverability

Suggested GitHub topics:

- `codex-skill`
- `agent-skill`
- `codebase-analysis`
- `onboarding`
- `mermaid`
- `excalidraw`
- `developer-tools`

Useful publishing assets:

1. A short README section showing `overview/OVERVIEW.md`
2. One example Mermaid diagram and one example Excalidraw scene screenshot
3. The self-audit result summary
4. The latest `audit-skill` report
5. A release note that explains the shift from generic output to proof-backed explanation plus editable diagrams
