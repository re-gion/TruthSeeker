# TruthSeeker 宣传片事实依据

本文件用于约束 `truthseeker-promo.html` 的宣传文案，避免把未在报告或代码库中体现的能力写成已完成能力。

## 已确认素材

- 系统截图：来自 `D:\a311\系统赛\2026系统赛\信安项目文档与PPT\项目报告后期润色\插图\系统截图`
- Logo：来自 `truthseeker-web/components/logo`
- 报告：`2.8w字详细版-TruthSeeker项目报告0610.pdf`
- 仓库说明：`README.md`、`task.md`、`lessons.md`、前后端源码

## 可宣传卖点

1. TruthSeeker 面向跨模态恶意 AIGC 鉴伪、情报溯源与人机协同研判。
2. 系统不是单点检测器，而是将多模态证据、专业工具、OSINT、证据图谱、逻辑质询和人工专家回注串成可审计研判链路。
3. 当前运行拓扑为：电子取证 Agent -> Challenger -> OSINT -> Challenger -> Commander -> END。
4. Challenger 采用明确质量门槛：前 4 轮低于 0.8 必须打回，第 5 轮放行并写入残留风险。
5. 低置信停滞可触发人机协同，用户和外部专家意见可回流到后续裁决。
6. 报告侧支持 Markdown/PDF、审计日志、稳定 `report_hash` 和 provenance graph。
7. 公开案例库与个人经验库用于类案参考和经验复用，RAG 命中不能替代当前检材事实。
8. 项目报告给出面向评委的性能叙述：上层多智能体协同研判系统在 1000 条公开基准抽样样本上的总体准确率、精确率、召回率和 F1 分别为 91.9%、90.5%、92.0% 和 91.9%，平均处理耗时 166.6s。

## 需要克制表述

- 仓库 README 明确指出：当前代码库采用 Fed-MBPR-compatible 运行时架构，仓库内没有独立 Fed-MBPR 训练服务。因此宣传片只写“Fed-MBPR-compatible / 底层检测器可替换 / 报告研究方向”，不把训练服务写成已上线运行模块。
- 外部工具如 Sightengine、Reality Defender、VirusTotal、Exa、WhoisXML 可能结构化降级；宣传片不写“所有外部工具必定成功”。
- 公开案例 RAG 与个人经验 RAG 是参考/checklist，不是当前任务事实来源。

## 45 秒叙事主线

1. 0-7s：恶意 AIGC 从单点伪造变成跨模态复合攻击。
2. 7-15s：TruthSeeker 不是另一个检测按钮，而是一条可信研判链。
3. 15-25s：四类 Agent 串联，Challenger 质询让结论经得起追问。
4. 25-33s：人机协同与专家意见进入主推理链路。
5. 33-40s：证据图谱、审计日志、报告 hash 与案例/经验沉淀形成闭环。
6. 40-45s：Logo 收束，口号为“让每一次判断，都能追溯到证据。”
