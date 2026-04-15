"use client"

/**
 * 生成结构化 Markdown 检测报告
 * 用于 Phase 3.1.3 - 报告与导出
 */

interface ReportData {
    taskId: string
    inputType: string
    logs: Array<{ agent: string; content: string; timestamp?: string; type?: string; round?: number }>
    forensicsResult?: Record<string, unknown> | null
    osintResult?: Record<string, unknown> | null
    challengerFeedback?: Record<string, unknown> | null
    finalVerdict?: Record<string, unknown> | null
    agentWeights?: Record<string, number>
    currentRound?: number
}

export function generateMarkdownReport(data: ReportData): string {
    const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })
    const verdictEmoji: Record<string, string> = {
        forged: "🚨 伪造",
        suspicious: "⚠️ 可疑",
        authentic: "✅ 真实",
        inconclusive: "❓ 无法判定",
    }

    let md = `# TruthSeeker 深度伪造鉴定报告\n\n`
    md += `> 生成时间: ${now}  \n`
    md += `> 任务 ID: \`${data.taskId}\`  \n`
    md += `> 检测类型: ${data.inputType}  \n`
    md += `> 辩论轮数: ${data.currentRound || 0}\n\n`

    // ── 最终裁决 ──
    md += `---\n\n## 📋 最终裁决\n\n`
    if (data.finalVerdict) {
        const v = data.finalVerdict
        const emoji = verdictEmoji[(v.verdict as string) || "inconclusive"] || "❓"
        md += `**结论**: ${emoji}  \n`
        md += `**判定标签**: ${v.verdict_label || "-"}  \n`
        md += `**中文说明**: ${v.verdict_cn || "-"}  \n`
        md += `**综合置信度**: ${(((v.confidence_overall as number) || 0) * 100).toFixed(1)}%  \n\n`
        if (Array.isArray(v.key_evidence) && v.key_evidence.length > 0) {
            md += `### 关键证据\n\n`
                ; (v.key_evidence as string[]).forEach((e, i) => {
                    md += `${i + 1}. ${e}\n`
                })
            md += `\n`
        }
    } else {
        md += `_检测尚未完成，无最终裁决。_\n\n`
    }

    // ── 各 Agent 分析结果 ──
    md += `---\n\n## 🔬 视听鉴伪Agent (Forensics Agent)\n\n`
    if (data.forensicsResult) {
        const f = data.forensicsResult
        md += `- **置信度**: ${(((f.confidence as number) || 0) * 100).toFixed(1)}%\n`
        md += `- **判定**: ${f.verdict || "-"}\n`
        if (f.analysis_summary) md += `- **摘要**: ${f.analysis_summary}\n`
        md += `\n`
    } else {
        md += `_暂无结果_\n\n`
    }

    md += `## 🕵️ 情报溯源Agent (OSINT Agent)\n\n`
    if (data.osintResult) {
        const o = data.osintResult
        md += `- **置信度**: ${(((o.confidence as number) || 0) * 100).toFixed(1)}%\n`
        md += `- **判定**: ${o.verdict || "-"}\n`
        if (o.analysis_summary) md += `- **摘要**: ${o.analysis_summary}\n`
        md += `\n`
    } else {
        md += `_暂无结果_\n\n`
    }

    md += `## ⚖️ 逻辑质询Agent (Challenger Agent)\n\n`
    if (data.challengerFeedback) {
        const c = data.challengerFeedback
        md += `- **质量评分**: ${(((c.quality_score as number) || 0) * 100).toFixed(1)}%\n`
        md += `- **需要补充证据**: ${c.requires_more_evidence ? "是" : "否"}\n`
        if (Array.isArray(c.challenges) && c.challenges.length > 0) {
            md += `- **质疑点**:\n`
                ; (c.challenges as string[]).forEach((ch) => {
                    md += `  - ${ch}\n`
                })
        }
        md += `\n`
    } else {
        md += `_暂无结果_\n\n`
    }

    // ── 决策权重 ──
    if (data.agentWeights && Object.keys(data.agentWeights).length > 0) {
        md += `---\n\n## 📊 决策权重分布\n\n`
        md += `| Agent | 权重 |\n|---|---|\n`
        Object.entries(data.agentWeights).forEach(([key, val]) => {
            const label: Record<string, string> = {
                forensics: "视听鉴伪Agent", osint: "情报溯源Agent", challenger: "逻辑质询Agent"
            }
            md += `| ${label[key] || key} | ${(val * 100).toFixed(1)}% |\n`
        })
        md += `\n`
    }

    // ── 完整日志 ──
    md += `---\n\n## 📜 完整检测日志\n\n`
    if (data.logs.length > 0) {
        const agentLabel: Record<string, string> = {
            forensics: "🔬 法医", osint: "🕵️ 情报", challenger: "⚖️ 质询", commander: "🏛️ 指挥"
        }
        data.logs.forEach((log) => {
            const label = agentLabel[log.agent] || log.agent
            const time = log.timestamp ? `[${new Date(log.timestamp).toLocaleTimeString("zh-CN")}]` : ""
            md += `- ${time} **${label}**: ${log.content}\n`
        })
    } else {
        md += `_暂无日志_\n`
    }

    md += `\n---\n\n_本报告由 TruthSeeker AI 深度伪造鉴定系统自动生成_\n`
    return md
}

/** 触发浏览器下载 Markdown 文件 */
export function downloadMarkdownReport(content: string, filename: string) {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

/** 从后端 API 下载 PDF 报告 */
export async function downloadPdfReport(taskId: string) {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/report/${taskId}/pdf`, {
            method: "GET",
        })
        if (!resp.ok) throw new Error(`PDF 生成失败: ${resp.status}`)
        const blob = await resp.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `truthseeker-report-${taskId.slice(0, 8)}.pdf`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    } catch (e) {
        console.error("PDF download failed:", e)
        alert("PDF 报告生成失败，请稍后重试")
    }
}
