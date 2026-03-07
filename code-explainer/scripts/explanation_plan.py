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


def _pick_summary_doc(parsed_docs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    scored: List[tuple[int, Dict[str, Any]]] = []
    for doc in parsed_docs:
        path = str(doc.get("path", "")).lower()
        score = 0
        if "readme" in path:
            score += 100
        if "architecture" in path:
            score += 50
        if "overview" in path or "getting-started" in path:
            score += 40
        if path.startswith("docs/"):
            score += 20
        if path.startswith("references/"):
            score -= 10
        scored.append((score, doc))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_doc = scored[0]
    return top_doc if top_score >= 20 else None


def _module_examples(files: List[Dict[str, Any]], module_name: str, limit: int = 3) -> List[str]:
    examples: List[str] = []
    prefix = "" if module_name == "(root-files)" else f"{module_name}/"
    for item in files:
        path = item.get("path", "")
        if module_name == "(root-files)":
            if "/" in path:
                continue
        elif not path.startswith(prefix):
            continue
        examples.append(path)
        if len(examples) >= limit:
            break
    return examples


def _module_responsibility(name: str, sample_paths: List[str]) -> str:
    lowered = name.lower()
    if lowered in {"app", "src"}:
        return "Holds the main product code and entry surfaces."
    hints = {
        "api": "Exposes API handlers and request-facing orchestration.",
        "service": "Contains business logic and cross-module workflows.",
        "services": "Contains business logic and cross-module workflows.",
        "repo": "Manages storage or persistence concerns.",
        "repositories": "Manages storage or persistence concerns.",
        "data": "Owns storage, schemas, or state transitions.",
        "model": "Defines core data structures or domain models.",
        "models": "Defines core data structures or domain models.",
        "ui": "Contains user-facing interface code.",
        "components": "Contains reusable user-interface building blocks.",
        "pages": "Maps product screens or route-level views.",
        "hooks": "Encapsulates reusable stateful client logic.",
        "tests": "Provides behavior checks and safe-change coverage.",
        "docs": "Documents product intent and engineering workflows.",
        "scripts": "Automates project tasks and developer workflows.",
    }
    for token, summary in hints.items():
        if token in lowered:
            return summary
    if sample_paths:
        first = Path(sample_paths[0]).name
        return f"Groups related implementation files such as `{first}`."
    return "Groups related implementation files."


def _module_change_hint(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ["api", "pages", "ui", "components"]):
        return "Start here when you are changing user-facing behavior."
    if any(token in lowered for token in ["service", "domain", "core", "logic"]):
        return "Start here when you are changing business rules."
    if any(token in lowered for token in ["repo", "data", "model", "db", "store"]):
        return "Start here when you are changing persistence or data contracts."
    if "test" in lowered:
        return "Use this area to validate and lock in behavior changes."
    return "Inspect this area after tracing the entrypoint and primary flow."


def _audience_start_here(audience: str, entrypoints: List[Dict[str, Any]], modules: List[Dict[str, Any]]) -> List[str]:
    top_module = next((m.get("name", "") for m in modules if m.get("name") and m.get("name") != "(root-files)"), "")
    first_entry = entrypoints[0]["path"] if entrypoints else ""
    if audience == "engineering":
        return [
            f"Open `{first_entry}` first to anchor execution, if an entrypoint was detected." if first_entry else "Start with the detected entrypoints list.",
            f"Then inspect `{top_module}/` to understand the dominant code surface." if top_module else "Then inspect the largest top-level module.",
            "Use the dependency and flow views before editing shared modules.",
        ]
    if audience == "mixed":
        return [
            "Read the overview first, then trace one real request path.",
            f"Open `{top_module}/` to connect product concepts to code." if top_module else "Open the largest top-level module to connect product concepts to code.",
            "Use the change guidance section before planning work.",
        ]
    return [
        "Read the overview and request flow before looking at code details.",
        f"Use `{top_module}/` as the first folder to inspect." if top_module else "Use the largest top-level folder as the first place to inspect.",
        "Treat caveats and confidence notes as boundaries on what the explainer knows.",
    ]


def _diagram_briefs(entrypoints: List[Dict[str, Any]], modules: List[Dict[str, Any]], flows: Dict[str, Any], mode: str) -> List[Dict[str, str]]:
    first_entry = entrypoints[0]["path"] if entrypoints else "entrypoint"
    top_modules = [m.get("name", "") for m in modules if m.get("name") and m.get("name") != "(root-files)"][:4]
    briefs = [
        {
            "id": "c4_context",
            "title": "System context",
            "purpose": "Show the product boundary, primary actor, and major external touchpoints.",
            "reader_question": "What kind of system is this, and what surrounds it?",
        },
        {
            "id": "c4_container",
            "title": "Codebase shape",
            "purpose": f"Show the main execution surfaces starting from `{first_entry}` and the top modules {', '.join(top_modules) or 'under analysis'}.",
            "reader_question": "How is the repository organized at a high level?",
        },
        {
            "id": "primary_user_flow",
            "title": "Primary user flow",
            "purpose": "Show the main request or interaction path through the codebase.",
            "reader_question": "What happens first, next, and last in the main flow?",
        },
        {
            "id": "module_dependency_graph",
            "title": "Module relationships",
            "purpose": "Show which top-level areas depend on one another, so change impact is visible.",
            "reader_question": "Which modules are central, shared, or risky to edit?",
        },
    ]
    if mode == "deep":
        briefs.extend(
            [
                {
                    "id": "request_lifecycle_sequence",
                    "title": "Request lifecycle",
                    "purpose": "Show the execution handoff between the main stages of a request.",
                    "reader_question": "How does work move through the system?",
                },
                {
                    "id": "where_to_change_map",
                    "title": "Where to change",
                    "purpose": "Show the likely first files or modules to inspect when making a feature change.",
                    "reader_question": "Where should I start changing code safely?",
                },
            ]
        )
    return briefs


def _collect_caveats(
    stack_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
) -> List[str]:
    caveats: List[str] = []
    discovered = int(docs_payload.get("discovered_count", 0))
    parsed = int(docs_payload.get("parsed_count", 0))
    if discovered > 0 and parsed == 0:
        caveats.append("Documentation exists but could not be parsed, so product intent is inferred mostly from code structure.")
    elif discovered >= 4 and parsed / max(discovered, 1) < 0.5:
        caveats.append("Documentation coverage is partial, so some higher-level intent may be missing.")
    if int(entry_payload.get("count", 0)) == 0:
        caveats.append("No clear entrypoint was detected, so startup guidance is weaker than normal.")
    if stack_payload.get("architecture_pattern") == "Custom/Undetected":
        caveats.append("The repository does not match a strong built-in architecture heuristic, so module boundaries are partly inferred.")
    if int(dep_payload.get("internal_edge_count", 0)) == 0:
        caveats.append("Internal dependency edges were sparse, so relationship diagrams are based more on structure than on traced imports.")
    return caveats[:6]


def build_explanation_plan(
    repo_root: Path,
    source: str,
    audience: str,
    mode: str,
    analysis_type: str,
    index_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
    out_dir: Path,
) -> Dict[str, Any]:
    files = index_payload.get("files", [])
    parsed_docs = docs_payload.get("parsed_docs", [])
    summary_doc = _pick_summary_doc(parsed_docs)
    summary_seed = ""
    if summary_doc:
        summary_seed = str(summary_doc.get("summary", "")).strip()

    modules_payload = []
    for module in index_payload.get("modules", []):
        name = module.get("name", "")
        if not name:
            continue
        examples = _module_examples(files, name)
        modules_payload.append(
            {
                "name": name,
                "file_count": int(module.get("file_count", 0)),
                "responsibility_hint": _module_responsibility(name, examples),
                "change_hint": _module_change_hint(name),
                "sample_paths": examples,
            }
        )

    top_modules = [m for m in modules_payload if m["name"] != "(root-files)"][:8]
    entrypoints = entry_payload.get("entrypoints", [])
    primary_flow = flow_payload.get("primary_user_flow", {}).get("steps", [])

    payload = {
        "generated_at": common.now_iso(),
        "repo_name": stack_payload.get("repo_name", common.detect_repo_name(source, repo_root)),
        "source": source,
        "audience": audience,
        "mode": mode,
        "analysis_type": analysis_type,
        "summary_seed": summary_seed,
        "summary_seed_doc": summary_doc.get("path", "") if summary_doc else "",
        "primary_question_set": [
            "What does this system do?",
            "How is the codebase organized?",
            "What path does a core request take?",
            "Where should a new person start?",
        ],
        "start_here": _audience_start_here(audience, entrypoints, top_modules),
        "top_modules": top_modules,
        "entrypoints": entrypoints[:10],
        "primary_flow_steps": primary_flow[:8],
        "diagram_briefs": _diagram_briefs(entrypoints, top_modules, flow_payload, mode),
        "caveats": _collect_caveats(stack_payload, docs_payload, entry_payload, dep_payload),
        "docs_used": [
            {
                "path": doc.get("path", ""),
                "title": doc.get("title", ""),
                "summary": doc.get("summary", ""),
            }
            for doc in parsed_docs[:8]
        ],
        "mode_context": context_payload,
    }
    common.write_json(out_dir / "explanation_plan.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a grounded explanation plan for repository explainers.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--index", required=True)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--explainer-context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_explanation_plan(
        repo_root=Path(args.repo).resolve(),
        source=args.source,
        audience=args.audience,
        mode=common.normalize_mode(args.mode),
        analysis_type=args.analysis_type,
        index_payload=common.read_json(Path(args.index), default={}),
        stack_payload=common.read_json(Path(args.stack), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        docs_payload=common.read_json(Path(args.coverage), default={}),
        context_payload=common.read_json(Path(args.explainer_context), default={}),
        out_dir=Path(args.output).resolve(),
    )
    print(json.dumps({"top_modules": len(payload.get("top_modules", [])), "caveats": len(payload.get("caveats", []))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
