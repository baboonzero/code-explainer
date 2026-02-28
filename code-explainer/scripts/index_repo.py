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


def _extract_symbol_candidates(path: Path) -> List[Dict[str, Any]]:
    text = common.read_text(path)
    if not text:
        return []
    symbols: List[Dict[str, Any]] = []
    patterns = [
        (r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", "function"),
        (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
        (r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", "function"),
        (r"^\s*const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(", "function"),
        (r"^\s*export\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
    ]
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = re.search(pattern, line)
            if match:
                symbols.append({"name": match.group(1), "kind": kind, "line": lineno})
    return symbols[:200]


def build_index(
    repo_root: Path,
    out_dir: Path,
    include_globs: List[str] | None = None,
    exclude_globs: List[str] | None = None,
) -> Dict[str, Any]:
    files = common.list_files(
        repo_root,
        include_globs=include_globs or [],
        exclude_globs=exclude_globs or [],
    )
    languages = common.language_counts(files)
    modules = common.top_level_modules(files)
    symbols: List[Dict[str, Any]] = []

    symbol_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs"}
    for item in files[:5000]:
        ext = item.get("ext")
        if ext not in symbol_extensions:
            continue
        absolute = repo_root / item["path"]
        extracted = _extract_symbol_candidates(absolute)
        if not extracted:
            continue
        for symbol in extracted:
            symbols.append(
                {
                    "file": item["path"],
                    "name": symbol["name"],
                    "kind": symbol["kind"],
                    "line": symbol["line"],
                }
            )
        if len(symbols) >= 12000:
            break

    payload = {
        "indexed_at": common.now_iso(),
        "repo_root": repo_root.as_posix(),
        "include_globs": include_globs or [],
        "exclude_globs": exclude_globs or [],
        "file_count": len(files),
        "files": files,
        "language_counts": languages,
        "modules": modules,
        "symbols": symbols,
    }
    common.write_json(out_dir / "index.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build file/module/symbol index for a repository.")
    parser.add_argument("--repo", required=True, help="Repository root path")
    parser.add_argument("--output", required=True, help="Output meta directory")
    parser.add_argument("--include-glob", action="append", default=[])
    parser.add_argument("--exclude-glob", action="append", default=[])
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    out_dir = Path(args.output).resolve()
    common.ensure_dir(out_dir)
    payload = build_index(
        repo_root,
        out_dir,
        include_globs=args.include_glob,
        exclude_globs=args.exclude_glob,
    )
    print(f"Indexed {payload['file_count']} files into {out_dir / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
