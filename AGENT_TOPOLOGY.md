# TruthSeeker 四 Agent 阶段式研判 + 人机协同 拓扑详解

> 更新日期：2026-06-06
> 对应代码：`truthseeker-api/app/agents/graph.py`、`nodes/*.py`、`edges/conditions.py`、`services/consultation_workflow.py`
> 文档状态：深度运行时说明。若本文件与源码、`docs/APP_FLOW.md` 或 `docs/BACKEND_STRUCTURE.md` 冲突，以源码和 durable docs 为准，并同步修正本文件。

---

## 一、整体拓扑

系统是一条**阶段式流水线**。Forensics 和 OSINT 各自完成后交给 Challenger 质询；
Challenger 决定"打回补强"还是"放行到下一阶段"。Commander 生成最终裁决后**直接结束**，不再经过 Challenger。

```
START
  │
  ▼
┌──────────────┐     ┌────────────┐
│  Forensics   │────▶│ Challenger │──┐
│ (电子取证)    │     │ (逻辑质询)  │  │
└──────────────┘     └────────────┘  │
      ▲                   │          │
      └───────────────────┘ 打回     │ 放行
         (≤5轮/阶段)                  │
                                     ▼
┌──────────────┐     ┌────────────┐
│    OSINT     │────▶│ Challenger │──┐
│ (情报溯源)    │     │ (逻辑质询)  │  │
└──────────────┘     └────────────┘  │
      ▲                   │          │
      └───────────────────┘ 打回     │ 放行
         (≤5轮/阶段)                  │
                                     ▼
                              ┌──────────────┐
                              │   Commander   │────▶ END
                              │ (研判指挥)     │
                              └──────────────┘
```

### 运行时基础设施

| 组件 | 说明 |
|------|------|
| **Checkpointer** | `MemorySaver`（内存级），进程重启后 checkpoint 丢失 |
| **编译方式** | 模块级单例 `compiled_graph = build_graph()`，导入时编译，所有请求复用 |
| **请求隔离** | 通过 `thread_id` 隔离，每个检测任务一个独立线程 |
| **Resume 回退** | checkpoint 丢失时从 `analysis_states` 表重建状态，跳过已完成阶段直接进入 Commander |
| **并发保护** | 已有 `active_detection_run_id` 的任务返回 409；resume 模式不受限 |
| **SSE 心跳** | 每 20 秒发送 `:keepalive\n\n`，防止代理断开长连接 |

### 与旧拓扑的关键区别

| 对比维度 | 旧拓扑 | 当前拓扑 |
|---------|--------|---------|
| Commander 审查 | Commander → Challenger → END | Commander → **END**（不再经过 Challenger） |
| 轮次跟踪 | 全局统一 `current_round` | **每阶段独立** `phase_rounds`（各阶段互不干扰） |
| 质量历史 | 全局 `confidence_history` | **每阶段独立** `phase_quality_history` |
| 被打回后做什么 | 原样重跑 | 带上 **Challenger 反馈 + 协同摘要** 做"补强分析" |
| 已成功的工具 | 每轮都重调 | **自动复用**上轮已成功的工具结果（跳过重复调用） |
| 跨阶段质询 | 无特殊处理 | **自动忽略**跨阶段的质询点，当前阶段只审查当前阶段 |
| 人机协同 | 无 | 经验库优先拦截 → 人机协同 → 摘要确认回注 |
| 放行条件 | 单一阈值 | **三重门控**（阈值 / 轮次上限 / 协同放行） |

---

## 二、四个 Agent 各自的职责与工具

| Agent | 角色 | 核心任务 | 可调用工具 |
|-------|------|---------|-----------|
| **Forensics** | 电子取证专家 | 对所有检材做技术检测，输出结构化取证报告 | Sightengine AIGC 图片检测、Reality Defender（音视频深伪）、VirusTotal（文件哈希 + 文本 URL）、内部文本 AIGC 检测、案例 RAG、个人经验 RAG、Kimi/MiMo LLM 多模态推理 |
| **OSINT** | 情报溯源分析师 | 追踪来源、构建溯源图谱、评估威胁 | 文本声明抽取 + 社工风险评分、VirusTotal URL、WhoisXML 域名溯源、Exa 搜索、案例 RAG、个人经验 RAG、溯源图谱构建器、内部文本 AIGC 检测、Kimi/MiMo LLM |
| **Challenger** | 逻辑质询官 | 交叉验证、质询、决定是否放行 | Kimi/MiMo LLM（结构化 JSON 审查）、确定性代码检查器（硬规则）、个人经验 RAG |
| **Commander** | 研判指挥官 | 综合所有证据做出最终裁决 | Kimi/MiMo LLM（最终裁决报告）、溯源图谱构建器、加权置信度计算器 |

所有 Agent **先自主推理，后调用工具**：先基于配置的多模态 Agent LLM（默认 Kimi K2.5，可切 MiMo v2.5）读取样本和上下文自主分析，再按角色调用外部工具，最后融合两部分结果完成任务。

### Agent 间工具结果共享

| 共享内容 | 机制 | 说明 |
|---------|------|------|
| 文本 AIGC 检测 | OSINT 通过 `text_fingerprint` 匹配 Forensics 结果 | 相同文本不重复调用，标记 `reused_from="forensics"` |
| VirusTotal URL | **不共享** | Forensics 用 `virustotal_text_ioc`，OSINT 用 `virustotal_osint_ioc`，同 URL 分别请求 |
| 案例 RAG | 各自独立调用 | 不同 Agent 检索角度不同，不复用 |
| 个人经验 RAG | 各自独立调用 | 按 `user_id + target_agent` 隔离检索 |

### LLM 调用与降级

| Agent | LLM 函数 | 降级行为 |
|-------|---------|---------|
| Forensics | `forensics_interpret` | 多模态失败 → 降级文本模式 → 返回 `[降级模式: LLM不可用]` |
| OSINT | `osint_interpret` | 同上 |
| Challenger | `challenger_model_review` | 失败 → 使用 `base_quality` 作为 `model_confidence`，不新增 model_issues |
| Commander | `commander_ruling` | 失败 → 使用硬编码 Markdown 裁决模板 |

---

## 三、Challenger 核心机制

### 3.1 双重审查

Challenger 对每个阶段做两层审查：

1. **确定性代码检查（硬规则）**：不依赖 LLM，纯代码判定
2. **LLM 交叉审查（软判断）**：调用 Kimi 做逻辑一致性分析，输出结构化 JSON

两者结果合并取并集。

### 3.2 各阶段硬规则检查项

**Forensics 阶段** (`_forensics_issues`)：

| 检查项 | 严重度 | 触发条件 |
|--------|--------|---------|
| `missing_forensics` | high | forensics 字典为空 |
| `missing_tool_matrix` | high | `tool_summary.total == 0` |
| `tool_failed` | high | `tool_summary.failed > 0` |
| `tool_degraded` | medium | `tool_summary.degraded > 0` |
| `low_confidence` | high | `confidence < 0.55`（注意：此阈值独立于 satisfaction_threshold） |

**OSINT 阶段** (`_osint_issues`)：

| 检查项 | 严重度 | 触发条件 |
|--------|--------|---------|
| `missing_osint` | high | osint 字典为空 |
| `missing_graph` | high | provenance_graph 为空 |
| `thin_graph` | medium | `nodes < 3` |
| `missing_citations` | high | citations 为空列表 |
| `low_citation_coverage` | medium | `citation_coverage < 0.60` |
| `too_many_model_inferred_edges` | medium | `inferred_ratio > 0.35` |
| `missing_osint_tool_matrix` | high | `tool_summary.total == 0` |
| `osint_tool_failed` | high | `tool_summary.failed > 0` |
| `osint_tool_degraded` | medium | `tool_summary.degraded > 0` |

**Commander 阶段** (`_commander_issues`)：

| 检查项 | 严重度 | 触发条件 |
|--------|--------|---------|
| `invalid_verdict` | high | verdict 不在 `{authentic, suspicious, forged, inconclusive}` |
| `missing_final_graph` | high | provenance_graph 为空 |
| `overconfident_verdict` | high | `confidence < 0.35` 且 `verdict != "inconclusive"` |
| `missing_recommendations` | medium | recommendations 为空 |

### 3.3 置信度计算

```
confidence = min(model_confidence, _score_issues(issues_found, base=1.0))
confidence = _apply_evidence_floor(confidence, evidence_floor, high, medium)
```

**`_score_issues` 扣分规则**（从 1.0 起步）：

| severity | 扣分 |
|----------|------|
| high | -0.30 |
| medium | -0.15 |
| 其他（含 low） | -0.05 |

结果截断到 `[0.0, 1.0]`。3 个 high 即可将分数压至 0.1。

**`_evidence_confidence_floor` 地板计算**（各条件互斥取 max）：

| 条件 | 地板值 |
|------|--------|
| `aigc_probability >= 0.9` 且 `forensics_confidence >= 0.7` | 0.58 |
| `aigc_probability >= 0.75` 且 `forensics_confidence >= 0.6` | 0.48 |
| `max(vt_score, threat_score) >= 0.75` | 0.58 |
| `max(text_risk_score, social_engineering_score) >= 0.7` | 0.50 |
| 溯源图谱 `nodes >= 3` 且有 citations | 0.45 |
| `phase == "commander"` 且 `forensics_confidence >= 0.7` 且 `threat_score >= 0.7` | 0.55 |

**全局上限**：`min(0.65, floor)` — 地板永远不超过 0.65。

**`_apply_evidence_floor` 应用**：地板可被 high/medium 问题部分"侵蚀"：
- `gap_penalty = min(0.14, len(high) * 0.06 + len(medium) * 0.03)`
- 最终返回 `max(confidence, evidence_floor - gap_penalty)`
- 例：地板 0.65 + 3 个 high → 实际地板 = 0.65 - 0.14 = 0.51

### 3.4 全部硬编码阈值速查表

| 阈值 | 值 | 用途 |
|------|-----|------|
| `CHALLENGER_SATISFACTION_THRESHOLD` | **0.8** | 置信度放行门槛 |
| `MAX_ROUNDS` | **5** | 每阶段最大质询轮次（硬上限也是 5） |
| `convergence_threshold` | **0.08** | Delta(t) 收敛阈值 |
| `CONSULTATION_STUCK_ROUNDS` | **3** | 触发人机协同所需的连续低置信轮数 |
| `CONSULTATION_CONFIDENCE_THRESHOLD` | **0.8** | 协同触发的低置信门槛 |
| `CONSULTATION_DELTA_THRESHOLD` | **0.08** | 协同触发的 delta 稳定门槛 |
| Forensics `low_confidence` | **0.55** | 硬规则：取证报告置信度过低 |
| Commander `overconfident_verdict` | **0.35** | 硬规则：置信度过低但裁决非 inconclusive |
| OSINT `citation_coverage` | **0.60** | 硬规则：引用覆盖率下限 |
| OSINT `inferred_ratio` | **0.35** | 硬规则：模型推断边占比上限 |
| 经验压制 token 重叠率 | **0.18** | 经验 RAG 匹配阈值 |
| 证据地板上限 | **0.65** | `_evidence_confidence_floor` 绝对上限 |

### 3.5 三重门控（打回/放行判定）

```
放行条件（满足任一即可）：
  ① 阈值放行：置信度 ≥ 0.8 且无 high 问题 且 LLM 不建议补证
  ② 轮次上限放行：达到 max_rounds（5轮）→ 强制放行，写入残留风险
  ③ 协同放行：用户跳过 / 专家建议放行 → 放行，标记 collaboration_release

打回条件（三重门控都不满足时）：
  requires_more_evidence = not maxed and not threshold_release and not collaboration_release
```

### 3.6 阶段隔离与跨阶段问题

Challenger **只审查当前阶段**的问题，跨阶段的质询点被**完全丢弃**（不写入 challenge_record，不出现在 residual_risks）：

```python
issues_found, cross_phase_issues = _current_phase_issues(issues_found, phase)
if cross_phase_issues:
    model_requires_more_evidence = False  # 忽略跨阶段质询
    model_target_agent = phase            # 重置为目标为当前阶段
```

### 3.7 基准质量（base_quality）的阶段差异

三阶段的基准质量来源不一致：

| 阶段 | base_quality 取值 |
|------|-------------------|
| forensics | `forensics.get("confidence", 0.5)` |
| osint | 优先 `provenance_graph.quality.completeness`，回退 `osint.get("confidence", 0.5)` |
| commander | `final_verdict.get("quality_score", final_verdict.get("confidence", 0.5))` |

### 3.8 经验库 RAG 的使用

经验库在 Challenger 中有**两次调用**：

1. **压制冗余质询点**（以 `agent="challenger"` 查询）：
   - 对经验匹配文本提取 token 集合
   - 经验文本必须同时包含"否定/跳过"标记和"质询/打回/补强"标记
   - token 重叠率 >= 0.18 时判定为可压制该质询点
   - 分母为 `min(len(issue_tokens), 24)`，长文本 issue 更容易被压制

2. **协同触发前拦截**（以当前 `phase` 查询）：
   - 仅在 `forensics` 和 `osint` 阶段生效，**commander 阶段不做经验辅助**
   - 且当前阶段尚未被经验库辅助过（每阶段最多 1 次）
   - 命中 → 取消人机协同，改为打回按经验补强

### 3.9 打回后如何"补强"

被打回的 Agent **不是原样重跑**，而是做**补强分析**：

1. **读取 Challenger 反馈**（`reinforcement_context`）：包含失败工具列表、期望补强方向、协同摘要、上轮分析
2. **工具复用**：`phase_round > 1` 时自动复用上轮成功的工具结果（按 `(tool, target)` 元组索引）
3. **重跑失败的工具**：仅重试失败/降级/新 IOC 对应的工具
4. **补强报告**：附加指令"本轮只针对逻辑质询 Agent 打回点和人机协同摘要补强，不重复上一轮完整报告"

### 3.10 关于 `evaluate_phase_convergence`

`conditions.py` 中定义了 `evaluate_phase_convergence` 和 `should_converge` 两个收敛函数，但**当前均未被实际调用**。收敛逻辑完全由 Commander 节点内联处理（`is_converged=True` 在 commander_node 返回时硬编码）。保留这些函数供未来图重构时启用。

---

## 四、Commander 最终裁决

### 4.1 权重计算

使用 `Decimal` 精确计算，`ROUND_HALF_UP` 舍入到 0.001：

```python
forensics_weight = 0.45（未降级）/ 0.25（降级）
osint_weight     = 0.30（未降级）/ 0.15（降级）
challenger_weight = 1.0 - forensics_weight - osint_weight
```

| 场景 | forensics | osint | challenger |
|------|-----------|-------|------------|
| 全部正常 | 0.45 | 0.30 | 0.25 |
| forensics 降级 | 0.25 | 0.30 | 0.45 |
| osint 降级 | 0.45 | 0.15 | 0.40 |
| 两者都降级 | 0.25 | 0.15 | 0.60 |

### 4.2 综合评分公式

```
aigc_score = forensics_aigc_prob × forensics_weight + osint_risk × osint_weight
overall_risk_score = max(aigc_score, osint_risk)
overall_confidence = forensics_conf × fw + osint_conf × ow + challenger_conf × cw
```

### 4.3 裁决逻辑

```
forged（伪造）:    aigc_score > 0.65 且 confidence > 0.6
                   或 osint_risk > 0.75 且 osint_conf > 0.5 且 quality > 0.45

suspicious（可疑）: aigc_score > 0.4 或 osint_risk > 0.4
                   或 osint.is_suspicious
                   或 forensics_is_aigc 且 confidence > 0.5

authentic（真实）:  confidence > 0.5 且未命中上述条件

inconclusive（不确定）: 其余情况
```

### 4.4 建议生成

按裁决分支差异化生成：

| verdict | 建议内容 |
|---------|---------|
| forged | 下架+溯源调查、逆向分析追踪生成工具、音频异常时建议声纹比对 |
| suspicious | 人工复核、不同工具交叉验证、补充检测维度 |
| authentic | 判定真实可正常使用、建议定期复检 |
| inconclusive | 人工专家介入、收集更多样本对比 |

所有分支额外检查 `forensics.degraded` 和 `osint.degraded`，降级时追加警告建议。

### 4.5 最终溯源图谱

Commander 构建**审定版**图谱：先使用 OSINT 阶段的 `provenance_graph`，再通过 `build_provenance_graph()` 重新构建并加入 `final_verdict`。

### 4.6 为什么直接结束

Commander → END 是图的硬边，原因：
1. 所有阶段性质询已在 Forensics 和 OSINT 阶段完成
2. Commander 已综合了 Challenger 的全部历史记录，再审一遍是冗余的
3. Commander 的裁决是确定性规则 + LLM 报告，没有外部工具可能失败
4. 最终报告需要一次性输出，不应再被打回循环

---

## 五、人机协同（Human-in-the-Loop）

人机协同不是普通聊天，而是自动流程遇到**低置信僵局**时的人工证据回注机制。

### 5.1 协同触发链路

```
Challenger 检测到卡住
  │
  ▼
查个人经验库 RAG ─── 命中 → 跳过协同，打回按经验补强（最多1次/阶段）
  │ 未命中
  ▼
评估触发条件 ─── 不满足 → 继续自动打回
  │ 满足
  ▼
触发人机协同
```

**经验库优先拦截**：在触发人机协同之前，先查当前账号的个人经验库 RAG（仅 forensics/osint 阶段，**commander 阶段不触发**）。如果命中，跳过协同，改为打回按经验补强一轮。补强后仍卡住才进入人机协同。

### 5.2 触发条件（五条件同时满足）

```
1. 最近 N 轮（默认3）都打回同一个 Agent
   → target_agent 一致，且 phase == target_agent（当前阶段打回当前阶段）
2. 最近 N 轮置信度全部 < 阈值（默认 0.8）
3. 相邻轮置信度变化都 < 阈值（默认 0.08，即没有改善趋势）
4. 未达到阶段最大轮次（phase_round < max_rounds）
5. 协同次数未超限：已完成协同数 < max(0, max_rounds - stuck_rounds)（最多2次）
```

### 5.3 首次 vs 重复触发

| 触发类型 | 条件 | 行为 |
|---------|------|------|
| 首次触发 | 之前没有已完成的协同 | 直接暂停，`event_type = "collaboration_required"` |
| 重复触发 | 已有 ≥1 次完成的协同 | 需要用户审批，`event_type = "collaboration_approval_required"` |

### 5.4 协同流程

```
Challenger 检测到卡住
  │
  ▼
LangGraph interrupt() ← 图执行暂停，状态自动 checkpoint
  │
  ▼
创建协同会话（Supabase collaboration_sessions）
  │
  ▼
前端收到 SSE 事件：collaboration_required 或 collaboration_approval_required
  │
  ├── 用户发起邀请链接（24h 有效）
  │     │
  │     ▼
  │   专家通过链接加入，提交结构化意见
  │   （角色 / 消息 / 锚定 Agent / 建议动作 / 置信度）
  │     │
  │     ▼
  │   用户结束协同
  │     │
  │     ▼
  │   Commander 自动生成协同摘要（两种版本）
  │     │
  │     ▼
  │   用户确认/编辑摘要
  │
  ▼
前端调用 detect/stream?resume=true
  │
  ▼
Command(resume=resume_payload) → 注入专家意见 + 确认的协同摘要
  │
  ▼
Challenger 重新执行（融合专家意见继续质询）
  │
  ▼
如果仍然卡住 → 再次触发协同（repeat_index 递增，最多2次）
如果收敛 → 放行到下一阶段
```

### 5.5 协同摘要的两种版本

| 版本 | 生成方式 | 用途 |
|------|---------|------|
| **机械摘要** (`build_moderator_summary`) | 规则拼接：key_quotes（最多5条，每条300字符）、按角色分组拼接、扫描含`?`的未解决问题 | 作为 LLM 不可用时的兜底 |
| **LLM 语义摘要** (`commander_summarize_consultation`) | LLM 阅读协同上下文、help_needed、专家任务和对话，生成结构化摘要 | 正常流程使用 |

优先使用用户手动确认的 `user_confirmed_summary`，否则使用 LLM 版本。

### 5.6 协同上下文构建

`build_consultation_context` 构建展示给用户和专家的上下文：

- **expert_tasks** 最多 5 条，优先高严重度问题，每条含 question / requested_action / expected_output
- **progress_summary** 包含三个 Agent 的置信度和降级状态
- **sample_links** 从 evidence_files 提取（含 storage_path 和 file_url）

### 5.7 协同恢复后的放行判定

```python
# 1. 将专家意见注入 review_challenges
human_context = _resume_collaboration_context(expert_messages, confirmed_summary)
if human_context:
    review_challenges.append(human_context)

# 2. LLM 审查时传入所有 challenges（含专家意见）
model_review = await challenger_model_review(...)

# 3. 放行关键词检查（reinforce 优先于 release）
打回关键词：["打回", "补强", "继续调查", "进一步核验", "继续补证", "不应放行"] → 不放行
放行关键词：["可以放行", "允许放行", "继续推进", "不要再强求", "能力上限",
           "工具上限", "无法获得更多证据", "带残留风险"] → 放行（带残留风险）

# 4. 用户跳过协同（action="skip_consultation"）
→ 直接放行，标记 collaboration_release = True
```

**注意**：关键词匹配是字符串 `in` 包含匹配，存在语义误判风险。例如"不应该放行"中的"放行"会命中 release marker，但因 reinforce marker 中有"不应放行"可先命中。然而"不应该放行"不包含"不应放行"这个精确子串，反而可能误命中 release marker。

### 5.8 个人经验入库

协同结束后，Commander 通过 `commander_extract_experience_drafts`（LLM）从专家交流中提取**可复用经验草稿**（方法、判据、补证路径、升级条件）。LLM 不可用时返回空数组。

草稿先按当前账号和目标 Agent 去重（相似度阈值 0.58），用户可在前端编辑、删除，再单独确认入库。
经验只保存可复用方法论，不保存具体检材名、链接或可识别案件细节。

### 5.9 协同次数上限

最多触发 **2 次**人机协同（`max_rounds - stuck_rounds = 5 - 3 = 2`）。第 2 次需用户审批，超过上限后不再触发协同。

### 5.10 interrupt 不可用时的降级

若 `langgraph.types.interrupt` 不可用（版本不支持），`consultation_required` 为 True 时只能记录日志继续自动重审，无法真正暂停等待人工。

---

## 六、工具层细节

### 6.1 工具并发模式（all-settled）

所有外部工具通过 `asyncio.gather` 并发执行，每个工具包裹在 `_settle_tool()` 中：
- 使用 `asyncio.wait_for(coro, timeout=timeout)` 设超时
- 超时或异常不中断其他工具，返回 `status="failed", degraded=True`
- 返回结构统一：`tool, target, status, degraded, result, summary, started_at, completed_at`

### 6.2 各工具超时与降级

| 工具 | 超时 | 降级行为 |
|------|------|---------|
| **Sightengine** | 内置重试 3 次（0.4s, 1.2s 退避） | 失败 → 尝试 Reality Defender fallback → mock（`degraded=True`, `aigc_probability` 0.45-0.55 确定性哈希） |
| **Reality Defender** | client/download/upload/poll 各有独立超时 | 失败 → mock（`degraded=True`, `confidence=0.2`） |
| **VirusTotal URL** | httpx 10s + 轮询 5×3s = 25s | 超时 → 回查已有报告 → 仍无 → `_pending_vt_url_result`（`degraded=True, threat_score=0.0, scan_available=False`，不将"未完成"误读为"安全"） |
| **VirusTotal 文件哈希** | 60s | 失败 → mock |
| **WhoisXML** | httpx client 级超时 | 无 key → `status="no_key"`；部分子组件失败 → `status="partial"`；DNS 403 → 专门 limitation 提示 |
| **Exa 搜索** | 20s | 无查询 → `status="degraded"`；无 key → `status="degraded"`；全部失败 → `status="failed"` |
| **内部文本 AIGC** | 进程级缓存（SHA-256 指纹） | 使用 `use_llm=False`（仅本地结构特征），确保确定性结果 |

### 6.3 文本 AIGC 检测融合

`analyze_text` 融合 LLM 分析和本地结构分析：

```
LLM 正常时：ai_probability = llm × 0.68 + local × 0.22 + social_engineering × 0.10
LLM 降级时：ai_probability = local × 0.78 + social_engineering × 0.22

is_ai_generated = ai_probability > 0.6
```

本地结构分析维度：句长均匀性（0.24）、词汇多样性（0.18）、burstiness（0.18）、短语重复度（0.18）、标点规律性（0.08）、模板标记（0.14）。

### 6.4 VirusTotal URL 共享机制

同一任务内相同 URL 复用同一个 completed 或历史结果（进程级缓存 `_URL_SCAN_CACHE`），避免 Forensics/OSINT 对同一 URL 得到互相矛盾的统计。但 Forensics 用 `virustotal_text_ioc`、OSINT 用 `virustotal_osint_ioc`，工具标识不同，**不跨 Agent 直接复用**。

### 6.5 降级控制器（DegradationManager）

- 每个 API 独立跟踪：`ok → degraded（1次失败）→ failed（连续3次失败）`
- `is_available` = status != "failed"（degraded 仍可用）
- **进程级单例** `shared_degradation`，多 Worker 部署下各 Worker 独立跟踪

### 6.6 溯源图谱构建

- **节点类型**：artifact, entity, source, evidence, finding, claim, event, agent, verdict
- **边类型**：extracted_from, mentions, derived_from, supports, refutes, contradicts, reviewed_by, before, after
- **质量指标**：completeness（节点+边数/12）、citation_coverage（有引用的边占比）、model_inferred_ratio（模型推断边占比）
- **稳定 ID**：SHA-256 前 12 位，自动去重
- **模型推断**：无引用的关系标记 `model_inferred=true`，不得展示为外部事实

---

## 七、完整状态流转（案例3实战）

假设用户上传"政府通知"图片（`案例3-图片-政府通知.jpg`）+ 相关文本（`案例3-文本-政府通知.txt`），提示词为"请鉴定该通知是否为 AIGC 伪造公文"。

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第1轮：Forensics 阶段（电子取证）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Forensics Agent 执行：**

1. **自主推理**：Agent LLM 读取图片 + 文本 + case_prompt，分析排版风格、公章细节、文本措辞
2. **并发工具调用（all-settled）：**
   - 图片 → **Sightengine AIGC 检测** → AI 生成概率 87%
   - 图片 SHA-256 → **VirusTotal** → 无恶意标记
   - 文本 → **内部文本 AIGC 检测** → AI 概率 72%，社工风险 0.45
   - 文本 URL → **VirusTotal URL** → 威胁评分 0.15
3. **案例 RAG** + **经验 RAG** 检索类似案例和个人经验作为参考
4. **融合输出**：自主推理 + 工具结果 → 取证报告

**Forensics 置信度计算（三段式）：**
```
有 RD/Sightengine 成功结果 →
confidence = max(0.2, min(0.95, max(rd_conf, text_aigc_conf, 0.55 + vt_threat * 0.25)))
→ 约 0.78
```

**Challenger 审查（phase=forensics, round=1）：**

```
├── 硬规则检查（_forensics_issues）：
│   ├── missing_forensics? ✗（报告存在）
│   ├── missing_tool_matrix? ✗（4 个工具）
│   ├── tool_failed? ✗（全部成功）
│   ├── tool_degraded? ✗
│   └── low_confidence? ✗（0.78 > 0.55）
│
├── LLM 交叉审查：
│   ├── model_confidence: 0.82
│   └── model_issues: 1 个 medium（工具降级说明）
│
├── 经验 RAG 压制检查：无匹配质询点被压制
│
├── 置信度计算：
│   ├── _score_issues: 0 high, 1 medium → 1.0 - 0.15 = 0.85
│   ├── confidence = min(0.82, 0.85) = 0.82
│   ├── evidence_floor: aigc_prob=0.87 < 0.9 → 0.48
│   └── 最终: max(0.82, 0.48) = 0.82
│
├── 三重门控判定：
│   ├── 阈值放行：0.82 ≥ 0.8 且无 high 且 LLM 不要求补证 → 满足 ✓
│   └── → 放行
│
└── 结果：requires_more_evidence = False → 放行 ✓
```

**结果：放行** → `analysis_phase` 更新为 `osint`

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第2轮：OSINT 阶段（情报溯源）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**OSINT Agent 执行：**

1. **自主推理**：读取全局证据板 + Forensics 结果 + 原始样本
2. **文本声明抽取**：`text_claim_extract` 提取关键声明、社工话术、URL 线索
3. **文本 AIGC 检测**：通过 `text_fingerprint` 匹配 Forensics 已有结果 → **复用**，不重复调用
4. **并发工具调用（all-settled）：**
   - URL → **VirusTotal URL**（独立工具标识 `virustotal_osint_ioc`，同 URL 重新请求）
   - URL → **WhoisXML 域名溯源** → 注册时间仅 3 天，高度可疑
   - 脱敏查询词 → **Exa 搜索** → 未找到官方来源佐证
5. **构建溯源图谱**：文本 → URL → 域名 → 注册者（5 节点，3 条引用，引用覆盖率 60%）
6. **融合输出**：自主推理 + 工具结果 → OSINT 报告

**OSINT 置信度计算：**
```
Exa 成功 + VT 有结果 →
osint_confidence = min(0.92, 0.62 + len(search_results) * 0.04)
→ 约 0.82
```

**Challenger 审查（phase=osint, round=1）：**

```
├── 硬规则检查（_osint_issues）：
│   ├── missing_osint? ✗
│   ├── missing_graph? ✗
│   ├── thin_graph? ✗（5 ≥ 3）
│   ├── missing_citations? ✗（有引用）
│   ├── low_citation_coverage? ✗（0.60 ≥ 0.60）
│   ├── too_many_model_inferred_edges? ✗（0.35 ≤ 0.35）
│   ├── missing_osint_tool_matrix? ✗
│   ├── osint_tool_failed? ✗
│   └── osint_tool_degraded? ✗
│
├── 置信度：0.82 ≥ 0.8 → 阈值放行 ✓
│
└── 结果：放行 ✓
```

**结果：放行** → `analysis_phase` 更新为 `commander`

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第3轮：Commander 阶段（最终裁决）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Commander Agent 执行：**

1. **权重计算**：forensics=0.45, osint=0.30, challenger=0.25（均未降级）
2. **综合评分**：
   ```
   aigc_score = 0.87 × 0.45 + 0.75 × 0.30 = 0.617
   overall_confidence = 0.78 × 0.45 + 0.82 × 0.30 + 0.82 × 0.25 = 0.806
   ```
3. **裁决**：`aigc_score (0.617) > 0.4` → `verdict = "suspicious"`
4. **LLM 裁决报告**：`commander_ruling()` 生成结构化 Markdown
5. **最终溯源图谱**：`build_provenance_graph()` 加入 `final_verdict`
6. **建议**：人工复核、交叉验证、补充检测维度

**Commander → END：** 直接结束，`is_converged = True`，`termination_reason = "commander_ruling"`

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 打回场景：Forensics 被打回 → 补强
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

假设 Challenger 第1次审查 Forensics 时发现 high 问题：

```
Challenger 审查发现：
├── [high] tool_failed: VirusTotal 超时
├── [high] low_confidence: 0.50 < 0.55
├── _score_issues: 2 high → 1.0 - 0.60 = 0.40
├── confidence = min(model_confidence, 0.40) = 0.40
├── 阈值放行：0.40 < 0.8 → 不满足
├── 轮次上限：round=1 < 5 → 不满足
└── 判定：打回 → target_agent = "forensics"
```

**Forensics 第2次执行（phase_round=2）：**

1. **读取 Challenger 反馈**（`reinforcement_context`）：获知 VT 失败、期望补强方向
2. **工具复用**：Sightengine、文本 AIGC 检测自动复用（标记 `reused=True`）
3. **重跑失败工具**：VirusTotal 重新尝试
4. **补强分析**：只针对打回点写补充报告，附加指令"不重复上一轮完整报告"

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 人机协同场景：连续低置信僵局
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

假设 Forensics 阶段连续 3 轮被打回，置信度 0.60 → 0.62 → 0.63：

**第3轮打回后触发协同前检查：**

```
1. 查经验库 RAG ─── 未命中
2. 评估触发条件：
   ├── 连续 3 轮 target_agent 一致？ ✓（"forensics"）
   ├── 3 轮置信度全部 < 0.8？ ✓（0.60, 0.62, 0.63）
   ├── 相邻变化 < 0.08？ ✓（0.02, 0.01）
   ├── phase_round < max_rounds？ ✓（3 < 5）
   └── 协同次数 < 2？ ✓（0 < 2）
3. 首次触发 → event_type = "collaboration_required"
```

**协同流程：**

```
interrupt() → 图暂停，状态 checkpoint 到内存
  │
  ▼
创建协同会话 → 前端显示邀请面板
  │
  ▼
用户邀请数字取证专家加入
  │
  ▼
专家提交结构化意见
  │
  ▼
用户结束协同 → Commander 生成两种摘要：
  - 机械摘要（规则拼接，兜底用）
  - LLM 语义摘要（正常流程使用）
  │
  ▼
用户确认/编辑摘要
  │
  ▼
resume=true → 注入专家意见 + 确认摘要
  │
  ▼
Challenger 重新审查（融合专家意见）
  │
  ├── 专家意见含"可以放行" → collaboration_release = True → 放行
  └── 专家意见含"继续调查" → 不放行 → 继续打回
```

**经验入库**：`commander_extract_experience_drafts` 提取草稿 → 用户编辑确认 → 入库（相似度阈值 0.58 去重）

---

## 八、报告与持久化

### 8.1 最终报告结构（Markdown 九章节）

1. 任务信息（表格）
2. 最终裁决（verdict, confidence, key_evidence）
3. 降级状态汇总（仅在降级时出现）
4. 电子取证 Agent 分析
5. 情报溯源 Agent 分析
6. 公开案例与个人经验 RAG 检索情况
7. 逻辑质询时间线
8. 全程审计日志（**最多展示 50 条**）
9. 建议与说明

### 8.2 report_hash 计算

对 `task_id, verdict, confidence_overall, summary, key_evidence, recommendations, verdict_payload, generated_at, share_token` 取值，递归脱敏 11 个敏感 key（token/signed_url 等），JSON 序列化（`sort_keys=True, separators=(",",":")`）后 SHA-256。

**注意**：`verdict_payload` 嵌套很深，脱敏递归进入 dict/list，但只覆盖 11 个 key 名。若含其他敏感字段名（如 `api_key`），不会被过滤。

### 8.3 PDF 降级链

`fpdf` → `Pillow`（150 DPI A4）→ 两者均失败则 HTTP 500。fpdf 需要中文字体（搜索 simhei/msyh/simsun/PingFang/DejaVuSans）。

### 8.4 状态持久化

- `analysis_states` 表保存每轮中间结果快照（forensics/osint/challenger/final_verdict + evidence_board）
- `reports` 表保存最终报告和 verdict_payload
- resume 回退时从 `analysis_states` 重建状态，跳过已完成阶段直接进入 Commander

### 8.5 detection_run_id

每次新检测生成 UUID，写入 task metadata、SSE 事件、审计日志和 final_verdict。三层回退查找：report → task → analysis_states → audit_logs → agent_logs。

---

## 九、完整状态流转图

```
State 变化追踪（正常流程 3 轮结束）：

轮次1: START
  → forensics_node 执行
    state.analysis_phase = "forensics"
    state.phase_rounds = {"forensics": 1, "osint": 1, "commander": 1}
    state.forensics_result = {...取证报告...}
    state.tool_results = {"forensics": [...]}
  → challenger_node 执行
    state.challenger_feedback = {phase: "forensics", requires_more_evidence: false, ...}
  → challenger_route: 返回 "osint"（放行）

轮次2:
  → osint_node 执行
    state.analysis_phase = "osint"
    state.osint_result = {...情报报告...}
    state.provenance_graph = {...溯源图谱...}
    state.tool_results = {"forensics": [...], "osint": [...]}
  → challenger_node 执行
    state.challenger_feedback = {phase: "osint", requires_more_evidence: false, ...}
  → challenger_route: 返回 "commander"（放行）

轮次3:
  → commander_node 执行
    state.final_verdict = {...最终裁决（含 detection_run_id）...}
    state.analysis_phase = "commander"
    state.is_converged = true
    state.termination_reason = "commander_ruling"
  → END（直接结束，不再经过 Challenger）

后续：
  → persist_update 写入 analysis_states
  → upsert_report 写入 reports（含 report_hash）
  → SSE 推送 final_verdict → case_import_* → complete
```

---

## 十、SSE 事件

检测流使用 `POST /api/v1/detect/stream` 返回 SSE。协同事件使用 `collaboration_*` 前缀（兼容旧 `consultation_*`）：

| 事件 | 触发时机 |
|------|---------|
| `start` | 检测开始 |
| `node_start` / `node_complete` | 节点开始/完成 |
| `agent_log` | Agent 日志 |
| `evidence_update` / `challenges_update` | 证据/质询更新 |
| `forensics_result` / `osint_result` / `challenger_feedback` | 阶段结果 |
| `final_verdict` | 最终裁决 |
| `timeline_update` / `weights_update` / `round_update` | 时间线/权重/轮次更新 |
| `collaboration_required` | 首次触发人机协同，自动暂停 |
| `collaboration_approval_required` | 重复触发，需用户审批 |
| `collaboration_started` | 协同会话开始 |
| `collaboration_summary_pending` | 等待用户确认摘要 |
| `collaboration_summary_confirmed` | 摘要已确认，准备恢复 |
| `collaboration_skipped` | 用户跳过协同 |
| `collaboration_resumed` | 协同恢复，流程继续 |
| `case_import_start/created/duplicate/skipped/error` | 公开案例入库 |
| `task_failed` / `error` / `complete` | 终态事件 |

**已完成任务复用**：再次收到非 resume 的 stream 请求时，直接从 reports/analysis_states 恢复 final_verdict，推送 `final_verdict → case_import_skipped → complete(reused=true)`。

---

## 十一、总结

```
┌─────────────────────────────────────────────────────────────────────┐
│                         正常自动流程                                  │
│                                                                     │
│  Forensics → Challenger → OSINT → Challenger → Commander → END      │
│      ▲           │                       │                          │
│      └───────────┘ 打回(≤5轮)            │ 打回(≤5轮)               │
│                                          └─────────────────────     │
│                                                                     │
│  每阶段独立计轮次，被打回后做"补强分析"而非原样重跑                      │
│  已成功的外部工具自动复用，不重复调用 API                               │
│  三重门控：阈值放行 / 轮次上限放行 / 协同放行                           │
│  MemorySaver 内存级 checkpoint，进程重启后从 analysis_states 回退      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    连续 N 轮卡在同一阶段
                    置信度 < 阈值 且无改善趋势
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         人机协同流程                                  │
│                                                                     │
│  ① 经验库 RAG 优先拦截 → 命中则跳过协同，按经验补强（commander 不触发）  │
│  ② 未命中 → interrupt() 暂停 → 专家注入意见 → resume()               │
│  ③ Commander 生成摘要（机械版 + LLM 版）→ 用户确认 → 融合意见继续      │
│  ④ 首次自动触发；重复触发需用户审批；最多 2 次                          │
│  ⑤ 协同结束后 LLM 提取经验草稿 → 用户确认入库                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**一句话总结：取证 → 质询 → 情报 → 质询 → 裁决 → 结束。Challenger 是裁判，它说"不行"就打回补强，说"过了"就前进。如果反复打回都做不好，先查经验库，再不行就请人类专家来帮忙。Commander 裁决后直接结束，不再重复质询。**
