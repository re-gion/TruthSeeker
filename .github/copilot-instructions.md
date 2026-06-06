# TruthSeeker Copilot Instructions

默认用中文回复。项目级事实以 `AGENTS.md`、`docs/TECH_STACK.md`、`docs/APP_FLOW.md`、`docs/BACKEND_STRUCTURE.md` 和实际源码为准。

## Current Project

TruthSeeker 是 CISCN 2026 跨模态恶意 AIGC 鉴伪、溯源与人机协同系统。

- Frontend: `truthseeker-web/`, Next.js 16.1.6, React 19.2.3, Tailwind CSS 4.
- Backend: `truthseeker-api/`, FastAPI 0.134.0, Python 3.11+, LangGraph 1.x.
- Database: Supabase PostgreSQL/RLS/Realtime/pgvector.
- Current graph: `forensics -> challenger -> osint -> challenger -> commander -> END`.

## Read Before Editing

- Whole repo: `AGENTS.md`
- Frontend: `truthseeker-web/AGENTS.md`, `docs/FRONTEND_GUIDELINES.md`
- Backend: `truthseeker-api/AGENTS.md`, `docs/BACKEND_STRUCTURE.md`
- Agents: `truthseeker-api/app/agents/AGENTS.md`
- Flow/API/state: `docs/APP_FLOW.md`
- Versions/env: `docs/TECH_STACK.md`
- Current tasks/pitfalls: `task.md`, `lessons.md`

## Hard Rules

- Do not expose or copy real secrets from `.env`, `.env.local`, `.mcp.json`, or local config.
- Do not edit `.agent/`, `.agents/`, `.claude/`, `.cursor/`, `.qoder/`, `.trae/`, `.superpowers/`, `node_modules/`, `.next`, virtualenvs, caches, or generated logs unless explicitly requested.
- LangGraph state must stay `TypedDict`; Pydantic is for API models only.
- Use `motion/react`, Tailwind CSS v4 CSS-first config, `@supabase/ssr`, and shadcn canary-compatible patterns.
- Public protocol keys remain `forensics`, `osint`, `challenger`, `commander`.
- New user-facing AIGC fields use `aigc_*`; legacy `deepfake_*` is compatibility only.
- Canonical collaboration routes/events use `collaboration_*`; old `consultation_*` is compatibility.

## Verification

Frontend:

```powershell
cd truthseeker-web
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Backend:

```powershell
cd truthseeker-api
python -m pytest tests
python -m uvicorn app.main:app --reload
```

Run the narrow relevant checks first, then broader checks when feasible. If local services, network, or credentials block a check, report the exact limitation instead of claiming success.
