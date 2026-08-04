# TruthSeeker Domain Language

TruthSeeker 以可追溯证据为中心，组织多角色智能体完成恶意 AIGC 鉴伪、溯源、质询、裁决与人机协同。本词汇表统一产品、文档与后续 Agent + Skill 设计中的领域语言。

## Language

**Agent**:
在阶段式研判流程中承担一种稳定职责与决策边界的智能角色。
_Avoid_: Bot、模型实例、独立服务

**系统提示词**:
Agent 的稳定身份、职责边界、安全约束与输出契约。
_Avoid_: 完整能力包、Skill、业务流程脚本

**核心 Skill 包**:
固定绑定到一个 Agent、可版本化且可审计的专业方法契约；它定义该 Agent 如何运用证据完成职责，但不能改写系统硬规则。
_Avoid_: 额外提示词、动态插件、Prompt 模板

**Skill 工作流**:
核心 Skill 包中面向一种明确业务场景的具名能力路径；同一 Agent 可以拥有多个工作流，但仍只绑定一个核心 Skill 包。
_Avoid_: 动态 Skill、子 Agent

**Skill 执行证据**:
证明某个 Skill 版本在本轮被成功加载并实际使用的可见记录。
_Avoid_: 能力宣称、静态介绍

**Skill 降级**:
核心 Skill 未能加载或通过校验时，Agent 仅凭系统提示词继续运行且必须公开标记的状态。
_Avoid_: 已采用 Skill、正常执行

**确定性硬规则**:
不由模型或 Skill 改写的评分、路由、门槛与公共协议约束。
_Avoid_: 建议、最佳实践、模型判断

**研判指挥与协同编排 Skill**:
研判指挥 Agent 的固定核心 Skill 包，包含最终裁决、人机协同主持和脱敏经验提炼三个工作流。
_Avoid_: Commander 三个 Skill、动态 Skill 路由
