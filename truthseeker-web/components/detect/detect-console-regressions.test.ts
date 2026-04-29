import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

const projectRoot = process.cwd()

function readSource(relativePath: string) {
  return readFileSync(join(projectRoot, relativePath), "utf8")
}

describe("detect console timeline regressions", () => {
  it("removes the 2D orthographic agent view while keeping the 3D, timeline, and graph entries", () => {
    const source = readSource("components/detect/DetectConsole.tsx")

    expect(source).not.toContain('"2d"')
    expect(source).not.toContain("'2d'")
    expect(source).not.toContain("2D 正交")
    expect(source).not.toContain('viewMode !== "timeline"')
    expect(source).toContain('"3d" | "timeline" | "graph"')
    expect(source).toContain("BentoScene")
    expect(source).toContain("EvidenceTimeline")
    expect(source).toContain("ProvenanceGraphView")
  })

  it("renders challenger timeline rounds as local phase rounds instead of global R labels", () => {
    const source = readSource("components/detect/EvidenceTimeline.tsx")

    expect(source).toContain("phaseRound")
    expect(source).toContain("formatRoundLabel")
    expect(source).toContain("Forensics R")
    expect(source).not.toContain("R{round}")
  })

  it("uses a system workflow board instead of a debate-round-only header card", () => {
    const source = readSource("components/detect/DetectConsole.tsx")

    expect(source).toContain("SystemFlowBoard")
    expect(source).toContain("上传输入")
    expect(source).toContain("创建任务")
    expect(source).toContain("开始检测")
    expect(source).toContain("逻辑质询 Agent vs")
    expect(source).toContain("电子取证 Agent 第")
    expect(source).not.toContain("辩论轮次")
    expect(source).not.toContain("当前决策权重分布")
  })

  it("keeps consultation controls role-scoped and exposes the new context fields", () => {
    const panelSource = readSource("components/collaboration/ExpertPanel.tsx")
    const streamSource = readSource("hooks/useAgentStream.ts")
    const consoleSource = readSource("components/detect/DetectConsole.tsx")

    expect(streamSource).toContain("consultation_approval_required")
    expect(streamSource).toContain("consultation_started")
    expect(streamSource).toContain("consultation_summary_pending")
    expect(streamSource).toContain("consultation_summary_confirmed")
    expect(streamSource).toContain("consultation_skipped")
    expect(streamSource).toContain("consultation_resumed")
    expect(panelSource).toContain("canModerateConsultation(currentRole)")
    expect(panelSource).toContain("结束会诊")
    expect(panelSource).toContain("确认摘要并交给 Commander")
    expect(panelSource).toContain("message_type")
    expect(panelSource).toContain("anchor_agent")
    expect(panelSource).toContain("suggested_action")
    expect(panelSource).toContain("会诊上下文")
    expect(consoleSource).toContain("consultationState={consultationState}")
  })
})
