// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ExpertPanel, normalizeAutonomousObservationText } from "./ExpertPanel"
import type { ConsultationState } from "@/hooks/useAgentStream"

const realtimeMocks = vi.hoisted(() => ({
  channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
      send: vi.fn(),
  })),
}))

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    channel: realtimeMocks.channel,
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
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    realtimeMocks.channel.mockClear()
  })

  it("uses a dedicated collaboration topic instead of displacing the task stream channel", () => {
    render(<ExpertPanel taskId="task-1" currentRole="host" consultationState={consultationState} />)

    expect(realtimeMocks.channel).toHaveBeenCalledWith("collaboration:task-1")
  })

  it("polls persisted expert replies within three seconds when realtime delivery is unavailable", async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ messages: [] }),
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel taskId="task-1" currentRole="host" consultationState={consultationState} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    const initialCalls = fetchMock.mock.calls.length

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect(initialCalls).toBeGreaterThan(0)
    expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCalls)
  })

  it("does not overlap message polling while the previous request is still pending", async () => {
    vi.useFakeTimers()
    let resolveFetch: ((value: { ok: boolean; json: () => Promise<{ messages: never[] }> }) => void) | undefined
    const fetchMock = vi.fn(() => new Promise<{ ok: boolean; json: () => Promise<{ messages: never[] }> }>((resolve) => {
      resolveFetch = resolve
    }))
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel taskId="task-1" currentRole="host" consultationState={consultationState} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveFetch?.({ ok: true, json: async () => ({ messages: [] }) })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("aborts an in-flight message request when the panel unmounts", async () => {
    const capturedSignals: AbortSignal[] = []
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal) capturedSignals.push(init.signal)
      return new Promise(() => undefined)
    })
    vi.stubGlobal("fetch", fetchMock)

    const { unmount } = render(
      <ExpertPanel taskId="task-1" currentRole="host" consultationState={consultationState} />,
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    expect(capturedSignals[0]).toBeInstanceOf(AbortSignal)
    unmount()
    expect(capturedSignals[0].aborted).toBe(true)
  })

  it("does not start a history refresh when message persistence finishes after unmount", async () => {
    let resolvePost: ((value: { ok: boolean; json: () => Promise<{ message_id: string }> }) => void) | undefined
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Promise<{ ok: boolean; json: () => Promise<{ message_id: string }> }>((resolve) => {
          resolvePost = resolve
        })
      }
      return Promise.resolve({ ok: true, json: async () => ({ messages: [] }) })
    })
    vi.stubGlobal("fetch", fetchMock)

    const { unmount } = render(<ExpertPanel
      taskId="task-1"
      currentRole="expert"
      inviteToken="invite-1"
      consultationState={{ ...consultationState, session: { id: "session-1" } }}
    />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    fireEvent.change(screen.getByPlaceholderText(/提交专家意见/), { target: { value: "建议核验来源链路。" } })
    fireEvent.click(screen.getByRole("button", { name: "发送" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    unmount()
    resolvePost?.({ ok: true, json: async () => ({ message_id: "message-1" }) })
    await act(async () => {
      await Promise.resolve()
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("broadcasts moderation state on the shared task stream channel", async () => {
    const eventChannel = { send: vi.fn().mockResolvedValue("ok") }
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            session: {
              id: "session-1",
              status: "summary_pending",
              summary_payload: { generated_summary: "专家建议补充来源链路。" },
            },
          }),
        }
      }
      return { ok: true, json: async () => ({ messages: [] }) }
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      eventChannel={eventChannel as never}
      consultationState={{
        ...consultationState,
        session: { id: "session-1" },
      }}
    />)
    fireEvent.click(screen.getByRole("button", { name: "结束协同" }))

    await waitFor(() => {
      expect(eventChannel.send).toHaveBeenCalledWith(expect.objectContaining({
        type: "broadcast",
        event: "agent_stream",
        payload: expect.objectContaining({ type: "collaboration_summary_pending" }),
      }))
    })
  })

  it("restores the expert reply and shows an error when persistence fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return { ok: false, json: async () => ({ detail: "消息注入失败，请稍后重试" }) }
      }
      return { ok: true, json: async () => ({ messages: [] }) }
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel
      taskId="task-1"
      currentRole="expert"
      inviteToken="invite-1"
      consultationState={{ ...consultationState, session: { id: "session-1" } }}
    />)
    const input = screen.getByPlaceholderText(/提交专家意见/)
    fireEvent.change(input, { target: { value: "建议补充原始发布页。" } })
    fireEvent.click(screen.getByRole("button", { name: "发送" }))

    await waitFor(() => {
      expect(screen.getByText("消息注入失败，请稍后重试")).toBeInTheDocument()
    })
    expect(input).toHaveValue("建议补充原始发布页。")
    const collaborationChannel = realtimeMocks.channel.mock.results.at(-1)?.value
    expect(collaborationChannel?.send).not.toHaveBeenCalled()
  })

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

  it("shows experience drafts returned by summary confirmation without waiting for a self broadcast", async () => {
    const draft = {
      title: "可疑登录通知的域名核验",
      target_agents: ["osint"],
      problem_pattern: "客服通知引导用户访问非官方域名",
      recommended_method: "核对注册域、品牌官方域与独立威胁情报",
      evidence_to_check: ["注册域", "跳转链路"],
      when_to_escalate: "外部情报不可用且域名归属无法确认时",
      limitations: "不能仅凭话术定性",
    }
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            session: {
              id: "session-1",
              status: "summary_confirmed",
              summary_payload: {
                generated_summary: "建议核验非官方域名。",
                user_confirmed_summary: "建议核验非官方域名。",
                experience_drafts: [draft],
              },
            },
          }),
        }
      }
      return { ok: true, json: async () => ({ messages: [] }) }
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_pending",
        summaryDraft: "建议核验非官方域名。",
        experienceDrafts: [],
        session: { id: "session-1" },
      }}
    />)

    fireEvent.click(screen.getByRole("button", { name: "确认摘要并交给 Commander" }))

    await waitFor(() => {
      expect(screen.getByDisplayValue("可疑登录通知的域名核验")).toBeInTheDocument()
    })
  })

  it("shows the backend reason when summary confirmation returns no experience drafts", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            session: {
              id: "session-1",
              status: "summary_confirmed",
              summary_payload: {
                generated_summary: "已确认摘要",
                user_confirmed_summary: "已确认摘要",
                experience_drafts: [],
                experience_drafts_error: "个人经验库草稿生成失败",
              },
            },
          }),
        }
      }
      return { ok: true, json: async () => ({ messages: [] }) }
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_pending",
        summaryDraft: "已确认摘要",
        experienceDrafts: [],
        session: { id: "session-1" },
      }}
    />)

    fireEvent.click(screen.getByRole("button", { name: "确认摘要并交给 Commander" }))

    await waitFor(() => {
      expect(screen.getByText("个人经验库草稿生成失败")).toBeInTheDocument()
    })
  })

  it("explains an already confirmed historical session with an empty draft snapshot", async () => {
    render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_confirmed",
        experienceDrafts: [],
        session: {
          id: "session-1",
          summary_payload: {
            experience_drafts: [],
            experience_skill_execution: { execution_status: "check_failed" },
          },
        },
      }}
    />)

    await waitFor(() => {
      expect(screen.getByText(/个人经验草稿未通过输出检查/)).toBeInTheDocument()
    })
  })

  it("does not overwrite an edited draft when the parent rebuilds the same session snapshot", async () => {
    const originalDraft = {
      title: "原始标题",
      target_agents: ["osint"],
      problem_pattern: "可疑通知",
      recommended_method: "核验来源",
      evidence_to_check: [],
      when_to_escalate: "证据不足时",
      limitations: "仅作线索",
    }
    const { rerender } = render(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_confirmed",
        experienceDrafts: [originalDraft],
        session: { id: "session-1" },
      }}
    />)
    const titleInput = await screen.findByDisplayValue("原始标题")
    fireEvent.change(titleInput, { target: { value: "用户编辑后的标题" } })

    rerender(<ExpertPanel
      taskId="task-1"
      currentRole="host"
      consultationState={{
        ...consultationState,
        status: "summary_confirmed",
        experienceDrafts: [{ ...originalDraft }],
        session: { id: "session-1" },
      }}
    />)

    expect(screen.getByDisplayValue("用户编辑后的标题")).toBeInTheDocument()
  })
})
