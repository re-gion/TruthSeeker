"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { motion } from "motion/react"
import { AlertCircle, FileText, Film, Image as ImageIcon, Mic, Search, ShieldCheck } from "lucide-react"
import {
  CASE_CATEGORY_OPTIONS,
  type CaseCategory,
  formatCaseFileSize,
  getCaseList,
  type PublicCaseCard,
} from "@/lib/cases"

const PAGE_SIZE = 6

const STATIC_CASES = [
  {
    id: "builtin-audio-scam",
    title: "董事长语音诈骗",
    categoryLabel: "音频伪造",
    summary: "通过少量样本克隆高管声音，指使财务转账的典型音频 AIGC 伪造案例。",
    meta: "1:24 / High",
    icon: Mic,
    tone: "border-blue-400/25 bg-blue-500/8 text-blue-300",
  },
  {
    id: "builtin-video-faceswap",
    title: "Politician AI 伪造视频",
    categoryLabel: "视频伪造",
    summary: "使用高质量目标人脸替换源视频人物，用于散播虚假政治言论。",
    meta: "0:45 / Critical",
    icon: Film,
    tone: "border-red-400/25 bg-red-500/8 text-red-300",
  },
  {
    id: "builtin-mixed-phishing",
    title: "钓鱼链接+伪造截图",
    categoryLabel: "图文混合",
    summary: "结合生成的虚假聊天记录截图与恶意链接，进行多维度社会工程学攻击。",
    meta: "图片 / Medium",
    icon: ImageIcon,
    tone: "border-amber-400/25 bg-amber-500/8 text-amber-300",
  },
  {
    id: "builtin-text-news",
    title: "AI 生成新闻",
    categoryLabel: "文本生成",
    summary: "利用大语言模型批量生成的虚假舆情新闻，具有煽动性与迷惑性。",
    meta: "长文本 / Medium",
    icon: FileText,
    tone: "border-emerald-400/25 bg-emerald-500/8 text-emerald-300",
  },
]

function renderCategoryIcon(category: CaseCategory) {
  if (category === "audio_forgery") return <Mic className="h-5 w-5" />
  if (category === "video_forgery") return <Film className="h-5 w-5" />
  if (category === "image_forgery" || category === "image_text_mixed") return <ImageIcon className="h-5 w-5" />
  return <FileText className="h-5 w-5" />
}

function verdictTone(verdict: string) {
  if (verdict === "forged") return "text-red-300 border-red-400/25 bg-red-500/10"
  if (verdict === "suspicious") return "text-amber-300 border-amber-400/25 bg-amber-500/10"
  if (verdict === "authentic") return "text-emerald-300 border-emerald-400/25 bg-emerald-500/10"
  return "text-slate-300 border-slate-400/20 bg-slate-500/10"
}

function StaticCaseCard({ item }: { item: (typeof STATIC_CASES)[number] }) {
  const Icon = item.icon
  return (
    <Link href={`/cases/${item.id}`} className={`block rounded-lg border p-5 transition-colors hover:border-[#D4FF12]/35 ${item.tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <Icon className="h-6 w-6 shrink-0" />
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-white">{item.title}</h3>
            <div className="mt-1 text-xs text-white/55">{item.categoryLabel}</div>
          </div>
        </div>
        <span className="rounded border border-white/10 px-2 py-1 text-[11px] whitespace-nowrap text-white/50">内置</span>
      </div>
      <p className="mt-4 line-clamp-2 min-h-10 text-sm leading-5 text-white/68">{item.summary}</p>
      <div className="mt-5 border-t border-white/10 pt-3 text-xs text-white/45">{item.meta}</div>
    </Link>
  )
}

function RealCaseCard({ item }: { item: PublicCaseCard }) {
  const firstFile = item.publicFiles[0]
  return (
    <Link
      href={`/cases/${item.id}`}
      className="group rounded-lg border border-white/10 bg-white/[0.045] p-5 transition-colors hover:border-[#D4FF12]/35 hover:bg-white/[0.07]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#D4FF12]/20 bg-[#D4FF12]/8 text-[#D4FF12]">
            {renderCategoryIcon(item.mediaCategory)}
          </div>
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-white group-hover:text-[#D4FF12]">{item.title}</h3>
            <div className="mt-1 text-xs text-white/55">{item.categoryLabel}</div>
          </div>
        </div>
        <span className={`rounded border px-2 py-1 text-[11px] ${verdictTone(String(item.verdict))}`}>
          {item.verdictLabel}
        </span>
      </div>
      <p className="mt-4 line-clamp-2 min-h-10 text-sm leading-5 text-white/68">{item.summary}</p>
      <div className="mt-5 grid grid-cols-3 gap-3 border-t border-white/10 pt-3 text-xs text-white/45">
        <span>{item.confidenceLabel}</span>
        <span>{item.difficulty}</span>
        <span className="truncate">{firstFile ? formatCaseFileSize(firstFile.sizeBytes) : "无检材"}</span>
      </div>
    </Link>
  )
}

export function CaseLibraryClient() {
  const [category, setCategory] = useState<CaseCategory>("all")
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<PublicCaseCard[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getCaseList({ category, page, pageSize: PAGE_SIZE })
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setTotalPages(result.totalPages)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "公开案例库暂时不可用")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [category, page])

  const staticCases = useMemo(() => STATIC_CASES, [])

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-white/10 bg-black/30 p-4">
        <div className="flex flex-wrap items-center gap-2">
          {CASE_CATEGORY_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => {
                if (option.id === category && page === 1) return
                setLoading(true)
                setError(null)
                setCategory(option.id)
                setPage(1)
              }}
              className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                category === option.id
                  ? "border-[#D4FF12]/35 bg-[#D4FF12]/12 text-[#D4FF12]"
                  : "border-white/10 bg-white/[0.04] text-white/62 hover:bg-white/[0.07] hover:text-white"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white/72">
            <ShieldCheck className="h-4 w-4 text-[#D4FF12]" />
            真实公开案例
          </div>
          <div className="text-xs text-white/40">第 {page} / {totalPages} 页</div>
        </div>

        {error ? (
          <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 p-5 text-sm text-amber-200">
            <AlertCircle className="mr-2 inline h-4 w-4" />
            {error}
          </div>
        ) : loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-48 rounded-lg border border-white/10 bg-white/[0.04]" />
            ))}
          </div>
        ) : items.length ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((item, index) => (
              <motion.div key={item.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }}>
                <RealCaseCard item={item} />
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-8 text-center">
            <Search className="mx-auto h-8 w-8 text-white/30" />
            <div className="mt-3 text-sm text-white/62">当前分类还没有真实公开案例</div>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
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
      </section>

      <section>
        <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white/72">
          <FileText className="h-4 w-4 text-white/45" />
          内置展示案例
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {staticCases.map((item) => (
            <StaticCaseCard key={item.id} item={item} />
          ))}
        </div>
      </section>
    </div>
  )
}
