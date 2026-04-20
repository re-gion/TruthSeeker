# TruthSeeker Web Agent Guide

## Scope

This file applies to `truthseeker-web/`.

## Runtime And Commands

Use npm because this project commits `package-lock.json`:

```powershell
cd truthseeker-web
npm install
npm run lint
npm run typecheck
npm run test:unit
npm run build
npm run dev
```

The frontend defaults to `http://localhost:3000` and expects the backend at `NEXT_PUBLIC_API_BASE_URL`, normally `http://localhost:8000`.

## Architecture Map

- `app/` - Next.js App Router pages, layouts, route handlers, and global CSS.
- `components/` - feature components and shared UI.
- `components/landing/` - marketing and product-story sections.
- `components/detect/` - detection console and evidence timeline.
- `components/dashboard/` - data dashboard charts and view.
- `components/collaboration/` - expert consultation and presence UI.
- `hooks/` - client interaction, realtime, and animation hooks.
- `lib/` - shared mapping, Supabase clients, reports, and utilities.
- `public/` - icons, images, and local fonts.

## Frontend Rules

- Use Next.js App Router conventions. Components are server components by default; add `"use client"` only for hooks, browser APIs, realtime, animation, or interactive state.
- Use `@/*` imports for project-local modules.
- Use `motion` from `motion/react`; do not import `framer-motion`.
- Tailwind CSS is v4: keep theme tokens in CSS with `@import "tailwindcss"` and `@theme`; do not add `tailwind.config.js` unless the project intentionally migrates.
- When adding shadcn/ui components, use the canary-compatible CLI pattern from project docs; do not assume older Tailwind v3 defaults.
- Use `tw-animate-css` for Tailwind v4 animation utilities; do not add `tailwindcss-animate`.
- Use `@supabase/ssr` for SSR auth flows, not deprecated auth-helper packages.
- Server Components using request APIs must follow the installed Next.js version behavior; verify with `npm run typecheck`.
- Preserve the "digital forensic laboratory" visual language from `docs/FRONTEND_GUIDELINES.md`: dark default theme, Indigo AI, Cyber Lime accents, Liquid Glass surfaces, Bento layouts, purposeful motion, and accessible contrast.
- For 3D work, keep `@react-three/fiber` and `@react-three/drei` versions compatible with React 19; verify visually if a dev server can run.
- Do not place secrets in client code. Only `NEXT_PUBLIC_*` variables may be read by browser code.

## Testing And Verification

- For TypeScript or component changes, run `npm run lint` and `npm run typecheck`.
- For dashboard or pure mapping logic, run `npm run test:unit`.
- For layout, animation, or responsive UI changes, run the dev server and inspect the affected page in a browser when feasible.
- For production-impacting changes, run `npm run build` before completion.
