#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _list_to_bullets(items: List[str], fallback: str = "- Not available") -> str:
    if not items:
        return fallback
    return "\n".join([f"- {item}" for item in items])


def _module_table(modules: List[Dict[str, Any]], limit: int = 20) -> str:
    lines = ["| Module | File Count | Total Size (KB) |", "|---|---:|---:|"]
    for module in modules[:limit]:
        kb = round(module.get("total_bytes", 0) / 1024.0, 1)
        lines.append(f"| `{module['name']}` | {module['file_count']} | {kb} |")
    return "\n".join(lines)


def _entry_table(entries: List[Dict[str, str]]) -> str:
    if not entries:
        return "_No clear entrypoints detected._"
    lines = ["| Path | Kind |", "|---|---|"]
    for entry in entries[:25]:
        lines.append(f"| `{entry['path']}` | {entry['kind']} |")
    return "\n".join(lines)


def _dep_section(dep_payload: Dict[str, Any]) -> str:
    external = dep_payload.get("external_dependencies", {})
    if not external:
        return "_No dependency manifests detected._"
    chunks = []
    for manifest, deps in external.items():
        chunks.append(f"### `{manifest}`")
        if deps:
            chunks.append(_list_to_bullets([f"`{d}`" for d in deps[:80]]))
        else:
            chunks.append("- No dependencies parsed")
        chunks.append("")
    chunks.append(f"Internal dependency edges detected: **{dep_payload.get('internal_edge_count', 0)}**")
    return "\n".join(chunks)


def _diagram_links(diagram_manifest: Dict[str, Any]) -> str:
    links = []
    for file_name in diagram_manifest.get("diagram_files", []):
        stem = Path(file_name).stem
        links.append(f"- `{file_name}` | [SVG](../diagrams/svg/{stem}.svg) | [PNG](../diagrams/png/{stem}.png)")
    return "\n".join(links) if links else "- No diagrams generated."


def _where_to_modify(modules: List[Dict[str, Any]]) -> str:
    if not modules:
        return "- Check entrypoint files and service modules."
    suggestions = []
    for module in modules[:6]:
        name = module["name"]
        suggestions.append(f"- For changes in **{name}**, start with `{name}/` and trace callers from entrypoints.")
    return "\n".join(suggestions)


def _glossary_terms(
    stack_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    module_payload: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    terms: List[Dict[str, str]] = []
    frameworks = stack_payload.get("frameworks", [])
    for fw in frameworks:
        terms.append({"term": fw, "definition": f"{fw} framework used in this repository."})

    arch = stack_payload.get("architecture_pattern", "Architecture")
    terms.append({"term": arch, "definition": f"Detected architectural style: {arch}."})

    for manifest, deps in dep_payload.get("external_dependencies", {}).items():
        if deps:
            terms.append({"term": manifest, "definition": f"Dependency manifest containing {len(deps)} package entries."})

    for module in module_payload[:6]:
        terms.append(
            {
                "term": module["name"],
                "definition": f"Top-level module with {module['file_count']} files in this codebase.",
            }
        )
    dedup = {}
    for item in terms:
        dedup[item["term"]] = item
    return list(dedup.values())[:40]


def generate_docs(
    output_root: Path,
    templates_root: Path,
    source: str,
    mode: str,
    audience: str,
    index_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    diagram_manifest: Dict[str, Any],
    enrichment_payload: Dict[str, Any],
) -> Dict[str, Any]:
    overview_dir = common.ensure_dir(output_root / "overview")
    deep_dir = common.ensure_dir(output_root / "deep")

    modules = index_payload.get("modules", [])
    entrypoints = entry_payload.get("entrypoints", [])
    languages = stack_payload.get("languages", {})
    frameworks = stack_payload.get("frameworks", [])
    repo_name = stack_payload.get("repo_name", common.detect_repo_name(source, output_root))

    top_languages = ", ".join([f"{lang} ({count})" for lang, count in list(languages.items())[:5]]) or "Unknown"
    top_frameworks = ", ".join(frameworks[:8]) or "None detected"
    key_building_blocks = [m["name"] for m in modules[:7]]

    replacements_common = {
        "repo_name": repo_name,
        "source": source,
        "mode": mode,
        "audience": audience,
        "generated_at": common.now_iso(),
        "architecture_pattern": stack_payload.get("architecture_pattern", "Unknown"),
        "top_languages": top_languages,
        "top_frameworks": top_frameworks,
        "building_blocks": _list_to_bullets(key_building_blocks, "- No major blocks detected"),
        "entrypoints_table": _entry_table(entrypoints),
        "module_table": _module_table(modules),
        "dependency_section": _dep_section(dep_payload),
        "diagram_links": _diagram_links(diagram_manifest),
        "where_to_modify": _where_to_modify(modules),
        "request_lifecycle": _list_to_bullets(flow_payload.get("request_lifecycle", [])),
        "critical_paths": _list_to_bullets([p["name"] for p in flow_payload.get("critical_paths", [])]),
    }

    overview_template = common.load_template(templates_root / "overview.md.j2")
    arch_template = common.load_template(templates_root / "deep_architecture.md.j2")
    modules_template = common.load_template(templates_root / "deep_modules.md.j2")
    flows_template = common.load_template(templates_root / "deep_flows.md.j2")
    glossary_template = common.load_template(templates_root / "glossary.md.j2")

    overview_text = common.render_template(overview_template, replacements_common)
    arch_text = common.render_template(arch_template, replacements_common)
    modules_text = common.render_template(modules_template, replacements_common)
    flows_text = common.render_template(flows_template, replacements_common)

    glossary_terms = _glossary_terms(stack_payload, dep_payload, modules)
    glossary_lines = "\n".join([f"- **{item['term']}**: {item['definition']}" for item in glossary_terms])
    glossary_text = common.render_template(glossary_template, {**replacements_common, "glossary_entries": glossary_lines})

    # Dependencies deep doc is generated directly to keep contract explicit.
    dependencies_deep = f"""# Dependencies Deep Explainer

Generated at: {common.now_iso()}

## External Dependencies

{_dep_section(dep_payload)}

## Internal Dependency Footprint

- Internal edge count: **{dep_payload.get('internal_edge_count', 0)}**
- Parsed edge sample size: **{len(dep_payload.get('internal_edges', []))}**

## Risk and Upgrade Callouts

- Review dependencies with no recent update policy.
- Prioritize auth, networking, and serialization packages for security review.
- Confirm lockfile hygiene and reproducible installs for onboarding reliability.
"""

    (overview_dir / "OVERVIEW.md").write_text(overview_text, encoding="utf-8")
    (deep_dir / "ARCHITECTURE_DEEP.md").write_text(arch_text, encoding="utf-8")
    (deep_dir / "MODULES_DEEP.md").write_text(modules_text, encoding="utf-8")
    (deep_dir / "FLOWS_DEEP.md").write_text(flows_text, encoding="utf-8")
    (deep_dir / "DEPENDENCIES_DEEP.md").write_text(dependencies_deep, encoding="utf-8")
    (deep_dir / "GLOSSARY.md").write_text(glossary_text, encoding="utf-8")

    claims = [
        common.collect_claim(
            "claim_primary_language",
            f"Primary language appears to be {stack_payload.get('primary_language', 'Unknown')}.",
            [f"meta/index.json", "meta/stack.json"],
            0.88,
            "Derived from file extension distribution",
        ),
        common.collect_claim(
            "claim_architecture",
            f"Detected architecture pattern is {stack_payload.get('architecture_pattern', 'Unknown')}.",
            ["meta/stack.json"],
            0.72,
            "Heuristic directory pattern matching",
        ),
        common.collect_claim(
            "claim_entrypoints",
            f"Detected {len(entrypoints)} likely entrypoint files.",
            ["meta/entrypoints.json"],
            0.80,
            "Filename and conventional file pattern matching",
        ),
        common.collect_claim(
            "claim_diagram_set",
            f"Generated {diagram_manifest.get('count', 0)} Mermaid diagrams for onboarding and deep dives.",
            ["meta/diagram_manifest.json"],
            0.95,
            "Deterministic diagram build output",
        ),
    ]

    if enrichment_payload.get("records"):
        claims.append(
            common.collect_claim(
                "claim_external_enrichment",
                "External context enrichment was attempted for this analysis.",
                ["meta/enrichment.json"],
                0.66,
                "Network sources may vary over time; local analysis remains primary.",
            )
        )

    payload = {
        "generated_at": common.now_iso(),
        "overview_file": "overview/OVERVIEW.md",
        "deep_files": [
            "deep/ARCHITECTURE_DEEP.md",
            "deep/MODULES_DEEP.md",
            "deep/FLOWS_DEEP.md",
            "deep/DEPENDENCIES_DEEP.md",
            "deep/GLOSSARY.md",
        ],
        "claims": claims,
    }
    common.write_json(output_root / "meta" / "docs_generation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate two-tier markdown explainers.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--templates-root", required=True)
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--index", required=True)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--diagram-manifest", required=True)
    parser.add_argument("--enrichment", required=True)
    args = parser.parse_args()

    payload = generate_docs(
        output_root=Path(args.output_root).resolve(),
        templates_root=Path(args.templates_root).resolve(),
        source=args.source,
        mode=common.normalize_mode(args.mode),
        audience=args.audience,
        index_payload=common.read_json(Path(args.index), default={}),
        stack_payload=common.read_json(Path(args.stack), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        diagram_manifest=common.read_json(Path(args.diagram_manifest), default={}),
        enrichment_payload=common.read_json(Path(args.enrichment), default={}),
    )
    print(json.dumps({"overview": payload["overview_file"], "deep_count": len(payload["deep_files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

