# TruthSeeker Agent + Skill 架构规格

> 状态：四 Agent 固定 Skill 运行时、Commander 三工作流、前端固定绑定展示与报告执行矩阵均已接入。  
> 决策日期：2026-08-04  
> 依据：[ADR-0001](./adr/0001-fixed-core-agent-skills.md) 与根目录 [CONTEXT.md](../CONTEXT.md)。

## 1. 目标与非目标

目标不是把现有系统提示词改名为 Skill，而是建立可版本化、可测试、可审计的专业能力层，并能证明本轮是否真实采用了它。

第一版不实现：

- 根据案件自动选择多个 Skill；
- Skill 自行修改评分、路由或 Challenger 门槛；
- Skill 自行安装新工具或访问未授权资源；
- 缺失 Skill 时伪装成正常执行；
- 在普通用户界面公开完整提示词和内部检查规则。

### 当前实施状态（2026-08-04）

- 已实现四个固定绑定的 `SKILL.md` 包、严格 frontmatter/schema 校验、SHA-256 内容摘要和 Commander 三工作流定向提取。
- 已实现 `load_status`、`execution_status`、`contract_checks`、`check_results` 与 `limitations`，缺失或损坏时返回结构化降级且不注入 Skill。
- Forensics、OSINT、Challenger 和 Commander 最终裁决均已在 LLM 调用前加载对应 Skill，并把加载、应用、跳过或检查失败写入日志、审计、结果和 `degradation_status`。
- Commander 的 `human_collaboration` 已覆盖求助点去重与协同摘要，`experience_distillation` 已覆盖经验草稿提炼；执行元数据会随协同上下文、摘要或显式 sink 传回并进入审计。
- Agent 卡片已展示静态绑定名称和版本；最终报告已从持久化运行时元数据生成 Skill 执行摘要矩阵。可选真实 Kimi 对照评测仍未执行。

## 2. 三层职责与优先级

| 层 | 负责 | 不负责 |
|---|---|---|
| 确定性 Python | 评分、路由、硬门槛、协议字段、结构化降级 | 角色文风与专业方法叙述 |
| 系统提示词 | 稳定身份、职责边界、安全约束、输出格式 | 可频繁迭代的专业步骤和工具清单 |
| 核心 Skill | 分析步骤、工具策略、证据门槛、复核清单、降级处置 | 改写硬规则和公共协议 |

冲突优先级固定为：`确定性代码 > 系统提示词 > 核心 Skill > 本轮案件上下文`。

## 3. 固定绑定

| Agent | 核心 Skill 包 | 第一版职责 |
|---|---|---|
| Forensics | 多模态电子取证 Skill | 检材观察、工具矩阵、证据融合、限制与补证 |
| OSINT | 情报溯源与证据图谱 Skill | 查询设计、来源核验、实体关系、引用与图谱质量 |
| Challenger | 证据质询与收敛控制 Skill | 阶段审查、矛盾定位、补证建议、残留风险与放行依据 |
| Commander | 研判指挥与协同编排 Skill | 最终裁决、协同主持、脱敏经验提炼 |

Commander 包内包含三个显式工作流：

1. `final_adjudication`：综合评分、证据链解释、分歧处置和最终建议；
2. `human_collaboration`：求助点去重、专家任务整理、协同摘要与回注；
3. `experience_distillation`：从已结束协同中生成脱敏经验草稿。

工作流由现有明确调用点选择，不经过动态 Skill 路由器。

## 4. Skill 契约

每个 Skill 目录包含一个人类可读的 `SKILL.md`。当前 frontmatter 包含：

```yaml
name: multimodal-forensics
version: 1.0.0
schema_version: 1
agent: forensics
workflows: [primary_analysis]
```

正文固定描述：适用场景、输入边界、标准步骤、允许工具、证据门槛、禁止事项、输出要求、自检清单和降级策略。加载器只接受白名单字段，并计算内容摘要用于审计；Skill 不携带密钥、任意 Python 或任意 Shell。

## 5. 运行时状态与降级语义

为每个 Agent 结果附加 `skill_execution`，并明确区分“文件加载”“方法注入执行”“输出检查”三个事实：

```json
{
  "skill_name": "multimodal-forensics",
  "skill_version": "1.0.0",
  "workflow": "primary_analysis",
  "load_status": "loaded",
  "execution_status": "applied",
  "content_digest": "sha256:...",
  "contract_checks": ["required_report_sections"],
  "check_results": [
    {"name": "required_report_sections", "status": "passed", "details": []}
  ],
  "limitations": []
}
```

`load_status` 允许值：

- `loaded`：契约通过校验并注入本轮上下文；
- `degraded`：Skill 存在但读取、版本或结构校验失败；
- `not_loaded`：未找到绑定的 Skill。

`execution_status` 允许值：

- `pending`：已加载，尚未完成模型调用与输出检查；
- `applied`：Skill 内容确实注入本轮调用，且已完成代码侧检查；
- `check_failed`：已注入，但一个或多个代码侧检查未通过；
- `skipped`：未加载、加载失败，或 LLM 已降级而无法证明本轮真实采用了 Skill。

当 `load_status` 不是 `loaded`：

- Agent 继续使用现有系统提示词和确定性代码；
- SSE 日志、审计事件与最终报告必须明确记录原因；
- 不生成“采用了某 Skill”或等价表述；
- 不把 Skill 降级误写成 LLM、API 或分析成功。

## 6. 注入与校验边界

加载器在 Agent 调用 LLM 前完成解析和校验，只把当前 Agent、当前工作流需要的 Skill 片段注入上下文。Forensics、OSINT、Challenger 和 Commander 最终裁决会检查各自必需 Markdown 章节真实存在、唯一、顺序正确且正文非空；Commander 最终裁决还要求四分类唯一，并与 Python 确定性裁决一致。最终裁决值会作为硬规则显式注入，并由 Python 覆盖报告的结论章节，LLM 只负责证据解释。Commander 综合置信度同样只有一个权威值：由各 Agent 置信度乘动态权重后求和；报告上方显示该值，下方“置信度与证据链”由 Python 写入同值及逐项计算过程，LLM 不得引用 `forensics_score` 或生成第二套综合置信度。协同主持和经验提炼先把模型常见的安全结构漂移归一化为系统实际持久化、消费的公开合同，再对该规范产物执行检查；经验草稿第一次出现可修复的字段缺失或类型漂移时，会携带完整字段合同自动纠正重试一次，重试后仍无效的条目继续明确记为检查失败，不能静默伪装成空结果。所有路径都依据显式 LLM 调用状态判断是否具备“实际采用”的证据；LLM 初始化失败、调用降级或格式回退时，即使本地结果符合格式，也只能记为 `skipped`，且不得声称 LLM 可用。案件字段会先序列化并转义，再置于低于 Skill 的统一数据边界中。更深入的引用覆盖、工具状态真实性与业务语义检查仍可继续扩充。

系统必须分别记录 `load_status`、`execution_status` 和逐项 `check_results`，避免把成功读取文件等同于成功执行方法。只有 `load_status=loaded`、`execution_status=applied` 且约定检查通过时，界面或报告才可写“本轮采用了该 Skill”；其余状态只能陈述降级或检查失败事实。

## 7. 产品可见性

- Agent 卡片：显示绑定 Skill 名称和版本，并明确标注“固定绑定”，不把设计能力冒充本轮执行结果；
- 实时日志：显示加载、工作流、检查和降级事件；
- 最终报告：Skill 执行摘要矩阵只读取分析快照和协同会话中实际持久化的状态、版本、工作流、检查结果和限制；旧任务缺少元数据时明确写“无法核验”，不从静态绑定反推执行成功；
- 审计日志：保存内容摘要与状态，便于复现，不保存完整敏感上下文。

## 8. 验收与对照评测

当前离线测试已经覆盖：

- 四个绑定与 schema 校验；
- 前端公开绑定清单与后端 Skill 名称、版本的跨端一致性；
- 正常加载、缺失、损坏、版本不兼容；
- 系统提示词、Skill 与案件上下文的注入优先级；
- Forensics 日志、审计、结果和报告降级字段；
- Commander 三工作流的显式选择；
- Commander 四分类唯一性、确定性裁决一致性，以及协同确认后元数据保留；
- Skill 未加载及 LLM 降级时不出现“已采用 Skill”表述；
- 伪造的行内标题、未实现检查器和本地降级报告不能被误判为 `applied`。

尚待运行真实 Kimi 对照评测；运行时接入、产品可见性与基础输出契约已经纳入离线测试。

发布前手动运行真实 Kimi 对照评测：同一组固定案件快照分别以“仅系统提示词”和“系统提示词 + Skill”运行，比较输出契约完整率、证据引用覆盖、降级误报、Challenger 打回质量与最终裁决一致性。模型主观评分不能作为唯一指标，真实 API 调用不设为 CI 必选项。

## 9. 分阶段实施进度

1. [x] 定义 Skill schema、四 Agent 固定绑定表与只读加载器；
2. [x] 为 Forensics 做端到端试点，验证加载、注入、检查、日志、审计、结果和降级；
3. [x] 接入 OSINT、Challenger 及 Commander 三工作流，并实现各自基础代码侧输出检查；
4. [x] 增加 Agent 卡片固定绑定铭牌和最终报告实际执行矩阵；
5. [ ] 扩充离线 fixtures，并在人工开启时运行真实 Kimi on/off 对照；
6. [ ] 完成固定绑定闭环后再评估动态 Skill 选择，不预留未经验证的自动路由行为。
