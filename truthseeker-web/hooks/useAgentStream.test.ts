import { describe, expect, it } from "vitest"

import { mapAgentHistoryToStreamState } from "./useAgentStream"

describe("mapAgentHistoryToStreamState", () => {
  it("restores persisted logs, snapshots, and completion state for invited experts", () => {
    const mapped = mapAgentHistoryToStreamState({
      task: { status: "completed" },
      agent_logs: [
        {
          agent_name: "forensics",
          log_type: "finding",
          content: "检测完成",
          timestamp: "2026-04-21T00:00:00.000Z",
          round_number: 1,
        },
      ],
      analysis_states: [
        {
          round_number: 1,
          evidence_board: {
            timeline_events: [
              {
                agent: "challenger",
                event_type: "phase_review",
                phase: "forensics",
                phase_round: 1,
                summary: "Forensics 第一轮质询",
                timestamp: "2026-04-21T00:00:01.000Z",
              },
            ],
          },
          result_snapshot: {
            forensics: { confidence: 0.71 },
            osint: { confidence: 0.62 },
            challenger: { quality_score: 0.8 },
          },
        },
      ],
      audit_logs: [
        {
          action: "task_created",
          agent: "system",
          created_at: "2026-04-20T23:59:59.000Z",
          metadata: { file_count: 2 },
        },
      ],
      report: {
        verdict_payload: {
          verdict: "suspicious",
          confidence: 0.74,
          agent_weights: { forensics: 0.5, osint: 0.5 },
        },
      },
    })

    expect(mapped.logs).toHaveLength(3)
    expect(mapped.logs[0]).toMatchObject({ agent: "system", type: "audit", sourceKind: "audit" })
    expect(mapped.logs[1]).toMatchObject({ agent: "forensics", type: "finding", content: "检测完成" })
    expect(mapped.logs[2]).toMatchObject({
      agent: "challenger",
      phase: "forensics",
      phaseRound: 1,
      sourceKind: "timeline",
    })
    expect(mapped.forensicsResult).toEqual({ confidence: 0.71 })
    expect(mapped.osintResult).toEqual({ confidence: 0.62 })
    expect(mapped.challengerFeedback).toEqual({ quality_score: 0.8 })
    expect(mapped.finalVerdict).toMatchObject({ verdict: "suspicious", confidence: 0.74 })
    expect(mapped.agentWeights).toEqual({ forensics: 0.5, osint: 0.5 })
    expect(mapped.isComplete).toBe(true)
    expect(mapped.isWaitingConsultation).toBe(false)
  })
})
