import { describe, expect, it, vi } from "vitest"

import {
  createFallbackDashboardViewModel,
  DASHBOARD_EXTERNAL_INSIGHTS,
  getDashboardViewModel,
  isHighRiskVerdictAlias,
  normalizeDashboardResponse,
} from "./index"

describe("dashboard external insights", () => {
  it("keeps every authority module traceable and assigns a visual direction", () => {
    expect(DASHBOARD_EXTERNAL_INSIGHTS.length).toBeGreaterThanOrEqual(4)

    for (const insight of DASHBOARD_EXTERNAL_INSIGHTS) {
      expect(insight.id).toEqual(expect.any(String))
      expect(insight.layer).toEqual(expect.any(String))
      expect(insight.moduleTitle).toEqual(expect.any(String))
      expect(insight.summary).toEqual(expect.any(String))
      expect(insight.visualType).toEqual(expect.any(String))
      expect(insight.metrics.length).toBeGreaterThan(0)
      expect(insight.source.publisher).toEqual(expect.any(String))
      expect(insight.source.publishedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(insight.source.reportTitle).toEqual(expect.any(String))
      expect(insight.source.url).toMatch(/^https?:\/\//)
    }
  })
})

describe("high-risk verdict normalization", () => {
  it("recognizes the approved alias set and ignores safe verdicts", () => {
    expect(isHighRiskVerdictAlias("forged")).toBe(true)
    expect(isHighRiskVerdictAlias("deepfake")).toBe(true)
    expect(isHighRiskVerdictAlias("疑似")).toBe(true)
    expect(isHighRiskVerdictAlias("高风险")).toBe(true)
    expect(isHighRiskVerdictAlias("authentic")).toBe(false)
    expect(isHighRiskVerdictAlias("真实")).toBe(false)
  })
})

describe("dashboard response normalization", () => {
  it("maps the backend aggregate payload into the screen view model", () => {
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
            points: [
              { label: "04-12", value: 1 },
              { label: "04-13", value: 2 },
            ],
          },
          {
            id: "response-time",
            title: "近7日平均响应时间",
            unit: "ms",
            points: [
              { label: "04-12", value: 160 },
              { label: "04-13", value: 220 },
            ],
          },
        ],
        threat_mix: [
          { label: "政务短视频换脸", value: 3, share: 0.5 },
          { label: "语音冒充", value: 2, share: 0.333 },
        ],
        status_breakdown: [
          { label: "已完成", value: 8, share: 0.666 },
          { label: "分析中", value: 4, share: 0.333 },
        ],
        evidence_mix: [
          { label: "视觉证据", value: 4, share: 0.5 },
          { label: "音频证据", value: 2, share: 0.25 },
        ],
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
        data_warnings: [{ table: "reports", message: "reports 数据源读取失败" }],
      },
      "2026-04-18T00:00:00.000Z",
    )

    expect(viewModel.capabilityState).toBe("warning")
    expect(viewModel.dataWarnings).toEqual(["reports 数据源读取失败"])
    expect(viewModel.generatedAt).toBe("2026-04-18T12:00:00.000Z")
    expect(viewModel.kpis).toEqual({
      totalTasks: 12,
      highRiskTasks: 4,
      averageResponseMs: 186,
      completedToday: 3,
    })
    expect(viewModel.trendSeries.map((series) => series.id)).toEqual(["daily-completions", "response-time"])
    expect(viewModel.threatMix[0]?.label).toBe("政务短视频换脸")
    expect(viewModel.statusBreakdown[0]?.label).toBe("已完成")
    expect(viewModel.evidenceMix[0]?.label).toBe("视觉证据")
    expect(viewModel.flowSankey.links).toHaveLength(2)
    expect(viewModel.capabilityMetrics.map((metric) => metric.id)).toEqual([
      "reports-generated",
      "consultation-triggered",
      "reports-covered",
    ])
  })

  it("creates a compact fallback state when the aggregate interface is unavailable", () => {
    const viewModel = createFallbackDashboardViewModel("2026-04-18T00:00:00.000Z")

    expect(viewModel.capabilityState).toBe("error")
    expect(viewModel.kpis).toEqual({
      totalTasks: 0,
      highRiskTasks: 0,
      averageResponseMs: 0,
      completedToday: 0,
    })
    expect(viewModel.evidenceMix).toEqual([])
    expect(viewModel.flowSankey).toEqual({ nodes: [], links: [] })
  })
})

describe("dashboard data fetching", () => {
  it("falls back gracefully when the backend aggregate endpoint fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({}),
    })

    const viewModel = await getDashboardViewModel(fetchMock as unknown as typeof fetch)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(viewModel.capabilityState).toBe("error")
    expect(viewModel.externalInsights).toHaveLength(DASHBOARD_EXTERNAL_INSIGHTS.length)
  })
})
