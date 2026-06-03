# TruthSeeker Agent 交互与专家会诊说明

## 当前 Agent 拓扑

当前工作流是阶段式四 Agent：

`Forensics -> Challenger -> OSINT -> Challenger -> Commander -> Challenger -> END`

因此，Forensics、OSINT、Commander 每完成一个阶段都会进入 Challenger 质询。Challenger 并不是只在异常时触发；异常只决定是否打回重跑或触发专家会诊。

## 质询与打回条件

Challenger 会读取当前 `analysis_phase` 对应阶段的结果：

- Forensics 阶段：检查外部工具矩阵、工具失败/降级、取证置信度。
- OSINT 阶段：检查溯源图谱、引用覆盖率、模型推断比例、工具失败/降级。
- Commander 阶段：检查最终裁决枚举、最终图谱、处置建议，以及低证据质量下是否过度确定。

Challenger 的 `confidence` / `quality_score` 是对当前阶段输出质量的评分，不等于 Forensics 或 OSINT 自己给出的 `confidence`。例如 Forensics 可以认为自己取证置信度为 0.95，但 Challenger 因 VT 冲突、品牌未核验、域名溯源不足等问题把阶段质量评为 0.00。

打回条件主要包括：

- 当前阶段质询轮次少于 2 轮。
- LLM 质询建议 `requires_more_evidence=true`。
- 存在 high 严重度问题且阶段未稳定收敛。
- 未达到最大轮次；达到最大轮次后会保留残留风险并继续推进。

## 专家会诊触发条件

专家会诊由 Challenger 的连续质询记录触发。默认条件是：

- 最近多轮质询目标 Agent 一致。
- 最近多轮均存在 high 严重度问题。
- 当前 Challenger 置信度低于会诊阈值。
- 相邻质询轮次的置信度变化持续小于阈值，说明自动补证进入停滞。

首次满足条件时可自动进入会诊；后续重复触发通常需要用户审批或跳过。会诊意见会进入 Commander 的最终裁决上下文，但不会替代外部工具证据。

## 综合置信度口径

最终 `confidence_overall` 采用三 Agent 加权求和：

`Forensics confidence * Forensics weight + OSINT confidence * OSINT weight + Challenger confidence * Challenger weight`

Challenger 为 0 时，只表示它自身权重贡献为 0，不能把整体置信度乘成 0。例如：

`(0.95 * 0.45) + (0.82 * 0.30) + (0.00 * 0.25) = 0.674`

报告中如出现 OSINT 自身置信度，应称为“OSINT 溯源置信度”，不能写成最终综合置信度。

## 外部工具适配

- 图片 AIGC 检测默认使用 Sightengine `genai`。
- 音视频 deepfake 检测继续使用 Reality Defender。
- URL 与文件哈希威胁情报使用 VirusTotal；URL 扫描必须等待 `completed` 后才采信统计。
- 域名注册与 DNS 历史使用 WhoisXML；未配置 API Key 时只能写“域名溯源未启用/不可用”。
- 公开案例 RAG 只作为类案参考，不改变核心判定分数。
