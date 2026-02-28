# Output Contract

`code-explainer` writes the following deterministic output tree under `<output>/`:

1. `overview/OVERVIEW.md`
2. `deep/ARCHITECTURE_DEEP.md`
3. `deep/MODULES_DEEP.md`
4. `deep/FLOWS_DEEP.md`
5. `deep/DEPENDENCIES_DEEP.md`
6. `deep/GLOSSARY.md`
7. `diagrams/*.mmd`
8. `diagrams/svg/*.svg`
9. `diagrams/png/*.png`
10. `meta/analysis_manifest.json`
11. `meta/confidence_report.json`
12. `meta/source_attribution.json`
13. `meta/index.json`
14. `meta/stack.json`
15. `meta/entrypoints.json`
16. `meta/dependencies.json`
17. `meta/flows.json`
18. `meta/diagram_manifest.json`
19. `meta/mermaid_validation.json`
20. `meta/render_report.json`
21. `meta/enrichment.json`
22. `meta/coverage_report.json`
23. `meta/llm_summary.json`
24. `meta/docs_generation.json`
25. `meta/quality_report.json`

## Manifest Schema

`analysis_manifest.json` includes:

- `source`
- `repo_root`
- `commit_ref`
- `scan_time`
- `mode`
- `languages`
- `frameworks`
- `entrypoints`
- `module_count`
- `diagram_count`
- `audience`
- `overview_length`
- `include_globs[]`
- `exclude_globs[]`
- `docs_discovered`
- `docs_parsed`
- `llm_descriptions_enabled`
- `llm_descriptions_used`
- `llm_model`

## Coverage Schema

`coverage_report.json` contains:

- `generated_at`
- `mode`
- `discovered_count`
- `parsed_count`
- `skipped_count`
- `discovered_docs[]`
- `parsed_docs[]` with `path`, `title`, `summary`, `headings[]`, `line_count`, `size_bytes`, `keywords[]`
- `skipped_docs[]` with `path`, `reason`

## LLM Narrative Schema

`llm_summary.json` contains:

- `generated_at`
- `enabled`
- `used`
- `asked_before_use`
- `prompted_for_key`
- `provider`
- `model`
- `repo_summary_paragraph`
- `directory_summaries[]` with `name`, `summary`
- `deep_dive_starters[]`
- `confidence_notes[]`
- `error`

## Confidence Schema

`confidence_report.json` contains:

- `generated_at`
- `claims[]` where each claim has:
- `claim_id`
- `claim_text`
- `evidence_paths[]`
- `confidence_score`
- `reason`

## Attribution Schema

`source_attribution.json` contains:

- `generated_at`
- `attributions[]` where each attribution has:
- `claim_id`
- `source_type` (`local`, `web`, or `deepwiki`)
- `source_uri`
- `extraction_timestamp`
