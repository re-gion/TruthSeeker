import { describe, expect, it } from "vitest"

import { mergeConsultationComments, normalizeConsultationMessage } from "./consultation-messages"

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
})
