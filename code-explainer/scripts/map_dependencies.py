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


def _internal_edges(repo_root: Path, files: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    import_patterns = [
        r'^\s*import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
        r'^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+',
        r'^\s*require\([\'"]([^\'"]+)[\'"]\)',
    ]
    scan_exts = {".py", ".js", ".ts", ".tsx", ".jsx"}
    for item in files[:8000]:
        ext = item.get("ext")
        if ext not in scan_exts:
            continue
        src_path = item["path"]
        text = common.read_text(repo_root / src_path)
        if not text:
            continue
        for line in text.splitlines():
            for pattern in import_patterns:
                match = re.search(pattern, line)
                if not match:
                    continue
                target = match.group(1)
                if target.startswith(".") or "/" in target:
                    edges.append({"from": src_path, "to": target})
    return edges[:12000]


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

