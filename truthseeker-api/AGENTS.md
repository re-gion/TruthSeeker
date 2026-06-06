# TruthSeeker API Agent Guide

## Scope

This file applies to `truthseeker-api/`.

## Runtime And Commands

Use Python 3.11+ from this directory. In this Windows workspace, prefer `venv_new\Scripts\python.exe` when it exists.

```powershell
cd truthseeker-api
python -m pip install -r requirements.txt
python -m pytest tests
python -m uvicorn app.main:app --reload
```

The API defaults to `http://localhost:8000`. Use `.env.example` as the template for local `.env`; do not expose real API keys.

## Architecture Map

- `app/main.py` - FastAPI app, CORS, auth, rate limit, exception handlers, health endpoint.
- `app/config.py` - pydantic-settings environment mapping and legacy env aliases.
- `app/api/v1/` - HTTP route modules; register new routers in `router.py`.
- `app/agents/` - LangGraph state machine, nodes, edges, and tool integrations.
- `app/middleware/` - auth, exception, and rate-limit middleware.
- `app/services/` - persistence, reports, cases, RAG, input validation, audit, and collaboration helpers.
- `app/utils/` - shared utilities such as Supabase client setup.
- `sql/migrations/` - Supabase schema migrations.
- `tests/` - pytest tests using local fakes/mocks for Supabase and external services.

Current registered route groups are `detect`, `tasks`, `upload`, `report`, `collaboration`, legacy `consultation`, `share`, `dashboard`, `cases`, and `experiences`.

## Backend Rules

- Keep public API paths under `/api/v1`.
- Validate file uploads and untrusted inputs at route boundaries.
- Preserve graceful degradation when external AI, Reality Defender, VirusTotal, Kimi, OpenAI, or Supabase calls fail.
- Treat `/api/v1/collaboration` as canonical. Keep `/api/v1/consultation` compatibility unless the user explicitly asks to remove the legacy alias.
- Do not claim canonical expert links are production-ready until the authentication whitelist gap in `docs/KNOWN_GAPS.md` has a regression test.
- Do not write new user-facing "deepfake probability" fields. Use `aigc_*`; keep `deepfake_*` only as old snapshot fallback.
- Keep collaboration tables (`collaboration_*`) as the new write path. Old `consultation_*` tables are compatibility/read fallback.
- If changing graph flow, update `app/agents/graph.py`, `app/agents/edges/conditions.py`, `docs/APP_FLOW.md`, and `docs/BACKEND_STRUCTURE.md` together.
- Do not make tests depend on real network services or real credentials; mock external clients.
- When adding a route, add focused tests for success, failure, and sensitive-data redaction when relevant.
- Middleware execution order matters in Starlette; review `app/main.py` comments before changing middleware registration.
- Do not commit local `venv/`, `venv_new/`, `.env`, caches, logs, or generated `__pycache__`.

## Verification

For backend changes, run the narrow pytest target first, then `python -m pytest tests` when feasible. For API behavior, prefer `fastapi.testclient.TestClient` tests with fake Supabase data.
