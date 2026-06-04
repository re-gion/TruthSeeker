import { describe, expect, it, vi } from "vitest"

import {
  downloadCanonicalMarkdownReportWithAuditLog,
  downloadPdfReport,
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

  it("retries canonical markdown when the report row is not readable on the first request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, text: async () => "报告尚未生成" })
      .mockResolvedValueOnce({ ok: true, text: async () => "# 后端报告" })

    const markdown = await fetchCanonicalMarkdownReport("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 后端报告")
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("retries audit-log markdown when fetch rejects transiently", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ ok: true, text: async () => "# 完整审计日志" })

    const markdown = await fetchAuditLogMarkdown("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 完整审计日志")
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("retries pdf download when fetch rejects transiently", async () => {
    const clickedDownloads: string[] = []
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(["pdf"], { type: "application/pdf" }) })

    vi.spyOn(URL, "createObjectURL").mockImplementation(() => "blob:pdf")
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

    await downloadPdfReport("task-123456789", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(clickedDownloads).toEqual(["truthseeker-report-task-123.pdf"])
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
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(["audit pdf"], { type: "application/pdf" }) })

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
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/report/task-123456789/audit-log.pdf", {
      method: "GET",
      headers: { Authorization: "Bearer jwt-token" },
    })
    expect(clickedDownloads).toEqual([
      "truthseeker-report-task-123.pdf",
      "truthseeker-audit-log-task-123.pdf",
    ])
  })

  it("defers blob URL revocation until after the browser starts the download", async () => {
    vi.useFakeTimers()
    const revokedUrls: string[] = []
    const clickedDownloads: string[] = []
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, blob: async () => new Blob(["pdf"], { type: "application/pdf" }) })

    vi.spyOn(URL, "createObjectURL").mockImplementation(() => "blob:large-pdf")
    vi.spyOn(URL, "revokeObjectURL").mockImplementation((url) => {
      revokedUrls.push(url)
    })
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

    await downloadPdfReport("task-123456789", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(clickedDownloads).toEqual(["truthseeker-report-task-123.pdf"])
    expect(revokedUrls).toEqual([])

    vi.runAllTimers()
    expect(revokedUrls).toEqual(["blob:large-pdf"])
    vi.useRealTimers()
  })

  it("keeps the pdf download when the audit-log request fails", async () => {
    const clickedDownloads: string[] = []
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(["pdf"], { type: "application/pdf" }) })
      .mockRejectedValue(new TypeError("Failed to fetch"))

    vi.spyOn(URL, "createObjectURL").mockImplementation(() => "blob:pdf")
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    vi.stubGlobal("alert", vi.fn())
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

    expect(clickedDownloads).toEqual(["truthseeker-report-task-123.pdf"])
    expect(globalThis.alert).toHaveBeenCalledWith("审计日志生成失败，请稍后重试")
  })
})
