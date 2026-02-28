#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _write_diagram(diagrams_dir: Path, name: str, body: str) -> str:
    path = diagrams_dir / f"{name}.mmd"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path.name


def _safe_label(text: str, max_len: int = 42) -> str:
    cleaned = " ".join(text.replace("\\", "/").replace('"', "'").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _node_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx}"


def _module_from_path(path: str) -> str:
    if not path:
        return "unknown"
    norm = path.replace("\\", "/")
    if "/" not in norm:
        return "(root-files)"
    return norm.split("/", 1)[0]


def _build_request_lifecycle_sequence(flows: Dict[str, Any]) -> str:
    steps = flows.get("request_lifecycle", [])
    if len(steps) < 2:
        steps = ["User Action", "Application Layer", "Response"]
    participants = []
    messages = []
    for idx, step in enumerate(steps, start=1):
        pid = _node_id("P", idx)
        participants.append(f'    participant {pid} as "{_safe_label(step, 34)}"')
    for idx in range(1, len(steps)):
        src = _node_id("P", idx)
        dst = _node_id("P", idx + 1)
        messages.append(f"    {src}->>{dst}: {_safe_label(steps[idx - 1], 30)}")
    return "sequenceDiagram\n" + "\n".join(participants + messages)


def _build_primary_user_flow(flows: Dict[str, Any]) -> str:
    primary = flows.get("primary_user_flow", {})
    steps = primary.get("steps", [])
    if len(steps) < 2:
        steps = ["User intent", "Entrypoint", "Core module", "Result"]

    lines = ["flowchart TD"]
    for idx, step in enumerate(steps):
        nid = _node_id("N", idx)
        lines.append(f'    {nid}["{_safe_label(step)}"]')
    for idx in range(len(steps) - 1):
        lines.append(f"    N{idx} --> N{idx + 1}")
    return "\n".join(lines)


def _build_module_dependency_graph(deps: Dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    edge_lines: List[str] = []
    seen = set()
    for edge in deps.get("internal_edges", [])[:120]:
        src_path = edge.get("from", "")
        dst_path = edge.get("to_resolved", "") or edge.get("to", "")
        src_mod = common.safe_word(_module_from_path(src_path), fallback="module_src")
        dst_mod = common.safe_word(_module_from_path(dst_path), fallback="module_dst")
        key = f"{src_mod}->{dst_mod}"
        if src_mod == dst_mod or key in seen:
            continue
        seen.add(key)
        edge_lines.append(f"    {src_mod} --> {dst_mod}")
        if len(edge_lines) >= 45:
            break
    if not edge_lines:
        edge_lines = ["    module_a --> module_b", "    module_b --> module_c"]
    lines.extend(edge_lines)
    return "\n".join(lines)


def _build_critical_path_sequence(flows: Dict[str, Any]) -> str:
    critical_paths = flows.get("critical_paths", [])
    steps: List[str] = []
    if critical_paths:
        steps = critical_paths[0].get("steps", [])
    if len(steps) < 2:
        steps = ["Entry", "Service", "Data", "Response"]

    lines = ["sequenceDiagram"]
    for idx, step in enumerate(steps, start=1):
        lines.append(f'    participant C{idx} as "{_safe_label(step, 36)}"')
    for idx in range(1, len(steps)):
        lines.append(f"    C{idx}->>C{idx + 1}: {_safe_label(steps[idx - 1], 30)}")
    return "\n".join(lines)


def _build_trust_boundary_flow(flows: Dict[str, Any]) -> str:
    boundaries = flows.get("trust_boundaries", [])
    if not boundaries:
        boundaries = [
            {"name": "External user to application", "type": "network"},
            {"name": "Application to data store", "type": "data"},
        ]

    lines = ["flowchart TB", '    user["External Actor"]', '    app["Application Boundary"]']
    lines.append("    user --> app")
    last_node = "app"
    for idx, boundary in enumerate(boundaries, start=1):
        nid = _node_id("T", idx)
        label = _safe_label(f"{boundary.get('name', 'Boundary')} ({boundary.get('type', 'trust')})", 44)
        lines.append(f'    {nid}["{label}"]')
        lines.append(f"    {last_node} --> {nid}")
        last_node = nid
    return "\n".join(lines)


def _build_data_lineage_flow(flows: Dict[str, Any]) -> str:
    lineage = flows.get("data_lineage", [])
    if len(lineage) < 2:
        lineage = ["Input", "Validation", "Processing", "Storage", "Presentation"]

    lines = ["flowchart LR"]
    for idx, step in enumerate(lineage):
        nid = _node_id("D", idx)
        lines.append(f'    {nid}["{_safe_label(step, 38)}"]')
    for idx in range(len(lineage) - 1):
        lines.append(f"    D{idx} --> D{idx + 1}")
    return "\n".join(lines)


def _build_where_to_change_map(modules: List[Dict[str, Any]], flows: Dict[str, Any]) -> str:
    lines = ["flowchart TD", '    req["Feature Request"]']
    module_names = [m.get("name", "module") for m in modules if m.get("name") != "(root-files)"][:6]
    if not module_names:
        module_names = ["entrypoints", "services", "data"]
    for idx, name in enumerate(module_names, start=1):
        nid = _node_id("M", idx)
        lines.append(f'    {nid}["{_safe_label(name)}"]')
        lines.append(f"    req --> {nid}")
        lines.append(f"    {nid} --> tests")
    if flows.get("primary_user_flow", {}).get("steps"):
        lines.append('    tests["Test Coverage"]')
    else:
        lines.append('    tests["Validation Checklist"]')
    return "\n".join(lines)


def build_diagrams(
    stack: Dict[str, Any],
    modules: List[Dict[str, Any]],
    deps: Dict[str, Any],
    flows: Dict[str, Any],
    diagrams_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    common.ensure_dir(diagrams_dir)
    files: List[str] = []

    repo_name = stack.get("repo_name", "System")
    frameworks = ", ".join(stack.get("frameworks", [])[:3]) or "Core stack"
    primary_language = stack.get("primary_language", "Unknown")

    files.append(
        _write_diagram(
            diagrams_dir,
            "c4_context",
            f"""
C4Context
  title C4 Context - {repo_name}
  Person(user, "User", "PM, designer, or engineer using the product")
  System(app, "{repo_name}", "Software platform under analysis")
  System_Ext(ext, "External systems", "{frameworks}")
  Rel(user, app, "Uses")
  Rel(app, ext, "Integrates with")
""",
        )
    )

    module_labels = [m["name"] for m in modules if m["name"] != "(root-files)"][:5] or ["core"]
    container_nodes = "\n".join(
        [f'    Container(c{i}, "{_safe_label(name, 28)}", "{primary_language}", "Core module")' for i, name in enumerate(module_labels, start=1)]
    )
    rel_lines = []
    for i in range(1, len(module_labels)):
        rel_lines.append(f'  Rel(c{i}, c{i + 1}, "calls/depends on")')
    files.append(
        _write_diagram(
            diagrams_dir,
            "c4_container",
            f"""
C4Container
  title C4 Container - {repo_name}
  Person(user, "User", "Interacts with platform")
  System_Boundary(sys, "{repo_name}") {{
{container_nodes}
  }}
  Rel(user, c1, "Interacts with")
{"".join(line + chr(10) for line in rel_lines)}
""",
        )
    )

    files.append(_write_diagram(diagrams_dir, "request_lifecycle_sequence", _build_request_lifecycle_sequence(flows)))
    files.append(_write_diagram(diagrams_dir, "primary_user_flow", _build_primary_user_flow(flows)))
    files.append(_write_diagram(diagrams_dir, "module_dependency_graph", _build_module_dependency_graph(deps)))

    if mode == "deep":
        files.append(_write_diagram(diagrams_dir, "critical_path_sequence", _build_critical_path_sequence(flows)))
        files.append(_write_diagram(diagrams_dir, "trust_boundary_flow", _build_trust_boundary_flow(flows)))
        files.append(_write_diagram(diagrams_dir, "data_lineage_flow", _build_data_lineage_flow(flows)))
        files.append(_write_diagram(diagrams_dir, "where_to_change_map", _build_where_to_change_map(modules, flows)))

    payload = {
        "generated_at": common.now_iso(),
        "mode": mode,
        "diagram_files": files,
        "count": len(files),
    }
    common.write_json(diagrams_dir.parent / "meta" / "diagram_manifest.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Mermaid diagrams from analysis artifacts.")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()

    index_payload = common.read_json(Path(args.index), default={})
    stack_payload = common.read_json(Path(args.stack), default={})
    dep_payload = common.read_json(Path(args.dependencies), default={})
    flow_payload = common.read_json(Path(args.flows), default={})
    payload = build_diagrams(
        stack_payload,
        index_payload.get("modules", []),
        dep_payload,
        flow_payload,
        Path(args.diagrams_dir).resolve(),
        common.normalize_mode(args.mode),
    )
    print(f"Built {payload['count']} Mermaid diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
