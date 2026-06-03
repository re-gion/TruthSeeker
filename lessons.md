# TruthSeeker 开发错误记录本

> 犯错后立即记录。开发前快速浏览。最后更新: 2026-04-29

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
| 2026-04-29 | 文档/会诊机制 | 把专家会诊写成普通聊天或一次性自动暂停，会导致流程反复中断、专家意见不可计算、报告看不出人工介入边界 | 文档和实现必须区分首次自动会诊、重复触发审批、Commander 摘要、主持人确认/结束、邀请 TTL 和结构化消息 |
| 2026-05-28 | 公开案例库/Supabase | 免费层不适合把音视频二进制复制进数据库或案例专用桶；重复公开案例也不能阻断用户正常检测 | 原始检材复用私有 `media` bucket 的 storage path，案例表只存脱敏展示字段、报告 Markdown、SHA-256 指纹和短期预览入口；勾选公开时单文件限制 50MB |
| 2026-06-01 | 公开案例库/RAG | 相似公开案例容易被模型误写成当前任务事实，RAG 服务不可用也可能不应影响鉴伪分数 | 公开案例 RAG 只作为类案参考；Forensics/OSINT 可调用并写入报告/日志，但 Commander 不因命中直接改分。embedding 缺 key、pgvector 查询失败时必须结构化降级并继续检测 |
| 2026-06-02 | 后端/SSE 会诊恢复 | Commander 已持久化最终裁决后，如果 post-Commander Challenger 触发会诊中断，新的 `resume=true` 流可能不会再次收到 `final_verdict`，导致误报“未生成最终裁决”并跳过公开案例导入 | Commander 完成后直接 END，不再进入 Challenger；resume 流仍保留从 `reports`、`tasks.result` 或 `analysis_states` 找回已持久化裁决的兜底 |
| 2026-06-02 | 后端/公开案例报告 | 公开案例 Markdown 的“关键证据”章节容易展示内部结构化对象，和最终裁决摘要重复且对公众无解释价值 | 公开案例入库和详情 API 都过滤“关键证据”章节；检测台正式 Markdown/PDF 报告不受影响 |
| 2026-06-02 | 后端/文本 AIGC 检测 | 文本 AIGC 检测如果依赖外部 API，key、编码、额度或网络失败会污染证据链 | 文本 AIGC 改为内部 `ai_text_detector` 工具，供 Forensics/OSINT 调用；输出概率性线索、结构化信号和限制说明，不作为单独定性证据 |
| 2026-06-02 | 后端/VirusTotal URL 扫描 | VT URL 新提交扫描可能长时间 `queued`，短轮询结束后会出现 `analysis_queued` 且没有厂商统计 | queued 时不要把空统计当 0 检出；应补充回查 `/api/v3/urls/{url_id}` 的既有 `last_analysis_stats`，仍无结果才标记 `scan_available=false` |
| 2026-06-03 | 后端/Challenger 会诊恢复 | `resume_after_consultation` 如果被当作自动放行，会导致仍需补证的阶段直接跳到下一 Agent；跨阶段复用 `consultation_trigger_history` 还会让 OSINT 阶段错误触发 forensics 会诊 | 会诊恢复载荷要先注入本轮 Challenger 上下文，只有 `skip_consultation` 才强制放行；会诊触发必须按当前 `phase == target_agent` 的连续记录计算 |
| 2026-06-03 | 后端/文本 AIGC 与会诊上下文 | 同一问题连续三轮由 LLM 改写后会污染“需要帮助”字段；按某个案例写死 canonical 规则会过拟合 | Commander 在启动专家会诊时调用 LLM 对 `help_needed` 语义合并，LLM 不可用才用通用相似度兜底；不要按单个工具/API 错误写死关键词规则 |
| 2026-06-03 | 后端/AIGC 字段命名 | 图片 `AI_GENERATED`、音视频合成篡改和旧 Deepfake provider 字段混用，会让报告把 AIGC 概率误写成 Deepfake 概率 | 新运行时主字段统一用 `aigc_probability`、`is_aigc`、`aigc_score`；旧 `deepfake_*` 只作为历史 JSONB 读取 fallback，不能进入新报告主字段或用户可见术语 |

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
- FedPaRS 在当前仓库应写成 compatible 运行时或可替换底座，不要把未实现的训练/推理能力写成已完成。
- Windows npm 在当前机器上可能同时出现 registry DNS 失败和本地代理 `127.0.0.1:7897` 连接失败；依赖安装失败不能直接判断为前端代码问题，需把 package-lock 更新留到网络恢复后再做。不要手改 `package.json` 伪装安装完成，也不要把临时 SVG 图谱组件当作 `@xyflow/react` 的最终替代方案。
