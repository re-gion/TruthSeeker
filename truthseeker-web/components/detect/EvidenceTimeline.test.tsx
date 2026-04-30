// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { EvidenceTimeline } from "./EvidenceTimeline"

describe("EvidenceTimeline", () => {
  it("does not render generic flow badges and only shows one audit badge", () => {
    render(
      <EvidenceTimeline
        isComplete={false}
        logs={[
          {
            agent: "forensics",
            type: "finding",
            content: "取证完成",
            timestamp: "2026-04-21T08:00:00.000Z",
            round: 1,
          },
          {
            agent: "system",
            type: "audit",
            content: "task_created",
            timestamp: "2026-04-21T08:00:01.000Z",
            sourceKind: "audit",
          },
        ]}
      />,
    )

    expect(screen.queryByText(/^流程/)).not.toBeInTheDocument()
    expect(screen.getAllByText("审计")).toHaveLength(1)
  })

  it("renders R separators only between real challenger question rounds", () => {
    render(
      <EvidenceTimeline
        isComplete={false}
        logs={[
          {
            agent: "challenger",
            type: "phase_review",
            content: "第一轮正常质询",
            timestamp: "2026-04-21T08:00:00.000Z",
            phase: "forensics",
            phaseRound: 1,
          },
          {
            agent: "forensics",
            type: "finding",
            content: "普通第二轮日志",
            timestamp: "2026-04-21T08:00:01.000Z",
            round: 2,
          },
          {
            agent: "challenger",
            type: "phase_review",
            content: "第二轮真实质询",
            timestamp: "2026-04-21T08:00:02.000Z",
            phase: "forensics",
            phaseRound: 2,
          },
        ]}
      />,
    )

    expect(screen.queryByText("R1")).not.toBeInTheDocument()
    expect(screen.getByText("R2")).toBeInTheDocument()
    expect(screen.queryByText(/^流程/)).not.toBeInTheDocument()
  })

  it("marks cross-stage evidence supplementation distinctly", () => {
    render(
      <EvidenceTimeline
        isComplete={false}
        logs={[
          {
            agent: "challenger",
            type: "evidence_supplement",
            action: "cross_phase_evidence_supplement",
            content: "跨阶段补充公开来源截图",
            timestamp: "2026-04-21T08:00:00.000Z",
            sourceKind: "timeline",
          },
        ]}
      />,
    )

    expect(screen.getByText("跨阶段补证")).toBeInTheDocument()
  })
})
