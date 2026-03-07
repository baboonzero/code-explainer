# Diagram Style Guide

## Core Rules

1. Mermaid is the canonical diagram source format.
2. Every diagram must have a purpose tied to onboarding comprehension.
3. Keep labels short and plain-language-first for non-technical readers.
4. Split diagrams when readability is degraded by scale.
5. Mermaid remains the canonical source; Excalidraw exports are editable derivatives of those same diagrams.
6. The deterministic local Excalidraw exporter is the default production path; the official bridge is optional and development-only.

## Standard Mode Diagram Set

1. `c4_context.mmd`
2. `c4_container.mmd`
3. `request_lifecycle_sequence.mmd`
4. `primary_user_flow.mmd`
5. `module_dependency_graph.mmd`

## Deep Mode Additions

1. `critical_path_sequence.mmd`
2. `trust_boundary_flow.mmd`
3. `data_lineage_flow.mmd`
4. `where_to_change_map.mmd`

## Rendering Policy

1. Validate Mermaid before rendering.
2. Export SVG first, then PNG.
3. Use a neutral, high-contrast theme.
4. Prefer 16:9 or wider canvases for architecture and dependency maps.
5. When Excalidraw export is enabled, mirror each Mermaid diagram into an editable `.excalidraw.json` scene and keep the SVG/PNG previews aligned with the same content.

## Complexity Heuristics

Flag for split or simplification when:

- > 50 nodes
- > 120 edges
- > 220 lines in Mermaid source
