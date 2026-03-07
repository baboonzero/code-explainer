#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _escape(text: str) -> str:
    return html.escape(text or "", quote=True)


def _table_rows(items: List[List[str]]) -> str:
    rows = []
    for row in items:
        cells = "".join([f"<td>{_escape(cell)}</td>" for cell in row])
        rows.append(f"<tr>{cells}</tr>")
    return "\n".join(rows)


def _mode_context_block(analysis_type: str, context_payload: Dict[str, Any]) -> str:
    if analysis_type == "project-recap":
        recap = context_payload.get("project_recap", {})
        if not recap.get("available"):
            return f"<p class='note'>{_escape(recap.get('reason', 'Project recap context unavailable.'))}</p>"
        items = [
            f"Commit window: {recap.get('since', context_payload.get('since', 'n/a'))}",
            f"Commits in window: {recap.get('commit_count', 0)}",
            f"Contributors: {len(recap.get('contributors', []))}",
            f"Uncommitted changes present: {'yes' if recap.get('has_uncommitted_changes') else 'no'}",
        ]
        top_files = recap.get("top_changed_files", [])[:8]
        top_html = "".join(
            [f"<li><code>{_escape(item['path'])}</code> ({item['touch_count']} touches)</li>" for item in top_files]
        ) or "<li>No changed files detected in selected window.</li>"
        return (
            "<p class='subhead'>Project Recap</p>"
            "<p class='subhead'>Recent Activity</p>"
            f"<ul>{''.join([f'<li>{_escape(x)}</li>' for x in items])}</ul>"
            f"<p class='subhead'>Most touched files</p><ul>{top_html}</ul>"
        )

    if analysis_type == "plan-review":
        plan = context_payload.get("plan_review", {})
        if not plan.get("available"):
            return f"<p class='note'>{_escape(plan.get('reason', 'Plan review context unavailable.'))}</p>"
        missing = plan.get("referenced_missing_files", [])
        existing = plan.get("referenced_existing_files", [])
        missing_html = "".join([f"<li><code>{_escape(path)}</code></li>" for path in missing[:20]]) or "<li>None</li>"
        existing_html = "".join([f"<li><code>{_escape(path)}</code></li>" for path in existing[:20]]) or "<li>None</li>"
        return (
            "<ul>"
            f"<li>Plan file: <code>{_escape(plan.get('plan_file', 'n/a'))}</code></li>"
            f"<li>Plan headings: {plan.get('heading_count', 0)}</li>"
            f"<li>Referenced files: {plan.get('referenced_files_count', 0)}</li>"
            f"<li>Missing referenced files: {len(missing)}</li>"
            "</ul>"
            "<div class='split'>"
            "<div><p class='subhead'>Referenced files found</p><ul>"
            f"{existing_html}</ul></div>"
            "<div><p class='subhead'>Referenced files missing</p><ul>"
            f"{missing_html}</ul></div>"
            "</div>"
        )

    if analysis_type == "diff-review":
        diff = context_payload.get("diff_review", {})
        if not diff.get("available"):
            return f"<p class='note'>{_escape(diff.get('reason', 'Diff context unavailable.'))}</p>"
        rows = [
            ["Git Ref", str(diff.get("git_ref", "n/a"))],
            ["Changed Files", str(diff.get("changed_file_count", 0))],
            ["Added", str(diff.get("added_files", 0))],
            ["Modified", str(diff.get("modified_files", 0))],
            ["Deleted", str(diff.get("deleted_files", 0))],
            ["Renamed", str(diff.get("renamed_files", 0))],
        ]
        return (
            "<table class='mini-table'><tbody>"
            f"{_table_rows(rows)}"
            "</tbody></table>"
        )

    highlights = context_payload.get("highlights", [])
    highlight_html = "".join([f"<li>{_escape(item)}</li>" for item in highlights]) or "<li>No additional highlights.</li>"
    return f"<ul>{highlight_html}</ul>"


def _diagram_cards(output_root: Path, diagram_manifest: Dict[str, Any]) -> str:
    cards: List[str] = []
    diagrams_dir = output_root / "diagrams"
    excalidraw_report = common.read_json(output_root / "meta" / "excalidraw_report.json", default={})
    excalidraw_map = {
        item.get("diagram", ""): item
        for item in excalidraw_report.get("results", [])
        if item.get("diagram")
    }
    for idx, file_name in enumerate(diagram_manifest.get("diagram_files", []), start=1):
        mmd_path = diagrams_dir / file_name
        mmd_text = common.read_text(mmd_path)
        if not mmd_text.strip():
            continue
        title = Path(file_name).stem.replace("_", " ").title()
        links = [
            f'<a href="../diagrams/svg/{_escape(Path(file_name).stem)}.svg">SVG</a>',
            f'<a href="../diagrams/png/{_escape(Path(file_name).stem)}.png">PNG</a>',
        ]
        excalidraw_item = excalidraw_map.get(file_name, {})
        if excalidraw_item.get("status") == "ok":
            links.append(f'<a href="../diagrams/{_escape(excalidraw_item.get("scene", ""))}">Excalidraw</a>')
        cards.append(
            f"""
<article class="card diagram-card">
  <h3>{_escape(title)}</h3>
  <div class="mermaid-wrap" data-initial-zoom="{1.1 if idx <= 3 else 1.0}">
    <div class="zoom-controls">
      <button type="button" data-action="zoom-in">+</button>
      <button type="button" data-action="zoom-out">−</button>
      <button type="button" data-action="zoom-reset">↺</button>
    </div>
    <pre class="mermaid">{_escape(mmd_text)}</pre>
  </div>
  <p class="meta-links">
    {" ".join(links)}
  </p>
</article>
"""
        )
    return "\n".join(cards) if cards else "<p class='note'>No diagrams generated.</p>"


def generate_html(
    output_root: Path,
    source: str,
    mode: str,
    audience: str,
    overview_length: str,
    analysis_type: str,
    stack_payload: Dict[str, Any],
    index_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    llm_payload: Dict[str, Any],
    diagram_manifest: Dict[str, Any],
    context_payload: Dict[str, Any],
    verification_payload: Dict[str, Any],
) -> Dict[str, Any]:
    html_dir = common.ensure_dir(output_root / "html")
    html_path = html_dir / "ONBOARDING.html"

    repo_name = stack_payload.get("repo_name", common.detect_repo_name(source, output_root))
    summary = (llm_payload.get("repo_summary_paragraph") or "").strip()
    if not summary:
        summary = (
            f"{repo_name} follows {stack_payload.get('architecture_pattern', 'a custom')} architecture "
            f"with primary language {stack_payload.get('primary_language', 'Unknown')}."
        )

    languages = stack_payload.get("languages", {})
    lang_text = ", ".join([f"{k} ({v})" for k, v in list(languages.items())[:8]]) or "Unknown"
    frameworks = ", ".join(stack_payload.get("frameworks", [])[:8]) or "None detected"
    modules = index_payload.get("modules", [])[:20]
    entrypoints = entry_payload.get("entrypoints", [])[:30]
    lifecycle = flow_payload.get("request_lifecycle", [])
    critical_paths = flow_payload.get("critical_paths", [])[:8]

    module_rows = _table_rows(
        [[m.get("name", ""), str(m.get("file_count", 0)), str(m.get("type", ""))] for m in modules]
    )
    entry_rows = _table_rows([[e.get("path", ""), e.get("kind", "")] for e in entrypoints])
    path_rows = _table_rows(
        [[p.get("name", "Path"), " -> ".join([str(s) for s in p.get("steps", [])[:7]])] for p in critical_paths]
    )
    verification_rows = _table_rows(
        [
            [
                fact.get("claim_id", ""),
                fact.get("status", ""),
                ", ".join([loc.get("path", "") for loc in fact.get("evidence_locations", [])[:3]]),
            ]
            for fact in verification_payload.get("facts", [])[:40]
        ]
    )

    mode_context_html = _mode_context_block(analysis_type, context_payload)
    diagram_cards_html = _diagram_cards(output_root, diagram_manifest)

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(repo_name)} - Code Explainer</title>
  <style>
    :root {{
      --bg: #f7f4ee;
      --surface: #ffffff;
      --surface-muted: #f1ece3;
      --text: #2b2317;
      --text-dim: #6f6453;
      --border: rgba(0, 0, 0, 0.09);
      --accent: #0f766e;
      --accent-dim: rgba(15, 118, 110, 0.12);
      --warn: #b45309;
      --danger: #b91c1c;
      --hero: #fff8ef;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #111414;
        --surface: #1a1f1f;
        --surface-muted: #212828;
        --text: #e5eee9;
        --text-dim: #9eb1a8;
        --border: rgba(255, 255, 255, 0.12);
        --accent: #34d399;
        --accent-dim: rgba(52, 211, 153, 0.14);
        --warn: #f59e0b;
        --danger: #f87171;
        --hero: #1e2422;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(ellipse at 15% 0%, var(--accent-dim) 0%, transparent 40%),
        var(--bg);
    }}
    .layout {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: 250px minmax(0, 1fr);
      gap: 24px;
    }}
    .toc {{
      position: sticky;
      top: 18px;
      align-self: start;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
    }}
    .toc h2 {{ font-size: 14px; margin: 0 0 12px; color: var(--text-dim); }}
    .toc a {{
      display: block;
      padding: 8px 10px;
      border-radius: 8px;
      text-decoration: none;
      color: var(--text);
      font-size: 13px;
    }}
    .toc a:hover {{ background: var(--surface-muted); }}
    main {{
      display: grid;
      gap: 20px;
      min-width: 0;
    }}
    section {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      min-width: 0;
    }}
    .hero {{
      background: var(--hero);
      border-color: color-mix(in srgb, var(--accent) 35%, var(--border) 65%);
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
      padding: 24px;
    }}
    .hero h1 {{ margin: 0 0 8px; font-size: clamp(26px, 4vw, 42px); }}
    .meta {{
      color: var(--text-dim);
      font-size: 13px;
      margin-bottom: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
    }}
    .subgrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .card {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      background: var(--surface-muted);
      min-width: 0;
      overflow-wrap: break-word;
    }}
    .card h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .subhead {{
      margin: 10px 0 6px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-dim);
    }}
    .split {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      text-align: left;
      padding: 8px 10px;
      vertical-align: top;
      overflow-wrap: break-word;
      min-width: 0;
    }}
    th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      position: sticky;
      top: 0;
      background: var(--surface);
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 360px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface);
    }}
    details {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      background: var(--surface-muted);
      margin-top: 12px;
    }}
    details summary {{
      cursor: pointer;
      font-weight: 600;
      color: var(--text);
    }}
    .note {{ color: var(--text-dim); font-size: 13px; }}
    .diagram-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .diagram-card {{ background: var(--surface); }}
    .mermaid-wrap {{
      position: relative;
      margin-top: 8px;
      border: 1px solid var(--border);
      border-radius: 10px;
      min-height: 420px;
      max-height: 620px;
      overflow: auto;
      padding: 42px 12px 12px;
      background: var(--surface-muted);
    }}
    .mermaid {{
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 340px;
      transform-origin: top center;
    }}
    .mermaid-wrap.is-zoomed {{ cursor: grab; }}
    .mermaid-wrap.is-panning {{ cursor: grabbing; user-select: none; }}
    .zoom-controls {{
      position: sticky;
      top: 0;
      display: flex;
      justify-content: flex-end;
      gap: 4px;
      margin-bottom: 8px;
      z-index: 3;
      pointer-events: auto;
    }}
    .zoom-controls button {{
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      border-radius: 8px;
      width: 28px;
      height: 28px;
      cursor: pointer;
    }}
    .meta-links {{
      display: flex;
      gap: 10px;
      font-size: 12px;
      margin-top: 8px;
    }}
    .meta-links a {{ color: var(--accent); text-decoration: none; }}
    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .toc {{
        position: sticky;
        top: 0;
        z-index: 20;
        overflow-x: auto;
        white-space: nowrap;
      }}
      .toc a {{ display: inline-block; }}
      .subgrid, .split, .diagram-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <nav class="toc">
      <h2>Navigate</h2>
      <a href="#summary">Summary</a>
      <a href="#mode-context">Mode Context</a>
      <a href="#architecture">Architecture</a>
      <a href="#modules">Modules</a>
      <a href="#flows">Flows</a>
      <a href="#dependencies">Dependencies</a>
      <a href="#evidence">Evidence</a>
    </nav>
    <main>
      <section id="summary" class="hero">
        <h1>{_escape(repo_name)} Explainer</h1>
        <div class="meta">
          <span>Source: <code>{_escape(source)}</code></span>
          <span>Type: <code>{_escape(analysis_type)}</code></span>
          <span>Mode: <code>{_escape(mode)}</code></span>
          <span>Audience: <code>{_escape(audience)}</code></span>
          <span>Length: <code>{_escape(overview_length)}</code></span>
        </div>
        <p>{_escape(summary)}</p>
        <div class="subgrid">
          <article class="card">
            <h3>Stack</h3>
            <p><strong>Languages:</strong> {_escape(lang_text)}</p>
            <p><strong>Frameworks:</strong> {_escape(frameworks)}</p>
            <p><strong>Architecture:</strong> {_escape(stack_payload.get('architecture_pattern', 'Unknown'))}</p>
          </article>
          <article class="card">
            <h3>Coverage</h3>
            <p>Docs parsed: <strong>{docs_payload.get('parsed_count', 0)}/{docs_payload.get('discovered_count', 0)}</strong></p>
            <p>Entrypoints: <strong>{entry_payload.get('count', len(entry_payload.get('entrypoints', [])))}</strong></p>
            <p>Internal edges: <strong>{dep_payload.get('internal_edge_count', 0)}</strong></p>
          </article>
        </div>
      </section>

      <section id="mode-context">
        <h2>Mode-Specific Context</h2>
        {mode_context_html}
      </section>

      <section id="architecture">
        <h2>Architecture Diagrams</h2>
        <p class="note">Interactive Mermaid diagrams. Use +/-/reset, Ctrl/Cmd + wheel, and drag-pan when zoomed.</p>
        <div class="diagram-grid">
          {diagram_cards_html}
        </div>
      </section>

      <section id="modules">
        <h2>Module Landscape</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Module</th><th>Files</th><th>Type</th></tr>
            </thead>
            <tbody>
              {module_rows}
            </tbody>
          </table>
        </div>
      </section>

      <section id="flows">
        <h2>Flow Tracing</h2>
        <p><strong>Request lifecycle:</strong> {_escape(' -> '.join([str(x) for x in lifecycle])) or 'Not detected'}</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Critical Path</th><th>Steps</th></tr>
            </thead>
            <tbody>
              {path_rows}
            </tbody>
          </table>
        </div>
      </section>

      <section id="dependencies">
        <h2>Dependency View</h2>
        <details open>
          <summary>Entrypoints</summary>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Path</th><th>Kind</th></tr></thead>
              <tbody>{entry_rows}</tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>External dependency manifests</summary>
          <pre>{_escape(json.dumps(dep_payload.get("external_dependencies", {}), indent=2, ensure_ascii=False))}</pre>
        </details>
      </section>

      <section id="evidence">
        <h2>Verification Checkpoint</h2>
        <p class="note">Evidence gathered before narrative generation, with source file locations.</p>
        <div class="table-wrap">
          <table class="mini-table">
            <thead><tr><th>Claim</th><th>Status</th><th>Evidence Sources</th></tr></thead>
            <tbody>{verification_rows}</tbody>
          </table>
        </div>
      </section>
    </main>
  </div>

  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    mermaid.initialize({{
      startOnLoad: false,
      theme: 'base',
      look: 'classic',
      flowchart: {{ curve: 'basis' }},
      themeVariables: {{
        primaryColor: isDark ? '#1f3330' : '#e6f4ee',
        primaryTextColor: isDark ? '#e5eee9' : '#2b2317',
        primaryBorderColor: isDark ? '#34d399' : '#0f766e',
        lineColor: isDark ? '#87a79b' : '#5e6f68',
        secondaryColor: isDark ? '#262b2b' : '#eef1ef',
        tertiaryColor: isDark ? '#2a312f' : '#f1eee8',
        background: isDark ? '#1a1f1f' : '#ffffff',
        fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
        fontSize: '17px'
      }}
    }});

    function applyZoom(wrap, next) {{
      const target = wrap.querySelector('.mermaid');
      const z = Math.max(0.35, Math.min(3.0, next));
      target.dataset.zoom = String(z);
      if ('zoom' in target.style) {{
        target.style.zoom = z;
      }} else {{
        target.style.transform = `scale(${{z}})`;
      }}
      wrap.classList.toggle('is-zoomed', z > 1.01);
    }}

    function initWrap(wrap) {{
      const target = wrap.querySelector('.mermaid');
      const initial = parseFloat(wrap.dataset.initialZoom || '1');
      applyZoom(wrap, initial);

      let panStartX = 0;
      let panStartY = 0;
      let panScrollLeft = 0;
      let panScrollTop = 0;

      wrap.addEventListener('wheel', (e) => {{
        if (!e.ctrlKey && !e.metaKey) return;
        e.preventDefault();
        const current = parseFloat(target.dataset.zoom || '1');
        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        applyZoom(wrap, current * factor);
      }}, {{ passive: false }});

      wrap.addEventListener('mousedown', (e) => {{
        if (e.target.closest('.zoom-controls')) return;
        const current = parseFloat(target.dataset.zoom || '1');
        if (current <= 1.01) return;
        wrap.classList.add('is-panning');
        panStartX = e.clientX;
        panStartY = e.clientY;
        panScrollLeft = wrap.scrollLeft;
        panScrollTop = wrap.scrollTop;
      }});

      window.addEventListener('mousemove', (e) => {{
        if (!wrap.classList.contains('is-panning')) return;
        wrap.scrollLeft = panScrollLeft - (e.clientX - panStartX);
        wrap.scrollTop = panScrollTop - (e.clientY - panStartY);
      }});

      window.addEventListener('mouseup', () => {{
        wrap.classList.remove('is-panning');
      }});
    }}

    function bindControls() {{
      document.querySelectorAll('.mermaid-wrap').forEach((wrap) => {{
        wrap.querySelectorAll('.zoom-controls button').forEach((button) => {{
          button.addEventListener('click', () => {{
            const target = wrap.querySelector('.mermaid');
            const current = parseFloat(target.dataset.zoom || '1');
            const action = button.dataset.action;
            if (action === 'zoom-in') applyZoom(wrap, current * 1.2);
            if (action === 'zoom-out') applyZoom(wrap, current * 0.8);
            if (action === 'zoom-reset') applyZoom(wrap, parseFloat(wrap.dataset.initialZoom || '1'));
          }});
        }});
      }});
    }}

    mermaid.run().then(() => {{
      bindControls();
      document.querySelectorAll('.mermaid-wrap').forEach(initWrap);
    }}).catch((err) => {{
      console.error('Mermaid render failed', err);
    }});
  </script>
</body>
</html>
"""

    html_path.write_text(html_text, encoding="utf-8")
    payload = {
        "generated_at": common.now_iso(),
        "analysis_type": analysis_type,
        "output_file": common.relative_path(html_path, output_root),
        "diagram_count": len(diagram_manifest.get("diagram_files", [])),
        "section_count": 7,
    }
    common.write_json(output_root / "meta" / "html_generation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate interactive HTML explainer.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--overview-length", default="medium")
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--stack", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--llm-summary", required=True)
    parser.add_argument("--diagram-manifest", required=True)
    parser.add_argument("--explainer-context", required=True)
    parser.add_argument("--verification", required=True)
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    payload = generate_html(
        output_root=output_root,
        source=args.source,
        mode=common.normalize_mode(args.mode),
        audience=args.audience,
        overview_length=args.overview_length,
        analysis_type=args.analysis_type,
        stack_payload=common.read_json(Path(args.stack), default={}),
        index_payload=common.read_json(Path(args.index), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        docs_payload=common.read_json(Path(args.coverage), default={}),
        llm_payload=common.read_json(Path(args.llm_summary), default={}),
        diagram_manifest=common.read_json(Path(args.diagram_manifest), default={}),
        context_payload=common.read_json(Path(args.explainer_context), default={}),
        verification_payload=common.read_json(Path(args.verification), default={}),
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
