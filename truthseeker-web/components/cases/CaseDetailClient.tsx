"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ArrowLeft, ExternalLink, FileText, Film, Image as ImageIcon, Loader2, Mic, Trash2 } from "lucide-react"
import { deleteCase, formatCaseFileSize, getCaseDetail, requestCasePreviewUrl, type PublicCaseDetail } from "@/lib/cases"
import { getAuthToken } from "@/lib/auth"

function FileIcon({ modality }: { modality: string | null }) {
  if (modality === "audio") return <Mic className="h-5 w-5" />
  if (modality === "video") return <Film className="h-5 w-5" />
  if (modality === "image") return <ImageIcon className="h-5 w-5" />
  return <FileText className="h-5 w-5" />
}

type PreviewState = {
  signedUrl: string
  previewKind: string
  text: string
  charset: string | null
  detectedEncoding: string | null
  textUrl: string | null
}

function PreviewPane({ preview, mimeType }: { preview: PreviewState; mimeType: string | null }) {
  const url = preview.signedUrl
  const externalUrl = preview.previewKind === "text" && preview.textUrl ? preview.textUrl : url
  const openOriginalLink = (
    <a href={externalUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[#D4FF12]">
      <ExternalLink className="h-3.5 w-3.5" />
      新页面查看原检材
    </a>
  )

  if (preview.previewKind === "text" || mimeType?.startsWith("text/")) {
    return (
      <div className="mt-3 flex min-h-0 flex-1 flex-col rounded-lg border border-white/10 bg-black/35 p-3">
        <div className="mb-2 flex items-center justify-between gap-3 text-xs text-white/45">
          <span>文本预览 · UTF-8</span>
          {externalUrl && openOriginalLink}
        </div>
        <pre className="min-h-72 flex-1 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-white/75">
          {preview.text || "暂无可预览文本"}
        </pre>
      </div>
    )
  }
  if (mimeType?.startsWith("audio/")) {
    return (
      <div className="mt-3 flex min-h-0 flex-1 flex-col rounded-lg border border-white/10 bg-black/35 p-3">
        <div className="mb-2 flex justify-end text-xs">{openOriginalLink}</div>
        <audio controls src={url} className="w-full" />
      </div>
    )
  }
  if (mimeType?.startsWith("video/")) {
    return (
      <div className="mt-3 flex min-h-0 flex-1 flex-col rounded-lg border border-white/10 bg-black/35 p-3">
        <div className="mb-2 flex justify-end text-xs">{openOriginalLink}</div>
        <video controls src={url} className="aspect-video w-full rounded-lg border border-white/10 bg-black" />
      </div>
    )
  }
  if (mimeType?.startsWith("image/")) {
    return (
      <div className="mt-3 flex min-h-0 flex-1 flex-col rounded-lg border border-white/10 bg-black/35 p-3">
        <div className="mb-2 flex justify-end text-xs">{openOriginalLink}</div>
        {/* eslint-disable-next-line @next/next/no-img-element -- Signed Storage URLs are short-lived and not known in next.config image domains. */}
        <img src={url} alt="公开案例原始图片检材预览" className="max-h-96 w-full rounded-md object-contain" />
      </div>
    )
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm text-[#D4FF12]">
      <ExternalLink className="h-4 w-4" />
      打开预览
    </a>
  )
}

export function CaseDetailClient({ caseId }: { caseId: string }) {
  const router = useRouter()
  const [detail, setDetail] = useState<PublicCaseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({})
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)

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
      setPreviews((current) => ({ ...current, [fileId]: result }))
    } catch (err) {
      setError(err instanceof Error ? err.message : "检材预览链接生成失败")
    } finally {
      setPreviewLoading(null)
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      return
    }
    setDeleteLoading(true)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("请先登录")
      await deleteCase(caseId, token)
      router.push("/cases")
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败")
      setDeleteConfirm(false)
    } finally {
      setDeleteLoading(false)
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
      <div className="flex items-center justify-between">
        <Link href="/cases" className="inline-flex items-center gap-2 text-sm text-white/55 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
          返回公开案例库
        </Link>
        {detail.sourceKind !== "builtin" && (
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
            {deleteLoading ? "删除中" : deleteConfirm ? "确认删除" : "删除案例"}
          </button>
        )}
      </div>

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

      <section className="grid items-stretch gap-4 md:grid-cols-2">
        {detail.publicFiles.map((file) => {
          const preview = previews[file.id]
          return (
            <div key={file.id} className="flex h-full flex-col rounded-lg border border-white/10 bg-white/[0.04] p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3 text-white">
                  <FileIcon modality={file.modality} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{file.name}</div>
                    <div className="mt-1 text-xs text-white/45">{file.mimeType || "unknown"} · {formatCaseFileSize(file.sizeBytes)}</div>
                  </div>
                </div>
                {detail.sourceKind !== "builtin" && (
                  <button
                    type="button"
                    onClick={() => loadPreview(file.id)}
                    disabled={previewLoading === file.id}
                    className="rounded-lg border border-[#D4FF12]/25 px-3 py-1.5 text-xs text-[#D4FF12] disabled:opacity-50"
                  >
                    {previewLoading === file.id ? "生成中" : "短期预览"}
                  </button>
                )}
              </div>
              {preview && <PreviewPane preview={preview} mimeType={file.mimeType} />}
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
