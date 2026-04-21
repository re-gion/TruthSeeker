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

    const scroller = screen.getByTestId("agent-log-scroll")

    expect(scroller).toHaveStyle({ height: "100%", maxHeight: "100%" })
    expect(scroller.className).toContain("overflow-y-auto")
  })
})
