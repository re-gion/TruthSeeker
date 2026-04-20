# Documentation Agent Guide

## Scope

This file applies to `docs/`.

## Documentation Role

`docs/` is the durable project knowledge base. Keep root `AGENTS.md` concise and point here for deeper context.

- `PRD.md` - product goals, user flows, modules, non-functional needs, success metrics.
- `TECH_STACK.md` - current dependency and environment-variable reference.
- `FRONTEND_GUIDELINES.md` - UI/UX language, colors, motion, responsiveness, accessibility.
- `BACKEND_STRUCTURE.md` - backend layout, Supabase schema, LangGraph design, API overview, security notes.
- `APP_FLOW.md` - multi-agent state flow, realtime channels, data model, frontend state model.
- `IMPLEMENTATION_PLAN.md` - phased roadmap and review checklist.
- `superpowers/plans/` - detailed execution plans.

## Writing Rules

- Write project-facing documentation in clear Chinese unless the file already uses another language.
- Keep docs tied to actual code and manifests. If the code differs from older docs, update docs rather than copying stale claims.
- Prefer concrete paths, commands, and current behavior over broad intent statements.
- Do not include real secrets, tokens, local-only URLs with credentials, or private account identifiers.
- When documenting external data or reports, include source name and retrieval date if available.
- If a behavior change affects both frontend and backend, update the flow/contract docs in the same change.

## Verification

For docs-only changes, check Markdown structure, links/paths, and consistency with source files. If docs mention a command, verify the command exists in the relevant manifest or README.
