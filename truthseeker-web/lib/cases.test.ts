import { describe, expect, it, vi } from "vitest"

import {
  CASE_CATEGORY_OPTIONS,
  getCaseDetail,
  getCaseList,
  normalizeCaseDetail,
  normalizeCaseListResponse,
  requestCasePreviewUrl,
} from "./cases"

describe("public case library mapping", () => {
  it("keeps the expected category filter labels", () => {
    expect(CASE_CATEGORY_OPTIONS.map((option) => option.id)).toEqual([
      "all",
      "text_generation",
      "image_forgery",
      "image_text_mixed",
      "audio_forgery",
      "video_forgery",
    ])
    expect(CASE_CATEGORY_OPTIONS.find((option) => option.id === "image_forgery")?.label).toBe("图像伪造")
  })

  it("normalizes backend list payload and strips unsafe file paths from UI models", () => {
    const view = normalizeCaseListResponse({
      items: [
        {
          id: "case-1",
          title: "公开案例",
          media_category: "audio_forgery",
          summary: "疑似音频克隆",
          verdict: "forged",
          confidence_overall: 0.91,
          difficulty: "High",
          public_files: [{ id: "file-1", name: "sample.mp3", storage_path: "hidden/path.mp3" }],
          published_at: "2026-05-28T00:00:00+00:00",
        },
      ],
      page: 1,
      page_size: 6,
      total: 9,
    })

    expect(view.items[0].categoryLabel).toBe("音频伪造")
    expect(view.items[0].confidenceLabel).toBe("91.0%")
    expect(view.items[0].publicFiles[0].storagePath).toBeNull()
    expect(view.totalPages).toBe(2)
  })

  it("maps builtin case source for detail pages", () => {
    const detail = normalizeCaseDetail({
      id: "builtin-audio-scam",
      source_kind: "builtin",
      title: "董事长语音诈骗",
      media_category: "audio_forgery",
      public_files: [],
      report_markdown: "# 董事长语音诈骗",
    })

    expect(detail.sourceKind).toBe("builtin")
    expect(detail.reportMarkdown).toContain("董事长语音诈骗")
  })

  it("normalizes legacy AIGC and deepfake verdict aliases for public cases", () => {
    expect(normalizeCaseDetail({
      id: "case-ai",
      verdict: "AI_GENERATED",
      public_files: [],
    }).verdictLabel).toBe("疑似 AIGC")

    const detail = normalizeCaseDetail({
      id: "case-deepfake",
      verdict: "deepfake",
      public_files: [],
    })
    expect(detail.verdict).toBe("forged")
    expect(detail.verdictLabel).toBe("确认伪造")
  })

  it("fetches list/detail/preview endpoints with the expected public API shape", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], page: 2, page_size: 3, total: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "case-1", title: "详情", public_files: [], report_markdown: "# 报告" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          signed_url: "https://storage.example/file",
          expires_in: 600,
          preview_kind: "text",
          text_url: "/api/v1/cases/case-1/files/file-1/text",
        }),
      })

    await getCaseList({ category: "video_forgery", page: 2, pageSize: 3 }, fetchMock as unknown as typeof fetch)
    await getCaseDetail("case-1", fetchMock as unknown as typeof fetch)
    const preview = await requestCasePreviewUrl("case-1", "file-1", fetchMock as unknown as typeof fetch)

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/v1/cases?category=video_forgery&page=2&page_size=3", {
      cache: "no-store",
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/v1/cases/case-1", { cache: "no-store" })
    expect(fetchMock).toHaveBeenNthCalledWith(3, "http://localhost:8000/api/v1/cases/case-1/preview-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: "file-1" }),
    })
    expect(preview.signedUrl).toBe("https://storage.example/file")
    expect(preview.previewKind).toBe("text")
    expect(preview.textUrl).toBe("http://localhost:8000/api/v1/cases/case-1/files/file-1/text")
  })
})
