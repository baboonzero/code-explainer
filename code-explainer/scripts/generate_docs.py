#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _list_to_bullets(items: List[str], fallback: str = "- Not available", limit: int | None = None) -> str:
    if not items:
        return fallback
    scoped = items if limit is None else items[:limit]
    return "\n".join([f"- {item}" for item in scoped])


def _module_table(modules: List[Dict[str, Any]], limit: int = 20) -> str:
    lines = ["| Module | Type | File Count | Total Size (KB) |", "|---|---|---:|---:|"]
    for module in modules[:limit]:
        kb = round(module.get("total_bytes", 0) / 1024.0, 1)
        lines.append(
            f"| `{module['name']}` | {module.get('type', 'unknown')} | {module['file_count']} | {kb} |"
        )
    return "\n".join(lines)


def _entry_table(entries: List[Dict[str, str]], limit: int = 25) -> str:
    if not entries:
        return "_No clear entrypoints detected. See confidence and quality reports for caveats._"
    lines = ["| Path | Kind |", "|---|---|"]
    for entry in entries[:limit]:
        lines.append(f"| `{entry['path']}` | {entry['kind']} |")
    return "\n".join(lines)


def _dep_section(dep_payload: Dict[str, Any], max_per_manifest: int = 80) -> str:
    external = dep_payload.get("external_dependencies", {})
    if not external:
        return "_No dependency manifests detected._"
    chunks = []
    for manifest, deps in external.items():
        chunks.append(f"### `{manifest}`")
        if deps:
            chunks.append(_list_to_bullets([f"`{d}`" for d in deps[:max_per_manifest]]))
        else:
            chunks.append("- No dependencies parsed")
        chunks.append("")
    chunks.append(f"Internal dependency edges detected: **{dep_payload.get('internal_edge_count', 0)}**")
    return "\n".join(chunks)


def _diagram_links(diagram_manifest: Dict[str, Any]) -> str:
    links = []
    for file_name in diagram_manifest.get("diagram_files", []):
        stem = Path(file_name).stem
        links.append(f"- `{file_name}` | [SVG](../diagrams/svg/{stem}.svg) | [PNG](../diagrams/png/{stem}.png)")
    return "\n".join(links) if links else "- No diagrams generated."


def _where_to_modify(modules: List[Dict[str, Any]], limit: int) -> str:
    if not modules:
        return "- Start from detected entrypoint files, then trace dependencies in `module_dependency_graph.svg`."
    suggestions = []
    for module in modules[:limit]:
        name = module["name"]
        if name == "(root-files)":
            suggestions.append("- For startup/config changes, inspect top-level files listed in `(root-files)`.")
            continue
        suggestions.append(f"- For changes in **{name}**, start with `{name}/` and trace callers from entrypoints.")
    return "\n".join(suggestions)


def _example_leaves(module: Dict[str, Any], max_items: int = 3) -> str:
    leaves: List[str] = []
    for path in module.get("examples", [])[:10]:
        leaf = Path(path).name
        if not leaf or leaf in leaves:
            continue
        leaves.append(leaf)
        if len(leaves) >= max_items:
            break
    return ", ".join(leaves)


def _module_role_hint(module: Dict[str, Any]) -> str:
    name = str(module.get("name", "")).lower()
    examples = " ".join([str(x).lower() for x in module.get("examples", [])[:8]])
    context = f"{name} {examples}"

    if name in {"docs", "references", "reference", "documentation"} or any(
        token in context for token in ["readme", "guide", "handbook", "reference", ".md", ".rst"]
    ):
        return "contains onboarding and reference documentation"
    if name in {"scripts", "tools", "tooling"} or any(
        token in context for token in ["script", "tool", "cli", "command", "automation"]
    ):
        return "contains automation scripts and command-line tooling"
    if any(token in context for token in ["auth", "login", "identity", "account", "profile", "permission"]):
        return "handles identity, accounts, or access control flows"
    if any(token in context for token in ["api", "route", "router", "handler", "controller", "endpoint"]):
        return "exposes system interfaces and request entry paths"
    if any(token in context for token in ["ui", "page", "component", "frontend", "webapp", "screen"]):
        return "contains user-facing UI surfaces and interaction logic"
    if any(token in context for token in ["service", "core", "domain", "usecase", "business", "engine"]):
        return "implements core business logic and orchestration"
    if any(token in context for token in ["data", "db", "database", "repo", "model", "schema", "migration", "store"]):
        return "manages data modeling, persistence, or storage access"
    if any(token in context for token in ["worker", "queue", "job", "task", "cron", "background"]):
        return "runs asynchronous and background processing"
    if any(token in context for token in ["infra", "deploy", "k8s", "terraform", "docker", "helm"]):
        return "defines deployment and infrastructure configuration"
    if any(token in context for token in ["test", "spec", "e2e", "integration", "pytest", "jest"]):
        return "contains test coverage and quality checks"
    return "contains an important slice of system behavior and implementation"


def _llm_directory_summaries(llm_payload: Dict[str, Any], fallback_modules: List[Dict[str, Any]], limit: int = 8) -> str:
    items = llm_payload.get("directory_summaries", [])
    lines: List[str] = []
    if isinstance(items, list):
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if not name or not summary:
                continue
            lines.append(f"- **{name}**: {summary}")
    if lines:
        return "\n".join(lines)

    for module in fallback_modules[:limit]:
        name = module.get("name", "")
        if not name:
            continue
        file_count = int(module.get("file_count", 0))
        role = _module_role_hint(module)
        examples = _example_leaves(module)
        if examples:
            lines.append(
                f"- **{name}**: {role}. It has about {file_count} files, including `{examples}`."
            )
        else:
            lines.append(f"- **{name}**: {role}. It has about {file_count} files.")
    return "\n".join(lines) if lines else "- No directory-level summary available."


def _llm_deep_dive_starters(llm_payload: Dict[str, Any]) -> str:
    starters = llm_payload.get("deep_dive_starters", [])
    if not isinstance(starters, list) or not starters:
        return "- Start from entrypoints, then trace one request through dependencies."
    return "\n".join([f"- {str(item)}" for item in starters[:6]])


def _llm_confidence_notes(llm_payload: Dict[str, Any]) -> str:
    notes = llm_payload.get("confidence_notes", [])
    if not isinstance(notes, list) or not notes:
        if llm_payload.get("enabled", False) and not llm_payload.get("used", False):
            error = llm_payload.get("error", "LLM summary unavailable for this run.")
            return f"- {error}"
        return "- LLM summary disabled; deterministic analysis remains primary."
    return "\n".join([f"- {str(item)}" for item in notes[:6]])


def _glossary_terms(
    stack_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    module_payload: List[Dict[str, Any]],
    doc_payload: Dict[str, Any],
) -> List[Dict[str, str]]:
    terms: List[Dict[str, str]] = []
    frameworks = stack_payload.get("frameworks", [])
    for fw in frameworks:
        terms.append({"term": fw, "definition": f"{fw} framework used in this repository."})

    arch = stack_payload.get("architecture_pattern", "Architecture")
    terms.append({"term": arch, "definition": f"Detected architectural style: {arch}."})

    for manifest, deps in dep_payload.get("external_dependencies", {}).items():
        if deps:
            terms.append({"term": manifest, "definition": f"Dependency manifest containing {len(deps)} package entries."})

    for module in module_payload[:8]:
        terms.append(
            {
                "term": module["name"],
                "definition": f"Module/group with {module['file_count']} files in this codebase.",
            }
        )

    for doc in doc_payload.get("parsed_docs", [])[:8]:
        terms.append(
            {
                "term": Path(doc["path"]).name,
                "definition": f"Repository document used during analysis: {doc.get('title', '')}.",
            }
        )

    dedup = {}
    for item in terms:
        dedup[item["term"]] = item
    return list(dedup.values())[:50]


def _length_profile(overview_length: str) -> Dict[str, int]:
    if overview_length == "short":
        return {
            "module_limit": 10,
            "entry_limit": 10,
            "doc_link_limit": 4,
            "where_to_modify_limit": 4,
            "critical_path_limit": 3,
        }
    if overview_length == "long":
        return {
            "module_limit": 35,
            "entry_limit": 40,
            "doc_link_limit": 12,
            "where_to_modify_limit": 10,
            "critical_path_limit": 10,
        }
    return {
        "module_limit": 20,
        "entry_limit": 25,
        "doc_link_limit": 8,
        "where_to_modify_limit": 6,
        "critical_path_limit": 6,
    }


def _audience_note(audience: str) -> str:
    if audience == "engineering":
        return "This output prioritizes technical precision and traceability from entrypoints to dependencies."
    if audience == "mixed":
        return "This output balances plain-language onboarding with technical traceability for implementation handoff."
    return "This output prioritizes plain language and practical orientation before code-level detail."


def _mode_note(mode: str) -> str:
    if mode == "quick":
        return "Quick mode: bounded depth, concise explanations, and fewer critical paths."
    if mode == "deep":
        return "Deep mode: expanded flow tracing, richer diagrams, and stronger evidence notes."
    return "Standard mode: balanced depth for onboarding with reliable architecture and flow coverage."


def _overview_length_note(overview_length: str) -> str:
    if overview_length == "short":
        return "Overview length: short (executive skim)."
    if overview_length == "long":
        return "Overview length: long (extended onboarding context)."
    return "Overview length: medium (default readability)."


def _docs_summary(doc_payload: Dict[str, Any], limit: int) -> str:
    parsed = doc_payload.get("parsed_docs", [])
    if not parsed:
        return "- No repository docs were parsed; this overview is code-first."
    rows = []
    for doc in parsed[:limit]:
        title = doc.get("title", Path(doc["path"]).name)
        rows.append(f"- [`{doc['path']}`](../{doc['path']}) - {title}")
    return "\n".join(rows)


def _pick_summary_doc(parsed_docs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not parsed_docs:
        return None
    ranked = []
    for doc in parsed_docs:
        path = doc.get("path", "").lower()
        score = 0
        if "readme" in path:
            score += 100
        if "overview" in path or "getting-started" in path:
            score += 60
        if "setup" in path or "architecture" in path:
            score += 40
        if path.startswith("docs/"):
            score += 20
        if path.startswith("references/"):
            score -= 15
        ranked.append((score, doc))
    ranked.sort(key=lambda item: item[0], reverse=True)
    top_score, top_doc = ranked[0]
    if top_score < 20:
        return None
    return top_doc


def _docs_coverage_line(doc_payload: Dict[str, Any]) -> str:
    discovered = int(doc_payload.get("discovered_count", 0))
    parsed = int(doc_payload.get("parsed_count", 0))
    skipped = int(doc_payload.get("skipped_count", 0))
    if discovered == 0:
        return "No documentation files were discovered in this repository."
    return f"Docs coverage: parsed **{parsed}/{discovered}** docs (skipped: {skipped})."


def _plain_system_summary(
    repo_name: str,
    stack_payload: Dict[str, Any],
    doc_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    audience: str,
    index_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
) -> str:
    llm_summary = str(llm_payload.get("repo_summary_paragraph", "")).strip()
    if llm_summary:
        return llm_summary

    parsed_docs = doc_payload.get("parsed_docs", [])
    summary_doc = _pick_summary_doc(parsed_docs)
    architecture = stack_payload.get("architecture_pattern", "custom architecture")
    primary_language = stack_payload.get("primary_language", "Unknown")
    module_count = len(index_payload.get("modules", []))
    entry_count = len(entry_payload.get("entrypoints", []))
    external_dep_count = sum(
        len(deps) for deps in dep_payload.get("external_dependencies", {}).values() if isinstance(deps, list)
    )
    primary_steps = flow_payload.get("primary_user_flow", {}).get("steps", [])[:4]
    primary_flow = " -> ".join(primary_steps)

    if summary_doc:
        seed = summary_doc.get("summary", "").strip()
        if seed:
            suffix = (
                f" From code signals, it looks like a {architecture} system in {primary_language}, "
                f"organized into {module_count} top-level areas with {entry_count} likely entrypoints."
            )
            if primary_flow:
                suffix += f" A representative flow is: {primary_flow}."
            if audience == "engineering":
                return f"{seed}\n\n{suffix}"
            if audience == "mixed":
                return f"{seed}\n\n{suffix} This gives a practical map for product and engineering handoff."
            return f"{seed}\n\n{suffix}"

    frameworks = ", ".join(stack_payload.get("frameworks", [])[:4]) or "core platform libraries"
    if audience == "engineering":
        return (
            f"{repo_name} appears to be a {architecture} codebase built primarily in {primary_language} "
            f"on {frameworks}. It contains {module_count} top-level modules and {entry_count} likely entrypoints. "
            f"Detected external dependencies: {external_dep_count}. "
            "This summary is inferred from repository structure, dependency signals, and parsed documentation."
        )
    if audience == "mixed":
        return (
            f"{repo_name} appears to be organized as a {architecture} system built on {frameworks}. "
            f"The repository has {module_count} major code areas and {entry_count} likely entrypoints, which is "
            "a practical starting map for both product and engineering stakeholders."
        )
    return (
        f"{repo_name} is a working software system organized into about {module_count} major areas. "
        f"It is primarily {primary_language}-based, uses {frameworks}, and exposes around {entry_count} likely "
        "entrypoints where requests or commands begin. This explainer traces how information moves through the "
        "code so PMs, designers, and new engineers can understand what exists before reading files in depth."
    )


def _critical_path_lines(flow_payload: Dict[str, Any], limit: int) -> str:
    lines: List[str] = []
    for path in flow_payload.get("critical_paths", [])[:limit]:
        steps = " -> ".join(path.get("steps", []))
        lines.append(f"- **{path.get('name', 'Critical Path')}**: {steps}")
    return "\n".join(lines) if lines else "- No critical path extracted from dependency graph."


def _primary_flow_summary(flow_payload: Dict[str, Any]) -> str:
    flow = flow_payload.get("primary_user_flow", {})
    steps = flow.get("steps", [])
    if not steps:
        return "Primary user flow could not be confidently extracted from code; see quality report warnings."
    return " -> ".join(steps)


def _external_context_summary(enrichment_payload: Dict[str, Any]) -> str:
    records = enrichment_payload.get("records", [])
    if not records:
        return "No external enrichment records."
    available = [r for r in records if r.get("available") or r.get("status") == 200]
    if not available:
        return "External enrichment attempted but no usable external records were returned."
    labels = ", ".join(sorted({r.get("source", "unknown") for r in available}))
    return f"External enrichment sources used: {labels}."


def _analysis_focus_section(analysis_type: str, context_payload: Dict[str, Any]) -> str:
    if analysis_type == "project-recap":
        recap = context_payload.get("project_recap", {})
        if not recap.get("available"):
            return f"- Project recap context unavailable: {recap.get('reason', 'unknown')}"
        lines = [
            f"- Commit window: {recap.get('since', context_payload.get('since', 'n/a'))}",
            f"- Commits in window: {recap.get('commit_count', 0)}",
            f"- Contributors: {len(recap.get('contributors', []))}",
        ]
        top = recap.get("top_changed_files", [])
        if top:
            lines.append(
                f"- Most-touched file: `{top[0]['path']}` ({top[0]['touch_count']} touches)"
            )
        return "\n".join(lines)

    if analysis_type == "plan-review":
        plan = context_payload.get("plan_review", {})
        if not plan.get("available"):
            return f"- Plan review context unavailable: {plan.get('reason', 'unknown')}"
        lines = [
            f"- Plan file: `{plan.get('plan_file', 'n/a')}`",
            f"- Referenced files: {plan.get('referenced_files_count', 0)}",
            f"- Missing referenced files: {len(plan.get('referenced_missing_files', []))}",
            f"- Existing referenced files: {len(plan.get('referenced_existing_files', []))}",
        ]
        return "\n".join(lines)

    if analysis_type == "diff-review":
        diff = context_payload.get("diff_review", {})
        if not diff.get("available"):
            return f"- Diff context unavailable: {diff.get('reason', 'unknown')}"
        lines = [
            f"- Compared against ref: `{diff.get('git_ref', 'n/a')}`",
            f"- Changed files: {diff.get('changed_file_count', 0)}",
            f"- Added/Modified/Deleted: {diff.get('added_files', 0)}/{diff.get('modified_files', 0)}/{diff.get('deleted_files', 0)}",
        ]
        return "\n".join(lines)

    highlights = context_payload.get("highlights", [])
    if highlights:
        return "\n".join([f"- {item}" for item in highlights[:6]])
    return "- Onboarding mode focuses on system purpose, module boundaries, and critical flows."


def _mode_specific_context_block(analysis_type: str, context_payload: Dict[str, Any]) -> str:
    if analysis_type == "project-recap":
        recap = context_payload.get("project_recap", {})
        if not recap.get("available"):
            return f"- {recap.get('reason', 'Project recap context unavailable.')}"
        lines = ["### Recent Activity Snapshot"]
        for commit in recap.get("commit_sample", [])[:8]:
            lines.append(f"- `{commit}`")
        return "\n".join(lines)
    if analysis_type == "plan-review":
        plan = context_payload.get("plan_review", {})
        if not plan.get("available"):
            return f"- {plan.get('reason', 'Plan review context unavailable.')}"
        lines = ["### Plan File Coverage", f"- Plan file: `{plan.get('plan_file', 'n/a')}`"]
        missing = plan.get("referenced_missing_files", [])[:10]
        if missing:
            lines.append("- Missing referenced files:")
            for item in missing:
                lines.append(f"  - `{item}`")
        else:
            lines.append("- No missing referenced files detected.")
        return "\n".join(lines)
    if analysis_type == "diff-review":
        diff = context_payload.get("diff_review", {})
        if not diff.get("available"):
            return f"- {diff.get('reason', 'Diff context unavailable.')}"
        lines = ["### Diff Snapshot"]
        for row in diff.get("name_status_sample", [])[:12]:
            lines.append(f"- `{row.get('status', '?')}` `{row.get('path', '')}`")
        return "\n".join(lines)
    return "- Standard onboarding context."


def _apply_verification_evidence(claims: List[Dict[str, Any]], verification_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts = verification_payload.get("facts", [])
    fact_by_id = {fact.get("claim_id", ""): fact for fact in facts}
    for claim in claims:
        claim_id = claim.get("claim_id", "")
        fact = fact_by_id.get(claim_id)
        if not fact:
            continue
        locations = fact.get("evidence_locations", [])
        if locations:
            claim["evidence_locations"] = locations
        claim["verification_status"] = fact.get("status", "")
    return claims


def generate_docs(
    output_root: Path,
    templates_root: Path,
    source: str,
    mode: str,
    audience: str,
    overview_length: str,
    analysis_type: str,
    output_format: str,
    index_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    diagram_manifest: Dict[str, Any],
    docs_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
    verification_payload: Dict[str, Any],
    enrichment_payload: Dict[str, Any],
) -> Dict[str, Any]:
    overview_dir = common.ensure_dir(output_root / "overview")
    deep_dir = common.ensure_dir(output_root / "deep")

    profile = _length_profile(overview_length)

    modules = index_payload.get("modules", [])
    entrypoints = entry_payload.get("entrypoints", [])
    languages = stack_payload.get("languages", {})
    frameworks = stack_payload.get("frameworks", [])
    repo_name = stack_payload.get("repo_name", common.detect_repo_name(source, output_root))

    top_languages = ", ".join([f"{lang} ({count})" for lang, count in list(languages.items())[:5]]) or "Unknown"
    top_frameworks = ", ".join(frameworks[:8]) or "None detected"
    key_building_blocks = [m["name"] for m in modules[:7]]

    replacements_common = {
        "repo_name": repo_name,
        "source": source,
        "mode": mode,
        "analysis_type": analysis_type,
        "audience": audience,
        "overview_length": overview_length,
        "generated_at": common.now_iso(),
        "architecture_pattern": stack_payload.get("architecture_pattern", "Unknown"),
        "top_languages": top_languages,
        "top_frameworks": top_frameworks,
        "building_blocks": _list_to_bullets(key_building_blocks, "- No major blocks detected"),
        "entrypoints_table": _entry_table(entrypoints, limit=profile["entry_limit"]),
        "module_table": _module_table(modules, limit=profile["module_limit"]),
        "dependency_section": _dep_section(dep_payload),
        "diagram_links": _diagram_links(diagram_manifest),
        "where_to_modify": _where_to_modify(modules, limit=profile["where_to_modify_limit"]),
        "request_lifecycle": _list_to_bullets(flow_payload.get("request_lifecycle", [])),
        "critical_paths": _critical_path_lines(flow_payload, profile["critical_path_limit"]),
        "audience_note": _audience_note(audience),
        "mode_note": _mode_note(mode),
        "overview_length_note": _overview_length_note(overview_length),
        "plain_summary": _plain_system_summary(
            repo_name,
            stack_payload,
            docs_payload,
            llm_payload,
            audience,
            index_payload,
            entry_payload,
            dep_payload,
            flow_payload,
        ),
        "docs_coverage": _docs_coverage_line(docs_payload),
        "docs_quick_links": _docs_summary(docs_payload, profile["doc_link_limit"]),
        "primary_user_flow_summary": _primary_flow_summary(flow_payload),
        "external_context_summary": _external_context_summary(enrichment_payload),
        "analysis_focus_section": _analysis_focus_section(analysis_type, context_payload),
        "mode_specific_context": _mode_specific_context_block(analysis_type, context_payload),
        "directory_plain_summaries": _llm_directory_summaries(llm_payload, modules, limit=profile["module_limit"]),
        "llm_deep_dive_starters": _llm_deep_dive_starters(llm_payload),
        "llm_confidence_notes": _llm_confidence_notes(llm_payload),
        "llm_enabled": "true" if llm_payload.get("enabled", False) else "false",
        "llm_used": "true" if llm_payload.get("used", False) else "false",
    }

    overview_template = common.load_template(templates_root / "overview.md.j2")
    arch_template = common.load_template(templates_root / "deep_architecture.md.j2")
    modules_template = common.load_template(templates_root / "deep_modules.md.j2")
    flows_template = common.load_template(templates_root / "deep_flows.md.j2")
    glossary_template = common.load_template(templates_root / "glossary.md.j2")

    overview_text = common.render_template(overview_template, replacements_common)
    arch_text = common.render_template(arch_template, replacements_common)
    modules_text = common.render_template(modules_template, replacements_common)
    flows_text = common.render_template(flows_template, replacements_common)

    glossary_terms = _glossary_terms(stack_payload, dep_payload, modules, docs_payload)
    glossary_lines = "\n".join([f"- **{item['term']}**: {item['definition']}" for item in glossary_terms])
    glossary_text = common.render_template(glossary_template, {**replacements_common, "glossary_entries": glossary_lines})

    dependencies_deep = f"""# Dependencies Deep Explainer

Generated at: {common.now_iso()}

## External Dependencies

{_dep_section(dep_payload)}

## Explainer Focus

{_analysis_focus_section(analysis_type, context_payload)}

## Internal Dependency Footprint

- Internal edge count: **{dep_payload.get('internal_edge_count', 0)}**
- Parsed edge sample size: **{len(dep_payload.get('internal_edges', []))}**

## Risk and Upgrade Callouts

- Review dependencies with no recent update policy.
- Prioritize auth, networking, and serialization packages for security review.
- Confirm lockfile hygiene and reproducible installs for onboarding reliability.
"""
    wrote_markdown = output_format in {"markdown", "both"}
    if wrote_markdown:
        (overview_dir / "OVERVIEW.md").write_text(overview_text, encoding="utf-8")
        (deep_dir / "ARCHITECTURE_DEEP.md").write_text(arch_text, encoding="utf-8")
        (deep_dir / "MODULES_DEEP.md").write_text(modules_text, encoding="utf-8")
        (deep_dir / "FLOWS_DEEP.md").write_text(flows_text, encoding="utf-8")
        (deep_dir / "DEPENDENCIES_DEEP.md").write_text(dependencies_deep, encoding="utf-8")
        (deep_dir / "GLOSSARY.md").write_text(glossary_text, encoding="utf-8")

    claims = [
        common.collect_claim(
            "claim_primary_language",
            f"Primary language appears to be {stack_payload.get('primary_language', 'Unknown')}.",
            ["meta/index.json", "meta/stack.json"],
            0.88,
            "Derived from file extension distribution",
        ),
        common.collect_claim(
            "claim_architecture",
            f"Detected architecture pattern is {stack_payload.get('architecture_pattern', 'Unknown')}.",
            ["meta/stack.json"],
            0.72,
            "Heuristic directory and dependency pattern matching",
        ),
        common.collect_claim(
            "claim_entrypoints",
            f"Detected {len(entrypoints)} likely entrypoint files.",
            ["meta/entrypoints.json"],
            0.82,
            "Filename and source-content bootstrap heuristics",
        ),
        common.collect_claim(
            "claim_doc_coverage",
            f"Parsed {docs_payload.get('parsed_count', 0)} of {docs_payload.get('discovered_count', 0)} documentation files.",
            ["meta/coverage_report.json"],
            0.9,
            "Deterministic documentation ingestion pass",
        ),
        common.collect_claim(
            "claim_diagram_set",
            f"Generated {diagram_manifest.get('count', 0)} Mermaid diagrams for onboarding and deep dives.",
            ["meta/diagram_manifest.json"],
            0.95,
            "Deterministic diagram build output",
        ),
        common.collect_claim(
            "claim_analysis_type",
            f"Explainer mode is {analysis_type}.",
            ["meta/explainer_context.json"],
            0.93,
            "Based on explicit CLI selection and generated context artifact.",
        ),
    ]

    if llm_payload.get("used", False):
        claims.append(
            common.collect_claim(
                "claim_llm_narrative",
                "An LLM-generated narrative summary was incorporated for repository and directory explainers.",
                ["meta/llm_summary.json"],
                0.7,
                "Generated from deterministic context payload + model inference.",
            )
        )

    if enrichment_payload.get("records"):
        claims.append(
            common.collect_claim(
                "claim_external_enrichment",
                "External context enrichment was attempted for this analysis.",
                ["meta/enrichment.json"],
                0.66,
                "Network sources may vary over time; local analysis remains primary.",
            )
        )

    claims = _apply_verification_evidence(claims, verification_payload)

    payload = {
        "generated_at": common.now_iso(),
        "overview_file": "overview/OVERVIEW.md" if wrote_markdown else "",
        "deep_files": [
            "deep/ARCHITECTURE_DEEP.md",
            "deep/MODULES_DEEP.md",
            "deep/FLOWS_DEEP.md",
            "deep/DEPENDENCIES_DEEP.md",
            "deep/GLOSSARY.md",
        ] if wrote_markdown else [],
        "output_format": output_format,
        "analysis_type": analysis_type,
        "wrote_markdown": wrote_markdown,
        "audience": audience,
        "mode": mode,
        "overview_length": overview_length,
        "claims": claims,
    }
    common.write_json(output_root / "meta" / "docs_generation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate two-tier markdown explainers.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--templates-root", required=True)
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--overview-length", default="medium", choices=["short", "medium", "long"])
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--output-format", default="markdown")
    parser.add_argument("--index", required=True)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--diagram-manifest", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--llm-summary", required=True)
    parser.add_argument("--explainer-context", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--enrichment", required=True)
    args = parser.parse_args()

    payload = generate_docs(
        output_root=Path(args.output_root).resolve(),
        templates_root=Path(args.templates_root).resolve(),
        source=args.source,
        mode=common.normalize_mode(args.mode),
        audience=args.audience,
        overview_length=args.overview_length,
        analysis_type=args.analysis_type,
        output_format=args.output_format,
        index_payload=common.read_json(Path(args.index), default={}),
        stack_payload=common.read_json(Path(args.stack), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        diagram_manifest=common.read_json(Path(args.diagram_manifest), default={}),
        docs_payload=common.read_json(Path(args.coverage), default={}),
        llm_payload=common.read_json(Path(args.llm_summary), default={}),
        context_payload=common.read_json(Path(args.explainer_context), default={}),
        verification_payload=common.read_json(Path(args.verification), default={}),
        enrichment_payload=common.read_json(Path(args.enrichment), default={}),
    )
    print(json.dumps({"overview": payload["overview_file"], "deep_count": len(payload["deep_files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
