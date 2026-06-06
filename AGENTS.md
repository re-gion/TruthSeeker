# TruthSeeker Agent Guide

## Scope

This file applies to the whole repository. More specific `AGENTS.md` files in child directories override these rules for their subtree. User messages still override repository instructions.

## Project Snapshot

TruthSeeker is a CISCN 2026 cross-modal malicious AIGC detection, provenance, and human collaboration system.

- `truthseeker-web/` - Next.js 16.1.6, React 19.2.3, Tailwind CSS 4 frontend for landing, upload, detection console, reports, dashboard, public cases, and personal experience library.
- `truthseeker-api/` - FastAPI 0.134.0 backend with Supabase persistence, LangGraph 1.x staged agents, SSE detection stream, reports, sharing, public cases, personal experience library, and collaboration APIs.
- `docs/` - durable product, architecture, flow, frontend, backend, and implementation documentation.
- `task.md` - milestone checklist and current project status.
- `lessons.md` - recurring pitfalls and hard-won debugging notes.

Current runtime topology is:

```text
upload/task -> forensics -> challenger -> osint -> challenger -> commander -> END
```

Commander ends the graph directly after final verdict generation. The older "Commander -> Challenger -> END" pattern is obsolete unless the graph code changes again.

## Source Of Truth

When facts disagree, prefer this order:

1. Actual source files, package manifests, SQL migrations, and tests.
2. `docs/TECH_STACK.md`.
3. `docs/APP_FLOW.md` and `docs/BACKEND_STRUCTURE.md`.
4. `task.md` and `lessons.md`.
5. Other files in `docs/`.
6. Root narrative reports, white papers, and historical plans.

Do not present planned Fed-MBPR training/inference as current runtime behavior. The current codebase is Fed-MBPR-compatible and keeps the detector layer replaceable, but it does not include a Fed-MBPR training service.

## Files Agents Must Not Touch Casually

Do not edit `.agent/`, `.agents/`, `.claude/`, `.cursor/`, `.qoder/`, `.trae/`, `.superpowers/`, `node_modules/`, `.next/`, virtual environments, caches, generated logs, or local env files unless the user explicitly asks.

Never print, copy, or commit real secrets from `.env`, `.env.local`, `.mcp.json`, or local config files. Use `.env.example` and `docs/TECH_STACK.md` for documenting variables.

## Working Agreements

- Reply to the user in clear, natural Chinese unless asked otherwise.
- Run `git status --short` before editing and avoid overwriting unrelated user changes.
- Keep changes scoped. Do not broaden into unrelated refactors.
- Prefer existing project patterns over new libraries or new abstractions.
- If behavior changes, update the closest durable documentation in the same change.
- For multi-file feature or bug work, update or add focused tests when feasible.
- Treat external AI/API failures as structured degradation, not as successful evidence.

## Frontend Commands

Use npm because `truthseeker-web/package-lock.json` is committed.

```powershell
cd truthseeker-web
npm install
npm run lint
npm run typecheck
npm run test:unit
npm run build
npm run dev
```

Frontend defaults:

- URL: `http://localhost:3000`
- Backend: `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Browser-exposed env vars must be `NEXT_PUBLIC_*`.

## Backend Commands

Prefer the project virtual environment on this Windows workspace when it exists.

```powershell
cd truthseeker-api
python -m pip install -r requirements.txt
python -m pytest tests
python -m uvicorn app.main:app --reload
```

If available locally, `truthseeker-api\venv_new\Scripts\python.exe` is the most reliable interpreter for backend tests. Use `pytest -p no:cacheprovider` or `PYTHONDONTWRITEBYTECODE=1` if Windows cache writes fail.

Backend defaults:

- API: `http://localhost:8000`
- Health: `GET /health`
- API prefix: `/api/v1`

## Current API Surface

Registered route groups:

- `POST /api/v1/upload/`
- `POST /api/v1/tasks`, `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/detect/stream`
- `GET /api/v1/report/{task_id}/md`, `/pdf`, `/audit-log.md`, `/audit-log.pdf`
- `POST /api/v1/share/{task_id}`, `GET /api/v1/share/{token}`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/cases`, `GET /api/v1/cases/{case_id}`, preview/text/delete helpers
- `GET /api/v1/experiences`, `GET /api/v1/experiences/{entry_id}`, `POST /api/v1/experiences/confirm`, `DELETE /api/v1/experiences/{entry_id}`
- Canonical collaboration routes under `/api/v1/collaboration`; `/api/v1/consultation` remains as a compatibility alias.
- Before claiming canonical expert links are production-ready, resolve and test the authentication gap recorded in `docs/KNOWN_GAPS.md`.

## Critical Runtime Rules

- LangGraph state must stay `TypedDict`, not Pydantic `BaseModel`.
- Public protocol keys remain `forensics`, `osint`, `challenger`, `commander`.
- `forensics` is user-facing "电子取证 Agent"; do not narrow it back to only visual/audio.
- New runtime/user-facing AIGC fields use `aigc_probability`, `is_aigc`, and `aigc_score`; legacy `deepfake_*` is read-only compatibility for old JSONB snapshots.
- Challenger hard gates: before round 5, confidence `< 0.8` requires returning to the target Agent; round 5 releases with residual risk.
- Collaboration triggers when the same target Agent has 3 recent low-confidence rounds and adjacent changes `< 0.08`.
- Public case RAG and personal experience RAG are references/checklists, not current-case facts.
- Provenance graph claims/tool findings/source edges need citations where possible; model-inferred edges must be explicit.

## Completion Standard

A task is complete only when:

- The requested behavior or document change is implemented.
- Affected docs are consistent with current code/manifests.
- Relevant checks have been run, or the reason they could not run is recorded.
- `task.md` and `lessons.md` are updated when milestone status or a recurring pitfall changes.

## Git And PR Notes

- Use Angular-style commit messages with `type: 中文主题` when asked to commit.
- Do not push, especially to `main`, without explicit user confirmation.
- For PR descriptions, summarize major changes in Markdown and call out likely impact points.
