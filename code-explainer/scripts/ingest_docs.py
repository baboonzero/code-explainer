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


DOC_HINT_TOKENS = {
    "readme",
    "setup",
    "install",
    "onboarding",
    "architecture",
    "design",
    "contributing",
    "guide",
    "local_setup",
    "runbook",
    "howto",
    "getting-started",
}


def _is_doc_candidate(path: str) -> bool:
    lower = path.lower()
    name = Path(path).name.lower()
    if lower.startswith("docs/") and lower.endswith((".md", ".mdx", ".rst")):
        return True
    if lower.endswith((".md", ".mdx", ".rst")) and any(token in name for token in DOC_HINT_TOKENS):
        return True
    if name in {"changelog.md", "architecture.md", "contributing.md"}:
        return True
    return False


def _extract_summary(text: str, max_chars: int) -> str:
    cleaned_lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "```", "<!--", "|", "-", "*", ">")):
            continue
        if re.match(r"^\d+\.\s+", stripped):
            continue
        cleaned_lines.append(stripped)
        if len(" ".join(cleaned_lines)) >= max_chars:
            break
    if not cleaned_lines:
        return ""
    joined = " ".join(cleaned_lines)
    if len(joined) > max_chars:
        joined = joined[: max_chars - 1].rstrip() + "..."
    return joined


def _extract_headings(text: str, limit: int = 8) -> List[str]:
    headings = re.findall(r"^\s{0,3}#{1,3}\s+(.+?)\s*$", text, flags=re.MULTILINE)
    return [h.strip() for h in headings[:limit] if h.strip()]


def _doc_limit_for_mode(mode: str) -> int:
    if mode == "quick":
        return 15
    if mode == "deep":
        return 80
    return 40


def _summary_len_for_mode(mode: str) -> int:
    if mode == "quick":
        return 220
    if mode == "deep":
        return 700
    return 420


def ingest_docs(repo_root: Path, index_payload: Dict[str, Any], out_dir: Path, mode: str) -> Dict[str, Any]:
    files = index_payload.get("files", [])
    discovered = sorted([item["path"] for item in files if _is_doc_candidate(item.get("path", ""))])

    max_docs = _doc_limit_for_mode(mode)
    max_summary_chars = _summary_len_for_mode(mode)
    max_doc_bytes = 600_000

    parsed_docs: List[Dict[str, Any]] = []
    skipped_docs: List[Dict[str, str]] = []

    for idx, rel in enumerate(discovered):
        if idx >= max_docs:
            skipped_docs.append({"path": rel, "reason": "bounded_by_mode_limit"})
            continue
        abs_path = repo_root / rel
        if not abs_path.exists():
            skipped_docs.append({"path": rel, "reason": "missing_on_disk"})
            continue
        size = int(abs_path.stat().st_size)
        if size > max_doc_bytes:
            skipped_docs.append({"path": rel, "reason": f"too_large>{max_doc_bytes}"})
            continue
        text = common.read_text(abs_path)
        if not text.strip():
            skipped_docs.append({"path": rel, "reason": "empty_or_unreadable"})
            continue

        headings = _extract_headings(text)
        summary = _extract_summary(text, max_summary_chars)
        title = headings[0] if headings else Path(rel).name
        parsed_docs.append(
            {
                "path": rel,
                "title": title,
                "summary": summary,
                "headings": headings,
                "line_count": common.file_line_count(abs_path),
                "size_bytes": size,
                "keywords": common.discover_words(text, min_len=4, max_words=16),
            }
        )

    payload = {
        "generated_at": common.now_iso(),
        "mode": mode,
        "discovered_count": len(discovered),
        "parsed_count": len(parsed_docs),
        "skipped_count": len(skipped_docs),
        "discovered_docs": discovered,
        "parsed_docs": parsed_docs,
        "skipped_docs": skipped_docs,
    }
    common.write_json(out_dir / "coverage_report.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest repository documentation and emit coverage report.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--index", required=True, help="Path to meta/index.json")
    parser.add_argument("--output", required=True, help="Meta output directory")
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()

    payload = ingest_docs(
        repo_root=Path(args.repo).resolve(),
        index_payload=common.read_json(Path(args.index), default={}),
        out_dir=Path(args.output).resolve(),
        mode=common.normalize_mode(args.mode),
    )
    print(
        f"Doc coverage: discovered={payload['discovered_count']} parsed={payload['parsed_count']} "
        f"skipped={payload['skipped_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
