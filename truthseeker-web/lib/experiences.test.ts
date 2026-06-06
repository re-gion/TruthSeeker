import { describe, expect, it, vi } from "vitest"

import {
  confirmExperienceDrafts,
  deleteExperience,
  getExperienceDetail,
  getExperienceList,
  normalizeExperienceEntry,
  normalizeExperienceList,
} from "./experiences"

describe("personal experience library mapping", () => {
  it("normalizes backend list payloads", () => {
    const result = normalizeExperienceList({
      items: [
        {
          id: "exp-1",
          source_task_id: "task-1",
          source_session_id: "session-1",
          title: "域名降级补证",
          target_agents: ["osint"],
          problem_pattern: "域名工具降级时缺少注册人与 DNS 历史。",
          recommended_method: "使用搜索结果和威胁情报交叉补证。",
          evidence_to_check: ["DNS 历史"],
          when_to_escalate: "外部来源全部不可用时再协同。",
          limitations: "搜索结果只能作为线索。",
          created_at: "2026-06-04T00:00:00+00:00",
          updated_at: "2026-06-04T00:00:00+00:00",
        },
      ],
      page: 2,
      page_size: 9,
      total: 19,
    })

    expect(result.items[0]).toMatchObject({
      id: "exp-1",
      target_agents: ["osint"],
      evidence_to_check: ["DNS 历史"],
    })
    expect(result.totalPages).toBe(3)
  })

  it("fills safe defaults for incomplete entries", () => {
    const entry = normalizeExperienceEntry({ id: "exp-2" })

    expect(entry.title).toBe("未命名个人经验")
    expect(entry.target_agents).toEqual([])
    expect(entry.evidence_to_check).toEqual([])
    expect(entry.created_at).toBeNull()
  })

  it("calls list/detail/confirm/delete endpoints with authenticated personal API shape", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], page: 1, page_size: 9, total: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "exp-1", title: "详情", target_agents: ["challenger"] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ inserted: 1, indexed_chunks: 1 }),
      })
      .mockResolvedValueOnce({ ok: true })

    await getExperienceList({ agent: "challenger", q: "钓鱼", page: 1, pageSize: 9 }, "token", fetchMock as unknown as typeof fetch)
    await getExperienceDetail("exp-1", "token", fetchMock as unknown as typeof fetch)
    await confirmExperienceDrafts({
      task_id: "task-1",
      session_id: "session-1",
      drafts: [{
        title: "钓鱼文本质询降噪",
        target_agents: ["challenger"],
        problem_pattern: "钓鱼痕迹明显时文本 AIGC 不应成为主要质询点。",
        recommended_method: "优先核验钓鱼语义、诱导动作和外链风险。",
        evidence_to_check: ["诱导动作"],
        when_to_escalate: "证据链无法闭合时会诊。",
        limitations: "不能替代事实核验。",
      }],
    }, "token", fetchMock as unknown as typeof fetch)
    await deleteExperience("exp-1", "token", fetchMock as unknown as typeof fetch)

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/v1/experiences?agent=challenger&q=%E9%92%93%E9%B1%BC&page=1&page_size=9", {
      cache: "no-store",
      headers: { Authorization: "Bearer token" },
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/v1/experiences/exp-1", {
      cache: "no-store",
      headers: { Authorization: "Bearer token" },
    })
    expect(fetchMock).toHaveBeenNthCalledWith(3, "http://localhost:8000/api/v1/experiences/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer token" },
      body: JSON.stringify({
        task_id: "task-1",
        session_id: "session-1",
        drafts: [{
          title: "钓鱼文本质询降噪",
          target_agents: ["challenger"],
          problem_pattern: "钓鱼痕迹明显时文本 AIGC 不应成为主要质询点。",
          recommended_method: "优先核验钓鱼语义、诱导动作和外链风险。",
          evidence_to_check: ["诱导动作"],
          when_to_escalate: "证据链无法闭合时会诊。",
          limitations: "不能替代事实核验。",
        }],
      }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(4, "http://localhost:8000/api/v1/experiences/exp-1", {
      method: "DELETE",
      headers: { Authorization: "Bearer token" },
    })
  })
})
