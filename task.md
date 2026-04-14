# TruthSeeker 开发任务清单

> **使用说明**: 按顺序自上而下执行任务，每完成一项在 `[ ]` 中打勾 `[x]`。遇到阻塞问题立即记录到 `lessons.md`。
> **最后审查日期**: 2026-04-14（基于代码事实核验）

---

## 里程碑总览

- [x] **M1 - MVP可用**: Layer1完成（视频检测 + 双Agent + SSE）
- [x] **M2 - 完整辩论**: Layer2完成（全模态 + 四Agent + 收敛算法）
- [ ] **M3 - 专家会诊**: Layer3核心完成（Realtime协作，3D可选）
- [ ] **M4 - 竞赛就绪**: Polish完成（部署 + 演示准备）

---

## Layer 1: 核心鉴伪能力（MVP） ✅ 已完成

### Phase 1.1: 基础设施搭建 ✅

#### 1.1.1 项目初始化
- [x] 前端: Next.js 项目创建、shadcn@canary 初始化、Tailwind v4 配置
- [x] 前端依赖安装（motion、R3F、Supabase SSR 等）
- [x] 后端: FastAPI 项目结构创建、虚拟环境、依赖安装
- [x] Supabase 项目创建、环境变量配置

#### 1.1.2 基础 UI 框架
- [x] 根布局 `app/layout.tsx`、Header 组件
- [x] Tailwind v4 主题配置（@theme 指令、品牌色）
- [x] 文件上传组件 `FileUploader.tsx`（拖拽上传、类型验证、进度条）

#### 1.1.3 Supabase 集成
- [x] Supabase Client 配置（client.ts + server.ts，使用 @supabase/ssr）
- [x] 用户认证（注册、登录、登出，使用 Server Actions）
- [x] 认证中间件 `middleware.ts`（路由保护）
- [x] **数据库 Schema 迁移** — tasks 表已通过 Supabase 迁移创建
- [x] **RLS 策略** — 已配置（users_own_tasks + anon_tasks_insert）
- [x] 任务 API（POST/GET /api/v1/tasks，含 Supabase 持久化 + 降级）

### Phase 1.2: 双 Agent 核心流程 ✅

#### 1.2.1 LangGraph 基础
- [x] State 定义（TypedDict，`app/agents/state.py`）
- [x] Forensics Agent（`nodes/forensics.py`，调用 Deepfake API + mock 降级）
- [x] Commander Agent（`nodes/commander.py`，动态权重 + 四级裁决）
- [x] 工作流编排（`graph.py`，StateGraph 完整拓扑）

#### 1.2.2 SSE 实时推送
- [x] FastAPI SSE 端点（`detect.py`，StreamingResponse）
- [x] 前端 `useAgentStream.ts`（SSE 连接 + 事件解析）
- [x] AgentLog 打字机效果（`AgentLog.tsx`）

#### 1.2.3 MVP 整合
- [x] 端到端流程：上传 → 创建任务 → SSE 推送 → 展示结果
- [x] **文件实际上传** — FileUploader 先上传文件到后端，获取真实 Supabase Storage URL

**✅ M1 已达成**: 可上传视频并查看检测结果（使用 mock URL 方案）

---

## Layer 2: 全模态与四 Agent 完整辩论 ✅ 已完成

### Phase 2.1: 多模态扩展

#### 2.1.1 Agent 扩展
- [x] OSINT Agent（`nodes/osint.py`，URL 威胁分析 + 域名声誉）
- [x] VirusTotal API 集成（`tools/threat_intel.py`，真实 API + mock 降级）
- [x] Challenger Agent（`nodes/challenger.py`，三层质疑逻辑 + 打回重审）

#### 2.1.2 收敛机制
- [x] 收敛判定逻辑（`edges/conditions.py`，权重变化 + 置信度历史）
- [x] 条件边路由（proceed_to_commander / return_to_forensics / return_to_osint）
- [x] 最大轮数兜底

#### 2.1.3 完整流程
- [x] 四 Agent 协同（Forensics → OSINT → Challenger → [条件路由] → Commander）
- [x] 测试脚本（`test_graph.py`）

### 未实现的 Layer2 计划项（降低优先级）
- [ ] 音频特征提取（频谱分析、声纹提取）— 当前通过 API 调用实现
- [ ] 图片 EXIF 解析 — 当前通过 API 调用实现
- [ ] 网页内容抓取 / Whois 查询 — 非核心功能
- [ ] 权重变化图表 / 收敛过程动画 — 前端可视化待补充

**✅ M2 已达成**: 四 Agent 辩论完整运行

---

## Layer 3: 专家会诊与 3D UI

### Phase 3.1: 专家会诊（核心差异化）

#### 3.1.1 Supabase Realtime
- [x] Broadcast 通道（前端 `useAgentStream.ts` 中有广播发送）
- [x] Presence 实现（`useRealtimeSession.ts`，在线用户感知 + 角色标识）
- [ ] **后端 Broadcast 推送** — 后端 SSE 端点未主动向 Supabase Broadcast 推送，仅前端转发

#### 3.1.2 专家会诊模式
- [x] 邀请机制（邀请码 + 邀请链接，`InviteButton.tsx`）
- [x] 权限控制（主持人/专家/访客三种角色）
- [x] 专家会诊面板（`ExpertPanel.tsx`，实时聊天 + 消息同步）
- [ ] **暂停/恢复辩论** — 前端有 UI 概念，但后端无暂停 LangGraph 执行的机制
- [ ] **投票决策** — 未实现
- [ ] 二维码生成 — 已推迟

#### 3.1.3 报告与导出
- [x] Markdown 报告生成（`lib/report.ts`，结构化模板 + 浏览器下载）
- [ ] PDF 导出
- [ ] 报告分享链接

### Phase 3.2: 3D Bento Box ✅
- [x] R3F 场景搭建（`BentoScene.tsx`，Canvas + 相机 + 光照）
- [x] Liquid Glass 效果（CSS glassmorphism + 3D glass shards）
- [x] 动画与过渡（面板切换、滚动视差、微交互）

**⏳ M3 部分达成**: 专家会诊 UI 可用，但后端协作机制不完整

---

## Polish: 竞赛优化与演示准备

### Phase 4.1: 竞赛功能完善 ✅
- [x] 演示案例库（4 个内置案例，`DemoCaseSelector.tsx`）
- [x] 数据大屏（统计仪表盘 + 3D 地球 + 图表，使用硬编码数据）
- [x] 实时对抗演示（对比视图 + 对抗工具箱）

### Phase 4.2: 最终优化与部署
- [x] **后端认证中间件** — JWT 鉴权中间件已实现（条件注册，公开路由白名单）
- [x] **输入验证加固** — 文件类型白名单、大小限制（upload.py 中实现）
- [x] 速率限制（`rate_limit.py`，基于 IP 的滑动窗口）
- [ ] Vercel 部署（前端）
- [ ] 后端部署（Render/Railway）
- [ ] 竞赛答辩 PPT
- [ ] 演示视频录制

---

## 待补充的新任务（后端完善）

### 数据库与持久化
- [x] 通过 Supabase 迁移创建 tasks 表 Schema
- [x] 配置 RLS 策略（用户只能访问自己的任务）
- [x] 创建 `.env.example` 文件（前端 + 后端）

### 后端安全与健壮性
- [x] 后端认证中间件（验证 Supabase JWT）
- [ ] 全局异常处理器
- [ ] 结构化日志
- [x] 文件上传端点（接收文件 → 存储 → 返回 URL）

### 测试
- [ ] 后端单元测试（Agent 节点、条件边）
- [ ] API 集成测试
- [ ] 前后端联调测试

### 前端补全
- [x] Dashboard 接入真实数据（替换硬编码）
- [ ] 案例库真实加载功能
- [x] 文件上传进度条接入真实进度

---

## 每日开发检查清单

开始前：
- [ ] 查看 task.md 确定当前任务
- [ ] 回顾 lessons.md 避免重复犯错

结束时：
- [ ] 更新 task.md 任务状态
- [ ] 记录问题到 lessons.md
- [ ] Git commit
