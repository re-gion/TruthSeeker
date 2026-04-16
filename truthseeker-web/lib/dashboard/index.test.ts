import { describe, expect, it } from "vitest"

import {
  DASHBOARD_EXTERNAL_INSIGHTS,
  buildDashboardViewModel,
  calculateAverageResponseMs,
  isHighRiskVerdictAlias,
} from "./index"

describe("dashboard external insights", () => {
  it("keeps every authority module fully traceable", () => {
    expect(DASHBOARD_EXTERNAL_INSIGHTS.length).toBeGreaterThanOrEqual(4)

    for (const insight of DASHBOARD_EXTERNAL_INSIGHTS) {
      expect(insight.id).toEqual(expect.any(String))
      expect(insight.layer).toEqual(expect.any(String))
      expect(insight.moduleTitle).toEqual(expect.any(String))
      expect(insight.note).toEqual(expect.any(String))
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

describe("response time aggregation", () => {
  it("uses only valid completed tasks when calculating the average latency", () => {
    const average = calculateAverageResponseMs([
      {
        id: "task-1",
        status: "completed",
        response_ms: 120,
      },
      {
        id: "task-2",
        status: "completed",
        started_at: "2026-04-16T08:00:00.000Z",
        completed_at: "2026-04-16T08:00:00.240Z",
      },
      {
        id: "task-3",
        status: "completed",
        response_ms: 0,
      },
      {
        id: "task-4",
        status: "analyzing",
        response_ms: 300,
      },
      {
        id: "task-5",
        status: "completed",
        started_at: "2026-04-16T09:00:00.000Z",
        completed_at: null,
      },
    ])

    expect(average).toBe(180)
  })
})

describe("dashboard view model", () => {
  it("returns the planned shape and tolerates empty datasets", () => {
    const viewModel = buildDashboardViewModel({
      tasks: [],
      reports: [],
      consultationInvites: [],
      generatedAt: "2026-04-16T00:00:00.000Z",
    })

    expect(viewModel.generatedAt).toBe("2026-04-16T00:00:00.000Z")
    expect(viewModel.dataWarnings).toEqual([])
    expect(viewModel.kpis).toEqual({
      totalTasks: 0,
      highRiskTasks: 0,
      averageResponseMs: 0,
      completedToday: 0,
    })
    expect(viewModel.trendSeries.map((series) => series.id)).toEqual(
      expect.arrayContaining(["response-time", "daily-completions"]),
    )
    expect(viewModel.distributionSeries.map((series) => series.id)).toEqual(
      expect.arrayContaining(["threat-types", "task-status"]),
    )
    expect(viewModel.capabilityMetrics.map((metric) => metric.id)).toEqual(
      expect.arrayContaining(["reports-generated", "consultation-triggered"]),
    )
    expect(viewModel.externalInsights).toHaveLength(DASHBOARD_EXTERNAL_INSIGHTS.length)
  })

  it("prefers task results, falls back to reports, and counts completed-today in Asia/Shanghai", () => {
    const viewModel = buildDashboardViewModel({
      generatedAt: "2026-04-16T15:00:00.000Z",
      tasks: [
        {
          id: "task-1",
          status: "completed",
          input_type: "video",
          result: { verdict: "forged", threat_type: "政要人物换脸" },
          started_at: "2026-04-16T08:00:00.000Z",
          completed_at: "2026-04-16T08:00:00.300Z",
          created_at: "2026-04-16T07:55:00.000Z",
        },
        {
          id: "task-2",
          status: "completed",
          input_type: "audio",
          result: "{\"verdict\":\"authentic\"}",
          started_at: "2026-04-15T08:00:00.000Z",
          completed_at: "2026-04-15T08:00:00.100Z",
          created_at: "2026-04-15T07:55:00.000Z",
        },
        {
          id: "task-3",
          status: "analyzing",
          input_type: "text",
          created_at: "2026-04-16T10:00:00.000Z",
        },
      ],
      reports: [
        {
          task_id: "task-4",
          verdict: { verdict: "疑似" },
          generated_at: "2026-04-16T12:00:00.000Z",
        },
      ],
      consultationInvites: [
        {
          task_id: "task-1",
          status: "pending",
          created_at: "2026-04-16T11:00:00.000Z",
        },
        {
          task_id: "task-1",
          status: "accepted",
          created_at: "2026-04-16T12:00:00.000Z",
        },
      ],
    })

    expect(viewModel.kpis.totalTasks).toBe(3)
    expect(viewModel.kpis.highRiskTasks).toBe(2)
    expect(viewModel.kpis.completedToday).toBe(1)
    expect(viewModel.kpis.averageResponseMs).toBe(200)
    expect(viewModel.dataWarnings).toEqual([])
    expect(
      viewModel.distributionSeries.find((series) => series.id === "threat-types")?.items[0]?.label,
    ).toBe("政要人物换脸")
    expect(
      viewModel.capabilityMetrics.find((metric) => metric.id === "reports-generated")?.value,
    ).toBe(1)
    expect(
      viewModel.capabilityMetrics.find((metric) => metric.id === "consultation-triggered")?.value,
    ).toBe(1)
  })
})
