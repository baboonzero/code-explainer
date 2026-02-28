#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _module_from_path(path: str) -> str:
    if not path:
        return "unknown"
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return "(root-files)"
    return normalized.split("/", 1)[0]


def _step_label(step: str) -> str:
    if not step:
        return "unknown"
    normalized = step.replace("\\", "/")
    if "/" in normalized:
        leaf = normalized.rsplit("/", 1)[-1]
        if "." in leaf:
            return leaf.rsplit(".", 1)[0]
        return _module_from_path(normalized)
    return normalized


def _request_flow(frameworks: List[str], primary_critical_path: List[str], entrypoints: List[Dict[str, str]]) -> List[str]:
    if primary_critical_path:
        dedup = []
        seen = set()
        for step in primary_critical_path[:7]:
            label = _step_label(step)
            if label in seen:
                continue
            seen.add(label)
            dedup.append(label)
        if len(dedup) >= 4:
            return dedup
        if len(dedup) >= 2:
            return [dedup[0], dedup[1], "persistence", "outcome"]

    framework_set = set(frameworks)
    if framework_set & {"Express", "FastAPI", "Django", "Flask", "NestJS", "Gin"}:
        first = _module_from_path(entrypoints[0]["path"]) if entrypoints else "entrypoint"
        return ["Client request", first, "Service layer", "Data layer", "Response"]
    return ["User action", "Entry module", "Core module", "Persistence/state", "Outcome"]


def _edge_adjacency(edges: List[Dict[str, str]]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        src = edge.get("from", "")
        dst = edge.get("to_resolved", "") or edge.get("to", "")
        if not src or not dst:
            continue
        graph[src].append(dst)
    return graph


def _trace_critical_path(entry: str, graph: Dict[str, List[str]], max_steps: int = 8) -> List[str]:
    path = [entry]
    current = entry
    seen = {entry}
    for _ in range(max_steps - 1):
        candidates = [c for c in graph.get(current, []) if c not in seen]
        if not candidates:
            break
        next_node = candidates[0]
        path.append(next_node)
        seen.add(next_node)
        current = next_node
    return path


def _top_module_chain(edges: List[Dict[str, str]], max_steps: int = 6) -> List[str]:
    outbound: Dict[str, int] = defaultdict(int)
    for edge in edges:
        src_mod = _module_from_path(edge.get("from", ""))
        outbound[src_mod] += 1
    ranked = sorted(outbound.items(), key=lambda kv: kv[1], reverse=True)
    return [item[0] for item in ranked[:max_steps]]


def _derive_data_lineage(entrypoints: List[Dict[str, str]], edges: List[Dict[str, str]]) -> List[str]:
    layered = []
    first_entry = entrypoints[0]["path"] if entrypoints else "entrypoint"
    layered.append(f"Ingress ({_module_from_path(first_entry)})")
    module_chain = _top_module_chain(edges, max_steps=6)

    keywords = [
        ("validation", re.compile(r"valid|schema", flags=re.IGNORECASE)),
        ("service", re.compile(r"service|handler|controller", flags=re.IGNORECASE)),
        ("domain", re.compile(r"domain|logic|usecase", flags=re.IGNORECASE)),
        ("storage", re.compile(r"repo|store|db|model|migration", flags=re.IGNORECASE)),
        ("presentation", re.compile(r"view|api|response|ui", flags=re.IGNORECASE)),
    ]
    chosen = []
    for module in module_chain:
        for label, pattern in keywords:
            if pattern.search(module) and label not in chosen:
                chosen.append(label)
                break

    if not chosen:
        chosen = ["validation", "service", "storage", "presentation"]
    layered.extend(chosen[:5])
    return layered


def _derive_trust_boundaries(
    entrypoints: List[Dict[str, str]],
    external_deps: Dict[str, List[str]],
) -> List[Dict[str, str]]:
    boundaries: List[Dict[str, str]] = []
    if entrypoints:
        boundaries.append(
            {
                "name": f"External actor -> {_module_from_path(entrypoints[0]['path'])}",
                "type": "network ingress",
            }
        )
    has_remote = False
    for deps in external_deps.values():
        for dep in deps:
            dep_lower = dep.lower()
            if any(token in dep_lower for token in ["http", "grpc", "aws", "azure", "gcp", "supabase", "firebase"]):
                has_remote = True
                break
        if has_remote:
            break
    if has_remote:
        boundaries.append({"name": "Application -> third-party services", "type": "external API"})
    boundaries.append({"name": "Application -> data storage", "type": "data access"})
    return boundaries


def map_flows(
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    out_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    frameworks = stack_payload.get("frameworks", [])
    entrypoints = entry_payload.get("entrypoints", [])
    internal_edges = dep_payload.get("internal_edges", [])
    adjacency = _edge_adjacency(internal_edges)

    depth_by_mode = {"quick": 4, "standard": 6, "deep": 9}
    path_limit_by_mode = {"quick": 2, "standard": 5, "deep": 10}

    critical_paths = []
    if entrypoints:
        for entry in entrypoints[: path_limit_by_mode.get(mode, 5)]:
            traced = _trace_critical_path(entry["path"], adjacency, max_steps=depth_by_mode.get(mode, 6))
            critical_paths.append(
                {
                    "name": f"Path from {entry['path']}",
                    "steps": traced,
                    "step_count": len(traced),
                }
            )

    fallback_chain = _top_module_chain(internal_edges, max_steps=6)
    primary_steps = critical_paths[0]["steps"] if critical_paths else fallback_chain
    if len(primary_steps) < 2:
        entry_module = _module_from_path(entrypoints[0]["path"]) if entrypoints else "entry"
        augmented = [entry_module]
        for mod in fallback_chain[:4]:
            if mod not in augmented:
                augmented.append(mod)
        if len(augmented) < 2:
            augmented.append("response")
        primary_steps = augmented
    request_flow = _request_flow(frameworks, primary_steps, entrypoints)
    primary_user_flow = {
        "name": critical_paths[0]["name"] if critical_paths else "Primary repository flow",
        "steps": [_step_label(step) for step in (primary_steps[:7] if primary_steps else ["User intent", "Entry module", "Outcome"])],
    }
    trust_boundaries = _derive_trust_boundaries(entrypoints, dep_payload.get("external_dependencies", {}))
    data_lineage = _derive_data_lineage(entrypoints, internal_edges)

    payload = {
        "mapped_at": common.now_iso(),
        "mode": mode,
        "request_lifecycle": request_flow,
        "primary_user_flow": primary_user_flow,
        "critical_paths": critical_paths,
        "trust_boundaries": trust_boundaries if mode == "deep" else trust_boundaries[:2],
        "data_lineage": data_lineage if mode == "deep" else data_lineage[:4],
        "dependency_edge_count": dep_payload.get("internal_edge_count", 0),
        "entrypoint_count": len(entrypoints),
    }
    common.write_json(out_dir / "flows.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Map codebase request and data flows.")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()
    payload = map_flows(
        common.read_json(Path(args.stack), default={}),
        common.read_json(Path(args.entrypoints), default={}),
        common.read_json(Path(args.dependencies), default={}),
        Path(args.output).resolve(),
        common.normalize_mode(args.mode),
    )
    print(f"Mapped flow artifacts for mode={payload['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
