import { describe, expect, it } from "vitest"

import {
  canModerateConsultation,
  mapAgentHistoryToStreamState,
  normalizeConsultationEvent,
} from "./useAgentStream"

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

  it("uses timeline event summary as content and falls back to the persisted state timestamp", () => {
    const mapped = mapAgentHistoryToStreamState({
      task: { status: "running" },
      analysis_states: [
        {
          created_at: "2026-04-21T08:00:00.000Z",
          round_number: 2,
          evidence_board: {
            timeline_events: [
              {
                agent: "challenger",
                event_type: "phase_review",
                phase: "osint",
                phase_round: 2,
                summary: "第二轮溯源质询需要补证",
              },
            ],
          },
        },
      ],
    })

    expect(mapped.logs).toHaveLength(1)
    expect(mapped.logs[0]).toMatchObject({
      agent: "challenger",
      content: "第二轮溯源质询需要补证",
      timestamp: "2026-04-21T08:00:00.000Z",
      sourceKind: "timeline",
    })
  })

  it("deduplicates the same event when restored from audit, agent, and timeline rows", () => {
    const mapped = mapAgentHistoryToStreamState({
      task: { status: "running" },
      audit_logs: [
        {
          action: "task_created",
          agent: "system",
          created_at: "2026-04-21T08:00:00.000Z",
        },
      ],
      agent_logs: [
        {
          agent_name: "system",
          log_type: "audit",
          content: "task_created",
          timestamp: "2026-04-21T08:00:00.000Z",
        },
      ],
      analysis_states: [
        {
          created_at: "2026-04-21T08:00:00.000Z",
          evidence_board: {
            timeline_events: [
              {
                agent: "system",
                type: "audit",
                content: "task_created",
                timestamp: "2026-04-21T08:00:00.000Z",
              },
            ],
          },
        },
      ],
    })

    expect(mapped.logs).toHaveLength(1)
    expect(mapped.logs[0]).toMatchObject({
      agent: "system",
      type: "audit",
      content: "task_created",
      timestamp: "2026-04-21T08:00:00.000Z",
    })
  })
})

describe("consultation event helpers", () => {
  it("normalizes the new consultation SSE payload into a user-facing context", () => {
    const state = normalizeConsultationEvent({
      type: "consultation_approval_required",
      task_id: "task-1",
      reason: "核心证据冲突",
      payload: {
        context: {
          background: "疑似公开视频二次编辑",
          progress: "Challenger 已完成三轮质询",
          blockers: ["取证分数与溯源证据冲突"],
          help_needed: "请判断是否需要补充来源链路",
          sample_links: [
            { title: "样本 A", url: "https://example.invalid/a" },
            "https://example.invalid/b",
          ],
        },
        session: { id: "session-1" },
        summary_draft: "建议等待专家意见后再恢复裁决",
      },
    })

    expect(state.status).toBe("approval_required")
    expect(state.reason).toBe("核心证据冲突")
    expect(state.context.background).toBe("疑似公开视频二次编辑")
    expect(state.context.progress).toBe("Challenger 已完成三轮质询")
    expect(state.context.blockers).toEqual(["取证分数与溯源证据冲突"])
    expect(state.context.helpNeeded).toBe("请判断是否需要补充来源链路")
    expect(state.context.sampleLinks).toEqual([
      { label: "样本 A", url: "https://example.invalid/a" },
      { label: "样本 2", url: "https://example.invalid/b" },
    ])
    expect(state.summaryDraft).toBe("建议等待专家意见后再恢复裁决")
  })

  it("keeps moderation actions limited to the logged-in owner host role", () => {
    expect(canModerateConsultation("host")).toBe(true)
    expect(canModerateConsultation("expert")).toBe(false)
    expect(canModerateConsultation("viewer")).toBe(false)
  })
})
