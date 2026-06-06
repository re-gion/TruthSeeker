import { afterEach, describe, expect, it, vi } from "vitest"

import { createReportShareLink } from "./share"

describe("report sharing", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

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

  it("keeps retrying long enough for report persistence lag after completion", async () => {
    vi.useFakeTimers()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: "报告尚未生成" }) })
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: "报告尚未生成" }) })
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ detail: "报告分享准备失败" }) })
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: "报告尚未生成" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ share_url: "/report/share-token" }) })

    const promise = createReportShareLink("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    await vi.advanceTimersByTimeAsync(300)
    await vi.advanceTimersByTimeAsync(900)
    await vi.advanceTimersByTimeAsync(1500)
    await vi.advanceTimersByTimeAsync(1500)

    await expect(promise).resolves.toBe("/report/share-token")
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })
})
