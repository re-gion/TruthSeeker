// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ExperienceDetailClient } from "./ExperienceDetailClient"
import { getExperienceDetail } from "@/lib/experiences"

vi.mock("next/link", () => ({
  default: ({ children, href, className }: { children: React.ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/lib/auth", () => ({
  getAuthToken: vi.fn().mockResolvedValue("token"),
}))

vi.mock("@/lib/experiences", async () => {
  const actual = await vi.importActual<typeof import("@/lib/experiences")>("@/lib/experiences")
  return {
    ...actual,
    deleteExperience: vi.fn(),
    getExperienceDetail: vi.fn(),
  }
})

describe("ExperienceDetailClient", () => {
  it("renders stored markdown fields as markdown in detail cards", async () => {
    vi.mocked(getExperienceDetail).mockResolvedValue({
      id: "exp-1",
      source_task_id: null,
      source_session_id: null,
      source_collaboration_session_id: null,
      title: "工具失效补证策略",
      target_agents: ["forensics"],
      problem_pattern: "### 适用条件\n\n**核心矛盾** 已出现",
      recommended_method: "1. 保留原始检材\n2. 交叉核验来源",
      evidence_to_check: ["**视觉异常**", "`metadata` 字段"],
      when_to_escalate: "> 多轮补证仍无法解释",
      limitations: "不能替代 **外部检测结论**",
      created_at: "2026-06-14T00:00:00.000Z",
      updated_at: null,
    })

    render(<ExperienceDetailClient entryId="exp-1" />)

    expect((await screen.findByRole("heading", { name: "适用条件" })).tagName).toBe("H3")
    expect(screen.getByText("核心矛盾").tagName).toBe("STRONG")
    expect(screen.getByText("保留原始检材").tagName).toBe("LI")
    expect(screen.getByText("视觉异常").tagName).toBe("STRONG")
    expect(screen.getByText("metadata").tagName).toBe("CODE")
    expect(screen.getByText("外部检测结论").tagName).toBe("STRONG")
  })
})
