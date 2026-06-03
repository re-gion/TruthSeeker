// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { CaseLibraryClient } from "./CaseLibraryClient"
import { getCaseList } from "@/lib/cases"

vi.mock("next/link", () => ({
  default: ({ children, href, className }: { children: React.ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
  },
}))

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases")
  return {
    ...actual,
    getCaseList: vi.fn(),
  }
})

describe("CaseLibraryClient", () => {
  it("renders real case cards as block links so card borders are not fragmented", async () => {
    vi.mocked(getCaseList).mockResolvedValue({
      items: [
        {
          id: "case-1",
          sourceKind: "public",
          taskId: "task-1",
          title: "图文混合身份冒充诈骗案例",
          mediaCategory: "image_text_mixed",
          categoryLabel: "图文混合",
          summary: "本案例涉及图文混合内容，经 forensic 分析发现存在伪造领域特征。",
          verdict: "suspicious",
          verdictLabel: "高度可疑",
          confidenceOverall: 0,
          confidenceLabel: "0.0%",
          difficulty: "Low",
          publicFiles: [{ id: "file-1", name: "case.png", mimeType: "image/png", modality: "image", sizeBytes: 900, storagePath: null }],
          publishedAt: "2026-06-02T00:00:00.000Z",
        },
      ],
      page: 1,
      pageSize: 6,
      total: 1,
      totalPages: 1,
    })

    render(<CaseLibraryClient />)

    const cardLink = await screen.findByRole("link", { name: /图文混合身份冒充诈骗案例/ })

    expect(cardLink.className).toContain("block")
  })
})
