# TruthSeeker 开发任务清单

> **使用说明**: 按顺序自上而下执行任务，每完成一项在 `[ ]` 中打勾 `[x]`。遇到阻塞问题立即记录到 `lessons.md`。
> **最后审查日期**: 2026-06-06（文档一致性、GitHub README 与代理指引同步）

---

## 里程碑总览

- [x] **M1 - MVP可用**: Layer1完成（视频检测 + 双Agent + SSE）
- [x] **M2 - 完整辩论**: Layer2完成（全模态 + 四Agent + 收敛算法）
- [x] **M3 - 人机协同**: Layer3核心完成（Realtime 协作、协同暂停/恢复、专家邀请、3D 可选）
- [ ] **M4 - 竞赛就绪**: Polish完成（部署 + 演示准备）

---

## 2026-04-20 P0/P1/P2 闭环修复 ✅

### P0 — 多文件真实检测入口

- [x] 前端上传改为最多 5 个文件；前端统一预检 250MB，后端按模态执行视频 250MB、音频 20MB、图片 50MB、文本 5MB 限制。
- [x] 文本框改为全局检测提示词，不再允许仅凭提示词创建检测任务。
- [x] 重建后端为阶段式流程：电子取证 Agent -> Challenger -> OSINT 图谱 Agent -> Challenger -> Commander -> END。
- [x] `forensics` 对外协议 key 保留，但用户可见语义改为电子取证 Agent。
- [x] 可配置全模态 Agent LLM 作为四 Agent 共享多模态推理基座；默认 Kimi 2.5，工具结果 all-settled 后再进入 Agent 推理。
- [x] 新增 Exa 后端搜索工具和 provenance graph，并在检测台新增图谱视图。
- [x] 安装 `@xyflow/react` ^12.10.2 并将图谱视图替换为 React Flow 交互渲染（支持拖拽、缩放、节点详情面板）。
- [x] 任务创建保存 `case_prompt`、文件清单、模态和 storage path。
- [x] 检测页按 `taskId` 从后端任务记录启动检测，不再通过 URL 传 signed file URL。
- [x] 检测失败会写入 `failed` 状态并向前端发送 `task_failed`。

### P1 — 安全边界与可信流程

- [x] 上传、建任务、检测、报告下载、创建分享均要求登录。
- [x] 后端只信任 JWT 中的 `request.state.user_id`，忽略客户端传入的 `user_id`。
- [x] 外部专家凭邀请令牌提交协同意见；主持人创建邀请和继续研判必须登录。
- [x] 阶段式收敛：目标 Agent 最多 5 轮，前 4 轮低于 0.8 必须打回，第 5 轮上限放行并标注残留风险；质量变化阈值 0.08。
- [x] 低置信停滞时通过 LangGraph in-process interrupt/checkpointer 暂停为 `waiting_collaboration`，旧 `waiting_consultation` 保留兼容；checkpoint 丢失时可基于持久化快照兜底裁决。
- [x] 主持人使用同一 `taskId` 触发 `resume=true` 继续研判。
- [x] 协同面板加载历史消息，并显示等待协同/继续研判状态。

### P2 — 报告可信输出与文档

- [x] 新增 `reports.report_hash` 和 `audit_logs` 迁移。
- [x] 报告 hash 使用 SHA-256 稳定 JSON 哈希，分享页和 Markdown 报告展示 hash。
- [x] 审计日志覆盖 upload、task_create、detect_start、detect_failed、detect_completed、report_generated、report_downloaded、share_created、share_viewed、collaboration_message、collaboration_resume（旧 consultation_* 兼容）。
- [x] 白皮书中的联邦学习底座正式名称统一为 Fed-MBPR。
- [x] `docs/APP_FLOW.md`、`docs/BACKEND_STRUCTURE.md` 已同步最新流程。
- [x] 公开案例库真实加载：用户授权公开后，完整报告生成才入库，支持去重、分页筛选和短期检材预览。
- [x] 公开案例库 RAG 工具化：pgvector 分块索引、SiliconFlow embedding 配置、Forensics/OSINT 内部检索、报告展示调用情况。
- [x] 个人经验库：人机协同结束后生成可编辑经验草稿，按账号和目标 Agent 去重后展示；用户单独确认入库，Forensics/OSINT/Challenger 按账号私有检索；支持列表、详情和删除。
- [x] 溯源图谱引用质量：上传检材、工具结果、外源、公开案例 RAG、个人经验 RAG 统一生成带 `source_kind` 的 citation，claim/tool finding/source edge 绑定 `citation_ids`，质量门槛为 `citation_coverage >= 0.60`、`model_inferred_ratio <= 0.35`。
- [x] 报告结构：第五章合并公开案例与个人经验 RAG，第六章合并逻辑质询时间线，按置信度、下一步行动、人机协同、发现问题和放行/打回说明展示。

## 2026-04-21 调研报告问题修复 ✅

- [x] 补 `20260415_baseline_schema_rls.sql`，让核心表、索引和 RLS policy 在仓库内可从零复现。
- [x] 生产环境强制要求真实 `SUPABASE_JWT_SECRET`，避免 `NOT_SET` 被误用于生产鉴权。
- [x] 前端 MD 下载改走后端 canonical 报告接口，和 PDF、分享页保持同一来源。
- [x] Dashboard 和任务列表不再把后端数据源异常伪装成空数据；Dashboard 会返回并展示 `data_warnings`。
- [x] 文本上传增加扩展名、编码和控制字符比例校验，降低二进制伪装为文本的风险。
- [x] 降级 mock 改为 SHA-256 稳定派生，避免同一输入跨进程出现不同风险分数。
- [x] 协同恢复在内存 checkpoint 丢失时，可从 `analysis_states` 和协同消息重建 Commander 可裁决状态。
- [x] 分享报告页支持 Markdown 表格渲染，报告权重表不再显示为原始 `|` 文本。
- [x] 注册成功后保留页面成功态，不再立即跳转导致提示不可见。
- [x] 删除 Forensics Agent 中不可达的文本检测分支，文本检材只由 OSINT 处理。
- [x] 公开案例库真实加载：新增独立案例表、公开 API、前端列表/详情页和保守脱敏。
- [x] 公开案例库 RAG：真实公开案例和内置展示案例可作为类案参考，内置案例支持点击查看 Markdown 报告。
- [ ] Fed-MBPR 训练底座运行时代码暂不实现，白皮书/PRD 保持目标架构叙事。
- [ ] 部署配置暂不实现。

## 2026-04-28 审计日志与降级可见性增强 ✅

- [x] 全库降级/模拟结果在后端终端和鉴伪溯源报告中可见（osint_search、threat_intel、report_generator 等 16 处修复）。
- [x] `audit_logs` 表增加 `agent` 字段和索引，支持按 Agent 追溯。
- [x] 四 Agent 节点（forensics/osint/commander/challenger）关键位置插入审计日志调用。
- [x] SSE 流 `node_complete` 处补充审计事件。
- [x] `audit_log.py` 成功写入时输出格式化终端日志 `[AUDIT][AGENT] action | task=xxx`。
- [x] 删除前端废弃 `generateMarkdownReport` 及相关死代码。

## 2026-04-29 人机协同机制文档同步

- [x] 将根目录协同草稿整理进 `docs/PRD.md`、`docs/APP_FLOW.md` 和 `docs/BACKEND_STRUCTURE.md`。
- [x] 明确三轮低置信停滞触发、首次自动协同、重复触发需用户审批、Commander 主持摘要、用户控制结束、邀请 TTL、结构化消息、摘要确认、报告和时间线影响。
- [x] 后端实现 `collaboration_sessions` / `collaboration_trigger_history` 等状态字段，旧 `consultation_*` 只作兼容。
- [x] API 与前端补齐协同摘要确认、重复触发审批、用户结束协同和结构化消息类型。
- [x] 报告与时间线补齐协同摘要确认、恢复或结束后的可见记录。

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
- [x] **数据库 Schema 迁移** — 历史阶段曾完成 9 表/17 迁移同步；当前新增表与 Storage 初始化仍需按 `docs/KNOWN_GAPS.md` 复核
- [x] **RLS 策略** — 历史核心表已启用 RLS；公开案例写策略仍存在待修复的过宽权限
- [x] 任务 API（POST/GET /api/v1/tasks，含 Supabase 持久化 + 降级）

### Phase 1.2: 双 Agent 核心流程 ✅

#### 1.2.1 LangGraph 基础
- [x] State 定义（TypedDict，`app/agents/state.py`）
- [x] Forensics Agent（`nodes/forensics.py`，Reality Defender 真实 API + LLM 推理；文本检材改由 OSINT 处理）
- [x] Commander Agent（`nodes/commander.py`，动态权重 + LLM 裁决报告 + 降级权重调整）
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
- [x] OSINT Agent（`nodes/osint.py`，URL/文件哈希/元数据分析 + LLM 推理 + 文本URL提取）
- [x] VirusTotal API 集成（`tools/threat_intel.py`，URL扫描+域名声誉+文件哈希扫描+元数据提取）
- [x] Challenger Agent（`nodes/challenger.py`，规则检查 + LLM 交叉验证 + 专家意见读取）

#### 2.1.2 收敛机制
- [x] 收敛判定逻辑（`edges/conditions.py`，权重变化 + 置信度历史）
- [x] 条件边路由（proceed_to_commander / return_to_forensics / return_to_osint）
- [x] 最大轮数兜底

#### 2.1.3 完整流程
- [x] 四 Agent 协同（Forensics → Challenger → OSINT → Challenger → Commander；条件路由可打回当前目标 Agent 或暂停进入人机协同）
- [x] 测试脚本（`test_graph.py`）

### 未实现的 Layer2 计划项（降低优先级，能通过API调用实现的就先通过API调用来实现）
- [ ] 音频特征提取（频谱分析、声纹提取）— 当前通过 API 调用实现
- [ ] 图片 EXIF 解析 — 当前通过 API 调用实现
- [ ] 权重变化图表 / 收敛过程动画 — 前端可视化待补充

**✅ M2 已达成**: 四 Agent 辩论完整运行

---

## Layer 3: 人机协同与 3D UI

### Phase 3.1: 人机协同（核心差异化）

#### 3.1.1 Supabase Realtime
- [x] Broadcast 通道（前端 `useAgentStream.ts` 中有广播发送）
- [x] Presence 实现（`useRealtimeSession.ts`，在线用户感知 + 角色标识）
- [x] **后端 Broadcast 推送** — 后端 SSE 端点未主动向 Supabase Broadcast 推送，仅前端转发（通过 collaboration API 实现消息注入）

#### 3.1.2 人机协同模式
- [x] 邀请机制（邀请码 + 邀请链接，`InviteButton.tsx`）
- [x] 权限控制（主持人/专家/访客三种角色）
- [x] 人机协同面板（`ExpertPanel.tsx`，实时聊天 + 消息同步）

#### 3.1.3 报告与导出
- [x] Markdown 报告生成（后端 canonical 报告下载；前端模板保留为辅助生成逻辑）
- [x] PDF 导出
- [x] 报告分享链接

### Phase 3.2: 3D Bento Box ✅
- [x] R3F 场景搭建（`BentoScene.tsx`，Canvas + 相机 + 光照）
- [x] Liquid Glass 效果（CSS glassmorphism + 3D glass shards）
- [x] 动画与过渡（面板切换、滚动视差、微交互）

**✅ M3 已达成**: 人机协同 UI + 后端消息闭环 + 暂停/恢复研判可用；投票机制暂不作为本轮目标

---

## Polish: 竞赛优化与演示准备

### Phase 4.1: 竞赛功能完善 ✅
- [x] 公开案例库（4 个内置展示案例 + 授权公开的真实历史检测案例）
- [x] 数据大屏（统计仪表盘 + 3D 地球 + 图表，使用硬编码数据）
- [x] 实时对抗演示（对比视图 + 对抗工具箱）

### Phase 4.2: 最终优化与部署（最终的部署先不做、PPT、视频先不做）
- [x] **后端认证中间件** — JWT 鉴权中间件已实现（条件注册，公开路由白名单）
- [x] **输入验证加固** — 文件类型白名单、大小限制（upload.py 中实现）
- [x] 速率限制（`rate_limit.py`，基于 IP 的滑动窗口）
- [ ] Vercel 部署（前端）
- [ ] 后端部署（Render/Railway）
- [ ] 竞赛答辩 PPT
- [ ] 演示视频录制

---

## 待补充的新任务（后端完善）

### P0 — 真实 API 集成（2026-04-15 完成）
- [x] **修复 config.py 环境变量映射** — Kimi_API_KEY、Virus_Total、Reality_Defender 字段映射
- [x] **Reality Defender API 真实集成** — 3步异步流程（presigned → upload → poll），`deepfake_api.py` 完整重写
- [x] **VirusTotal API 增强** — 新增 `scan_file_hash()`、`check_domain_reputation()`、`extract_media_metadata()`
- [x] **Kimi/Moonshot LLM 客户端** — `llm_client.py`，四个 Agent 专用函数
- [x] **智能降级控制器** — `fallback.py`，DegradationManager 三级降级（full/degraded/minimal）
- [x] **文本检测通道** — `text_detection.py`，LLM 文本分析 + URL提取 + 结构分析

### P1 — 四 Agent LLM 推理集成（2026-04-15 完成）
- [x] **Forensics Agent 重写** — 媒体鉴伪通道，Reality Defender API + LLM 推理；文本文件交由 OSINT
- [x] **OSINT Agent 增强** — 媒体文件哈希扫描+元数据分析并发，文本URL提取，LLM 推理
- [x] **Challenger Agent 重写** — 规则检查+LLM交叉验证+专家意见读取
- [x] **Commander Agent 重写** — 动态降级权重+LLM裁决报告+时间轴事件

### P2 — 端到端闭环（2026-04-15 完成）
- [x] **后端报告生成** — `report_generator.py`，Markdown + fpdf2 文本型 PDF 生成，Pillow 图像 PDF 兜底
- [x] **报告下载 API** — `report.py`，GET /md + GET /pdf + GET /audit-log.md + GET /audit-log.pdf 端点
- [x] **证据时间轴前端** — `EvidenceTimeline.tsx`，垂直时间轴+Agent颜色编码+动画
- [x] **人机协同后端闭环** — `consultation.py`，消息注入+Supabase持久化+Agent读取；新入口 `/collaboration`，旧 `/consultation` 兼容
- [x] **DetectConsole 集成** — 时间轴视图切换 + PDF下载按钮
- [x] **State 新增字段** — degradation_status、expert_messages、timeline_events

### 数据库与持久化
- [x] 通过 Supabase 基线迁移定义全部 9 表 Schema，并新增 `collaboration_sessions`、`collaboration_invites`、`collaboration_messages` 双表迁移兼容旧 `consultation_*`
- [x] 历史核心 9 表已配置 RLS；公开案例与 RAG 写策略仍需收紧
- [x] 历史远端曾执行 17 次迁移；当前新增迁移与线上状态需重新核验
- [x] `analysis_states.result_snapshot` 列已补齐（代码依赖此字段做人机协同恢复）
- [x] 创建 `.env.example` 文件（前端 + 后端）

### 后端安全与健壮性
- [x] 后端认证中间件（验证 Supabase JWT）
- [x] 全局异常处理器（`exception_handler.py`，统一 JSON 错误格式）
- [x] 结构化日志（`setup_logging()`，管道分隔格式 + 第三方库降噪）
- [x] 文件上传端点（接收文件 → 存储 → 返回 URL）

### 测试
- [x] 后端单元测试 — 2026-04-28 曾验证 86 项 pytest，覆盖纯函数、降级管理、收敛路由、报告完整性、认证配置、文本校验、协同恢复和数据库错误可见性；当前测试数量以后续实际运行结果为准
- [x] API 集成测试 — report/consultation/dashboard 端点 mock DB 测试通过
- [ ] 前后端联调测试（需真实 Supabase 环境）

### 前端补全
- [x] Dashboard 接入真实数据（替换硬编码）
- [x] 案例库真实加载功能
- [x] 文件上传进度条接入真实进度

### 2026-06-06 文档与上线缺口审计
- [x] 全量同步 README、核心 docs、根目录和重要子目录 Agent 指南
- [x] 清理日志、缓存、崩溃转储和可再生增量产物
- [ ] 修复公开案例与公开案例 RAG 的过宽写入 RLS
- [ ] 修复 canonical `/collaboration` 专家路径生产认证白名单并补 API 测试
- [ ] 增加 `media` Storage bucket 与 RLS 的幂等迁移
- [ ] 修复历史空 `expires_at` 导致的新协作迁移风险
- [ ] Dashboard 协同统计切换为新表主读、旧表兼容

详细证据、影响与验收要求见 `docs/KNOWN_GAPS.md`。

### 2026-04-29 质询、报告与检测页体验修订
- [x] Challenger 改为 Kimi 结构化质询建议 + 代码硬门槛兜底（置信度 >=0.8 且无阻断问题时放行、最多 5 轮；Δ(t)<0.08 用于协同停滞判断；Commander 完成后不再质询）
- [x] Forensics / OSINT / Challenger LLM 字段改为 Agent 定制 Markdown 输出，保留模型自主推理段落
- [x] 报告章节改为逻辑质询、质询时间线、全程审计日志、建议与说明顺延
- [x] 检测页历史回放合并 agent_logs、timeline_events、audit_logs；时间轴展示 Challenger 局部轮次
- [x] 删除检测页 2D Agent 视图，仅保留 3D、时间轴、图谱入口

### 2026-04-29 Agent 自主推理与 Kimi coding plan 适配
- [x] 开发文档统一为“四个 Agent 先基于当前配置的全模态 Agent LLM 自主推理，再按角色调用外部工具，最后融合两部分结果”
- [x] 后端 LLM 配置支持 `AGENT_LLM_PROVIDER=kimi-k2.5|mimo` 选择 Agent 底层全模态模型；K2.5 通过 `KIMI_PROVIDER=official|coding|siliconflow` 选择官方 API、Kimi coding plan 或 SiliconFlow 渠道
- [x] 删除 `KIMI_FALLBACK_MODEL=moonshot-v1-128k` 模型级回退配置，LLM 不可用时只进入本地结构化降级
- [x] `.env.example` 补充官方 API 与 coding plan 的示例配置
- [x] `.env.example` 补充小米 MiMo Token Plan 示例配置，`AGENT_LLM_PROVIDER=mimo` 时使用 `MIMO_MODEL=mimo-v2.5`，不替换检测 API 和 embedding API
- [x] 检测页右上角改为系统流程展板，按上传输入、创建任务、开始检测、Agent 执行、局部质询轮次、报告生成展示全流程
- [x] 修复官方 Kimi API 地址归一、K2.5 thinking/temperature 参数风险，以及多轮质询重复调用成功外部工具导致的误降级
- [x] Forensics / OSINT 接入内部文本 AIGC 检测工具矩阵（不再依赖外部文本检测 API）
- [x] 公开案例库 Markdown 过滤“关键证据”章节，避免把结构化内部证据对象展示给公众
- [x] 将新检测链路主字段从旧 `deepfake_*` 迁移到 `aigc_*`，旧字段仅作为历史快照兼容 fallback

---

## 每日开发检查清单

开始前：
- [ ] 查看 task.md 确定当前任务
- [ ] 回顾 lessons.md 避免重复犯错

结束时：
- [ ] 更新 task.md 任务状态
- [ ] 记录问题到 lessons.md
- [ ] Git commit
