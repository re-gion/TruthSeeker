---
applyTo: "truthseeker-web/**"
---

# TruthSeeker Frontend Instructions

完整规范见 `truthseeker-web/AGENTS.md` 和 `docs/FRONTEND_GUIDELINES.md`。本文件只保留 Copilot 速查规则。

## Stack

- Next.js 16.1.6 App Router
- React 19.2.3
- TypeScript 5
- Tailwind CSS 4
- `motion` 12.x from `motion/react`
- `@supabase/ssr`
- React Three Fiber 9 + Drei 10

## Rules

- Components are server components by default. Add `"use client"` only for hooks, browser APIs, animation, realtime, or local state.
- Use `@/*` imports for project-local modules.
- Use `motion/react`; do not import `framer-motion`.
- Tailwind is v4 CSS-first. Do not add `tailwind.config.js` unless intentionally migrating the project.
- Use `@supabase/ssr`; do not add deprecated auth-helper packages.
- Only `NEXT_PUBLIC_*` variables may be read in browser code.
- Preserve canonical wording: “人机协同” and “个人经验库”. Keep legacy consultation handling only for old history compatibility.
- Public unauthenticated pages currently include `/report/*` and `/cases/*`.

## Checks

```powershell
cd truthseeker-web
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Run the narrow relevant unit tests for mapping/report/dashboard/collaboration changes, then broader checks when feasible.
