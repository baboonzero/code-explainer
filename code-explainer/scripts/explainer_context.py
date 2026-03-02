#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


ANALYSIS_TYPES = {"onboarding", "project-recap", "plan-review", "diff-review"}


def _is_git_repo(repo_root: Path) -> bool:
    code, out, _err = common.run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, timeout=10)
    return code == 0 and out.strip().lower() == "true"


def _parse_stat_line(line: str) -> Dict[str, Any]:
    # Example: " src/app.py | 32 ++++++++++++++++++++-----"
    m = re.match(r"^\s*(.*?)\s+\|\s+(\d+)\s+", line)
    if not m:
        return {}
    return {"path": m.group(1).strip(), "changes": int(m.group(2))}


def _project_recap_context(repo_root: Path, since: str) -> Dict[str, Any]:
    if not _is_git_repo(repo_root):
        return {"available": False, "reason": "Not a git repository."}

    commit_cmd = ["git", "log", "--oneline", f"--since={since}"]
    stat_cmd = ["git", "log", "--stat", "--pretty=format:%h %s", f"--since={since}"]
    files_cmd = ["git", "log", "--name-only", "--pretty=format:", f"--since={since}"]
    shortlog_cmd = ["git", "shortlog", "-sn", f"--since={since}"]
    status_cmd = ["git", "status", "--short"]

    _c1, commit_out, _e1 = common.run_cmd(commit_cmd, cwd=repo_root, timeout=25)
    _c2, stat_out, _e2 = common.run_cmd(stat_cmd, cwd=repo_root, timeout=25)
    _c3, files_out, _e3 = common.run_cmd(files_cmd, cwd=repo_root, timeout=25)
    _c4, shortlog_out, _e4 = common.run_cmd(shortlog_cmd, cwd=repo_root, timeout=25)
    _c5, status_out, _e5 = common.run_cmd(status_cmd, cwd=repo_root, timeout=25)

    commits = [line.strip() for line in commit_out.splitlines() if line.strip()]
    contributors = [line.strip() for line in shortlog_out.splitlines() if line.strip()]
    uncommitted = [line.strip() for line in status_out.splitlines() if line.strip()]

    changed_files = []
    for line in files_out.splitlines():
        rel = line.strip()
        if rel:
            changed_files.append(rel)
    top_files = Counter(changed_files).most_common(12)

    stat_entries = []
    for line in stat_out.splitlines():
        parsed = _parse_stat_line(line)
        if parsed:
            stat_entries.append(parsed)

    return {
        "available": True,
        "since": since,
        "commit_count": len(commits),
        "commit_sample": commits[:25],
        "contributors": contributors[:12],
        "top_changed_files": [{"path": p, "touch_count": c} for p, c in top_files],
        "stat_entries": stat_entries[:40],
        "has_uncommitted_changes": bool(uncommitted),
        "uncommitted_sample": uncommitted[:40],
    }


def _extract_plan_file_refs(text: str) -> List[str]:
    refs: List[str] = []
    backtick_refs = re.findall(r"`([A-Za-z0-9_\-./]+?\.[A-Za-z0-9]+)`", text)
    bare_refs = re.findall(
        r"\b([A-Za-z0-9_\-./]+?\.(?:py|ts|tsx|js|jsx|go|rs|java|kt|md|json|yaml|yml|toml|sql|sh|ps1))\b",
        text,
    )
    for ref in [*backtick_refs, *bare_refs]:
        normalized = ref.strip().replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized and normalized not in refs:
            refs.append(normalized)
    return refs


def _resolve_plan_path(plan_file: str, repo_root: Path) -> Path | None:
    if not plan_file:
        return None
    candidate = Path(plan_file)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    repo_candidate = (repo_root / plan_file).resolve()
    if repo_candidate.exists():
        return repo_candidate
    local_candidate = candidate.resolve()
    if local_candidate.exists():
        return local_candidate
    return None


def _plan_review_context(repo_root: Path, plan_file: str) -> Dict[str, Any]:
    resolved = _resolve_plan_path(plan_file, repo_root)
    if not resolved:
        return {
            "available": False,
            "reason": "No plan file provided or file does not exist.",
            "plan_file": plan_file or "",
        }

    text = common.read_text(resolved)
    if not text.strip():
        return {
            "available": False,
            "reason": "Plan file is empty or unreadable.",
            "plan_file": resolved.as_posix(),
        }

    headings = re.findall(r"^\s{0,3}#{1,4}\s+(.+)$", text, flags=re.MULTILINE)
    refs = _extract_plan_file_refs(text)
    existing: List[str] = []
    missing: List[str] = []
    for ref in refs:
        if (repo_root / ref).exists():
            existing.append(ref)
        else:
            missing.append(ref)

    return {
        "available": True,
        "plan_file": common.relative_path(resolved, repo_root),
        "heading_count": len(headings),
        "headings": headings[:40],
        "referenced_files_count": len(refs),
        "referenced_existing_files": existing[:120],
        "referenced_missing_files": missing[:120],
        "summary_excerpt": " ".join([line.strip() for line in text.splitlines() if line.strip()][:8])[:800],
    }


def _diff_review_context(repo_root: Path, git_ref: str) -> Dict[str, Any]:
    if not _is_git_repo(repo_root):
        return {"available": False, "reason": "Not a git repository.", "git_ref": git_ref}

    ref = git_ref.strip() if git_ref else "main"
    stat_cmd = ["git", "diff", "--stat", ref, "--"]
    status_cmd = ["git", "diff", "--name-status", ref, "--"]
    _c1, stat_out, _e1 = common.run_cmd(stat_cmd, cwd=repo_root, timeout=25)
    _c2, status_out, _e2 = common.run_cmd(status_cmd, cwd=repo_root, timeout=25)

    stat_entries = []
    for line in stat_out.splitlines():
        parsed = _parse_stat_line(line)
        if parsed:
            stat_entries.append(parsed)

    name_status = []
    for line in status_out.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            name_status.append({"status": parts[0], "path": parts[1]})

    added = len([x for x in name_status if x["status"].startswith("A")])
    modified = len([x for x in name_status if x["status"].startswith("M")])
    deleted = len([x for x in name_status if x["status"].startswith("D")])
    renamed = len([x for x in name_status if x["status"].startswith("R")])

    return {
        "available": True,
        "git_ref": ref,
        "changed_file_count": len(name_status),
        "added_files": added,
        "modified_files": modified,
        "deleted_files": deleted,
        "renamed_files": renamed,
        "stat_entries": stat_entries[:120],
        "name_status_sample": name_status[:120],
    }


def build_explainer_context(
    repo_root: Path,
    source: str,
    analysis_type: str,
    out_dir: Path,
    since: str = "2 weeks ago",
    git_ref: str = "main",
    plan_file: str = "",
) -> Dict[str, Any]:
    resolved_type = analysis_type if analysis_type in ANALYSIS_TYPES else "onboarding"
    payload: Dict[str, Any] = {
        "generated_at": common.now_iso(),
        "source": source,
        "analysis_type": resolved_type,
        "repo_root": repo_root.as_posix(),
        "since": since,
        "git_ref": git_ref,
        "plan_file": plan_file,
        "project_recap": {},
        "plan_review": {},
        "diff_review": {},
        "highlights": [],
    }

    if resolved_type == "project-recap":
        recap = _project_recap_context(repo_root, since)
        payload["project_recap"] = recap
        if recap.get("available"):
            payload["highlights"].append(f"{recap.get('commit_count', 0)} commits in the selected window.")
            if recap.get("top_changed_files"):
                payload["highlights"].append(
                    f"Most-touched file: {recap['top_changed_files'][0]['path']} "
                    f"({recap['top_changed_files'][0]['touch_count']} touches)."
                )
    elif resolved_type == "plan-review":
        plan_ctx = _plan_review_context(repo_root, plan_file)
        payload["plan_review"] = plan_ctx
        if plan_ctx.get("available"):
            payload["highlights"].append(
                f"Plan references {plan_ctx.get('referenced_files_count', 0)} files."
            )
            if plan_ctx.get("referenced_missing_files"):
                payload["highlights"].append(
                    f"{len(plan_ctx['referenced_missing_files'])} referenced files are missing in the repo."
                )
    elif resolved_type == "diff-review":
        diff_ctx = _diff_review_context(repo_root, git_ref)
        payload["diff_review"] = diff_ctx
        if diff_ctx.get("available"):
            payload["highlights"].append(
                f"{diff_ctx.get('changed_file_count', 0)} files differ from ref `{diff_ctx.get('git_ref', git_ref)}`."
            )
            payload["highlights"].append(
                f"Added/Modified/Deleted: {diff_ctx.get('added_files', 0)}/"
                f"{diff_ctx.get('modified_files', 0)}/{diff_ctx.get('deleted_files', 0)}."
            )
    else:
        payload["highlights"].append("Onboarding mode focuses on architecture, modules, and critical flows.")

    common.write_json(out_dir / "explainer_context.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build mode-specific context for explainer generation.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--output", required=True)
    parser.add_argument("--since", default="2 weeks ago")
    parser.add_argument("--git-ref", default="main")
    parser.add_argument("--plan-file", default="")
    args = parser.parse_args()

    payload = build_explainer_context(
        repo_root=Path(args.repo).resolve(),
        source=args.source,
        analysis_type=args.analysis_type,
        out_dir=Path(args.output).resolve(),
        since=args.since,
        git_ref=args.git_ref,
        plan_file=args.plan_file,
    )
    print(
        f"Explainer context built: type={payload['analysis_type']} "
        f"highlights={len(payload.get('highlights', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
