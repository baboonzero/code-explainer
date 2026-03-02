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


BASE_REQUIRED_OUTPUTS = [
    "meta/analysis_manifest.json",
    "meta/confidence_report.json",
    "meta/source_attribution.json",
    "meta/coverage_report.json",
    "meta/llm_summary.json",
    "meta/verification_checkpoint.json",
    "meta/fact_check_report.json",
    "meta/docs_generation.json",
]


def _required_outputs_for_format(output_format: str) -> List[str]:
    outputs = list(BASE_REQUIRED_OUTPUTS)
    if output_format in {"markdown", "both"}:
        outputs.extend(
            [
                "overview/OVERVIEW.md",
                "deep/ARCHITECTURE_DEEP.md",
                "deep/MODULES_DEEP.md",
                "deep/FLOWS_DEEP.md",
                "deep/DEPENDENCIES_DEEP.md",
                "deep/GLOSSARY.md",
            ]
        )
    if output_format in {"html", "both"}:
        outputs.extend(["html/ONBOARDING.html", "meta/html_generation.json"])
    return outputs


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


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_content_corpus(output_root: Path, output_format: str) -> str:
    chunks: List[str] = []
    if output_format in {"markdown", "both"}:
        for rel in [
            "overview/OVERVIEW.md",
            "deep/ARCHITECTURE_DEEP.md",
            "deep/MODULES_DEEP.md",
            "deep/FLOWS_DEEP.md",
            "deep/DEPENDENCIES_DEEP.md",
            "deep/GLOSSARY.md",
        ]:
            text = common.read_text(output_root / rel)
            if text:
                chunks.append(text)
    if output_format in {"html", "both"}:
        html_text = common.read_text(output_root / "html" / "ONBOARDING.html")
        if html_text:
            chunks.append(_strip_html(html_text))
    return "\n".join(chunks).lower()


def _check_content_completeness(output_root: Path, output_format: str) -> Dict[str, Any]:
    index_payload = common.read_json(output_root / "meta" / "index.json", default={})
    flow_payload = common.read_json(output_root / "meta" / "flows.json", default={})
    corpus = _build_content_corpus(output_root, output_format)

    modules = index_payload.get("modules", [])
    major_modules = [
        m.get("name", "")
        for m in modules
        if m.get("name") and m.get("name") != "(root-files)" and int(m.get("file_count", 0)) >= 2
    ][:10]
    if not major_modules:
        major_modules = [m.get("name", "") for m in modules if m.get("name")][:6]

    module_results = []
    represented_modules = 0
    for module_name in major_modules:
        present = module_name.lower() in corpus if module_name else False
        module_results.append({"module": module_name, "represented": present})
        if present:
            represented_modules += 1

    primary_flow_steps = flow_payload.get("primary_user_flow", {}).get("steps", [])
    if not primary_flow_steps:
        primary_flow_steps = flow_payload.get("request_lifecycle", [])
    major_flows = [str(step).strip() for step in primary_flow_steps if str(step).strip()][:8]
    flow_results = []
    represented_flows = 0
    for step in major_flows:
        present = step.lower() in corpus
        flow_results.append({"step": step, "represented": present})
        if present:
            represented_flows += 1

    module_ratio = represented_modules / max(len(major_modules), 1)
    flow_ratio = represented_flows / max(len(major_flows), 1) if major_flows else 1.0

    payload = {
        "checked_at": common.now_iso(),
        "output_format": output_format,
        "major_module_count": len(major_modules),
        "represented_module_count": represented_modules,
        "module_representation_ratio": round(module_ratio, 3),
        "module_results": module_results,
        "major_flow_count": len(major_flows),
        "represented_flow_count": represented_flows,
        "flow_representation_ratio": round(flow_ratio, 3),
        "flow_results": flow_results,
    }
    common.write_json(output_root / "meta" / "content_completeness.json", payload)
    return payload


def _check_semantic_quality(output_root: Path, output_format: str, analysis_type: str) -> Dict[str, List[str]]:
    errors: List[str] = []
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

    if output_format in {"markdown", "both"}:
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

    fact_report = common.read_json(output_root / "meta" / "fact_check_report.json", default={})
    if fact_report and not fact_report.get("passed", False):
        errors.append(
            f"Fact-check failed with {fact_report.get('mismatch_count', 0)} mismatches in generated explainers."
        )

    completeness = _check_content_completeness(output_root, output_format)
    module_ratio = float(completeness.get("module_representation_ratio", 0.0))
    flow_ratio = float(completeness.get("flow_representation_ratio", 0.0))
    if completeness.get("major_module_count", 0) > 0:
        if module_ratio < 0.35:
            errors.append(
                f"Content completeness failed: only {completeness.get('represented_module_count', 0)}/"
                f"{completeness.get('major_module_count', 0)} major modules represented."
            )
        elif module_ratio < 0.6:
            warnings.append(
                f"Low module representation in output ({completeness.get('represented_module_count', 0)}/"
                f"{completeness.get('major_module_count', 0)})."
            )
    if completeness.get("major_flow_count", 0) > 0:
        if flow_ratio <= 0.0:
            errors.append("Content completeness failed: no major flow steps represented in outputs.")
        elif flow_ratio < 0.6:
            warnings.append(
                f"Low flow-step representation in output ({completeness.get('represented_flow_count', 0)}/"
                f"{completeness.get('major_flow_count', 0)})."
            )

    mode_keywords = {
        "project-recap": ["project recap", "recent activity"],
        "plan-review": ["plan", "risk"],
        "diff-review": ["diff", "changed"],
    }
    corpus = _build_content_corpus(output_root, output_format)
    expected_tokens = mode_keywords.get(analysis_type, [])
    if expected_tokens and not all(token in corpus for token in expected_tokens):
        warnings.append(
            f"Mode-specific framing appears weak for {analysis_type}; expected tokens not all present."
        )

    return {"errors": errors, "warnings": warnings}


def run_quality_gate(
    output_root: Path,
    mode: str,
    output_format: str = "markdown",
    analysis_type: str = "onboarding",
) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    required = _required_outputs_for_format(output_format)
    for item in required:
        path = output_root / item
        if not path.exists():
            errors.append(f"Missing required output: {item}")

    if output_format in {"markdown", "both"}:
        errors.extend(_check_overview_links(output_root))
    errors.extend(_check_diagram_complexity(output_root / "diagrams"))

    validation = common.read_json(output_root / "meta" / "mermaid_validation.json", default={})
    if validation and not validation.get("overall_ok", False):
        errors.append("Mermaid validation failed for one or more diagrams.")

    confidence = common.read_json(output_root / "meta" / "confidence_report.json", default={"claims": []})
    attribution = common.read_json(output_root / "meta" / "source_attribution.json", default={"attributions": []})
    errors.extend(_check_claim_evidence(confidence, attribution))

    semantic = _check_semantic_quality(output_root, output_format, analysis_type)
    errors.extend(semantic["errors"])
    warnings.extend(semantic["warnings"])

    payload = {
        "checked_at": common.now_iso(),
        "mode": mode,
        "output_format": output_format,
        "analysis_type": analysis_type,
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
    parser.add_argument("--output-format", default="markdown")
    parser.add_argument("--analysis-type", default="onboarding")
    args = parser.parse_args()
    report = run_quality_gate(
        output_root=Path(args.output_root).resolve(),
        mode=common.normalize_mode(args.mode),
        output_format=args.output_format,
        analysis_type=args.analysis_type,
    )
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
