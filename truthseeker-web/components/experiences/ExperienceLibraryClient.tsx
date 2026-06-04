"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { AlertCircle, BookOpenCheck, Loader2, Search } from "lucide-react"
import { getAuthToken } from "@/lib/auth"
import {
  EXPERIENCE_AGENT_OPTIONS,
  getExperienceList,
  type ExperienceAgent,
  type ExperienceEntry,
} from "@/lib/experiences"

const PAGE_SIZE = 9

function agentLabel(agent: string) {
  return EXPERIENCE_AGENT_OPTIONS.find((item) => item.id === agent)?.label ?? agent
}

function ExperienceCard({ item }: { item: ExperienceEntry }) {
  return (
    <Link
      href={`/experiences/${item.id}`}
      className="group block h-full rounded-lg border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.06),rgba(255,255,255,0.025))] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-[#06B6D4]/40 hover:bg-white/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06B6D4]/45"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="line-clamp-2 text-base font-semibold leading-6 text-white group-hover:text-[#67E8F9]">
            {item.title}
          </h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.target_agents.map((agent) => (
              <span key={agent} className="rounded border border-[#06B6D4]/25 bg-[#06B6D4]/10 px-2 py-0.5 text-[11px] text-[#67E8F9]">
                {agentLabel(agent)}
              </span>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-4 line-clamp-3 min-h-[3.75rem] text-sm leading-5 text-white/62">
        {item.problem_pattern}
      </p>
      <div className="mt-5 border-t border-white/10 pt-3 text-xs text-white/42">
        {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "未记录时间"}
      </div>
    </Link>
  )
}

export function ExperienceLibraryClient() {
  const [agent, setAgent] = useState<ExperienceAgent>("all")
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<ExperienceEntry[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getAuthToken()
      .then((token) => {
        if (!token) throw new Error("请先登录后查看个人经验库")
        return getExperienceList({ agent, q: query, page, pageSize: PAGE_SIZE }, token)
      })
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setTotalPages(result.totalPages)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "个人经验库暂时不可用")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [agent, query, page])

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-white/10 bg-black/30 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {EXPERIENCE_AGENT_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => {
                  setLoading(true)
                  setError(null)
                  setAgent(option.id)
                  setPage(1)
                }}
                className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                  agent === option.id
                    ? "border-[#06B6D4]/40 bg-[#06B6D4]/12 text-[#67E8F9]"
                    : "border-white/10 bg-white/[0.04] text-white/62 hover:bg-white/[0.07] hover:text-white"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <label className="relative block min-w-0 lg:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
            <input
              value={query}
              onChange={(event) => {
                setLoading(true)
                setError(null)
                setQuery(event.target.value)
                setPage(1)
              }}
              placeholder="搜索个人经验"
              className="w-full rounded-lg border border-white/10 bg-white/[0.04] py-2 pl-9 pr-3 text-sm text-white outline-none transition-colors placeholder:text-white/35 focus:border-[#06B6D4]/40"
            />
          </label>
        </div>
      </section>

      {error ? (
        <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 p-5 text-sm text-amber-200">
          <AlertCircle className="mr-2 inline h-4 w-4" />
          {error}
        </div>
      ) : loading ? (
        <div className="flex min-h-64 items-center justify-center text-white/55">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          正在加载个人经验库
        </div>
      ) : items.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => <ExperienceCard key={item.id} item={item} />)}
        </div>
      ) : (
        <div className="rounded-lg border border-white/10 bg-white/[0.035] p-8 text-center">
          <BookOpenCheck className="mx-auto h-8 w-8 text-white/30" />
          <div className="mt-3 text-sm text-white/62">当前筛选下还没有个人经验</div>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          disabled={page <= 1 || loading}
          onClick={() => {
            setLoading(true)
            setError(null)
            setPage((value) => Math.max(value - 1, 1))
          }}
          className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/64 disabled:opacity-35"
        >
          上一页
        </button>
        <button
          type="button"
          disabled={page >= totalPages || loading}
          onClick={() => {
            setLoading(true)
            setError(null)
            setPage((value) => value + 1)
          }}
          className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/64 disabled:opacity-35"
        >
          下一页
        </button>
      </div>
    </div>
  )
}
