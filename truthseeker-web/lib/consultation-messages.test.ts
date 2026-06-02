import { describe, expect, it } from "vitest"

import { filterDisplayComments, mergeConsultationComments, normalizeConsultationMessage, type ConsultationComment } from "./consultation-messages"

describe("consultation message helpers", () => {
  it("deduplicates messages by id and lets the backend row replace a matching optimistic message", () => {
    const optimistic = {
      id: "temp-1",
      clientMessageId: "client-1",
      authorId: "host-1",
      role: "host" as const,
      text: "请看这条会诊意见",
      timestamp: "2026-04-30T08:00:00.000Z",
    }

    const backend = normalizeConsultationMessage({
      id: "row-1",
      client_message_id: "client-1",
      role: "user",
      expert_name: "host-1",
      message: "请看这条会诊意见",
      created_at: "2026-04-30T08:00:01.000Z",
    })

    const merged = mergeConsultationComments([optimistic], [backend, backend])

    expect(merged).toHaveLength(1)
    expect(merged[0]).toMatchObject({
      id: "row-1",
      clientMessageId: "client-1",
      role: "host",
      text: "请看这条会诊意见",
    })
  })

  it("filterDisplayComments hides summary draft once summary_confirmed arrives", () => {
    const draftMsg: ConsultationComment = {
      id: "msg-1",
      authorId: "commander",
      role: "commander",
      text: "草稿摘要",
      timestamp: "2026-06-02T10:00:00.000Z",
      messageType: "summary",
    }
    const confirmedMsg: ConsultationComment = {
      id: "msg-2",
      authorId: "commander",
      role: "commander",
      text: "确认后摘要",
      timestamp: "2026-06-02T10:01:00.000Z",
      messageType: "summary_confirmed",
    }

    expect(filterDisplayComments([draftMsg])).toHaveLength(1)

    const filtered = filterDisplayComments([draftMsg, confirmedMsg])
    expect(filtered).toHaveLength(1)
    expect(filtered[0].messageType).toBe("summary_confirmed")
  })

  it("filterDisplayComments only hides summary from the matching session when sessionIds are present", () => {
    const draftA: ConsultationComment = {
      id: "draft-a",
      authorId: "commander",
      role: "commander",
      text: "session A 草稿",
      timestamp: "2026-06-02T10:00:00.000Z",
      messageType: "summary",
      sessionId: "session-a",
    }
    const confirmedA: ConsultationComment = {
      id: "confirmed-a",
      authorId: "commander",
      role: "commander",
      text: "session A 确认",
      timestamp: "2026-06-02T10:01:00.000Z",
      messageType: "summary_confirmed",
      sessionId: "session-a",
    }
    const draftB: ConsultationComment = {
      id: "draft-b",
      authorId: "commander",
      role: "commander",
      text: "session B 草稿",
      timestamp: "2026-06-02T10:02:00.000Z",
      messageType: "summary",
      sessionId: "session-b",
    }

    // confirmed of session-a 只过滤 session-a 的草稿，保留 session-b
    const filtered = filterDisplayComments([draftA, confirmedA, draftB])
    expect(filtered).toHaveLength(2)
    expect(filtered.some(c => c.id === "draft-a")).toBe(false)
    expect(filtered.some(c => c.id === "confirmed-a")).toBe(true)
    expect(filtered.some(c => c.id === "draft-b")).toBe(true)
  })
})
