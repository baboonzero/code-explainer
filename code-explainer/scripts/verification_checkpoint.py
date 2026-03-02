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


def _find_line_with_pattern(path: Path, pattern: str) -> int:
    text = common.read_text(path)
    if not text:
        return 0
    for idx, line in enumerate(text.splitlines(), start=1):
        if pattern in line:
            return idx
    return 0


def _json_line_for_key(path: Path, key: str) -> int:
    return _find_line_with_pattern(path, f'"{key}"')


def _location(path: Path, root: Path, key: str = "") -> Dict[str, Any]:
    line = _json_line_for_key(path, key) if key else 0
    excerpt = ""
    text = common.read_text(path)
    if text and line > 0:
        lines = text.splitlines()
        if line - 1 < len(lines):
            excerpt = lines[line - 1].strip()
    return {
        "path": common.relative_path(path, root),
        "line": line,
        "excerpt": excerpt[:220],
    }


def _fact(
    claim_id: str,
    claim_text: str,
    expected_text: str,
    must_include_tokens: List[str],
    locations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "expected_text": expected_text,
        "must_include_tokens": must_include_tokens,
        "status": "verified" if locations else "unverified",
        "evidence_locations": locations,
    }


def build_verification_checkpoint(
    output_root: Path,
    source: str,
    analysis_type: str,
    stack_payload: Dict[str, Any],
    index_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
) -> Dict[str, Any]:
    meta_dir = output_root / "meta"
    stack_path = meta_dir / "stack.json"
    index_path = meta_dir / "index.json"
    entry_path = meta_dir / "entrypoints.json"
    dep_path = meta_dir / "dependencies.json"
    flows_path = meta_dir / "flows.json"
    coverage_path = meta_dir / "coverage_report.json"
    context_path = meta_dir / "explainer_context.json"

    primary_language = stack_payload.get("primary_language", "Unknown")
    architecture_pattern = stack_payload.get("architecture_pattern", "Unknown")
    entry_count = int(entry_payload.get("count", len(entry_payload.get("entrypoints", []))))
    module_count = len(index_payload.get("modules", []))
    docs_parsed = int(docs_payload.get("parsed_count", 0))
    docs_discovered = int(docs_payload.get("discovered_count", 0))
    edge_count = int(dep_payload.get("internal_edge_count", 0))
    request_steps = flow_payload.get("request_lifecycle", [])

    facts: List[Dict[str, Any]] = [
        _fact(
            "claim_primary_language",
            f"Primary language appears to be {primary_language}.",
            f"Primary language appears to be {primary_language}.",
            [primary_language.lower()],
            [_location(stack_path, output_root, "primary_language")],
        ),
        _fact(
            "claim_architecture",
            f"Detected architecture pattern is {architecture_pattern}.",
            f"Detected architecture pattern is {architecture_pattern}.",
            [architecture_pattern.lower()],
            [_location(stack_path, output_root, "architecture_pattern")],
        ),
        _fact(
            "claim_entrypoints",
            f"Detected {entry_count} likely entrypoint files.",
            f"Detected {entry_count} likely entrypoint files.",
            [str(entry_count), "entrypoint"],
            [_location(entry_path, output_root, "count")],
        ),
        _fact(
            "claim_doc_coverage",
            f"Parsed {docs_parsed} of {docs_discovered} documentation files.",
            f"Parsed {docs_parsed} of {docs_discovered} documentation files.",
            [str(docs_parsed), str(docs_discovered), "docs"],
            [
                _location(coverage_path, output_root, "parsed_count"),
                _location(coverage_path, output_root, "discovered_count"),
            ],
        ),
        _fact(
            "claim_dependency_edges",
            f"Internal dependency edge count is {edge_count}.",
            f"Internal dependency edge count is {edge_count}.",
            [str(edge_count), "dependency"],
            [_location(dep_path, output_root, "internal_edge_count")],
        ),
        _fact(
            "claim_module_count",
            f"Detected {module_count} top-level modules/groups.",
            f"Detected {module_count} top-level modules/groups.",
            [str(module_count), "module"],
            [_location(index_path, output_root, "modules")],
        ),
        _fact(
            "claim_analysis_type",
            f"Explainer mode is {analysis_type}.",
            f"Explainer mode is {analysis_type}.",
            [analysis_type.lower()],
            [_location(context_path, output_root, "analysis_type")],
        ),
    ]

    if request_steps:
        step = str(request_steps[0]).strip()
        if step:
            facts.append(
                _fact(
                    "claim_request_flow",
                    f"Request lifecycle starts with {step}.",
                    f"Request lifecycle starts with {step}.",
                    [step.lower()],
                    [_location(flows_path, output_root, "request_lifecycle")],
                )
            )

    if analysis_type == "project-recap":
        recap = context_payload.get("project_recap", {})
        if recap.get("available"):
            commit_count = int(recap.get("commit_count", 0))
            facts.append(
                _fact(
                    "claim_recap_commits",
                    f"Project recap window contains {commit_count} commits.",
                    f"Project recap window contains {commit_count} commits.",
                    [str(commit_count), "commit"],
                    [_location(context_path, output_root, "commit_count")],
                )
            )
    elif analysis_type == "plan-review":
        plan = context_payload.get("plan_review", {})
        if plan.get("available"):
            referenced = int(plan.get("referenced_files_count", 0))
            facts.append(
                _fact(
                    "claim_plan_file_refs",
                    f"Plan references {referenced} files.",
                    f"Plan references {referenced} files.",
                    [str(referenced), "plan", "file"],
                    [_location(context_path, output_root, "referenced_files_count")],
                )
            )
    elif analysis_type == "diff-review":
        diff = context_payload.get("diff_review", {})
        if diff.get("available"):
            changed = int(diff.get("changed_file_count", 0))
            facts.append(
                _fact(
                    "claim_diff_changed_files",
                    f"Diff review detected {changed} changed files.",
                    f"Diff review detected {changed} changed files.",
                    [str(changed), "changed", "file"],
                    [_location(context_path, output_root, "changed_file_count")],
                )
            )

    payload = {
        "generated_at": common.now_iso(),
        "source": source,
        "analysis_type": analysis_type,
        "fact_count": len(facts),
        "facts": facts,
    }
    common.write_json(meta_dir / "verification_checkpoint.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verification checkpoint facts before narrative generation.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--explainer-context", required=True)
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    payload = build_verification_checkpoint(
        output_root=output_root,
        source=args.source,
        analysis_type=args.analysis_type,
        stack_payload=common.read_json(Path(args.stack), default={}),
        index_payload=common.read_json(Path(args.index), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        docs_payload=common.read_json(Path(args.coverage), default={}),
        context_payload=common.read_json(Path(args.explainer_context), default={}),
    )
    print(json.dumps({"fact_count": payload.get("fact_count", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
