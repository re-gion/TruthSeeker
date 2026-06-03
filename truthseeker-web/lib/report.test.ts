import { describe, expect, it, vi } from "vitest"

import {
  downloadCanonicalMarkdownReportWithAuditLog,
  downloadPdfReportWithAuditLog,
  extractAnalysisSnapshot,
  extractVerdictSnapshot,
  fetchAuditLogMarkdown,
  fetchCanonicalMarkdownReport,
} from "./report"

describe("report snapshot normalization", () => {
  it("maps tool-level AIGC verdict aliases without falling back to inconclusive", () => {
    expect(extractVerdictSnapshot({ verdict: "AI_GENERATED", confidence: 0.98 })).toMatchObject({
      verdict: "suspicious",
      verdictLabel: "疑似 AIGC",
      confidence: 0.98,
    })
    expect(extractAnalysisSnapshot({ result: "synthetic", ai_generated_probability: 0.88 })).toMatchObject({
      verdict: "suspicious",
      verdictLabel: "疑似 AIGC",
      confidence: 0.88,
    })
  })

  it("keeps legacy deepfake aliases high risk while using canonical verdict values", () => {
    expect(extractVerdictSnapshot({ verdict: "deepfake", confidence_overall: 0.91 })).toMatchObject({
      verdict: "forged",
      verdictLabel: "确认伪造",
      confidence: 0.91,
    })
  })
})

describe("canonical report downloads", () => {
  it("fetches markdown from the backend canonical report endpoint with auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "# 后端报告",
    })

    const markdown = await fetchCanonicalMarkdownReport("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 后端报告")
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/report/task-123/md", {
      method: "GET",
      headers: { Authorization: "Bearer jwt-token" },
    })
  })

  it("fetches complete audit-log markdown from the backend with auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "# 完整审计日志",
    })

    const markdown = await fetchAuditLogMarkdown("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 完整审计日志")
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/report/task-123/audit-log.md", {
      method: "GET",
      headers: { Authorization: "Bearer jwt-token" },
    })
  })

  it("retries audit-log markdown when the first request fails transiently", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, text: async () => "error" })
      .mockResolvedValueOnce({ ok: true, text: async () => "# 完整审计日志" })

    const markdown = await fetchAuditLogMarkdown("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 完整审计日志")
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("downloads both canonical markdown report and audit log", async () => {
    const createdUrls: string[] = []
    const clickedDownloads: string[] = []
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, text: async () => "# 后端报告" })
      .mockResolvedValueOnce({ ok: true, text: async () => "# 完整审计日志" })

    vi.spyOn(URL, "createObjectURL").mockImplementation(() => {
      const url = `blob:test-${createdUrls.length + 1}`
      createdUrls.push(url)
      return url
    })
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    vi.stubGlobal("document", {
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
      createElement: vi.fn(() => ({
        href: "",
        download: "",
        click() {
          clickedDownloads.push(this.download)
        },
      })),
    })

    await downloadCanonicalMarkdownReportWithAuditLog("task-123456789", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(clickedDownloads).toEqual([
      "truthseeker-report-task-123.md",
      "truthseeker-audit-log-task-123.md",
    ])
  })

  it("downloads both pdf report and audit log", async () => {
    const createdUrls: string[] = []
    const clickedDownloads: string[] = []
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(["pdf"], { type: "application/pdf" }) })
      .mockResolvedValueOnce({ ok: true, text: async () => "# 完整审计日志" })

    vi.spyOn(URL, "createObjectURL").mockImplementation(() => {
      const url = `blob:test-${createdUrls.length + 1}`
      createdUrls.push(url)
      return url
    })
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    vi.stubGlobal("document", {
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
      createElement: vi.fn(() => ({
        href: "",
        download: "",
        click() {
          clickedDownloads.push(this.download)
        },
      })),
    })

    await downloadPdfReportWithAuditLog("task-123456789", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/report/task-123456789/pdf", {
      method: "GET",
      headers: { Authorization: "Bearer jwt-token" },
    })
    expect(clickedDownloads).toEqual([
      "truthseeker-report-task-123.pdf",
      "truthseeker-audit-log-task-123.md",
    ])
  })
})
