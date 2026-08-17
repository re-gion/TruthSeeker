// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render } from "@testing-library/react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { describe, expect, it } from "vitest"

import { balanceCodeFences } from "./report-markdown"

// 复现报告里「图谱关键节点与关系」小节的真实故障：LLM 用 ```mermaid 画图谱但
// 忘了闭合围栏（或被后端字段截断切掉闭合围栏），导致其后所有章节都被渲染进同一个
// 代码块（页面表现为荧光绿样式越界）。
const brokenReport = [
  "## 四、情报溯源 Agent 分析",
  "",
  "### 来源可信度与图谱质量",
  "",
  "图谱关键节点与关系如下：",
  "",
  "```mermaid",
  "A --> B",
  "B --> C",
  "",
  "### 关联风险与复核建议",
  "",
  "- 建议人工复核域名注册时间",
].join("\n")

function renderReport(markdown: string) {
  return render(
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>,
  )
}

describe("unclosed graph fence regression", () => {
  it("without balancing, everything after the fence is swallowed into one code block", () => {
    const { container } = renderReport(brokenReport)
    // 「关联风险与复核建议」不再是标题，而是落进了 <code>
    expect(container.querySelector("h3")?.textContent).not.toContain("关联风险与复核建议")
    expect(container.querySelector("code")?.textContent).toContain("关联风险与复核建议")
  })

  it("balanceCodeFences restores later sections to normal headings and lists", () => {
    const { container } = renderReport(balanceCodeFences(brokenReport))
    const headings = [...container.querySelectorAll("h3")].map((node) => node.textContent)
    expect(headings).toContain("关联风险与复核建议")
    // 后续列表不再被吞进代码块
    expect(container.querySelector("li")?.textContent).toContain("建议人工复核域名注册时间")
    const codeText = container.querySelector("code")?.textContent ?? ""
    expect(codeText).not.toContain("关联风险与复核建议")
  })
})
