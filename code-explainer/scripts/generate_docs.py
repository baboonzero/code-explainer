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


def _bullets(items: List[str], fallback: str = "- Not available") -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return fallback
    return "\n".join([f"- {item}" for item in cleaned])


def _numbered(items: List[str], fallback: str = "1. Not available") -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return fallback
    return "\n".join([f"{index}. {item}" for index, item in enumerate(cleaned, start=1)])


def _repo_summary(
    repo_name: str,
    stack_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    plan_payload: Dict[str, Any],
) -> str:
    summary = str(llm_payload.get("repo_summary_paragraph", "")).strip()
    if summary:
        return summary
    seed = str(plan_payload.get("summary_seed", "")).strip()
    if seed:
        return seed
    frameworks = ", ".join(stack_payload.get("frameworks", [])[:3]) or stack_payload.get("primary_language", "the detected stack")
    architecture = stack_payload.get("architecture_pattern", "a custom structure")
    return (
        f"{repo_name} appears to be organized as {architecture.lower()} and built on {frameworks}. "
        "This summary is grounded in repository structure, entrypoints, dependencies, and any parsed docs."
    )


def _module_explanations(llm_payload: Dict[str, Any], plan_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    llm_modules = llm_payload.get("module_explanations", [])
    if isinstance(llm_modules, list) and llm_modules:
        return [item for item in llm_modules if isinstance(item, dict)]
    fallback = []
    for item in plan_payload.get("top_modules", [])[:8]:
        samples = item.get("sample_paths", [])
        fallback.append(
            {
                "name": item.get("name", ""),
                "responsibility": item.get("responsibility_hint", ""),
                "why_it_matters": item.get("change_hint", ""),
                "first_file_to_open": samples[0] if samples else "",
                "sample_paths": samples,
            }
        )
    return fallback


def _flow_explanations(llm_payload: Dict[str, Any], plan_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps = llm_payload.get("flow_explanation_steps", [])
    if isinstance(steps, list) and steps:
        return [item for item in steps if isinstance(item, dict)]
    fallback = []
    for step in plan_payload.get("primary_flow_steps", [])[:6]:
        fallback.append(
            {
                "step": step,
                "what_happens": f"The main flow passes through `{step}`.",
                "why_it_matters": "This helps a new reader follow the core behavior end-to-end.",
            }
        )
    return fallback


def _diagram_briefs(llm_payload: Dict[str, Any], plan_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = llm_payload.get("diagram_briefs", [])
    if isinstance(items, list) and items:
        return [item for item in items if isinstance(item, dict)]
    fallback = []
    for item in plan_payload.get("diagram_briefs", [])[:8]:
        fallback.append(
            {
                "id": item.get("id", ""),
                "caption": item.get("purpose", ""),
                "takeaway": item.get("reader_question", ""),
            }
        )
    return fallback


def _module_cards_text(modules: List[Dict[str, Any]], max_items: int = 6) -> str:
    sections: List[str] = []
    for item in modules[:max_items]:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        sections.append(f"### `{name}`")
        responsibility = str(item.get("responsibility", "") or item.get("responsibility_hint", "")).strip()
        if responsibility:
            sections.append(f"- Role: {responsibility}")
        why = str(item.get("why_it_matters", "") or item.get("change_hint", "")).strip()
        if why:
            sections.append(f"- Why it matters: {why}")
        first_file = str(item.get("first_file_to_open", "")).strip()
        if first_file:
            sections.append(f"- First file to open: `{first_file}`")
        sample_paths = item.get("sample_paths", [])
        if isinstance(sample_paths, list) and sample_paths:
            sections.append(f"- Evidence: {', '.join([f'`{path}`' for path in sample_paths[:3]])}")
        sections.append("")
    return "\n".join(sections).strip() or "No module cards available."


def _flow_text(flows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for index, item in enumerate(flows, start=1):
        step = str(item.get("step", "")).strip()
        if not step:
            continue
        lines.append(f"{index}. **{step}**")
        what_happens = str(item.get("what_happens", "")).strip()
        if what_happens:
            lines.append(f"   What happens: {what_happens}")
        why = str(item.get("why_it_matters", "")).strip()
        if why:
            lines.append(f"   Why it matters: {why}")
    return "\n".join(lines) if lines else "1. No primary flow explanation available."


def _diagram_text(diagram_briefs: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for item in diagram_briefs:
        diagram_id = str(item.get("id", "")).strip()
        if not diagram_id:
            continue
        caption = str(item.get("caption", "")).strip()
        takeaway = str(item.get("takeaway", "")).strip()
        lines.append(f"- `{diagram_id}.svg`: {caption}")
        if takeaway:
            lines.append(f"  Read it to answer: {takeaway}")
    return "\n".join(lines) if lines else "- No diagram briefs available."


def _evidence_block(plan_payload: Dict[str, Any], docs_payload: Dict[str, Any], entry_payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    summary_doc = str(plan_payload.get("summary_seed_doc", "")).strip()
    if summary_doc:
        lines.append(f"- Primary doc used for intent: `{summary_doc}`")
    entrypoints = entry_payload.get("entrypoints", [])
    if entrypoints:
        lines.append(f"- Primary entrypoint: `{entrypoints[0].get('path', '')}`")
    parsed_docs = docs_payload.get("parsed_docs", [])
    if parsed_docs:
        extra = [f"`{doc.get('path', '')}`" for doc in parsed_docs[:4] if doc.get("path")]
        if extra:
            lines.append(f"- Additional docs: {', '.join(extra)}")
    return "\n".join(lines) if lines else "- No strong evidence anchors were available."


def _dependencies_text(dep_payload: Dict[str, Any]) -> str:
    manifests = dep_payload.get("external_dependencies", {})
    if not manifests:
        return "_No dependency manifests were parsed._"
    sections: List[str] = []
    for manifest, deps in manifests.items():
        sections.append(f"### `{manifest}`")
        if deps:
            sections.append(_bullets([f"`{dep}`" for dep in deps[:30]]))
        else:
            sections.append("- No dependencies parsed")
        sections.append("")
    sections.append(f"Internal import edges detected: **{dep_payload.get('internal_edge_count', 0)}**")
    return "\n".join(sections).strip()


def _glossary_text(stack_payload: Dict[str, Any], dep_payload: Dict[str, Any], modules: List[Dict[str, Any]], docs_payload: Dict[str, Any]) -> str:
    entries: List[str] = []
    for framework in stack_payload.get("frameworks", [])[:6]:
        entries.append(f"- **{framework}**: Framework detected in the repository dependencies.")
    entries.append(f"- **{stack_payload.get('architecture_pattern', 'Architecture')}**: Detected repository organization pattern.")
    for item in modules[:5]:
        name = str(item.get("name", "")).strip()
        responsibility = str(item.get("responsibility", "") or item.get("responsibility_hint", "")).strip()
        if name and responsibility:
            entries.append(f"- **{name}**: {responsibility}")
    for manifest in dep_payload.get("external_dependencies", {}).keys():
        entries.append(f"- **{manifest}**: Dependency manifest parsed during analysis.")
    for doc in docs_payload.get("parsed_docs", [])[:4]:
        title = str(doc.get("title", "")).strip()
        path = str(doc.get("path", "")).strip()
        if title and path:
            entries.append(f"- **{title}**: Documentation source at `{path}`.")
    return "\n".join(dict.fromkeys(entries)) if entries else "- No glossary terms extracted."


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
    plan_payload: Dict[str, Any],
    verification_payload: Dict[str, Any],
    enrichment_payload: Dict[str, Any],
) -> Dict[str, Any]:
    del templates_root, context_payload, verification_payload, enrichment_payload
    overview_dir = common.ensure_dir(output_root / "overview")
    deep_dir = common.ensure_dir(output_root / "deep")
    wrote_markdown = output_format in {"markdown", "both"}

    repo_name = stack_payload.get("repo_name", common.detect_repo_name(source, output_root))
    summary = _repo_summary(repo_name, stack_payload, llm_payload, plan_payload)
    pitch = str(llm_payload.get("elevator_pitch", "")).strip()
    modules = _module_explanations(llm_payload, plan_payload)
    flows = _flow_explanations(llm_payload, plan_payload)
    diagram_briefs = _diagram_briefs(llm_payload, plan_payload)
    audience_start = llm_payload.get("audience_start_here", []) if isinstance(llm_payload.get("audience_start_here", []), list) else []
    if not audience_start:
        audience_start = plan_payload.get("start_here", [])
    caveats = llm_payload.get("caveats", []) if isinstance(llm_payload.get("caveats", []), list) and llm_payload.get("caveats", []) else plan_payload.get("caveats", [])
    confidence_notes = llm_payload.get("confidence_notes", []) if isinstance(llm_payload.get("confidence_notes", []), list) else []

    architecture_pattern = stack_payload.get("architecture_pattern", "Unknown")
    languages = ", ".join([f"{lang} ({count})" for lang, count in list(stack_payload.get("languages", {}).items())[:5]]) or "Unknown"
    frameworks = ", ".join(stack_payload.get("frameworks", [])[:6]) or "None detected"
    primary_flow_summary = " -> ".join(plan_payload.get("primary_flow_steps", [])[:6]) or "Not confidently extracted"
    diagram_index_text = _diagram_text(diagram_briefs)
    evidence_block = _evidence_block(plan_payload, docs_payload, entry_payload)

    overview_text = f"""# {repo_name}: Overview

Generated: {common.now_iso()}
Source: `{source}`
Mode: `{mode}`
Audience: `{audience}`
Analysis type: `{analysis_type}`
Length profile: `{overview_length}`

## What This Repository Does

{summary}

{pitch}

## How The Codebase Is Organized

- Detected architecture: **{architecture_pattern}**
- Languages: {languages}
- Frameworks: {frameworks}

{_module_cards_text(modules, max_items=5)}

## Core Request Or Product Flow

{_flow_text(flows[:5])}

Primary extracted flow: `{primary_flow_summary}`

## Where To Start

{_numbered([str(item) for item in audience_start])}

## Diagram Guide

{diagram_index_text}

## Evidence Used

{evidence_block}

## Caveats And Confidence

{_bullets([str(item) for item in caveats], fallback='- No major caveats recorded.')}

{_bullets([str(item) for item in confidence_notes], fallback='- Confidence is based on extracted repository evidence.')}

## Deep Dive Links

- [Architecture](../deep/ARCHITECTURE_DEEP.md)
- [Modules](../deep/MODULES_DEEP.md)
- [Flows](../deep/FLOWS_DEEP.md)
- [Dependencies](../deep/DEPENDENCIES_DEEP.md)
- [Glossary](../deep/GLOSSARY.md)
"""

    architecture_text = f"""# Architecture Deep Explainer

Generated: {common.now_iso()}

## System Thesis

{summary}

## Why This Shape Matters

- Detected architecture: **{architecture_pattern}**
- Dominant stack: {frameworks}
- Main languages: {languages}

## Entrypoints

{_bullets([f"`{item.get('path', '')}` - {item.get('kind', '')}" for item in entry_payload.get('entrypoints', [])[:10]], fallback='- No clear entrypoints detected.')}

## Main Building Blocks

{_module_cards_text(modules, max_items=8)}

## Diagram Intent

{diagram_index_text}

## Evidence

{evidence_block}
"""

    modules_text = f"""# Modules Deep Explainer

Generated: {common.now_iso()}

## Module Cards

{_module_cards_text(modules, max_items=10)}

## Safe Change Guidance

{_bullets([str(item.get('why_it_matters', '') or item.get('change_hint', '')) for item in modules[:8]], fallback='- No change guidance available.')}

## Documentation Anchors

{_bullets([f"`{doc.get('path', '')}` - {doc.get('title', '')}" for doc in docs_payload.get('parsed_docs', [])[:8]], fallback='- No parsed documentation anchors.')}
"""

    critical_paths = []
    for item in flow_payload.get("critical_paths", [])[:6]:
        steps = " -> ".join(item.get("steps", [])[:8])
        if steps:
            critical_paths.append(f"**{item.get('name', 'Critical path')}**: {steps}")

    flows_text = f"""# Flows Deep Explainer

Generated: {common.now_iso()}

## Main Flow

{_flow_text(flows[:8])}

## Request Lifecycle

{_bullets([str(item) for item in flow_payload.get('request_lifecycle', [])], fallback='- No request lifecycle extracted.')}

## Critical Paths

{_bullets(critical_paths, fallback='- No critical paths extracted.')}

## Trust Boundaries

{_bullets([f"{item.get('name', '')} ({item.get('type', '')})" for item in flow_payload.get('trust_boundaries', [])], fallback='- No trust boundaries extracted.')}
"""

    dependencies_text = f"""# Dependencies Deep Explainer

Generated: {common.now_iso()}

## External Dependencies

{_dependencies_text(dep_payload)}

## Dependency Risk Notes

- Review networking, auth, and persistence packages first.
- Shared modules shown in `module_dependency_graph.svg` are higher-risk edit points.
- Treat sparse import edges as a signal to verify boundaries manually.
"""

    glossary_text = f"""# Glossary

Generated: {common.now_iso()}

{_glossary_text(stack_payload, dep_payload, modules, docs_payload)}
"""

    if wrote_markdown:
        (overview_dir / "OVERVIEW.md").write_text(overview_text, encoding="utf-8")
        (deep_dir / "ARCHITECTURE_DEEP.md").write_text(architecture_text, encoding="utf-8")
        (deep_dir / "MODULES_DEEP.md").write_text(modules_text, encoding="utf-8")
        (deep_dir / "FLOWS_DEEP.md").write_text(flows_text, encoding="utf-8")
        (deep_dir / "DEPENDENCIES_DEEP.md").write_text(dependencies_text, encoding="utf-8")
        (deep_dir / "GLOSSARY.md").write_text(glossary_text, encoding="utf-8")

    claims = [
        common.collect_claim(
            "claim_primary_language",
            f"Primary language appears to be {stack_payload.get('primary_language', 'Unknown')}.",
            ["meta/stack.json"],
            0.9,
            "Derived from file extension distribution.",
        ),
        common.collect_claim(
            "claim_architecture",
            f"Detected architecture pattern is {architecture_pattern}.",
            ["meta/stack.json"],
            0.76,
            "Heuristic architecture detection plus module structure.",
        ),
        common.collect_claim(
            "claim_top_modules",
            "The explainer names major modules and gives change guidance.",
            ["meta/explanation_plan.json", "overview/OVERVIEW.md", "deep/MODULES_DEEP.md"],
            0.86,
            "Module cards are generated from explicit module evidence.",
        ),
        common.collect_claim(
            "claim_start_here",
            "The explainer provides audience-specific starting points.",
            ["meta/explanation_plan.json", "overview/OVERVIEW.md"],
            0.84,
            "Start-here guidance is generated from detected entrypoints, modules, and audience.",
        ),
        common.collect_claim(
            "claim_diagram_set",
            f"Generated {diagram_manifest.get('count', 0)} diagrams with explicit narrative purpose.",
            ["meta/diagram_manifest.json", "overview/OVERVIEW.md"],
            0.94,
            "Diagram briefs are tied to onboarding questions.",
        ),
    ]

    if llm_payload.get("used", False):
        claims.append(
            common.collect_claim(
                "claim_llm_narrative",
                "The output incorporates an explanation-first narrative layer.",
                ["meta/llm_summary.json", "overview/OVERVIEW.md"],
                0.82,
                "Narrative is generated before doc assembly and reflected in the output.",
            )
        )

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
    parser = argparse.ArgumentParser(description="Generate grounded repository explainers.")
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
    parser.add_argument("--explanation-plan", required=True)
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
        plan_payload=common.read_json(Path(args.explanation_plan), default={}),
        verification_payload=common.read_json(Path(args.verification), default={}),
        enrichment_payload=common.read_json(Path(args.enrichment), default={}),
    )
    print(json.dumps({"overview": payload["overview_file"], "deep_count": len(payload["deep_files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
