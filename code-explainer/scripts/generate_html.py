#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _escape(text: str) -> str:
    return html.escape(text or "", quote=True)


def _extract_section(markdown_text: str, heading: str) -> str:
    if not markdown_text.strip():
        return ""
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown_text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _clean_inline_md(text: str) -> str:
    out = text
    out = re.sub(r"`([^`]+)`", r"\1", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
    out = re.sub(r"\*([^*]+)\*", r"\1", out)
    return out.strip()


def _paragraphs_from_markdown(section: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", section) if b.strip()]
    rows: List[str] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(re.match(r"^[-*]\s+", ln) or re.match(r"^\d+\.\s+", ln) for ln in lines):
            continue
        text = _clean_inline_md(" ".join(lines))
        if text:
            rows.append(f"<p>{_escape(text)}</p>")
    return "\n".join(rows)


def _bullet_list_from_markdown(section: str) -> str:
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        m = re.match(r"^[-*]\s+(.+)$", stripped)
        if not m:
            continue
        items.append(_escape(_clean_inline_md(m.group(1))))
    if not items:
        return "<p class='note'>No items available.</p>"
    lis = "".join([f"<li>{item}</li>" for item in items])
    return f"<ul>{lis}</ul>"


def _numbered_list_from_markdown(section: str) -> str:
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if not m:
            continue
        items.append(_escape(_clean_inline_md(m.group(1))))
    if not items:
        return "<p class='note'>No steps available.</p>"
    lis = "".join([f"<li>{item}</li>" for item in items])
    return f"<ol>{lis}</ol>"


def _table_rows(items: List[List[str]]) -> str:
    rows = []
    for row in items:
        cells = "".join([f"<td>{_escape(cell)}</td>" for cell in row])
        rows.append(f"<tr>{cells}</tr>")
    return "\n".join(rows)


def _diagram_priority(stem: str) -> int:
    order = [
        "primary_user_flow",
        "request_lifecycle_sequence",
        "module_dependency_graph",
        "c4_container",
        "c4_context",
        "critical_path_sequence",
        "trust_boundary_flow",
        "data_lineage_flow",
        "where_to_change_map",
    ]
    try:
        return order.index(stem)
    except ValueError:
        return 999


def _diagram_title(stem: str) -> str:
    titles = {
        "primary_user_flow": "Primary User Flow",
        "request_lifecycle_sequence": "Request Lifecycle Sequence",
        "module_dependency_graph": "Module Dependency Graph",
        "c4_container": "C4 Container View",
        "c4_context": "C4 Context View",
        "critical_path_sequence": "Critical Path Sequence",
        "trust_boundary_flow": "Trust Boundary Flow",
        "data_lineage_flow": "Data Lineage",
        "where_to_change_map": "Where To Change Map",
    }
    return titles.get(stem, stem.replace("_", " ").title())


def _diagram_cards(diagram_manifest: Dict[str, Any]) -> str:
    stems = [Path(name).stem for name in diagram_manifest.get("diagram_files", [])]
    stems.sort(key=_diagram_priority)
    cards: List[str] = []
    for stem in stems:
        title = _diagram_title(stem)
        svg_src = f"../diagrams/svg/{stem}.svg"
        png_src = f"../diagrams/png/{stem}.png"
        cards.append(
            f"""
<article class="diagram-card">
  <div class="diagram-head">
    <h3>{_escape(title)}</h3>
    <div class="diagram-actions">
      <button class="btn-open" data-title="{_escape(title)}" data-src="{_escape(svg_src)}" data-fallback="{_escape(png_src)}" type="button">Open Full Screen</button>
      <a href="{_escape(svg_src)}" target="_blank" rel="noopener">SVG</a>
      <a href="{_escape(png_src)}" target="_blank" rel="noopener">PNG</a>
    </div>
  </div>
  <div class="diagram-frame">
    <img class="diagram-preview" src="{_escape(svg_src)}" data-fallback="{_escape(png_src)}" alt="{_escape(title)} diagram" loading="lazy" />
  </div>
</article>
"""
        )
    return "\n".join(cards) if cards else "<p class='note'>No diagrams generated.</p>"


def _mode_context_block(analysis_type: str, context_payload: Dict[str, Any]) -> str:
    if analysis_type == "project-recap":
        recap = context_payload.get("project_recap", {})
        if not recap.get("available"):
            return f"<p class='note'>{_escape(recap.get('reason', 'Project recap context unavailable.'))}</p>"
        items = [
            f"Commit window: {recap.get('since', context_payload.get('since', 'n/a'))}",
            f"Commits in window: {recap.get('commit_count', 0)}",
            f"Contributors: {len(recap.get('contributors', []))}",
        ]
        return "<ul>" + "".join([f"<li>{_escape(item)}</li>" for item in items]) + "</ul>"
    if analysis_type == "plan-review":
        plan = context_payload.get("plan_review", {})
        if not plan.get("available"):
            return f"<p class='note'>{_escape(plan.get('reason', 'Plan review context unavailable.'))}</p>"
        return (
            "<ul>"
            f"<li>Plan file: <code>{_escape(plan.get('plan_file', 'n/a'))}</code></li>"
            f"<li>Referenced files: {plan.get('referenced_files_count', 0)}</li>"
            f"<li>Missing references: {len(plan.get('referenced_missing_files', []))}</li>"
            "</ul>"
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
        ]
        return "<table><tbody>" + _table_rows(rows) + "</tbody></table>"
    highlights = context_payload.get("highlights", [])
    if not highlights:
        return "<p class='note'>Onboarding mode: purpose, module map, and key flows.</p>"
    return "<ul>" + "".join([f"<li>{_escape(str(item))}</li>" for item in highlights[:8]]) + "</ul>"


def _fallback_summary(
    repo_name: str,
    stack_payload: Dict[str, Any],
    index_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
) -> str:
    primary_language = stack_payload.get("primary_language", "Unknown")
    module_count = len(index_payload.get("modules", []))
    entry_count = int(entry_payload.get("count", len(entry_payload.get("entrypoints", []))))
    flow_steps = flow_payload.get("primary_user_flow", {}).get("steps", [])[:4]
    flow_clause = " -> ".join([str(step) for step in flow_steps]) if flow_steps else "intake -> analysis -> outputs"
    return (
        f"{repo_name} is mostly a {primary_language} project with about {module_count} main project areas. "
        f"I found around {entry_count} likely starting files. "
        f"A typical journey through the code looks like: {flow_clause}."
    )


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
    overview_md = common.read_text(output_root / "overview" / "OVERVIEW.md")
    deep_md = common.read_text(output_root / "deep" / "SYSTEM_DEEP_DIVE.md")

    summary_section = _extract_section(overview_md, "What This Repository Does")
    flow_section = _extract_section(overview_md, "How Information Flows")
    map_section = _extract_section(overview_md, "Directory Map (Plain Language)")
    start_here_section = _extract_section(overview_md, "If You Are New, Start Here")
    deep_critical_section = _extract_section(deep_md, "2) Important Journeys Through The Code")

    summary_html = _paragraphs_from_markdown(summary_section)
    if not summary_html:
        summary = (llm_payload.get("repo_summary_paragraph") or "").strip() or _fallback_summary(
            repo_name, stack_payload, index_payload, entry_payload, flow_payload
        )
        summary_html = f"<p>{_escape(summary)}</p>"

    flow_line = _clean_inline_md(flow_section).strip() if flow_section else ""
    if not flow_line:
        flow_line = " -> ".join([str(x) for x in flow_payload.get("request_lifecycle", [])]) or "Not detected"

    languages = stack_payload.get("languages", {})
    lang_text = ", ".join([f"{k} ({v})" for k, v in list(languages.items())[:8]]) or "Unknown"
    frameworks = ", ".join(stack_payload.get("frameworks", [])[:8]) or "None detected"
    architecture_raw = stack_payload.get("architecture_pattern", "Unknown")
    architecture_human = (
        f"Custom project layout (detector label: {architecture_raw})"
        if architecture_raw == "Custom/Undetected"
        else architecture_raw
    )
    modules = index_payload.get("modules", [])[:20]
    entrypoints = entry_payload.get("entrypoints", [])[:30]
    critical_paths = flow_payload.get("critical_paths", [])[:8]

    module_rows = _table_rows(
        [[m.get("name", ""), str(m.get("file_count", 0)), str(m.get("type", ""))] for m in modules]
    )
    entry_rows = _table_rows([[e.get("path", ""), e.get("kind", "")] for e in entrypoints])
    path_rows = _table_rows(
        [[p.get("name", "Path"), " -> ".join([str(s) for s in p.get("plain_steps", p.get("steps", []))[:9]])] for p in critical_paths]
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
    diagram_cards_html = _diagram_cards(diagram_manifest)
    mode_context_html = _mode_context_block(analysis_type, context_payload)
    map_html = _bullet_list_from_markdown(map_section)
    start_here_html = _numbered_list_from_markdown(start_here_section)
    critical_html = _bullet_list_from_markdown(deep_critical_section)

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(repo_name)} - Code Explainer</title>
  <style>
    :root {{
      --bg: #f4f0e7;
      --panel: #fffdf8;
      --panel-2: #f6efe1;
      --text: #2f2619;
      --muted: #6e6453;
      --line: rgba(0,0,0,0.1);
      --accent: #0f766e;
      --accent-soft: rgba(15,118,110,0.12);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #141816;
        --panel: #1d2421;
        --panel-2: #24302b;
        --text: #e7efe9;
        --muted: #9fb3a8;
        --line: rgba(255,255,255,0.14);
        --accent: #34d399;
        --accent-soft: rgba(52,211,153,0.14);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background: radial-gradient(circle at 15% 0%, var(--accent-soft), transparent 35%), var(--bg);
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    .layout {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: 240px minmax(0,1fr);
      gap: 20px;
    }}
    .toc {{
      position: sticky;
      top: 16px;
      align-self: start;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
      padding: 12px;
    }}
    .toc h2 {{ margin: 0 0 10px; font-size: 13px; color: var(--muted); }}
    .toc a {{
      display: block;
      padding: 8px 10px;
      border-radius: 8px;
      color: var(--text);
      text-decoration: none;
      font-size: 13px;
    }}
    .toc a:hover {{ background: var(--panel-2); }}
    main {{ display: grid; gap: 16px; }}
    section {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
      padding: 20px;
    }}
    .hero {{
      background: linear-gradient(130deg, var(--panel), var(--panel-2));
      box-shadow: 0 10px 28px rgba(0,0,0,0.08);
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(26px, 4vw, 42px); }}
    h2 {{ margin: 0 0 12px; font-size: 22px; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 12px;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0,1fr));
      gap: 12px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel-2);
      padding: 12px;
    }}
    .note {{ color: var(--muted); font-size: 13px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 8px 10px;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: auto;
      max-height: 360px;
      background: var(--panel);
    }}
    .diagram-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0,1fr));
      gap: 14px;
    }}
    .diagram-card {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel-2);
      padding: 12px;
    }}
    .diagram-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .diagram-head h3 {{ margin: 0; font-size: 16px; }}
    .diagram-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      font-size: 12px;
    }}
    .diagram-actions a {{
      color: var(--accent);
      text-decoration: none;
      padding: 4px 6px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: var(--panel);
    }}
    .btn-open {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      border-radius: 8px;
      padding: 6px 10px;
      cursor: pointer;
      font-size: 12px;
      font-family: inherit;
    }}
    .diagram-frame {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #ffffff;
      height: 340px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: auto;
      padding: 8px;
    }}
    .diagram-preview {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      display: block;
      cursor: zoom-in;
    }}
    .lightbox {{
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.85);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 20px;
    }}
    .lightbox.open {{ display: flex; }}
    .lightbox-inner {{
      width: min(96vw, 1600px);
      height: min(92vh, 1000px);
      background: #ffffff;
      border-radius: 12px;
      padding: 12px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 10px;
    }}
    .lightbox-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }}
    .lightbox-head h3 {{ margin: 0; font-size: 16px; color: #222; }}
    .lightbox-close {{
      border: 1px solid #ddd;
      background: #fff;
      border-radius: 8px;
      padding: 6px 10px;
      cursor: pointer;
    }}
    .lightbox-canvas {{
      overflow: auto;
      border: 1px solid #ddd;
      border-radius: 10px;
      background: #fff;
    }}
    .lightbox-img {{
      width: 100%;
      height: auto;
      min-width: 900px;
      display: block;
    }}
    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .toc {{ position: static; }}
      .diagram-grid {{ grid-template-columns: 1fr; }}
      .grid2 {{ grid-template-columns: 1fr; }}
      .diagram-frame {{ height: 300px; }}
      .lightbox-img {{ min-width: 640px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <nav class="toc">
      <h2>Navigate</h2>
      <a href="#summary">Summary</a>
      <a href="#diagrams">Visual Walkthrough</a>
      <a href="#modules">Project Areas</a>
      <a href="#flows">How Work Moves</a>
      <a href="#evidence">Evidence</a>
    </nav>
    <main>
      <section id="summary" class="hero">
        <h1>{_escape(repo_name)} Onboarding Explainer</h1>
        <div class="meta">
          <span>Source: <code>{_escape(source)}</code></span>
          <span>Mode: <code>{_escape(mode)}</code></span>
          <span>Audience: <code>{_escape(audience)}</code></span>
          <span>Type: <code>{_escape(analysis_type)}</code></span>
          <span>Length: <code>{_escape(overview_length)}</code></span>
        </div>
        {summary_html}
        <div class="grid2">
          <article class="panel">
            <strong>Quick Facts</strong>
            <p>Project shape: <strong>{_escape(architecture_human)}</strong></p>
            <p>Languages: <strong>{_escape(lang_text)}</strong></p>
            <p>Frameworks: <strong>{_escape(frameworks)}</strong></p>
            <p>Starting files found: <strong>{entry_payload.get('count', len(entry_payload.get('entrypoints', [])))}</strong></p>
          </article>
          <article class="panel">
            <strong>Best First Steps</strong>
            {start_here_html}
          </article>
        </div>
      </section>

      <section>
        <h2>What Context Was Used</h2>
        {mode_context_html}
      </section>

      <section id="diagrams">
        <h2>Visual Walkthrough</h2>
        <p class="note">These visuals come from the same generated files as the markdown docs. Read inline or open full screen.</p>
        <div class="diagram-grid">
          {diagram_cards_html}
        </div>
      </section>

      <section id="modules">
        <h2>Main Project Areas</h2>
        {map_html}
        <div class="table-wrap">
          <table>
            <thead><tr><th>Module</th><th>Files</th><th>Type</th></tr></thead>
            <tbody>{module_rows}</tbody>
          </table>
        </div>
      </section>

      <section id="flows">
        <h2>How Work Moves Through The Project</h2>
        <p><strong>Main flow:</strong> {_escape(flow_line)}</p>
        <h3>Important Journeys</h3>
        {critical_html}
        <div class="table-wrap">
          <table>
            <thead><tr><th>Path</th><th>Steps</th></tr></thead>
            <tbody>{path_rows}</tbody>
          </table>
        </div>
      </section>

      <section id="evidence">
        <h2>How Sure This Explanation Is</h2>
        <div class="grid2">
          <article class="panel">
            <p>Docs parsed: <strong>{docs_payload.get('parsed_count', 0)}/{docs_payload.get('discovered_count', 0)}</strong></p>
            <p>Starting files found: <strong>{entry_payload.get('count', len(entry_payload.get('entrypoints', [])))}</strong></p>
            <p>File links mapped: <strong>{dep_payload.get('internal_edge_count', 0)}</strong></p>
          </article>
          <article class="panel">
            <p class="note">This HTML is aligned to generated markdown and diagram artifacts for the same run.</p>
          </article>
        </div>
        <h3>Starting Files</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>File</th><th>Why it is likely a start file</th></tr></thead>
            <tbody>{entry_rows}</tbody>
          </table>
        </div>
        <h3>Evidence Behind Claims</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Claim</th><th>Status</th><th>Evidence Sources</th></tr></thead>
            <tbody>{verification_rows}</tbody>
          </table>
        </div>
      </section>
    </main>
  </div>

  <div id="lightbox" class="lightbox" aria-hidden="true">
    <div class="lightbox-inner">
      <div class="lightbox-head">
        <h3 id="lightbox-title">Diagram</h3>
        <button id="lightbox-close" class="lightbox-close" type="button">Close</button>
      </div>
      <div class="lightbox-canvas">
        <img id="lightbox-img" class="lightbox-img" src="" alt="Diagram full view" />
      </div>
    </div>
  </div>

  <script>
    (function() {{
      const lightbox = document.getElementById('lightbox');
      const lightboxImg = document.getElementById('lightbox-img');
      const lightboxTitle = document.getElementById('lightbox-title');
      const closeBtn = document.getElementById('lightbox-close');

      function fallbackImg(img) {{
        const fallback = img.getAttribute('data-fallback');
        if (fallback && img.getAttribute('src') !== fallback) {{
          img.setAttribute('src', fallback);
        }}
      }}

      document.querySelectorAll('img.diagram-preview').forEach((img) => {{
        img.addEventListener('error', () => fallbackImg(img));
        img.addEventListener('click', () => {{
          lightboxTitle.textContent = img.getAttribute('alt') || 'Diagram';
          lightboxImg.src = img.getAttribute('src');
          lightboxImg.setAttribute('data-fallback', img.getAttribute('data-fallback') || '');
          lightbox.classList.add('open');
          lightbox.setAttribute('aria-hidden', 'false');
        }});
      }});

      document.querySelectorAll('.btn-open').forEach((btn) => {{
        btn.addEventListener('click', () => {{
          const src = btn.getAttribute('data-src') || '';
          const fallback = btn.getAttribute('data-fallback') || '';
          const title = btn.getAttribute('data-title') || 'Diagram';
          lightboxTitle.textContent = title;
          lightboxImg.src = src;
          lightboxImg.setAttribute('data-fallback', fallback);
          lightbox.classList.add('open');
          lightbox.setAttribute('aria-hidden', 'false');
        }});
      }});

      lightboxImg.addEventListener('error', () => {{
        const fallback = lightboxImg.getAttribute('data-fallback') || '';
        if (fallback && lightboxImg.src !== fallback) {{
          lightboxImg.src = fallback;
        }}
      }});

      closeBtn.addEventListener('click', () => {{
        lightbox.classList.remove('open');
        lightbox.setAttribute('aria-hidden', 'true');
      }});

      lightbox.addEventListener('click', (e) => {{
        if (e.target === lightbox) {{
          lightbox.classList.remove('open');
          lightbox.setAttribute('aria-hidden', 'true');
        }}
      }});

      document.addEventListener('keydown', (e) => {{
        if (e.key === 'Escape') {{
          lightbox.classList.remove('open');
          lightbox.setAttribute('aria-hidden', 'true');
        }}
      }});
    }})();
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
        "section_count": 6,
        "html_uses_rendered_assets": True,
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
