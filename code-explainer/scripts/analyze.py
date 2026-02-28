#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common
import index_repo
import detect_stack
import map_entrypoints
import map_dependencies
import map_flows
import ingest_docs
import llm_describe
import build_diagrams
import validate_mermaid
import render_diagrams
import enrich_external
import generate_docs
import quality_gate


def _clone_github_repo(source: str) -> Tuple[Path, str]:
    slug = common.github_repo_slug(source)
    temp_root = Path(tempfile.mkdtemp(prefix="code_explainer_repo_"))
    clone_dir = temp_root / slug.split("/")[-1]
    if not common.which("git"):
        raise RuntimeError("git is required for GitHub URL analysis but was not found on PATH.")
    code, _out, err = common.run_cmd(["git", "clone", "--depth", "1", source, str(clone_dir)], timeout=300)
    if code != 0:
        raise RuntimeError(f"Failed to clone repository: {err.strip() or 'unknown error'}")
    return clone_dir, temp_root.as_posix()


def _resolve_source(source: str) -> Tuple[Path, bool, str]:
    source = source.strip()
    if common.is_github_url(source):
        repo_root, cleanup_root = _clone_github_repo(source)
        return repo_root, True, cleanup_root
    path = Path(source).resolve()
    if not path.exists() or not path.is_dir():
        raise RuntimeError(f"Local source path does not exist or is not a directory: {source}")
    return path, False, ""


def _write_confidence_and_attribution(
    output_root: Path,
    docs_payload: Dict[str, Any],
    enrichment_payload: Dict[str, Any],
) -> None:
    claims = docs_payload.get("claims", [])
    confidence_payload = {"generated_at": common.now_iso(), "claims": claims}
    common.write_json(output_root / "meta" / "confidence_report.json", confidence_payload)

    attributions = []
    for item in enrichment_payload.get("source_attribution", []):
        attributions.append(item)
    for claim in claims:
        if claim.get("evidence_paths"):
            attributions.append(
                {
                    "claim_id": claim["claim_id"],
                    "source_type": "local",
                    "source_uri": "local-analysis",
                    "extraction_timestamp": common.now_iso(),
                }
            )
    common.write_json(output_root / "meta" / "source_attribution.json", {"generated_at": common.now_iso(), "attributions": attributions})


def _write_manifest(
    output_root: Path,
    source: str,
    mode: str,
    audience: str,
    overview_length: str,
    repo_root: Path,
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    module_count: int,
    diagram_count: int,
    include_globs: List[str],
    exclude_globs: List[str],
) -> None:
    manifest = {
        "source": source,
        "repo_root": repo_root.as_posix(),
        "commit_ref": common.maybe_git_ref(repo_root),
        "scan_time": common.now_iso(),
        "mode": mode,
        "audience": audience,
        "overview_length": overview_length,
        "languages": stack_payload.get("languages", {}),
        "frameworks": stack_payload.get("frameworks", []),
        "entrypoints": entry_payload.get("entrypoints", []),
        "docs_discovered": docs_payload.get("discovered_count", 0),
        "docs_parsed": docs_payload.get("parsed_count", 0),
        "llm_descriptions_enabled": llm_payload.get("enabled", False),
        "llm_descriptions_used": llm_payload.get("used", False),
        "llm_model": llm_payload.get("model", ""),
        "module_count": module_count,
        "diagram_count": diagram_count,
        "include_globs": include_globs,
        "exclude_globs": exclude_globs,
    }
    common.write_json(output_root / "meta" / "analysis_manifest.json", manifest)


def run_pipeline(
    source: str,
    output_root: Path,
    mode: str,
    audience: str,
    overview_length: str,
    enable_web_enrichment: bool,
    enable_llm_descriptions: bool,
    include_globs: List[str] | None = None,
    exclude_globs: List[str] | None = None,
) -> Dict[str, Any]:
    output_root = common.ensure_dir(output_root)
    meta_dir = common.ensure_dir(output_root / "meta")
    diagrams_dir = common.ensure_dir(output_root / "diagrams")
    common.ensure_dir(output_root / "overview")
    common.ensure_dir(output_root / "deep")
    common.ensure_dir(output_root / "diagrams" / "svg")
    common.ensure_dir(output_root / "diagrams" / "png")

    repo_root, should_cleanup, cleanup_root = _resolve_source(source)
    try:
        include_globs = include_globs or []
        exclude_globs = exclude_globs or []
        index_payload = index_repo.build_index(
            repo_root,
            meta_dir,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        )
        stack_payload = detect_stack.analyze_stack(repo_root, index_payload, meta_dir)
        entry_payload = map_entrypoints.map_entrypoints(index_payload, repo_root, meta_dir)
        dep_payload = map_dependencies.map_dependencies(repo_root, index_payload, meta_dir)
        flow_payload = map_flows.map_flows(stack_payload, entry_payload, dep_payload, meta_dir, mode)
        coverage_payload = ingest_docs.ingest_docs(repo_root, index_payload, meta_dir, mode)
        enrichment_payload = enrich_external.enrich_external(source, meta_dir, enable_web_enrichment)
        llm_payload = llm_describe.generate_llm_descriptions(
            repo_root=repo_root,
            source=source,
            mode=mode,
            audience=audience,
            index_payload=index_payload,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            docs_payload=coverage_payload,
            out_dir=meta_dir,
            enabled=enable_llm_descriptions,
        )

        diagram_manifest = build_diagrams.build_diagrams(
            stack=stack_payload,
            modules=index_payload.get("modules", []),
            deps=dep_payload,
            flows=flow_payload,
            diagrams_dir=diagrams_dir,
            mode=mode,
        )

        validation_payload = validate_mermaid.validate_mermaid(diagrams_dir, meta_dir)
        render_payload = render_diagrams.render_diagrams(diagrams_dir, output_root / "diagrams", theme="neutral")

        docs_gen_payload = generate_docs.generate_docs(
            output_root=output_root,
            templates_root=SCRIPT_DIR.parent / "assets" / "templates",
            source=source,
            mode=mode,
            audience=audience,
            overview_length=overview_length,
            index_payload=index_payload,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            diagram_manifest=diagram_manifest,
            docs_payload=coverage_payload,
            llm_payload=llm_payload,
            enrichment_payload=enrichment_payload,
        )
        _write_confidence_and_attribution(output_root, docs_gen_payload, enrichment_payload)
        _write_manifest(
            output_root=output_root,
            source=source,
            mode=mode,
            audience=audience,
            overview_length=overview_length,
            repo_root=repo_root,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            docs_payload=coverage_payload,
            llm_payload=llm_payload,
            module_count=len(index_payload.get("modules", [])),
            diagram_count=diagram_manifest.get("count", 0),
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        )

        quality_payload = quality_gate.run_quality_gate(output_root, mode)

        return {
            "source_root": repo_root.as_posix(),
            "output_root": output_root.as_posix(),
            "mode": mode,
            "audience": audience,
            "overview_length": overview_length,
            "file_count": index_payload.get("file_count", 0),
            "docs_discovered": coverage_payload.get("discovered_count", 0),
            "docs_parsed": coverage_payload.get("parsed_count", 0),
            "llm_descriptions_used": llm_payload.get("used", False),
            "diagram_count": diagram_manifest.get("count", 0),
            "validation_ok": validation_payload.get("overall_ok", False),
            "renderer": render_payload.get("renderer", ""),
            "quality_passed": quality_payload.get("passed", False),
            "quality_errors": quality_payload.get("errors", []),
            "quality_warnings": quality_payload.get("warnings", []),
        }
    finally:
        if should_cleanup and cleanup_root:
            shutil.rmtree(cleanup_root, ignore_errors=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code-Explainer pipeline entrypoint.")
    parser.add_argument("command", nargs="?", default="analyze", help="Use 'analyze' (default).")
    parser.add_argument("--source", required=True, help="Local folder path or GitHub repository URL")
    parser.add_argument("--output", required=True, help="Output directory root")
    parser.add_argument("--mode", default="standard", choices=["quick", "standard", "deep"])
    parser.add_argument("--audience", default="nontech", choices=["nontech", "mixed", "engineering"])
    parser.add_argument("--overview-length", default="medium", choices=["short", "medium", "long"])
    parser.add_argument(
        "--include-glob",
        action="append",
        default=[],
        help="Glob(s) to include. If provided, only matching files are indexed.",
    )
    parser.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        help="Glob(s) to exclude from indexing.",
    )
    parser.add_argument("--enable-web-enrichment", default="true")
    parser.add_argument("--enable-llm-descriptions", default="true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command != "analyze":
        print("Only 'analyze' is supported.")
        return 2

    mode = common.normalize_mode(args.mode)
    web_enabled = common.bool_from_string(args.enable_web_enrichment)
    llm_enabled = common.bool_from_string(args.enable_llm_descriptions)
    summary = run_pipeline(
        source=args.source,
        output_root=Path(args.output).resolve(),
        mode=mode,
        audience=args.audience,
        overview_length=args.overview_length,
        enable_web_enrichment=web_enabled,
        enable_llm_descriptions=llm_enabled,
        include_globs=args.include_glob,
        exclude_globs=args.exclude_glob,
    )
    print("Code-explainer run complete:")
    for key in [
        "source_root",
        "output_root",
        "mode",
        "audience",
        "overview_length",
        "file_count",
        "docs_discovered",
        "docs_parsed",
        "llm_descriptions_used",
        "diagram_count",
        "validation_ok",
        "renderer",
        "quality_passed",
    ]:
        print(f"- {key}: {summary.get(key)}")
    if summary.get("quality_errors"):
        print("- quality_errors:")
        for err in summary["quality_errors"]:
            print(f"  - {err}")
    if summary.get("quality_warnings"):
        print("- quality_warnings:")
        for warn in summary["quality_warnings"]:
            print(f"  - {warn}")
    return 0 if summary.get("quality_passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
