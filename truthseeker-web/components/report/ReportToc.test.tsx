// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { ReportTocEntry } from "@/lib/report-toc"

import { ReportToc } from "./ReportToc"

const entries: ReportTocEntry[] = [
  { id: "report-section-verdict", text: "裁决结论", depth: 0, kind: "page" },
  { id: "report-一-任务信息", text: "一、任务信息", depth: 0, kind: "heading" },
  { id: "report-协同轮次-1", text: "协同轮次 1", depth: 1, kind: "heading" },
]

describe("ReportToc", () => {
  it("lists every entry and marks the active one", () => {
    render(
      <ReportToc entries={entries} activeId="report-一-任务信息" open onOpenChange={() => {}} />,
    )

    expect(screen.getByRole("navigation", { name: "报告目录" })).toBeInTheDocument()
    entries.forEach((entry) => {
      expect(screen.getByRole("button", { name: entry.text })).toBeInTheDocument()
    })
    expect(screen.getByRole("button", { name: "一、任务信息" })).toHaveAttribute("aria-current", "location")
    expect(screen.getByRole("button", { name: "裁决结论" })).not.toHaveAttribute("aria-current")
  })

  it("indents subsections deeper than main sections", () => {
    render(<ReportToc entries={entries} activeId={null} open onOpenChange={() => {}} />)

    expect(screen.getByRole("button", { name: "一、任务信息" }).className).toContain("pl-2.5")
    expect(screen.getByRole("button", { name: "协同轮次 1" }).className).toContain("pl-5")
  })

  it("collapses to a single reopen button that keeps the toc reachable", () => {
    const onOpenChange = vi.fn()
    render(<ReportToc entries={entries} activeId={null} open={false} onOpenChange={onOpenChange} />)

    expect(screen.queryByRole("navigation")).not.toBeInTheDocument()
    const opener = screen.getByRole("button", { name: "展开报告目录" })
    expect(opener).toHaveAttribute("aria-expanded", "false")

    fireEvent.click(opener)
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it("scrolls the clicked section into view and pins its highlight", () => {
    const onNavigate = vi.fn()
    const scrollIntoView = vi.fn()

    const target = document.createElement("div")
    target.id = "report-一-任务信息"
    target.scrollIntoView = scrollIntoView
    document.body.appendChild(target)

    render(
      <ReportToc
        entries={entries}
        activeId={null}
        open
        onOpenChange={() => {}}
        onNavigate={onNavigate}
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: "一、任务信息" }))

    // 用 scrollIntoView 而非自算像素：长报告滚动途中字体加载会让预算的落点漂移
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" })
    // 点击必须同时锁定高亮，否则平滑滚动落定前目录显示上一节
    expect(onNavigate).toHaveBeenCalledWith("report-一-任务信息")

    document.body.removeChild(target)
  })

  it("renders nothing when there are no entries", () => {
    const { container } = render(<ReportToc entries={[]} activeId={null} open onOpenChange={() => {}} />)

    expect(container).toBeEmptyDOMElement()
  })

  it("scrolls the toc list so the active entry stays visible", () => {
    const many: ReportTocEntry[] = Array.from({ length: 40 }, (_, index) => ({
      id: `report-章节-${index}`,
      text: `章节 ${index}`,
      depth: 0,
      kind: "heading",
    }))

    const { container } = render(
      <ReportToc entries={many} activeId="report-章节-39" open onOpenChange={() => {}} />,
    )

    const list = container.querySelector("ol")!
    // jsdom 的布局全为 0，这里只验证不抛错且 scrollTop 被写过（不是 NaN）
    expect(Number.isFinite(list.scrollTop)).toBe(true)
    expect(
      container.querySelector('[data-toc-id="report-章节-39"]')?.getAttribute("aria-current"),
    ).toBe("location")
  })
})
