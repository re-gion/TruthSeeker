"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ArrowLeft, ExternalLink, FileText, Film, Image as ImageIcon, Loader2, Mic } from "lucide-react"
import { formatCaseFileSize, getCaseDetail, requestCasePreviewUrl, type PublicCaseDetail } from "@/lib/cases"

function FileIcon({ modality }: { modality: string | null }) {
  if (modality === "audio") return <Mic className="h-5 w-5" />
  if (modality === "video") return <Film className="h-5 w-5" />
  if (modality === "image") return <ImageIcon className="h-5 w-5" />
  return <FileText className="h-5 w-5" />
}

function PreviewPane({ url, mimeType }: { url: string; mimeType: string | null }) {
  if (mimeType?.startsWith("audio/")) {
    return <audio controls src={url} className="mt-3 w-full" />
  }
  if (mimeType?.startsWith("video/")) {
    return <video controls src={url} className="mt-3 aspect-video w-full rounded-lg border border-white/10 bg-black" />
  }
  if (mimeType?.startsWith("image/")) {
    return <object data={url} type={mimeType} className="mt-3 aspect-video w-full rounded-lg border border-white/10 bg-black" />
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm text-[#D4FF12]">
      <ExternalLink className="h-4 w-4" />
      打开预览
    </a>
  )
}

export function CaseDetailClient({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<PublicCaseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({})
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getCaseDetail(caseId)
      .then((result) => {
        if (!cancelled) setDetail(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "公开案例不存在或暂时不可用")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [caseId])

  async function loadPreview(fileId: string) {
    setPreviewLoading(fileId)
    try {
      const result = await requestCasePreviewUrl(caseId, fileId)
      setPreviewUrls((current) => ({ ...current, [fileId]: result.signedUrl }))
    } catch (err) {
      setError(err instanceof Error ? err.message : "检材预览链接生成失败")
    } finally {
      setPreviewLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center text-white/55">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        正在加载公开案例
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-6 text-red-200">
        {error || "公开案例不存在"}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Link href="/cases" className="inline-flex items-center gap-2 text-sm text-white/55 hover:text-white">
        <ArrowLeft className="h-4 w-4" />
        返回公开案例库
      </Link>

      <section className="rounded-lg border border-white/10 bg-white/[0.045] p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="text-sm text-[#D4FF12]">{detail.categoryLabel}</div>
            <h1 className="mt-2 text-3xl font-bold text-white">{detail.title}</h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-white/62">{detail.summary}</p>
          </div>
          <div className="grid min-w-56 gap-2 rounded-lg border border-white/10 bg-black/25 p-4 text-sm text-white/62">
            <span>裁决：{detail.verdictLabel}</span>
            <span>置信度：{detail.confidenceLabel}</span>
            <span>难度：{detail.difficulty}</span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {detail.publicFiles.map((file) => {
          const previewUrl = previewUrls[file.id]
          return (
            <div key={file.id} className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3 text-white">
                  <FileIcon modality={file.modality} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{file.name}</div>
                    <div className="mt-1 text-xs text-white/45">{file.mimeType || "unknown"} · {formatCaseFileSize(file.sizeBytes)}</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => loadPreview(file.id)}
                  disabled={previewLoading === file.id}
                  className="rounded-lg border border-[#D4FF12]/25 px-3 py-1.5 text-xs text-[#D4FF12] disabled:opacity-50"
                >
                  {previewLoading === file.id ? "生成中" : "短期预览"}
                </button>
              </div>
              {previewUrl && <PreviewPane url={previewUrl} mimeType={file.mimeType} />}
            </div>
          )
        })}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.045] p-6">
        <h2 className="mb-5 text-lg font-semibold text-white">研判报告</h2>
        <div className="report-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail.reportMarkdown}</ReactMarkdown>
        </div>
      </section>
    </div>
  )
}
