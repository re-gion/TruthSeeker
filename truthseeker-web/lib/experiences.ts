export type ExperienceAgent = "forensics" | "osint" | "challenger" | "all"

export interface ExperienceDraft {
  title: string
  target_agents: string[]
  problem_pattern: string
  recommended_method: string
  evidence_to_check: string[]
  when_to_escalate: string
  limitations: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

export function readExperienceDraftsFromSession(session: unknown): ExperienceDraft[] {
  const summaryPayload = asRecord(asRecord(session)?.summary_payload)
  const source = summaryPayload?.experience_drafts
  if (!Array.isArray(source)) return []
  return source.flatMap((item): ExperienceDraft[] => {
    const row = asRecord(item)
    if (!row) return []
    const title = nonEmptyString(row.title)
    const problemPattern = nonEmptyString(row.problem_pattern)
    const recommendedMethod = nonEmptyString(row.recommended_method)
    const targetAgents = Array.isArray(row.target_agents)
      ? row.target_agents.map(String).map((value) => value.trim()).filter(Boolean)
      : []
    if (!title || !problemPattern || !recommendedMethod || targetAgents.length === 0) return []
    return [{
      title,
      target_agents: targetAgents,
      problem_pattern: problemPattern,
      recommended_method: recommendedMethod,
      evidence_to_check: Array.isArray(row.evidence_to_check)
        ? row.evidence_to_check.map(String).map((value) => value.trim()).filter(Boolean)
        : [],
      when_to_escalate: nonEmptyString(row.when_to_escalate) ?? "",
      limitations: nonEmptyString(row.limitations) ?? "",
    }]
  })
}

export function readExperienceDraftStatusFromSession(session: unknown): string | null {
  const summaryPayload = asRecord(asRecord(session)?.summary_payload)
  const error = nonEmptyString(summaryPayload?.experience_drafts_error)
  if (error) return error
  const skillExecution = asRecord(summaryPayload?.experience_skill_execution)
  if (skillExecution?.execution_status === "check_failed") {
    return "个人经验草稿未通过输出检查，请重新发起协同或重试检测"
  }
  if (Array.isArray(summaryPayload?.experience_drafts)) {
    if (summaryPayload.experience_drafts.length > 0) {
      return readExperienceDraftsFromSession(session).length === 0
        ? "个人经验草稿格式无效，暂时无法展示"
        : null
    }
    return "本次协同未生成新的个人经验草稿，可能没有可复用结论或已与现有经验重复"
  }
  return null
}

export interface ExperienceEntry extends ExperienceDraft {
  id: string
  source_task_id: string | null
  source_session_id: string | null
  source_collaboration_session_id: string | null
  created_at: string | null
  updated_at: string | null
}

interface BackendListResponse {
  items?: Array<Partial<ExperienceEntry>>
  page?: number
  page_size?: number
  total?: number
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export const EXPERIENCE_AGENT_OPTIONS: Array<{ id: ExperienceAgent; label: string }> = [
  { id: "all", label: "全部" },
  { id: "forensics", label: "取证 Agent" },
  { id: "osint", label: "溯源 Agent" },
  { id: "challenger", label: "质询 Agent" },
]

export function normalizeExperienceEntry(row: Partial<ExperienceEntry>): ExperienceEntry {
  const sourceSessionId = row.source_collaboration_session_id || row.source_session_id || null
  return {
    id: String(row.id || ""),
    source_task_id: row.source_task_id || null,
    source_session_id: sourceSessionId,
    source_collaboration_session_id: sourceSessionId,
    title: row.title || "未命名个人经验",
    target_agents: Array.isArray(row.target_agents) ? row.target_agents.map(String) : [],
    problem_pattern: row.problem_pattern || "",
    recommended_method: row.recommended_method || "",
    evidence_to_check: Array.isArray(row.evidence_to_check) ? row.evidence_to_check.map(String) : [],
    when_to_escalate: row.when_to_escalate || "",
    limitations: row.limitations || "",
    created_at: row.created_at || null,
    updated_at: row.updated_at || null,
  }
}

export function normalizeExperienceList(payload: BackendListResponse) {
  const page = Math.max(payload.page || 1, 1)
  const pageSize = Math.max(payload.page_size || 12, 1)
  const total = Math.max(payload.total || 0, 0)
  return {
    items: (payload.items || []).map(normalizeExperienceEntry),
    page,
    pageSize,
    total,
    totalPages: Math.max(Math.ceil(total / pageSize), 1),
  }
}

export async function getExperienceList(
  params: { agent?: ExperienceAgent; q?: string; page?: number; pageSize?: number },
  token: string,
  fetchImpl: typeof fetch = fetch,
) {
  const search = new URLSearchParams({
    agent: params.agent || "all",
    q: params.q || "",
    page: String(params.page || 1),
    page_size: String(params.pageSize || 12),
  })
  const resp = await fetchImpl(`${API_BASE}/api/v1/experiences?${search.toString()}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error("个人经验库暂时不可用")
  return normalizeExperienceList(await resp.json())
}

export async function getExperienceDetail(entryId: string, token: string, fetchImpl: typeof fetch = fetch) {
  const resp = await fetchImpl(`${API_BASE}/api/v1/experiences/${entryId}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error("个人经验不存在或暂时不可用")
  return normalizeExperienceEntry(await resp.json())
}

export interface ConfirmExperienceResult {
  status?: "ok" | "partial" | "failed"
  inserted: number
  indexed_chunks: number
  failed?: Array<{ title?: string; error?: string; indexing_failed?: boolean }>
}

export function remainingExperienceDraftsAfterConfirm(
  drafts: ExperienceDraft[],
  result: ConfirmExperienceResult,
): ExperienceDraft[] {
  const failures = result.failed || []
  if (failures.length === 0) {
    return result.status === "failed" ? drafts : []
  }
  const failedTitles = new Set(
    failures.map((item) => nonEmptyString(item.title)).filter((title): title is string => Boolean(title)),
  )
  if (failedTitles.size === 0) return drafts
  return drafts.filter((draft) => failedTitles.has(draft.title.trim()))
}

export async function confirmExperienceDrafts(
  payload: { task_id: string; session_id: string; drafts: ExperienceDraft[] },
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ConfirmExperienceResult> {
  const resp = await fetchImpl(`${API_BASE}/api/v1/experiences/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    let detail = "个人经验入库失败"
    try { detail = (await resp.json()).detail || detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return (await resp.json()) as ConfirmExperienceResult
}

export async function deleteExperience(entryId: string, token: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  const resp = await fetchImpl(`${API_BASE}/api/v1/experiences/${entryId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) {
    let detail = "个人经验删除失败"
    try { detail = (await resp.json()).detail || detail } catch { /* ignore */ }
    throw new Error(detail)
  }
}
