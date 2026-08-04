// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AgentCard } from "./AgentCard"

describe("AgentCard core Skill binding", () => {
  it.each([
    ["forensics", "多模态电子取证", "multimodal-forensics"],
    ["osint", "情报溯源与证据图谱", "osint-provenance"],
    ["challenger", "证据质询与收敛控制", "evidence-challenge"],
    ["commander", "研判指挥与协同编排", "command-collaboration"],
  ])("shows %s as a fixed binding without claiming runtime application", (agentKey, label, skillName) => {
    render(
      <AgentCard
        name="测试 Agent"
        agentKey={agentKey}
        icon={<span>◇</span>}
        status="idle"
      />,
    )

    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText("v1.0.0")).toBeInTheDocument()
    expect(screen.getByText("固定绑定")).toBeInTheDocument()
    expect(screen.getByTitle(`${skillName} v1.0.0`)).toBeInTheDocument()
    expect(screen.queryByText("本轮已采用")).not.toBeInTheDocument()
  })
})
