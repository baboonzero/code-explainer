#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _build_python_module_map(files: List[Dict[str, Any]]) -> Dict[str, str]:
    module_map: Dict[str, str] = {}
    for item in files:
        path = item["path"]
        if not path.endswith(".py"):
            continue
        if path.endswith("__init__.py"):
            module = path[: -len("__init__.py")].rstrip("/").replace("/", ".")
        else:
            module = path[: -len(".py")].replace("/", ".")
        if module:
            module_map[module] = path
    return module_map


def _resolve_python_import(
    src_path: str,
    target: str,
    imported_symbol: str,
    module_map: Dict[str, str],
    file_set: set[str],
) -> str:
    src_module = src_path[: -len(".py")].replace("/", ".") if src_path.endswith(".py") else ""
    if target.startswith("."):
        dot_count = len(target) - len(target.lstrip("."))
        base_parts = src_module.split(".")
        if src_path.endswith("__init__.py") and base_parts:
            base_parts = base_parts[:-1]
        keep = max(0, len(base_parts) - dot_count)
        suffix = target.lstrip(".")
        abs_module = ".".join([*base_parts[:keep], suffix]).strip(".")
        if abs_module in module_map:
            return module_map[abs_module]
        symbol_module = f"{abs_module}.{imported_symbol}".strip(".")
        if symbol_module in module_map:
            return module_map[symbol_module]
        return ""

    if target in module_map:
        return module_map[target]
    symbol_module = f"{target}.{imported_symbol}".strip(".")
    if symbol_module in module_map:
        return module_map[symbol_module]

    root_token = target.split(".", 1)[0]
    src_dir = Path(src_path).parent.as_posix()
    if src_dir == ".":
        src_dir = ""
    sibling_candidates = [
        f"{src_dir}/{root_token}.py" if src_dir else f"{root_token}.py",
        f"{src_dir}/{root_token}/__init__.py" if src_dir else f"{root_token}/__init__.py",
        f"{root_token}.py",
        f"{root_token}/__init__.py",
    ]
    for candidate in sibling_candidates:
        normalized = candidate.replace("//", "/")
        if normalized in file_set:
            return normalized
    return ""


def _resolve_js_import(src_path: str, target: str, file_set: set[str], top_levels: set[str]) -> str:
    src_dir = Path(src_path).parent
    candidates: List[str] = []

    def add_candidates(base: str) -> None:
        ext_candidates = ["", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", "/index.js", "/index.ts", "/index.tsx"]
        for ext in ext_candidates:
            candidates.append((base + ext).replace("\\", "/"))

    if target.startswith("."):
        add_candidates((src_dir / target).as_posix())
    elif target.startswith("@/"):
        add_candidates(target[2:])
    elif target.split("/", 1)[0] in top_levels:
        add_candidates(target)

    for c in candidates:
        norm = c.replace("//", "/")
        if norm in file_set:
            return norm
    return ""


def _internal_edges(repo_root: Path, files: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    scan_exts = {".py", ".js", ".ts", ".tsx", ".jsx"}
    file_set = {item["path"] for item in files}
    top_levels = {p.split("/", 1)[0] for p in file_set if "/" in p}
    py_module_map = _build_python_module_map(files)
    py_root_tokens = {k.split(".", 1)[0] for k in py_module_map}

    for item in files[:12000]:
        ext = item.get("ext")
        if ext not in scan_exts:
            continue
        src_path = item["path"]
        text = common.read_text(repo_root / src_path)
        if not text:
            continue
        for line in text.splitlines():
            if ext == ".py":
                m_from = re.search(r"^\s*from\s+([A-Za-z0-9_\.]+|\.+[A-Za-z0-9_\.]*)\s+import\s+([A-Za-z0-9_*, ]+)", line)
                if m_from:
                    target = m_from.group(1).strip()
                    imported = m_from.group(2).split(",")[0].strip().strip("*")
                    resolved = _resolve_python_import(src_path, target, imported, py_module_map, file_set)
                    if resolved or target.startswith(".") or target.split(".", 1)[0] in py_root_tokens:
                        edges.append({"from": src_path, "to": target, "to_resolved": resolved, "kind": "python-from"})
                    continue

                m_import = re.search(r"^\s*import\s+([A-Za-z0-9_\. ,]+)", line)
                if m_import:
                    imports = [s.strip() for s in m_import.group(1).split(",") if s.strip()]
                    for target in imports:
                        target = target.split(" as ", 1)[0].strip()
                        resolved = _resolve_python_import(src_path, target, "", py_module_map, file_set)
                        if resolved or target.split(".", 1)[0] in py_root_tokens:
                            edges.append({"from": src_path, "to": target, "to_resolved": resolved, "kind": "python-import"})
                continue

            # JS/TS imports
            m_from = re.search(r'^\s*import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', line)
            if m_from:
                target = m_from.group(1).strip()
                resolved = _resolve_js_import(src_path, target, file_set, top_levels)
                if resolved or target.startswith(".") or target.startswith("@/") or "/" in target:
                    edges.append({"from": src_path, "to": target, "to_resolved": resolved, "kind": "js-from"})
                continue

            m_req = re.search(r'^\s*(?:const|let|var)?\s*.*?require\([\'"]([^\'"]+)[\'"]\)', line)
            if m_req:
                target = m_req.group(1).strip()
                resolved = _resolve_js_import(src_path, target, file_set, top_levels)
                if resolved or target.startswith(".") or target.startswith("@/") or "/" in target:
                    edges.append({"from": src_path, "to": target, "to_resolved": resolved, "kind": "js-require"})

    return edges[:20000]


def map_dependencies(repo_root: Path, index_payload: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    files = index_payload.get("files", [])
    external = common.scan_external_dependencies(repo_root)
    internal = _internal_edges(repo_root, files)
    payload = {
        "mapped_at": common.now_iso(),
        "external_dependencies": external,
        "internal_edges": internal,
        "external_count": sum(len(v) for v in external.values()),
        "internal_edge_count": len(internal),
    }
    common.write_json(out_dir / "dependencies.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Map external and internal dependencies.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = map_dependencies(
        Path(args.repo).resolve(),
        common.read_json(Path(args.index), default={}),
        Path(args.output).resolve(),
    )
    print(
        f"Dependencies mapped: external={payload['external_count']} "
        f"internal_edges={payload['internal_edge_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
