#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _humanize(text: str) -> str:
    return " ".join(str(text or "").replace("_", " ").replace("-", " ").split()).strip()


def _role_hint(name: str) -> str:
    token = (name or "").lower()
    if token in {"scripts", "tools"}:
        return "the scripts that run the analysis and create the final explainer files"
    if token in {"docs", "references"}:
        return "written documentation, guides, and reference notes"
    if any(x in token for x in ["api", "route", "handler", "controller"]):
        return "the part that receives requests or inputs"
    if any(x in token for x in ["service", "core", "domain", "logic"]):
        return "the main project behavior and decision logic"
    if any(x in token for x in ["data", "db", "repo", "model", "store"]):
        return "how data is saved, loaded, and transformed"
    if any(x in token for x in ["ui", "page", "component", "frontend"]):
        return "what users see and interact with"
    return "an important part of the project"


def _sample_files_for_module(module_name: str, files: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    out: List[str] = []
    for item in files:
        rel = item.get("path", "")
        if module_name == "(root-files)":
            if "/" in rel:
                continue
        else:
            norm = rel.replace("\\", "/")
            if not (
                norm.startswith(f"{module_name}/")
                or f"/{module_name}/" in norm
            ):
                continue
        out.append(rel)
        if len(out) >= limit:
            break
    return out


def _entrypoints_table(entrypoints: List[Dict[str, Any]]) -> str:
    if not entrypoints:
        return "_I could not find a clear starting file in this run._"
    lines = ["| Start here | Why this file matters |", "|---|---|"]
    for ep in entrypoints[:10]:
        kind = str(ep.get("kind", "entrypoint")).strip()
        score = ep.get("score", "")
        confidence = ""
        if str(score) != "":
            try:
                s = int(score)
                if s >= 100:
                    confidence = " (high confidence)"
                elif s >= 60:
                    confidence = " (medium confidence)"
                else:
                    confidence = " (low confidence)"
            except Exception:
                confidence = ""
        lines.append(f"| `{ep.get('path', '')}` | {kind}{confidence} |")
    return "\n".join(lines)


def _critical_path_text(flow_payload: Dict[str, Any], limit: int = 4) -> str:
    rows = []
    for path in flow_payload.get("critical_paths", [])[:limit]:
        steps = [str(s) for s in path.get("plain_steps", path.get("steps", [])) if str(s).strip()]
        if not steps:
            continue
        cleaned = []
        for step in steps:
            if step.startswith("Read "):
                cleaned.append(step)
            elif "/" in step:
                p = Path(step)
                cleaned.append(f"{p.parent.name}/{p.stem}" if p.parent.name else p.stem)
            elif "." in step:
                module_name, fn_name = step.rsplit(".", 1)
                cleaned.append(f"{module_name}.{fn_name.replace('_', ' ').strip()}")
            else:
                cleaned.append(_humanize(step))
        rows.append(f"- **{path.get('name', 'Main path')}**: {' -> '.join(cleaned)}")
    return "\n".join(rows) if rows else "- No detailed critical path extracted."


def _plain_summary(
    repo_name: str,
    audience: str,
    stack_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    index_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
) -> str:
    llm_summary = str(llm_payload.get("repo_summary_paragraph", "")).strip()
    if llm_summary:
        return llm_summary

    parsed_docs = docs_payload.get("parsed_docs", [])
    readme = None
    for doc in parsed_docs:
        if "readme" in str(doc.get("path", "")).lower():
            readme = doc
            break
    if readme and readme.get("summary"):
        seed = str(readme.get("summary", "")).strip()
    else:
        seed = ""

    module_count = len(index_payload.get("modules", []))
    language = stack_payload.get("primary_language", "Unknown")
    architecture = stack_payload.get("architecture_pattern", "general")
    lifecycle = " -> ".join([str(s) for s in flow_payload.get("request_lifecycle", [])[:4]])
    entry_count = int(index_payload.get("file_count", 0))

    if not seed:
        if audience == "nontech":
            return (
                f"This repository contains the code and documentation for {repo_name}. "
                f"Most of the code is written in {language}. "
                f"The project is organized into {module_count} main areas, and the overall flow is: "
                f"{lifecycle or 'input -> processing -> output'}."
            )
        return (
            f"{repo_name} is mostly a {language} project. "
            f"It is organized into {module_count} main folders and files with a clear step-by-step processing flow."
        )
    return (
        f"{seed}\n\n"
        f"In plain terms: this is mainly a {language} project with about {module_count} major code areas "
        f"and around {entry_count} tracked files. "
        f"A representative end-to-end flow is: {lifecycle or 'input -> processing -> output'}."
    )


def _directory_map(index_payload: Dict[str, Any], max_items: int = 7) -> str:
    modules = index_payload.get("modules", [])[:max_items]
    files = index_payload.get("files", [])
    if not modules:
        return "- No module groups detected."
    lines = []
    for module in modules:
        name = module.get("name", "")
        if not name:
            continue
        count = int(module.get("file_count", 0))
        role = _role_hint(name)
        samples = _sample_files_for_module(name, files, limit=3)
        sample_text = ", ".join([f"`{s}`" for s in samples]) if samples else "no sample files collected"
        lines.append(
            f"- **{name}** ({count} files): {role}. Examples: {sample_text}."
        )
    return "\n".join(lines)


def _diagram_links(diagram_manifest: Dict[str, Any]) -> str:
    out = []
    for name in diagram_manifest.get("diagram_files", []):
        stem = Path(name).stem
        out.append(f"- `{name}` -> [SVG](../diagrams/svg/{stem}.svg) | [PNG](../diagrams/png/{stem}.png)")
    return "\n".join(out) if out else "- No diagrams generated."


def _llm_notes(llm_payload: Dict[str, Any]) -> str:
    if llm_payload.get("used", False):
        notes = llm_payload.get("confidence_notes", [])
        if isinstance(notes, list) and notes:
            return "\n".join([f"- {str(note)}" for note in notes[:5]])
        return "- LLM narratives were used for summary framing."
    if llm_payload.get("enabled", False):
        return f"- AI summary was enabled but not used: {llm_payload.get('error', 'no model response')}"
    return "- AI narrative generation is turned off for this run."


def _apply_verification_evidence(claims: List[Dict[str, Any]], verification_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    fact_map = {fact.get("claim_id", ""): fact for fact in verification_payload.get("facts", [])}
    for claim in claims:
        fact = fact_map.get(claim.get("claim_id", ""))
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
    del templates_root
    del context_payload
    del enrichment_payload

    overview_dir = common.ensure_dir(output_root / "overview")
    deep_dir = common.ensure_dir(output_root / "deep")

    repo_name = stack_payload.get("repo_name", common.detect_repo_name(source, output_root))
    architecture_raw = stack_payload.get("architecture_pattern", "Unknown")
    architecture_human = (
        f"Custom project layout (detector label: {architecture_raw})"
        if architecture_raw == "Custom/Undetected"
        else architecture_raw
    )
    languages = stack_payload.get("languages", {})
    lang_line = ", ".join([f"{k} ({v})" for k, v in list(languages.items())[:6]]) or "Unknown"
    framework_line = ", ".join(stack_payload.get("frameworks", [])[:8]) or "None detected"
    summary = _plain_summary(
        repo_name, audience, stack_payload, docs_payload, llm_payload, index_payload, flow_payload
    )
    directory_map = _directory_map(index_payload, max_items=8 if overview_length == "long" else 6)
    lifecycle = flow_payload.get("request_lifecycle", [])
    lifecycle_line = " -> ".join([str(s) for s in lifecycle]) if lifecycle else "No clear flow was extracted in this run"
    critical_paths = _critical_path_text(flow_payload, limit=6 if mode == "deep" else 4)
    entrypoints_table = _entrypoints_table(entry_payload.get("entrypoints", []))
    diagram_links = _diagram_links(diagram_manifest)
    llm_notes = _llm_notes(llm_payload)

    overview_text = f"""# {repo_name}: Start Here

Generated: {common.now_iso()}  
Source: `{source}`  
Mode: `{mode}`  
Audience: `{audience}`  
Explainer type: `{analysis_type}`

## What This Repository Does

{summary}

## Quick Facts

- Overall project shape: **{architecture_human}**
- Main coding language(s): **{lang_line}**
- Key framework(s): **{framework_line}**
- Starting file(s) found: **{entry_payload.get("count", len(entry_payload.get("entrypoints", [])))}**
- File links mapped: **{dep_payload.get("internal_edge_count", 0)}**

## Directory Map (Plain Language)

{directory_map}

## How Information Flows

`{lifecycle_line}`

## If You Are New, Start Here

1. Open `../diagrams/svg/primary_user_flow.svg`.
2. Read `../deep/SYSTEM_DEEP_DIVE.md`.
3. Use `../meta/verification_checkpoint.json` when you need evidence for specific claims.
"""

    deep_text = f"""# {repo_name}: System Deep Dive

Generated: {common.now_iso()}

## 1) What Happens From Start To Finish

`{lifecycle_line}`

## 2) Important Journeys Through The Code

{critical_paths}

## 3) Best Files To Open First

{entrypoints_table}

## 4) What Each Main Folder Is Responsible For

{directory_map}

## 5) Visual Maps

{diagram_links}

## 6) How Reliable This Explanation Is

- Docs parsed: **{docs_payload.get("parsed_count", 0)}/{docs_payload.get("discovered_count", 0)}**
- Diagram count: **{diagram_manifest.get("count", 0)}**
- Quality checks: `../meta/quality_report.json`
- Fact checks: `../meta/fact_check_report.json`
- AI notes:
{llm_notes}
"""

    wrote_markdown = output_format in {"markdown", "both"}
    if wrote_markdown:
        (overview_dir / "OVERVIEW.md").write_text(overview_text.strip() + "\n", encoding="utf-8")
        (deep_dir / "SYSTEM_DEEP_DIVE.md").write_text(deep_text.strip() + "\n", encoding="utf-8")

    claims = [
        common.collect_claim(
            "claim_primary_language",
            f"Primary language appears to be {stack_payload.get('primary_language', 'Unknown')}.",
            ["meta/index.json", "meta/stack.json"],
            0.88,
            "Derived from extension distribution.",
        ),
        common.collect_claim(
            "claim_entrypoints",
            f"Detected {entry_payload.get('count', 0)} likely entrypoints.",
            ["meta/entrypoints.json"],
            0.82,
            "Entrypoint scoring based on bootstrap and filename signals.",
        ),
        common.collect_claim(
            "claim_flow",
            "Primary lifecycle and critical paths were extracted from orchestration and dependency signals.",
            ["meta/flows.json", "meta/dependencies.json"],
            0.8,
            "Combines AST call extraction with dependency path tracing.",
        ),
        common.collect_claim(
            "claim_docs_coverage",
            f"Parsed {docs_payload.get('parsed_count', 0)} of {docs_payload.get('discovered_count', 0)} docs.",
            ["meta/coverage_report.json"],
            0.9,
            "Deterministic documentation ingestion.",
        ),
        common.collect_claim(
            "claim_diagrams",
            f"Generated {diagram_manifest.get('count', 0)} diagrams.",
            ["meta/diagram_manifest.json", "meta/render_report.json"],
            0.95,
            "Deterministic diagram build and render artifacts.",
        ),
    ]

    if llm_payload.get("used", False):
        claims.append(
            common.collect_claim(
                "claim_llm_narrative",
                "LLM-assisted narrative summary was included.",
                ["meta/llm_summary.json"],
                0.72,
                "LLM generation built from bounded repository context.",
            )
        )

    claims = _apply_verification_evidence(claims, verification_payload)

    payload = {
        "generated_at": common.now_iso(),
        "overview_file": "overview/OVERVIEW.md" if wrote_markdown else "",
        "deep_files": ["deep/SYSTEM_DEEP_DIVE.md"] if wrote_markdown else [],
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
    parser = argparse.ArgumentParser(description="Generate markdown explainers.")
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
