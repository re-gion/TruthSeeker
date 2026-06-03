import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

describe("DetectConsole report buttons", () => {
  it("uses PDF report and audit-log wording and downloader", () => {
    const source = readFileSync(join(process.cwd(), "components/detect/DetectConsole.tsx"), "utf8")

    expect(source).toContain("PDF 报告与审计日志")
    expect(source).toContain("downloadPdfReportWithAuditLog")
  })
})
