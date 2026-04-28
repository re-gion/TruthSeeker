"use client"

import { useCallback, useMemo, useState } from "react"
import { FileSearch, Filter, Network, ShieldCheck } from "lucide-react"
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type NodeProps,
  type Edge as RFEdge,
  type Node as RFNode,
} from "@xyflow/react"

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

function ProvenanceNodeComponent({ data, selected }: NodeProps) {
  return (
    <div className={`text-left transition-transform hover:scale-[1.02] ${selected ? "ring-2 ring-[#D4FF12]/70" : ""}`}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0.5, width: 6, height: 6 }} />
      <div className="flex items-start justify-between gap-2">
        <span className="line-clamp-2 font-medium">{String(data.label)}</span>
        <span className="shrink-0 rounded bg-black/30 px-1.5 py-0.5 text-[10px] text-white/55">
          {String(data.nodeType)}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between text-[10px] text-white/45">
        <span>{(((data.confidence as number) ?? 0) * 100).toFixed(0)}%</span>
        {Boolean(data.modelInferred) && <span className="text-[#F59E0B]">model_inferred</span>}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0.5, width: 6, height: 6 }} />
    </div>
  )
}

const nodeTypes = { provenance: ProvenanceNodeComponent }

export function ProvenanceGraphView({ graph, isComplete }: ProvenanceGraphViewProps) {
  const filters = useMemo(() => getGraphFilters(graph), [graph])
  const [nodeTypesFilter, setNodeTypesFilter] = useState<Set<string>>(new Set())
  const [edgeTypesFilter, setEdgeTypesFilter] = useState<Set<string>>(new Set())
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const filteredGraph = useMemo(
    () => filterProvenanceGraph(graph, nodeTypesFilter, edgeTypesFilter),
    [edgeTypesFilter, graph, nodeTypesFilter],
  )
  const mapped = useMemo(() => toReactFlowGraph(filteredGraph), [filteredGraph])
  const nodeLookup = useMemo(
    () => new Map((filteredGraph.nodes || []).map((node) => [node.id, node])),
    [filteredGraph.nodes],
  )
  const selectedNode = selectedNodeId ? nodeLookup.get(selectedNodeId) ?? null : null

  const citations = Array.isArray(filteredGraph.citations) ? filteredGraph.citations : []
  const quality = filteredGraph.quality || {}

  function toggle(setter: (next: Set<string>) => void, current: Set<string>, value: string) {
    const next = new Set(current)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    setter(next)
  }

  const onNodeClick = useCallback((_event: React.MouseEvent, node: RFNode) => {
    setSelectedNodeId(node.id)
  }, [])

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
      <div className="min-w-0 rounded-xl border border-white/10 bg-black/35 flex flex-col">
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
              active={nodeTypesFilter.size === 0 || nodeTypesFilter.has(type)}
              onClick={() => toggle(setNodeTypesFilter, nodeTypesFilter, type)}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-2 border-b border-white/10 px-4 py-3">
          {filters.edgeTypes.map((type) => (
            <FilterButton
              key={type}
              label={type}
              active={edgeTypesFilter.size === 0 || edgeTypesFilter.has(type)}
              onClick={() => toggle(setEdgeTypesFilter, edgeTypesFilter, type)}
            />
          ))}
        </div>

        <div className="flex-1 min-h-0">
          <ReactFlow
            nodes={mapped.nodes as RFNode[]}
            edges={mapped.edges as RFEdge[]}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#334155" gap={20} size={1} />
            <Controls className="!bg-black/50 !border-white/10 !text-white/70" />
          </ReactFlow>
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
