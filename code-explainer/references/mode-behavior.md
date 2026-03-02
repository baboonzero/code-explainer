# Mode Behavior

## Quick

Goal: Fast orientation with lightweight outputs.

- Reduced dependency/flow depth.
- Core docs still generated.
- Fewer inferred critical paths.
- Lower documentation ingestion cap.

## Standard (Default)

Goal: Balanced fidelity and runtime for most repositories.

- Full required two-tier docs.
- Mandatory standard diagram set.
- Context + container + request + dependency views.
- Balanced doc ingestion and semantic quality checks.

## Deep

Goal: Maximum fidelity and audit-ready onboarding.

- Adds advanced diagrams and richer flow analysis.
- Includes trust boundary and data lineage outputs.
- Better suited for large or complex repos.
- Higher doc ingestion cap and longer extracted flow traces.

## Audience Behavior

- `nontech`: plain-language phrasing first, minimal jargon.
- `mixed`: business-and-technical balance.
- `engineering`: technical detail and traceability emphasis.
- If LLM narrative is enabled and available, wording is further adapted per audience.

## Overview Length

- `short`: executive skim.
- `medium`: balanced default.
- `long`: expanded onboarding context and references.

## LLM Narrative

- Controlled with `--llm-mode <auto|required|off>`.
- `auto`: try LLM when possible, otherwise continue with deterministic fallback.
- `required`: fail quality gate unless LLM narrative is successfully used.
- `off`: deterministic-only mode; no LLM attempt.
- Interactive controls (enabled by default in `analyze.py`):
- `--ask-before-llm-use true|false`
- `--prompt-for-llm-key true|false`
- Legacy compatibility: `--enable-llm-descriptions <true|false>` maps to `auto|off`.
- Reads API config from env vars:
- `CODE_EXPLAINER_LLM_API_KEY` (or `OPENAI_API_KEY`)
- `CODE_EXPLAINER_LLM_BASE_URL` (optional)
- `CODE_EXPLAINER_LLM_MODEL` (optional)

## Output Format

- `--format markdown`: generate markdown explainers (overview + deep docs).
- `--format html`: generate a single interactive HTML explainer page.
- `--format both`: generate markdown + interactive HTML.
- Default format is `both`.

## Output Layout

- `--output-layout compact`: default. Produces a minimal root with `START_HERE.md`, `DEEP_DIVE.md`, `ONBOARDING.html`, and stores full artifacts in `_details/`.
- `--output-layout full`: writes the full docs/diagrams/meta tree directly under output root.
- If `--output` is omitted:
- Local source: output goes to `<source>/code-explainer-output`.
- GitHub URL source: output goes to `<current-working-directory>/code-explainer-output`.

## Explainer Type

- `--explainer-type onboarding`: default onboarding narrative.
- `--explainer-type project-recap`: emphasizes recent activity and mental model refresh.
- `--explainer-type plan-review`: compares plan/spec references against actual codebase.
- `--explainer-type diff-review`: frames explainer around code changes from `--git-ref`.

Optional supporting flags:

- `--since "<window>"` for `project-recap` (default: `2 weeks ago`)
- `--plan-file <path>` for `plan-review`
- `--git-ref <ref>` for `diff-review`
