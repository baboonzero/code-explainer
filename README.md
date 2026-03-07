# code-explainer

`code-explainer` is a Codex skill for explaining a local repository or GitHub repository in simple, concrete language. The rebuilt version is explanation-first: it creates a grounded narrative plan, generates onboarding docs and focused diagrams from that plan, and scores the output for clarity, specificity, grounding, usefulness, and honesty.

## What It Produces

A standard run writes:

- `overview/OVERVIEW.md`
- `deep/ARCHITECTURE_DEEP.md`
- `deep/MODULES_DEEP.md`
- `deep/FLOWS_DEEP.md`
- `deep/DEPENDENCIES_DEEP.md`
- `deep/GLOSSARY.md`
- `diagrams/*.mmd`
- `diagrams/svg/*.svg`
- `diagrams/png/*.png`
- `meta/*.json`

Important proof artifacts:

- `meta/explanation_plan.json`
- `meta/explanation_quality.json`
- `meta/verification_checkpoint.json`
- `meta/fact_check_report.json`
- `meta/quality_report.json`

## Why This Version Is Better

The older build overpromised and produced generic output. This rebuild changes the contract:

- the explanation is planned before docs are written
- diagrams are tied to onboarding questions
- the quality gate can fail generic or weakly grounded output
- the repo ships fixture repos plus a self-audit path

## Repository Layout

```text
code-explainer/
  SKILL.md
  agents/openai.yaml
  assets/
    fixtures/
    templates/
  references/
  scripts/
README.md
PUBLISHING.md
install_to_codex.ps1
```

## Install Runtime Dependencies

Required:

- Python `3.10+`
- Node.js `18+` and npm
- Git

Recommended:

- Mermaid CLI (`mmdc`) from `@mermaid-js/mermaid-cli`

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\code-explainer\scripts\install_runtime.ps1
```

macOS/Linux:

```bash
bash ./code-explainer/scripts/install_runtime.sh
```

## Install Into Codex

From this repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_to_codex.ps1
```

This copies the skill into `~/.codex/skills/code-explainer`. Restart Codex after installation.

## Run

```bash
cd code-explainer
python scripts/analyze.py analyze \
  --source <local_path_or_github_url> \
  --output <output_dir> \
  --mode standard \
  --format markdown \
  --explainer-type onboarding \
  --audience nontech \
  --overview-length medium \
  --enable-llm-descriptions true \
  --ask-before-llm-use false \
  --prompt-for-llm-key false \
  --enable-web-enrichment false
```

Useful controls:

- `--include-glob <pattern>`
- `--exclude-glob <pattern>`
- `--format markdown|html|both`
- `--mode quick|standard|deep`
- `--explainer-type onboarding|project-recap|plan-review|diff-review`
- `--audience nontech|mixed|engineering`

## LLM Behavior

- Live model path: set `CODE_EXPLAINER_LLM_API_KEY` or `OPENAI_API_KEY`
- Optional overrides: `CODE_EXPLAINER_LLM_BASE_URL`, `CODE_EXPLAINER_LLM_MODEL`
- Offline proof path: set `CODE_EXPLAINER_MOCK_LLM=true`

If live LLM access is unavailable, the skill records that downgrade in `meta/llm_summary.json`.

## Self Audit

Run the shipped proof path:

```bash
cd code-explainer
python scripts/self_audit.py
```

This runs the skill against fixture repositories in `assets/fixtures/` and writes proof artifacts under `.audit_tmp/code-explainer-self/`.

## Current Status

The rebuilt skill audited at `97.1/100` and is currently `production-grade` under the local `audit-skill` rubric.

## Publishing

See `PUBLISHING.md` for GitHub publishing and distribution guidance.

## License

MIT. See `LICENSE`.
