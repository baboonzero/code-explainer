# Publishing and Distribution

## 1) Publish to GitHub

From repository root:

```bash
git add .
git commit -m "feat: add code-explainer skill"
git remote add origin https://github.com/<your-org-or-user>/code-explainer.git
git push -u origin main
```

## 2) Verify Install from GitHub

Use the Skills CLI install pattern:

```bash
npx skills add https://github.com/<your-org-or-user>/code-explainer --skill code-explainer
```

Or with Codex system installer script:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo <your-org-or-user>/code-explainer \
  --path code-explainer
```

Dependency note for downstream users:

- Python 3.10+
- Node.js 18+ and npm
- Git
- Mermaid CLI (`@mermaid-js/mermaid-cli`) for full SVG/PNG rendering

Point users to:

- `README.md` -> "Dependencies (Required for Skill Installation/Use)"
- `code-explainer/SKILL.md` -> "Dependencies"

## 3) `skills.sh` Listing Expectations

- `skills.sh` tracks install activity from `npx skills` usage.
- The site updates roughly every 12 hours.
- Removed/unavailable repos can be pruned from listings.

Practical implication:

1. Publish repo publicly.
2. Ensure install command works.
3. Have users install via `npx skills ...` so the skill becomes discoverable through ecosystem tracking.

## 4) Increase Discoverability

1. Add GitHub topics: `agent-skill`, `codex`, `mermaid`, `codebase-analysis`, `onboarding`.
2. Add a short demo GIF in README showing generated overview + deep docs.
3. Publish a GitHub release with example outputs.
4. Share in developer communities with install command and sample output links.
