---
description: 
alwaysApply: true
---

---
description: 
alwaysApply: true
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TruthSeeker** is a cross-modal deepfake detection system for the CISCN2026 competition. It uses a multi-agent architecture with LangGraph orchestration, featuring four specialized agents (Forensics, OSINT, Challenger, Commander) that debate and converge on a final verdict.

### High-Level Architecture

```
Frontend (Next.js15 + React19)
├──3D Bento Box UI (React Three Fiber v9)
├── Real-time Agent State Visualization
└── Expert Collaboration Mode

Backend (FastAPI + LangGraph v1.0+)
├── LangGraph State Machine (TypedDict-based)
├── Four-Agent Debate System
│ ├── Forensics Agent (Audio/Video analysis)
│ ├── OSINT Agent (Threat intelligence)
│ ├── Challenger Agent (Logic verification)
│ └── Commander Agent (Final verdict)
└── SSE Streaming for Real-time Updates

Database (Supabase)
├── PostgreSQL with RLS
├── Realtime Broadcast/Presence
└── Vector storage for embeddings
```

## Technology Stack Lock

**Version freeze as of2026-03-01 - DO NOT upgrade without verification:**

### Frontend
- Next.js ^15.2.0 with App Router
- React ^19.0.0
- Tailwind CSS ^4.0.0 (CSS-first config, no tailwind.config.js)
- shadcn/ui @canary (for Tailwind v4 support)
- **motion** ^12.9.2 (formerly framer-motion, import from "motion/react")
- @react-three/fiber ^9.5.0 + @react-three/drei ^10.0.0
- @supabase/ssr ^0.5.0 (auth-helpers is deprecated)

### Backend
- FastAPI0.134.0
- LangGraph >=1.0.9 (CRITICAL: State must use TypedDict, NOT Pydantic)
- Python ^3.11

Never skip ahead - each layer has defined deliverables and milestones.

## Reference Documents (MUST READ before coding)

The following documents in `/docs` directory contain authoritative specifications. **Always read the relevant document before implementing any feature:**

| Document | Path | Purpose | When to Read |
|----------|------|---------|--------------|
| **PRD.md** | `docs/PRD.md` | Product requirements, core business logic, agent definitions, competition scenarios | Before ANY implementation to understand requirements |
| **TECH_STACK.md** | `docs/TECH_STACK.md` | Version-locked dependencies, initialization commands, breaking changes | Before installing dependencies or upgrading packages |
| **IMPLEMENTATION_PLAN.md** | `docs/IMPLEMENTATION_PLAN.md` |60-day roadmap, daily tasks, milestone checkpoints | At the start of each development day |
| **FRONTEND_GUIDELINES.md** | `docs/FRONTEND_GUIDELINES.md` | Next.js15 patterns, Tailwind v4 config, motion imports, R3F setup | Before writing frontend code |
| **BACKEND_STRUCTURE.md** | `docs/BACKEND_STRUCTURE.md` | LangGraph v1.0+ patterns, TypedDict State, agent architecture, SSE implementation | Before writing backend code |
| **APP_FLOW.md** | `docs/APP_FLOW.md` | User journey, page flows, state transitions, Realtime events | Before designing UI interactions or API contracts |

### Development Workflow

1. **Before starting a task**: Read IMPLEMENTATION_PLAN.md to confirm current phase and priorities
2. **Before frontend coding**: Read FRONTEND_GUIDELINES.md + TECH_STACK.md (check versions)
3. **Before backend coding**: Read BACKEND_STRUCTURE.md + TECH_STACK.md (check LangGraph rules)
4. **Before UI design**: Read APP_FLOW.md + PRD.md (section3.1 Frontend modules)
5. **Before adding dependencies**: Read TECH_STACK.md breaking changes section

### Critical Cross-References

- **Agent State structure**: PRD.md (section2.1) + BACKEND_STRUCTURE.md
- **Color scheme/Tokens**: PRD.md (section3.1) + FRONTEND_GUIDELINES.md
- **API Contracts**: APP_FLOW.md (state transitions) + BACKEND_STRUCTURE.md (endpoints)
- **Database Schema**: BACKEND_STRUCTURE.md + PRD.md (evidence board requirements)

## Critical Implementation Rules

###1. LangGraph State Definition (MANDATORY)

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
from pydantic import BaseModel # FORBIDDEN for State!
```

###2. Motion Import Pattern

```tsx
// CORRECT
import { motion } from "motion/react"

// WRONG - Old package name
import { motion } from "framer-motion"
```

###3. Tailwind v4 Configuration

```css
/* globals.css */
@import "tailwindcss";
@import "tw-animate-css"; /* Not tailwindcss-animate */

@theme {
 --color-indigo-ai: #6366F1;
 --color-cyber-lime: #D4FF12;
}
```

###4. Supabase SSR Client

```tsx
// Use @supabase/ssr, never @supabase/auth-helpers
import { createBrowserClient } from '@supabase/ssr'
```

## Development Commands

### Frontend Setup
```bash
cd truthseeker-web

# Install dependencies
npm install

# Development server
npm run dev

# Build
npm run build

# Lint
npm run lint
```

### Backend Setup
```bash
cd truthseeker-api

# Virtual environment
python -m venv venv
source venv/bin/activate # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Development server
uvicorn main:app --reload --port8000

# Run tests
pytest
pytest tests/test_specific.py::test_function -v # Single test
```

### Database Migrations
```bash
# Using Supabase MCP
mcp__supabase__apply_migration
```

## Project Structure

```
truthseeker/
├── docs/ # Design documents (authoritative specs)
│ ├── PRD.md # Product requirements
│ ├── TECH_STACK.md # Version-locked dependencies
│ ├── IMPLEMENTATION_PLAN.md #60-day roadmap
│ ├── FRONTEND_GUIDELINES.md # Frontend architecture
│ ├── BACKEND_STRUCTURE.md # Backend architecture
│ └── APP_FLOW.md # User flows & state transitions
├── task.md # ⭐ Development task checklist (MUST follow)
├── lessons.md # ⭐ Error log & lessons learned (MUST update)
├── CLAUDE.md # This file - project guide for Claude Code
├── truthseeker-web/ # Next.js frontend
│ ├── app/ # App Router pages
│ ├── components/
│ │ ├── ui/ # shadcn components
│ │ ├── agents/ # Agent visualization
│ │ └── bento/ #3D Bento grid
│ ├── lib/
│ │ └── supabase/ # Client/server utils
│ └── globals.css # Tailwind v4 theme
├── truthseeker-api/ # FastAPI backend
│ ├── agents/ # LangGraph agent definitions
│ ├── graph/ # State machine workflow
│ ├── tools/ # External API integrations
│ └── main.py
└── .agents/skills/ # Available skills for this project
```

## Task Management (CRITICAL)

### task.md -开发任务清单
**位置**: `task.md` (项目根目录)

这是开发的**唯一任务来源**，按顺序列出了从 Layer1到 Polish的所有开发任务。

**使用规范**:
1. **每次开发前**:打开 task.md，找到第一个未完成的任务
2. **开发完成后**:在 `[ ]`中打勾 `[x]`标记完成
3. **遇到阻塞**:解决问题之后，立即将错误经验记录到 lessons.md，然后继续下一个可执行任务
4. **禁止跳过**:必须按顺序执行，不要跳跃式开发

**里程碑检查点**:
- M1 (Layer1完成): MVP可演示视频检测
- M2 (Layer2完成):四Agent辩论完整运行
- M3 (Layer3完成):专家会诊可用（3D UI可选）
- M4 (Polish完成):竞赛提交版本

### lessons.md -错误记录本
**位置**: `lessons.md` (项目根目录)

记录开发中犯下的**所有错误**，用于避免重复犯错。

**使用规范**:
1. **每次犯错后**:立即记录到 lessons.md
2. **记录内容**:日期、错误描述、根本原因、解决方案、预防措施
3. **每日回顾**:开始开发前快速浏览 lessons.md
4. **分类归档**:按 LangGraph/前端/后端/数据库等类别整理

**常见陷阱速查** (必须在 lessons.md中记录):
- LangGraph State用 TypedDict而非 Pydantic
- motion导入路径是 `motion/react`而非 `framer-motion`
- Tailwind v4用 `@import "tailwindcss"`而非三行 `@tailwind`
- Drei必须用 v10才能支持 React19
- Supabase用 `@supabase/ssr`而非 auth-helpers

## Agent Architecture

The core innovation is a **dynamic debate system** with convergence termination:

1. **Forensics Agent**: Analyzes video/audio using detection APIs
2. **OSINT Agent**: Investigates URLs, domains, threat intelligence
3. **Challenger Agent**: Critically examines evidence, requests re-analysis
4. **Commander Agent**: Weights all inputs, makes final verdict

**Convergence Algorithm**: When agent weight distributions change < threshold across two consecutive rounds, debate terminates.

## Available Skills/MCPs

When working on specific areas, invoke these skills:

- `ui-ux-pro-max`: UI/UX design decisions
- `next-best-practices`: Next.js patterns review
- `tailwind-design-system`: Theme/styling guidance
- `supabase-postgres-best-practices`: Database optimization
- `vercel-react-best-practices`: Performance optimization

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Backend (.env)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
VIRUSTOTAL_API_KEY=
DEEPFAKE_API_KEY=
```

## Common Pitfalls

1. **Using wrong shadcn CLI**: Must use `npx shadcn@canary` for Tailwind v4
2. **Pydantic State in LangGraph**: Will cause runtime errors - always use TypedDict
3. **framer-motion import**: Package renamed to `motion`
4. **Drei version mismatch**: Drei v9 doesn't work with React19, must use v10
5. **async cookies() in Next.js15**: Server Components must await cookies()

## Layer-Based Development

Follow the implementation plan strictly by layers:

- **Layer1 (Week1-2)**: Core video detection,2 Agents, basic UI
- **Layer2 (Week3-4)**: Full multimodal,4 Agents, debate system
- **Layer3 (Week5-6)**:3D UI, expert collaboration
- **Polish (Week7-8)**: Competition demo preparation
