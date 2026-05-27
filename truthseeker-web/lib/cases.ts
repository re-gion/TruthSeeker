export type CaseCategory =
  | "all"
  | "text_generation"
  | "image_forgery"
  | "image_text_mixed"
  | "audio_forgery"
  | "video_forgery"

export type CaseVerdict = "authentic" | "suspicious" | "forged" | "inconclusive" | string

export interface PublicCaseFile {
  id: string
  name: string
  mimeType: string | null
  modality: string | null
  sizeBytes: number | null
  storagePath: null
}

export interface PublicCaseCard {
  id: string
  taskId: string | null
  title: string
  mediaCategory: CaseCategory
  categoryLabel: string
  summary: string
  verdict: CaseVerdict
  verdictLabel: string
  confidenceOverall: number | null
  confidenceLabel: string
  difficulty: string
  publicFiles: PublicCaseFile[]
  publishedAt: string | null
}

export interface PublicCaseDetail extends PublicCaseCard {
  reportMarkdown: string
}

interface BackendCase {
  id?: string | null
  task_id?: string | null
  title?: string | null
  media_category?: CaseCategory | null
  summary?: string | null
  verdict?: CaseVerdict | null
  confidence_overall?: number | null
  difficulty?: string | null
  public_files?: Array<{
    id?: string | null
    name?: string | null
    mime_type?: string | null
    modality?: string | null
    size_bytes?: number | null
    storage_path?: string | null
  }>
  published_at?: string | null
  report_markdown?: string | null
}

interface BackendListResponse {
  items?: BackendCase[]
  page?: number
  page_size?: number
  total?: number
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export const CASE_CATEGORY_OPTIONS: Array<{ id: CaseCategory; label: string }> = [
  { id: "all", label: "全部" },
  { id: "text_generation", label: "文本生成" },
  { id: "image_forgery", label: "图像伪造" },
  { id: "image_text_mixed", label: "图文混合" },
  { id: "audio_forgery", label: "音频伪造" },
  { id: "video_forgery", label: "视频伪造" },
]

export const CASE_CATEGORY_LABELS = Object.fromEntries(
  CASE_CATEGORY_OPTIONS.map((option) => [option.id, option.label]),
) as Record<CaseCategory, string>

const VERDICT_LABELS: Record<string, string> = {
  authentic: "内容真实",
  suspicious: "高度可疑",
  forged: "确认伪造",
  inconclusive: "无法判定",
}

function readCategory(value: unknown): CaseCategory {
  return CASE_CATEGORY_OPTIONS.some((option) => option.id === value) ? value as CaseCategory : "text_generation"
}

export function formatCaseFileSize(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "未知大小"
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function normalizeCase(row: BackendCase): PublicCaseCard {
  const mediaCategory = readCategory(row.media_category)
  const confidence = typeof row.confidence_overall === "number" ? row.confidence_overall : null
  return {
    id: row.id || "",
    taskId: row.task_id || null,
    title: row.title || "未命名公开案例",
    mediaCategory,
    categoryLabel: CASE_CATEGORY_LABELS[mediaCategory],
    summary: row.summary || "暂无摘要",
    verdict: row.verdict || "inconclusive",
    verdictLabel: VERDICT_LABELS[String(row.verdict || "inconclusive")] || "无法判定",
    confidenceOverall: confidence,
    confidenceLabel: confidence == null ? "未标注" : `${(confidence * 100).toFixed(1)}%`,
    difficulty: row.difficulty || "Medium",
    publicFiles: (row.public_files || []).map((file, index) => ({
      id: file.id || `file-${index + 1}`,
      name: file.name || `检材 ${index + 1}`,
      mimeType: file.mime_type || null,
      modality: file.modality || null,
      sizeBytes: typeof file.size_bytes === "number" ? file.size_bytes : null,
      storagePath: null,
    })),
    publishedAt: row.published_at || null,
  }
}

export function normalizeCaseListResponse(payload: BackendListResponse) {
  const page = Math.max(payload.page || 1, 1)
  const pageSize = Math.max(payload.page_size || 6, 1)
  const total = Math.max(payload.total || 0, 0)
  return {
    items: (payload.items || []).map(normalizeCase),
    page,
    pageSize,
    total,
    totalPages: Math.max(Math.ceil(total / pageSize), 1),
  }
}

export async function getCaseList(
  params: { category?: CaseCategory; page?: number; pageSize?: number },
  fetchImpl: typeof fetch = fetch,
) {
  const search = new URLSearchParams({
    category: params.category || "all",
    page: String(params.page || 1),
    page_size: String(params.pageSize || 6),
  })
  const resp = await fetchImpl(`${API_BASE}/api/v1/cases?${search.toString()}`, { cache: "no-store" })
  if (!resp.ok) throw new Error("公开案例库暂时不可用")
  return normalizeCaseListResponse(await resp.json())
}

export async function getCaseDetail(caseId: string, fetchImpl: typeof fetch = fetch): Promise<PublicCaseDetail> {
  const resp = await fetchImpl(`${API_BASE}/api/v1/cases/${caseId}`, { cache: "no-store" })
  if (!resp.ok) throw new Error("公开案例不存在或暂时不可用")
  const payload = await resp.json() as BackendCase
  return {
    ...normalizeCase(payload),
    reportMarkdown: payload.report_markdown || "",
  }
}

export async function requestCasePreviewUrl(caseId: string, fileId: string, fetchImpl: typeof fetch = fetch) {
  const resp = await fetchImpl(`${API_BASE}/api/v1/cases/${caseId}/preview-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId }),
  })
  if (!resp.ok) throw new Error("检材预览链接生成失败")
  const payload = await resp.json() as { signed_url?: string; signedUrl?: string; expires_in?: number }
  return {
    signedUrl: payload.signed_url || payload.signedUrl || "",
    expiresIn: payload.expires_in || 600,
  }
}
