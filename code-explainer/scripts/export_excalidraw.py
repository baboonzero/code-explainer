#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _copy_if_exists(source: Path, dest: Path) -> bool:
    if not source.exists():
        return False
    common.ensure_dir(dest.parent)
    shutil.copy2(source, dest)
    return True


def _runtime_status() -> Dict[str, Any]:
    node = common.which("node")
    bridge = SCRIPT_DIR / "mermaid_to_excalidraw.mjs"
    package_dir = SKILL_DIR / "node_modules" / "@excalidraw" / "mermaid-to-excalidraw"
    package_json = SKILL_DIR / "package.json"

    issues: List[str] = []
    if not node:
        issues.append("Node.js was not found on PATH.")
    if not bridge.exists():
        issues.append("The Mermaid-to-Excalidraw bridge script is missing.")
    if not package_json.exists():
        issues.append("package.json is missing from the skill runtime.")
    if not package_dir.exists():
        issues.append("The @excalidraw/mermaid-to-excalidraw package is not installed.")

    return {
        "ok": len(issues) == 0,
        "node": node or "",
        "bridge": bridge.as_posix(),
        "package_dir": package_dir.as_posix(),
        "issues": issues,
    }


def _scene_root() -> Dict[str, Any]:
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://github.com/openai/code-explainer",
        "elements": [],
        "appState": {
            "viewBackgroundColor": "#ffffff",
            "gridSize": None,
            "theme": "light",
        },
        "files": {},
    }


def _new_id(prefix: str, counter: int) -> str:
    return f"{prefix}_{counter}"


def _estimate_text_box(text: str, font_size: int = 20) -> Tuple[float, float]:
    lines = [line for line in str(text).split("\\n")] or [""]
    max_chars = max(len(line) for line in lines)
    width = max(120.0, min(420.0, max_chars * (font_size * 0.62)))
    height = max(36.0, len(lines) * (font_size * 1.4))
    return round(width, 1), round(height, 1)


def _base_style() -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "angle": 0,
        "strokeColor": "#1f2937",
        "backgroundColor": "#f8fafc",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": random.randint(1, 2_000_000_000),
        "version": 1,
        "versionNonce": random.randint(1, 2_000_000_000),
        "isDeleted": False,
        "boundElements": None,
        "updated": now_ms,
        "link": None,
        "locked": False,
    }


def _rectangle_element(element_id: str, x: float, y: float, width: float, height: float, accent: str = "#2563eb") -> Dict[str, Any]:
    payload = _base_style()
    payload.update(
        {
            "id": element_id,
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "strokeColor": accent,
            "backgroundColor": "#f8fbff",
        }
    )
    return payload


def _text_element(element_id: str, x: float, y: float, text: str, font_size: int = 20) -> Dict[str, Any]:
    width, height = _estimate_text_box(text, font_size=font_size)
    baseline = max(18, int(font_size * 0.8))
    payload = _base_style()
    payload.update(
        {
            "id": element_id,
            "type": "text",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "strokeColor": "#111827",
            "backgroundColor": "transparent",
            "strokeWidth": 1,
            "roughness": 0,
            "text": text,
            "fontSize": font_size,
            "fontFamily": 1,
            "textAlign": "center",
            "verticalAlign": "middle",
            "containerId": None,
            "originalText": text,
            "lineHeight": 1.25,
            "baseline": baseline,
        }
    )
    payload["roundness"] = None
    return payload


def _arrow_element(element_id: str, x: float, y: float, dx: float, dy: float, accent: str = "#475569") -> Dict[str, Any]:
    payload = _base_style()
    payload.update(
        {
            "id": element_id,
            "type": "arrow",
            "x": x,
            "y": y,
            "width": dx,
            "height": dy,
            "strokeColor": accent,
            "backgroundColor": "transparent",
            "points": [[0, 0], [dx, dy]],
            "startBinding": None,
            "endBinding": None,
            "lastCommittedPoint": None,
            "startArrowhead": None,
            "endArrowhead": "arrow",
            "elbowed": False,
        }
    )
    payload["roundness"] = None
    return payload


def _clean_label(label: str) -> str:
    text = str(label or "").strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    return text.replace('\\"', '"')


def _parse_flowchart(source: str) -> Tuple[Dict[str, str], List[Tuple[str, str, str]], str]:
    lines = [line.rstrip() for line in source.splitlines() if line.strip()]
    direction = "TD"
    if lines:
        header = lines[0].strip()
        parts = header.split()
        if len(parts) >= 2 and parts[0] in {"flowchart", "graph"}:
            direction = parts[1]

    nodes: Dict[str, str] = {}
    edges: List[Tuple[str, str, str]] = []
    for raw in lines[1:]:
        line = raw.strip()
        if line.startswith("%%"):
            continue
        if "[" in line and "]" in line and "--" not in line and "->" not in line:
            node_id = line.split("[", 1)[0].strip()
            label = line.split("[", 1)[1].rsplit("]", 1)[0]
            label = label.strip().strip('"')
            nodes[node_id] = label
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        src = parts[0]
        dst = parts[-1]
        middle = " ".join(parts[1:-1]).strip()
        if not any(token in middle for token in ["-->", ".->", "-.->", "==>", "---->"]):
            continue
        label = ""
        if "|" in middle:
            bits = middle.split("|")
            if len(bits) >= 3:
                label = _clean_label(bits[1])
        elif middle.startswith("-.") and middle.endswith(".->"):
            label = _clean_label(middle[2:-3])
        if src not in nodes:
            nodes[src] = src
        if dst not in nodes:
            nodes[dst] = dst
        edges.append((src, dst, label))
    return nodes, edges, direction


def _parse_sequence(source: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str]]]:
    participants: List[Tuple[str, str]] = []
    messages: List[Tuple[str, str, str]] = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line == "sequenceDiagram":
            continue
        if line.startswith("participant "):
            tail = line[len("participant ") :]
            if " as " in tail:
                token, label = tail.split(" as ", 1)
                participants.append((token.strip(), _clean_label(label.strip())))
            else:
                participants.append((tail.strip(), tail.strip()))
            continue
        if ":" in line and "->" in line:
            left, message = line.split(":", 1)
            if "->>" in left:
                src, dst = left.split("->>", 1)
            elif "-->" in left:
                src, dst = left.split("-->", 1)
            else:
                continue
            messages.append((src.strip(), dst.strip(), message.strip()))
    return participants, messages


def _flowchart_scene(title: str, source: str) -> Dict[str, Any]:
    nodes, edges, direction = _parse_flowchart(source)
    scene = _scene_root()
    elements: List[Dict[str, Any]] = []
    node_positions: Dict[str, Tuple[float, float, float, float]] = {}
    horizontal = direction.upper() in {"LR", "RL"}
    spacing_x = 300.0
    spacing_y = 170.0
    base_x = 120.0
    base_y = 140.0
    ordered_nodes = list(nodes.items())

    for index, (node_id, label) in enumerate(ordered_nodes, start=1):
        width, height = _estimate_text_box(label)
        x = base_x + (index - 1) * spacing_x if horizontal else base_x + ((index - 1) % 2) * spacing_x
        y = base_y + ((index - 1) % 2) * spacing_y if horizontal else base_y + (index - 1) * spacing_y
        if horizontal and len(ordered_nodes) > 4:
            x = base_x + ((index - 1) % 3) * spacing_x
            y = base_y + math.floor((index - 1) / 3) * spacing_y
        rect_id = _new_id("rect", index)
        text_id = _new_id("text", index)
        elements.append(_rectangle_element(rect_id, x, y, width, height, accent="#2563eb"))
        elements.append(_text_element(text_id, x + 16, y + 14, label, font_size=20))
        node_positions[node_id] = (x, y, width, height)

    for index, (src, dst, label) in enumerate(edges, start=1):
        if src not in node_positions or dst not in node_positions:
            continue
        sx, sy, sw, sh = node_positions[src]
        dx, dy, dw, dh = node_positions[dst]
        start_x = sx + sw / 2
        start_y = sy + sh / 2
        end_x = dx + dw / 2
        end_y = dy + dh / 2
        elements.append(_arrow_element(_new_id("arrow", index), start_x, start_y, end_x - start_x, end_y - start_y))
        if label:
            mid_x = start_x + ((end_x - start_x) / 2) - 90
            mid_y = start_y + ((end_y - start_y) / 2) - 18
            elements.append(_text_element(_new_id("edge_label", index), mid_x, mid_y, label, font_size=16))

    scene["appState"]["name"] = title
    scene["elements"] = elements
    return scene


def _sequence_scene(title: str, source: str) -> Dict[str, Any]:
    participants, messages = _parse_sequence(source)
    scene = _scene_root()
    elements: List[Dict[str, Any]] = []
    participant_positions: Dict[str, Tuple[float, float]] = {}
    base_x = 140.0
    header_y = 90.0
    spacing_x = 260.0
    for index, (token, label) in enumerate(participants, start=1):
        x = base_x + (index - 1) * spacing_x
        rect_id = _new_id("participant_rect", index)
        text_id = _new_id("participant_text", index)
        elements.append(_rectangle_element(rect_id, x, header_y, 190.0, 70.0, accent="#0f766e"))
        elements.append(_text_element(text_id, x + 12, header_y + 16, label, font_size=18))
        participant_positions[token] = (x + 95.0, header_y + 70.0)
        lifeline = _arrow_element(_new_id("lifeline", index), x + 95.0, header_y + 78.0, 0.0, 520.0, accent="#94a3b8")
        lifeline["endArrowhead"] = None
        lifeline["strokeStyle"] = "dashed"
        elements.append(lifeline)

    for index, (src, dst, label) in enumerate(messages, start=1):
        if src not in participant_positions or dst not in participant_positions:
            continue
        start_x, _ = participant_positions[src]
        end_x, _ = participant_positions[dst]
        y = header_y + 120.0 + (index - 1) * 88.0
        elements.append(_arrow_element(_new_id("message", index), start_x, y, end_x - start_x, 0.0, accent="#475569"))
        elements.append(_text_element(_new_id("message_text", index), min(start_x, end_x) + 20.0, y - 28.0, label, font_size=16))

    scene["appState"]["name"] = title
    scene["elements"] = elements
    return scene


def _fallback_scene(title: str, source: str) -> Dict[str, Any]:
    stripped = source.strip()
    if stripped.startswith("sequenceDiagram"):
        return _sequence_scene(title, source)
    return _flowchart_scene(title, source)


def _write_scene(path: Path, scene: Dict[str, Any]) -> None:
    common.ensure_dir(path.parent)
    path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")


def export_excalidraw(
    diagrams_dir: Path,
    rendered_diagrams_dir: Path,
    meta_dir: Path,
    enabled: bool = True,
) -> Dict[str, Any]:
    scene_dir = common.ensure_dir(rendered_diagrams_dir / "excalidraw")
    svg_dir = common.ensure_dir(scene_dir / "svg")
    png_dir = common.ensure_dir(scene_dir / "png")
    report_path = meta_dir / "excalidraw_report.json"

    if not enabled:
        payload = {
            "generated_at": common.now_iso(),
            "requested": False,
            "status": "disabled",
            "environment_blocked": False,
            "scene_count": 0,
            "failed_count": 0,
            "results": [],
            "warnings": ["Excalidraw export disabled by caller."],
        }
        common.write_json(report_path, payload)
        return payload

    runtime = _runtime_status()
    results: List[Dict[str, Any]] = []
    scene_count = 0
    failed_count = 0
    renderer_svg_dir = rendered_diagrams_dir / "svg"
    renderer_png_dir = rendered_diagrams_dir / "png"

    for index, mmd_path in enumerate(sorted(diagrams_dir.glob("*.mmd")), start=1):
        stem = mmd_path.stem
        scene_path = scene_dir / f"{stem}.excalidraw.json"
        preview_svg = svg_dir / f"{stem}.svg"
        preview_png = png_dir / f"{stem}.png"
        source = common.read_text(mmd_path)

        entry: Dict[str, Any] = {
            "diagram": mmd_path.name,
            "scene": scene_path.relative_to(rendered_diagrams_dir).as_posix(),
            "preview_svg": preview_svg.relative_to(rendered_diagrams_dir).as_posix(),
            "preview_png": preview_png.relative_to(rendered_diagrams_dir).as_posix(),
            "status": "failed",
            "warnings": [],
            "errors": [],
            "element_count": 0,
            "file_count": 0,
            "preview_strategy": "copied-mermaid-render",
            "exporter": "",
        }

        bridge_error = ""
        if runtime["ok"]:
            code, stdout, stderr = common.run_cmd(
                [
                    runtime["node"],
                    str(Path("scripts") / "mermaid_to_excalidraw.mjs"),
                    "--input",
                    str(mmd_path),
                    "--output",
                    str(scene_path),
                    "--title",
                    stem.replace("_", " ").title(),
                ],
                cwd=SKILL_DIR,
                timeout=90,
            )
            if code == 0 and scene_path.exists():
                payload = common.read_json(scene_path, default={})
                entry["status"] = "ok"
                entry["exporter"] = "official-bridge"
                entry["element_count"] = len(payload.get("elements", []))
                entry["file_count"] = len(payload.get("files", {}))
                if stdout.strip():
                    try:
                        bridge_payload = json.loads(stdout)
                        entry["element_count"] = int(bridge_payload.get("elementCount", entry["element_count"]))
                        entry["file_count"] = int(bridge_payload.get("fileCount", entry["file_count"]))
                    except json.JSONDecodeError:
                        entry["warnings"].append("Bridge output was not valid JSON; the scene file was still created.")
            else:
                bridge_error = stderr.strip() or stdout.strip() or "The official Mermaid-to-Excalidraw bridge failed."
                entry["warnings"].append("Fell back to the local Excalidraw scene generator.")

        if entry["status"] != "ok":
            try:
                fallback = _fallback_scene(stem.replace("_", " ").title(), source)
                _write_scene(scene_path, fallback)
                entry["status"] = "ok"
                entry["exporter"] = "python-fallback"
                entry["element_count"] = len(fallback.get("elements", []))
                entry["file_count"] = len(fallback.get("files", {}))
                if bridge_error:
                    entry["warnings"].append(bridge_error)
                if not runtime["ok"]:
                    entry["warnings"].extend(runtime["issues"])
            except Exception as exc:
                failed_count += 1
                entry["status"] = "failed"
                entry["errors"].append(str(exc))
                if bridge_error:
                    entry["errors"].append(bridge_error)

        if entry["status"] == "ok":
            scene_count += 1

        svg_copied = _copy_if_exists(renderer_svg_dir / f"{stem}.svg", preview_svg)
        png_copied = _copy_if_exists(renderer_png_dir / f"{stem}.png", preview_png)
        if not svg_copied or not png_copied:
            entry["preview_strategy"] = "missing-mermaid-preview"
            entry["warnings"].append("Mermaid preview assets were unavailable for Excalidraw preview copy.")

        results.append(entry)

    status = "ok"
    if failed_count > 0:
        status = "partial" if scene_count > 0 else "failed"

    warnings: List[str] = []
    if not runtime["ok"]:
        warnings.append("Official Excalidraw bridge runtime unavailable; used the local deterministic scene generator.")
        warnings.extend(runtime["issues"])

    payload = {
        "generated_at": common.now_iso(),
        "requested": True,
        "status": status,
        "environment_blocked": False,
        "scene_count": scene_count,
        "failed_count": failed_count,
        "results": results,
        "warnings": warnings,
        "runtime": runtime,
    }
    common.write_json(report_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Mermaid diagrams to editable Excalidraw scenes.")
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--rendered-diagrams-dir", required=True)
    parser.add_argument("--meta-dir", required=True)
    parser.add_argument("--enabled", default="true")
    args = parser.parse_args()

    payload = export_excalidraw(
        diagrams_dir=Path(args.diagrams_dir).resolve(),
        rendered_diagrams_dir=Path(args.rendered_diagrams_dir).resolve(),
        meta_dir=Path(args.meta_dir).resolve(),
        enabled=common.bool_from_string(args.enabled),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "scene_count": payload["scene_count"],
                "failed_count": payload["failed_count"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
