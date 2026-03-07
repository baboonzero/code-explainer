#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze
import common


FIXTURES = [
    {
        "name": "todo-api",
        "source": SKILL_DIR / "assets" / "fixtures" / "todo-api",
        "audience": "mixed",
    },
    {
        "name": "insights-dashboard",
        "source": SKILL_DIR / "assets" / "fixtures" / "insights-dashboard",
        "audience": "nontech",
    },
]


def _run_fixture(base_output: Path, fixture: Dict[str, Any]) -> Dict[str, Any]:
    output_root = base_output / fixture["name"]
    os.environ["CODE_EXPLAINER_MOCK_LLM"] = "true"
    summary = analyze.run_pipeline(
        source=fixture["source"].as_posix(),
        output_root=output_root,
        mode="standard",
        audience=fixture["audience"],
        overview_length="medium",
        output_format="markdown",
        analysis_type="onboarding",
        enable_web_enrichment=False,
        enable_llm_descriptions=True,
        enable_excalidraw_export=True,
        enable_official_excalidraw_bridge=False,
    )
    quality = common.read_json(output_root / "meta" / "quality_report.json", default={})
    explanation_quality = common.read_json(output_root / "meta" / "explanation_quality.json", default={})
    excalidraw = common.read_json(output_root / "meta" / "excalidraw_report.json", default={})
    return {
        "fixture": fixture["name"],
        "output_root": output_root.as_posix(),
        "quality_passed": summary.get("quality_passed", False),
        "diagram_count": summary.get("diagram_count", 0),
        "explanation_quality_score": explanation_quality.get("score", 0.0),
        "excalidraw_status": excalidraw.get("status", "missing"),
        "excalidraw_scene_count": excalidraw.get("scene_count", 0),
        "quality_errors": quality.get("errors", []),
        "quality_warnings": quality.get("warnings", []),
    }


def run_self_audit(output_root: Path) -> Dict[str, Any]:
    common.ensure_dir(output_root)
    results = [_run_fixture(output_root, fixture) for fixture in FIXTURES]
    passed = (
        all(item["quality_passed"] for item in results)
        and all(item["explanation_quality_score"] >= 80.0 for item in results)
        and all(item["excalidraw_status"] == "ok" for item in results)
        and all(item["excalidraw_scene_count"] >= item["diagram_count"] for item in results)
    )
    payload = {
        "generated_at": common.now_iso(),
        "passed": passed,
        "fixtures": results,
    }
    common.write_json(output_root / "self-audit.json", payload)

    lines = [
        "# Code Explainer Self Audit",
        "",
        f"- Passed: `{passed}`",
        "",
        "## Fixture Results",
        "",
    ]
    for item in results:
        lines.append(f"### {item['fixture']}")
        lines.append(f"- Quality passed: `{item['quality_passed']}`")
        lines.append(f"- Explanation quality score: `{item['explanation_quality_score']}`")
        lines.append(f"- Diagram count: `{item['diagram_count']}`")
        lines.append(f"- Excalidraw status: `{item['excalidraw_status']}`")
        lines.append(f"- Excalidraw scene count: `{item['excalidraw_scene_count']}`")
        if item["quality_errors"]:
            lines.append("- Errors:")
            for err in item["quality_errors"]:
                lines.append(f"  - {err}")
        if item["quality_warnings"]:
            lines.append("- Warnings:")
            for warn in item["quality_warnings"]:
                lines.append(f"  - {warn}")
        lines.append("")
    (output_root / "self-audit.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run code-explainer against shipped fixtures and emit proof artifacts.")
    default_output = (Path.cwd() / ".audit_tmp" / "code-explainer-self").as_posix()
    parser.add_argument("--output-root", default=default_output)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skill-path", default="")
    args = parser.parse_args()

    output_arg = args.output_dir or args.output_root or default_output
    payload = run_self_audit(Path(output_arg).resolve())
    print(json.dumps({"passed": payload["passed"], "fixtures": len(payload["fixtures"])}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
