#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def map_entrypoints(index_payload: Dict[str, Any], repo_root: Path, out_dir: Path) -> Dict[str, Any]:
    files = index_payload.get("files", [])
    entrypoints = common.detect_entrypoints(files, repo_root=repo_root)
    payload = {
        "mapped_at": common.now_iso(),
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
