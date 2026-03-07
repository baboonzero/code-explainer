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
SKILL_DIR = SCRIPT_DIR.parent
LOCAL_ENV_PATH = SKILL_DIR / ".env"
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
    answer = input("Use LLM to generate the explanation narrative for this run? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _prompt_api_key() -> str:
    try:
        return getpass.getpass("Enter LLM API key (input hidden): ").strip()
    except Exception:
        return ""


def _confirm_persist_key(env_path: Path) -> bool:
    answer = input(f"Save the LLM API key to {env_path.as_posix()} for future runs? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _read_local_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_local_env_key(path: Path, key: str, value: str) -> None:
    existing_lines: List[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    updated = False
    next_lines: List[str] = []
    for raw in existing_lines:
        if raw.strip().startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(raw)
    if not updated:
        next_lines.append(f"{key}={value}")

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def resolve_llm_runtime(
    prompt_for_key: bool = True,
    persist_key_mode: str = "ask",
    require_key: bool = True,
) -> Dict[str, Any]:
    model = os.environ.get("CODE_EXPLAINER_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = _normalize_base_url(os.environ.get("CODE_EXPLAINER_LLM_BASE_URL", DEFAULT_BASE_URL))
    local_env = _read_local_env(LOCAL_ENV_PATH)
    interactive = _is_interactive_terminal()
    prompted = False
    persisted = False
    key_source = ""

    api_key = os.environ.get("CODE_EXPLAINER_LLM_API_KEY", "").strip()
    if api_key:
        key_source = "environment:CODE_EXPLAINER_LLM_API_KEY"
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if api_key:
            key_source = "environment:OPENAI_API_KEY"
    if not api_key:
        api_key = local_env.get("CODE_EXPLAINER_LLM_API_KEY", "").strip()
        if api_key:
            key_source = f"local-env:{LOCAL_ENV_PATH.name}"
    if not api_key:
        api_key = local_env.get("OPENAI_API_KEY", "").strip()
        if api_key:
            key_source = f"local-env:{LOCAL_ENV_PATH.name}"

    if not api_key and prompt_for_key:
        prompted = True
        if not interactive:
            raise RuntimeError(
                "No LLM API key was found and this terminal cannot prompt. Set CODE_EXPLAINER_LLM_API_KEY or OPENAI_API_KEY, "
                f"or add CODE_EXPLAINER_LLM_API_KEY to {LOCAL_ENV_PATH.as_posix()}."
            )
        api_key = _prompt_api_key()
        if not api_key and require_key:
            raise RuntimeError("LLM API key is required for this skill and was not provided.")
        key_source = "prompt"
        persist_mode = (persist_key_mode or "ask").strip().lower()
        should_persist = False
        if api_key:
            if persist_mode == "true":
                should_persist = True
            elif persist_mode == "ask":
                should_persist = _confirm_persist_key(LOCAL_ENV_PATH)
            if should_persist:
                _write_local_env_key(LOCAL_ENV_PATH, "CODE_EXPLAINER_LLM_API_KEY", api_key)
                persisted = True
                key_source = f"local-env:{LOCAL_ENV_PATH.name}"

    if not api_key and require_key:
        raise RuntimeError(
            "No LLM API key found. Set CODE_EXPLAINER_LLM_API_KEY or OPENAI_API_KEY, "
            f"or add CODE_EXPLAINER_LLM_API_KEY to {LOCAL_ENV_PATH.as_posix()}."
        )

    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "prompted_for_key": prompted,
        "persisted_key": persisted,
        "key_source": key_source,
        "env_path": LOCAL_ENV_PATH.as_posix(),
    }


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
            "User-Agent": "code-explainer/2.0",
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
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _default_llm_payload(enabled: bool, model: str) -> Dict[str, Any]:
    return {
        "generated_at": common.now_iso(),
        "enabled": enabled,
        "used": False,
        "asked_before_use": False,
        "prompted_for_key": False,
        "provider": "openai_compatible",
        "model": model,
        "repo_summary_paragraph": "",
        "elevator_pitch": "",
        "audience_start_here": [],
        "module_explanations": [],
        "flow_explanation_steps": [],
        "diagram_briefs": [],
        "caveats": [],
        "confidence_notes": [],
        "key_source": "",
        "persisted_key": False,
        "env_path": LOCAL_ENV_PATH.as_posix(),
        "error": "",
    }


def _compact_context(
    source: str,
    mode: str,
    audience: str,
    analysis_type: str,
    stack_payload: Dict[str, Any],
    dep_payload: Dict[str, Any],
    flow_payload: Dict[str, Any],
    plan_payload: Dict[str, Any],
) -> Dict[str, Any]:
    modules = []
    for item in plan_payload.get("top_modules", [])[:8]:
        modules.append(
            {
                "name": item.get("name", ""),
                "file_count": item.get("file_count", 0),
                "responsibility_hint": item.get("responsibility_hint", ""),
                "change_hint": item.get("change_hint", ""),
                "sample_paths": item.get("sample_paths", [])[:3],
            }
        )
    return {
        "source": source,
        "mode": mode,
        "audience": audience,
        "analysis_type": analysis_type,
        "repo_name": stack_payload.get("repo_name", ""),
        "primary_language": stack_payload.get("primary_language", ""),
        "frameworks": stack_payload.get("frameworks", []),
        "architecture_pattern": stack_payload.get("architecture_pattern", ""),
        "entrypoints": plan_payload.get("entrypoints", [])[:8],
        "primary_flow_steps": plan_payload.get("primary_flow_steps", [])[:8],
        "modules": modules,
        "docs_used": plan_payload.get("docs_used", [])[:6],
        "start_here": plan_payload.get("start_here", [])[:4],
        "diagram_briefs": plan_payload.get("diagram_briefs", [])[:8],
        "caveats": plan_payload.get("caveats", [])[:6],
        "external_dependencies": dep_payload.get("external_dependencies", {}),
        "request_lifecycle": flow_payload.get("request_lifecycle", []),
    }


def _request_messages(context_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    system_prompt = (
        "You explain codebases for PMs, designers, and new engineers. "
        "Return strict JSON only. "
        "Write in simple, concrete language. "
        "Do not use filler like 'service layer', 'core module', or 'user goal' unless the context clearly supports it. "
        "Do not invent facts. If evidence is weak, say so explicitly."
    )
    user_prompt = (
        "Using the context, produce JSON with keys:\n"
        "repo_summary_paragraph (string, 90-160 words),\n"
        "elevator_pitch (string, 1-2 sentences),\n"
        "audience_start_here (array of 3 concise bullets),\n"
        "module_explanations (array of objects with name, responsibility, why_it_matters, first_file_to_open),\n"
        "flow_explanation_steps (array of objects with step, what_happens, why_it_matters),\n"
        "diagram_briefs (array of objects with id, caption, takeaway),\n"
        "caveats (array of concise caveats),\n"
        "confidence_notes (array of concise notes).\n"
        "Use the exact module names and flow steps from context where possible.\n"
        f"Context:\n{json.dumps(context_payload, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _mock_payload(context_payload: Dict[str, Any], model: str) -> Dict[str, Any]:
    repo_name = context_payload.get("repo_name", "This repository")
    frameworks = ", ".join(context_payload.get("frameworks", [])[:3]) or context_payload.get("primary_language", "the detected stack")
    architecture = context_payload.get("architecture_pattern", "a custom structure")
    summary_seed = ""
    docs_used = context_payload.get("docs_used", [])
    if docs_used:
        summary_seed = str(docs_used[0].get("summary", "")).strip()
    if not summary_seed:
        summary_seed = (
            f"{repo_name} is organized as {architecture.lower()} and appears to be built on {frameworks}. "
            "This explanation is grounded in repository structure, entrypoints, dependencies, and available docs."
        )

    module_explanations = []
    for item in context_payload.get("modules", [])[:6]:
        samples = item.get("sample_paths", [])
        module_explanations.append(
            {
                "name": item.get("name", ""),
                "responsibility": item.get("responsibility_hint", ""),
                "why_it_matters": item.get("change_hint", ""),
                "first_file_to_open": samples[0] if samples else "",
            }
        )

    flow_steps = []
    for step in context_payload.get("primary_flow_steps", [])[:6]:
        flow_steps.append(
            {
                "step": step,
                "what_happens": f"This stage advances the main execution path through `{step}`.",
                "why_it_matters": "Understanding this step helps a new reader follow the core product behavior.",
            }
        )

    diagram_briefs = []
    for item in context_payload.get("diagram_briefs", [])[:6]:
        diagram_briefs.append(
            {
                "id": item.get("id", ""),
                "caption": item.get("purpose", ""),
                "takeaway": item.get("reader_question", ""),
            }
        )

    return {
        "generated_at": common.now_iso(),
        "enabled": True,
        "used": True,
        "asked_before_use": False,
        "prompted_for_key": False,
        "provider": "mock_grounded",
        "model": model,
        "repo_summary_paragraph": summary_seed,
        "elevator_pitch": f"{repo_name} is the main system under analysis. Start with the overview, then trace one real flow.",
        "audience_start_here": context_payload.get("start_here", [])[:3],
        "module_explanations": module_explanations,
        "flow_explanation_steps": flow_steps,
        "diagram_briefs": diagram_briefs,
        "caveats": context_payload.get("caveats", [])[:5],
        "confidence_notes": [
            "This run used the grounded mock explainer path, so wording is deterministic.",
            "Narrative claims are limited to extracted repository evidence.",
        ],
        "error": "",
        "request_context": context_payload,
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
    plan_payload: Dict[str, Any],
    out_dir: Path,
    enabled: bool = True,
    ask_before_use: bool = False,
    prompt_for_key: bool = True,
    persist_key_mode: str = "ask",
    resolved_runtime: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    del repo_root, index_payload, entry_payload, docs_payload
    model = os.environ.get("CODE_EXPLAINER_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = _default_llm_payload(enabled=enabled, model=model)
    if not enabled:
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    request_context = _compact_context(
        source=source,
        mode=mode,
        audience=audience,
        analysis_type=analysis_type,
        stack_payload=stack_payload,
        dep_payload=dep_payload,
        flow_payload=flow_payload,
        plan_payload=plan_payload,
    )

    use_mock = common.bool_from_string(os.environ.get("CODE_EXPLAINER_MOCK_LLM", "false"))
    if use_mock:
        payload = _mock_payload(request_context, model="mock-grounded-v1")
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    interactive = _is_interactive_terminal()
    if ask_before_use:
        payload["asked_before_use"] = True
        if not interactive:
            payload["enabled"] = False
            payload["error"] = "LLM ask-before-use requested but terminal is non-interactive; skipped."
            common.write_json(out_dir / "llm_summary.json", payload)
            return payload
        if not _confirm_llm_usage():
            payload["enabled"] = False
            payload["error"] = "User declined LLM narrative generation for this run."
            common.write_json(out_dir / "llm_summary.json", payload)
            return payload

    runtime = resolved_runtime
    if runtime is None:
        try:
            runtime = resolve_llm_runtime(
                prompt_for_key=prompt_for_key,
                persist_key_mode=persist_key_mode,
                require_key=True,
            )
        except RuntimeError as exc:
            payload["error"] = str(exc)
            common.write_json(out_dir / "llm_summary.json", payload)
            return payload

    api_key = str(runtime.get("api_key", "")).strip()
    payload["prompted_for_key"] = bool(runtime.get("prompted_for_key", False))
    payload["persisted_key"] = bool(runtime.get("persisted_key", False))
    payload["key_source"] = str(runtime.get("key_source", "")).strip()
    payload["env_path"] = str(runtime.get("env_path", LOCAL_ENV_PATH.as_posix()))
    payload["model"] = str(runtime.get("model", model)).strip() or model

    if not api_key:
        payload["error"] = "No API key found (set CODE_EXPLAINER_LLM_API_KEY or OPENAI_API_KEY)."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    endpoint = f"{str(runtime.get('base_url', DEFAULT_BASE_URL)).rstrip('/')}/chat/completions"
    request_payload = {
        "model": payload["model"],
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
        "messages": _request_messages(request_context),
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

    choices = response_json.get("choices", [])
    content = ""
    if choices and isinstance(choices[0], dict):
        content = ((choices[0].get("message") or {}).get("content", "")) or ""

    parsed = _extract_json(content)
    if not parsed:
        payload["error"] = "LLM response content did not include parseable JSON."
        common.write_json(out_dir / "llm_summary.json", payload)
        return payload

    payload.update(
        {
            "used": True,
            "repo_summary_paragraph": str(parsed.get("repo_summary_paragraph", "")).strip(),
            "elevator_pitch": str(parsed.get("elevator_pitch", "")).strip(),
            "audience_start_here": parsed.get("audience_start_here", [])[:4] if isinstance(parsed.get("audience_start_here", []), list) else [],
            "module_explanations": parsed.get("module_explanations", [])[:10] if isinstance(parsed.get("module_explanations", []), list) else [],
            "flow_explanation_steps": parsed.get("flow_explanation_steps", [])[:10] if isinstance(parsed.get("flow_explanation_steps", []), list) else [],
            "diagram_briefs": parsed.get("diagram_briefs", [])[:10] if isinstance(parsed.get("diagram_briefs", []), list) else [],
            "caveats": parsed.get("caveats", [])[:6] if isinstance(parsed.get("caveats", []), list) else [],
            "confidence_notes": parsed.get("confidence_notes", [])[:6] if isinstance(parsed.get("confidence_notes", []), list) else [],
            "error": "",
            "request_context": request_context,
        }
    )
    common.write_json(out_dir / "llm_summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate grounded repository explanations with an LLM or mock path.")
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
    parser.add_argument("--explanation-plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--enabled", default="true")
    parser.add_argument("--ask-before-use", default="false")
    parser.add_argument("--prompt-for-key", default="true")
    parser.add_argument("--persist-key", default="ask")
    args = parser.parse_args()

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
        plan_payload=common.read_json(Path(args.explanation_plan), default={}),
        out_dir=Path(args.output).resolve(),
        enabled=common.bool_from_string(args.enabled),
        ask_before_use=common.bool_from_string(args.ask_before_use),
        prompt_for_key=common.bool_from_string(args.prompt_for_key),
        persist_key_mode=args.persist_key,
    )
    print(json.dumps({"used": payload.get("used", False), "provider": payload.get("provider", ""), "error": payload.get("error", "")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
