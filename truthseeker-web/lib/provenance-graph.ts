export type ProvenanceNodeType =
  | "artifact"
  | "entity"
  | "source"
  | "evidence"
  | "finding"
  | "claim"
  | "event"
  | "agent"
  | "verdict"

export type ProvenanceEdgeType =
  | "extracted_from"
  | "mentions"
  | "derived_from"
  | "supports"
  | "refutes"
  | "contradicts"
  | "reviewed_by"
  | "before"
  | "after"

export interface ProvenanceNode {
  id: string
  type: ProvenanceNodeType | string
  label: string
  confidence?: number
  citation_ids?: string[]
  model_inferred?: boolean
  metadata?: Record<string, unknown>
}

export interface ProvenanceEdge {
  id?: string
  source: string
  target: string
  type: ProvenanceEdgeType | string
  citation_ids?: string[]
  model_inferred?: boolean
  explanation?: string
}

export interface ProvenanceCitation {
  id: string
  source_name?: string
  url?: string
  retrieved_at?: string
  summary?: string
  file_hash?: string
  metadata?: Record<string, unknown>
}

export interface ProvenanceGraph {
  schema_version?: string
  task_id?: string
  nodes?: ProvenanceNode[]
  edges?: ProvenanceEdge[]
  citations?: ProvenanceCitation[]
  quality?: Record<string, unknown>
  generated_at?: string
}

export interface ReactFlowNodeLike {
  id: string
  type?: string
  position: { x: number; y: number }
  data: {
    label: string
    nodeType: string
    confidence?: number
    citationIds: string[]
    modelInferred: boolean
    metadata?: Record<string, unknown>
  }
  style?: Record<string, string | number>
}

export interface ReactFlowEdgeLike {
  id: string
  source: string
  target: string
  label: string
  animated?: boolean
  data: {
    edgeType: string
    citationIds: string[]
    modelInferred: boolean
    explanation?: string
  }
  style?: Record<string, string | number>
}

export const NODE_COLORS: Record<string, { border: string; bg: string; color: string }> = {
  artifact: { border: "#6366F1", bg: "rgba(99,102,241,0.16)", color: "#E0E7FF" },
  source: { border: "#10B981", bg: "rgba(16,185,129,0.14)", color: "#D1FAE5" },
  evidence: { border: "#06B6D4", bg: "rgba(6,182,212,0.14)", color: "#CFFAFE" },
  finding: { border: "#06B6D4", bg: "rgba(6,182,212,0.14)", color: "#CFFAFE" },
  claim: { border: "#F59E0B", bg: "rgba(245,158,11,0.14)", color: "#FEF3C7" },
  event: { border: "#94A3B8", bg: "rgba(148,163,184,0.10)", color: "#E2E8F0" },
  agent: { border: "#D4FF12", bg: "rgba(212,255,18,0.10)", color: "#F4FF9A" },
  verdict: { border: "#EF4444", bg: "rgba(239,68,68,0.14)", color: "#FEE2E2" },
}

function clamp01(value: unknown, fallback = 0.5) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, Math.min(1, value))
    : fallback
}

function graphLayers(nodes: ProvenanceNode[]) {
  const order: Record<string, number> = {
    artifact: 0,
    source: 0,
    evidence: 1,
    finding: 1,
    claim: 2,
    entity: 2,
    event: 3,
    agent: 4,
    verdict: 5,
  }
  const buckets = new Map<number, ProvenanceNode[]>()
  nodes.forEach((node) => {
    const layer = order[node.type] ?? 2
    const bucket = buckets.get(layer) ?? []
    bucket.push(node)
    buckets.set(layer, bucket)
  })
  return buckets
}

export function toReactFlowGraph(graph: ProvenanceGraph | null | undefined) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph?.edges) ? graph.edges : []
  const buckets = graphLayers(nodes)
  const mappedNodes: ReactFlowNodeLike[] = []

  Array.from(buckets.entries())
    .sort(([a], [b]) => a - b)
    .forEach(([layer, bucket]) => {
      bucket.forEach((node, index) => {
        const color = NODE_COLORS[node.type] ?? NODE_COLORS.entity
        mappedNodes.push({
          id: node.id,
          type: "provenance",
          position: {
            x: layer * 240,
            y: index * 120 + (layer % 2) * 52,
          },
          data: {
            label: node.label || node.id,
            nodeType: node.type,
            confidence: clamp01(node.confidence),
            citationIds: Array.isArray(node.citation_ids) ? node.citation_ids.filter(Boolean) : [],
            modelInferred: Boolean(node.model_inferred),
            metadata: node.metadata,
          },
          style: {
            minWidth: 168,
            maxWidth: 220,
            border: `1px solid ${color.border}`,
            background: color.bg,
            color: color.color,
            borderRadius: 8,
            padding: 10,
            fontSize: 12,
            lineHeight: 1.35,
          },
        })
      })
    })

  const mappedEdges: ReactFlowEdgeLike[] = edges.map((edge, index) => ({
    id: edge.id || `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.type,
    animated: Boolean(edge.model_inferred),
    data: {
      edgeType: edge.type,
      citationIds: Array.isArray(edge.citation_ids) ? edge.citation_ids.filter(Boolean) : [],
      modelInferred: Boolean(edge.model_inferred),
      explanation: edge.explanation,
    },
    style: {
      stroke: edge.model_inferred ? "#F59E0B" : "#64748B",
      strokeDasharray: edge.model_inferred ? "6 4" : "0",
    },
  }))

  return { nodes: mappedNodes, edges: mappedEdges }
}

export function getGraphFilters(graph: ProvenanceGraph | null | undefined) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph?.edges) ? graph.edges : []
  return {
    nodeTypes: Array.from(new Set(nodes.map((node) => node.type))).sort(),
    edgeTypes: Array.from(new Set(edges.map((edge) => edge.type))).sort(),
  }
}

export function filterProvenanceGraph(
  graph: ProvenanceGraph | null | undefined,
  nodeTypes: Set<string>,
  edgeTypes: Set<string>,
): ProvenanceGraph {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph?.edges) ? graph.edges : []
  const visibleNodes = nodeTypes.size > 0 ? nodes.filter((node) => nodeTypes.has(node.type)) : nodes
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id))
  const visibleEdges = edges.filter((edge) => {
    const edgeTypeVisible = edgeTypes.size === 0 || edgeTypes.has(edge.type)
    return edgeTypeVisible && visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
  })

  return {
    ...graph,
    nodes: visibleNodes,
    edges: visibleEdges,
    citations: Array.isArray(graph?.citations) ? graph.citations : [],
    quality: graph?.quality ?? {},
  }
}
