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


def analyze_stack(repo_root: Path, index_payload: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    frameworks = common.detect_frameworks(repo_root)
    architecture = common.detect_architecture_pattern(repo_root)
    languages = index_payload.get("language_counts", {})
    primary_language = next(iter(languages), "Unknown")
    repo_name = common.detect_repo_name(repo_root.as_posix(), repo_root)

    payload = {
        "analyzed_at": common.now_iso(),
        "repo_name": repo_name,
        "primary_language": primary_language,
        "languages": languages,
        "frameworks": frameworks,
        "architecture_pattern": architecture,
    }
    common.write_json(out_dir / "stack.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect codebase language/framework/architecture stack.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--index", required=True, help="Path to index.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    index_payload = common.read_json(Path(args.index), default={})
    payload = analyze_stack(Path(args.repo).resolve(), index_payload, Path(args.output).resolve())
    print(
        f"Detected primary language={payload['primary_language']} "
        f"frameworks={','.join(payload['frameworks']) if payload['frameworks'] else 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

