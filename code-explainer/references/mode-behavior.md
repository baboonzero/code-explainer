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

- Controlled with `--enable-llm-descriptions <true|false>`.
- Optional interactive controls:
- `--ask-before-llm-use true`
- `--prompt-for-llm-key true`
- Reads API config from env vars:
- `CODE_EXPLAINER_LLM_API_KEY` (or `OPENAI_API_KEY`)
- `CODE_EXPLAINER_LLM_BASE_URL` (optional)
- `CODE_EXPLAINER_LLM_MODEL` (optional)
