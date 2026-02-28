#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


REQUIRED_OUTPUTS = [
    "overview/OVERVIEW.md",
    "deep/ARCHITECTURE_DEEP.md",
    "deep/MODULES_DEEP.md",
    "deep/FLOWS_DEEP.md",
    "deep/DEPENDENCIES_DEEP.md",
    "deep/GLOSSARY.md",
    "meta/analysis_manifest.json",
    "meta/confidence_report.json",
    "meta/source_attribution.json",
    "meta/coverage_report.json",
    "meta/llm_summary.json",
]


def _check_overview_links(output_root: Path) -> List[str]:
    errors: List[str] = []
    overview = output_root / "overview" / "OVERVIEW.md"
    text = common.read_text(overview)
    for target in re.findall(r"\]\((\.\./deep/[^)]+)\)", text):
        resolved = (overview.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"Broken deep link in overview: {target}")
    return errors


def _check_diagram_complexity(diagrams_dir: Path) -> List[str]:
    violations: List[str] = []
    for mmd in diagrams_dir.glob("*.mmd"):
        lines = common.file_line_count(mmd)
        if lines > 220:
            violations.append(f"Diagram {mmd.name} has {lines} lines and exceeds readability threshold (220).")
    return violations


def _check_claim_evidence(confidence_report: Dict[str, Any], attribution_report: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    claims = confidence_report.get("claims", [])
    attributed_claims = {item.get("claim_id", "") for item in attribution_report.get("attributions", [])}
    for claim in claims:
        evidence = claim.get("evidence_paths", [])
        claim_id = claim.get("claim_id", "")
        if not evidence and claim_id not in attributed_claims:
            errors.append(f"Claim missing evidence and attribution: {claim_id}")
    return errors


def _check_semantic_quality(output_root: Path) -> List[str]:
    warnings: List[str] = []
    entrypoints = common.read_json(output_root / "meta" / "entrypoints.json", default={})
    if int(entrypoints.get("count", 0)) == 0:
        warnings.append("No entrypoints detected; onboarding flow guidance may be incomplete.")

    coverage = common.read_json(output_root / "meta" / "coverage_report.json", default={})
    discovered = int(coverage.get("discovered_count", 0))
    parsed = int(coverage.get("parsed_count", 0))
    if discovered > 0 and parsed == 0:
        warnings.append("Documentation discovered but none parsed; overview may miss project intent from docs.")
    elif discovered >= 5 and parsed / max(discovered, 1) < 0.4:
        warnings.append("Low documentation parse coverage (<40%); review coverage_report.json for skipped reasons.")

    overview_text = common.read_text(output_root / "overview" / "OVERVIEW.md").lower()
    generic_markers = [
        "user goal",
        "need context?",
        "service layer",
        "data layer",
        "core module",
    ]
    generic_hits = [marker for marker in generic_markers if marker in overview_text]
    if len(generic_hits) >= 3:
        warnings.append(
            "Overview appears overly generic (placeholder-like phrases detected); consider deeper mode or tighter include-glob filters."
        )

    flows = common.read_json(output_root / "meta" / "flows.json", default={})
    if int(flows.get("dependency_edge_count", 0)) > 0 and not flows.get("critical_paths"):
        warnings.append("Dependency edges were found but no critical paths were extracted.")

    llm_summary = common.read_json(output_root / "meta" / "llm_summary.json", default={})
    if llm_summary.get("enabled", False) and not llm_summary.get("used", False):
        err = llm_summary.get("error", "LLM narrative was enabled but not used.")
        warnings.append(f"LLM narrative unavailable: {err}")

    return warnings


def run_quality_gate(output_root: Path, mode: str) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    for item in REQUIRED_OUTPUTS:
        path = output_root / item
        if not path.exists():
            errors.append(f"Missing required output: {item}")

    errors.extend(_check_overview_links(output_root))
    errors.extend(_check_diagram_complexity(output_root / "diagrams"))

    validation = common.read_json(output_root / "meta" / "mermaid_validation.json", default={})
    if validation and not validation.get("overall_ok", False):
        errors.append("Mermaid validation failed for one or more diagrams.")

    confidence = common.read_json(output_root / "meta" / "confidence_report.json", default={"claims": []})
    attribution = common.read_json(output_root / "meta" / "source_attribution.json", default={"attributions": []})
    errors.extend(_check_claim_evidence(confidence, attribution))
    warnings.extend(_check_semantic_quality(output_root))

    payload = {
        "checked_at": common.now_iso(),
        "mode": mode,
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
    common.write_json(output_root / "meta" / "quality_report.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run quality gates on code-explainer outputs.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()
    report = run_quality_gate(Path(args.output_root).resolve(), common.normalize_mode(args.mode))
    if report["passed"]:
        print("Quality gate passed.")
        if report["warnings"]:
            print(f"Warnings: {len(report['warnings'])}")
        return 0
    print("Quality gate failed:")
    for err in report["errors"]:
        print(f"- {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
