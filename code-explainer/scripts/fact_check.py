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


def _load_markdown_corpus(output_root: Path) -> str:
    paths = [
        output_root / "overview" / "OVERVIEW.md",
        output_root / "deep" / "ARCHITECTURE_DEEP.md",
        output_root / "deep" / "MODULES_DEEP.md",
        output_root / "deep" / "FLOWS_DEEP.md",
        output_root / "deep" / "DEPENDENCIES_DEEP.md",
        output_root / "deep" / "GLOSSARY.md",
    ]
    chunks: List[str] = []
    for path in paths:
        text = common.read_text(path)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


def _load_html_corpus(output_root: Path) -> str:
    html_path = output_root / "html" / "ONBOARDING.html"
    text = common.read_text(html_path)
    if not text:
        return ""
    # Strip tags for simpler matching.
    stripped = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped


def _token_match(text: str, tokens: List[str]) -> bool:
    lowered = text.lower()
    for token in tokens:
        t = str(token or "").strip().lower()
        if not t:
            continue
        if t not in lowered:
            return False
    return True


def run_fact_check(
    output_root: Path,
    output_format: str,
    analysis_type: str,
    verification_payload: Dict[str, Any],
) -> Dict[str, Any]:
    corpus_chunks: List[str] = []
    if output_format in {"markdown", "both"}:
        corpus_chunks.append(_load_markdown_corpus(output_root))
    if output_format in {"html", "both"}:
        corpus_chunks.append(_load_html_corpus(output_root))
    corpus = "\n".join([c for c in corpus_chunks if c]).strip()

    checks: List[Dict[str, Any]] = []
    advisory_checks: List[Dict[str, Any]] = []
    confirmed = 0
    mismatches = 0
    for fact in verification_payload.get("facts", []):
        claim_id = fact.get("claim_id", "")
        tokens = [str(x) for x in fact.get("must_include_tokens", []) if str(x).strip()]
        if not tokens:
            tokens = [str(fact.get("expected_text", "")).strip()]
        ok = _token_match(corpus, tokens) if corpus else False
        checks.append(
            {
                "claim_id": claim_id,
                "expected_text": fact.get("expected_text", ""),
                "tokens": tokens,
                "matched": ok,
            }
        )
        if ok:
            confirmed += 1
        else:
            mismatches += 1

    required_mode_sections = {
        "project-recap": ["project recap", "recent activity"],
        "plan-review": ["plan", "risk"],
        "diff-review": ["diff", "changed", "review"],
    }
    mode_tokens = required_mode_sections.get(analysis_type, [])
    mode_section_ok = _token_match(corpus, mode_tokens) if mode_tokens else True
    if mode_tokens:
        advisory_checks.append(
            {
                "claim_id": "mode_specific_sections",
                "expected_text": f"Mode-specific tokens for {analysis_type}: {', '.join(mode_tokens)}",
                "tokens": mode_tokens,
                "matched": mode_section_ok,
            }
        )

    payload = {
        "checked_at": common.now_iso(),
        "output_format": output_format,
        "analysis_type": analysis_type,
        "fact_count": len(verification_payload.get("facts", [])),
        "confirmed_count": confirmed,
        "mismatch_count": mismatches,
        "passed": mismatches == 0,
        "checks": checks,
        "advisory_checks": advisory_checks,
    }
    common.write_json(output_root / "meta" / "fact_check_report.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Fact-check generated explainers against verification checkpoint.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--output-format", default="markdown")
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--verification", required=True)
    args = parser.parse_args()

    payload = run_fact_check(
        output_root=Path(args.output_root).resolve(),
        output_format=args.output_format,
        analysis_type=args.analysis_type,
        verification_payload=common.read_json(Path(args.verification), default={}),
    )
    print(json.dumps({"passed": payload["passed"], "mismatch_count": payload["mismatch_count"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
