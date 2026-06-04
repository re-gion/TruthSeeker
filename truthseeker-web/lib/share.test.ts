import { describe, expect, it, vi } from "vitest"

import { createReportShareLink } from "./share"

describe("report sharing", () => {
  it("retries when the share endpoint has not observed the completed report yet", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: "报告尚未生成" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ share_url: "/report/share-token" }) })

    const url = await createReportShareLink("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(url).toBe("/report/share-token")
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith("http://localhost:8000/api/v1/share/task-123", {
      method: "POST",
      headers: { Authorization: "Bearer jwt-token" },
    })
  })
})
