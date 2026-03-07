#!/usr/bin/env python3
"""
Shared helpers for the code-explainer pipeline.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from fnmatch import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".cache",
    "coverage",
    "target",
    ".pui",
    "output",
    "artifacts",
}

DEFAULT_EXCLUDE_GLOBS = [
    ".out*/**",
    ".ci-*/**",
    "output/**",
    "artifacts/**",
    "reports/**",
    "tmp/**",
    "temp/**",
    "**/__pycache__/**",
]


LANG_EXTENSIONS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".sql": "SQL",
    ".scala": "Scala",
    ".dart": "Dart",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return default


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 60) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def is_mermaid_environment_failure(text: str) -> bool:
    lowered = (text or "").lower()
    signals = [
        "failed to launch the browser process",
        "browser launch",
        "spawn eperm",
        "invalid file descriptor to icu data received",
        "troubleshooting: https://pptr.dev/troubleshooting",
        "could not find chrome",
        "failed to spawn browser",
        "no usable sandbox",
    ]
    return any(signal in lowered for signal in signals)


def which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def is_github_url(value: str) -> bool:
    return bool(re.match(r"^https?://(www\.)?github\.com/[^/]+/[^/]+/?$", value.strip()))


def github_repo_slug(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    return cleaned.replace("https://github.com/", "").replace("http://github.com/", "")


def _matches_any_glob(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        p = pattern.strip()
        if not p:
            continue
        if fnmatch(normalized, p):
            return True
        # Also support directory-only globs like "docs/".
        if p.endswith("/") and normalized.startswith(p):
            return True
    return False


def list_files(
    root: Path,
    limit: int = 30000,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    include_globs = include_globs or []
    exclude_globs = (exclude_globs or []) + DEFAULT_EXCLUDE_GLOBS
    files: List[Dict[str, Any]] = []
    for current_root, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".venv")]
        for name in names:
            full_path = Path(current_root) / name
            rel = full_path.relative_to(root).as_posix()
            if rel.startswith("."):
                continue
            if _matches_any_glob(rel, exclude_globs):
                continue
            if include_globs and not _matches_any_glob(rel, include_globs):
                continue
            try:
                size = full_path.stat().st_size
            except Exception:
                size = 0
            files.append(
                {
                    "path": rel,
                    "ext": full_path.suffix.lower(),
                    "size_bytes": size,
                }
            )
            if len(files) >= limit:
                return files
    return files


def language_counts(files: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in files:
        lang = LANG_EXTENSIONS.get(item.get("ext", ""))
        if not lang:
            continue
        counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def top_level_modules(files: Iterable[Dict[str, Any]], max_items: int = 60) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    root_files = {"name": "(root-files)", "type": "file_group", "file_count": 0, "total_bytes": 0, "examples": []}
    for item in files:
        path = item["path"]
        size = int(item.get("size_bytes", 0))
        if "/" not in path:
            root_files["file_count"] += 1
            root_files["total_bytes"] += size
            if len(root_files["examples"]) < 10:
                root_files["examples"].append(path)
            continue

        top = path.split("/", 1)[0]
        if top not in buckets:
            buckets[top] = {"name": top, "type": "directory", "file_count": 0, "total_bytes": 0}
        buckets[top]["file_count"] += 1
        buckets[top]["total_bytes"] += size

    ranked = sorted(
        buckets.values(), key=lambda m: (m["file_count"], m["total_bytes"]), reverse=True
    )
    if root_files["file_count"] > 0:
        ranked.append(root_files)
    return ranked[:max_items]


def detect_frameworks(repo_root: Path) -> List[str]:
    frameworks: List[str] = []
    package_json = repo_root / "package.json"
    requirements = repo_root / "requirements.txt"
    pyproject = repo_root / "pyproject.toml"
    go_mod = repo_root / "go.mod"
    cargo_toml = repo_root / "Cargo.toml"

    pkg_text = read_text(package_json)
    req_text = read_text(requirements)
    pyproject_text = read_text(pyproject)
    go_text = read_text(go_mod)
    cargo_text = read_text(cargo_toml)

    framework_signals = [
        ("next", "Next.js"),
        ("react", "React"),
        ("vue", "Vue"),
        ("angular", "Angular"),
        ("svelte", "Svelte"),
        ("express", "Express"),
        ("fastify", "Fastify"),
        ("nestjs", "NestJS"),
        ("fastapi", "FastAPI"),
        ("django", "Django"),
        ("flask", "Flask"),
        ("spring", "Spring"),
        ("gin-gonic", "Gin"),
        ("fiber", "Fiber"),
        ("actix-web", "Actix"),
        ("rocket", "Rocket"),
    ]
    haystack = "\n".join([pkg_text, req_text, pyproject_text, go_text, cargo_text]).lower()
    for signal, name in framework_signals:
        if signal in haystack and name not in frameworks:
            frameworks.append(name)
    return frameworks


def detect_architecture_pattern(repo_root: Path) -> str:
    dirs = {p.name.lower() for p in repo_root.iterdir() if p.is_dir()}
    if {"models", "views", "controllers"} <= dirs:
        return "MVC"
    if {"api", "services", "repositories"} <= dirs:
        return "Layered"
    if "features" in dirs:
        return "Feature-based"
    if {"domain", "application", "infrastructure"} <= dirs:
        return "Domain-driven"
    if "packages" in dirs or "apps" in dirs:
        return "Monorepo"
    return "Custom/Undetected"


def _looks_like_python_entrypoint(path: str, text: str) -> Optional[str]:
    lowered = text.lower()
    if "__name__" in text and "__main__" in text:
        return "Python main guard"
    if re.search(r"^\s*(app|application)\s*=\s*FastAPI\(", text, flags=re.MULTILINE):
        return "FastAPI app bootstrap"
    if re.search(r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", text, flags=re.MULTILINE):
        return "Python script entrypoint"
    if path.endswith("manage.py"):
        return "Django management entrypoint"
    return None


def _looks_like_js_entrypoint(path: str, text: str) -> Optional[str]:
    if "app.listen(" in text or ".listen(" in text:
        return "Server listener bootstrap"
    if "createRoot(" in text or "ReactDOM.render(" in text:
        return "Frontend app bootstrap"
    if "NestFactory.create" in text:
        return "NestJS bootstrap"
    if path.endswith(("next.config.js", "next.config.ts")):
        return "Next.js config entrypoint"
    return None


def _looks_like_go_entrypoint(path: str, text: str) -> Optional[str]:
    if path.endswith("main.go") and "func main()" in text:
        return "Go main package"
    return None


def detect_entrypoints(
    files: Iterable[Dict[str, Any]],
    repo_root: Optional[Path] = None,
    max_scan: int = 2500,
) -> List[Dict[str, str]]:
    patterns = {
        "main.py": "Python entrypoint",
        "app.py": "Python app bootstrap",
        "server.py": "Python server",
        "index.js": "JavaScript entrypoint",
        "index.ts": "TypeScript entrypoint",
        "main.ts": "TypeScript main",
        "main.go": "Go main package",
        "lib.rs": "Rust library root",
        "main.rs": "Rust binary entrypoint",
        "manage.py": "Django management entrypoint",
        "next.config.js": "Next.js config",
    }
    results: List[Dict[str, str]] = []
    scan_count = 0
    seen_paths = set()
    for item in files:
        filename = item["path"].split("/")[-1].lower()
        if filename in patterns:
            results.append({"path": item["path"], "kind": patterns[filename]})
            seen_paths.add(item["path"])

        if repo_root is None:
            continue
        if scan_count >= max_scan:
            continue
        ext = item.get("ext", "")
        if ext not in {".py", ".js", ".jsx", ".ts", ".tsx", ".go"}:
            continue
        text = read_text(repo_root / item["path"])
        if not text:
            continue
        kind = None
        if ext == ".py":
            kind = _looks_like_python_entrypoint(item["path"], text)
        elif ext in {".js", ".jsx", ".ts", ".tsx"}:
            kind = _looks_like_js_entrypoint(item["path"], text)
        elif ext == ".go":
            kind = _looks_like_go_entrypoint(item["path"], text)
        if kind and item["path"] not in seen_paths:
            results.append({"path": item["path"], "kind": kind})
            seen_paths.add(item["path"])
        scan_count += 1

    # Keep deterministic ordering.
    results.sort(key=lambda x: x["path"])
    return results


def parse_dependency_file(path: Path) -> List[str]:
    text = read_text(path)
    deps: List[str] = []
    if path.name == "package.json":
        try:
            payload = json.loads(text)
            for block in ["dependencies", "devDependencies", "peerDependencies"]:
                deps.extend(list((payload.get(block) or {}).keys()))
        except Exception:
            return deps
        return sorted(set(deps))

    if path.name in {"requirements.txt", "go.mod"}:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if path.name == "go.mod":
                if line.startswith("require") or line.startswith("module") or line.startswith("go "):
                    continue
                parts = line.split()
                if parts:
                    deps.append(parts[0])
            else:
                deps.append(re.split(r"[<>=!~]", line)[0].strip())
        return sorted(set([d for d in deps if d]))

    if path.name in {"pyproject.toml", "Cargo.toml"}:
        for line in text.splitlines():
            if "=" not in line:
                continue
            key = line.split("=", 1)[0].strip().strip('"').strip("'")
            if not key or key.startswith("["):
                continue
            if key.lower() in {"name", "version", "description", "authors"}:
                continue
            deps.append(key)
        return sorted(set(deps))
    return deps


def scan_external_dependencies(repo_root: Path) -> Dict[str, List[str]]:
    manifests = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "go.mod",
        "Cargo.toml",
    ]
    result: Dict[str, List[str]] = {}
    for file_name in manifests:
        path = repo_root / file_name
        if path.exists():
            result[file_name] = parse_dependency_file(path)
    return result


def detect_repo_name(source: str, repo_root: Path) -> str:
    if is_github_url(source):
        slug = github_repo_slug(source)
        return slug.split("/")[-1]
    return repo_root.name


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def load_template(path: Path) -> str:
    return read_text(path, default="")


def render_template(template: str, replacements: Dict[str, str]) -> str:
    result = template
    for key, value in replacements.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def safe_word(text: str, fallback: str = "unknown") -> str:
    match = re.findall(r"[A-Za-z0-9_-]+", text.lower())
    if not match:
        return fallback
    return "-".join(match[:4])


def normalize_mode(mode: str) -> str:
    mode = (mode or "standard").lower().strip()
    if mode not in {"quick", "standard", "deep"}:
        return "standard"
    return mode


def bool_from_string(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def first_nonempty(values: Iterable[str], fallback: str = "Unknown") -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return fallback


def maybe_git_ref(repo_root: Path) -> str:
    code, out, _err = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, timeout=10)
    if code == 0:
        return out.strip()
    return "unknown"


def maybe_remote_origin(repo_root: Path) -> str:
    code, out, _err = run_cmd(["git", "config", "--get", "remote.origin.url"], cwd=repo_root, timeout=10)
    if code == 0:
        return out.strip()
    return ""


def collect_claim(
    claim_id: str,
    claim_text: str,
    evidence_paths: List[str],
    confidence_score: float,
    reason: str,
) -> Dict[str, Any]:
    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "evidence_paths": evidence_paths,
        "confidence_score": round(confidence_score, 2),
        "reason": reason,
    }


def discover_words(text: str, min_len: int = 3, max_words: int = 250) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{" + str(min_len - 1) + r",}", text)
    freq: Dict[str, int] = {}
    for word in words:
        key = word.strip()
        freq[key] = freq.get(key, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, _ in ranked[:max_words]]


def file_line_count(path: Path) -> int:
    text = read_text(path)
    if not text:
        return 0
    return len(text.splitlines())
