---
applyTo: "truthseeker-api/**"
---

# TruthSeeker Backend Instructions

完整规范见 `truthseeker-api/AGENTS.md` 和 `docs/BACKEND_STRUCTURE.md`。本文件只保留 Copilot 速查规则。

## Stack

- FastAPI 0.134.0
- Python 3.11+
- LangGraph 1.x
- Pydantic 2
- Supabase Python client

## Architecture

- API routes live in `app/api/v1/` and are registered in `app/api/v1/router.py`.
- LangGraph files live in `app/agents/`.
- Current graph: `START -> forensics -> challenger -> osint -> challenger -> commander -> END`.
- External tool wrappers live in `app/agents/tools/`; route and node files should orchestrate rather than embed provider details.
- Persistence/report/case/RAG/collaboration helpers live in `app/services/`.

## Rules

- `TruthSeekerState` must be `TypedDict`; do not use Pydantic `BaseModel` for graph state.
- New public API paths must stay under `/api/v1`.
- Canonical collaboration route is `/api/v1/collaboration`; `/api/v1/consultation` is a compatibility alias.
- Tools must return structured `success`, `degraded`, or `failed` data and avoid crashing the graph on provider failure.
- New user-facing AIGC fields use `aigc_probability`, `is_aigc`, and `aigc_score`. Keep `deepfake_*` only for old snapshot fallback.
- Do not depend on real credentials or network in tests.
- Do not print secrets or full third-party raw payloads into logs, SSE events, reports, or docs.

## Checks

```powershell
cd truthseeker-api
python -m pytest tests
python -m uvicorn app.main:app --reload
```

Use focused pytest targets for small changes. On this Windows workspace, `venv_new\Scripts\python.exe` may be the most reliable interpreter.
