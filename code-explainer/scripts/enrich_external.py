#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import common


def _http_get(url: str, timeout: int = 15) -> Tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "code-explainer/1.0",
            "Accept": "application/json,text/html,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")
    except Exception:
        return 0, ""


def enrich_external(source: str, out_meta_dir: Path, enabled: bool = True) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    attributions: List[Dict[str, Any]] = []
    if not enabled:
        payload = {
            "enriched_at": common.now_iso(),
            "enabled": False,
            "records": records,
            "source_attribution": attributions,
        }
        common.write_json(out_meta_dir / "enrichment.json", payload)
        return payload

    if common.is_github_url(source):
        slug = common.github_repo_slug(source)
        owner, repo = slug.split("/", 1)
        deepwiki_url = f"https://deepwiki.com/{owner}/{repo}"
        github_api = f"https://api.github.com/repos/{owner}/{repo}"
        readme_api = f"https://api.github.com/repos/{owner}/{repo}/readme"

        status_repo, repo_body = _http_get(github_api)
        if status_repo == 200:
            try:
                repo_payload = json.loads(repo_body)
            except Exception:
                repo_payload = {}
            records.append(
                {
                    "source": "github_api_repo",
                    "uri": github_api,
                    "status": status_repo,
                    "description": repo_payload.get("description", ""),
                    "topics": repo_payload.get("topics", []),
                    "language": repo_payload.get("language", ""),
                    "stars": repo_payload.get("stargazers_count", 0),
                }
            )
            attributions.append(
                {
                    "claim_id": "external_repo_metadata",
                    "source_type": "web",
                    "source_uri": github_api,
                    "extraction_timestamp": common.now_iso(),
                }
            )

        status_readme, readme_body = _http_get(readme_api)
        if status_readme == 200:
            records.append(
                {
                    "source": "github_api_readme",
                    "uri": readme_api,
                    "status": status_readme,
                    "snippet": readme_body[:1200],
                }
            )
            attributions.append(
                {
                    "claim_id": "external_readme_metadata",
                    "source_type": "web",
                    "source_uri": readme_api,
                    "extraction_timestamp": common.now_iso(),
                }
            )

        status_dw, deepwiki_body = _http_get(deepwiki_url)
        records.append(
            {
                "source": "deepwiki",
                "uri": deepwiki_url,
                "status": status_dw,
                "available": status_dw == 200,
                "snippet": deepwiki_body[:1200] if deepwiki_body else "",
            }
        )
        attributions.append(
            {
                "claim_id": "external_deepwiki_context",
                "source_type": "deepwiki",
                "source_uri": deepwiki_url,
                "extraction_timestamp": common.now_iso(),
            }
        )
    else:
        records.append(
            {
                "source": "local_only",
                "uri": "",
                "status": 0,
                "available": False,
                "snippet": "No external enrichment for local-only source by default.",
            }
        )

    payload = {
        "enriched_at": common.now_iso(),
        "enabled": enabled,
        "records": records,
        "source_attribution": attributions,
    }
    common.write_json(out_meta_dir / "enrichment.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich analysis with DeepWiki and web metadata.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--enabled", default="true")
    args = parser.parse_args()
    payload = enrich_external(
        args.source,
        Path(args.output).resolve(),
        enabled=common.bool_from_string(args.enabled),
    )
    print(f"External enrichment records: {len(payload['records'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

