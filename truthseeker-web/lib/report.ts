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

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
    return typeof value === "object" && value !== null
}

function readValue(record: UnknownRecord, keys: string[]): unknown {
    for (const key of keys) {
        if (key in record) return record[key]
    }
    return undefined
}

function readString(record: UnknownRecord, keys: string[], fallback = ""): string {
    const value = readValue(record, keys)
    if (typeof value === "string" && value.trim()) return value
    if (typeof value === "number" || typeof value === "boolean") return String(value)
    return fallback
}

function readNumber(record: UnknownRecord, keys: string[], fallback = 0): number {
    const value = readValue(record, keys)
    if (typeof value === "number" && Number.isFinite(value)) return value
    if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number(value)
        if (Number.isFinite(parsed)) return parsed
    }
    return fallback
}

function readBoolean(record: UnknownRecord, keys: string[], fallback = false): boolean {
    const value = readValue(record, keys)
    if (typeof value === "boolean") return value
    if (typeof value === "string") return value === "true"
    return fallback
}

function normalizeTextList(value: unknown): string[] {
    if (!Array.isArray(value)) return []

    return value
        .map((item) => {
            if (typeof item === "string") return item
            if (typeof item === "number" || typeof item === "boolean") return String(item)
            if (isRecord(item)) {
                const label = readString(item, ["label", "text", "content", "title", "summary", "source", "name"], "")
                const confidence = readValue(item, ["confidence", "score"])
                const confidenceText = typeof confidence === "number" ? ` (${(confidence * 100).toFixed(1)}%)` : ""
                if (label) return `${label}${confidenceText}`
                try {
                    return JSON.stringify(item)
                } catch {
                    return ""
                }
            }
            return ""
        })
        .filter((item): item is string => item.trim().length > 0)
}

export function extractVerdictSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    const verdict = readString(record, ["verdict", "verdict_value", "label"], "inconclusive")
    const verdictLabel = readString(record, ["verdict_label", "verdict_cn", "label", "title"], verdict)
    const confidence = readNumber(record, ["confidence_overall", "confidence", "score"], 0)
    const evidence = normalizeTextList(readValue(record, ["key_evidence", "evidence", "keyEvidence"]))

    return {
        verdict,
        verdictLabel,
        confidence,
        evidence,
    }
}

export function extractAnalysisSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    return {
        verdict: readString(record, ["verdict", "result", "label"], "unknown"),
        analysisSummary: readString(record, ["analysis_summary", "llm_analysis", "summary", "analysis"], ""),
        confidence: readNumber(record, ["confidence_overall", "confidence", "score"], 0),
    }
}

export function extractChallengerSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    return {
        qualityScore: readNumber(record, ["quality_score", "confidence", "score"], 0),
        requiresMoreEvidence: readBoolean(record, ["requires_more_evidence", "needs_more_evidence"], false),
        challenges: normalizeTextList(readValue(record, ["challenges", "issues_found", "issues", "findings"])),
    }
}

function formatSectionItemList(items: string[]) {
    return items.map((item, index) => `${index + 1}. ${item}`).join("\n")
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
        const verdict = extractVerdictSnapshot(data.finalVerdict)
        const emoji = verdictEmoji[verdict.verdict] || "❓"
        md += `**结论**: ${emoji}  \n`
        md += `**判定标签**: ${verdict.verdictLabel || "-"}  \n`
        md += `**综合置信度**: ${(verdict.confidence * 100).toFixed(1)}%  \n\n`
        if (verdict.evidence.length > 0) {
            md += `### 关键证据\n\n`
            md += `${formatSectionItemList(verdict.evidence)}\n`
            md += `\n`
        }
    } else {
        md += `_检测尚未完成，无最终裁决。_\n\n`
    }

    // ── 各 Agent 分析结果 ──
    md += `---\n\n## 🔬 电子取证Agent (Forensics Agent)\n\n`
    if (data.forensicsResult) {
        const forensics = extractAnalysisSnapshot(data.forensicsResult)
        md += `- **置信度**: ${(forensics.confidence * 100).toFixed(1)}%\n`
        md += `- **判定**: ${forensics.verdict || "-"}\n`
        if (forensics.analysisSummary) md += `- **摘要**: ${forensics.analysisSummary}\n`
        md += `\n`
    } else {
        md += `_暂无结果_\n\n`
    }

    md += `## 🕵️ 情报溯源Agent (OSINT Agent)\n\n`
    if (data.osintResult) {
        const osint = extractAnalysisSnapshot(data.osintResult)
        md += `- **置信度**: ${(osint.confidence * 100).toFixed(1)}%\n`
        md += `- **判定**: ${osint.verdict || "-"}\n`
        if (osint.analysisSummary) md += `- **摘要**: ${osint.analysisSummary}\n`
        md += `\n`
    } else {
        md += `_暂无结果_\n\n`
    }

    md += `## ⚖️ 逻辑质询Agent (Challenger Agent)\n\n`
    if (data.challengerFeedback) {
        const challenger = extractChallengerSnapshot(data.challengerFeedback)
        md += `- **质量评分**: ${(challenger.qualityScore * 100).toFixed(1)}%\n`
        md += `- **需要补充证据**: ${challenger.requiresMoreEvidence ? "是" : "否"}\n`
        if (challenger.challenges.length > 0) {
            md += `- **质疑点**:\n`
            md += `${challenger.challenges.map((challenge) => `  - ${challenge}`).join("\n")}\n`
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
                forensics: "电子取证Agent", osint: "情报溯源Agent", challenger: "逻辑质询Agent"
            }
            md += `| ${label[key] || key} | ${(val * 100).toFixed(1)}% |\n`
        })
        md += `\n`
    }

    // ── 完整日志 ──
    md += `---\n\n## 📜 完整检测日志\n\n`
    if (data.logs.length > 0) {
        const agentLabel: Record<string, string> = {
            forensics: "🔬 取证", osint: "🕵️ 情报", challenger: "⚖️ 质询", commander: "🏛️ 指挥"
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
type FetchLike = typeof fetch


export async function fetchCanonicalMarkdownReport(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
) {
    const resp = await fetchImpl(`${API_BASE}/api/v1/report/${taskId}/md`, {
        method: "GET",
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
    })
    if (!resp.ok) throw new Error(`Markdown 报告生成失败: ${resp.status}`)
    return resp.text()
}


export async function downloadCanonicalMarkdownReport(taskId: string, authToken?: string | null) {
    try {
        const markdown = await fetchCanonicalMarkdownReport(taskId, authToken)
        downloadMarkdownReport(markdown, `truthseeker-report-${taskId.slice(0, 8)}.md`)
    } catch (e) {
        console.error("Markdown download failed:", e)
        alert("Markdown 报告生成失败，请稍后重试")
    }
}

/** 从后端 API 下载 PDF 报告 */
export async function downloadPdfReport(taskId: string, authToken?: string | null) {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/report/${taskId}/pdf`, {
            method: "GET",
            headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
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
