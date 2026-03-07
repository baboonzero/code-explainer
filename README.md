# code-explainer

`code-explainer` is a Codex skill for turning a local repository or GitHub repository URL into grounded onboarding material. It is explanation-first: it builds a narrative plan from real repo evidence, generates docs and diagrams from that plan, and proves output quality with a shipped self-audit.

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
- `diagrams/excalidraw/*.excalidraw.json`
- `diagrams/excalidraw/svg/*.svg`
- `diagrams/excalidraw/png/*.png`
- `meta/*.json`

Important proof artifacts:

- `meta/explanation_plan.json`
- `meta/explanation_quality.json`
- `meta/verification_checkpoint.json`
- `meta/fact_check_report.json`
- `meta/excalidraw_report.json`
- `meta/quality_report.json`

## Why This Version Is Better

The older build looked polished but produced weak output. The current contract is stricter:

- explanation planning happens before doc generation
- every diagram has an onboarding purpose
- Mermaid is the canonical diagram source
- editable Excalidraw scenes are generated from the same diagram set
- quality gates fail generic, weakly grounded, or incomplete output
- the repo ships fixture repos and a self-audit path

## Repository Layout

```text
code-explainer/
  SKILL.md
  package.json
  package-lock.json
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

## Runtime Dependencies

Required:

- Python `3.10+`
- Node.js `18+` and npm
- Git

Recommended:

- Mermaid CLI (`mmdc`) from `@mermaid-js/mermaid-cli`

Installed locally by the skill runtime:

- `@excalidraw/mermaid-to-excalidraw`

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

This copies the current skill package into `~/.codex/skills/code-explainer`. Restart Codex after installation, then run the skill runtime installer inside the installed copy if you need the local Node dependencies there.

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
  --enable-excalidraw-export true \
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
- `--enable-excalidraw-export true|false`

## Diagram and Excalidraw Behavior

- Mermaid remains the canonical source of truth.
- The skill exports editable Excalidraw scenes from that Mermaid set.
- If the official Excalidraw bridge works in the local runtime, it is used directly.
- If the official bridge is browser-dependent or unavailable, the skill falls back to a deterministic local scene generator for the Mermaid subset it emits and records that downgrade in `meta/excalidraw_report.json`.

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

The current build audits at `98.8/100` and is `production-grade` under the local `audit-skill` rubric. The self-audit currently proves:

- `2` fixture repositories
- `5` diagrams per fixture
- `5` Excalidraw scenes per fixture
- `97.1` explanation-quality score per fixture

## Publishing

See `PUBLISHING.md` for GitHub publishing and distribution guidance.

## License

MIT. See `LICENSE`.
