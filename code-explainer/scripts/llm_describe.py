#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _normalize_base_url(url: str) -> str:
    clean = (url or DEFAULT_BASE_URL).strip().rstrip("/")
    return clean or DEFAULT_BASE_URL


def _is_interactive_terminal() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except Exception:
        return False


def _confirm_llm_usage() -> bool:
    answer = input("Use LLM to generate narrative summaries for this run? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _prompt_api_key() -> str:
    try:
        return getpass.getpass("Enter LLM API key (input hidden): ").strip()
    except Exception:
        return ""


def _post_json(url: str, api_key: str, payload: Dict[str, Any], timeout: int = 90) -> Tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "code-explainer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")
    except Exception:
        return 0, ""


def _extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _compact_context(
    source: str,
    mode: str,
    audience: str,
    analysis_type: str,
    index_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
) -> Dict[str, Any]:
    modules = []
    for module in index_payload.get("modules", [])[:20]:
        modules.append(
            {
                "name": module.get("name", ""),
                "type": module.get("type", ""),
                "file_count": module.get("file_count", 0),
            }
        )
    docs = []
    for doc in docs_payload.get("parsed_docs", [])[:8]:
        docs.append(
            {
                "path": doc.get("path", ""),
                "title": doc.get("title", ""),
                "summary": doc.get("summary", "")[:320],
            }
        )
    entrypoints = entry_payload.get("entrypoints", [])[:20]
    critical_paths = []
    for path in flow_payload.get("critical_paths", [])[:5]:
        critical_paths.append(
            {
                "name": path.get("name", ""),
                "steps": path.get("steps", [])[:6],
            }
        )
    external_deps = {}
    for manifest, deps in dep_payload.get("external_dependencies", {}).items():
        external_deps[manifest] = deps[:30]

    return {
        "source": source,
        "mode": mode,
        "audience": audience,
        "analysis_type": analysis_type,
        "repo_name": stack_payload.get("repo_name", ""),
        "architecture_pattern": stack_payload.get("architecture_pattern", ""),
        "primary_language": stack_payload.get("primary_language", ""),
        "languages": stack_payload.get("languages", {}),
        "frameworks": stack_payload.get("frameworks", []),
        "modules": modules,
        "entrypoints": entrypoints,
        "critical_paths": critical_paths,
        "request_lifecycle": flow_payload.get("request_lifecycle", []),
        "docs": docs,
        "external_dependencies": external_deps,
        "internal_edge_count": dep_payload.get("internal_edge_count", 0),
        "mode_context": context_payload,
    }


def _request_messages(context_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    system_prompt = (
        "You are a repository onboarding analyst. "
        "Return strict JSON only, no markdown. "
        "Target audience includes PMs, designers, and new engineers. "
        "Do not invent facts not present in context. "
        "If uncertain, state uncertainty explicitly."
    )
    user_prompt = (
        "Using the context, produce JSON with keys:\n"
        "repo_summary_paragraph (string, 90-180 words),\n"
        "directory_summaries (array of objects: name, summary),\n"
        "deep_dive_starters (array of 3-6 concise bullets),\n"
        "confidence_notes (array of 2-5 concise notes).\n"
        "Summaries must be specific and useful for onboarding.\n"
        "Adapt framing to analysis_type (onboarding/project-recap/plan-review/diff-review).\n"
        "Limit directory_summaries to top-level modules in context.\n"
        f"Context:\n{json.dumps(context_payload, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _default_llm_payload(enabled: bool, model: str) -> Dict[str, Any]:
    return {
        "generated_at": common.now_iso(),
        "enabled": enabled,
        "llm_mode": "auto",
        "used": False,
        "asked_before_use": False,
        "consent_granted": False,
        "consent_mode": "implicit",
        "prompted_for_key": False,
        "api_key_source": "none",
        "provider": "openai_compatible",
        "model": model,
        "repo_summary_paragraph": "",
        "directory_summaries": [],
        "deep_dive_starters": [],
        "confidence_notes": [],
        "error": "",
    }


def generate_llm_descriptions(
    repo_root: Path,
    source: str,
    mode: str,
    audience: str,
    analysis_type: str,
    index_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
    entry_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    docs_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
    out_dir: Path,
    llm_mode: str = "auto",
    ask_before_use: bool = False,
    prompt_for_key: bool = False,
) -> Dict[str, Any]:
    llm_mode = (llm_mode or "auto").strip().lower()
    if llm_mode not in {"auto", "required", "off"}:
        llm_mode = "auto"

    model = os.environ.get("CODE_EXPLAINER_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    enabled = llm_mode != "off"
    payload = _default_llm_payload(enabled=enabled, model=model)
    payload["llm_mode"] = llm_mode
    if not enabled:
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    interactive = _is_interactive_terminal()
    payload["consent_granted"] = True
    if interactive:
        payload["consent_mode"] = "interactive"
    else:
        payload["consent_mode"] = "non_interactive"

    if ask_before_use:
        payload["asked_before_use"] = True
        if interactive:
            payload["consent_granted"] = _confirm_llm_usage()
            if not payload["consent_granted"]:
                payload["enabled"] = False
                if llm_mode == "required":
                    payload["error"] = "LLM mode is required, but user declined LLM narrative generation."
                else:
                    payload["error"] = "User declined LLM narrative generation for this run."
                common.write_json(out_dir / "llm_summary.json", payload)
                return payload

    api_key = (
        os.environ.get("CODE_EXPLAINER_LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )
    if api_key:
        payload["api_key_source"] = "env"
    if not api_key and prompt_for_key:
        payload["prompted_for_key"] = True
        if interactive:
            api_key = _prompt_api_key()
            if api_key:
                payload["api_key_source"] = "prompt"

    if not api_key:
        if llm_mode == "required":
            payload["error"] = (
                "LLM mode is required, but no API key was found "
                "(set CODE_EXPLAINER_LLM_API_KEY or OPENAI_API_KEY)."
            )
        else:
            payload["error"] = "No API key found (set CODE_EXPLAINER_LLM_API_KEY or OPENAI_API_KEY)."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    base_url = _normalize_base_url(os.environ.get("CODE_EXPLAINER_LLM_BASE_URL", DEFAULT_BASE_URL))
    endpoint = f"{base_url}/chat/completions"
    context_payload = _compact_context(
        source=source,
        mode=mode,
        audience=audience,
        analysis_type=analysis_type,
        index_payload=index_payload,
        stack_payload=stack_payload,
        entry_payload=entry_payload,
        dep_payload=dep_payload,
        flow_payload=flow_payload,
        docs_payload=docs_payload,
        context_payload=context_payload,
    )

    request_payload = {
        "model": model,
        "temperature": 0.2,
        "messages": _request_messages(context_payload),
    }
    status, body = _post_json(endpoint, api_key, request_payload)
    if status != 200 or not body:
        payload["error"] = f"LLM request failed with status={status or 'network_error'}."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    try:
        response_json = json.loads(body)
    except Exception:
        payload["error"] = "LLM response was not valid JSON envelope."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    content = ""
    choices = response_json.get("choices", [])
    if choices:
        content = (
            (choices[0].get("message") or {}).get("content", "")
            if isinstance(choices[0], dict)
            else ""
        )
    parsed = _extract_json(content)
    if not parsed:
        payload["error"] = "LLM response content did not include parseable JSON."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    repo_summary = str(parsed.get("repo_summary_paragraph", "")).strip()
    directory_summaries = parsed.get("directory_summaries", [])
    deep_dive_starters = parsed.get("deep_dive_starters", [])
    confidence_notes = parsed.get("confidence_notes", [])
    if not isinstance(directory_summaries, list):
        directory_summaries = []
    if not isinstance(deep_dive_starters, list):
        deep_dive_starters = []
    if not isinstance(confidence_notes, list):
        confidence_notes = []

    payload.update(
        {
            "used": bool(repo_summary or directory_summaries),
            "repo_summary_paragraph": repo_summary,
            "directory_summaries": directory_summaries[:20],
            "deep_dive_starters": [str(x) for x in deep_dive_starters[:8]],
            "confidence_notes": [str(x) for x in confidence_notes[:8]],
            "error": "",
            "request_context": context_payload,
        }
    )
    common.write_json(out_dir / "llm_summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LLM narrative summaries for repository onboarding.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--audience", default="nontech")
    parser.add_argument("--analysis-type", default="onboarding")
    parser.add_argument("--index", required=True)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--entrypoints", required=True)
    parser.add_argument("--dependencies", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--explainer-context", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--llm-mode", default="auto", choices=["auto", "required", "off"])
    parser.add_argument("--enabled", default="")
    parser.add_argument("--ask-before-use", default="false")
    parser.add_argument("--prompt-for-key", default="false")
    args = parser.parse_args()

    llm_mode = (args.llm_mode or "auto").strip().lower()
    if args.enabled.strip():
        llm_mode = "auto" if common.bool_from_string(args.enabled) else "off"

    payload = generate_llm_descriptions(
        repo_root=Path(args.repo).resolve(),
        source=args.source,
        mode=common.normalize_mode(args.mode),
        audience=args.audience,
        analysis_type=args.analysis_type,
        index_payload=common.read_json(Path(args.index), default={}),
        stack_payload=common.read_json(Path(args.stack), default={}),
        entry_payload=common.read_json(Path(args.entrypoints), default={}),
        dep_payload=common.read_json(Path(args.dependencies), default={}),
        flow_payload=common.read_json(Path(args.flows), default={}),
        docs_payload=common.read_json(Path(args.coverage), default={}),
        context_payload=common.read_json(Path(args.explainer_context), default={}),
        out_dir=Path(args.output).resolve(),
        llm_mode=llm_mode,
        ask_before_use=common.bool_from_string(args.ask_before_use),
        prompt_for_key=common.bool_from_string(args.prompt_for_key),
    )
    print(json.dumps({"used": payload.get("used", False), "error": payload.get("error", "")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
