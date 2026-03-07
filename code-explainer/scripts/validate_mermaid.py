#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


VALID_STARTERS = {
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "C4Context",
    "C4Container",
    "C4Component",
    "C4Dynamic",
    "C4Deployment",
    "gantt",
    "gitGraph",
}


def _heuristic_validate(text: str) -> List[str]:
    errors: List[str] = []
    stripped = text.strip()
    if not stripped:
        return ["Empty Mermaid document"]
    first = stripped.splitlines()[0].strip()
    starter = first.split()[0] if first else ""
    if starter not in VALID_STARTERS:
        errors.append(f"Unknown diagram starter '{first}'")
    if text.count("[") != text.count("]"):
        errors.append("Unbalanced square brackets")
    if text.count("{") != text.count("}"):
        errors.append("Unbalanced curly braces")
    return errors


def validate_mermaid(diagrams_dir: Path, out_meta_dir: Path) -> Dict[str, Any]:
    mmdc = common.which("mmdc")
    results = []
    overall_ok = True
    environment_blocked = False
    temp_root = common.ensure_dir(out_meta_dir / ".validate_tmp")
    for mmd in sorted(diagrams_dir.glob("*.mmd")):
        text = common.read_text(mmd)
        errors: List[str] = []
        warnings: List[str] = []
        method = "heuristic"
        if mmdc:
            method = "mmdc"
            temp_dir = temp_root / mmd.stem
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            common.ensure_dir(temp_dir)
            temp_svg = temp_dir / "out.svg"
            code, _stdout, stderr = common.run_cmd(
                [mmdc, "-i", str(mmd), "-o", str(temp_svg), "-b", "transparent"],
                timeout=45,
            )
            if code != 0:
                stderr_text = stderr.strip() or "mmdc validation failed"
                if common.is_mermaid_environment_failure(stderr_text):
                    method = "heuristic-fallback"
                    environment_blocked = True
                    warnings.append(stderr_text)
                    errors.extend(_heuristic_validate(text))
                else:
                    errors.append(stderr_text)
        else:
            errors.extend(_heuristic_validate(text))

        ok = len(errors) == 0
        overall_ok = overall_ok and ok
        results.append(
            {
                "file": mmd.name,
                "ok": ok,
                "method": method,
                "errors": errors,
                "warnings": warnings,
            }
        )

    payload = {
        "validated_at": common.now_iso(),
        "validator": "mmdc" if mmdc else "heuristic",
        "overall_ok": overall_ok,
        "environment_blocked": environment_blocked,
        "results": results,
    }
    common.write_json(out_meta_dir / "mermaid_validation.json", payload)
    shutil.rmtree(temp_root, ignore_errors=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Mermaid files.")
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--output", required=True, help="Meta output directory")
    args = parser.parse_args()

    payload = validate_mermaid(Path(args.diagrams_dir).resolve(), Path(args.output).resolve())
    bad = [r for r in payload["results"] if not r["ok"]]
    if bad:
        print(f"Validation failed for {len(bad)} diagram(s)")
        return 1
    print(f"Validated {len(payload['results'])} diagram(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
