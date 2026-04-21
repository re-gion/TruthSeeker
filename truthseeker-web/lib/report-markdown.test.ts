import { describe, expect, it } from "vitest"

import { renderReportMarkdown } from "./report-markdown"

describe("shared report markdown rendering", () => {
  it("renders markdown tables as accessible html tables and escapes cell content", () => {
    const html = renderReportMarkdown(`
## 权重

| Agent | 权重 |
|---|---|
| Forensics | 45% |
| <script>bad</script> | 30% |
`)

    expect(html).toContain("<table>")
    expect(html).toContain("<th>Agent</th>")
    expect(html).toContain("<td>Forensics</td>")
    expect(html).toContain("&lt;script&gt;bad&lt;/script&gt;")
    expect(html).not.toContain("<script>")
  })
})
