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
})
