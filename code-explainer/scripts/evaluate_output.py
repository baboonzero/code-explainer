#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _read_docs(output_root: Path) -> Dict[str, str]:
    files = {
        "overview": output_root / "overview" / "OVERVIEW.md",
        "architecture": output_root / "deep" / "ARCHITECTURE_DEEP.md",
        "modules": output_root / "deep" / "MODULES_DEEP.md",
        "flows": output_root / "deep" / "FLOWS_DEEP.md",
    }
    return {name: common.read_text(path) for name, path in files.items()}


def _sentences(text: str) -> List[str]:
    return [item.strip() for item in re.split(r"[.!?]\s+", text) if item.strip()]


def _avg_sentence_length(text: str) -> float:
    sentences = _sentences(text)
    if not sentences:
        return 0.0
    word_counts = [len(re.findall(r"\b\w+\b", item)) for item in sentences]
    return sum(word_counts) / max(len(word_counts), 1)


def _count_matches(text: str, needles: List[str]) -> int:
    lowered = text.lower()
    return sum(1 for item in needles if str(item).strip() and str(item).lower() in lowered)


def evaluate_output(output_root: Path, audience: str, analysis_type: str) -> Dict[str, Any]:
    docs = _read_docs(output_root)
    corpus = "\n".join(docs.values())
    lowered = corpus.lower()

    plan_payload = common.read_json(output_root / "meta" / "explanation_plan.json", default={})
    llm_payload = common.read_json(output_root / "meta" / "llm_summary.json", default={})
    diagram_manifest = common.read_json(output_root / "meta" / "diagram_manifest.json", default={})
    entry_payload = common.read_json(output_root / "meta" / "entrypoints.json", default={})

    required_headings = [
        "what this repository does",
        "how the codebase is organized",
        "core request or product flow",
        "where to start",
        "caveats and confidence",
    ]
    required_hits = _count_matches(docs.get("overview", ""), required_headings)
    structure_score = 100.0 * (required_hits / len(required_headings))

    generic_phrases = [
        "core module",
        "service layer",
        "data layer",
        "user goal",
        "stakeholders",
        "this output prioritizes",
    ]
    generic_hits = _count_matches(lowered, generic_phrases)
    avg_sentence = _avg_sentence_length(docs.get("overview", ""))
    clarity_score = 100.0
    if avg_sentence > 28:
        clarity_score -= min(25.0, (avg_sentence - 28) * 2.5)
    clarity_score -= min(25.0, generic_hits * 8.0)

    top_modules = [item.get("name", "") for item in plan_payload.get("top_modules", []) if item.get("name")]
    module_hits = _count_matches(lowered, top_modules[:6])
    module_score = 100.0 if not top_modules else 100.0 * (module_hits / max(min(len(top_modules), 6), 1))

    entrypoints = [item.get("path", "") for item in entry_payload.get("entrypoints", []) if item.get("path")]
    entry_score = 100.0 if not entrypoints else 100.0 * (1.0 if entrypoints[0].lower() in lowered else 0.0)

    flow_steps = [str(item).strip() for item in plan_payload.get("primary_flow_steps", []) if str(item).strip()]
    flow_hits = _count_matches(lowered, flow_steps[:5])
    flow_score = 100.0 if not flow_steps else 100.0 * (flow_hits / max(min(len(flow_steps), 5), 1))

    grounding_signals = len(re.findall(r"`[^`/]+/[^`]+`", corpus)) + len(re.findall(r"`[^`]+\.[A-Za-z0-9]+`", corpus))
    grounding_score = min(100.0, grounding_signals * 15.0)
    if "evidence" in lowered:
        grounding_score = min(100.0, grounding_score + 15.0)

    diagram_ids = [item.get("id", "") for item in diagram_manifest.get("diagrams", []) if item.get("id")]
    diagram_hits = _count_matches(lowered, diagram_ids[:6])
    diagram_score = 100.0 if not diagram_ids else 100.0 * (diagram_hits / max(min(len(diagram_ids), 6), 1))

    usefulness_hits = _count_matches(lowered, ["where to start", "safe change guidance", "diagram guide", "evidence used"])
    usefulness_score = 100.0 * (usefulness_hits / 4.0)

    caveats = llm_payload.get("caveats", []) or plan_payload.get("caveats", [])
    honesty_score = 100.0 if caveats else 55.0
    if llm_payload.get("enabled", False) and not llm_payload.get("used", False):
        honesty_score = max(0.0, honesty_score - 20.0)

    dimensions = {
        "structure": round(structure_score, 1),
        "clarity": round(max(0.0, clarity_score), 1),
        "specificity": round((module_score + entry_score + flow_score) / 3.0, 1),
        "grounding": round(min(100.0, grounding_score), 1),
        "diagram_usefulness": round(diagram_score, 1),
        "usefulness": round(usefulness_score, 1),
        "honesty": round(honesty_score, 1),
    }
    total = round(sum(dimensions.values()) / len(dimensions), 1)
    failures = [name for name, value in dimensions.items() if value < 60.0]
    payload = {
        "evaluated_at": common.now_iso(),
        "audience": audience,
        "analysis_type": analysis_type,
        "dimensions": dimensions,
        "score": total,
        "passed": total >= 80.0 and not failures,
        "failures": failures,
        "generic_phrase_hits": generic_hits,
        "avg_overview_sentence_length": round(avg_sentence, 1),
    }
    common.write_json(output_root / "meta" / "explanation_quality.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate generated explainers for clarity, specificity, and grounding.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--analysis-type", default="onboarding")
    args = parser.parse_args()

    payload = evaluate_output(Path(args.output_root).resolve(), args.audience, args.analysis_type)
    print(json.dumps({"score": payload["score"], "passed": payload["passed"], "failures": payload["failures"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
