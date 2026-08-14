"use client"

import type { Components } from "react-markdown"

import { buildHeadingIdIndex } from "@/lib/report-toc"

/**
 * 给详细报告的 h2/h3 补上目录使用的同一批锚点 id。
 *
 * 只认 Markdown 源码行号：react-markdown 会在 hast 节点上带 `position`，
 * 按行号命中后，同名标题（例如多个「对最终研判的影响」）也能各自对上自己的 id。
 *
 * 缩进在列表项里的标题（质询时间线会整段引用上一轮分析，里面含 `### 自主情报推理`
 * 这类同名标题）不属于报告结构，既不进目录，也不发 id——否则它们会和顶层同名章节
 * 抢同一个锚点，产生重复 DOM id 并让目录跳错位置。
 */
export function createReportHeadingComponents(markdown: string, scrollOffset: number): Components {
  const index = buildHeadingIdIndex(markdown)

  const withAnchor = (Tag: "h2" | "h3") => {
    const Heading: Components[typeof Tag] = ({ node, children, ...props }) => {
      const line = node?.position?.start.line
      const id = line != null ? index.byLine.get(line) : undefined

      return (
        <Tag {...props} id={id} style={{ scrollMarginTop: `${scrollOffset}px` }}>
          {children}
        </Tag>
      )
    }
    return Heading
  }

  return { h2: withAnchor("h2"), h3: withAnchor("h3") }
}
