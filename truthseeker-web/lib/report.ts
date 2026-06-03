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

const VERDICT_ALIASES: Record<string, { verdict: string; label: string }> = {
    authentic: { verdict: "authentic", label: "内容真实" },
    real: { verdict: "authentic", label: "内容真实" },
    suspicious: { verdict: "suspicious", label: "高度可疑" },
    aigc: { verdict: "suspicious", label: "疑似 AIGC" },
    ai_generated: { verdict: "suspicious", label: "疑似 AIGC" },
    "ai-generated": { verdict: "suspicious", label: "疑似 AIGC" },
    synthetic: { verdict: "suspicious", label: "疑似 AIGC" },
    manipulated: { verdict: "suspicious", label: "疑似 AIGC" },
    generated: { verdict: "suspicious", label: "疑似 AIGC" },
    forged: { verdict: "forged", label: "确认伪造" },
    fake: { verdict: "forged", label: "确认伪造" },
    deepfake: { verdict: "forged", label: "确认伪造" },
    "deep fake": { verdict: "forged", label: "确认伪造" },
    inconclusive: { verdict: "inconclusive", label: "无法判定" },
    unknown: { verdict: "inconclusive", label: "无法判定" },
}

function normalizeVerdict(raw: string, rawLabel = "") {
    const key = raw.trim().toLowerCase()
    const normalized = VERDICT_ALIASES[key] || VERDICT_ALIASES[key.replace(/\s+/g, "_")]
    if (normalized) return normalized
    return { verdict: raw || "inconclusive", label: rawLabel || raw || "无法判定" }
}

export function extractVerdictSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    const rawVerdict = readString(record, ["verdict", "verdict_value", "label"], "inconclusive")
    const rawVerdictLabel = readString(record, ["verdict_label", "verdict_cn", "label", "title"], rawVerdict)
    const normalized = normalizeVerdict(rawVerdict, rawVerdictLabel)
    const confidence = readNumber(record, ["confidence_overall", "confidence", "score", "aigc_score", "aigc_probability", "ai_generated_probability", "deepfake_probability"], 0)
    const evidence = normalizeTextList(readValue(record, ["key_evidence", "evidence", "keyEvidence"]))

    return {
        verdict: normalized.verdict,
        verdictLabel: rawVerdictLabel && rawVerdictLabel !== rawVerdict ? rawVerdictLabel : normalized.label,
        confidence,
        evidence,
    }
}

export function extractAnalysisSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    const rawVerdict = readString(record, ["verdict", "result", "label"], "unknown")
    const normalized = normalizeVerdict(rawVerdict)
    return {
        verdict: normalized.verdict,
        verdictLabel: normalized.label,
        analysisSummary: readString(record, ["analysis_summary", "llm_analysis", "summary", "analysis"], ""),
        confidence: readNumber(record, ["confidence_overall", "confidence", "score", "aigc_score", "aigc_probability", "ai_generated_probability", "deepfake_probability"], 0),
    }
}

export function extractChallengerSnapshot(value: unknown) {
    const record = isRecord(value) ? value : {}
    return {
        qualityScore: readNumber(record, ["confidence", "quality_score", "score"], 0),
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

function requestOptions(authToken?: string | null): RequestInit {
    return {
        method: "GET",
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
    }
}

async function fetchTextWithRetry(
    url: string,
    errorLabel: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
    attempts = 3,
) {
    let lastStatus = 0
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        const resp = await fetchImpl(url, requestOptions(authToken))
        if (resp.ok) return resp.text()
        lastStatus = resp.status
        if (attempt < attempts && resp.status >= 500) {
            await Promise.resolve()
            continue
        }
        break
    }
    throw new Error(`${errorLabel}: ${lastStatus}`)
}

async function fetchPdfBlob(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
    attempts = 3,
) {
    let lastStatus = 0
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        const resp = await fetchImpl(`${API_BASE}/api/v1/report/${taskId}/pdf`, requestOptions(authToken))
        if (resp.ok) return resp.blob()
        lastStatus = resp.status
        if (attempt < attempts && resp.status >= 500) {
            await Promise.resolve()
            continue
        }
        break
    }
    throw new Error(`PDF 生成失败: ${lastStatus}`)
}

function downloadBlobFile(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}


export async function fetchCanonicalMarkdownReport(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
) {
    return fetchTextWithRetry(`${API_BASE}/api/v1/report/${taskId}/md`, "Markdown 报告生成失败", authToken, fetchImpl)
}

export async function fetchAuditLogMarkdown(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
) {
    return fetchTextWithRetry(`${API_BASE}/api/v1/report/${taskId}/audit-log.md`, "审计日志生成失败", authToken, fetchImpl)
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

export async function downloadCanonicalMarkdownReportWithAuditLog(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
) {
    try {
        const [markdown, auditLog] = await Promise.all([
            fetchCanonicalMarkdownReport(taskId, authToken, fetchImpl),
            fetchAuditLogMarkdown(taskId, authToken, fetchImpl),
        ])
        const shortId = taskId.slice(0, 8)
        downloadMarkdownReport(markdown, `truthseeker-report-${shortId}.md`)
        downloadMarkdownReport(auditLog, `truthseeker-audit-log-${shortId}.md`)
    } catch (e) {
        console.error("Markdown + audit log download failed:", e)
        alert("Markdown 报告或审计日志生成失败，请稍后重试")
    }
}

/** 从后端 API 下载 PDF 报告 */
export async function downloadPdfReport(taskId: string, authToken?: string | null, fetchImpl: FetchLike = fetch) {
    try {
        const blob = await fetchPdfBlob(taskId, authToken, fetchImpl)
        downloadBlobFile(blob, `truthseeker-report-${taskId.slice(0, 8)}.pdf`)
    } catch (e) {
        console.error("PDF download failed:", e)
        alert("PDF 报告生成失败，请稍后重试")
    }
}

/** 从后端 API 下载 PDF 报告，并附带完整 Markdown 审计日志 */
export async function downloadPdfReportWithAuditLog(
    taskId: string,
    authToken?: string | null,
    fetchImpl: FetchLike = fetch,
) {
    try {
        const pdfBlob = await fetchPdfBlob(taskId, authToken, fetchImpl)
        const auditLog = await fetchAuditLogMarkdown(taskId, authToken, fetchImpl)
        const shortId = taskId.slice(0, 8)
        downloadBlobFile(pdfBlob, `truthseeker-report-${shortId}.pdf`)
        downloadMarkdownReport(auditLog, `truthseeker-audit-log-${shortId}.md`)
    } catch (e) {
        console.error("PDF + audit log download failed:", e)
        alert("PDF 报告或审计日志生成失败，请稍后重试")
    }
}
