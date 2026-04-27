import { describe, expect, it } from "vitest"

import { toReactFlowGraph } from "./provenance-graph"

describe("toReactFlowGraph", () => {
  it("maps provenance graph nodes and edges into React Flow elements", () => {
    const graph = {
      nodes: [
        { id: "artifact:file-1", type: "artifact", label: "clip.mp4", confidence: 0.9 },
        { id: "claim:1", type: "claim", label: "疑似拼接", confidence: 0.65 },
      ],
      edges: [
        {
          id: "edge-1",
          source: "artifact:file-1",
          target: "claim:1",
          type: "supports",
          model_inferred: true,
          explanation: "模型基于上下文推断",
        },
      ],
      citations: [{ id: "file:file-1", source_name: "上传检材" }],
      quality: { completeness: 0.7 },
    }

    const mapped = toReactFlowGraph(graph)

    expect(mapped.nodes).toHaveLength(2)
    expect(mapped.nodes[0]).toMatchObject({
      id: "artifact:file-1",
      data: { label: "clip.mp4", nodeType: "artifact" },
    })
    expect(mapped.edges).toHaveLength(1)
    expect(mapped.edges[0]).toMatchObject({
      id: "edge-1",
      source: "artifact:file-1",
      target: "claim:1",
      label: "supports",
    })
  })
})
