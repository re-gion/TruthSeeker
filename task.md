# TruthSeeker 开发任务清单

> **使用说明**: 按顺序自上而下执行任务，每完成一项在 `[ ]` 中打勾 `[x]`。遇到阻塞问题立即记录到 `lessons.md`。
> **最后审查日期**: 2026-06-06（文档一致性、GitHub README 与代理指引同步）

---

## 当前已知缺口

> 原 `docs/KNOWN_GAPS.md` 已于 2026-06-20 归档删除，缺口清单迁移至此。完成修复后应补测试并从本清单移除。

**已确认（代码/迁移静态审计）：**

- [ ] `media` Storage bucket 与 Storage RLS 的幂等迁移缺失：`truthseeker-api/sql/migrations/` 无 bucket 创建语句，新 Supabase 项目不能只依赖仓库迁移跑通上传。影响：上传接口固定写入 `media`，bucket 缺失时文件上传失败。
- [ ] 公开案例与公开案例 RAG 写入 RLS 过宽：`20260528_case_library_entries.sql` 的 `insert ... with check (true)` / `update ... using (true)` 允许任意 authenticated 用户写入或篡改公共案例与向量块。影响：登录用户可能篡改公开数据。建议收紧到服务端受控写入并用不同账号执行 RLS 集成测试。

**待核验（需真实 Supabase 环境确认）：**

- 历史空 `expires_at` 数据是否阻塞新 `collaboration_invites` NOT NULL 迁移。
- Dashboard 协同统计是否已切新 `collaboration_*` 表主读、旧 `consultation_*` 表兼容。

---

## 2026-08-16 修复 Windows 事件循环导致 ASR / 关键帧抽取失效

- [x] 根因：`.env` 脏值修好后重跑案例10，ASR 音轨探测与视频关键帧抽取仍同时降级，堆栈指向 `asyncio/base_events._make_subprocess_transport` 抛空消息 `NotImplementedError`。定位为 uvicorn 在 Windows 上以 `--reload` 或多 worker 启动时（`Config.use_subprocess=True`）把事件循环固定为 SelectorEventLoop（`uvicorn.loops.asyncio.asyncio_loop_factory`），该循环不实现子进程 transport，`asyncio.create_subprocess_exec` 必然失败——这是本项目 `--reload` 标准开发启动方式下的必现问题。
- [x] 修复：`audio_transcription._run_process`（`video_observation` 共用）改为 `asyncio.to_thread` 线程池内执行同步 `subprocess.run`，不依赖事件循环类型；超时由 subprocess 自行终止子进程并转抛 `asyncio.TimeoutError`，返回值契约不变。
- [x] 验证：Proactor/Selector 双环境复现确认根因；强制 `_WindowsSelectorEventLoop` 下用案例10 真实视频实测 ffprobe 音轨探测、关键帧抽取（6 帧）、音轨抽取全部成功；新增 3 项 `_run_process` 回归（含 SelectorEventLoop 驱动、超时语义）；后端 pytest 225 项全过（5 项 Windows 临时目录权限 ERROR 与本改动无关，重定向 TMPDIR 后消失）。

---

## 2026-08-15 视频检材观察路径与三起工具降级根因修复

- [x] 视频观察路径（协同问题一）：调研确认 kimi-k2.6 在 Moonshot 官方平台原生支持视频理解（`video_url`，仅认 base64/`ms://file_id`，不支持 http URL 直传；coding 端点无视觉能力，SiliconFlow 视频未确认）。此前代码只传图片、视频仅文本引用，取证 Agent "看不见"视频被连续打回。新增 `app/agents/tools/video_observation.py`：official 渠道且 ≤40MB 走 base64 整段视频，其余 ffmpeg 均匀抽 ≤6 帧关键帧（宽 ≤1280）按图片传入，均不可用保留文本边界说明；`_invoke_multimodal_llm` 新增 `observe_video` 通道，仅取证阶段开启。
- [x] ASR NotImplementedError 降级（协同问题三）：根因是 `.env` 中 `FFMPEG_BINARY=` 行尾写了中文行内注释（dotenv 不支持），注释文本被当作 ffmpeg 可执行路径，视频音轨抽取的子进程调用必然失败。已清理 `.env` 脏值；`_resolve_binary` 加固为配置值必须指向真实文件否则回退 PATH；ASR 失败日志带完整堆栈；Groq 401/403 映射为明确降级原因。本地用案例10 真实视频端到端验证 ffprobe→抽取→上传链路已走通。
- [x] Reality Defender 403（协同问题二）：实测 RD API 返回 `free-tier-restriction: Video and text uploads require a paid plan`——免费套餐不允许视频/文本上传，属账户套餐限制而非代码缺陷（音频/图片仍可检测，此前音频案例全部成功）。代码改进：4xx 降级原因解析响应体 `code/message`（如 `http_403(free-tier-restriction: ...)`），报告与质询可自解释。
- [x] 视频分解检测（免费套餐策略）：视频不再整段送 RD，按能力边界分解——画面 → ffmpeg 均匀抽 3 帧关键帧逐帧送 Sightengine genai（聚合帧间最大概率，`video_keyframe_aigc` 工具，参与 media_aigc_probability 评分）；音轨 → ffmpeg 抽取 mp3 后按音频送 RD（无音轨为正常结论不计降级）。案例10 真实视频实测：关键帧 3/3 帧 AI 生成概率 0.99，音轨 RD 音频检测 0.08。`analyze_with_reality_defender`/`analyze_with_sightengine` 拆出字节级核心（`_rd_analyze_bytes`/`_sightengine_detect`）复用；新增 6 项回归测试（含 forensics 视频分发）。
- [x] Groq 403：本地实测 Groq 应用层 403（含 `/models`），key 形态有效但被拒绝，判断为 key 失效或工作区模型权限限制（今天上午音频案例 ASR 全部成功，期间状态发生变化）；代码已把 403 映射为可自解释降级原因，需在 Groq Console 检查 key 与模型权限。
- [x] 协同面板文本乱码：Supabase Storage 会丢弃上传 content-type 的 charset 参数，文本检材直开原始链接时浏览器按本地回退编码（GBK）渲染 UTF-8 字节成乱码。前端 `ConsultationLink` 携带 modality，text 检材改为面板内 fetch + 显式 UTF-8 解码预览，媒体检材保持新标签页打开。
- [x] 验证：后端 222 项 pytest 全过（新增视频观察 11 项、ASR 加固 2 项、RD 403 1 项、视频分解 6 项）；前端 25 项相关单测与 typecheck 全过；案例10 真实视频冒烟：LLM 观察内联判定通过、关键帧抽取 6 帧正常，分解检测关键帧 3/3 帧与音轨 RD 均取得真实结论。

---

## 2026-08-15 修复 Postgres NUL（22P05）导致检测收尾整体丢失

- [x] 根因：视频+文本检材检测中，外部工具结果/检材文本等不可信数据混入 NUL 空字符，收尾阶段 `analysis_states`/`reports`/`tasks` 三处写入全部被 Postgres 拒绝（22P05），整次检测在最后一步丢失，审计还误记 `report_generated`。
- [x] 持久化侧：`text_validation.strip_null_bytes` 递归剥离 NUL；`build_report_row`（先剥离再算 report_hash）、`build_analysis_state_row`、`build_agent_log_rows`、`normalize_final_verdict` 与 `AnalysisPersistenceService` 全部 `_safe_*` 写入方法统一落地；`upsert_report` 写入失败时不再记录 `report_generated` 审计。
- [x] 入口侧：`decode_text_bytes`、ASR 转写文本、`_cap_prompt_text`（LLM 提示词上限）同步剥离；`detect.py` 协同会话/审批写入与 `consultation.py` 专家消息写入同样覆盖。
- [x] 测试：新增 `tests/test_null_byte_sanitization.py`（7 项，模拟 Postgres 22P05 拒写）；后端 223 项 pytest 全过（另有 5 项因 Windows 默认临时目录权限报错，换 TEMP 后全过，与本改动无关）。
- [x] 外围写入面补齐：`tasks` 创建（用户标题/描述/提示词）、公开案例条目、案例 RAG chunks、经验条目与 chunks、专家消息统一剥离 NUL；新增 3 项外围写入回归测试（共 10 项）。
- [x] Commander 提示词瘦身：`commander_ruling` 从序列化完整 Agent 结果（实测一案 56 万字符、被截断丢尾）改为有界摘要——`_summarize_agent_for_commander`（叙事 12k、工具状态摘要、ASR 转写、域名溯源结论、检索标题级结果、图谱统计）与 `_summarize_challenger_for_commander`（质询结论与协同状态，丢弃会话/历史/RAG/skill 明细）；确定性注入（四分类、综合置信度、结论对照表）不受影响；提示词声明“摘要缺字段不等于工作未执行”；新增 2 项回归测试断言 30 万+ 字符膨胀载荷下提示词 < 8 万且关键内容保留。
- [x] 验证：后端 202 项 pytest 全过（含全部既有用例）。

---

## 2026-08-14 Agent 分工协作、协同频率与报告可读性改善

- [x] 阶段分工硬边界：Challenger/取证/溯源提示词与四份 SKILL.md（v1.1.0）写明职责归属；代码侧确定性过滤越界质询点（不得要求取证做 WHOIS/IP/DNS/情报溯源，也不得要求 OSINT 做像素级/音视频鉴伪）。
- [x] 跨阶段证据复用：取证经质询核验的结论（`upstream_verified_conclusions`）结构化注入 OSINT LLM 上下文，OSINT 讨论检材真伪必须引用上游结论，不得独立重建低置信判断。
- [x] 人机协同降频：每阶段每次检测至多 1 次协同（`CONSULTATION_MAX_SESSIONS_PER_PHASE=1`，超限带残留风险放行）；单次协同问题上限从 5 降为 3（`CONSULTATION_MAX_QUESTIONS=3`）。
- [x] 交叉验证概念统一：CONTEXT.md 新增词条；交叉验证 = 取证视角（是否伪造）× 溯源视角（是否虚假/恶意）的跨 Agent 互证；“缺少多工具复测”不再作为质询理由或证据链扣分依据；Commander 可疑裁决建议文案同步改写。
- [x] 分享报告可读性：最终裁决报告拆为独立全宽卡片并复用 `report-markdown` 表格样式；页面容器加宽至 `max-w-5xl`；“Agent 结论与关键分歧”表由确定性代码注入，“证据链质量评估”表由 Commander 提示词引导。
- [x] 经验库清理：删除 8 条已被本次机制吸收的经验（分工归属 ×2、跨阶段证据融合、跨阶段依赖标注、单工具栈边界、重复质询收敛、工具穷尽放行、置信度地板标注），保留 8 条方法论经验。
- [x] 测试：新增 `tests/test_agent_scope_and_collaboration_limits.py`（7 项）；后端 139 项 pytest 通过，前端 lint/typecheck/107 项单测通过。

## 2026-08-14 上游结论确定性引用、品牌实体检索与有效负结果放行

- [x] 上游结论补全：`upstream_verified_conclusions` 纳入文本 AIGC 检测结论；OSINT 复用取证文本检测结果时摘要显式标注“引用电子取证阶段已核验结论（复用）”。
- [x] 确定性引用块：OSINT 报告开头由代码注入“上游已核验结论引用”小节（图像/文本结论+来源归因），不再依赖模型自觉；Challenger 在该块存在且正文不冲突时不得再以叙事归属/引用粒度阻断。
- [x] 品牌/实体独立检索：新增轻量 LLM 实体抽取 `extract_osint_search_entities`（超时/失败回退），`build_deidentified_queries` 在域名信誉查询外补充实体查询（总数仍 ≤ `MAX_EXA_QUERIES`）；修复中文品牌名被 IDNA 误判为域名而丢弃的问题。
- [x] 有效负结果放行：Exa 正常执行完成但零命中时 OSINT 置信度保底 `0.8`，避免零命中案件被硬门槛锁死在打回-协同循环；仅搜索不可用/失败保持低置信。
- [x] 空结果不复用：重跑轮次对上一轮零命中的 Exa 结果重新搜索，仅复用已有命中的结果。
- [x] 品牌定性规则固化：搜索覆盖充分仍零命中 → 倾向“虚构品牌/品牌被冒充”，需列出搜索清单，不得停留“未检出/未确证”；写入 OSINT 提示词与 SKILL 契约。
- [x] RAG 工具边界硬规则：经验/类案 RAG 要求但当前工具不支持的验证动作不构成缺陷或质询点，Agent 只标注“当前工具不支持”。
- [x] 删除经验《品牌虚构性最低成本验证路径》（含 RAG 分块），其核心提升为系统规则；保留 8 条方法论经验。
- [x] SKILL 契约升版：osint-provenance、evidence-challenge 升至 v1.2.0，前端徽章与测试同步。

## 2026-08-14 分享报告左侧目录

- [x] 目录数据层：新增 `truthseeker-web/lib/report-toc.ts`，扫描报告 Markdown 生成两级目录（页面级区块 + `##` 同深度、`###` 缩进一级），跳过围栏代码块与缩进引用的标题；中文标题保留汉字 slug，同名标题追加序号后缀。
- [x] 锚点注入：新增 `components/report/reportMarkdownComponents.tsx`，按 Markdown 源码行号给 `h2`/`h3` 注入与目录一致的 id；质询时间线里被缩进引用的同名 `###` 标题不发 id，避免重复 DOM id 与跳错位置。
- [x] 目录组件：新增 `components/report/ReportToc.tsx`，可折叠（默认展开、不持久化偏好）、列表可滚动、高亮项自动滚回可视区；折叠后保留竖排"目录"按钮，栏位宽度不变。
- [x] 滚动跟随高亮：新增 `hooks/useActiveHeading.ts`（scroll + rAF 节流 + 150ms setTimeout 兜底，吸顶偏移 80px、2px 亚像素容差）；到达文档底部时强制高亮末章节，修复末尾几节永远越不过吸顶线的高亮卡顿。
- [x] 布局：仅 `≥1280px` 启用「220px 目录 + 1024px 正文」双栏，容器扩至 `1320px`，header 同步对齐；窄屏完全隐藏目录，布局与改动前一致。
- [x] 点击高亮锁定：点击目录立即锁定该条高亮，直到目标抵达吸顶线或用户自己滚动才交回测量——修复"点击后目录差一个标题"（35 条实测 33 条显示上一节）。锚点定位改用原生 `scrollIntoView`，修复大跨度跳转落点偏移 350px+（滚动途中字体分片加载改变文档总高）。
- [x] 顺手清理：删除 `globals.css` 中已无引用的 `.report-summary` 样式块（55 行）；`.pytest_tmp/` 加入 `.gitignore`。
- [x] 测试：新增 33 项前端单测（`lib/report-toc.test.ts`、`hooks/useActiveHeading*.test.*`、`components/report/*.test.tsx`）；前端 lint 0 错、typecheck 干净、142 项单测通过、生产构建通过；后端 146 项 pytest 未受影响仍全过；真实分享链接（1667 行报告、35 条目录）在 1440×900 浏览器实测：35 条目录逐一点击全部命中（落点误差 ≤3px、高亮一致）、无重复 DOM id、纯滚动跟随 7 个位置全部正确、折叠/展开正文不跳动、1100px 窄屏目录隐藏。



---

## 里程碑总览

- [x] **M1 - MVP可用**: Layer1完成（视频检测 + 双Agent + SSE）
- [x] **M2 - 完整辩论**: Layer2完成（全模态 + 四Agent + 收敛算法）
- [x] **M3 - 人机协同**: Layer3核心完成（Realtime 协作、协同暂停/恢复、专家邀请、3D 可选）
- [x] **M3 稳定性修复**: 协同消息使用独立 Realtime topic + 3 秒持久化轮询，发送失败可见且可重试；历史回放可选表失败时降级返回；摘要与经验草稿并发生成且不以短超时丢弃有效 LLM 结果
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
- [x] **数据库 Schema 迁移** — 历史阶段曾完成 9 表/17 迁移同步；当前新增表与 Storage 初始化仍需按上方「当前已知缺口」复核
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
- [x] 修复 canonical `/collaboration` 专家路径生产认证白名单并补 API 测试 — 已修复（`app/middleware/auth.py` 双前缀匹配 + `tests/test_collaboration_invite_access.py` 回归测试）
- [ ] 增加 `media` Storage bucket 与 RLS 的幂等迁移
- [ ] 修复历史空 `expires_at` 导致的新协作迁移风险
- [ ] Dashboard 协同统计切换为新表主读、旧表兼容

详细证据、影响与验收要求见上方「当前已知缺口」小节。

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

### 2026-08-04 Agent 核心 Skill 运行时

- [x] 定义四 Agent 固定核心 Skill 包、严格 schema、版本与 SHA-256 内容摘要
- [x] Commander 核心 Skill 固定包含 `final_adjudication`、`human_collaboration`、`experience_distillation` 三个显式工作流，不引入动态路由器
- [x] 拆分 Skill 的加载、实际应用和输出检查状态；缺失或损坏时静默回退系统提示词并记录结构化降级
- [x] 完成 Forensics 端到端试点：注入、章节检查、Agent 日志、审计事件、结果字段与降级状态
- [x] 接入 OSINT、Challenger 和 Commander 三工作流，并补各自输出检查、显式 LLM 状态、日志、审计与降级字段
- [x] 前端 Agent 卡片展示静态 Skill 名称/版本并标注“固定绑定”；最终报告从持久化元数据生成实际 Skill 执行摘要矩阵
- [x] 修复经验提炼合同轻微漂移导致的偶发未采用：首次失败自动纠正重试，重试仍失败才保留 `check_failed`
- [x] 修复样本日期被 LLM 反向解释及已完成 WHOIS 被重复列为待办；输出层增加确定性时间和域名工具状态守卫
- [ ] 在人工开启外部调用时运行真实 Kimi Skill on/off 对照评测；CI 继续只跑离线契约

### 2026-08-15 音频 ASR 语义转写（Forensics）

- [x] 新增 `audio_transcription` 工具：Groq OpenAI 兼容接口（默认 `whisper-large-v3-turbo`），音频直传、视频先 ffprobe 探测音轨（无音轨记录正常结论并跳过上传）再 ffmpeg 抽取音轨
- [x] Forensics 对音频/视频检材并行分发 ASR，转写进入工具矩阵与 `forensics_result.audio_transcripts`，取证 LLM 提示词要求校验音频语义与文本主题一致性（补齐 Challenger 提出的跨模态语义缺口）
- [x] 转写摘要以 `audio_transcript_summaries` 注入 OSINT「上游已核验结论引用」块（定位为证据内容而非鉴伪结论）
- [x] 结构化降级：未配置 `GROQ_API_KEY`、ffmpeg 缺失、文件超限或 Groq 失败均不虚构转写；`tests/test_audio_transcription.py` 11 项回归通过
- [x] 本机安装 ffmpeg 9.0.1（`C:\Users\user\ffmpeg\bin`，已入用户 PATH；代码另有回退路径解析）
- [ ] 配置真实 `GROQ_API_KEY` 后跑一次音频检材端到端检测，确认真实转写进入取证报告

---

## 每日开发检查清单

开始前：
- [ ] 查看 task.md 确定当前任务
- [ ] 回顾 lessons.md 避免重复犯错

结束时：
- [ ] 更新 task.md 任务状态
- [ ] 记录问题到 lessons.md
- [ ] Git commit
