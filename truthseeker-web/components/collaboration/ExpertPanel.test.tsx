// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ExpertPanel, normalizeAutonomousObservationText } from "./ExpertPanel"
import type { ConsultationState } from "@/hooks/useAgentStream"

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    channel: () => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
      send: vi.fn(),
    }),
  }),
}))

vi.mock("@/lib/auth", () => ({
  getAuthToken: vi.fn().mockResolvedValue(null),
}))

vi.mock("next/image", () => ({
  default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={alt} {...props} />,
}))

const consultationState = {
  status: "started",
  taskId: "task-1",
  reason: "核心证据互相冲突，需要人机协同。",
  context: {
    background: "公开视频疑似经过二次编辑。",
    progress: "Challenger 已完成三轮质询。",
    blockers: ["取证置信度与溯源链路冲突"],
    helpNeeded: ["请判断是否需要补充来源链路。"],
    sampleLinks: [{ label: "样本 A", url: "https://example.invalid/a" }],
    expertTasks: [
      { question: "核实来源链路是否可靠", expectedOutput: "给出可采信或不可采信判断" },
      { question: "判断画面异常是否来自压缩", expectedOutput: "说明是否影响最终裁决" },
    ],
  },
  history: [],
} satisfies ConsultationState

describe("ExpertPanel", () => {
  it("does not describe LLM autonomous observation as human observation", () => {
    expect(normalizeAutonomousObservationText("这严重依赖LLM人工观察，缺乏自动化验证。"))
      .toBe("这严重依赖LLM自主观察，缺乏自动化验证。")
    expect(normalizeAutonomousObservationText("仍建议保留人工复核入口和人工意见。"))
      .toBe("仍建议保留人工复核入口和人工意见。")
  })

  it("hides message metadata controls from experts", () => {
    render(<ExpertPanel taskId="task-1" currentRole="expert" consultationState={consultationState} />)

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText("阶段 / phase")).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/suggested_action/)).not.toBeInTheDocument()
  })

  it("collapses consultation context by default and expands to show expert tasks first", () => {
    render(<ExpertPanel taskId="task-1" currentRole="expert" consultationState={consultationState} />)

    expect(screen.getByText("2 项专家任务")).toBeInTheDocument()
    expect(screen.queryByText("公开视频疑似经过二次编辑。")).not.toBeInTheDocument()
    expect(screen.queryByText("核实来源链路是否可靠")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "展开" }))

    expect(screen.getByText("核实来源链路是否可靠")).toBeInTheDocument()
    expect(screen.getByText(/给出可采信或不可采信判断/)).toBeInTheDocument()
    expect(screen.getByText("公开视频疑似经过二次编辑。")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "收起" })).toBeInTheDocument()
  })

  it("hides the summary editor after confirmation while keeping editable experience drafts", async () => {
    render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_confirmed",
        summaryDraft: "已确认的协同摘要",
        experienceDrafts: [{
          title: "工具失效时的补证策略",
          target_agents: ["forensics", "osint"],
          problem_pattern: "关键自动化工具不可用",
          recommended_method: "补充自主观察与外部来源交叉核验",
          evidence_to_check: ["图像视觉特征", "来源链路"],
          when_to_escalate: "仍无法解释关键矛盾时",
          limitations: "不能替代真实外部检测结论",
        }],
      }}
    />)

    await waitFor(() => {
      expect(screen.queryByPlaceholderText("编辑 Commander 待确认的协同摘要...")).not.toBeInTheDocument()
    })
    expect(screen.getByText("经验标题")).toBeInTheDocument()
    expect(screen.getByText("适用对象")).toBeInTheDocument()
    expect(screen.getByText("适用条件")).toBeInTheDocument()
    expect(screen.getByText("经验具体内容")).toBeInTheDocument()
    expect(screen.getByText("补充说明")).toBeInTheDocument()
    expect(screen.queryByPlaceholderText("需要核验的证据，每行一项")).not.toBeInTheDocument()
  })
})
