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


def _extract_section(markdown_text: str, heading: str) -> str:
    if not markdown_text.strip():
        return ""
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown_text, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def _copy_html_for_compact(artifact_root: Path, output_root: Path) -> str:
    html_src = artifact_root / "html" / "ONBOARDING.html"
    if not html_src.exists():
        return ""
    html_text = common.read_text(html_src)
    if not html_text.strip():
        return ""
    # Keep links usable from compact root layout.
    html_text = html_text.replace("../diagrams/", "_details/diagrams/")
    html_text = html_text.replace("../deep/", "_details/deep/")
    html_text = html_text.replace("../overview/", "_details/overview/")
    html_dst = output_root / "ONBOARDING.html"
    html_dst.write_text(html_text, encoding="utf-8")
    return "ONBOARDING.html"


def build_compact_output(output_root: Path, artifact_root: Path, source: str, analysis_type: str) -> Dict[str, Any]:
    output_root = common.ensure_dir(output_root)

    overview_text = common.read_text(artifact_root / "overview" / "OVERVIEW.md")
    what_section = _extract_section(overview_text, "What This System Is")
    map_section = _extract_section(overview_text, "Directory Map (Plain Language)")
    start_steps = _extract_section(overview_text, "If You Are PM / Designer / New Engineer, Start Here")
    if start_steps:
        start_steps = start_steps.replace("../diagrams/", "_details/diagrams/")
        start_steps = start_steps.replace("meta/", "_details/meta/")

    html_file = _copy_html_for_compact(artifact_root, output_root)

    deep_doc_paths = [
        "_details/deep/ARCHITECTURE_DEEP.md",
        "_details/deep/MODULES_DEEP.md",
        "_details/deep/FLOWS_DEEP.md",
        "_details/deep/DEPENDENCIES_DEEP.md",
        "_details/deep/GLOSSARY.md",
    ]
    deep_links = "\n".join([f"- `{path}`" for path in deep_doc_paths])

    start_here = f"""# Start Here

This output is intentionally compact for fast onboarding.

Open these files first:

1. `ONBOARDING.html` (interactive explainer){"" if html_file else " - not generated in this run"}
2. `START_HERE.md` (this quick orientation)
3. `DEEP_DIVE.md` (where to go next)

Source analyzed: `{source}`
Explainer type: `{analysis_type}`

## What This Repository Does (Plain Language)

{what_section or "Open `_details/overview/OVERVIEW.md` for the full overview."}

## Key Project Areas

{map_section or "Open `_details/overview/OVERVIEW.md` for the module map."}

## Fast Onboarding Path

{start_steps or "1. Open ONBOARDING.html\n2. Review architecture and flows in DEEP_DIVE.md\n3. Use _details for supporting evidence"}

## Full Evidence and Artifacts

All detailed outputs are in `_details/` to keep this root folder simple.
"""
    (output_root / "START_HERE.md").write_text(start_here.strip() + "\n", encoding="utf-8")

    deep_dive = f"""# Deep Dive

Use this file when you want technical depth after reading `START_HERE.md`.

Recommended order:

1. `_details/deep/ARCHITECTURE_DEEP.md`
2. `_details/deep/FLOWS_DEEP.md`
3. `_details/deep/MODULES_DEEP.md`
4. `_details/deep/DEPENDENCIES_DEEP.md`
5. `_details/deep/GLOSSARY.md`

Detailed docs:

{deep_links}

Diagram assets:

- `_details/diagrams/svg/`
- `_details/diagrams/png/`
- `_details/diagrams/*.mmd`
"""
    (output_root / "DEEP_DIVE.md").write_text(deep_dive.strip() + "\n", encoding="utf-8")

    payload = {
        "generated_at": common.now_iso(),
        "output_layout": "compact",
        "details_dir": "_details",
        "entry_files": [
            "START_HERE.md",
            "DEEP_DIVE.md",
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
