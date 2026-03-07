# Output Contract

`code-explainer` writes the following deterministic output tree under `<output>/`:

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
11. `diagrams/excalidraw/*.excalidraw.json`
12. `diagrams/excalidraw/svg/*.svg`
13. `diagrams/excalidraw/png/*.png`
14. `meta/analysis_manifest.json`
15. `meta/confidence_report.json`
16. `meta/source_attribution.json`
17. `meta/index.json`
18. `meta/stack.json`
19. `meta/entrypoints.json`
20. `meta/dependencies.json`
21. `meta/flows.json`
22. `meta/diagram_manifest.json`
23. `meta/mermaid_validation.json`
24. `meta/render_report.json`
25. `meta/excalidraw_report.json`
26. `meta/enrichment.json`
27. `meta/coverage_report.json`
28. `meta/explainer_context.json`
29. `meta/verification_checkpoint.json`
30. `meta/explanation_plan.json`
31. `meta/llm_summary.json`
32. `meta/docs_generation.json`
33. `meta/html_generation.json` (when `--format html|both`)
34. `meta/fact_check_report.json`
35. `meta/content_completeness.json`
36. `meta/explanation_quality.json`
37. `meta/quality_report.json`

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
- `analysis_type`
- `include_globs[]`
- `exclude_globs[]`
- `docs_discovered`
- `docs_parsed`
- `llm_descriptions_enabled`
- `llm_descriptions_used`
- `llm_model`
- `verification_fact_count`
- `fact_check_passed`
- `excalidraw_export_requested`
- `excalidraw_export_status`
- `excalidraw_scene_count`
- `official_excalidraw_bridge_requested`
- `official_excalidraw_bridge_used`
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

## Explanation Plan Schema

`explanation_plan.json` contains:

- `repo_name`
- `summary_seed`
- `summary_seed_doc`
- `start_here[]`
- `top_modules[]` with `name`, `file_count`, `responsibility_hint`, `change_hint`, `sample_paths[]`
- `primary_flow_steps[]`
- `diagram_briefs[]`
- `caveats[]`

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
- `elevator_pitch`
- `audience_start_here[]`
- `module_explanations[]`
- `flow_explanation_steps[]`
- `diagram_briefs[]`
- `caveats[]`
- `confidence_notes[]`
- `error`
- `key_source`
- `persisted_key`
- `env_path`

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

## Explanation Quality Schema

`explanation_quality.json` contains:

- `score`
- `passed`
- `dimensions`
- `failures[]`
- `generic_phrase_hits`
- `avg_overview_sentence_length`

## Excalidraw Export Schema

`excalidraw_report.json` contains:

- `generated_at`
- `requested`
- `status` (`ok|partial|failed|environment_blocked|disabled`)
- `environment_blocked`
- `scene_count`
- `failed_count`
- `official_bridge_requested`
- `official_bridge_used`
- `warnings[]`
- `runtime`
- `results[]` where each result has:
- `diagram`
- `scene`
- `preview_svg`
- `preview_png`
- `status`
- `exporter`
- `element_count`
- `file_count`
- `preview_strategy`
- `warnings[]`
- `errors[]`

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
