# TruthSeeker - GitHub Copilot Instructions

始终用中文回复对话内容，除非是专有名词、公式以及代码。

This file provides guidance to GitHub Copilot when working with code in this repository.

## Project Overview

**TruthSeeker** is a cross-modal deepfake detection system for the CISCN2026 competition. It uses a multi-agent architecture with LangGraph orchestration, featuring four specialized agents (Forensics, OSINT, Challenger, Commander) that debate and converge on a final verdict.

### High-Level Architecture

```
Frontend (Next.js 15 + React 19)
├── 3D Bento Box UI (React Three Fiber v9)
├── Real-time Agent State Visualization
└── Expert Collaboration Mode

Backend (FastAPI + LangGraph v1.0+)
├── LangGraph State Machine (TypedDict-based)
├── Four-Agent Debate System
│   ├── Forensics Agent (Audio/Video analysis)
│   ├── OSINT Agent (Threat intelligence)
│   ├── Challenger Agent (Logic verification)
│   └── Commander Agent (Final verdict)
└── SSE Streaming for Real-time Updates

Database (Supabase)
├── PostgreSQL with RLS
├── Realtime Broadcast/Presence
└── Vector storage for embeddings
```

## Technology Stack Lock

**Version freeze as of 2026-03-01 - DO NOT upgrade without verification:**

### Frontend
- Next.js ^15.2.0 with App Router
- React ^19.0.0
- Tailwind CSS ^4.0.0 (CSS-first config, no tailwind.config.js)
- shadcn/ui @canary (for Tailwind v4 support)
- **motion** ^12.9.2 (formerly framer-motion, import from `"motion/react"`)
- @react-three/fiber ^9.5.0 + @react-three/drei ^10.0.0
- @supabase/ssr ^0.5.0 (auth-helpers is deprecated)

### Backend
- FastAPI 0.134.0
- LangGraph >=1.0.9 (CRITICAL: State must use TypedDict, NOT Pydantic)
- Python ^3.11

Never skip ahead - each layer has defined deliverables and milestones.

## Reference Documents (MUST READ before coding)

The following documents in `/docs` directory contain authoritative specifications. **Always read the relevant document before implementing any feature:**

| Document | Path | Purpose | When to Read |
|----------|------|---------|--------------|
| **PRD.md** | `docs/PRD.md` | Product requirements, core business logic, agent definitions, competition scenarios | Before ANY implementation to understand requirements |
| **TECH_STACK.md** | `docs/TECH_STACK.md` | Version-locked dependencies, initialization commands, breaking changes | Before installing dependencies or upgrading packages |
| **IMPLEMENTATION_PLAN.md** | `docs/IMPLEMENTATION_PLAN.md` | 60-day roadmap, daily tasks, milestone checkpoints | At the start of each development day |
| **FRONTEND_GUIDELINES.md** | `docs/FRONTEND_GUIDELINES.md` | Next.js 15 patterns, Tailwind v4 config, motion imports, R3F setup | Before writing frontend code |
| **BACKEND_STRUCTURE.md** | `docs/BACKEND_STRUCTURE.md` | LangGraph v1.0+ patterns, TypedDict State, agent architecture, SSE implementation | Before writing backend code |
| **APP_FLOW.md** | `docs/APP_FLOW.md` | User journey, page flows, state transitions, Realtime events | Before designing UI interactions or API contracts |

### Development Workflow

1. **Before starting a task**: Read `IMPLEMENTATION_PLAN.md` to confirm current phase and priorities
2. **Before frontend coding**: Read `FRONTEND_GUIDELINES.md` + `TECH_STACK.md` (check versions)
3. **Before backend coding**: Read `BACKEND_STRUCTURE.md` + `TECH_STACK.md` (check LangGraph rules)
4. **Before UI design**: Read `APP_FLOW.md` + `PRD.md` (section 3.1 Frontend modules)
5. **Before adding dependencies**: Read `TECH_STACK.md` breaking changes section

### Critical Cross-References

- **Agent State structure**: `PRD.md` (section 2.1) + `BACKEND_STRUCTURE.md`
- **Color scheme/Tokens**: `PRD.md` (section 3.1) + `FRONTEND_GUIDELINES.md`
- **API Contracts**: `APP_FLOW.md` (state transitions) + `BACKEND_STRUCTURE.md` (endpoints)
- **Database Schema**: `BACKEND_STRUCTURE.md` + `PRD.md` (evidence board requirements)

## Critical Implementation Rules

### 1. LangGraph State Definition (MANDATORY)

```python
# CORRECT - Use TypedDict
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class TruthSeekerState(TypedDict):
    task_id: str
    messages: Annotated[list, add_messages]
    evidence_board: dict
    round_count: int

# WRONG - Never use Pydantic for State
from pydantic import BaseModel  # FORBIDDEN for State!
```

### 2. Motion Import Pattern

```tsx
// CORRECT
import { motion } from "motion/react"

// WRONG - Old package name
import { motion } from "framer-motion"
```

### 3. Tailwind v4 Configuration

```css
/* globals.css */
@import "tailwindcss";
@import "tw-animate-css"; /* Not tailwindcss-animate */

@theme {
  --color-indigo-ai: #6366F1;
  --color-cyber-lime: #D4FF12;
}
```

### 4. Supabase SSR Client

```tsx
// Use @supabase/ssr, never @supabase/auth-helpers
import { createBrowserClient } from '@supabase/ssr'
```

### 5. Next.js 15 Async APIs

```tsx
// CORRECT - Server Components must await cookies/headers
import { cookies } from 'next/headers'
const cookieStore = await cookies()

// WRONG
const cookieStore = cookies() // Missing await!
```

## Development Commands

### Frontend

```bash
cd truthseeker-web

npm install          # Install dependencies
npm run dev          # Development server (http://localhost:3000)
npm run build        # Production build
npm run lint         # ESLint check
```

### Backend

```bash
cd truthseeker-api

# Windows
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Tests
pytest
pytest tests/test_specific.py::test_function -v
```

### Database Migrations

```bash
# Via Supabase MCP
mcp__supabase__apply_migration
```

## Project Structure

```
truthseeker/
├── docs/                        # Authoritative spec documents
│   ├── PRD.md
│   ├── TECH_STACK.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── FRONTEND_GUIDELINES.md
│   ├── BACKEND_STRUCTURE.md
│   └── APP_FLOW.md
├── task.md                      # ⭐ Development task checklist (MUST follow)
├── lessons.md                   # ⭐ Error log & lessons learned (MUST update)
├── truthseeker-web/             # Next.js frontend
│   ├── app/                     # App Router pages
│   ├── components/
│   │   ├── ui/                  # shadcn components
│   │   ├── agents/              # Agent visualization
│   │   └── bento/               # 3D Bento grid
│   ├── lib/
│   │   └── supabase/            # Client/server utils
│   └── app/globals.css          # Tailwind v4 theme
├── truthseeker-api/             # FastAPI backend
│   ├── app/agents/              # LangGraph agent definitions
│   ├── app/graph/               # State machine workflow
│   ├── app/tools/               # External API integrations
│   └── app/main.py
└── .agents/skills/              # Available Copilot skills
```

## Task Management (CRITICAL)

### task.md - 开发任务清单

这是开发的**唯一任务来源**，按顺序列出了从 Layer 1 到 Polish 的所有开发任务。

**使用规范**:
1. **每次开发前**: 打开 `task.md`，找到第一个未完成的任务
2. **开发完成后**: 在 `[ ]` 中打勾 `[x]` 标记完成
3. **遇到阻塞**: 解决问题之后，立即将错误经验记录到 `lessons.md`，然后继续下一个任务
4. **禁止跳过**: 必须按顺序执行，不要跳跃式开发

**里程碑检查点**:
- M1 (Layer 1 完成): MVP 可演示视频检测
- M2 (Layer 2 完成): 四 Agent 辩论完整运行
- M3 (Layer 3 完成): 专家会诊可用（3D UI 可选）
- M4 (Polish 完成): 竞赛提交版本

### lessons.md - 错误记录本

记录开发中犯下的**所有错误**，用于避免重复犯错。

**使用规范**:
1. **每次犯错后**: 立即记录到 `lessons.md`
2. **记录内容**: 日期、错误描述、根本原因、解决方案、预防措施
3. **每日回顾**: 开始开发前快速浏览 `lessons.md`
4. **分类归档**: 按 LangGraph / 前端 / 后端 / 数据库等类别整理

## Agent Architecture

The core innovation is a **dynamic debate system** with convergence termination:

1. **Forensics Agent**: Analyzes video/audio using detection APIs
2. **OSINT Agent**: Investigates URLs, domains, threat intelligence
3. **Challenger Agent**: Critically examines evidence, requests re-analysis
4. **Commander Agent**: Weights all inputs, makes final verdict

**Convergence Algorithm**: When agent weight distributions change < threshold across two consecutive rounds, debate terminates.

## Available Skills

When working on specific areas, invoke these skills in Copilot Chat:

| Skill | Trigger Scenario |
|-------|-----------------|
| `ui-ux-pro-max` | UI/UX design decisions |
| `next-best-practices` | Next.js patterns review |
| `tailwind-design-system` | Theme/styling guidance |
| `supabase-postgres-best-practices` | Database optimization |
| `vercel-react-best-practices` | Performance optimization |
| `systematic-debugging` | Bug investigation |
| `test-driven-development` | Before writing feature code |

## Environment Variables

### Frontend (`.env.local`)

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Backend (`.env`)

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
VIRUSTOTAL_API_KEY=
DEEPFAKE_API_KEY=
```

## Common Pitfalls

1. **Wrong shadcn CLI**: Must use `npx shadcn@canary` for Tailwind v4
2. **Pydantic State in LangGraph**: Will cause runtime errors — always use `TypedDict`
3. **framer-motion import**: Package renamed to `motion`, import from `"motion/react"`
4. **Drei version mismatch**: Drei v9 doesn't work with React 19, must use v10
5. **async cookies() in Next.js 15**: Server Components must `await cookies()`
6. **tailwindcss-animate**: Use `tw-animate-css` instead

## Layer-Based Development

Follow the implementation plan strictly by layers:

- **Layer 1 (Week 1-2)**: Core video detection, 2 Agents, basic UI
- **Layer 2 (Week 3-4)**: Full multimodal, 4 Agents, debate system
- **Layer 3 (Week 5-6)**: 3D UI, expert collaboration
- **Polish (Week 7-8)**: Competition demo preparation
