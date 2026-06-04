import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

describe("DetectConsole report buttons", () => {
  it("uses PDF report and audit-log wording and downloader", () => {
    const source = readFileSync(join(process.cwd(), "components/detect/DetectConsole.tsx"), "utf8")

    expect(source).toContain("PDF 报告与审计日志")
    expect(source).toContain("downloadPdfReportWithAuditLog")
  })

  it("shows a per-action spinner and disables report actions while generating", () => {
    const source = readFileSync(join(process.cwd(), "components/detect/DetectConsole.tsx"), "utf8")

    expect(source).toContain("pendingReportAction")
    expect(source).toContain("Loader2")
    expect(source).toContain("animate-spin")
    expect(source).toContain('disabled={pendingReportAction !== null}')
    expect(source).toContain('pendingReportAction === "md"')
    expect(source).toContain('pendingReportAction === "pdf"')
    expect(source).toContain('pendingReportAction === "share"')
  })
})
