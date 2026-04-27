"use client"

import { useMemo, useState } from "react"
import { FileSearch, Filter, Network, ShieldCheck } from "lucide-react"

import {
  filterProvenanceGraph,
  getGraphFilters,
  ProvenanceCitation,
  ProvenanceGraph,
  ProvenanceNode,
  toReactFlowGraph,
} from "@/lib/provenance-graph"

interface ProvenanceGraphViewProps {
  graph?: ProvenanceGraph | null
  isComplete: boolean
}

function readNumber(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-white/40">{label}</div>
      <div className="mt-1 font-mono text-sm text-white">{value}</div>
    </div>
  )
}

function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
        active
          ? "border-[#D4FF12]/45 bg-[#D4FF12]/10 text-[#D4FF12]"
          : "border-white/10 bg-white/[0.03] text-white/55 hover:text-white"
      }`}
    >
      {label}
    </button>
  )
}

function CitationPanel({ citations }: { citations: ProvenanceCitation[] }) {
  return (
    <div className="min-h-0 rounded-lg border border-white/10 bg-black/25 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-white/80">
        <FileSearch className="h-4 w-4 text-[#06B6D4]" />
        引用来源
      </div>
      <div className="max-h-44 space-y-2 overflow-auto pr-1">
        {citations.length === 0 ? (
          <div className="text-xs text-white/40">暂无引用</div>
        ) : (
          citations.map((citation) => (
            <div key={citation.id} className="rounded-md border border-white/10 bg-white/[0.03] p-2">
              <div className="truncate text-xs font-medium text-white/80">
                {citation.source_name || citation.id}
              </div>
              {citation.summary && <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-white/45">{citation.summary}</div>}
              {citation.url && (
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block truncate text-[11px] text-[#06B6D4] hover:text-[#67E8F9]"
                >
                  {citation.url}
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function NodeDetails({ node }: { node: ProvenanceNode | null }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/25 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-white/80">
        <ShieldCheck className="h-4 w-4 text-[#D4FF12]" />
        节点详情
      </div>
      {!node ? (
        <div className="text-xs text-white/40">选择图谱节点查看详情</div>
      ) : (
        <div className="space-y-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/35">{node.type}</div>
            <div className="text-sm font-medium text-white">{node.label}</div>
          </div>
          <div className="flex gap-2 text-[11px]">
            <span className="rounded bg-white/10 px-2 py-1 text-white/55">
              置信度 {((node.confidence ?? 0) * 100).toFixed(1)}%
            </span>
            {node.model_inferred && <span className="rounded bg-[#F59E0B]/15 px-2 py-1 text-[#F59E0B]">模型推断</span>}
          </div>
          {Array.isArray(node.citation_ids) && node.citation_ids.length > 0 && (
            <div className="text-[11px] text-white/45">引用: {node.citation_ids.join(", ")}</div>
          )}
        </div>
      )}
    </div>
  )
}

export function ProvenanceGraphView({ graph, isComplete }: ProvenanceGraphViewProps) {
  const filters = useMemo(() => getGraphFilters(graph), [graph])
  const [nodeTypes, setNodeTypes] = useState<Set<string>>(new Set())
  const [edgeTypes, setEdgeTypes] = useState<Set<string>>(new Set())
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const filteredGraph = useMemo(
    () => filterProvenanceGraph(graph, nodeTypes, edgeTypes),
    [edgeTypes, graph, nodeTypes],
  )
  const mapped = useMemo(() => toReactFlowGraph(filteredGraph), [filteredGraph])
  const nodeLookup = useMemo(
    () => new Map((filteredGraph.nodes || []).map((node) => [node.id, node])),
    [filteredGraph.nodes],
  )
  const selectedNode = selectedNodeId ? nodeLookup.get(selectedNodeId) ?? null : null
  const mappedLookup = useMemo(() => new Map(mapped.nodes.map((node) => [node.id, node])), [mapped.nodes])
  const canvasWidth = Math.max(760, ...mapped.nodes.map((node) => node.position.x + 240))
  const canvasHeight = Math.max(520, ...mapped.nodes.map((node) => node.position.y + 120))
  const citations = Array.isArray(filteredGraph.citations) ? filteredGraph.citations : []
  const quality = filteredGraph.quality || {}

  function toggle(setter: (next: Set<string>) => void, current: Set<string>, value: string) {
    const next = new Set(current)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    setter(next)
  }

  if (!isComplete) {
    return (
      <div className="flex min-h-[520px] items-center justify-center p-8">
        <div className="rounded-xl border border-white/10 bg-black/35 px-5 py-4 text-sm text-white/55">
          图谱将在最终裁决完成后展示审定版本
        </div>
      </div>
    )
  }

  if (!graph || !Array.isArray(graph.nodes) || graph.nodes.length === 0) {
    return (
      <div className="flex min-h-[520px] items-center justify-center p-8">
        <div className="rounded-xl border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-5 py-4 text-sm text-[#FCD34D]">
          最终报告未返回可视化图谱
        </div>
      </div>
    )
  }

  return (
    <div className="grid h-full min-h-[620px] grid-cols-[minmax(0,1fr)_320px] gap-4 p-4">
      <div className="min-w-0 rounded-xl border border-white/10 bg-black/35">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Network className="h-4 w-4 text-[#D4FF12]" />
            情报溯源图谱
          </div>
          <div className="flex items-center gap-2 text-[11px] text-white/45">
            <Filter className="h-3.5 w-3.5" />
            {mapped.nodes.length} 节点 / {mapped.edges.length} 关系
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-b border-white/10 px-4 py-3">
          {filters.nodeTypes.map((type) => (
            <FilterButton
              key={type}
              label={type}
              active={nodeTypes.size === 0 || nodeTypes.has(type)}
              onClick={() => toggle(setNodeTypes, nodeTypes, type)}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-2 border-b border-white/10 px-4 py-3">
          {filters.edgeTypes.map((type) => (
            <FilterButton
              key={type}
              label={type}
              active={edgeTypes.size === 0 || edgeTypes.has(type)}
              onClick={() => toggle(setEdgeTypes, edgeTypes, type)}
            />
          ))}
        </div>

        <div className="h-[calc(100%-122px)] overflow-auto">
          <div className="relative" style={{ width: canvasWidth, height: canvasHeight }}>
            <svg className="absolute inset-0 h-full w-full" width={canvasWidth} height={canvasHeight}>
              {mapped.edges.map((edge) => {
                const source = mappedLookup.get(edge.source)
                const target = mappedLookup.get(edge.target)
                if (!source || !target) return null
                const x1 = source.position.x + 184
                const y1 = source.position.y + 42
                const x2 = target.position.x + 8
                const y2 = target.position.y + 42
                const midX = (x1 + x2) / 2
                return (
                  <g key={edge.id}>
                    <path
                      d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                      fill="none"
                      stroke={edge.data.modelInferred ? "#F59E0B" : "#64748B"}
                      strokeDasharray={edge.data.modelInferred ? "6 4" : undefined}
                      strokeWidth={1.4}
                    />
                    <text x={midX} y={(y1 + y2) / 2 - 6} fill="#94A3B8" fontSize="10" textAnchor="middle">
                      {edge.label}
                    </text>
                  </g>
                )
              })}
            </svg>

            {mapped.nodes.map((node) => (
              <button
                key={node.id}
                type="button"
                onClick={() => setSelectedNodeId(node.id)}
                className={`absolute text-left shadow-lg transition-transform hover:scale-[1.02] ${
                  selectedNodeId === node.id ? "ring-2 ring-[#D4FF12]/70" : ""
                }`}
                style={{
                  ...node.style,
                  left: node.position.x,
                  top: node.position.y,
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 font-medium">{node.data.label}</span>
                  <span className="shrink-0 rounded bg-black/30 px-1.5 py-0.5 text-[10px] text-white/55">
                    {node.data.nodeType}
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between text-[10px] text-white/45">
                  <span>{((node.data.confidence ?? 0) * 100).toFixed(0)}%</span>
                  {node.data.modelInferred && <span className="text-[#F59E0B]">model_inferred</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <aside className="flex min-h-0 flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          <Metric label="完整性" value={`${(readNumber(quality.completeness) * 100).toFixed(0)}%`} />
          <Metric label="引用覆盖" value={`${(readNumber(quality.citation_coverage) * 100).toFixed(0)}%`} />
          <Metric label="推断占比" value={`${(readNumber(quality.model_inferred_ratio) * 100).toFixed(0)}%`} />
          <Metric label="审查质量" value={`${(readNumber(quality.challenger_quality_score) * 100).toFixed(0)}%`} />
        </div>
        <NodeDetails node={selectedNode} />
        <CitationPanel citations={citations} />
      </aside>
    </div>
  )
}
