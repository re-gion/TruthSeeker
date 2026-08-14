// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render } from "@testing-library/react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { describe, expect, it } from "vitest"

import { buildReportToc } from "@/lib/report-toc"

import { createReportHeadingComponents } from "./reportMarkdownComponents"

const markdown = [
  "# 报告",
  "",
  "## 八、人机协同",
  "",
  "### 对最终研判的影响",
  "",
  "## 九、建议与说明",
  "",
  "### 对最终研判的影响",
  "",
].join("\n")

describe("createReportHeadingComponents", () => {
  it("gives every heading the same id the toc links to, including duplicates", () => {
    const { container } = render(
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={createReportHeadingComponents(markdown, 80)}>
        {markdown}
      </ReactMarkdown>,
    )

    const renderedIds = [...container.querySelectorAll("h2, h3")].map((node) => node.id)
    const tocIds = buildReportToc({ markdown, hasSummary: false })
      .filter((entry) => entry.kind === "heading")
      .map((entry) => entry.id)

    expect(renderedIds).toEqual(tocIds)
    // 两个同名 h3 必须拿到不同锚点，否则第二个「对最终研判的影响」永远跳不到
    expect(new Set(renderedIds).size).toBe(renderedIds.length)
  })

  it("applies the scroll offset so anchors clear the sticky header", () => {
    const { container } = render(
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={createReportHeadingComponents(markdown, 80)}>
        {markdown}
      </ReactMarkdown>,
    )

    const heading = container.querySelector("h2")
    expect(heading).toHaveStyle({ scrollMarginTop: "80px" })
  })
})
