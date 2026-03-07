#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
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
import explainer_context
import explanation_plan
import verification_checkpoint
import llm_describe
import build_diagrams
import validate_mermaid
import render_diagrams
import export_excalidraw
import enrich_external
import generate_docs
import generate_html
import fact_check
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
    output_format: str,
    analysis_type: str,
    repo_root: Path,
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    verification_payload: Dict[str, Any],
    html_payload: Dict[str, Any],
    fact_check_payload: Dict[str, Any],
    excalidraw_payload: Dict[str, Any],
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
        "output_format": output_format,
        "analysis_type": analysis_type,
        "languages": stack_payload.get("languages", {}),
        "frameworks": stack_payload.get("frameworks", []),
        "entrypoints": entry_payload.get("entrypoints", []),
        "docs_discovered": docs_payload.get("discovered_count", 0),
        "docs_parsed": docs_payload.get("parsed_count", 0),
        "llm_descriptions_enabled": llm_payload.get("enabled", False),
        "llm_descriptions_used": llm_payload.get("used", False),
        "llm_model": llm_payload.get("model", ""),
        "verification_fact_count": verification_payload.get("fact_count", 0),
        "fact_check_passed": fact_check_payload.get("passed", False),
        "excalidraw_export_requested": excalidraw_payload.get("requested", False),
        "excalidraw_export_status": excalidraw_payload.get("status", "disabled"),
        "excalidraw_scene_count": excalidraw_payload.get("scene_count", 0),
        "official_excalidraw_bridge_requested": excalidraw_payload.get("official_bridge_requested", False),
        "official_excalidraw_bridge_used": excalidraw_payload.get("official_bridge_used", 0),
        "html_generated": bool(html_payload.get("output_file")),
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
    output_format: str,
    analysis_type: str,
    enable_web_enrichment: bool,
    enable_llm_descriptions: bool,
    enable_excalidraw_export: bool,
    enable_official_excalidraw_bridge: bool = False,
    ask_before_llm_use: bool = False,
    prompt_for_llm_key: bool = True,
    persist_llm_key: str = "ask",
    include_globs: List[str] | None = None,
    exclude_globs: List[str] | None = None,
    since: str = "2 weeks ago",
    git_ref: str = "main",
    plan_file: str = "",
) -> Dict[str, Any]:
    output_root = common.ensure_dir(output_root)
    meta_dir = common.ensure_dir(output_root / "meta")
    diagrams_dir = common.ensure_dir(output_root / "diagrams")
    common.ensure_dir(output_root / "overview")
    common.ensure_dir(output_root / "deep")
    common.ensure_dir(output_root / "diagrams" / "svg")
    common.ensure_dir(output_root / "diagrams" / "png")
    common.ensure_dir(output_root / "html")

    resolved_llm_runtime: Dict[str, Any] | None = None
    use_mock_llm = common.bool_from_string(os.environ.get("CODE_EXPLAINER_MOCK_LLM", "false"))
    if enable_llm_descriptions and not use_mock_llm:
        resolved_llm_runtime = llm_describe.resolve_llm_runtime(
            prompt_for_key=prompt_for_llm_key,
            persist_key_mode=persist_llm_key,
            require_key=True,
        )

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
        context_payload = explainer_context.build_explainer_context(
            repo_root=repo_root,
            source=source,
            analysis_type=analysis_type,
            out_dir=meta_dir,
            since=since,
            git_ref=git_ref,
            plan_file=plan_file,
        )
        plan_payload = explanation_plan.build_explanation_plan(
            repo_root=repo_root,
            source=source,
            audience=audience,
            mode=mode,
            analysis_type=analysis_type,
            index_payload=index_payload,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            docs_payload=coverage_payload,
            context_payload=context_payload,
            out_dir=meta_dir,
        )
        verification_payload = verification_checkpoint.build_verification_checkpoint(
            output_root=output_root,
            source=source,
            analysis_type=analysis_type,
            stack_payload=stack_payload,
            index_payload=index_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            docs_payload=coverage_payload,
            context_payload=context_payload,
            plan_payload=plan_payload,
        )

        enrichment_payload = enrich_external.enrich_external(source, meta_dir, enable_web_enrichment)
        llm_payload = llm_describe.generate_llm_descriptions(
            repo_root=repo_root,
            source=source,
            mode=mode,
            audience=audience,
            analysis_type=analysis_type,
            index_payload=index_payload,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            docs_payload=coverage_payload,
            context_payload=context_payload,
            plan_payload=plan_payload,
            out_dir=meta_dir,
            enabled=enable_llm_descriptions,
            ask_before_use=ask_before_llm_use,
            prompt_for_key=prompt_for_llm_key,
            persist_key_mode=persist_llm_key,
            resolved_runtime=resolved_llm_runtime,
        )

        diagram_manifest = build_diagrams.build_diagrams(
            stack=stack_payload,
            modules=index_payload.get("modules", []),
            deps=dep_payload,
            flows=flow_payload,
            plan_payload=plan_payload,
            diagrams_dir=diagrams_dir,
            mode=mode,
        )

        validation_payload = validate_mermaid.validate_mermaid(diagrams_dir, meta_dir)
        render_payload = render_diagrams.render_diagrams(diagrams_dir, output_root / "diagrams", theme="neutral")
        excalidraw_payload = export_excalidraw.export_excalidraw(
            diagrams_dir=diagrams_dir,
            rendered_diagrams_dir=output_root / "diagrams",
            meta_dir=meta_dir,
            enabled=enable_excalidraw_export,
            prefer_official_bridge=enable_official_excalidraw_bridge,
        )

        docs_gen_payload = generate_docs.generate_docs(
            output_root=output_root,
            templates_root=SCRIPT_DIR.parent / "assets" / "templates",
            source=source,
            mode=mode,
            audience=audience,
            overview_length=overview_length,
            analysis_type=analysis_type,
            output_format=output_format,
            index_payload=index_payload,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            dep_payload=dep_payload,
            flow_payload=flow_payload,
            diagram_manifest=diagram_manifest,
            docs_payload=coverage_payload,
            llm_payload=llm_payload,
            context_payload=context_payload,
            plan_payload=plan_payload,
            verification_payload=verification_payload,
            enrichment_payload=enrichment_payload,
        )

        html_payload: Dict[str, Any] = {}
        if output_format in {"html", "both"}:
            html_payload = generate_html.generate_html(
                output_root=output_root,
                source=source,
                mode=mode,
                audience=audience,
                overview_length=overview_length,
                analysis_type=analysis_type,
                stack_payload=stack_payload,
                index_payload=index_payload,
                entry_payload=entry_payload,
                dep_payload=dep_payload,
                flow_payload=flow_payload,
                docs_payload=coverage_payload,
                llm_payload=llm_payload,
                diagram_manifest=diagram_manifest,
                context_payload=context_payload,
                verification_payload=verification_payload,
            )

        _write_confidence_and_attribution(output_root, docs_gen_payload, enrichment_payload)
        fact_check_payload = fact_check.run_fact_check(
            output_root=output_root,
            output_format=output_format,
            analysis_type=analysis_type,
            verification_payload=verification_payload,
        )
        _write_manifest(
            output_root=output_root,
            source=source,
            mode=mode,
            audience=audience,
            overview_length=overview_length,
            output_format=output_format,
            analysis_type=analysis_type,
            repo_root=repo_root,
            stack_payload=stack_payload,
            entry_payload=entry_payload,
            docs_payload=coverage_payload,
            llm_payload=llm_payload,
            verification_payload=verification_payload,
            html_payload=html_payload,
            fact_check_payload=fact_check_payload,
            excalidraw_payload=excalidraw_payload,
            module_count=len(index_payload.get("modules", [])),
            diagram_count=diagram_manifest.get("count", 0),
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        )

        quality_payload = quality_gate.run_quality_gate(
            output_root=output_root,
            mode=mode,
            output_format=output_format,
            analysis_type=analysis_type,
            audience=audience,
        )

        return {
            "source_root": repo_root.as_posix(),
            "output_root": output_root.as_posix(),
            "mode": mode,
            "analysis_type": analysis_type,
            "output_format": output_format,
            "audience": audience,
            "overview_length": overview_length,
            "file_count": index_payload.get("file_count", 0),
            "docs_discovered": coverage_payload.get("discovered_count", 0),
            "docs_parsed": coverage_payload.get("parsed_count", 0),
            "llm_descriptions_used": llm_payload.get("used", False),
            "diagram_count": diagram_manifest.get("count", 0),
            "validation_ok": validation_payload.get("overall_ok", False),
            "renderer": render_payload.get("renderer", ""),
            "excalidraw_status": excalidraw_payload.get("status", "disabled"),
            "excalidraw_scene_count": excalidraw_payload.get("scene_count", 0),
            "official_excalidraw_bridge_used": excalidraw_payload.get("official_bridge_used", 0),
            "html_generated": bool(html_payload.get("output_file")),
            "fact_check_passed": fact_check_payload.get("passed", False),
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
    parser.add_argument("--format", default="markdown", choices=["markdown", "html", "both"])
    parser.add_argument(
        "--explainer-type",
        default="onboarding",
        choices=["onboarding", "project-recap", "plan-review", "diff-review"],
    )
    parser.add_argument("--plan-file", default="", help="Path to plan/spec file (used by plan-review).")
    parser.add_argument("--git-ref", default="main", help="Git ref for diff-review mode.")
    parser.add_argument("--since", default="2 weeks ago", help="Time window for project-recap mode.")
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
    parser.add_argument("--enable-excalidraw-export", default="true")
    parser.add_argument("--enable-official-excalidraw-bridge", default="false")
    parser.add_argument("--ask-before-llm-use", default="false")
    parser.add_argument("--prompt-for-llm-key", default="true")
    parser.add_argument("--persist-llm-key", default="ask", choices=["ask", "true", "false"])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command != "analyze":
        print("Only 'analyze' is supported.")
        return 2

    mode = common.normalize_mode(args.mode)
    web_enabled = common.bool_from_string(args.enable_web_enrichment)
    llm_enabled = common.bool_from_string(args.enable_llm_descriptions)
    excalidraw_enabled = common.bool_from_string(args.enable_excalidraw_export)
    official_excalidraw_bridge_enabled = common.bool_from_string(args.enable_official_excalidraw_bridge)
    ask_before_llm_use = common.bool_from_string(args.ask_before_llm_use)
    prompt_for_llm_key = common.bool_from_string(args.prompt_for_llm_key)
    summary = run_pipeline(
        source=args.source,
        output_root=Path(args.output).resolve(),
        mode=mode,
        audience=args.audience,
        overview_length=args.overview_length,
        output_format=args.format,
        analysis_type=args.explainer_type,
        enable_web_enrichment=web_enabled,
        enable_llm_descriptions=llm_enabled,
        enable_excalidraw_export=excalidraw_enabled,
        enable_official_excalidraw_bridge=official_excalidraw_bridge_enabled,
        ask_before_llm_use=ask_before_llm_use,
        prompt_for_llm_key=prompt_for_llm_key,
        persist_llm_key=args.persist_llm_key,
        include_globs=args.include_glob,
        exclude_globs=args.exclude_glob,
        since=args.since,
        git_ref=args.git_ref,
        plan_file=args.plan_file,
    )
    print("Code-explainer run complete:")
    for key in [
        "source_root",
        "output_root",
        "mode",
        "analysis_type",
        "output_format",
        "audience",
        "overview_length",
        "file_count",
        "docs_discovered",
        "docs_parsed",
        "llm_descriptions_used",
        "diagram_count",
        "validation_ok",
        "renderer",
        "excalidraw_status",
        "excalidraw_scene_count",
        "official_excalidraw_bridge_used",
        "html_generated",
        "fact_check_passed",
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
