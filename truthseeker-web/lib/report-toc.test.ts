import { describe, expect, it } from "vitest"

import {
  REPORT_SECTION_IDS,
  buildHeadingIdIndex,
  buildReportToc,
  slugifyHeadingText,
} from "./report-toc"

describe("slugifyHeadingText", () => {
  it("keeps CJK characters so Chinese headings stay addressable", () => {
    // 顿号属于标点，折叠成连字符；中文本体必须保留，否则中文标题会退化成空 slug
    expect(slugifyHeadingText("一、任务信息")).toBe("一-任务信息")
    expect(slugifyHeadingText("Agent Skill 执行摘要")).toBe("agent-skill-执行摘要")
  })

  it("drops emoji, markdown emphasis and punctuation noise", () => {
    expect(slugifyHeadingText("⚠️ 降级状态汇总")).toBe("降级状态汇总")
    expect(slugifyHeadingText("**逻辑质询**Agent ↔ `电子取证` Agent 第 1 轮")).toBe(
      "逻辑质询agent-电子取证-agent-第-1-轮",
    )
  })

  it("returns an empty string when nothing addressable remains", () => {
    expect(slugifyHeadingText("⚠️ ↔ ——")).toBe("")
  })
})

describe("buildReportToc", () => {
  const markdown = [
    "# TruthSeeker 跨模态鉴伪与溯源分析最终裁决报告",
    "",
    "## 一、任务信息",
    "",
    "| 项目 | 内容 |",
    "|---|---|",
    "",
    "## 八、人机协同",
    "",
    "### 协同轮次 1",
    "",
    "### 对最终研判的影响",
    "",
    "## 九、建议与说明",
    "",
    "### 对最终研判的影响",
    "",
  ].join("\n")

  it("puts page anchors and markdown h2 on the same depth and indents h3", () => {
    const entries = buildReportToc({ markdown, hasSummary: true })

    expect(entries.map((entry) => [entry.text, entry.depth, entry.kind])).toEqual([
      ["裁决结论", 0, "page"],
      ["最终裁决报告", 0, "page"],
      ["详细分析报告", 0, "page"],
      ["一、任务信息", 0, "heading"],
      ["八、人机协同", 0, "heading"],
      ["协同轮次 1", 1, "heading"],
      ["对最终研判的影响", 1, "heading"],
      ["九、建议与说明", 0, "heading"],
      ["对最终研判的影响", 1, "heading"],
    ])
  })

  it("uses the shared section ids for page anchors and unique ids for headings", () => {
    const entries = buildReportToc({ markdown, hasSummary: true })

    expect(entries.slice(0, 3).map((entry) => entry.id)).toEqual([
      REPORT_SECTION_IDS.verdict,
      REPORT_SECTION_IDS.summary,
      REPORT_SECTION_IDS.detail,
    ])
    expect(new Set(entries.map((entry) => entry.id)).size).toBe(entries.length)
    // 同名小节必须靠后缀区分，否则锚点互相抢占
    expect(entries.filter((entry) => entry.text === "对最终研判的影响").map((entry) => entry.id)).toEqual([
      "report-对最终研判的影响",
      "report-对最终研判的影响-2",
    ])  })

  it("omits the summary anchor when the ruling summary is absent", () => {
    const entries = buildReportToc({ markdown, hasSummary: false })

    expect(entries.map((entry) => entry.id)).not.toContain(REPORT_SECTION_IDS.summary)
    expect(entries[0].id).toBe(REPORT_SECTION_IDS.verdict)
    expect(entries[1].id).toBe(REPORT_SECTION_IDS.detail)
  })

  it("ignores h1 and headings inside fenced code blocks", () => {
    const withFence = [
      "# 报告标题",
      "",
      "```text",
      "## 伪装成标题的日志行",
      "```",
      "",
      "~~~",
      "### 另一种围栏内的标题",
      "~~~",
      "",
      "## 真实章节",
      "",
      "#### 四级标题不收录",
      "",
    ].join("\n")

    const entries = buildReportToc({ markdown: withFence, hasSummary: false })

    expect(entries.filter((entry) => entry.kind === "heading").map((entry) => entry.text)).toEqual([
      "真实章节",
    ])
  })

  it("degrades to the verdict anchor only when there is no markdown", () => {
    expect(buildReportToc({ markdown: "", hasSummary: false })).toEqual([
      { id: REPORT_SECTION_IDS.verdict, text: "裁决结论", depth: 0, kind: "page" },
    ])
  })

  it("never lets a heading slug collide with a page-anchor id", () => {
    // 标题正好叫「section verdict」时 slug 会撞上页面锚点，必须让位
    const collide = ["## section verdict", "", "## 正常章节", ""].join("\n")
    const entries = buildReportToc({ markdown: collide, hasSummary: false })
    const ids = entries.map((entry) => entry.id)

    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.filter((id) => id === REPORT_SECTION_IDS.verdict)).toHaveLength(1)
  })
})

describe("buildHeadingIdIndex", () => {
  const markdown = ["## 一、任务信息", "", "### 细节", "", "## 一、任务信息", ""].join("\n")

  it("maps source line numbers to the same ids the toc uses", () => {
    const index = buildHeadingIdIndex(markdown)
    const entries = buildReportToc({ markdown, hasSummary: false })
    const headingIds = entries.filter((entry) => entry.kind === "heading").map((entry) => entry.id)

    expect(index.byLine.get(1)).toBe(headingIds[0])
    expect(index.byLine.get(3)).toBe(headingIds[1])
    expect(index.byLine.get(5)).toBe(headingIds[2])
  })

  it("skips indented headings quoted inside list items", () => {
    // 质询时间线会把上一轮分析整段缩进引用，其中的 ### 标题不是报告结构，
    // 必须没有 id，否则会和顶层同名章节抢锚点
    const quoted = ["## 六、逻辑质询时间线", "", "  - previous:", "", "      ### 自主情报推理", ""].join("\n")
    const index = buildHeadingIdIndex(quoted)

    expect(index.byLine.get(1)).toBe("report-六-逻辑质询时间线")
    expect(index.byLine.get(5)).toBeUndefined()
  })
})
