---
name: code-explainer
description: Analyze a local codebase folder or GitHub repository URL and generate a two-tier onboarding explainer (crisp overview + deep-dive docs) with Mermaid, SVG, and PNG diagrams. Use when users need fast, high-fidelity understanding of an unfamiliar repository for PM/designer/new engineer onboarding.
---

# Code Explainer

Builds onboarding-grade repository explainers from local or GitHub sources.

## Use Cases

- New joiners who need a 10-minute understanding of a codebase.
- PM/design onboarding where code details must be translated to plain language.
- Engineering onboarding requiring architecture, module, flow, and dependency views.

## Output Model

Compact-first output + detailed artifacts:

1. Compact entry files (default): `START_HERE.md`, `SYSTEM_DEEP_DIVE.md`, `ONBOARDING.html`.
2. Detailed artifacts under `evidence/` in compact layout.
3. Optional full layout writes docs/diagrams/meta directly under output root.
4. Detailed docs include `overview/OVERVIEW.md` and `deep/SYSTEM_DEEP_DIVE.md`.
5. Diagrams include `.mmd`, `.svg`, and `.png`.
6. Metadata includes quality, confidence, attribution, verification, and fact-check reports.

See `references/output-contract.md` for exact files and semantics.

## Command

Run from this skill directory:

```bash
python scripts/analyze.py analyze \
  --source <local_path_or_github_url> \
  --output <optional_output_dir> \
  --mode <quick|standard|deep> \
  --format <markdown|html|both> \
  --output-layout <compact|full> \
  --explainer-type <onboarding|project-recap|plan-review|diff-review> \
  --audience <nontech|mixed|engineering> \
  --overview-length <short|medium|long> \
  --since <time_window> \
  --git-ref <ref> \
  --plan-file <path> \
  --include-glob <pattern> \
  --exclude-glob <pattern> \
  --llm-mode <auto|required|off> \
  --ask-before-llm-use <true|false> \
  --prompt-for-llm-key <true|false> \
  --enable-web-enrichment <true|false>
```

Defaults:

- `mode=standard`
- `format=both`
- `output-layout=compact`
- `explainer-type=onboarding`
- `audience=nontech`
- `overview-length=medium`
- `llm-mode=auto`
- `ask-before-llm-use=true` (interactive terminals)
- `prompt-for-llm-key=true` (interactive terminals)
- `enable-web-enrichment=true`
- `output` is optional:
- local source -> `<source>/code-explainer-output`
- GitHub URL -> `<current-working-directory>/code-explainer-output`

## Dependencies

Required:

- Python `3.10+`
- Node.js `18+` + npm
- Git (required when `--source` is a GitHub URL)

Recommended for high-quality rendering:

- Mermaid CLI (`mmdc`) from `@mermaid-js/mermaid-cli`

Install dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_runtime.ps1
```

or

```bash
bash ./scripts/install_runtime.sh
```

## Workflow

1. Intake and source normalization.
2. Local index build (files/modules/symbol candidates).
3. Stack/entrypoint/dependency/flow extraction.
4. Documentation ingestion (`coverage_report.json`).
5. Mode-specific context extraction (`explainer_context.json`).
6. Verification checkpoint generation (`verification_checkpoint.json`).
7. Optional LLM narrative generation (`llm_summary.json`).
8. Optional DeepWiki + web enrichment with attribution.
9. Mermaid generation (Context + Container + flow set).
10. Mermaid validation.
11. SVG then PNG rendering.
12. Markdown and/or HTML explainer generation.
13. Fact-check pass (`fact_check_report.json`).
14. Quality gates, completeness checks, and confidence report generation.

## Notes

- For GitHub URLs, `git` must be available on PATH.
- For high-fidelity diagram rendering, `mmdc` should be installed.
- Without `mmdc`, fallback rendering is used and flagged in reports.
- For LLM narrative summaries, set `CODE_EXPLAINER_LLM_API_KEY` (or `OPENAI_API_KEY`).
- Optional: set `CODE_EXPLAINER_LLM_BASE_URL` and `CODE_EXPLAINER_LLM_MODEL`.
- Interactive prompts are supported:
- `--ask-before-llm-use true`
- `--prompt-for-llm-key true`
- If you need strict narrative generation, run with `--llm-mode required`.
- Legacy flag remains supported: `--enable-llm-descriptions <true|false>`.
- This skill does not mutate the analyzed target repository.

## Dependency Troubleshooting

- If `mmdc` is not found: run `npm install -g @mermaid-js/mermaid-cli`, open a new terminal, then run `mmdc --version`.
- If Mermaid rendering fails with browser launch errors: reinstall Mermaid CLI and retry.
- If global npm install fails with permissions: use an elevated shell (Windows) or a Node version manager (macOS/Linux).
- If `python` is not found: install Python 3.10+ and ensure it is on `PATH`.
- If `git` is not found: install Git (required for GitHub URL source mode).

## References

- `references/output-contract.md`
- `references/diagram-style-guide.md`
- `references/persona-writing-guide.md`
- `references/mode-behavior.md`
