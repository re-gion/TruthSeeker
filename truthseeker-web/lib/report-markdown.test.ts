import { describe, expect, it } from "vitest"

import { balanceCodeFences, renderReportMarkdown } from "./report-markdown"

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

describe("balanceCodeFences", () => {
  it("closes an unclosed backtick fence so later content is not swallowed", () => {
    const input = "正文\n```mermaid\nA --> B\n后续章节"
    const balanced = balanceCodeFences(input)
    const fences = balanced.split("```").length - 1
    expect(fences % 2).toBe(0)
    expect(balanced.endsWith("```")).toBe(true)
  })

  it("leaves already-balanced fences untouched", () => {
    const input = "正文\n```\ncode\n```\n结尾"
    expect(balanceCodeFences(input)).toBe(input)
  })

  it("handles tilde fences and info strings on the opening fence", () => {
    expect(balanceCodeFences("~~~\ncontent").endsWith("~~~")).toBe(true)
    expect(balanceCodeFences("```text\ncontent").endsWith("```")).toBe(true)
  })

  it("ignores fences indented more than 3 spaces", () => {
    const input = "正文\n    ```\n    缩进内容"
    expect(balanceCodeFences(input)).toBe(input)
  })

  it("returns plain text unchanged", () => {
    const input = "## 标题\n- 列表项\n没有代码块"
    expect(balanceCodeFences(input)).toBe(input)
  })

  it("closes an unclosed fence before the next heading so later sections are rescued", () => {
    const input = "```mermaid\nA --> B\n\n### 后续小节\n\n正文"
    const balanced = balanceCodeFences(input)
    const fenceLineCount = balanced.split("\n").filter((l) => /^```/.test(l.trim())).length
    expect(fenceLineCount).toBe(2)
    // 闭合围栏必须出现在标题行之前
    expect(balanced.indexOf("```", 3)).toBeLessThan(balanced.indexOf("### 后续小节"))
  })
})
