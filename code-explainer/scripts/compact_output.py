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


def _section(markdown_text: str, heading: str) -> str:
    if not markdown_text.strip():
        return ""
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown_text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _rewrite_links(text: str, details_dir: str) -> str:
    return (
        text.replace("../diagrams/", f"{details_dir}/diagrams/")
        .replace("../meta/", f"{details_dir}/meta/")
        .replace("../overview/", f"{details_dir}/overview/")
        .replace("../deep/", f"{details_dir}/deep/")
    )


def _copy_html_for_compact(artifact_root: Path, output_root: Path, details_dir: str) -> str:
    html_src = artifact_root / "html" / "ONBOARDING.html"
    if not html_src.exists():
        return ""
    html_text = common.read_text(html_src)
    if not html_text.strip():
        return ""
    html_text = html_text.replace("../diagrams/", f"{details_dir}/diagrams/")
    html_text = html_text.replace("../deep/", f"{details_dir}/deep/")
    html_text = html_text.replace("../overview/", f"{details_dir}/overview/")
    html_text = html_text.replace("../meta/", f"{details_dir}/meta/")
    html_dst = output_root / "ONBOARDING.html"
    html_dst.write_text(html_text, encoding="utf-8")
    return "ONBOARDING.html"


def build_compact_output(output_root: Path, artifact_root: Path, source: str, analysis_type: str) -> Dict[str, Any]:
    output_root = common.ensure_dir(output_root)
    details_dir = artifact_root.name

    overview_text = common.read_text(artifact_root / "overview" / "OVERVIEW.md")
    deep_text = common.read_text(artifact_root / "deep" / "SYSTEM_DEEP_DIVE.md")
    summary = _section(overview_text, "What This Repository Does") or overview_text[:700]
    fast_path = _section(overview_text, "If You Are New, Start Here")
    fast_path = _rewrite_links(fast_path, details_dir) if fast_path else ""
    lifecycle_match = re.search(r"`([^`]+)`", deep_text)
    lifecycle = lifecycle_match.group(1) if lifecycle_match else ""

    html_file = _copy_html_for_compact(artifact_root, output_root, details_dir)

    start_here_text = f"""# START HERE

This folder is intentionally simple.

Open these files in order:

1. `START_HERE.md`
2. `SYSTEM_DEEP_DIVE.md`
3. `ONBOARDING.html`{" (generated)" if html_file else " (not generated in this run)"}

Source analyzed: `{source}`
Explainer type: `{analysis_type}`

## What This Repository Does

{summary or "See the deep dive for full details."}

## One-Line Flow

`{lifecycle or "Repository intake -> Analysis -> Explainers + Diagrams"}`

## Suggested Reading Path

{fast_path or "1. Skim this file\n2. Open SYSTEM_DEEP_DIVE.md\n3. Use diagrams and HTML for visual orientation."}

## Evidence Folder

All supporting artifacts are in `{details_dir}/`:

- `{details_dir}/overview/OVERVIEW.md`
- `{details_dir}/deep/SYSTEM_DEEP_DIVE.md`
- `{details_dir}/diagrams/` (Mermaid + SVG + PNG)
- `{details_dir}/meta/` (quality, confidence, and coverage reports)
"""
    (output_root / "START_HERE.md").write_text(start_here_text.strip() + "\n", encoding="utf-8")

    system_deep_dive = _rewrite_links(deep_text, details_dir).strip()
    if not system_deep_dive:
        system_deep_dive = (
            "# System Deep Dive\n\n"
            "Deep dive content was not generated in this run. Check quality reports under "
            f"`{details_dir}/meta/quality_report.json`."
        )
    (output_root / "SYSTEM_DEEP_DIVE.md").write_text(system_deep_dive + "\n", encoding="utf-8")

    payload = {
        "generated_at": common.now_iso(),
        "output_layout": "compact",
        "details_dir": details_dir,
        "entry_files": [
            "START_HERE.md",
            "SYSTEM_DEEP_DIVE.md",
            html_file or "",
        ],
    }
    payload["entry_files"] = [f for f in payload["entry_files"] if f]
    common.write_json(artifact_root / "meta" / "compact_output.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create compact entrypoint files from detailed analysis artifacts.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--analysis-type", default="onboarding")
    args = parser.parse_args()

    payload = build_compact_output(
        output_root=Path(args.output_root).resolve(),
        artifact_root=Path(args.artifact_root).resolve(),
        source=args.source,
        analysis_type=args.analysis_type,
    )
    print(f"Compact output files: {', '.join(payload.get('entry_files', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
