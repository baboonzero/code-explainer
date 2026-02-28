# code-explainer

`code-explainer` is an open-source skill that analyzes either a local repository folder or a GitHub URL and produces onboarding explainers for PMs, designers, and engineers.

Outputs include:

- Crisp top-level overview (`OVERVIEW.md`)
- Linked deep explainers (architecture, modules, flows, dependencies, glossary)
- Mermaid source diagrams (`.mmd`)
- Rendered SVG and PNG diagrams
- Confidence, attribution, and quality reports (`meta/*.json`)
- Documentation coverage report (`meta/coverage_report.json`)

## Repository Layout

```text
code-explainer/
  SKILL.md
  agents/openai.yaml
  scripts/
  references/
  assets/templates/
```

## Dependencies (Required for Skill Installation/Use)

Install these before using the skill:

- Python `3.10+`
- Node.js `18+` and npm
- Git

For high-fidelity diagram rendering (`SVG` + `PNG` via Mermaid CLI):

- Mermaid CLI (`mmdc`) from `@mermaid-js/mermaid-cli`

If `mmdc` is missing, the skill still runs but uses fallback rendering and reports it in `meta/render_report.json`.

## Install Runtime Dependencies

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\code-explainer\scripts\install_runtime.ps1
```

### macOS/Linux

```bash
bash ./code-explainer/scripts/install_runtime.sh
```

## Troubleshooting Dependencies

### 1) `mmdc` is not recognized

If you see: `mmdc: command not found` or `The term 'mmdc' is not recognized`

Run:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc --version
```

If it still fails:

1. Open a new terminal session.
2. Check global npm bin path:

```bash
npm bin -g
```

3. Ensure that path is on your `PATH` environment variable.

### 2) Mermaid rendering fails with Chromium/Puppeteer errors

If you see browser launch errors from `mmdc`:

1. Reinstall Mermaid CLI:

```bash
npm uninstall -g @mermaid-js/mermaid-cli
npm install -g @mermaid-js/mermaid-cli
```

2. Re-run:

```bash
mmdc --version
```

3. If still blocked, the skill will continue with fallback rendering and report it in `meta/render_report.json`.

### 3) `npm install -g` permission errors

- Windows: run PowerShell as Administrator and retry.
- macOS/Linux: avoid `sudo npm install -g` if possible; use Node version managers (`nvm`, `fnm`, `asdf`) and retry.

### 4) `python` command not found

Confirm Python install:

```bash
python --version
```

If unavailable on Windows but `py` exists:

```powershell
py --version
```

Install Python 3.10+ and ensure it is added to `PATH`.

### 5) `git` command not found for GitHub URL analysis

Install Git and verify:

```bash
git --version
```

Local folder analysis can still run without Git, but GitHub URL source mode requires it.

## Install Sequence (Fresh Machine)

1. Install runtime dependencies (section above).
2. Install skill into Codex:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_to_codex.ps1
```

3. Restart Codex to load the new skill.

## Run

```bash
cd code-explainer
python scripts/analyze.py analyze \
  --source <local_path_or_github_url> \
  --output <output_dir> \
  --mode standard \
  --audience nontech \
  --overview-length medium \
  --enable-llm-descriptions true \
  --ask-before-llm-use false \
  --prompt-for-llm-key false \
  --enable-web-enrichment true
```

Useful optional controls:

- `--include-glob "<pattern>"` (repeatable) to scope analysis to specific paths
- `--exclude-glob "<pattern>"` (repeatable) to remove generated/irrelevant files

For LLM-based narrative summaries:

- Set `CODE_EXPLAINER_LLM_API_KEY` (or `OPENAI_API_KEY`)
- Optional: `CODE_EXPLAINER_LLM_BASE_URL`, `CODE_EXPLAINER_LLM_MODEL`
- Optional interactive controls:
- `--ask-before-llm-use true` (prompt for permission)
- `--prompt-for-llm-key true` (securely prompt for key when missing)

## Install From GitHub (For Other Developers)

Using Skills CLI:

```bash
npx skills add https://github.com/baboonzero/code-explainer --skill code-explainer
```

Using Codex skill installer:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo baboonzero/code-explainer \
  --path code-explainer
```

## Install Into Codex

Use the installer script:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_to_codex.ps1
```

Or copy manually to:

```text
~/.codex/skills/code-explainer
```

Then restart Codex so it picks up the new skill.

## Open-Source Publishing

1. Initialize git in this repository.
2. Commit files.
3. Push to GitHub.
4. Add `topics` such as: `codex-skill`, `agent-skill`, `mermaid`, `codebase-analysis`, `onboarding`.
5. Submit/list the repository on skill directories (see notes in your assistant response).

## License

This project is licensed under the MIT License.

- Full text: `LICENSE`

Created by Anshumani Ruddra
