#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


PRIMARY_ENTRY_BASENAMES = {
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "run.py",
    "manage.py",
    "analyze.py",
    "index.ts",
    "main.ts",
    "index.js",
    "main.js",
}

UTILITY_BASENAMES = {
    "common.py",
    "utils.py",
    "helpers.py",
    "constants.py",
    "types.py",
}


def _score_entrypoint(item: Dict[str, str]) -> int:
    path = item.get("path", "")
    kind = item.get("kind", "").lower()
    base = Path(path).name.lower()
    score = 0

    if base in PRIMARY_ENTRY_BASENAMES:
        score += 100
    if any(token in kind for token in ["bootstrap", "listener", "entrypoint", "main"]):
        score += 35
    if "fastapi" in kind or "django" in kind or "nestjs" in kind:
        score += 20
    if re.search(r"/(bin|cmd|scripts|apps?)/", path.replace("\\", "/")):
        score += 12
    if base not in PRIMARY_ENTRY_BASENAMES and not re.search(r"(main|app|server|cli|run|start|analyz)", base):
        score -= 20
    if "test" in path.lower() or "/spec" in path.lower():
        score -= 30
    if base in UTILITY_BASENAMES:
        score -= 40
    return score


def _rank_entrypoints(entrypoints: list[Dict[str, str]], max_items: int = 12) -> list[Dict[str, str]]:
    enriched = []
    for item in entrypoints:
        row = dict(item)
        row["score"] = _score_entrypoint(item)
        enriched.append(row)
    enriched.sort(key=lambda x: (x.get("score", 0), x.get("path", "")), reverse=True)
    if not enriched:
        return []

    primary = [x for x in enriched if int(x.get("score", 0)) >= 40][:max_items]
    if primary:
        return primary
    return enriched[:max_items]


def map_entrypoints(index_payload: Dict[str, Any], repo_root: Path, out_dir: Path) -> Dict[str, Any]:
    files = index_payload.get("files", [])
    raw_entrypoints = common.detect_entrypoints(files, repo_root=repo_root)
    entrypoints = _rank_entrypoints(raw_entrypoints, max_items=12)
    payload = {
        "mapped_at": common.now_iso(),
        "raw_count": len(raw_entrypoints),
        "entrypoints": entrypoints,
        "count": len(entrypoints),
    }
    common.write_json(out_dir / "entrypoints.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Map probable application entrypoints.")
    parser.add_argument("--index", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = map_entrypoints(
        common.read_json(Path(args.index), default={}),
        Path(args.repo).resolve(),
        Path(args.output).resolve(),
    )
    print(f"Mapped {payload['count']} entrypoints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
