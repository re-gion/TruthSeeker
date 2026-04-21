import { describe, expect, it, vi } from "vitest"

import { fetchCanonicalMarkdownReport } from "./report"

describe("canonical report downloads", () => {
  it("fetches markdown from the backend canonical report endpoint with auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "# 后端报告",
    })

    const markdown = await fetchCanonicalMarkdownReport("task-123", "jwt-token", fetchMock as unknown as typeof fetch)

    expect(markdown).toBe("# 后端报告")
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/report/task-123/md", {
      method: "GET",
      headers: { Authorization: "Bearer jwt-token" },
    })
  })
})
