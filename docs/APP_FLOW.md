# TruthSeeker 应用流程

> 更新时间：2026-04-29

## 1. 输入边界

用户一次最多上传 5 个检材文件。后端按模态执行分类型大小限制：

- 视频：250MB，上限对齐 Reality Defender 当前视频处理能力。
- 音频：20MB。
- 图片：50MB。
- 文本文件：5MB，仅支持安全文本扩展名和可打印文本内容。

上传页文本框不是待检测文本输入区，而是 `case_prompt`：用于记录案件背景、检测目标、来源线索和重点风险。真正需要检测的文本必须以文本检材文件上传。

每个 Agent 都会接收全局输入视图，包括用户提示词、文件清单、短期 signed URL、模态、文件摘要和上一阶段证据。区别只在专业分工：电子取证侧重取证鉴伪，OSINT 侧重联网溯源，Challenger 侧重逻辑审查，Commander 侧重最终研判。

## 2. 任务创建

前端流程：

1. 用户选择 1 到 5 个文件。
2. 前端逐个调用 `POST /api/v1/upload/` 上传文件。
3. 后端返回标准文件对象：`id`、`name`、`mime_type`、`size_bytes`、`modality`、`storage_path`、可选 `file_url`。
4. 前端调用 `POST /api/v1/tasks` 创建任务。
5. 检测页只携带 `taskId`，不依赖 URL 中传 signed file URL。

任务表约定：

- `description` 保存 `case_prompt`。
- `metadata.files` 保存标准化文件清单。
- `storage_paths.files` 保存文件名、模态和 storage path。
- `input_type` 由后端根据文件模态推导，混合模态写为 `mixed`。
- 服务端只信任 JWT 中的 `request.state.user_id`。

## 3. 检测状态机

新运行时拓扑采用“阶段式四 Agent 研判”，对外仍保留 `forensics/osint/challenger/commander` 四个协议 key：

```mermaid
flowchart TD
  U["用户创建任务"] --> S["Detect Stream(taskId)"]
  S --> F["forensics: 电子取证 Agent"]
  F --> C1["challenger: 取证质询"]
  C1 -->|未收敛且未达上限| F
  C1 -->|取证收敛| O["osint: 情报溯源与图谱 Agent"]
  O --> C2["challenger: 图谱质询"]
  C2 -->|未收敛且未达上限| O
  C2 -->|图谱收敛| M["commander: 研判指挥 Agent"]
  M --> C3["challenger: 报告审阅"]
  C3 -->|报告需修订| M
  C3 -->|审阅通过或到达上限| R["报告生成、hash、审计"]
```

阶段规则：

- 自主推理先行：四个 Agent 都先基于 Kimi 2.6 原生多模态能力读取可访问样本、文本内容、全局检测目标和证据板，再按角色调用外部工具，最后融合自主推理与工具结果完成任务。
- `forensics` 不再是“只看视听”的专家，而是电子取证 Agent。它基于 Kimi 2.6 多模态上下文读取所有样本，同时调用 Reality Defender 和 VirusTotal 等专业工具。
- `osint` 回归情报溯源，读取取证证据、全局输入和脱敏搜索线索，调用 Exa API 与 VirusTotal 追加查询，生成可视化情报溯源图谱。
- `challenger` 在三个阶段分别审查取证报告、溯源图谱、最终报告。它会读全局证据板和原始样本上下文，先做自身逻辑质询，再结合硬门槛决定是否打回。
- `commander` 生成最终鉴伪与溯源报告。它同样先综合样本、证据板和各 Agent 结论进行自主裁决，再输出最终报告；报告阶段如果被 Challenger 打回，只重写报告，不重新打开取证或搜索工具链。
- 每阶段最多 5 轮，质量变化阈值为 0.08。达到阈值则视为收敛；达到轮次上限仍未完全解决时继续推进，但写入残留风险。
- 人机会诊触发采用统一门槛：同一目标 Agent 最近 3 轮都存在 high 质询，本轮置信度 `< 0.8`，且最近三轮相邻置信度变化均 `< 0.08`。首次触发自动暂停为 `waiting_consultation`；同一任务后续再次触发进入 `waiting_consultation_approval`，由用户决定“再次会诊”或“跳过本次”。

## 4. 人机专家会诊

会诊不是普通聊天，也不是事后批注。它是自动流程遇到高争议证据时的人工证据回注机制。

会诊状态流：

```mermaid
flowchart TD
  H["同一目标连续 3 轮 high 质询 + 低置信停滞"] --> A{"本任务首次触发?"}
  A -->|是| W["自动暂停 waiting_consultation"]
  A -->|否| P["提示用户审批是否再次会诊"]
  P -->|批准| W
  P -->|跳过本次| R["记录残留高质询风险，回到 Challenger 继续"]
  W --> I["创建本次会诊邀请"]
  I --> E["用户/专家提交轻结构化意见"]
  E --> S["用户结束会诊，Commander 汇总摘要"]
  S --> C{"用户编辑确认摘要"}
  C -->|确认| M["resume=true，带确认摘要回到 Challenger"]
  C -->|继续等待| E
```

会诊合同：

- 邀请按 `task_id` 和 `consultation_session.id` 绑定，默认 24 小时 TTL；样本链接沿用本轮邀请有效期，不生成永久公开链接。
- 消息保存为轻结构化记录：`session_id`、`message_type`、`anchor_agent`、`anchor_phase`、`confidence`、`suggested_action` 和 `metadata`。
- Commander 是主持人，负责在会诊开始时给出背景、进展、卡点和求助点；用户显示为“用户”，邀请链接访问者显示为“专家”。
- 只有用户能批准重复会诊、跳过本次、结束会诊、编辑确认 Commander 摘要。摘要确认后回注全局证据板，流程恢复到 Challenger。
- 会诊恢复时，后端通过 `resume=true` 注入专家/用户消息、会诊 sessions 和已确认摘要；若 LangGraph checkpoint 丢失，则从 `analysis_states`、`consultation_messages` 和 `consultation_sessions` 重建可裁决状态。

## 5. 工具调用与降级

专业工具必须使用 `all-settled` 语义：所有工具都要返回结构化结果，结果可以是 `success`、`degraded` 或 `failed`。任务不能因为某个工具失败就伪装成正常检测，也不能无限等待。

工具策略：

- 首轮全量调用：所有媒体文件进 Reality Defender；所有媒体哈希、文本 IOC 和 OSINT 新发现 IOC 进 VirusTotal。
- 后续智能重跑：只重跑失败、降级、被 Challenger 命中或新 IOC 对应的工具。
- Exa 搜索只发送脱敏线索：URL、域名、哈希、公开实体名、短关键声明，不发送完整原文或完整媒体描述。
- 所有外部工具保留硬超时；超时必须写成结构化失败结果。

## 6. 情报溯源图谱

图谱采用混合模型：

- 实体关系图：URL、域名、IP、文件哈希、人物、组织、账号、地点等。
- W3C PROV 风格溯源链：样本、工具查询、提取活动、证据、结论之间的来源关系。
- Claim/Evidence/Challenge 图：声明、支持证据、反证、质询点和最终裁决。

图谱写入：

- 阶段结果：`osint_result.provenance_graph`
- 最终审定版：`final_verdict.provenance_graph`

图谱字段：

- `nodes`: `artifact/entity/source/evidence/finding/claim/event/agent/verdict`
- `edges`: `extracted_from/mentions/derived_from/supports/refutes/contradicts/reviewed_by/before/after`
- `citations`: 来源 URL、检索时间、摘要、文件哈希、API 结果摘要
- `quality`: 完整性、引用覆盖率、模型推断比例、Challenger 审查结果

无引用但来自模型推理的关系可以进入图谱，但必须标记 `model_inferred=true`，不能作为外部事实展示。

## 7. SSE 事件

检测流使用 `POST /api/v1/detect/stream` 返回 SSE。保留现有事件契约：

- `start`
- `node_start`
- `agent_log`
- `evidence_update`
- `challenges_update`
- `forensics_result`
- `osint_result`
- `challenger_feedback`
- `timeline_update`
- `weights_update`
- `round_update`
- `final_verdict`
- `node_complete`
- `consultation_required`
- `consultation_approval_required`
- `consultation_started`
- `consultation_summary_pending`
- `consultation_summary_confirmed`
- `consultation_skipped`
- `consultation_resumed`
- `task_failed`
- `error`
- `complete`

新图谱不新增必须消费的新 SSE 事件，随 `final_verdict.provenance_graph` 下发；历史回放从 `reports.verdict_payload`、`analysis_states.result_snapshot`、`agent_logs`、`timeline_events` 和 `audit_logs` 读取。

## 8. 报告与可信输出

检测完成后，Commander 生成最终裁决，后端写入 `reports`：

- `verdict`: 仍沿用 `authentic/suspicious/forged/inconclusive`
- `confidence_overall`
- `summary`
- `key_evidence`
- `recommendations`
- `verdict_payload`
- `report_hash`

`verdict_payload` 承载子结论：取证结论、溯源结论、威胁判断、图谱质量、Challenger 审查结果和 `provenance_graph`。主 verdict 不扩展枚举，避免破坏数据库和前端颜色体系。

如果发生会诊，`verdict_payload` 还应包含会诊状态、邀请与确认摘要、专家意见数量、主持人最终动作和残留争议。Markdown/PDF 报告需要展示会诊触发原因、专家共识/分歧、Commander 摘要、主持人确认时间，以及这些意见如何影响最终裁决；时间线需要展示会诊触发、邀请创建、专家提交、摘要待确认、摘要确认、恢复或结束。

`report_hash` 使用 SHA-256，对规范化后的任务 ID、裁决、置信度、摘要、关键证据、建议和 verdict payload 做稳定 JSON 哈希。签名 URL、token、raw API 结果等敏感字段不进入哈希明文。

## 9. 暂不实现

- 不新增独立图数据库，图谱先复用现有 JSONB。
- 不实现真实案例库升级。
- 不实现 pgvector / 向量库。
- 不把 FedPaRS 训练/推理底座写成已运行实现；当前代码是 FedPaRS-compatible 运行时架构，底层检测器未来可替换为 FedPaRS 模型服务。
