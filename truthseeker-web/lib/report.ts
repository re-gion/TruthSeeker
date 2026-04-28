"use client"

/**
 * 生成结构化 Markdown 检测报告
 * 用于 Phase 3.1.3 - 报告与导出
 */

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
