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


def _request_flow(frameworks: List[str]) -> List[str]:
    if any(f in frameworks for f in ["Express", "FastAPI", "Django", "Flask", "NestJS", "Gin"]):
        return [
            "Client Request",
            "Routing Layer",
            "Middleware/Auth",
            "Business Service",
            "Data Layer",
            "Response",
        ]
    return [
        "User Interaction",
        "Application Controller",
        "Core Module",
        "Persistence/State",
        "UI/API Response",
    ]


def map_flows(
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    out_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    frameworks = stack_payload.get("frameworks", [])
    entrypoints = entry_payload.get("entrypoints", [])
    request_flow = _request_flow(frameworks)

    critical_paths = []
    if entrypoints:
        for entry in entrypoints[:6]:
            critical_paths.append(
                {
                    "name": f"Path from {entry['path']}",
                    "steps": [entry["path"], "service layer", "data layer", "response"],
                }
            )

    trust_boundaries = [
        {"name": "External user to application", "type": "network"},
        {"name": "Application to datastore", "type": "data access"},
    ]

    data_lineage = [
        "Input event/request",
        "Validation",
        "Transformation",
        "Storage",
        "Read/aggregation",
        "Presentation",
    ]

    payload = {
        "mapped_at": common.now_iso(),
        "mode": mode,
        "request_lifecycle": request_flow,
        "critical_paths": critical_paths if mode in {"standard", "deep"} else critical_paths[:2],
        "trust_boundaries": trust_boundaries if mode == "deep" else trust_boundaries[:1],
        "data_lineage": data_lineage if mode == "deep" else data_lineage[:4],
        "dependency_edge_count": dep_payload.get("internal_edge_count", 0),
    }
    common.write_json(out_dir / "flows.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Map codebase request and data flows.")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="standard")
    args = parser.parse_args()
    payload = map_flows(
        common.read_json(Path(args.stack), default={}),
        common.read_json(Path(args.entrypoints), default={}),
        common.read_json(Path(args.dependencies), default={}),
        Path(args.output).resolve(),
        common.normalize_mode(args.mode),
    )
    print(f"Mapped flow artifacts for mode={payload['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

