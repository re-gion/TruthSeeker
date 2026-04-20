# TruthSeeker Agent Guide

## Scope

This file applies to the whole repository. More specific `AGENTS.md` files in child directories override these rules for their subtrees.

## Project Map

TruthSeeker is a CISCN 2026 cross-modal Deepfake detection and provenance system.

- `truthseeker-web/` - Next.js frontend: landing page, detection console, reports, dashboard, collaboration UI.
- `truthseeker-api/` - FastAPI backend: task APIs, upload/detection streams, reports, consultation, LangGraph agents.
- `docs/` - durable product, architecture, flow, frontend, backend, and implementation documentation.
- `task.md` - current task checklist and milestone status. Read before choosing what to work on.
- `lessons.md` - known pitfalls. Read before modifying code.
- `CLAUDE.md` - legacy agent guidance. Use it as context, but prefer this file plus nested `AGENTS.md` files when guidance differs.

Do not edit `.agent/`, `.agents/`, `.claude/`, `.cursor/`, `.qoder/`, `.trae/`, `.superpowers/`, `node_modules/`, `.next/`, virtual environments, caches, or generated logs unless the user explicitly asks.

## Source Of Truth

When facts disagree, prefer this order:

1. Actual source files and package manifests.
2. `docs/TECH_STACK.md`.
3. `task.md` and `lessons.md`.
4. Other files in `docs/`.
5. Older narrative documents in the repository root.

Current checked-in manifests indicate Next.js 16.1.6, React 19.2.3, Tailwind CSS 4, FastAPI 0.134.0, Python 3.11+, and LangGraph 1.x.

## Working Agreements

- Keep reports to the user in clear, natural Chinese unless asked otherwise.
- Check `git status --short` before editing and avoid overwriting unrelated user changes.
- Keep changes scoped to the requested task. Do not refactor broad areas just because they are nearby.
- Never print, copy, or commit real secrets from `.env`, `.env.local`, `.mcp.json`, or local config files. Use `.env.example` when documenting variables.
- If behavior changes, update the closest durable documentation that explains that behavior.
- Prefer existing project patterns over adding new libraries or abstractions.

## Common Commands

Frontend:

```powershell
cd truthseeker-web
npm install
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Backend:

```powershell
cd truthseeker-api
python -m pip install -r requirements.txt
python -m pytest tests
python -m uvicorn app.main:app --reload
```

Run only the relevant checks for the files changed, but make a best effort to run the full affected gate before calling work complete. If a check cannot run because of missing local services, dependencies, or secrets, state that clearly.

## Completion Standard

A task is complete only when:

- The requested behavior or document change is implemented.
- The affected documentation remains consistent with source code and manifests.
- Relevant checks have been run, or the reason they could not run is recorded.
- `task.md` and `lessons.md` are updated when the task changes milestone status or records a new recurring pitfall.

## Git And PR Notes

- Use Angular-style commit messages with `type: 中文主题` when asked to commit.
- For PR descriptions, summarize major changes in Markdown and call out likely impact points.
