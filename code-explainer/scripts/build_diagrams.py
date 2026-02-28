#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _write_diagram(diagrams_dir: Path, name: str, body: str) -> str:
    path = diagrams_dir / f"{name}.mmd"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path.name


def build_diagrams(
    stack: Dict[str, Any],
    modules: List[Dict[str, Any]],
    deps: Dict[str, Any],
    flows: Dict[str, Any],
    diagrams_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    common.ensure_dir(diagrams_dir)
    files: List[str] = []

    repo_name = stack.get("repo_name", "System")
    frameworks = ", ".join(stack.get("frameworks", [])[:3]) or "Core stack"
    primary_language = stack.get("primary_language", "Unknown")

    files.append(
        _write_diagram(
            diagrams_dir,
            "c4_context",
            f"""
C4Context
  title C4 Context - {repo_name}
  Person(user, "User", "PM, designer, or engineer using the product")
  System(app, "{repo_name}", "Software platform under analysis")
  System_Ext(ext, "External systems", "{frameworks}")
  Rel(user, app, "Uses")
  Rel(app, ext, "Integrates with")
""",
        )
    )

    module_labels = [m["name"] for m in modules[:5]] or ["core"]
    container_nodes = "\n".join(
        [f'    Container(c{i}, "{name}", "{primary_language}", "Core module")' for i, name in enumerate(module_labels, start=1)]
    )
    rel_lines = []
    for i in range(1, len(module_labels)):
        rel_lines.append(f'  Rel(c{i}, c{i+1}, "calls/depends on")')
    files.append(
        _write_diagram(
            diagrams_dir,
            "c4_container",
            f"""
C4Container
  title C4 Container - {repo_name}
  Person(user, "User", "Interacts with platform")
  System_Boundary(sys, "{repo_name}") {{
{container_nodes}
  }}
  Rel(user, c1, "Interacts with")
{"".join(line + chr(10) for line in rel_lines)}
""",
        )
    )

    lifecycle_steps = flows.get("request_lifecycle", [])
    participants = "\n".join([f"    participant S{i} as {step.replace(' ', '_')}" for i, step in enumerate(lifecycle_steps, start=1)])
    messages = []
    for i in range(1, len(lifecycle_steps)):
        messages.append(f"    S{i}->>S{i+1}: {lifecycle_steps[i-1]} to {lifecycle_steps[i]}")
    files.append(
        _write_diagram(
            diagrams_dir,
            "request_lifecycle_sequence",
            f"""
sequenceDiagram
{participants}
{chr(10).join(messages)}
""",
        )
    )

    files.append(
        _write_diagram(
            diagrams_dir,
            "primary_user_flow",
            """
flowchart TD
    A[User Goal] --> B{Need Context?}
    B -->|Yes| C[Open OVERVIEW.md]
    C --> D[Review architecture diagram]
    D --> E[Jump to deep explainer]
    B -->|No| F[Go to task-specific section]
    E --> G[Understand modules and flows]
    F --> G
""",
        )
    )

    edge_lines = deps.get("internal_edges", [])[:25]
    graph_lines = []
    for edge in edge_lines:
        src = common.safe_word(edge.get("from", "src"))
        dst = common.safe_word(edge.get("to", "dst"))
        graph_lines.append(f"    {src} --> {dst}")
    if not graph_lines:
        graph_lines = ["    module_a --> module_b", "    module_b --> module_c"]
    files.append(
        _write_diagram(
            diagrams_dir,
            "module_dependency_graph",
            "flowchart LR\n" + "\n".join(graph_lines),
        )
    )

    if mode == "deep":
        files.append(
            _write_diagram(
                diagrams_dir,
                "critical_path_sequence",
                """
sequenceDiagram
    participant User
    participant Entry
    participant Service
    participant Data
    User->>Entry: Trigger critical workflow
    Entry->>Service: Validate and orchestrate
    Service->>Data: Persist and read state
    Data-->>Service: Return result
    Service-->>Entry: Compose response
    Entry-->>User: Return outcome
""",
            )
        )
        files.append(
            _write_diagram(
                diagrams_dir,
                "trust_boundary_flow",
                """
flowchart TB
    ext[External User] --> api[Public Interface]
    api --> app[Application Boundary]
    app --> db[(Data Store Boundary)]
    app --> third[Third-Party API Boundary]
""",
            )
        )
        files.append(
            _write_diagram(
                diagrams_dir,
                "data_lineage_flow",
                """
flowchart LR
    ingest[Input Data] --> validate[Validation]
    validate --> transform[Transformation]
    transform --> store[(Storage)]
    store --> aggregate[Aggregation]
    aggregate --> expose[Presentation]
""",
            )
        )
        files.append(
            _write_diagram(
                diagrams_dir,
                "where_to_change_map",
                """
flowchart TD
    req[Feature Request] --> ux[UI Layer]
    req --> api[API Layer]
    req --> domain[Domain Logic]
    req --> data[Data Model]
    ux --> tests[Test Updates]
    api --> tests
    domain --> tests
    data --> tests
""",
            )
        )

    payload = {
        "generated_at": common.now_iso(),
        "mode": mode,
        "diagram_files": files,
        "count": len(files),
    }
    common.write_json(diagrams_dir.parent / "meta" / "diagram_manifest.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Mermaid diagrams from analysis artifacts.")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--diagrams-dir", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()

    index_payload = common.read_json(Path(args.index), default={})
    stack_payload = common.read_json(Path(args.stack), default={})
    dep_payload = common.read_json(Path(args.dependencies), default={})
    flow_payload = common.read_json(Path(args.flows), default={})
    payload = build_diagrams(
        stack_payload,
        index_payload.get("modules", []),
        dep_payload,
        flow_payload,
        Path(args.diagrams_dir).resolve(),
        common.normalize_mode(args.mode),
    )
    print(f"Built {payload['count']} Mermaid diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

