#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


PNG_PLACEHOLDER_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgJfug7sAAAAASUVORK5CYII="
)


def _fallback_svg(diagram_name: str, mermaid_text: str) -> str:
    escaped = html.escape(mermaid_text[:2000])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900">
<rect width="100%" height="100%" fill="#0b1020"/>
<text x="40" y="60" fill="#ffffff" font-size="26" font-family="Arial">Fallback Render: {html.escape(diagram_name)}</text>
<text x="40" y="100" fill="#9bb1ff" font-size="16" font-family="Courier New">mmdc not available; showing Mermaid source excerpt.</text>
<foreignObject x="40" y="130" width="1320" height="740">
  <pre xmlns="http://www.w3.org/1999/xhtml" style="color:#d8e0ff;font-size:14px;white-space:pre-wrap;font-family:Consolas,monospace;">{escaped}</pre>
</foreignObject>
</svg>
"""


def render_diagrams(diagrams_dir: Path, output_dir: Path, theme: str = "neutral") -> Dict[str, Any]:
    svg_dir = common.ensure_dir(output_dir / "svg")
    png_dir = common.ensure_dir(output_dir / "png")
    mmdc = common.which("mmdc")

    results: List[Dict[str, Any]] = []
    config_path = ""
    temp_dir = None
    if mmdc:
        temp_dir = tempfile.TemporaryDirectory(prefix="code_explainer_mmdc_")
        config_path = str(Path(temp_dir.name) / "mermaid-render-config.json")
        config_payload = {
            "themeVariables": {
                "fontFamily": "IBM Plex Sans, Segoe UI, Arial",
                "fontSize": "16px",
                "lineColor": "#334155",
                "primaryTextColor": "#111827",
                "primaryBorderColor": "#334155",
                "primaryColor": "#f8fafc",
            },
            "flowchart": {"nodeSpacing": 55, "rankSpacing": 75, "curve": "basis"},
            "sequence": {
                "diagramMarginX": 40,
                "diagramMarginY": 24,
                "actorMargin": 70,
                "width": 180,
                "height": 76,
            },
        }
        Path(config_path).write_text(json.dumps(config_payload), encoding="utf-8")
    try:
        for mmd_path in sorted(diagrams_dir.glob("*.mmd")):
            base = mmd_path.stem
            svg_path = svg_dir / f"{base}.svg"
            png_path = png_dir / f"{base}.png"
            entry = {"diagram": mmd_path.name, "svg": svg_path.name, "png": png_path.name, "renderer": "", "ok": True, "errors": []}
            if mmdc:
                # White background + larger default typography/layout for cleaner onboarding visuals.
                svg_cmd = [mmdc, "-i", str(mmd_path), "-o", str(svg_path), "-t", theme, "-b", "white", "-s", "1.4", "-C", config_path]
                png_cmd = [mmdc, "-i", str(mmd_path), "-o", str(png_path), "-t", theme, "-b", "white", "-w", "2200", "-H", "1500", "-s", "1.4", "-C", config_path]
                code_svg, _out_svg, err_svg = common.run_cmd(svg_cmd, timeout=90)
                code_png, _out_png, err_png = common.run_cmd(png_cmd, timeout=90)
                entry["renderer"] = "mmdc"
                if code_svg != 0 or code_png != 0:
                    entry["ok"] = False
                    if err_svg.strip():
                        entry["errors"].append(err_svg.strip())
                    if err_png.strip():
                        entry["errors"].append(err_png.strip())
            else:
                source = common.read_text(mmd_path)
                svg_path.write_text(_fallback_svg(base, source), encoding="utf-8")
                png_path.write_bytes(base64.b64decode(PNG_PLACEHOLDER_B64))
                entry["renderer"] = "fallback"
                entry["errors"].append("mmdc not installed; used fallback renderers")
            results.append(entry)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    payload = {
        "rendered_at": common.now_iso(),
        "renderer": "mmdc" if mmdc else "fallback",
        "theme": theme,
        "results": results,
        "rendered_count": len(results),
    }
    common.write_json(output_dir.parent / "meta" / "render_report.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Mermaid diagrams to SVG and PNG.")
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--theme", default="neutral")
    args = parser.parse_args()

    payload = render_diagrams(Path(args.diagrams_dir).resolve(), Path(args.output_dir).resolve(), args.theme)
    failed = [r for r in payload["results"] if not r["ok"]]
    if failed:
        print(f"Rendered with {len(failed)} error(s)")
        return 1
    print(f"Rendered {payload['rendered_count']} diagram(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
