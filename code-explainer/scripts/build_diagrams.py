#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
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


def _safe_label(text: str, max_len: int = 34) -> str:
    cleaned = " ".join(str(text).replace("\\", "/").replace('"', "'").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _module_from_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if "/" not in normalized:
        return "(root-files)"
    return normalized.split("/", 1)[0]


def _first_entrypoint(entrypoints: List[Dict[str, Any]]) -> str:
    if not entrypoints:
        return "entrypoint"
    return str(entrypoints[0].get("path", "")).strip() or "entrypoint"


def _top_modules(plan_payload: Dict[str, Any], fallback_modules: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    planned = [item for item in plan_payload.get("top_modules", []) if isinstance(item, dict)]
    if planned:
        return planned[:limit]
    return [item for item in fallback_modules if item.get("name") and item.get("name") != "(root-files)"][:limit]


def _build_c4_context(stack: Dict[str, Any], dep_payload: Dict[str, Any], entrypoints: List[Dict[str, Any]]) -> str:
    repo_name = stack.get("repo_name", "System")
    frameworks = ", ".join(stack.get("frameworks", [])[:3]) or stack.get("primary_language", "primary stack")
    externals: List[str] = []
    for deps in dep_payload.get("external_dependencies", {}).values():
        for dep in deps:
            dep_lower = dep.lower()
            if any(token in dep_lower for token in ["postgres", "mysql", "redis", "supabase", "firebase", "aws", "stripe", "s3"]):
                externals.append(dep)
        if len(externals) >= 3:
            break
    external_label = ", ".join(externals[:3]) if externals else frameworks
    first_entry = _safe_label(Path(_first_entrypoint(entrypoints)).name, 22)
    repo_label = _safe_label(repo_name, 22)
    external_text = _safe_label(external_label, 28)
    return "\n".join(
        [
            "flowchart LR",
            f'    user["Primary user"]',
            f'    app["{repo_label}\\ncodebase under analysis"]',
            f'    entry["{first_entry}\\nentry surface"]',
            f'    ext["External systems\\n{external_text}"]',
            "    user -->|uses| app",
            "    app -->|starts at| entry",
            "    app -->|integrates with| ext",
        ]
    )


def _build_c4_container(stack: Dict[str, Any], entrypoints: List[Dict[str, Any]], modules: List[Dict[str, Any]]) -> str:
    repo_name = stack.get("repo_name", "System")
    language = stack.get("primary_language", "code")
    first_entry = _first_entrypoint(entrypoints)
    lines = [
        "flowchart TD",
        f'    entry["{_safe_label(Path(first_entry).name, 24)}\\nDetected entry surface"]',
    ]
    module_ids: List[str] = []
    for index, item in enumerate(modules, start=1):
        module_name = str(item.get("name", "module")).strip()
        container_id = f"m{index}"
        module_ids.append(container_id)
        lines.append(
            f'    {container_id}["{_safe_label(module_name, 24)}\\n{_safe_label(item.get("responsibility_hint", item.get("type", "module")), 28)}"]'
        )
    if module_ids:
        lines.append(f"    entry --> {module_ids[0]}")
        for left, right in zip(module_ids, module_ids[1:]):
            lines.append(f"    {left} --> {right}")
    lines.append(f'    note["{_safe_label(repo_name, 24)}\\n{_safe_label(language, 18)} stack"]')
    lines.append("    note -. context .-> entry")
    return "\n".join(lines)


def _build_request_lifecycle_sequence(flow_payload: Dict[str, Any]) -> str:
    steps = [str(item).strip() for item in flow_payload.get("request_lifecycle", []) if str(item).strip()]
    if len(steps) < 2:
        steps = ["User action", "Entrypoint", "Core logic", "Response"]
    lines = ["sequenceDiagram"]
    for index, step in enumerate(steps, start=1):
        lines.append(f'    participant S{index} as "{_safe_label(step)}"')
    for index in range(1, len(steps)):
        lines.append(f"    S{index}->>S{index + 1}: {_safe_label(steps[index - 1], 24)}")
    return "\n".join(lines)


def _build_primary_user_flow(plan_payload: Dict[str, Any], flow_payload: Dict[str, Any]) -> str:
    steps = [str(item).strip() for item in plan_payload.get("primary_flow_steps", []) if str(item).strip()]
    if len(steps) < 2:
        steps = [str(item).strip() for item in flow_payload.get("request_lifecycle", []) if str(item).strip()]
    if len(steps) < 2:
        steps = ["User intent", "Entrypoint", "Core behavior", "Outcome"]
    lines = ["flowchart TD"]
    for index, step in enumerate(steps):
        lines.append(f'    N{index}["{_safe_label(step)}"]')
    for index in range(len(steps) - 1):
        lines.append(f"    N{index} --> N{index + 1}")
    return "\n".join(lines)


def _major_module_edges(deps: Dict[str, Any], allowed_modules: List[str]) -> List[tuple[str, str]]:
    counts: Dict[tuple[str, str], int] = defaultdict(int)
    allowed = set(allowed_modules)
    for edge in deps.get("internal_edges", [])[:400]:
        src = _module_from_path(edge.get("from", ""))
        dst = _module_from_path(edge.get("to_resolved", "") or edge.get("to", ""))
        if src == dst or src not in allowed or dst not in allowed:
            continue
        counts[(src, dst)] += 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [item[0] for item in ranked[:12]]


def _build_module_dependency_graph(modules: List[Dict[str, Any]], deps: Dict[str, Any]) -> str:
    module_names = [str(item.get("name", "")).strip() for item in modules if item.get("name")]
    edges = _major_module_edges(deps, module_names)
    lines = ["flowchart LR"]
    for item in modules:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        node_id = common.safe_word(name, fallback="module")
        lines.append(f'    {node_id}["{_safe_label(name)}"]')
    if edges:
        for src, dst in edges:
            lines.append(f"    {common.safe_word(src)} --> {common.safe_word(dst)}")
    elif len(module_names) >= 2:
        for left, right in zip(module_names, module_names[1:]):
            lines.append(f"    {common.safe_word(left)} --> {common.safe_word(right)}")
    else:
        lines.append('    entry["entry"] --> core["core"]')
    return "\n".join(lines)


def _build_where_to_change_map(modules: List[Dict[str, Any]], entrypoints: List[Dict[str, Any]]) -> str:
    first_entry = _first_entrypoint(entrypoints)
    lines = ["flowchart TD", '    request["New change request"]', f'    entry["{_safe_label(first_entry)}"]', "    request --> entry"]
    for index, item in enumerate(modules[:5], start=1):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        node_id = f"C{index}"
        lines.append(f'    {node_id}["{_safe_label(name)}"]')
        lines.append(f"    entry --> {node_id}")
        lines.append(f'    {node_id} --> tests["tests or validation"]')
    return "\n".join(lines)


def build_diagrams(
    stack: Dict[str, Any],
    modules: List[Dict[str, Any]],
    deps: Dict[str, Any],
    flows: Dict[str, Any],
    plan_payload: Dict[str, Any],
    diagrams_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    common.ensure_dir(diagrams_dir)
    entrypoints = plan_payload.get("entrypoints", [])
    top_modules = _top_modules(plan_payload, modules)

    diagram_specs = [
        {
            "id": "c4_context",
            "title": "System context",
            "purpose": "Show the product boundary and external environment.",
            "body": _build_c4_context(stack, deps, entrypoints),
        },
        {
            "id": "c4_container",
            "title": "Codebase shape",
            "purpose": "Show the main entry surface and major code areas.",
            "body": _build_c4_container(stack, entrypoints, top_modules),
        },
        {
            "id": "request_lifecycle_sequence",
            "title": "Request lifecycle",
            "purpose": "Show the handoff across the main stages of execution.",
            "body": _build_request_lifecycle_sequence(flows),
        },
        {
            "id": "primary_user_flow",
            "title": "Primary user flow",
            "purpose": "Show the simplest end-to-end story through the codebase.",
            "body": _build_primary_user_flow(plan_payload, flows),
        },
        {
            "id": "module_dependency_graph",
            "title": "Module relationships",
            "purpose": "Show which top-level areas are central or coupled.",
            "body": _build_module_dependency_graph(top_modules, deps),
        },
    ]
    if mode == "deep":
        diagram_specs.append(
            {
                "id": "where_to_change_map",
                "title": "Where to change",
                "purpose": "Show likely starting points for implementing a feature change.",
                "body": _build_where_to_change_map(top_modules, entrypoints),
            }
        )

    files: List[str] = []
    manifest_items: List[Dict[str, str]] = []
    for item in diagram_specs:
        files.append(_write_diagram(diagrams_dir, item["id"], item["body"]))
        manifest_items.append(
            {
                "id": item["id"],
                "title": item["title"],
                "purpose": item["purpose"],
                "file": f"{item['id']}.mmd",
            }
        )

    payload = {
        "generated_at": common.now_iso(),
        "mode": mode,
        "diagram_files": files,
        "count": len(files),
        "diagrams": manifest_items,
    }
    common.write_json(diagrams_dir.parent / "meta" / "diagram_manifest.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build focused onboarding diagrams from repository analysis.")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--explanation-plan", required=True)
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()

    index_payload = common.read_json(Path(args.index), default={})
    stack_payload = common.read_json(Path(args.stack), default={})
    dep_payload = common.read_json(Path(args.dependencies), default={})
    flow_payload = common.read_json(Path(args.flows), default={})
    plan_payload = common.read_json(Path(args.explanation_plan), default={})
    payload = build_diagrams(
        stack_payload,
        index_payload.get("modules", []),
        dep_payload,
        flow_payload,
        plan_payload,
        Path(args.diagrams_dir).resolve(),
        common.normalize_mode(args.mode),
    )
    print(f"Built {payload['count']} diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
