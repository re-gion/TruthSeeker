# TruthSeeker 四 Agent 阶段式辩论 + 专家会诊 拓扑详解（当前版本）

> 更新日期：2026-06-03
> 对应代码：`truthseeker-api/app/agents/graph.py`、`nodes/*.py`、`edges/conditions.py`、`services/consultation_workflow.py`

---

## 一、整体拓扑

系统是一条**阶段式流水线**，每个阶段由专业 Agent 执行后交给 Challenger 质询：
Challenger 决定"打回重做"还是"放行到下一阶段"。Commander 生成最终裁决后直接结束。

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

### 与旧拓扑的关键区别

| 对比维度 | 旧拓扑 | 当前拓扑 |
|---------|--------|---------|
| Commander 审查 | Commander → Challenger → END | Commander → **END**（不再经过 Challenger） |
| 轮次跟踪 | 全局统一 `current_round` | **每阶段独立** `phase_rounds`（各阶段互不干扰） |
| 质量历史 | 全局 `confidence_history` | **每阶段独立** `phase_quality_history` |
| 被打回后做什么 | 原样重跑 | 带上 **Challenger 反馈 + 会诊摘要** 做"补强分析" |
| 已成功的工具 | 每轮都重调 | **自动复用**上轮已成功的工具结果（跳过重复调用） |
| 跨阶段质询 | 无特殊处理 | **自动忽略**跨阶段的质询点，当前阶段只审查当前阶段 |

---

## 二、四个 Agent 各自的职责与工具

| Agent | 角色 | 核心任务 | 可调用工具 |
|-------|------|---------|-----------|
| **Forensics** | 电子取证专家 | 对所有检材做技术检测，输出结构化取证报告 | AIGC 图片检测器（Sightengine）、Reality Defender（音视频深伪）、VirusTotal（文件哈希 + 文本 URL）、内部文本 AIGC 检测、案例 RAG、Kimi LLM 多模态推理 |
| **OSINT** | 情报溯源分析师 | 追踪来源、构建溯源图谱、评估威胁 | 文本声明抽取 + AI 检测 + 社工风险评分、VirusTotal URL、WhoisXML 域名溯源、Exa 搜索、案例 RAG、溯源图谱构建器、Kimi LLM |
| **Challenger** | 逻辑质询官 | 交叉验证、质询、决定是否放行 | Kimi LLM（结构化 JSON 审查）、确定性代码检查器（硬规则：缺失报告 / 工具失败 / 低置信度 / 图谱稀薄等） |
| **Commander** | 研判指挥官 | 综合所有证据做出最终裁决 | Kimi LLM（最终裁决报告）、溯源图谱构建器、加权置信度计算器 |

---

## 三、逐轮实战：案例3（政府通知图片 + 文本）

假设用户上传了一张"政府通知"图片（`案例3-图片-政府通知.jpg`）和一段相关文本（`案例3-文本-政府通知.txt`），全局检测提示词为"请鉴定该通知是否为 AIGC 伪造公文"。

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第1轮：Forensics 阶段（电子取证）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Forensics Agent 执行：**

1. 识别出 2 个检材：图片（媒体模态）+ 文本（文本模态）
2. **并发启动外部工具调用（all-settled）：**
   - 对图片调用 **AIGC 图片检测器** → 返回 AI 生成概率 87%
   - 对图片算 SHA-256 哈希，查 **VirusTotal** → 无恶意标记
   - 读取文本内容，调用**内部文本 AIGC 检测** → AI 概率 72%，社工风险 0.45
   - 从文本提取 URL，查 **VirusTotal URL** → 威胁评分 0.15
3. 所有工具结果 all-settled 后，调用**案例 RAG** 检索类似案例
4. 将全部工具结果 + 案例参考交给 **Kimi LLM** 生成取证报告：
   - 自主推理：图片排版风格、公章细节、文本措辞
   - 外部工具结果融合：Sightengine 87%、文本 AI 72%、VT 安全
   - 综合判断：高概率 AIGC，文本存在社工话术

**Challenger 第1次审查（Forensics 阶段，phase_round=1）：**

```
审查过程：
├── 硬规则检查（代码）：
│   ├── 取证报告存在？ ✓
│   ├── 工具矩阵已形成？ ✓（4 个工具）
│   ├── 有工具失败？ ✗ → 无
│   ├── 置信度 > 0.55？ ✓（0.78）
│   └── 文本 AI 检测结果已包含？ ✓
│
├── LLM 交叉审查（Kimi）：
│   ├── 分析 Forensics 报告的逻辑一致性
│   ├── 与用户样本对比
│   └── 输出：建议补充分析工具降级说明
│
└── 综合判定：
    ├── 硬规则 issues：0 个 high
    ├── LLM issues：1 个 medium（工具降级说明）
    ├── 置信度：0.78（经扣分后）
    ├── quality_delta：None（首轮无历史）
    └── 判定：置信度 > 0.8？否 → 有 high？否 → 打回？否
        → 放行 ✓（置信度未满 0.8 但无 high 问题，首轮回退条件不触发）
```

**结果：放行** → `analysis_phase` 更新为 `osint`，进入 OSINT 阶段

> 注意：如果首轮有 high 问题或 LLM 建议 `requires_more_evidence`，会打回 Forensics 重跑。
> 打回时 Forensics 会读取 Challenger 的 `challenger_feedback`，只针对打回点补强，不重复完整分析。

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第2轮：OSINT 阶段（情报溯源）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**OSINT Agent 执行：**

1. 读取全局证据板 + Forensics 取证结果
2. 读取文本内容，做**文本声明抽取** → 提取关键声明
3. **并发启动外部工具调用（all-settled）：**
   - 对文本调用 **AI 文本检测**（如 Forensics 已做且文本相同，自动复用，不重复调用）
   - 从文本提取 URL，查 **VirusTotal URL**（如 Forensics 已查过同一 URL，自动复用）
   - 对 URL 调用 **WhoisXML 域名溯源** → 注册时间仅 3 天，高度可疑
   - 生成脱敏查询词，调用 **Exa 搜索** → 未找到官方来源佐证
4. 调用**案例 RAG** 检索类似案例
5. 构建**溯源图谱**：文本 → URL → 域名 → 注册者（节点 + 边 + 引用）
6. Kimi LLM 输出 OSINT 报告：
   - 自主推理：域名极新、无官方佐证、社工话术明显
   - 外部情报融合：WhoisXML 注册 3 天、Exa 无佐证
   - 来源可信度：低
   - 关联风险：高度疑似钓鱼/伪造公文

**Challenger 第2次审查（OSINT 阶段，phase_round=1）：**

```
审查过程：
├── 硬规则检查（代码）：
│   ├── 情报溯源报告存在？ ✓
│   ├── 溯源图谱存在？ ✓
│   ├── 图谱节点 ≥ 3？ ✓（5 个节点）
│   ├── 图谱有引用？ ✓（3 条引用）
│   ├── 引用覆盖率 ≥ 25%？ ✓（60%）
│   ├── 模型推断占比 ≤ 65%？ ✓（40%）
│   └── 工具矩阵已形成？ ✓
│
├── LLM 交叉审查（Kimi）：
│   ├── 验证溯源图谱的逻辑链
│   ├── 检查是否有遗漏的重要情报源
│   └── 输出：建议精确化 Exa 搜索关键词
│
└── 综合判定：
    ├── 硬规则 issues：0 个 high，1 个 medium
    ├── LLM issues：1 个 medium（Exa 搜索词过宽）
    ├── 置信度：0.82
    ├── quality_delta：None（OSINT 首轮）
    └── 判定：置信度 > 0.8 且无 high → 放行 ✓
```

**结果：放行** → `analysis_phase` 更新为 `commander`，进入 Commander 阶段

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 第3轮：Commander 阶段（最终裁决）
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Commander Agent 执行：**

1. **汇总所有结果：**
   - Forensics 取证报告（AIGC 概率 87%，置信度 0.78）
   - OSINT 情报报告（威胁评分 0.75，溯源图谱 5 节点）
   - Challenger 历史质询记录（2 个阶段的审查结果）
   - 专家会诊意见（如有）

2. **加权置信度计算（确定性数值计算）：**
   ```
   forensics_weight = 0.45（未降级）
   osint_weight = 0.30（未降级）
   challenger_weight = 0.25

   overall_confidence = 0.78 × 0.45 + 0.82 × 0.30 + 0.82 × 0.25 = 0.806
   ```

3. **裁决逻辑（规则判定）：**
   ```
   aigc_score = 0.87 × 0.45 + 0.75 × 0.30 = 0.617
   overall_risk = max(0.617, 0.75) = 0.75

   → aigc_score > 0.4 或 osint_risk > 0.4 → verdict = "suspicious"（可疑）
   ```

4. **调用 Kimi LLM 生成最终裁决报告：**
   - 综合 Forensics + OSINT + Challenger + 专家意见
   - 输出：结构化裁决报告（Markdown 格式）
   - 包含：结论、关键证据、置信度分解、后续建议

5. **生成最终溯源图谱**（审定版，合并 Forensics + OSINT 的发现）

**Commander → END：**

Commander 输出 `final_verdict` 后**直接结束**，不再经过 Challenger 审查。

这是与旧拓扑最大的区别——旧拓扑中 Commander 完成后还要经过 Challenger 再审一遍，
但这会导致最终报告阶段重复前序质询的问题（Commander 本身已综合了 Challenger 的所有历史记录），
所以当前拓扑改为 Commander 直接结束。

---

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 打回场景示例：Forensics 被打回重跑
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

假设 Challenger 第1次审查 Forensics 时发现了 high 问题：

```
Challenger 审查发现：
├── [high] 工具矩阵中有 1 个工具调用失败（VirusTotal 超时）
├── [high] 置信度偏低（0.55）
└── 判定：打回 → target_agent = "forensics"
```

**Forensics 第2次执行（phase_round=2）：**

1. **读取 Challenger 反馈**（`reinforcement_context`）：
   - 获知哪些工具失败了
   - 获知 Challenger 期望补强的方向
2. **工具复用**：上轮已成功的工具（AIGC 检测、文本 AI 检测）自动复用，不重复调用
3. **重跑失败的工具**：VirusTotal 重新尝试
4. **补强分析**：只针对 Challenger 打回点写补充报告，不重复完整分析

**Challenger 第2次审查（Forensics 阶段，phase_round=2）：**

```
收敛判定：
├── quality_delta = |上轮置信度 - 本轮置信度| = |0.55 - 0.78| = 0.23
├── delta < 0.08？ ✗ → 不稳定
├── 置信度 > 0.8？ ✓
├── 至少 2 轮？ ✓
└── 三重门控未全部满足 → 打回？看有没有 high issues
    ├── high issues：0 个
    └── 无 high → 放行 ✓（进入 OSINT）
```

---

## 四、Challenger 的核心机制

### 4.1 阶段隔离

Challenger 是**阶段隔离**的——它只审查当前阶段的问题，忽略跨阶段的质询点。

```python
# 举例：Challenger 在 forensics 阶段发现了一个 osint 相关的问题
# → 这个问题会被自动过滤掉，不影响 forensics 阶段的判定
issues, cross_phase_issues = _current_phase_issues(issues_found, phase)
if cross_phase_issues:
    model_requires_more_evidence = False  # 忽略跨阶段质询
```

### 4.2 双重审查机制

Challenger 对每个阶段做两层审查：

1. **确定性代码检查（硬规则）**：不依赖 LLM，纯代码判定
   - Forensics 阶段：报告是否存在、工具是否失败、置信度是否达标
   - OSINT 阶段：图谱是否存在、节点是否够、引用是否充分
   - Commander 阶段：裁决枚举是否合法、是否携带图谱

2. **LLM 交叉审查（软判断）**：调用 Kimi 做逻辑一致性分析
   - 输出结构化 JSON：置信度、是否需要补证、打回目标 Agent
   - 与硬规则结果合并，取并集

### 4.3 收敛判定（三重门控）

Challenger 决定"打回还是放行"的逻辑：

```
放行条件（满足任一即可）：
  ① 置信度 > 0.8 且无 high 问题 且 LLM 不建议补证（首轮高置信直通）
  ② quality_delta < 0.08 且 置信度 > 0.8（稳定收敛）
  ③ 达到最大轮次（5轮）→ 强制放行，记录残留风险

打回条件（需同时满足）：
  - 未达到最大轮次
  - 有 high 问题 或 LLM 建议 requires_more_evidence
  - 未满足收敛门控
```

### 4.4 首轮高置信直通

新增了一个优化：如果第1轮审查就满足以下条件，直接放行，不浪费轮次：
- 置信度 > 0.8
- 没有 high 严重度问题
- LLM 没有建议 `requires_more_evidence`

---

## 五、专家会诊（Human-in-the-Loop）

### 5.1 触发条件

专家会诊**不是**简单地"连续3轮打回就触发"。它有更精确的判定逻辑：

```
触发条件（四个必须同时满足）：
  1. 最近 N 轮（默认3轮）都打回同一个 Agent
     → target_agent 必须一致，且 phase == target_agent（当前阶段打回当前阶段）
  2. 最近 N 轮都有高严重度问题
  3. 当前置信度 < 阈值（默认 0.8）
  4. 相邻轮置信度变化都 < 阈值（默认 0.08，即没有改善趋势）
```

### 5.2 首次 vs 重复触发

| 触发类型 | 条件 | 行为 |
|---------|------|------|
| 首次触发 | 之前没有已完成的会诊 | 直接暂停，`event_type = "consultation_required"` |
| 重复触发 | 已有 ≥1 次完成的会诊 | 需要主持人审批，`event_type = "consultation_approval_required"` |

### 5.3 会诊流程

```
Challenger 检测到卡住
  │
  ▼
LangGraph interrupt() ← 图执行暂停，状态自动 checkpoint
  │
  ▼
创建会诊会话（Supabase consultation_sessions）
  │
  ▼
前端收到 SSE 事件：consultation_required 或 consultation_approval_required
  │
  ├── 用户发起邀请链接（24h 有效）
  │     │
  │     ▼
  │   专家通过链接加入，提交结构化意见
  │   （角色 / 消息 / 锚定 Agent / 建议动作 / 置信度）
  │     │
  │     ▼
  │   用户关闭会话
  │     │
  │     ▼
  │   Commander 自动生成会诊摘要（`build_moderator_summary`）
  │   摘要包含：专家关键引文、意见数量、未解决问题
  │     │
  │     ▼
  │   用户确认/编辑摘要
  │
  ▼
前端调用 detect/stream?resume=true
  │
  ▼
Command(resume=resume_payload) → 注入专家意见 + 确认的会诊摘要
  │
  ▼
Challenger 重新执行（融合专家意见继续质询）
  │
  ▼
如果仍然卡住 → 再次触发会诊（repeat_index 递增）
如果收敛 → 放行到下一阶段
```

### 5.4 会诊恢复后 Challenger 如何使用专家意见

```python
# 1. 将专家意见注入 review_challenges
human_context = _resume_consultation_context(expert_messages, confirmed_consultation_summary)
if human_context:
    review_challenges.append(human_context)

# 2. LLM 审查时传入所有 challenges（含专家意见）
model_review = await challenger_model_review(
    forensics, osint, review_challenges, ...
)

# 3. 用户跳过会诊时（action="skip_consultation"）
# → 直接取消打回，强制放行
if consultation_resume_payload.get("action") == "skip_consultation":
    requires_more_evidence = False
```

---

## 六、被 Agent 打回后如何"补强"（而非重跑）

这是当前拓扑的一个重要设计：被打回的 Agent 不是原样重跑，而是做**补强分析**。

### 6.1 Forensics 补强

```python
# 检查是否有 Challenger 反馈需要补强
reinforcement_context = _build_reinforcement_context(state, "forensics", state.get("forensics_result"))
if reinforcement_context:
    raw_forensics["reinforcement_context"] = reinforcement_context
    # → LLM 生成报告时会看到：
    #   - Challenger 发现了哪些问题
    #   - 会诊摘要中的专家意见
    #   - 指令："本轮只针对 Challenger 打回点和会诊摘要补强，不重复上一轮完整报告"
```

### 6.2 OSINT 补强

同理，OSINT 被打回时也会读取 `reinforcement_context`，只针对打回点做补充分析。

### 6.3 工具复用

```python
# 被打回重跑时，上轮已成功的工具结果自动复用
previous_successes = _previous_successes(state)

def maybe_reuse(tool, target):
    if phase_round <= 1:
        return False  # 首轮不复用
    previous = previous_successes.get((tool, target))
    if previous:
        settled_results.append({**previous, "reused": True})
        return True  # 复用，不重复调用
    return False

# 例如：AIGC 检测在第1轮成功了，第2轮直接复用，不重新调 API
```

---

## 七、Commander 为什么不再经过 Challenger

旧拓扑中 Commander 完成后要经过 Challenger 审查，但这导致了几个问题：

1. **Commander 已经综合了 Challenger 的所有历史质询记录**——再审一遍是冗余的
2. **Commander 的裁决是确定性规则 + LLM 报告**——不像 Forensics/OSINT 有外部工具可能失败
3. **Commander 阶段被 Challenger 打回会导致循环**——Commander 没有新的工具可以重跑

所以当前拓扑改为：Commander 生成 `final_verdict` 后直接 `→ END`。

---

## 八、完整状态流转图

```
State 变化追踪（正常流程 3 轮结束）：

轮次1: START
  → forensics_node 执行
    state.analysis_phase = "forensics"
    state.phase_rounds = {"forensics": 1, "osint": 1, "commander": 1}
    state.forensics_result = {...取证报告...}
  → challenger_node 执行
    state.challenger_feedback = {phase: "forensics", requires_more_evidence: false, ...}
  → challenger_route: 返回 "osint"（放行）

轮次2:
  → osint_node 执行
    state.analysis_phase = "osint"
    state.osint_result = {...情报报告...}
    state.provenance_graph = {...溯源图谱...}
  → challenger_node 执行
    state.challenger_feedback = {phase: "osint", requires_more_evidence: false, ...}
  → challenger_route: 返回 "commander"（放行）

轮次3:
  → commander_node 执行
    state.final_verdict = {...最终裁决...}
    state.analysis_phase = "commander"
    state.is_converged = true
  → END（直接结束，不再经过 Challenger）
```

---

## 九、总结

```
┌─────────────────────────────────────────────────────────────────────┐
│                         正常自动流程                                  │
│                                                                     │
│  Forensics → Challenger → OSINT → Challenger → Commander → END      │
│      ▲           │                       │                          │
│      └───────────┘ 打回(≤5轮)            │ 打回(≤5轮)               │
│                                          └─────────────────────     │
│                                                                     │
│  每阶段独立计轮次，被 Agent 打回后做"补强分析"而非原样重跑              │
│  已成功的外部工具自动复用，不重复调用 API                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    连续 N 轮卡在同一阶段
                    置信度 < 阈值 且无改善趋势
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         专家会诊流程                                  │
│                                                                     │
│  interrupt() → 人类专家注入意见 → resume()                           │
│  Commander 自动生成摘要 → 用户确认 → Challenger 融合专家意见继续        │
│  首次自动触发；重复触发需主持人审批                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**一句话总结：取证 → 质询 → 情报 → 质询 → 裁决 → 结束。Challenger 是裁判，它说"不行"就打回重做（补强），说"过了"就前进。如果反复打回都做不好，就暂停请人类专家来帮忙。Commander 裁决后直接结束，不再重复质询。**
