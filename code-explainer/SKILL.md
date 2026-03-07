---
name: code-explainer
description: Analyze a local codebase folder or GitHub repository URL and generate a grounded onboarding explainer with clear markdown docs, focused Mermaid/SVG/PNG diagrams, evidence anchors, and explanation-quality scoring. Use when users need a codebase explained in simple, concrete language for PM/design/new engineer onboarding.
---

# Code Explainer

Builds explanation-first repository explainers from local folders or GitHub URLs.

## What Good Output Looks Like

A good run must do all of the following:

1. Explain what the repository does in plain language.
2. Name real entrypoints, modules, docs, and flow steps from the repository.
3. Tell the reader where to start and where change risk lives.
4. Produce diagrams that answer specific onboarding questions.
5. Emit proof artifacts showing whether the explanation is actually useful.

This skill should fail quality gates if the output is generic, vague, or weakly grounded.

## Output Model

1. `overview/OVERVIEW.md` for the plain-language explanation.
2. `deep/*.md` for architecture, modules, flows, dependencies, and glossary.
3. `diagrams/*.mmd` plus rendered `diagrams/svg/*.svg` and `diagrams/png/*.png`.
4. `diagrams/excalidraw/*.excalidraw.json` plus mirrored preview assets under `diagrams/excalidraw/svg/*.svg` and `diagrams/excalidraw/png/*.png`.
5. `meta/explanation_plan.json` describing the intended narrative.
6. `meta/explanation_quality.json` scoring clarity, specificity, grounding, usefulness, diagram usefulness, and honesty.
7. `meta/excalidraw_report.json` proving whether editable Excalidraw scenes were created or why that export was blocked.
8. `meta/*.json` for indexing, verification, confidence, attribution, and quality reports.

See `references/output-contract.md` for exact artifacts and `references/evaluation-rubric.md` for the passing bar.

## Command

Run from this skill directory:

```bash
python scripts/analyze.py analyze \
  --source <local_path_or_github_url> \
  --output <output_dir> \
  --mode <quick|standard|deep> \
  --format <markdown|html|both> \
  --explainer-type <onboarding|project-recap|plan-review|diff-review> \
  --audience <nontech|mixed|engineering> \
  --overview-length <short|medium|long> \
  --since <time_window> \
  --git-ref <ref> \
  --plan-file <path> \
  --include-glob <pattern> \
  --exclude-glob <pattern> \
  --enable-llm-descriptions <true|false> \
  --enable-excalidraw-export <true|false> \
  --enable-official-excalidraw-bridge <true|false> \
  --ask-before-llm-use <true|false> \
  --prompt-for-llm-key <true|false> \
  --enable-web-enrichment <true|false>
```

Defaults:

- `mode=standard`
- `format=markdown`
- `explainer-type=onboarding`
- `audience=nontech`
- `overview-length=medium`
- `enable-llm-descriptions=true`
- `enable-excalidraw-export=true`
- `enable-official-excalidraw-bridge=false`
- `ask-before-llm-use=false`
- `prompt-for-llm-key=false`
- `enable-web-enrichment=true`

## LLM Behavior

- The high-quality path is explanation-first and uses `scripts/llm_describe.py`.
- If `CODE_EXPLAINER_LLM_API_KEY` or `OPENAI_API_KEY` is set, the skill can use a live model.
- If live LLM access is unavailable, the pipeline falls back to grounded deterministic wording and records that downgrade in `meta/llm_summary.json`.
- For proof runs and offline regression tests, set `CODE_EXPLAINER_MOCK_LLM=true` to exercise the full explanation pipeline without network access.

## Workflow

1. Normalize the source and build a repository index.
2. Detect stack, entrypoints, dependencies, flows, and documentation coverage.
3. Build `explanation_plan.json` with top modules, audience starting points, diagram purposes, and caveats.
4. Generate the narrative layer with LLM or grounded mock/deterministic fallback.
5. Build focused diagrams tied to onboarding questions.
6. Export those diagrams into editable Excalidraw scenes through the deterministic local exporter.
7. Optionally prefer the official Excalidraw bridge only when explicitly enabled for development experiments.
8. Generate overview and deep docs from the explanation plan plus narrative layer.
9. Run fact-check and explanation-quality evaluation.
10. Fail the run if quality gates do not clear the rubric.

## Proof Path

Run the shipped self-audit:

```bash
python scripts/self_audit.py
```

This runs the skill on fixture repositories in `assets/fixtures/`, uses the grounded mock explainer path, and writes proof artifacts under `.audit_tmp/code-explainer-self/`.

## Dependencies

Required:

- Python `3.10+`
- Node.js `18+` + npm
- Git when `--source` is a GitHub URL

Recommended:

- Mermaid CLI (`mmdc`) from `@mermaid-js/mermaid-cli` for higher-fidelity diagram rendering
- Node.js is only required for GitHub cloning and optional development-time Excalidraw bridge experiments

Install dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_runtime.ps1
```

or

```bash
bash ./scripts/install_runtime.sh
```

## Notes

- This skill does not mutate the analyzed repository.
- If the explanation-quality score is below the rubric threshold, treat the output as failed even if files were produced.
- If Excalidraw export is enabled, treat missing or partial editable scene generation as a real quality issue, not a cosmetic extra.
- The deterministic local Excalidraw exporter is the canonical production path.
- The official `@excalidraw/mermaid-to-excalidraw` bridge is opt-in only via `--enable-official-excalidraw-bridge true` and should be treated as a development experiment, not a required runtime dependency.
- Use include/exclude globs to narrow analysis when the repository is very large or noisy.

## References

- `references/output-contract.md`
- `references/diagram-style-guide.md`
- `references/persona-writing-guide.md`
- `references/mode-behavior.md`
- `references/evaluation-rubric.md`
