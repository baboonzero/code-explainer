#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _write_diagram(diagrams_dir: Path, name: str, body: str) -> str:
    path = diagrams_dir / f"{name}.mmd"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path.name


def _safe_label(text: str, max_len: int = 52) -> str:
    cleaned = " ".join(str(text or "").replace("\\", "/").replace('"', "'").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _safe_id(value: str, idx: int) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "").strip())
    if not base:
        base = "node"
    return f"N{idx}_{base[:24]}"


def _humanize_step(step: str) -> str:
    text = str(step or "").strip()
    if not text:
        return "unknown"
    if "/" in text:
        leaf = Path(text).stem
        parent = Path(text).parent.name
        return f"{parent}/{leaf}" if parent and parent != "." else leaf
    if "." in text:
        left, right = text.rsplit(".", 1)
        return f"{left.replace('_', ' ')}: {right.replace('_', ' ')}"
    return text.replace("_", " ")


def _module_from_path(path: str) -> str:
    norm = str(path or "").replace("\\", "/").strip("/")
    if not norm:
        return "unknown"
    parts = norm.split("/")
    if len(parts) >= 3 and parts[1] in {"scripts", "src", "app", "lib"}:
        return parts[1]
    if len(parts) >= 2 and parts[0] in {"code-explainer", "packages", "apps"}:
        return parts[1]
    return parts[0]


def _build_context_diagram(repo_name: str, frameworks: str) -> str:
    return f"""
C4Context
  title C4 Context - {repo_name}
  Person(newjoiner, "New Joiner", "PM, designer, or engineer onboarding to this repository")
  System(explainer, "Code Explainer", "Builds human-readable onboarding artifacts")
  System(repo, "{repo_name}", "Repository under analysis")
  System_Ext(bundle, "Onboarding bundle", "Markdown + HTML + Mermaid/SVG/PNG artifacts")
  Rel(newjoiner, explainer, "Runs analysis")
  Rel(explainer, repo, "Reads code, docs, and structure from")
  Rel(explainer, bundle, "Produces explainers and diagrams for")
"""


def _build_container_diagram(repo_name: str, modules: List[Dict[str, Any]], flows: Dict[str, Any], primary_language: str) -> str:
    interactions = flows.get("module_interactions", [])
    ranked = [m.get("name", "") for m in modules if m.get("name") and m.get("name") != "(root-files)"][:6]
    ranked_from_critical = False
    critical = flows.get("critical_paths", [])
    if critical:
        call_modules = []
        for step in critical[0].get("steps", []):
            value = str(step)
            if "." not in value:
                continue
            mod = value.split(".", 1)[0].strip()
            if mod and mod not in call_modules:
                call_modules.append(mod)
            if len(call_modules) >= 6:
                break
        if len(call_modules) >= 2:
            ranked = call_modules[:6]
            ranked_from_critical = True
    if interactions and not ranked_from_critical:
        ordered = []
        for row in interactions:
            for key in ["from_module", "to_module"]:
                value = str(row.get(key, "")).strip()
                if value and value not in ordered and value != "(root-files)":
                    ordered.append(value)
            if len(ordered) >= 6:
                break
        if ordered:
            ranked = ordered[:6]

    if not ranked:
        ranked = ["application", "core", "outputs"]

    container_lines = []
    for idx, module_name in enumerate(ranked, start=1):
        container_lines.append(
            f'    Container(c{idx}, "{_safe_label(module_name, 24)}", "{primary_language}", "Major module group")'
        )
    rel_lines = []
    if interactions:
        used = set()
        idx_map = {name: i + 1 for i, name in enumerate(ranked)}
        for row in interactions[:18]:
            src = row.get("from_module", "")
            dst = row.get("to_module", "")
            if src not in idx_map or dst not in idx_map:
                continue
            key = (src, dst)
            if key in used:
                continue
            used.add(key)
            rel_lines.append(f'  Rel(c{idx_map[src]}, c{idx_map[dst]}, "depends on")')
    if not rel_lines and len(ranked) >= 2:
        for i in range(1, len(ranked)):
            rel_lines.append(f'  Rel(c{i}, c{i + 1}, "interacts with")')

    return (
        f"""
C4Container
  title C4 Container - {repo_name}
  Person(newjoiner, "New Joiner", "Uses generated onboarding docs")
  System_Boundary(sys, "{repo_name}") {{
{chr(10).join(container_lines)}
  }}
  Rel(newjoiner, c1, "Starts from")
{chr(10).join(rel_lines)}
"""
    )


def _build_request_lifecycle_sequence(flows: Dict[str, Any]) -> str:
    steps = [str(s) for s in flows.get("request_lifecycle", []) if str(s).strip()]
    if len(steps) < 3:
        steps = ["Repository intake", "Analysis pipeline", "Onboarding output"]

    lines = ["sequenceDiagram"]
    for idx, step in enumerate(steps, start=1):
        lines.append(f'    participant P{idx} as "{_safe_label(step, 36)}"')
    for idx in range(1, len(steps)):
        lines.append(f"    P{idx}->>P{idx + 1}: {_safe_label(steps[idx - 1], 30)}")
    return "\n".join(lines)


def _build_primary_user_flow(flows: Dict[str, Any]) -> str:
    steps = [str(s) for s in flows.get("primary_user_flow", {}).get("steps", []) if str(s).strip()]
    if len(steps) < 3:
        steps = [str(s) for s in flows.get("request_lifecycle", []) if str(s).strip()][:5]
    if len(steps) < 3:
        steps = ["Repository intake", "Analysis", "Output"]

    lines = ["flowchart TD"]
    node_ids = []
    for idx, step in enumerate(steps):
        nid = _safe_id(step, idx)
        node_ids.append(nid)
        lines.append(f'    {nid}["{_safe_label(step)}"]')
    for idx in range(len(node_ids) - 1):
        lines.append(f"    {node_ids[idx]} --> {node_ids[idx + 1]}")
    return "\n".join(lines)


def _build_module_dependency_graph(deps: Dict[str, Any], flows: Dict[str, Any], modules: List[Dict[str, Any]]) -> str:
    lines = ["flowchart LR"]
    edge_lines: List[str] = []
    seen = set()

    for edge in deps.get("internal_edges", [])[:400]:
        src_path = edge.get("from", "")
        src_mod = common.safe_word(_module_from_path(src_path), fallback="src")
        dst_path = edge.get("to_resolved", "") or edge.get("to", "")
        dst_mod = common.safe_word(_module_from_path(dst_path), fallback="dst")
        if src_mod == dst_mod:
            src_mod = common.safe_word(Path(src_path).stem, fallback="src_file")
            dst_mod = common.safe_word(Path(dst_path).stem, fallback="dst_file")
        if not src_mod or not dst_mod or src_mod == dst_mod:
            continue
        key = f"{src_mod}->{dst_mod}"
        if key in seen:
            continue
        seen.add(key)
        edge_lines.append(f"    {src_mod} --> {dst_mod}")
        if len(edge_lines) >= 55:
            break

    if not edge_lines:
        for row in flows.get("module_interactions", [])[:20]:
            src_mod = common.safe_word(str(row.get("from_module", "")), fallback="src")
            dst_mod = common.safe_word(str(row.get("to_module", "")), fallback="dst")
            if not src_mod or not dst_mod or src_mod == dst_mod:
                continue
            key = f"{src_mod}->{dst_mod}"
            if key in seen:
                continue
            seen.add(key)
            edge_lines.append(f"    {src_mod} --> {dst_mod}")

    if not edge_lines:
        module_names = [m.get("name", "") for m in modules if m.get("name") and m.get("name") != "(root-files)"][:3]
        for i in range(len(module_names) - 1):
            src_mod = common.safe_word(module_names[i], fallback=f"module_{i}")
            dst_mod = common.safe_word(module_names[i + 1], fallback=f"module_{i + 1}")
            edge_lines.append(f"    {src_mod} --> {dst_mod}")

    lines.extend(edge_lines or ["    repository --> outputs"])
    return "\n".join(lines)


def _build_critical_path_sequence(flows: Dict[str, Any]) -> str:
    path = []
    if flows.get("critical_paths"):
        path = [str(s) for s in flows["critical_paths"][0].get("steps", []) if str(s).strip()]
    if len(path) < 3:
        path = [str(s) for s in flows.get("request_lifecycle", []) if str(s).strip()][:5]
    if len(path) < 3:
        path = ["Entry", "Processing", "Output"]

    human_steps = [_humanize_step(step) for step in path[:8]]
    lines = ["sequenceDiagram"]
    for idx, step in enumerate(human_steps, start=1):
        lines.append(f'    participant C{idx} as "{_safe_label(step, 34)}"')
    for idx in range(1, len(human_steps)):
        lines.append(f"    C{idx}->>C{idx + 1}: {_safe_label(human_steps[idx - 1], 30)}")
    return "\n".join(lines)


def _build_trust_boundary_flow(flows: Dict[str, Any]) -> str:
    boundaries = flows.get("trust_boundaries", [])
    lines = ["flowchart TB", '    actor["External actor"]']
    if not boundaries:
        lines.extend(['    app["Repository boundary"]', "    actor --> app"])
        return "\n".join(lines)

    previous = "actor"
    for idx, boundary in enumerate(boundaries, start=1):
        node = f"T{idx}"
        label = _safe_label(f"{boundary.get('name', '')} ({boundary.get('type', '')})", 48)
        lines.append(f'    {node}["{label}"]')
        lines.append(f"    {previous} --> {node}")
        previous = node
    return "\n".join(lines)


def _build_data_lineage_flow(flows: Dict[str, Any]) -> str:
    lineage = [str(s) for s in flows.get("data_lineage", []) if str(s).strip()]
    if len(lineage) < 3:
        lineage = ["Input", "Processing", "Output"]
    lines = ["flowchart LR"]
    node_ids = []
    for idx, step in enumerate(lineage):
        nid = f"D{idx}"
        node_ids.append(nid)
        lines.append(f'    {nid}["{_safe_label(step, 42)}"]')
    for idx in range(len(node_ids) - 1):
        lines.append(f"    {node_ids[idx]} --> {node_ids[idx + 1]}")
    return "\n".join(lines)


def _build_where_to_change_map(modules: List[Dict[str, Any]], flows: Dict[str, Any]) -> str:
    lines = ["flowchart TD", '    request["Feature request"]']
    candidates = [m.get("name", "") for m in modules if m.get("name") and m.get("name") != "(root-files)"][:5]
    if not candidates:
        candidates = [str(s) for s in flows.get("request_lifecycle", [])[:4]]
    if not candidates:
        candidates = ["entrypoint", "core", "docs"]

    for idx, name in enumerate(candidates, start=1):
        node = f"W{idx}"
        lines.append(f'    {node}["{_safe_label(name, 30)}"]')
        lines.append(f"    request --> {node}")
        lines.append(f"    {node} --> tests")
    lines.append('    tests["Validation and regression checks"]')
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

    repo_name = stack.get("repo_name", "Repository")
    frameworks = ", ".join(stack.get("frameworks", [])[:3]) or "detected project stack"
    primary_language = stack.get("primary_language", "Unknown")

    files.append(_write_diagram(diagrams_dir, "c4_context", _build_context_diagram(repo_name, frameworks)))
    files.append(_write_diagram(diagrams_dir, "c4_container", _build_container_diagram(repo_name, modules, flows, primary_language)))
    files.append(_write_diagram(diagrams_dir, "request_lifecycle_sequence", _build_request_lifecycle_sequence(flows)))
    files.append(_write_diagram(diagrams_dir, "primary_user_flow", _build_primary_user_flow(flows)))
    files.append(_write_diagram(diagrams_dir, "module_dependency_graph", _build_module_dependency_graph(deps, flows, modules)))

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
