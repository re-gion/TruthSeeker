# TruthSeeker 开发错误记录本

> 犯错后立即记录。开发前快速浏览。最后更新: 2026-08-14

---

## 错误记录

| 日期 | 模块 | 错误描述 | 解决方案 |
|------|------|----------|----------|
| 2026-03-03 | 前端/React | HeroSection Hook 违规：useState/useEffect 在早期 return 之后调用 | Hook 必须在所有 return 之前调用 |
| 2026-03-03 | 前端/SVG | SVG 路径 d 属性使用百分比 | d 属性不支持百分比，需配合 viewBox 使用数值坐标 |
| 2026-03-10 | 前端/Next.js | App Router 转场时页面跳闪 | 不要用 useEffect+setTimeout 延迟切换，用 key={pathname} 重新挂载遮罩 |
| 2026-03-12 | 前端/R3F | MeshTransmissionMaterial 渲染为实心色块 | 需要 Environment 贴图或 Canvas GL alpha:true |
| 2026-03-15 | 后端/Python | 虚拟环境 python 路径失效（指向不存在的路径） | 重新创建 venv_new 并重装 requirements.txt |
| 2026-04-20 | Windows/npm | `npm run typecheck` 可能因本地 `.cmd` shim 启动失败而无报错退出 | 用 `npx tsc --noEmit --diagnostics` 或直接 `node ./node_modules/typescript/bin/tsc` 区分代码错误与命令启动层问题 |
| 2026-04-21 | 后端/pytest | Python 3.13 下 `WinError 10106` 可能由残留进程/损坏的 `.next` 缓存导致；清理环境和重启后可恢复 | 先杀残留 Node 进程、清理 `.next`，再重跑 |
| 2026-04-21 | 前端/Next.js | `next build` 超时（>300s）可能因 `.next` 缓存膨胀（1.6GB）导致 | 删除 `.next` 目录后重新构建，4.7s 即可完成 |
| 2026-04-28 | 前端/React Flow | React Flow v12 的 `NodeProps` 不再包含 `style` prop，自定义节点内部读取 `style` 会报类型错误 | `style` 由 React Flow 外层容器应用，自定义节点只负责渲染内容；条件渲染 `data.xxx` 时需用 `Boolean()` 包裹避免 `unknown` 类型报错 |
| 2026-04-28 | 后端/pytest | Python 3.13 下 `run_sync_coroutine()` 若仅 `coro.send(None)` 一次，遇到内部 `await asyncio.sleep()` 会挂起失败 | 检测到无运行事件循环时，改用 `asyncio.new_event_loop().run_until_complete(coro)` 完整驱动协程 |
| 2026-04-28 | 后端/外部工具降级 | Reality Defender、VirusTotal 等外部工具降级时，mock 占位结果被报告和 LLM 当成真实检测结论 | 降级结果必须显式标注 `analysis_available=false`、真实失败原因和低置信度；报告中只能写“未取得外部结论”，不能写成“未检出/正常” |
| 2026-04-28 | 后端/OSINT 报告 | Exa 搜索 query 混入内部诊断句，且返回正文被递归 dump 到最终报告，造成报告严重污染 | 搜索 query 优先域名/实体线索并过滤内部诊断；报告只展示标题、URL、短摘要，不输出网页全文或原始工具大对象 |
| 2026-04-28 | 后端/Challenger 时间线 | 报告按全局 round 分组会掩盖 Challenger 分别质询 Forensics/OSINT/Commander 的阶段轮次 | Challenger 需要输出结构化 `phase/phase_round/confidence/quality_delta`，报告按“Challenger ↔ Agent 第 N 轮”展示 |
| 2026-04-29 | 报告/时间轴 | LLM 长文本字段如果走通用字典渲染，会把 Markdown 段落压成一行；检测页只回放 agent_logs 会漏掉系统审计事件 | `llm_analysis`、`llm_cross_validation`、`llm_ruling` 要用 Markdown 专用渲染；前端时间轴合并 `agent_logs`、`timeline_events`、`audit_logs` 并按时间排序 |
| 2026-04-29 | 后端/Kimi 配置 | 把 `moonshot-v1-128k` 当作模型级回退会破坏“四 Agent 原生多模态推理基座一致性” | 只保留 Kimi 2.5；通过 `KIMI_PROVIDER=official|coding` 切换入口，调用失败时进入本地结构化降级而不是换模型 |
| 2026-04-29 | 后端/Kimi 与工具降级 | K2.5 默认 thinking 容易在报告推理阶段超时；禁用 thinking 后继续传 `temperature=1.0` 会触发官方 API 参数错误；多轮质询如果重跑已成功外部工具，会把瞬时网络/API 抖动误写成后续轮次降级 | 官方入口按 Kimi 文档使用 `api.moonshot.cn/v1`，K2.5 报告调用显式关闭 thinking 并使用 `temperature=0.6`；同一任务后续轮次复用已成功工具结果，只重试失败/降级项 |
| 2026-04-29 | 文档/测试样本 | 测试样本说明如果写成“Forensics 看图片、OSINT 读文本”会误导后续实现回到模态割裂 | 文档必须强调四个 Agent 都先自主读取可访问样本和上下文，再按角色调用工具并融合输出 |
| 2026-04-29 | 文档/人机协同机制 | 把人机协同写成普通聊天或一次性自动暂停，会导致流程反复中断、人工意见不可计算、报告看不出人工介入边界 | 文档和实现必须区分首次自动协同、重复触发审批、Commander 摘要、主持人确认/结束、外部专家邀请 TTL 和结构化消息 |
| 2026-05-28 | 公开案例库/Supabase | 免费层不适合把音视频二进制复制进数据库或案例专用桶；重复公开案例也不能阻断用户正常检测 | 原始检材复用私有 `media` bucket 的 storage path，案例表只存脱敏展示字段、报告 Markdown、SHA-256 指纹和短期预览入口；勾选公开时单文件限制 50MB |
| 2026-06-01 | 公开案例库/RAG | 相似公开案例容易被模型误写成当前任务事实，RAG 服务不可用也可能不应影响鉴伪分数 | 公开案例 RAG 只作为类案参考；Forensics/OSINT 可调用并写入报告/日志，但 Commander 不因命中直接改分。embedding 缺 key、pgvector 查询失败时必须结构化降级并继续检测 |
| 2026-06-02 | 后端/SSE 会诊恢复 | Commander 已持久化最终裁决后，如果 post-Commander Challenger 触发会诊中断，新的 `resume=true` 流可能不会再次收到 `final_verdict`，导致误报“未生成最终裁决”并跳过公开案例导入 | Commander 完成后直接 END，不再进入 Challenger；resume 流仍保留从 `reports`、`tasks.result` 或 `analysis_states` 找回已持久化裁决的兜底 |
| 2026-06-02 | 后端/公开案例报告 | 公开案例 Markdown 的“关键证据”章节容易展示内部结构化对象，和最终裁决摘要重复且对公众无解释价值 | 公开案例入库和详情 API 都过滤“关键证据”章节；检测台正式 Markdown/PDF 报告不受影响 |
| 2026-06-02 | 后端/文本 AIGC 检测 | 文本 AIGC 检测如果依赖外部 API，key、编码、额度或网络失败会污染证据链 | 文本 AIGC 改为内部 `ai_text_detector` 工具，供 Forensics/OSINT 调用；输出概率性线索、结构化信号和限制说明，不作为单独定性证据 |
| 2026-06-02 | 后端/VirusTotal URL 扫描 | VT URL 新提交扫描可能长时间 `queued`，短轮询结束后会出现 `analysis_queued` 且没有厂商统计 | queued 时不要把空统计当 0 检出；应补充回查 `/api/v3/urls/{url_id}` 的既有 `last_analysis_stats`，仍无结果才标记 `scan_available=false` |
| 2026-06-03 | 后端/Challenger 协同恢复 | `resume_after_consultation` 如果被当作自动放行，会导致仍需补证的阶段直接跳到下一 Agent；跨阶段复用 `consultation_trigger_history` 还会让 OSINT 阶段错误触发 forensics 协同 | 协同恢复载荷要先注入本轮 Challenger 上下文；低于阈值时只有用户/专家摘要明确打破能力上限或建议放行，或达到第 5 轮上限，才允许放行；协同触发必须按当前 `phase == target_agent` 的连续记录计算 |
| 2026-06-03 | 后端/文本 AIGC 与协同上下文 | 同一问题连续三轮由 LLM 改写后会污染“需要帮助”字段；按某个案例写死 canonical 规则会过拟合 | Commander 在启动人机协同时调用 LLM 对 `help_needed` 语义合并，LLM 不可用才用通用相似度兜底；不要按单个工具/API 错误写死关键词规则 |
| 2026-06-03 | 后端/协同轮次与摘要 | 第 5 轮仍触发协同会造成用户/专家回复无法再补强，因为再推理会变成第 6 轮；结束协同时只拼接聊天记录也不是摘要，字符截断还会产生残句 | 每个目标 Agent 最多在第 3/4 轮触发协同，第 5 轮直接放行并保留残留风险；结束协同优先由 Commander LLM 总结 `help_needed`、协同任务和用户/专家回复，LLM 降级兜底也必须提炼结论、确认态与后续动作，不得复制聊天原文 |
| 2026-06-05 | 后端/Challenger 低置信门槛 | 低于 0.8 仍让 Challenger 自主放行，会让 57%/65% 这类明显未达标结论直接进入下一 Agent | 前 4 轮 `confidence < 0.8` 必须打回目标 Agent；连续 3 轮低置信且相邻变化 `<0.08` 启动人机协同；第 5 轮必须放行但写 `max_rounds_release=true` 和残留风险 |
| 2026-08-05 | 后端/LLM 降级 | 多轮打回补强时 `reinforcement_context.previous_analysis_payload` 把上一轮完整结果（含上一轮 reinforcement_context）原样塞进 prompt，递归膨胀到 46 万+ 字符、超出 Kimi 262140 max_prompt_tokens，触发 400 后整轮降级为“LLM 不可用” | 打回补强只注入 `summarize_previous_analysis()` 生成的有界摘要（llm_analysis/分数/tool 摘要，不嵌套）；多模态入口加 `_cap_prompt_text` 总长截断兜底，超限截断保留前缀而不是整轮降级 |
| 2026-08-05 | 后端/text_claim_extract | OSINT 的声明抽取默认 `use_llm=True` 调 Kimi，LLM 503/挂起时超过 120s settle 超时被杀死，社工分复用 forensics 结果 | `text_claim_extract` 改为纯本地规则（`use_llm=False`）：关键声明由本地规则提取（品牌主体、引述、链接、金额、时间压力、诱导特征），AIGC 概率继续由独立 `ai_text_detector` 承担；`analyze_text_llm` 加 20s 内部超时保护 |
| 2026-08-05 | 后端/WhoisXML | 海外接口间歇性 `ConnectError` 时整个域名溯源工具降级；settle 超时 30s 小于工具内 whois→dns→geo 串行预算，慢响应会在中途被整体杀掉 | 工具内 GET 对瞬时网络错误重试 1 次（HTTP 4xx/5xx 不重试）；OSINT settle 超时提到 90s 覆盖组件总和 |
| 2026-08-05 | 后端/个人经验库 | 确认入库时单条 draft 数据库写入失败（瞬时 PostgREST/embedding 问题、并发重复确认撞唯一索引等）会让整批 503 "个人经验入库失败"，且前面已插入的条目被保留、失败原因不落任何可查询日志，事后无法定位 | `confirm_experience_drafts` 逐条 try/except 隔离：单条失败记录 `failed` 明细并继续下一条；23505 唯一索引冲突视为已存在幂等跳过；主表成功后向量索引失败单独记 `indexing_failed` 不阻塞；写入 audit_logs（`experience.confirm`/`experience.confirm_failed`），前端展示失败条目标题 |
| 2026-08-05 | 后端/LLM 降级 | SiliconFlow K2.6 高峰期返回 503 "System is too busy"（服务端过载，与余额无关），代码一次失败即整体降级为"LLM不可用"，报告措辞误导用户以为配置问题；另有偶发 `RuntimeError: bad config`（.env 热读竞态，瞬时、无法复现字面量）且审计无配置上下文 | `_invoke_llm`/`_invoke_multimodal_llm` 对 503/429/连接超时等瞬时错误退避重试 2 次（0.5s/1.5s）后再降级；初始化失败审计记录脱敏配置预览（provider/model/base_url/api_key 是否为空）和 traceback 快照；注意：排查"bad config"要先确认后端实际运行的解释器（本机是 C:\Python313 用户级 site-packages，不是 venv_new），包版本不同行为不同 |
| 2026-08-05 | 后端/检材下载 | 检材读取（`download_evidence_bytes`）无重试，经本机代理/网络抖动时间歇性 `httpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]` 一次失败即降级，报告显示 `text_ioc_extract [降级]`（标签有误导：实际失败点是"下载文本文件内容"，不是 IOC 抽取；文本内容读不到则后续 `ai_text_detector` 也被跳过） | 下载端与上传端对称：对 `httpx.TransportError` 有限重试（3 次，1.5s 退避），HTTP 4xx/5xx 不重试；`text_ioc_extract` 降级摘要已写明"文本检材读取失败"。排查此类问题时先看 `repr` 完整错误（报告/日志只显示 `ConnectError:` 前缀），再用 `httpx.get` 实测连通性复现间歇性 TLS 中断 | Challenger 质询把完整 forensics_result（~200KB，tool_results 原始对象 + case/experience RAG 匹配全文）+ osint_result（~120KB，含 provenance_graph 完整 JSON）序列化进 prompt，合计 31 万字符超过 Kimi 262140 max_prompt_tokens，触发截断/降级 | `challenger_model_review` 改用 `_summarize_agent_evidence` 证据摘要：只保留 llm_analysis（截 8k）、结构化分数、tool_result_summaries（每条 300 字符）、RAG 匹配标题级摘要（4 条）、provenance_graph 统计（节点/边/引用计数）、challenges 每条截 800；摘要后 prompt 从 31 万降到约 2 万字符 |
| 2026-06-05 | 后端/OSINT 图谱引用 | provenance graph 如果只给少数外源节点挂 citation，会造成 citation_coverage 过低、model_inferred_ratio 过高，报告不可审计 | 上传检材、工具结果、外源、公开案例 RAG、个人经验 RAG 都要生成带 `source_kind` 的 citation；claim/tool finding/source edge 必须绑定 `citation_ids`，模型推理只能显式标记 |
| 2026-06-03 | 后端/AIGC 字段命名 | 图片 `AI_GENERATED`、音视频合成篡改和旧 Deepfake provider 字段混用，会让报告把 AIGC 概率误写成 Deepfake 概率 | 新运行时主字段统一用 `aigc_probability`、`is_aigc`、`aigc_score`；旧 `deepfake_*` 只作为历史 JSONB 读取 fallback，不能进入新报告主字段或用户可见术语 |
| 2026-06-04 | 个人经验库/协同摘要 | 协同结束时生成的个人经验草稿如果只挂在 `summary_pending` payload 上，用户确认摘要时可能被重建的 `summary_payload` 覆盖丢失 | 摘要确认必须保留已有 `experience_drafts`；个人经验入库必须由用户单独确认，并在生成草稿和确认入库两处都做相似/重复过滤 |
| 2026-06-04 | 后端/Agent LLM provider | 给四 Agent 底层全模态模型新增 provider 时，容易误改检测 API、embedding API、输出长度或沿用普通 Bearer 鉴权头 | `AGENT_LLM_PROVIDER` 只控制 Agent LLM 模型家族；K2.5 渠道由 `KIMI_PROVIDER` 控制；`mimo` 使用 `MIMO_BASE_URL`、`MIMO_API_KEY`、`MIMO_MODEL=mimo-v2.5` 和 `MIMO_THINKING=enabled|disabled`，小米 Token Plan 需要 `api-key` 请求头；TruthSeeker 单次输出上限由 `AGENT_LLM_MAX_OUTPUT_TOKENS` 控制；Sightengine、Reality Defender、VirusTotal、Exa 和 `EMBEDDING_*` 保持独立 |
| 2026-06-04 | 后端/WhoisXML 报告统计 | WhoisXML WHOIS 成功但 DNS Lookup/IP Geolocation 403 时，如果把 `partial` 包装成 `degraded`，报告会出现“成功 5/7、降级 1、失败 0”这类不闭合口径，还会把部分可用误写成失败；默认链路不应再调用消耗 DRS 额度的 DNS History | OSINT 包装层保留 `partial`；报告用“可用/完整成功/部分可用/其他/降级/失败”展示；域名溯源默认用 WHOIS + DNS Lookup 当前 A/AAAA/CNAME + IP Geolocation，403 说明为对应 WhoisXML 子产品权限或额度受限 |
| 2026-06-04 | 后端/SSE 幂等 | 已完成或正在分析的任务如果刷新、热重载或 SSE 重连后再次 POST `/detect/stream`，没有终态保护和运行锁会把同一 `task_id` 从 Forensics 开始重跑，覆盖报告并污染时间线 | `status=completed` 且非 `resume=true` 时必须直接复用 `reports.verdict_payload`、`tasks.result` 或 `analysis_states` 的最终裁决；`status=analyzing` 且已有 `active_detection_run_id` 时拒绝新的非恢复启动；报告/审计按最终 `detection_run_id` 过滤，只展示最终有效运行 |
| 2026-06-04 | 后端/Agent 报告日期推理 | LLM 会把样本日期和分析时间的先后关系判反，例如把 2026-04-22 误称为相对 2026-06-04 或 2026-08-06 的未来日期；只把正确关系注入提示词仍可能被模型忽略 | 日期先后关系由代码生成确定性时间校验表并注入 Forensics/OSINT；对 Forensics、OSINT 和 Commander 的模型输出再做确定性矛盾校正，提示词约束不能代替输出守卫 |
| 2026-06-04 | 后端/OSINT 文本工具边界 | `text_claim_extract` 如果继续暴露 `ai_probability`，会和内部 `ai_text_detector` 的正式文本 AIGC 概率混淆，报告读者无法判断哪个才是准确信号 | `text_claim_extract` 只保留社工风险 claim、诱导话术、URL 和异常线索；文本 AIGC 概率只由 `ai_text_detector` 输出和参与 AIGC 风险评分 |
| 2026-06-06 | 文档/代理指引漂移 | `CLAUDE.md`、`AGENTS.md`、`.github/copilot-instructions.md` 如果各自复制技术栈、拓扑和命令，很容易出现 Next.js 15、旧并行拓扑或 Commander 后质询这类过期规则 | `AGENTS.md` 作为跨工具主指引；`CLAUDE.md` 只导入对应 `AGENTS.md`；`.github` 指令只保留速查并指向主文档，版本和拓扑以源码与 `docs/TECH_STACK.md` 为准 |
| 2026-08-04 | 后端/Agent Skill 审计 | 只记录 `status=loaded` 会把“文件读取成功”误写成“本轮确实采用且输出合格”；字符串包含式章节检查、LLM 本地降级报告和未隔离的案件文本也可能伪造成功 | 分离 `load_status`、`execution_status` 和逐项 `check_results`；以显式 LLM 状态证明实际调用；Markdown 检查忽略代码块并验证标题唯一、顺序和正文；全部不可信案件字段统一转义后放入低优先级数据边界 |
| 2026-08-04 | 后端/Commander 多工作流 Skill | 人机协同摘要和经验提炼不经过主 LangGraph 节点，如果只在 `commander_node` 接 Skill，会遗漏两条真实生产调用链，也无法在空草稿时携带执行状态 | 三个 Commander 工作流分别在实际调用点加载；协同上下文和摘要直接携带 `skill_execution`，经验提炼通过显式 sink 回传状态，再由协同摘要持久化并审计 |
| 2026-08-04 | 后端/Skill 降级真实性 | LLM 初始化异常、带 JSON 的本地回退文本或确认摘要机械重算，可能让系统误报 LLM/Skill 成功，或覆盖 Commander 已提炼的语义元数据 | 所有解析前先检查显式 LLM 状态；格式或本地回退只能记为降级/`skipped`；确认操作只更新确认字段，Commander 摘要、未解决项和 Skill/经验元数据从原摘要保留 |
| 2026-08-04 | 后端/Supabase 上传 | supabase-py storage 子客户端默认 `http2=True`；经本机系统代理上传时被远程重置流（`StreamReset PROTOCOL_ERROR`）或切断 TLS 握手，传输层吞掉真实状态码，前端只看到笼统 500；且无重试，瞬时抖动即失败 | `SyncClientOptions(httpx_client=httpx.Client(http2=False,...))` 注入共享 HTTP/1.1 客户端；上传端对 `httpx.TransportError` 有限重试且重试带 upsert；413 映射为明确文案。另修 storage3 `FileOptions` 两个坑：键必须带连字符（`content_type=` 下划线写法从不覆盖默认 content-type，历史上传全存成 text/plain），`upsert` 必须传字符串 `"true"`（布尔值会原样进 x-upsert 请求头触发 TypeError） |
| 2026-08-04 | 后端/专家邀请鉴权 | 专家邀请链接匿名访问走规范前缀 `/api/v1/collaboration/...`，认证中间件公开白名单却只含历史别名 `/api/v1/consultation/`，匿名专家请求全部 401，前端统一提示“邀请链接无效或已失效” | 公开规则按双前缀（collaboration/consultation）同时匹配，且只放行带 invite_token 端内校验的只读/注入接口（invite、messages、agent-history、inject）；session、approve、skip、end_consultation 等 owner 接口保持 JWT 保护。邀请链接必须整段复制转发，手动转述 I/l、K/k 等字符极易被改且无法靠大小写回退修复 |
| 2026-08-04 | 前后端/Skill 产品可见性 | Agent 固定绑定和本轮真实执行是两种不同事实；若卡片或报告都从静态配置推断，用户会把“具备该能力”误读为“本案已采用” | Agent 卡片只展示名称、版本与“固定绑定”；报告只读取分析快照和协同会话中的 `skill_execution`，按 `applied/check_failed/skipped` 展示，缺少元数据时明确无法核验 |
| 2026-08-06 | 后端/经验提炼与工具建议 | 经验提炼模型一次轻微 JSON 缺字段会让整个 Skill 标记为未采用；Commander 也可能把 OSINT 已完成的 WHOIS 再列为待办，并把默认未启用的历史 IP 查询写成现成功能 | 经验合同首次失败时携带完整 schema 自动纠正重试一次，仍失败才保留 `check_failed`；Commander 根据实际域名工具组件状态过滤重复 WHOIS 动作，并把历史 IP 明确标注为需另行启用和授权的 DNS History 扩展 |
| 2026-08-06 | 后端/Exa OSINT 相关性与网络抖动 | URL 检材的 Exa 查询混入 WhoisXML 工具摘要和泛化社工标签，导致搜索命中 WhoisXML 自家产品页；结果无案件相关性门槛；本机代理/TUN 将 `api.exa.ai` 解析到 `198.18.0.0/15` Fake-IP，TLS 首连会间歇出现 `UNEXPECTED_EOF_WHILE_READING`，只重试一次仍可能连续失败；90s 外层预算也覆盖不了 3 条查询的全部尝试 | 有 URL/域名时只构造精确主机 IOC 查询；结果必须命中主机或注册域才能进入证据链；`ConnectError` 最多 3 次总尝试（0.5s/1.5s 退避），仍失败则批次熔断并归并为一个结构化错误；外层超时按查询数、单次超时和尝试数计算并预留余量 |
| 2026-08-06 | 后端/Exa 零命中状态 | Exa `/search` 的引号查询仍是语义检索；罕见钓鱼主机不在索引时会返回 Halifax 等主题相关页面但不含案件域名。过滤器正确拒绝后，代码却把“成功检索、0 条直接佐证”标成 `degraded/no_relevant_results`，报告误写为工具不可用并触发 Challenger 降级质询 | 搜索成功与证据命中必须分开建模：无案件特异性命中返回 `success + no_case_specific_matches`，保留候选检查/拒绝计数并明确写“暂无直接公开佐证”；只有连接、超时、鉴权等调用故障才算降级或失败，绝不能靠放宽相关性门槛伪造证据 |
| 2026-08-05 | 后端/Commander Skill 合同 | 直接校验 LLM 原始 JSON 会把后续已经规范化并实际使用的摘要/经验草稿误报为 `check_failed`；仅靠提示词也不能阻止 LLM 把 Python 的确定性四分类改写成另一结论 | 协同摘要与经验草稿先做受控合同归一化，再校验实际返回产物；完全无效条目仍失败。最终四分类作为显式输入并由 Python 覆盖报告结论章节，LLM 只解释证据，不得改写硬规则 |
| 2026-08-06 | 前后端/协同实时性与恢复 | 协同面板和检测流复用相同 Supabase topic 会让重复订阅互相干扰；拆 topic 时若连状态事件也改道，其他客户端不会更新；发送持久化失败却保留乐观气泡会让专家误以为已送达；3 秒轮询若不等待上一请求结束，会在 Supabase 慢查询时叠加并最终触发 `httpx.PoolTimeout`，连带摘要确认和经验入库卡住；同步 Supabase 查询直接放在 async 路由里还会阻塞整个 FastAPI 事件循环；历史回放把所有历史表当强依赖会因单表异常整体 500；结束协同时串行等待两个 LLM 会叠加延迟，而协同层 12 秒短截止又会把稍慢的有效模型结果错误丢弃 | 聊天使用独立 `collaboration:{task_id}` topic，状态事件保留 `task:{task_id}`；3 秒持久化轮询采用单飞保护，未完成时跳过下一轮，消息历史同步查询整体交给受限线程池；发送失败撤回乐观气泡、恢复输入并提示；历史可选源逐表降级；摘要和经验草稿并发但不设协同层短截止，网络超时与重试继续交给底层 LLM 客户端，只有真实调用失败才使用本地兜底 |
| 2026-08-06 | 前后端/经验草稿确认 | 摘要确认接口已返回经验草稿，但发送端不消费响应且不能依赖收到自己的 Realtime 广播，导致后端有草稿、当前用户仍看不到；同时模型把 `evidence_to_check` 输出为字符串时，合同重试会把整批有效主体拒绝为 0 条且不写错误原因 | close/confirm 响应直接归并到面板本地状态并复用统一 session 解析器；可编辑核验清单安全归一化为数组，必填主体字段继续严格校验；`check_failed` 空结果持久化并展示明确原因，历史空快照也不得静默 |
| 2026-08-05 | 后端/Commander 综合置信度 | 报告卡片读取 `confidence_overall=78.4%`，但 LLM 在“置信度与证据链”中把 Forensics 的 `0.95` 误写成综合置信度，导致同一报告出现两个口径 | Commander 用确定性代码统一写入综合置信度及 `各 Agent 置信度 × 动态权重` 的逐项公式；LLM 只解释证据链，不输出第二个数值，也不得引用 `forensics_score` 代替综合结果；Skill 合同检查两处值一致 |
| 2026-08-05 | 后端/中间件顺序 | 用 `app.add_middleware(CORSMiddleware)` 注册的 CORS 会被 monkey-patch 注入的纯 ASGI Auth/RateLimit 包在内层；Auth 直接 send 的 401/429 响应缺失 CORS 头，浏览器跨域时把 401 当网络错误，控制台只报 `TypeError: Failed to fetch`，真实原因（如“令牌已过期”）被掩盖 | CORS 必须在 `_build_with_pure_asgi_middlewares` 里手动包成最外层（顺序 CORS → Auth → RateLimit → App），不要用 `add_middleware` 注册；排查浏览器 “Failed to fetch” 先 curl 带 Origin 检查 401/429 响应是否含 `access-control-allow-origin` |
| 2026-08-14 | 后端/Agent 分工 | Challenger LLM 反复以“取证没做 WHOIS/IP/DNS/情报溯源”为由打进取证阶段，而取证根本没有这些工具；低置信轮次堆满后必然触发人机协同，几乎每次检测都发生 | 阶段分工是硬边界：提示词（Challenger/取证/溯源 + SKILL.md）写明职责归属，代码侧 `_filter_out_of_scope_issues` 确定性过滤越界质询点（双向：也不得要求 OSINT 做像素级/音视频鉴伪），不计入打回理由 |
| 2026-08-14 | 后端/人机协同参数 | 协同触发置信度阈值与 Challenger 放行阈值同为 0.8，意味着任何未放行僵局都会滑向协同；每阶段 2 次上限 + 每次固定 5 个问题，用户协同压力过大 | 放行门槛与协同门槛不能隐式共用同一个值；协同频率用独立参数控制：`CONSULTATION_MAX_SESSIONS_PER_PHASE=1`（每阶段每次检测至多 1 次，超限带残留风险放行）、`CONSULTATION_MAX_QUESTIONS=3` |
| 2026-08-14 | 后端/跨阶段证据复用 | `osint_interpret` 调 LLM 时完全不传 forensics 结果，OSINT 对检材真伪只能独立重建低置信判断，与上游 Sightengine 0.99 形成落差，又反过来成为质询点 | 已通过质询核验的上游结论（`_upstream_verified_conclusions`）必须以结构化字段注入下游 LLM 上下文并配提示词硬规则：涉及检材真伪必须引用上游，不得独立重建分歧判断；新增阶段间依赖时先确认“下游 LLM 是否真的能看到上游结论” |
| 2026-08-14 | 前后端/报告渲染 | 分享报告第一部分用 `report-summary` 样式渲染 LLM markdown，该样式没有任何表格 CSS，模型输出的表格全部变成纯文本；内容又塞在裁决卡 emoji 侧排布局里，宽度被挤压 | 复用 markdown 渲染前确认样式类是否覆盖 table；第一部分拆为独立全宽卡片并复用 `report-markdown`；“Agent 结论与关键分歧”表由代码确定性注入保证存在（同综合置信度注入模式），证据链质量评估表由 Commander 提示词引导 |
| 2026-08-14 | 文档/概念一致性 | “交叉验证”在代码、建议文案和报告里被混用为“多工具交叉验证”，与系统实际的跨 Agent 视角互证（取证判伪造 × 溯源判虚假）语义冲突，模型据此扣分并建议换工具复检 | 领域词汇写入 CONTEXT.md；Challenger/Commander 提示词与 commander 建议文案统一为跨 Agent 互证定义；“缺少多工具复测”只能作为可选补强，不得作为质询理由、协同问题或证据链扣分依据 |
| 2026-08-14 | 后端/上游结论注入覆盖 | `upstream_verified_conclusions` 只收集图像/音视频检测摘要，取证阶段的文本 AIGC 结论没有进入上游注入，OSINT 复用该结果后以独立口吻复述（“文本AI生成概率低33.3%”），被 Challenger 连续 4 轮判为未引用上游 | 上游结论注入必须覆盖取证阶段全部鉴伪组件（图像+文本）；复用取证工具结果的摘要要显式标注“引用电子取证阶段已核验结论（复用）” |
| 2026-08-14 | 后端/叙事归属修复 | “报告措辞未标注上游来源”这类叙事级缺陷靠打回重跑修不好：同一缺陷被连续打回 4 轮，模型每轮都重写相似叙事，最终滑向人机协同 | 叙事级合规用确定性注入兜底：OSINT 报告开头由代码注入“上游已核验结论引用”小节；Challenger 在该块存在且正文不与上游数值冲突时不得再以归属/引用粒度阻断，避免“措辞缺陷→打回→协同”死锁 |
| 2026-08-14 | 后端/有效负结果 | OSINT 置信度只按命中数加分（0.62+0.04×命中），Exa 零命中永远 0.62 < 0.8 放行线，零命中案件被硬门槛锁死在打回循环，且重跑轮次复用空结果导致置信度精确停滞（Δ=0），必然触发协同 | “搜索正常执行但零命中”是有效负结果而非证据缺失：置信度保底 0.8；零命中结果不在重跑轮次复用（要真实重搜），仅复用已有命中的结果；`degraded/failed` 才保持低置信 |
| 2026-08-14 | 后端/搜索覆盖 | 查询构造只要检材有 URL 就只生成域名信誉查询，文本里的品牌名（如“星购生活”）从未被搜索，但报告给出“品牌未检出/未确证”结论——无搜索支撑的无效推断，还被经验 RAG 追责“未做应用商店/社交媒体核验” | 查询构造补充实体维度：一次轻量 LLM 实体抽取（超时/失败回退）生成品牌/机构/产品独立检索查询；实体存在性判断必须以实际执行的实体检索覆盖为准，未执行不得断言虚构 |
| 2026-08-14 | 后端/实体去重误判 | 中文品牌名能被 IDNA 编码成 punycode（“星购生活”→`xn--kiv31ne3g02z`），用 `_normalize_hostname` 判断“是否为域名”会把中文实体全部误判为域名而丢弃 | 判断“实体名是否为域名”不能用 hostname 解析/IDNA，要用 ASCII 域名正则全匹配（`_DOMAIN_PATTERN.fullmatch`） |
| 2026-08-14 | 前端/Markdown 锚点 | 给报告 h2/h3 注入目录锚点时用「行号命中 + 标题文本兜底」，结果质询时间线里被缩进引用的上一轮分析含同名 `### 自主情报推理` 等标题，靠文本兜底抢到了顶层章节的 id：44 个标题里出现 4 组重复 DOM id，目录点击跳到错误位置 | 长报告会整段引用自身内容，标题文本不是唯一键：锚点只按 Markdown 源码行号命中，不做文本兜底；目录扫描也要跳过缩进（非行首）的标题，它们不属于报告结构 |
| 2026-08-14 | 前端/滚动高亮 | 「最后一个越过吸顶线的标题」算法在长报告末尾失效：末尾几节距文档底部不足一屏，滚到底也越不过吸顶线，点末章节后高亮卡在前一节，看起来像坏了 | 滚动高亮必须特判文档底部：`scrollY + innerHeight >= scrollHeight - 2` 时直接高亮最后一个标题 |
| 2026-08-14 | 前端/eslint 规则 | `hooks/useActiveHeading.ts` 在 effect 体内同步 `setActiveId(null)` 处理空列表，被 `react-hooks/set-state-in-effect` 判为 error（Next 16 的 eslint 配置默认开启），lint 直接失败 | 派生状态在渲染期算，不在 effect 体里同步 setState：effect 只负责订阅外部事件；「id 列表变化时回到首项」这类兜底用渲染期表达式（`ids.includes(measuredId) ? measuredId : ids[0]`） |
| 2026-08-14 | 前端/滚动容器测量 | 目录列表自动滚动高亮项用了 `active.offsetTop`，但 `offsetTop` 相对最近定位祖先（`nav`，含标题栏）而非滚动容器 `ol`，页面初次加载时目录被无故下滚 49px，首个条目被裁掉 | 计算滚动容器内的偏移用 `getBoundingClientRect()` 差值（`activeRect.top - listRect.top`）增量调整 `scrollTop`，不要混用 `offsetTop` 与滚动容器坐标系 |
| 2026-08-14 | 前端/rAF 节流可靠性 | 滚动高亮只用 `requestAnimationFrame` 节流，在 5.6 万像素长文档 + 后台/被遮挡标签页里 rAF 被浏览器节流，平滑滚动停止后的最后一帧丢失，高亮永久停在上一节（点「一、任务信息」高亮却留在「九、建议与说明」） | rAF 节流要配一条 setTimeout 兜底（约 150ms trailing），保证滚动停止后必然有一次最终测量；不要把 rAF 当作"一定会执行"的调度器 |
| 2026-08-14 | 前端/目录高亮语义 | 长报告里"纯测量"选高亮必然差一节：点击目录后平滑滚动要跨几万像素、途中字体分片加载改变行高，落定前每一帧目标标题都还没越过吸顶线，35 条目录实测 33 条显示上一节 | 点击是明确的用户意图，不该由测量推断：点击时锁定该条高亮（pin），解锁条件是"目标已抵达吸顶线"（此时测量结论与锁定一致，交回不会闪）或用户自己滚动（wheel/touchstart/keydown/mousedown）。不要用"滚动停止计时器"解锁——长文档滚动会被主线程中途阻塞数秒，会误判成已落定 |
| 2026-08-14 | 前端/锚点滚动 | 目录点击用 `window.scrollTo({ top: rect.top + scrollY - offset })` 自算像素，大跨度跳转落点偏 350px+：滚动途中字体分片加载改变文档总高，点击瞬间算好的绝对像素已经失效 | 长文档锚点跳转用原生 `element.scrollIntoView({ behavior: 'smooth', block: 'start' })`，让浏览器在动画过程中持续校正；吸顶偏移交给锚点自身的 `scroll-margin-top`，不要在 JS 里重复算一遍 |

---

## 关键规范速查

| 类别 | 正确 | 错误 |
|------|------|------|
| LangGraph State | `TypedDict` | `Pydantic BaseModel` |
| Motion 导入 | `from "motion/react"` | `from "framer-motion"` |
| Tailwind 配置 | `@import "tailwindcss"` + `@theme {}` | `tailwind.config.js` + `@tailwind` |
| 动画包 | `tw-animate-css` | `tailwindcss-animate` |
| PostCSS | `@tailwindcss/postcss` | `tailwindcss` |
| Drei 版本 | v10（支持 React 19） | v9（不支持） |
| Supabase Auth | `@supabase/ssr` | `@supabase/auth-helpers` |
| shadcn CLI | `shadcn@canary` | `shadcn@latest` |

## 2026-04-28 后端重建注意事项

- `forensics/osint/challenger/commander` 是后端 SSE、前端检测台、报告生成和历史恢复共同依赖的协议 key。可以改变用户可见语义，但不要轻易改 key。
- 外部工具不可把“未配置、超时、网络失败”的降级结果伪装成真实检测通过；必须返回结构化 `success/degraded/failed`。
- provenance graph 中无引用但来自模型推理的边必须标记 `model_inferred=true`，报告中不能写成外部事实。
- Fed-MBPR 在当前仓库应写成 compatible 运行时或可替换底座，不要把未实现的训练/推理能力写成已完成。
- Windows npm 在当前机器上可能同时出现 registry DNS 失败和本地代理 `127.0.0.1:7897` 连接失败；依赖安装失败不能直接判断为前端代码问题，需把 package-lock 更新留到网络恢复后再做。不要手改 `package.json` 伪装安装完成，也不要把临时 SVG 图谱组件当作 `@xyflow/react` 的最终替代方案。
