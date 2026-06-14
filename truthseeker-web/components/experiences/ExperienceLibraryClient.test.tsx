// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ExperienceLibraryClient } from "./ExperienceLibraryClient"
import { getExperienceList } from "@/lib/experiences"

vi.mock("next/link", () => ({
  default: ({ children, href, className }: { children: React.ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock("@/lib/auth", () => ({
  getAuthToken: vi.fn().mockResolvedValue("token"),
}))

vi.mock("@/lib/experiences", async () => {
  const actual = await vi.importActual<typeof import("@/lib/experiences")>("@/lib/experiences")
  return {
    ...actual,
    getExperienceList: vi.fn(),
  }
})

describe("ExperienceLibraryClient", () => {
  it("renders markdown content inside personal experience cards", async () => {
    vi.mocked(getExperienceList).mockResolvedValue({
      items: [{
        id: "exp-1",
        source_task_id: null,
        source_session_id: null,
        source_collaboration_session_id: null,
        title: "工具失效补证策略",
        target_agents: ["forensics"],
        problem_pattern: "**关键异常**\n\n- 自动化取证失败",
        recommended_method: "",
        evidence_to_check: [],
        when_to_escalate: "",
        limitations: "",
        created_at: "2026-06-14T00:00:00.000Z",
        updated_at: null,
      }],
      page: 1,
      pageSize: 9,
      total: 1,
      totalPages: 1,
    })

    render(<ExperienceLibraryClient />)

    const emphasis = await screen.findByText("关键异常")
    expect(emphasis.tagName).toBe("STRONG")
    expect(screen.getByText("自动化取证失败").tagName).toBe("LI")
    expect(screen.queryByText(/\*\*关键异常\*\*/)).not.toBeInTheDocument()
  })
})
