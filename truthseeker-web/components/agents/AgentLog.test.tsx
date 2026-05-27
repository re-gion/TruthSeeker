// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AgentLog } from "./AgentLog"

describe("AgentLog", () => {
  it("uses a full-height scroll container when embedded in fixed agent panels", () => {
    render(
      <div style={{ height: "180px" }}>
        <AgentLog
          maxHeight="100%"
          logs={[
            {
              agent: "forensics",
              type: "finding",
              content: "第一条检测记录",
              timestamp: "2026-04-21T00:00:00.000Z",
            },
            {
              agent: "forensics",
              type: "finding",
              content: "第二条检测记录",
              timestamp: "2026-04-21T00:00:01.000Z",
            },
          ]}
        />
      </div>,
    )

    const shell = screen.getByTestId("agent-log-shell")
    const scroller = screen.getByTestId("agent-log-scroll")

    expect(shell).toHaveStyle({ height: "100%", maxHeight: "100%" })
    expect(shell.className).toContain("h-full")
    expect(shell.className).toContain("w-full")
    expect(shell.className).toContain("max-w-full")
    expect(shell.className).toContain("min-h-0")
    expect(shell.className).toContain("min-w-0")
    expect(shell.className).toContain("basis-0")
    expect(shell.className).toContain("overflow-hidden")
    expect(shell.className).toContain("box-border")
    expect(scroller.className).toContain("overflow-y-auto")
    expect(scroller.className).toContain("h-full")
    expect(scroller.className).toContain("w-full")
    expect(scroller.className).toContain("max-h-full")
    expect(scroller.className).toContain("max-w-full")
    expect(scroller.className).toContain("min-h-0")
    expect(scroller.className).toContain("min-w-0")
    expect(scroller.className).toContain("flex-1")
    expect(scroller.className).toContain("basis-0")
    expect(scroller.className).toContain("box-border")
    expect(scroller.className).not.toContain("pr-2")
  })

  it("renders each log entry as a full-width content block that wraps inside the panel", () => {
    const longContent = "https://example.test/suspicious/path/with/a/very-long-unbroken-token-that-must-not-force-horizontal-overflow"

    render(
      <div style={{ height: "220px", width: "420px" }}>
        <AgentLog
          maxHeight="100%"
          logs={[
            {
              agent: "forensics",
              type: "finding",
              content: longContent,
              timestamp: "2026-04-21T00:00:03.000Z",
            },
          ]}
        />
      </div>,
    )

    const entry = screen.getByTestId("agent-log-entry")
    const content = screen.getByTestId("agent-log-entry-content")

    expect(entry.className).toContain("grid")
    expect(entry.className).toContain("w-full")
    expect(entry.className).toContain("max-w-full")
    expect(entry.className).toContain("min-w-0")
    expect(content.className).toContain("block")
    expect(content.className).toContain("w-full")
    expect(content.className).toContain("max-w-full")
    expect(content.className).toContain("min-w-0")
    expect(content.className).toContain("[overflow-wrap:anywhere]")
    expect(content.className).toContain("[word-break:break-word]")
    expect(content.className).toContain("whitespace-pre-wrap")
    expect(content).toHaveTextContent(longContent)
  })

  it("renders long latest log content immediately instead of trapping it in a slow typewriter strip", () => {
    const longContent = "全局检测目标：判断该内容是否可能用于诈骗或身份冒充。".repeat(8)

    render(
      <div style={{ height: "220px" }}>
        <AgentLog
          maxHeight="100%"
          logs={[
            {
              agent: "commander",
              type: "thinking",
              content: longContent,
              timestamp: "2026-04-21T00:00:02.000Z",
            },
          ]}
        />
      </div>,
    )

    expect(screen.getByText(longContent)).toBeInTheDocument()
  })

  it("scrolls the actual log container to the bottom after entries render", () => {
    const originalRequestAnimationFrame = window.requestAnimationFrame
    const originalCancelAnimationFrame = window.cancelAnimationFrame
    const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollHeight")

    window.requestAnimationFrame = (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    }
    window.cancelAnimationFrame = () => undefined
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return this.getAttribute("data-testid") === "agent-log-scroll" ? 900 : 0
      },
    })

    try {
      render(
        <div style={{ height: "220px" }}>
          <AgentLog
            maxHeight="100%"
            logs={[
              {
                agent: "commander",
                type: "thinking",
                content: "第一条研判记录",
                timestamp: "2026-04-21T00:00:01.000Z",
              },
              {
                agent: "commander",
                type: "finding",
                content: "第二条研判记录",
                timestamp: "2026-04-21T00:00:02.000Z",
              },
            ]}
          />
        </div>,
      )

      expect(screen.getByTestId("agent-log-scroll").scrollTop).toBe(900)
    } finally {
      window.requestAnimationFrame = originalRequestAnimationFrame
      window.cancelAnimationFrame = originalCancelAnimationFrame
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, "scrollHeight", originalScrollHeight)
      } else {
        delete (HTMLElement.prototype as { scrollHeight?: number }).scrollHeight
      }
    }
  })
})
