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

Two-tier docs + rendered diagrams:

1. `overview/OVERVIEW.md` for non-technical orientation.
2. `deep/*.md` explainers for architecture, modules, flows, dependencies, and glossary.
3. `diagrams/*.mmd` + rendered `diagrams/svg/*.svg` and `diagrams/png/*.png`.
4. `meta/*.json` quality, confidence, and attribution artifacts.

See `references/output-contract.md` for exact files and semantics.

## Command

Run from this skill directory:

```bash
python scripts/analyze.py analyze \
  --source <local_path_or_github_url> \
  --output <output_dir> \
  --mode <quick|standard|deep> \
  --audience <nontech|mixed|engineering> \
  --enable-web-enrichment <true|false>
```

Defaults:

- `mode=standard`
- `audience=nontech`
- `enable-web-enrichment=true`

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
4. Optional DeepWiki + web enrichment with attribution.
5. Mermaid generation (Context + Container + flow set).
6. Mermaid validation.
7. SVG then PNG rendering.
8. Overview + deep markdown generation.
9. Quality gates and confidence report generation.

## Notes

- For GitHub URLs, `git` must be available on PATH.
- For high-fidelity diagram rendering, `mmdc` should be installed.
- Without `mmdc`, fallback rendering is used and flagged in reports.
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
