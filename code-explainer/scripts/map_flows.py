#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


UTILITY_MODULE_TOKENS = {"common", "utils", "helpers", "types", "constants"}


def _module_from_path(path: str) -> str:
    if not path:
        return "unknown"
    norm = path.replace("\\", "/").strip("/")
    parts = [p for p in norm.split("/") if p]
    if not parts:
        return "unknown"
    if len(parts) >= 3 and parts[1] in {"scripts", "src", "app", "lib"}:
        return parts[1]
    if len(parts) >= 2 and parts[0] in {"code-explainer", "packages", "apps"}:
        return parts[1]
    return parts[0]


def _humanize_token(token: str) -> str:
    text = (token or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return "unknown"
    return " ".join([part.capitalize() for part in text.split()])


def _humanize_call(call_name: str) -> str:
    value = (call_name or "").strip()
    if not value:
        return "unknown"
    if "." in value:
        left, right = value.rsplit(".", 1)
        semantic = {
            "run_pipeline": "Run full analysis pipeline",
            "_resolve_source": "Find the source code folder",
            "ensure_dir": "Prepare output folders",
            "_clear_generated_paths": "Clean old generated files",
            "_repo_relative_if_nested": "Ignore generated folders during scan",
            "build_index": "Index repository files",
            "analyze_stack": "Detect languages and frameworks",
            "map_entrypoints": "Find likely starting files",
            "map_dependencies": "Map how files depend on each other",
            "map_flows": "Trace key code journeys",
            "ingest_docs": "Read existing documentation",
            "generate_llm_descriptions": "Generate plain-language summaries",
            "build_diagrams": "Create Mermaid diagrams",
            "validate_mermaid": "Validate diagrams",
            "render_diagrams": "Render SVG and PNG",
            "generate_docs": "Generate markdown explainers",
            "generate_html": "Generate HTML onboarding page",
            "run_quality_gate": "Run output quality checks",
        }
        if right in semantic:
            return semantic[right]
        return f"{_humanize_token(left)}: {_humanize_token(right)}"
    return _humanize_token(value)


def _path_label(path: str) -> str:
    p = Path(path)
    parent = p.parent.name
    stem = p.stem
    if parent and parent not in {"", "."}:
        return f"{parent}/{stem}"
    return stem


def _plain_step(step: str) -> str:
    value = str(step or "").strip()
    if not value:
        return "unknown step"
    if value.endswith(".py") or "/" in value:
        return f"Read {_path_label(value)}"
    return _humanize_call(value) if "." in value else _humanize_token(value)


def _build_adjacency(edges: List[Dict[str, str]]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        src = edge.get("from", "")
        dst = edge.get("to_resolved", "") or edge.get("to", "")
        if not src or not dst:
            continue
        graph[src].append(dst)
    return graph


def _choose_next(
    current: str,
    graph: Dict[str, List[str]],
    outdegree: Dict[str, int],
    seen: set[str],
) -> str:
    candidates = [c for c in graph.get(current, []) if c not in seen]
    if not candidates:
        return ""

    def score(path: str) -> Tuple[int, int]:
        stem = Path(path).stem.lower()
        utility_penalty = -6 if stem in UTILITY_MODULE_TOKENS else 0
        return (outdegree.get(path, 0) + utility_penalty, -len(path))

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[0]


def _trace_path(entry: str, graph: Dict[str, List[str]], max_steps: int) -> List[str]:
    outdegree = {node: len(targets) for node, targets in graph.items()}
    path = [entry]
    current = entry
    seen = {entry}
    for _ in range(max_steps - 1):
        nxt = _choose_next(current, graph, outdegree, seen)
        if not nxt:
            break
        path.append(nxt)
        seen.add(nxt)
        current = nxt
    return path


def _ordered_calls(func_node: ast.FunctionDef) -> List[ast.Call]:
    calls: List[ast.Call] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            calls.append(node)
    calls.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
    return calls


def _extract_python_orchestration(
    repo_root: Path,
    rel_path: str,
    allowed_modules: set[str],
    max_steps: int,
) -> List[str]:
    if not rel_path.endswith(".py"):
        return []
    source = common.read_text(repo_root / rel_path)
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    import_aliases: Dict[str, str] = {}
    function_defs: Dict[str, ast.FunctionDef] = {}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_aliases[alias.asname or alias.name] = alias.name.split(".")[-1]
        elif isinstance(node, ast.ImportFrom):
            module_name = (node.module or "").split(".")[-1]
            for alias in node.names:
                alias_name = alias.asname or alias.name
                import_aliases[alias_name] = module_name or alias.name
        elif isinstance(node, ast.FunctionDef):
            function_defs[node.name] = node

    ordered_targets = [name for name in ["run_pipeline", "analyze", "execute", "main"] if name in function_defs]
    if not ordered_targets:
        ordered_targets = list(function_defs.keys())[:2]

    ignored_plain_calls = {"print", "len", "str", "int", "float", "dict", "list", "set", "sorted"}
    steps: List[str] = []
    file_stem = Path(rel_path).stem

    for target in ordered_targets:
        steps.append(f"{file_stem}.{target}")
        for call in _ordered_calls(function_defs[target]):
            func = call.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                alias = func.value.id
                module = import_aliases.get(alias, alias)
                if module in allowed_modules:
                    steps.append(f"{module}.{func.attr}")
            elif isinstance(func, ast.Name):
                call_name = func.id
                if call_name in ignored_plain_calls:
                    continue
                if call_name in function_defs:
                    steps.append(f"{file_stem}.{call_name}")

    deduped: List[str] = []
    seen = set()
    for step in steps:
        if step in seen:
            continue
        seen.add(step)
        deduped.append(step)
        if len(deduped) >= max_steps:
            break
    return deduped


def _module_interactions(edges: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for edge in edges:
        src = edge.get("from", "")
        dst = edge.get("to_resolved", "") or edge.get("to", "")
        if not src or not dst:
            continue
        src_mod = _module_from_path(src)
        dst_mod = _module_from_path(dst)
        if src_mod == dst_mod:
            src_mod = Path(src).stem
            dst_mod = Path(dst).stem
            if src_mod == dst_mod:
                continue
        counts[(src_mod, dst_mod)] += 1
    rows = [
        {"from_module": src, "to_module": dst, "count": count}
        for (src, dst), count in counts.items()
    ]
    rows.sort(key=lambda x: (x["count"], x["from_module"], x["to_module"]), reverse=True)
    return rows[:40]


def _derive_trust_boundaries(
    entrypoints: List[Dict[str, str]],
    external_dependencies: Dict[str, List[str]],
) -> List[Dict[str, str]]:
    boundaries: List[Dict[str, str]] = []
    if entrypoints:
        boundaries.append(
            {
                "name": f"Users and tools -> {_path_label(entrypoints[0]['path'])}",
                "type": "entrypoint boundary",
            }
        )
    external_tokens = " ".join([" ".join(v).lower() for v in external_dependencies.values()])
    if any(token in external_tokens for token in ["http", "grpc", "aws", "azure", "firebase", "supabase"]):
        boundaries.append({"name": "Repository -> external services", "type": "network/API boundary"})
    boundaries.append({"name": "Repository -> local files and artifacts", "type": "data/storage boundary"})
    return boundaries


def _derive_data_lineage(primary_steps: List[str]) -> List[str]:
    if not primary_steps:
        return ["User intent", "Entry handling", "Core processing", "Output artifacts"]
    mapped = ["User intent"]
    for step in primary_steps[:6]:
        lowered = step.lower()
        if any(token in lowered for token in ["index", "scan", "detect", "ingest"]):
            mapped.append("Discovery and indexing")
        elif any(token in lowered for token in ["map", "flow", "dependency"]):
            mapped.append("Structure and flow mapping")
        elif any(token in lowered for token in ["diagram", "render", "html"]):
            mapped.append("Visualization and presentation")
        elif any(token in lowered for token in ["quality", "verify", "check", "fact"]):
            mapped.append("Validation and confidence checks")
        else:
            mapped.append(_humanize_token(step))
    mapped.append("Onboarding outputs")

    out: List[str] = []
    for item in mapped:
        if not out or out[-1] != item:
            out.append(item)
    return out[:8]


def map_flows(
    repo_root: Path,
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    out_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    del stack_payload  # reserved for future stack-specific flow branching

    entrypoints = entry_payload.get("entrypoints", [])
    internal_edges = dep_payload.get("internal_edges", [])
    graph = _build_adjacency(internal_edges)
    mode_depth = {"quick": 5, "standard": 8, "deep": 12}.get(mode, 8)
    path_limit = {"quick": 2, "standard": 4, "deep": 7}.get(mode, 4)

    local_modules = {
        str(edge.get("to", "")).split(".", 1)[0].strip()
        for edge in internal_edges
        if edge.get("to_resolved", "")
    }
    local_modules = {m for m in local_modules if m}

    orchestration_paths: List[Dict[str, Any]] = []
    for entry in entrypoints[:path_limit]:
        entry_path = entry.get("path", "")
        calls = _extract_python_orchestration(repo_root, entry_path, local_modules, max_steps=mode_depth)
        if len(calls) < 3:
            continue
        orchestration_paths.append(
            {
                "name": f"Main journey from {_path_label(entry_path)}",
                "entrypoint": entry_path,
                "steps": calls,
                "plain_steps": [_plain_step(step) for step in calls],
                "step_count": len(calls),
                "evidence_paths": [entry_path],
            }
        )

    traced_paths: List[Dict[str, Any]] = []
    for entry in entrypoints[:path_limit]:
        entry_path = entry.get("path", "")
        if not entry_path:
            continue
        traced = _trace_path(entry_path, graph, max_steps=mode_depth)
        if len(traced) < 3:
            continue
        traced_paths.append(
            {
                "name": f"Linked-file journey from {_path_label(entry_path)}",
                "entrypoint": entry_path,
                "steps": traced,
                "plain_steps": [_plain_step(step) for step in traced],
                "step_count": len(traced),
                "evidence_paths": [entry_path],
            }
        )

    critical_paths = orchestration_paths + traced_paths
    if not critical_paths and entrypoints:
        first = entrypoints[0].get("path", "")
        critical_paths = [
            {
                "name": f"Fallback path from {_path_label(first)}",
                "entrypoint": first,
                "steps": [first],
                "step_count": 1,
                "evidence_paths": [first] if first else [],
            }
        ]

    raw_primary_steps = critical_paths[0].get("steps", []) if critical_paths else []
    raw_primary_plain_steps = critical_paths[0].get("plain_steps", []) if critical_paths else []
    request_lifecycle = [str(step) for step in raw_primary_plain_steps[:7]]
    if not request_lifecycle:
        request_lifecycle = [_humanize_call(step) if "." in step else _humanize_token(_path_label(step)) for step in raw_primary_steps[:7]]
    request_lifecycle = [s for s in request_lifecycle if s]
    if len(request_lifecycle) < 3:
        request_lifecycle = ["Repository intake", "Static analysis pipeline", "Onboarding outputs"]

    primary_user_flow = {
        "name": critical_paths[0].get("name", "Primary repository flow"),
        "steps": request_lifecycle,
        "evidence_paths": critical_paths[0].get("evidence_paths", []),
    }

    module_interactions = _module_interactions(internal_edges)
    trust_boundaries = _derive_trust_boundaries(entrypoints, dep_payload.get("external_dependencies", {}))
    data_lineage = _derive_data_lineage(request_lifecycle)

    payload = {
        "mapped_at": common.now_iso(),
        "mode": mode,
        "request_lifecycle": request_lifecycle,
        "primary_user_flow": primary_user_flow,
        "critical_paths": critical_paths,
        "module_interactions": module_interactions,
        "orchestration_paths": orchestration_paths,
        "trust_boundaries": trust_boundaries if mode == "deep" else trust_boundaries[:2],
        "data_lineage": data_lineage if mode == "deep" else data_lineage[:5],
        "dependency_edge_count": dep_payload.get("internal_edge_count", 0),
        "entrypoint_count": len(entrypoints),
    }
    common.write_json(out_dir / "flows.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Map codebase request and data flows.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()
    payload = map_flows(
        Path(args.repo).resolve(),
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
