"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { ArrowLeft, Loader2, Trash2 } from "lucide-react"
import { deleteExperience, getExperienceDetail, type ExperienceEntry } from "@/lib/experiences"
import { getAuthToken } from "@/lib/auth"
import { ExperienceMarkdown } from "./ExperienceMarkdown"

function agentName(agent: string) {
  if (agent === "forensics") return "取证 Agent"
  if (agent === "osint") return "溯源 Agent"
  if (agent === "challenger") return "质询 Agent"
  return agent
}

function evidenceMarkdown(items: string[]) {
  if (!items.length) return "未记录"
  return items.map((item) => `- ${item.replace(/\n/g, "\n  ")}`).join("\n")
}

export function ExperienceDetailClient({ entryId }: { entryId: string }) {
  const router = useRouter()
  const [detail, setDetail] = useState<ExperienceEntry | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    getAuthToken()
      .then((token) => {
        if (!token) throw new Error("请先登录后查看个人经验")
        return getExperienceDetail(entryId, token)
      })
      .then((result) => {
        if (!cancelled) setDetail(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "个人经验不存在或暂时不可用")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entryId])

  async function handleDelete() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      return
    }
    setDeleteLoading(true)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("请先登录")
      await deleteExperience(entryId, token)
      router.push("/experiences")
    } catch (err) {
      setError(err instanceof Error ? err.message : "个人经验删除失败")
      setDeleteConfirm(false)
    } finally {
      setDeleteLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center text-white/55">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        正在加载个人经验
      </div>
    )
  }

  if (error || !detail) {
    return <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-6 text-red-200">{error || "个人经验不存在"}</div>
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Link href="/experiences" className="inline-flex items-center gap-2 text-sm text-white/55 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
          返回个人经验库
        </Link>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteLoading}
          className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-colors disabled:opacity-50 ${
            deleteConfirm
              ? "border-red-500/60 bg-red-500/15 text-red-300 hover:bg-red-500/25"
              : "border-white/10 text-white/40 hover:border-red-400/40 hover:text-red-300"
          }`}
        >
          {deleteLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {deleteLoading ? "删除中" : deleteConfirm ? "确认删除" : "删除经验"}
        </button>
      </div>

      <section className="rounded-lg border border-white/10 bg-white/[0.045] p-6">
        <div className="flex flex-wrap gap-2">
          {detail.target_agents.map((agent) => (
            <span key={agent} className="rounded border border-[#06B6D4]/25 bg-[#06B6D4]/10 px-2 py-1 text-xs text-[#67E8F9]">
              {agentName(agent)}
            </span>
          ))}
        </div>
        <h1 className="mt-4 text-3xl font-bold text-white">{detail.title}</h1>
        <div className="mt-2 text-xs text-white/40">
          {detail.created_at ? new Date(detail.created_at).toLocaleString("zh-CN") : "未记录时间"}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
          <h2 className="text-sm font-semibold text-[#67E8F9]">适用问题</h2>
          <ExperienceMarkdown className="mt-3 text-sm leading-7 text-white/68">
            {detail.problem_pattern || "未记录"}
          </ExperienceMarkdown>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
          <h2 className="text-sm font-semibold text-[#D4FF12]">推荐方法</h2>
          <ExperienceMarkdown className="mt-3 text-sm leading-7 text-white/68">
            {detail.recommended_method || "未记录"}
          </ExperienceMarkdown>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
          <h2 className="text-sm font-semibold text-white">核验证据</h2>
          <ExperienceMarkdown className="mt-3 text-sm text-white/65">
            {evidenceMarkdown(detail.evidence_to_check)}
          </ExperienceMarkdown>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
          <h2 className="text-sm font-semibold text-white">限制与升级条件</h2>
          <ExperienceMarkdown className="mt-3 text-sm leading-7 text-white/68">
            {detail.when_to_escalate || "未记录"}
          </ExperienceMarkdown>
          <ExperienceMarkdown className="mt-3 text-sm leading-7 text-white/45">
            {detail.limitations || "未记录限制"}
          </ExperienceMarkdown>
        </div>
      </section>
    </div>
  )
}
