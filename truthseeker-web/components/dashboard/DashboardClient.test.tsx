// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { DashboardClient } from "./DashboardClient"
import { normalizeDashboardResponse } from "@/lib/dashboard"

vi.mock("@/components/dashboard/DashboardChart", () => ({
  DashboardChart: () => <div data-testid="dashboard-chart" />,
}))

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}))

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal("IntersectionObserver", IntersectionObserverMock)

describe("DashboardClient", () => {
  it("removes the old explanatory blocks and keeps the first two layers vertically stacked", () => {
    const viewModel = normalizeDashboardResponse(
      {
        generated_at: "2026-04-18T12:00:00.000Z",
        kpis: {
          total_tasks: 12,
          high_risk_tasks: 4,
          average_response_ms: 186,
          completed_today: 3,
        },
        trend_series: [
          {
            id: "daily-completions",
            title: "近7日完成任务量",
            unit: "件",
            points: [{ label: "04-18", value: 3 }],
          },
          {
            id: "response-time",
            title: "近7日平均响应时间",
            unit: "ms",
            points: [{ label: "04-18", value: 186 }],
          },
        ],
        threat_mix: [{ label: "政务短视频换脸", value: 3, share: 0.5 }],
        status_breakdown: [{ label: "已完成", value: 8, share: 0.66 }],
        evidence_mix: [{ label: "视觉证据", value: 4, share: 0.5 }],
        flow_sankey: {
          nodes: [{ name: "视频内容" }, { name: "帧级取证" }, { name: "高风险结论" }],
          links: [
            { source: "视频内容", target: "帧级取证", value: 3 },
            { source: "帧级取证", target: "高风险结论", value: 3 },
          ],
        },
        capability_metrics: [
          { id: "reports-generated", label: "已生成报告", value: 6, helper: "已入库的鉴定报告总量" },
          { id: "consultation-triggered", label: "会诊触发任务", value: 2, helper: "触发专家会诊的唯一任务数" },
          { id: "reports-covered", label: "报告覆盖任务", value: 5, helper: "已形成报告闭环的唯一任务数" },
        ],
      },
      "2026-04-18T00:00:00.000Z",
    )

    render(<DashboardClient viewModel={viewModel} />)

    expect(screen.queryByText("展示逻辑")).not.toBeInTheDocument()
    expect(screen.queryByText("数据说明")).not.toBeInTheDocument()
    expect(screen.queryByText("本页刻意不展示两类图")).not.toBeInTheDocument()
    expect(screen.queryByText("部分内部数据当前不可用")).not.toBeInTheDocument()

    expect(screen.getByText("证据类型分布")).toBeInTheDocument()
    expect(screen.getByText("证据流向")).toBeInTheDocument()
    expect(screen.getByTestId("risk-stack").className).toContain("flex-col")
    expect(screen.getByTestId("governance-stack").className).toContain("flex-col")
  })
})
