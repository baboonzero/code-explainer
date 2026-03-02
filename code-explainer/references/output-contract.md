# Output Contract

`code-explainer` supports two output layouts:

1. `compact` (default)
2. `full`

## Compact Layout (Default)

Written under `<output>/`:

1. `START_HERE.md`
2. `DEEP_DIVE.md`
3. `ONBOARDING.html` (when `--format html|both`)
4. `_details/` containing the full artifact tree listed below

## Full Layout

Written directly under `<output>/`:

1. `overview/OVERVIEW.md` (when `--format markdown|both`)
2. `deep/ARCHITECTURE_DEEP.md` (when `--format markdown|both`)
3. `deep/MODULES_DEEP.md` (when `--format markdown|both`)
4. `deep/FLOWS_DEEP.md` (when `--format markdown|both`)
5. `deep/DEPENDENCIES_DEEP.md` (when `--format markdown|both`)
6. `deep/GLOSSARY.md` (when `--format markdown|both`)
7. `html/ONBOARDING.html` (when `--format html|both`)
8. `diagrams/*.mmd`
9. `diagrams/svg/*.svg`
10. `diagrams/png/*.png`
11. `meta/analysis_manifest.json`
12. `meta/confidence_report.json`
13. `meta/source_attribution.json`
14. `meta/index.json`
15. `meta/stack.json`
16. `meta/entrypoints.json`
17. `meta/dependencies.json`
18. `meta/flows.json`
19. `meta/diagram_manifest.json`
20. `meta/mermaid_validation.json`
21. `meta/render_report.json`
22. `meta/enrichment.json`
23. `meta/coverage_report.json`
24. `meta/explainer_context.json`
25. `meta/verification_checkpoint.json`
26. `meta/llm_summary.json`
27. `meta/docs_generation.json`
28. `meta/html_generation.json` (when `--format html|both`)
29. `meta/fact_check_report.json`
30. `meta/content_completeness.json`
31. `meta/quality_report.json`
32. `meta/compact_output.json` (when `--output-layout compact`)

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
- `output_format`
- `output_layout`
- `analysis_type`
- `include_globs[]`
- `exclude_globs[]`
- `compact_entry_files[]`
- `docs_discovered`
- `docs_parsed`
- `llm_descriptions_enabled`
- `llm_descriptions_used`
- `llm_mode`
- `llm_model`
- `verification_fact_count`
- `fact_check_passed`
- `html_generated`

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

## Explainer Context Schema

`explainer_context.json` contains:

- `generated_at`
- `analysis_type` (`onboarding|project-recap|plan-review|diff-review`)
- `source`
- `repo_root`
- `since`
- `git_ref`
- `plan_file`
- `project_recap` (mode-specific)
- `plan_review` (mode-specific)
- `diff_review` (mode-specific)
- `highlights[]`

## Verification Schema

`verification_checkpoint.json` contains:

- `generated_at`
- `analysis_type`
- `fact_count`
- `facts[]` with:
- `claim_id`
- `claim_text`
- `expected_text`
- `must_include_tokens[]`
- `status`
- `evidence_locations[]` with `path`, `line`, `excerpt`

## LLM Narrative Schema

`llm_summary.json` contains:

- `generated_at`
- `enabled`
- `llm_mode`
- `used`
- `asked_before_use`
- `consent_granted`
- `consent_mode`
- `prompted_for_key`
- `api_key_source`
- `provider`
- `model`
- `repo_summary_paragraph`
- `directory_summaries[]` with `name`, `summary`
- `deep_dive_starters[]`
- `confidence_notes[]`
- `error`

## Fact-Check Schema

`fact_check_report.json` contains:

- `checked_at`
- `output_format`
- `analysis_type`
- `fact_count`
- `confirmed_count`
- `mismatch_count`
- `passed`
- `checks[]`
- `advisory_checks[]`

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
