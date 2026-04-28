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
})
