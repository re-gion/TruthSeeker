---
description: 
alwaysApply: true
---

# CLAUDE.md

## Project Overview

**TruthSeeker** — 跨模态 Deepfake 鉴伪与溯源系统（CISCN2026 竞赛项目）。基于 LangGraph 多智能体辩论架构，四个 Agent（Forensics、OSINT、Challenger、Commander）动态辩论并收敛出最终裁决。

```
Frontend (Next.js + React 19)          Backend (FastAPI + LangGraph)
├── 3D Bento UI (R3F v9)               ├── LangGraph State Machine (TypedDict)
├── Agent 实时状态可视化                ├── 四 Agent 辩论系统
├── 专家会诊协作模式                    ├── SSE 流式推送
└── Supabase Auth + Realtime            └── Supabase 持久化
```

## 当前进度（2026-04-21 审查）

- **M1 ✅ M2 ✅ M3 ✅** — 四 Agent 辩论完整运行，SSE 流式可用，专家会诊闭环
- **M4 ❌** — 部署和竞赛准备未开始
- 详见 `task.md` 获取完整任务状态

## 关键规则（违反会导致运行时错误）

1. **LangGraph State 必须用 TypedDict**，禁止 Pydantic BaseModel
2. **Motion 导入**: `import { motion } from "motion/react"`，不是 `"framer-motion"`
3. **Tailwind v4**: `@import "tailwindcss"` + `@theme {}`，不用 tailwind.config.js
4. **Supabase**: 用 `@supabase/ssr`，不是 `@supabase/auth-helpers`
5. **shadcn CLI**: 必须用 `npx shadcn@canary`（Tailwind v4 支持）
6. **Drei**: 必须用 v10（v9 不支持 React 19）
7. **Next.js 16**: Server Components 中 `cookies()` 必须 await

## 参考文档

| 文档 | 何时读 |
|------|--------|
| `docs/PRD.md` | 理解需求和业务逻辑 |
| `docs/TECH_STACK.md` | 安装依赖或升级包之前 |
| `docs/FRONTEND_GUIDELINES.md` | 写前端代码之前 |
| `docs/BACKEND_STRUCTURE.md` | 写后端代码之前 |
| `docs/APP_FLOW.md` | 设计 UI 交互或 API 契约之前 |
| `task.md` | 每次开发前确定当前任务 |
| `lessons.md` | 每次开发前回顾避免重复犯错 |

## 版本锁定

详见 `docs/TECH_STACK.md`。核心版本：
- Next.js 16.1.6 / React 19.2.3 / Tailwind CSS ^4.0.0
- FastAPI 0.134.0 / LangGraph >=1.0.9 / Python ^3.11
- motion ^12.34.3 / @react-three/fiber ^9.5.0 / @react-three/drei ^10.7.7
- @supabase/ssr ^0.8.0

## 环境变量

```bash
# truthseeker-web/.env.local
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# truthseeker-api/.env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
KIMI_API_KEY=
VIRUSTOTAL_API_KEY=
REALITY_DEFENDER_API_KEY=
```

## 测试账号

- 邮箱：gionre98@gmail.com
- 密码：@Zhangyujing0906
- 所有需要登录的测试、验证场景均使用此账号，不要再额外创建测试账号

## 任务管理

- **task.md** — 唯一任务来源，按顺序执行，完成后打勾
- **lessons.md** — 错误记录本，犯错后立即记录
- 遇到阻塞：查 `docs/TECH_STACK.md` → `docs/BACKEND_STRUCTURE.md` → `docs/PRD.md` → 记录到 lessons.md
