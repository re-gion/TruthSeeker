"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { RealtimeChannel } from "@supabase/supabase-js"
import { getAuthToken } from "@/lib/auth"

export type AgentEvent =
    | { type: "start"; task_id: string; max_rounds?: number }
    | { type: "node_start"; node: string }
    | { type: "agent_log"; node: string; log: AgentLogEntry }
    | { type: "timeline_update"; entry?: AgentLogEntry; log?: AgentLogEntry; events?: unknown[]; node?: string; round?: number }
    | { type: "evidence_update"; evidence: unknown[]; node?: string }
    | { type: "challenges_update"; challenges: unknown[] }
    | { type: "forensics_result"; result: Record<string, unknown> }
    | { type: "osint_result"; result: Record<string, unknown> }
    | { type: "challenger_feedback"; feedback: Record<string, unknown> }
    | { type: "weights_update"; weights: Record<string, number> }
    | { type: "round_update"; round: number }
    | { type: "final_verdict"; verdict: Record<string, unknown> }
    | { type: "consultation_required"; task_id: string; reason?: string; payload?: unknown; session?: unknown }
    | { type: "consultation_approval_required"; task_id: string; reason?: string; payload?: unknown; session?: unknown }
    | { type: "consultation_started"; task_id: string; reason?: string; payload?: unknown; session?: unknown }
    | { type: "consultation_summary_pending"; task_id: string; reason?: string; payload?: unknown; summary?: unknown; session?: unknown }
    | { type: "consultation_summary_confirmed"; task_id: string; reason?: string; payload?: unknown; summary?: unknown; session?: unknown }
    | { type: "consultation_skipped"; task_id: string; reason?: string; payload?: unknown; session?: unknown }
    | { type: "consultation_resumed"; task_id: string }
    | { type: "task_failed"; task_id?: string; message: string; detail?: unknown }
    | { type: "node_complete"; node: string }
    | { type: "error"; message: string; detail?: unknown }
    | { type: "complete"; task_id: string }

export interface AgentLogEntry {
    agent: string
    type: string
    content: string
    timestamp: string
    round?: number
    phase?: string
    phaseRound?: number
    sourceKind?: "agent" | "timeline" | "audit" | "system"
    action?: string
}

export interface AgentHistoryResponse {
    task?: Record<string, unknown> | null
    agent_logs?: Record<string, unknown>[]
    analysis_states?: Record<string, unknown>[]
    audit_logs?: Record<string, unknown>[]
    consultation_session?: Record<string, unknown> | null
    report?: Record<string, unknown> | null
}

export type ConsultationStatus =
    | "idle"
    | "approval_required"
    | "started"
    | "summary_pending"
    | "summary_confirmed"
    | "skipped"
    | "resumed"

export interface ConsultationLink {
    label: string
    url: string
}

export interface ConsultationContext {
    background?: string
    progress?: string
    blockers: string[]
    helpNeeded?: string
    sampleLinks: ConsultationLink[]
}

export interface ConsultationState {
    status: ConsultationStatus
    taskId?: string
    reason?: string
    context: ConsultationContext
    session?: Record<string, unknown>
    history: Record<string, unknown>[]
    summaryDraft?: string
    summaryConfirmed?: string
    lastEventType?: string
}

export interface StreamStateFromHistory {
    logs: AgentLogEntry[]
    forensicsResult: Record<string, unknown> | null
    osintResult: Record<string, unknown> | null
    challengerFeedback: Record<string, unknown> | null
    agentWeights: Record<string, number>
    finalVerdict: Record<string, unknown> | null
    currentRound: number
    isComplete: boolean
    isWaitingConsultation: boolean
    consultationState: ConsultationState
}

interface UseAgentStreamOptions {
    taskId: string
    inputType?: string
    fileUrl?: string
    files?: Record<string, unknown>[]
    casePrompt?: string
    priorityFocus?: string
    autoStart?: boolean
    maxRounds?: number
    role?: 'host' | 'expert' | 'viewer'
    inviteToken?: string | null
    channel?: RealtimeChannel | null
}

interface UseAgentStreamReturn {
    events: AgentEvent[]
    logs: AgentLogEntry[]
    forensicsResult: Record<string, unknown> | null
    osintResult: Record<string, unknown> | null
    challengerFeedback: Record<string, unknown> | null
    agentWeights: Record<string, number>
    finalVerdict: Record<string, unknown> | null
    currentRound: number
    maxRounds: number
    isRunning: boolean
    isComplete: boolean
    currentNode: string | null
    isWaitingConsultation: boolean
    errorMessage: string | null
    consultationState: ConsultationState
    start: () => void
    resume: () => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
const EMPTY_FILES: Record<string, unknown>[] = []

const EMPTY_CONSULTATION_CONTEXT: ConsultationContext = {
    blockers: [],
    sampleLinks: [],
}

const INITIAL_CONSULTATION_STATE: ConsultationState = {
    status: "idle",
    context: EMPTY_CONSULTATION_CONTEXT,
    history: [],
}

type ConsultationEvent = Extract<AgentEvent, {
    type:
        | "consultation_required"
        | "consultation_approval_required"
        | "consultation_started"
        | "consultation_summary_pending"
        | "consultation_summary_confirmed"
        | "consultation_skipped"
        | "consultation_resumed"
}>

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null
}

function readRecord(value: unknown): Record<string, unknown> | null {
    return isObject(value) ? value : null
}

function readNumber(value: unknown): number | undefined {
    return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function readString(value: unknown): string | undefined {
    return typeof value === "string" && value.trim() ? value : undefined
}

function readStringArray(value: unknown): string[] {
    if (typeof value === "string" && value.trim()) return [value.trim()]
    if (!Array.isArray(value)) return []
    return value
        .map(item => typeof item === "string" ? item.trim() : undefined)
        .filter((item): item is string => Boolean(item))
}

function readRecordArray(value: unknown): Record<string, unknown>[] {
    if (!Array.isArray(value)) return []
    return value.filter((item): item is Record<string, unknown> => isObject(item))
}

function pickString(...values: unknown[]) {
    for (const value of values) {
        const text = readString(value)
        if (text) return text
    }
    return undefined
}

function pickStringArray(...values: unknown[]) {
    for (const value of values) {
        const list = readStringArray(value)
        if (list.length > 0) return list
    }
    return []
}

function readProgressSummary(value: unknown): string | undefined {
    const text = readString(value)
    if (text) return text
    if (!isObject(value)) return undefined
    const fragments: string[] = []
    for (const [key, item] of Object.entries(value)) {
        if (item === undefined || item === null || item === "") continue
        fragments.push(`${key}=${String(item)}`)
    }
    return fragments.length > 0 ? fragments.join("，") : undefined
}

function readConsultationLinks(value: unknown): ConsultationLink[] {
    if (!Array.isArray(value)) return []
    return value
        .map((item, index): ConsultationLink | null => {
            if (typeof item === "string" && item.trim()) {
                return { label: `样本 ${index + 1}`, url: item.trim() }
            }
            if (!isObject(item)) return null
            const url = pickString(item.url, item.href, item.link, item.file_url, item.signed_url, item.signedUrl)
            if (!url) return null
            return {
                label: pickString(item.title, item.label, item.name) ?? `样本 ${index + 1}`,
                url,
            }
        })
        .filter((item): item is ConsultationLink => item !== null)
}

function mergeConsultationContext(current: ConsultationContext, incoming: Partial<ConsultationContext>): ConsultationContext {
    return {
        background: incoming.background ?? current.background,
        progress: incoming.progress ?? current.progress,
        blockers: incoming.blockers && incoming.blockers.length > 0 ? incoming.blockers : current.blockers,
        helpNeeded: incoming.helpNeeded ?? current.helpNeeded,
        sampleLinks: incoming.sampleLinks && incoming.sampleLinks.length > 0 ? incoming.sampleLinks : current.sampleLinks,
    }
}

function readSourceKind(value: unknown, fallback: AgentLogEntry["sourceKind"]): AgentLogEntry["sourceKind"] {
    return value === "agent" || value === "timeline" || value === "audit" || value === "system"
        ? value
        : fallback
}

function timestampValue(entry: AgentLogEntry) {
    const time = Date.parse(entry.timestamp)
    return Number.isFinite(time) ? time : 0
}

function sortTimelineEntries(entries: AgentLogEntry[]) {
    return [...entries].sort((a, b) => timestampValue(a) - timestampValue(b))
}

function mergeTimelineEntries(current: AgentLogEntry[], incoming: AgentLogEntry[]) {
    const merged = [...current]
    const keys = new Set(
        current.map(entry => `${entry.timestamp}|${entry.agent}|${entry.type}|${entry.content}|${entry.phase ?? ""}|${entry.phaseRound ?? ""}`),
    )
    for (const entry of incoming) {
        const key = `${entry.timestamp}|${entry.agent}|${entry.type}|${entry.content}|${entry.phase ?? ""}|${entry.phaseRound ?? ""}`
        if (keys.has(key)) continue
        keys.add(key)
        merged.push(entry)
    }
    return sortTimelineEntries(merged)
}

function readLogEntry(value: unknown): AgentLogEntry | null {
    if (!isObject(value)) return null

    const agent = typeof value.agent === "string" ? value.agent : typeof value.node === "string" ? value.node : "system"
    const content =
        typeof value.content === "string"
            ? value.content
            : typeof value.message === "string"
                ? value.message
                : typeof value.text === "string"
                    ? value.text
                    : ""

    return {
        agent,
        type: readString(value.type) ?? readString(value.event_type) ?? "timeline_update",
        content,
        timestamp: typeof value.timestamp === "string" ? value.timestamp : new Date().toISOString(),
        round: typeof value.round === "number" ? value.round : undefined,
        phase: readString(value.phase),
        phaseRound: readNumber(value.phase_round) ?? readNumber(value.phaseRound),
        sourceKind: readSourceKind(value.source_kind, "timeline"),
        action: readString(value.action),
    }
}

function readPersistedLogEntry(value: unknown): AgentLogEntry | null {
    if (!isObject(value)) return null
    const content = typeof value.content === "string" ? value.content : ""
    if (!content) return null
    return {
        agent: typeof value.agent_name === "string" ? value.agent_name : typeof value.agent === "string" ? value.agent : "system",
        type: typeof value.log_type === "string" ? value.log_type : typeof value.type === "string" ? value.type : "action",
        content,
        timestamp: typeof value.timestamp === "string" ? value.timestamp : typeof value.created_at === "string" ? value.created_at : new Date().toISOString(),
        round: readNumber(value.round_number) ?? readNumber(value.round),
        phase: readString(value.phase),
        phaseRound: readNumber(value.phase_round) ?? readNumber(value.phaseRound),
        sourceKind: "agent",
    }
}

function readTimelineEventsFromState(value: unknown): AgentLogEntry[] {
    if (!isObject(value)) return []
    const board = readRecord(value.evidence_board)
    const events = Array.isArray(board?.timeline_events) ? board.timeline_events : []
    const entries: AgentLogEntry[] = []
    for (const event of events) {
        const entry = readLogEntry(event)
        if (!entry) continue
        entries.push({
            ...entry,
            timestamp: entry.timestamp || readString(value.created_at) || new Date().toISOString(),
            sourceKind: "timeline",
        })
    }
    return entries
}

function formatAuditContent(value: Record<string, unknown>) {
    const action = readString(value.action) ?? "audit"
    const metadata = readRecord(value.metadata)
    const fragments: string[] = []
    for (const key of ["input_type", "file_count", "round", "verdict", "has_final_verdict"]) {
        const item = metadata?.[key]
        if (item === undefined || item === null) continue
        fragments.push(`${key}=${String(item)}`)
    }
    return fragments.length > 0 ? `${action}（${fragments.join(", ")}）` : action
}

function readAuditLogEntry(value: unknown): AgentLogEntry | null {
    if (!isObject(value)) return null
    const action = readString(value.action) ?? "audit"
    return {
        agent: readString(value.agent) ?? readString(value.actor_role) ?? "system",
        type: "audit",
        content: formatAuditContent(value),
        timestamp: readString(value.created_at) ?? readString(value.timestamp) ?? new Date().toISOString(),
        sourceKind: "audit",
        action,
    }
}

function consultationStatusForEvent(type: ConsultationEvent["type"]): ConsultationStatus {
    if (type === "consultation_approval_required") return "approval_required"
    if (type === "consultation_required") return "started"
    if (type === "consultation_started") return "started"
    if (type === "consultation_summary_pending") return "summary_pending"
    if (type === "consultation_summary_confirmed") return "summary_confirmed"
    if (type === "consultation_skipped") return "skipped"
    if (type === "consultation_resumed") return "resumed"
    return "idle"
}

function readConsultationContext(payload: Record<string, unknown> | null): Partial<ConsultationContext> {
    const session = readRecord(payload?.session)
    const context = readRecord(payload?.context)
        ?? readRecord(session?.context_payload)
        ?? readRecord(session?.context)
        ?? readRecord(payload?.consultation)
        ?? payload
    const sampleSource = context?.sample_links ?? context?.sampleLinks ?? context?.samples ?? context?.evidence_links ?? context?.links

    return {
        background: pickString(context?.background, context?.case_background, context?.background_notes, context?.caseBackground),
        progress: pickString(context?.progress, context?.current_progress, context?.status_summary, context?.statusSummary)
            ?? readProgressSummary(context?.progress_summary),
        blockers: pickStringArray(context?.blockers, context?.current_blocker, context?.blocking_points, context?.open_questions, context?.conflicts),
        helpNeeded: pickString(context?.help_needed, context?.helpNeeded, context?.requested_help, context?.assistance_needed)
            ?? readStringArray(context?.help_needed).join("；")
            ?? undefined,
        sampleLinks: readConsultationLinks(sampleSource),
    }
}

function readConsultationSummary(event: ConsultationEvent, payload: Record<string, unknown> | null) {
    const payloadSummary = readRecord(payload?.summary)
    const session = readRecord(payload?.session)
    const sessionSummary = readRecord(session?.summary_payload)
    const directSummary = readRecord("summary" in event ? event.summary : undefined)
    return pickString(
        "summary" in event ? event.summary : undefined,
        directSummary?.text,
        directSummary?.content,
        payload?.summary_draft,
        payload?.draft_summary,
        payload?.summaryDraft,
        payloadSummary?.text,
        payloadSummary?.content,
        sessionSummary?.user_confirmed_summary,
        sessionSummary?.confirmed_summary,
        sessionSummary?.generated_summary,
    )
}

export function normalizeConsultationEvent(event: ConsultationEvent, current: ConsultationState = INITIAL_CONSULTATION_STATE): ConsultationState {
    const payload = readRecord("payload" in event ? event.payload : undefined)
    const eventSession = readRecord("session" in event ? event.session : undefined)
    const session = readRecord(payload?.session) ?? eventSession ?? current.session
    const history = readRecordArray(payload?.history ?? payload?.messages)
    const status = consultationStatusForEvent(event.type)
    const summary = readConsultationSummary(event, payload)
    const contextPayload = session ? { ...(payload ?? {}), session } : payload

    return {
        status,
        taskId: "task_id" in event ? event.task_id : current.taskId,
        reason: "reason" in event ? event.reason ?? current.reason : current.reason,
        context: mergeConsultationContext(current.context, readConsultationContext(contextPayload)),
        session,
        history: history.length > 0 ? history : current.history,
        summaryDraft: status === "summary_pending" || summary ? summary ?? current.summaryDraft : current.summaryDraft,
        summaryConfirmed: status === "summary_confirmed" ? summary ?? current.summaryDraft ?? current.summaryConfirmed : current.summaryConfirmed,
        lastEventType: event.type,
    }
}

function consultationLogContent(state: ConsultationState, fallback: string) {
    if (state.status === "approval_required") return state.reason ?? fallback
    if (state.status === "started") return "Commander 已开启专家会诊，并作为主持汇总人工意见"
    if (state.status === "summary_pending") return "会诊摘要待用户确认"
    if (state.status === "summary_confirmed") return "用户已确认会诊摘要，人工意见可回注研判流程"
    if (state.status === "skipped") return state.reason ?? "用户跳过本轮会诊"
    return fallback
}

export function canModerateConsultation(role: "host" | "expert" | "viewer") {
    return role === "host"
}

function consultationStatusFromSession(session: Record<string, unknown> | null, taskStatus: string): ConsultationStatus {
    const sessionStatus = readString(session?.status)
    if (sessionStatus === "waiting_user_approval") return "approval_required"
    if (sessionStatus === "active" || sessionStatus === "requested") return "started"
    if (sessionStatus === "summary_pending") return "summary_pending"
    if (sessionStatus === "summary_confirmed") return "summary_confirmed"
    if (sessionStatus === "skipped") return "skipped"
    if (taskStatus === "waiting_consultation_approval") return "approval_required"
    if (taskStatus === "waiting_consultation") return "started"
    return "idle"
}

function isConsultationWaiting(status: string, consultationStatus: ConsultationStatus) {
    return status === "waiting_consultation"
        || status === "waiting_consultation_approval"
        || consultationStatus === "approval_required"
        || consultationStatus === "started"
        || consultationStatus === "summary_pending"
}

export function mapAgentHistoryToStreamState(history: AgentHistoryResponse): StreamStateFromHistory {
    const persistedLogs = Array.isArray(history.agent_logs)
        ? history.agent_logs.map(readPersistedLogEntry).filter((entry): entry is AgentLogEntry => entry !== null)
        : []
    const auditLogs = Array.isArray(history.audit_logs)
        ? history.audit_logs.map(readAuditLogEntry).filter((entry): entry is AgentLogEntry => entry !== null)
        : []

    let forensicsResult: Record<string, unknown> | null = null
    let osintResult: Record<string, unknown> | null = null
    let challengerFeedback: Record<string, unknown> | null = null
    let finalVerdict: Record<string, unknown> | null = null
    let currentRound = 1
    const timelineLogs: AgentLogEntry[] = []

    const states = Array.isArray(history.analysis_states) ? history.analysis_states : []
    for (const row of states) {
        currentRound = Math.max(currentRound, readNumber(row.round_number) ?? 1)
        timelineLogs.push(...readTimelineEventsFromState(row))
        const snapshot = readRecord(row.result_snapshot)
        if (!snapshot) continue
        forensicsResult = readRecord(snapshot.forensics) ?? forensicsResult
        osintResult = readRecord(snapshot.osint) ?? osintResult
        challengerFeedback = readRecord(snapshot.challenger) ?? challengerFeedback
        finalVerdict = readRecord(snapshot.final_verdict) ?? finalVerdict
    }

    const report = readRecord(history.report)
    const task = readRecord(history.task)
    finalVerdict = readRecord(report?.verdict_payload) ?? finalVerdict ?? readRecord(task?.result)

    const agentWeights = readRecord(finalVerdict?.agent_weights) as Record<string, number> | null
    const status = typeof task?.status === "string" ? task.status : ""
    const metadata = readRecord(task?.metadata)
    const consultationSession = readRecord(history.consultation_session)
    const consultationContext = readRecord(metadata?.consultation) ?? readRecord(metadata?.consultation_context)
    const consultationStatus = consultationStatusFromSession(consultationSession, status)
    const summaryPayload = readRecord(consultationSession?.summary_payload)
    const consultationState: ConsultationState = {
        ...INITIAL_CONSULTATION_STATE,
        status: consultationStatus,
        taskId: readString(task?.id),
        reason: readString(consultationSession?.reason) ?? readString(metadata?.consultation_reason),
        context: mergeConsultationContext(EMPTY_CONSULTATION_CONTEXT, readConsultationContext({
            ...(consultationContext ?? {}),
            session: consultationSession ?? undefined,
        })),
        session: consultationSession ?? undefined,
        summaryDraft: readString(summaryPayload?.generated_summary),
        summaryConfirmed: readString(summaryPayload?.user_confirmed_summary) ?? readString(summaryPayload?.confirmed_summary),
    }

    return {
        logs: sortTimelineEntries([...auditLogs, ...persistedLogs, ...timelineLogs]),
        forensicsResult,
        osintResult,
        challengerFeedback,
        agentWeights: agentWeights ?? {},
        finalVerdict,
        currentRound,
        isComplete: status === "completed" || Boolean(finalVerdict),
        isWaitingConsultation: isConsultationWaiting(status, consultationStatus),
        consultationState,
    }
}

function readTimelineEntry(event: Extract<AgentEvent, { type: "timeline_update" }>): AgentLogEntry | null {
    return readLogEntry(event.entry ?? event.log ?? event)
}

function readTimelineEntries(event: Extract<AgentEvent, { type: "timeline_update" }>): AgentLogEntry[] {
    if (Array.isArray(event.events) && event.events.length > 0) {
        return event.events
            .map((entry) => readLogEntry(entry))
            .filter((entry): entry is AgentLogEntry => entry !== null)
    }

    const singleEntry = readTimelineEntry(event)
    return singleEntry ? [singleEntry] : []
}

export function useAgentStream({
    taskId,
    inputType = "video",
    fileUrl,
    files = EMPTY_FILES,
    casePrompt = "",
    priorityFocus = "balanced",
    autoStart = true,
    maxRounds = 5,
    role = 'host',
    inviteToken,
    channel
}: UseAgentStreamOptions): UseAgentStreamReturn {
    const [events, setEvents] = useState<AgentEvent[]>([])
    const [logs, setLogs] = useState<AgentLogEntry[]>([])
    const [forensicsResult, setForensicsResult] = useState<Record<string, unknown> | null>(null)
    const [osintResult, setOsintResult] = useState<Record<string, unknown> | null>(null)
    const [challengerFeedback, setChallengerFeedback] = useState<Record<string, unknown> | null>(null)
    const [agentWeights, setAgentWeights] = useState<Record<string, number>>({})
    const [finalVerdict, setFinalVerdict] = useState<Record<string, unknown> | null>(null)
    const [currentRound, setCurrentRound] = useState(1)
    const [maxRoundsState, setMaxRoundsState] = useState(maxRounds)
    const [isRunning, setIsRunning] = useState(false)
    const [isComplete, setIsComplete] = useState(false)
    const [currentNode, setCurrentNode] = useState<string | null>(null)
    const [isWaitingConsultation, setIsWaitingConsultation] = useState(false)
    const [consultationState, setConsultationState] = useState<ConsultationState>(INITIAL_CONSULTATION_STATE)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const startedRef = useRef(false)
    const consultationStateRef = useRef<ConsultationState>(INITIAL_CONSULTATION_STATE)

    const updateConsultationState = useCallback((next: ConsultationState) => {
        consultationStateRef.current = next
        setConsultationState(next)
    }, [])

    const processEvent = useCallback((event: AgentEvent) => {
        setEvents(prev => [...prev, event])

        if (event.type === "start") {
            if (event.max_rounds) setMaxRoundsState(event.max_rounds)
            setErrorMessage(null)
            setIsWaitingConsultation(false)
        } else if (event.type === "node_start") {
            setCurrentNode(event.node)
        } else if (event.type === "agent_log") {
            setLogs(prev => mergeTimelineEntries(prev, [{ ...event.log, sourceKind: event.log.sourceKind ?? "agent" }]))
        } else if (event.type === "timeline_update") {
            const timelineEntries = readTimelineEntries(event)
            if (timelineEntries.length > 0) {
                setLogs(prev => mergeTimelineEntries(prev, timelineEntries))
            }
        } else if (event.type === "forensics_result") {
            setForensicsResult(event.result)
        } else if (event.type === "osint_result") {
            setOsintResult(event.result)
        } else if (event.type === "challenger_feedback") {
            setChallengerFeedback(event.feedback)
        } else if (event.type === "weights_update") {
            setAgentWeights(event.weights)
        } else if (event.type === "round_update") {
            setCurrentRound(event.round)
        } else if (event.type === "final_verdict") {
            setFinalVerdict(event.verdict)
        } else if (
            event.type === "consultation_required" ||
            event.type === "consultation_approval_required" ||
            event.type === "consultation_started" ||
            event.type === "consultation_summary_pending" ||
            event.type === "consultation_summary_confirmed" ||
            event.type === "consultation_skipped"
        ) {
            const nextConsultationState = normalizeConsultationEvent(event, consultationStateRef.current)
            updateConsultationState(nextConsultationState)
            const reason = event.reason || "检测证据存在高冲突，等待专家会诊"
            const waiting = event.type !== "consultation_summary_confirmed" && event.type !== "consultation_skipped"
            setIsWaitingConsultation(waiting)
            setIsRunning(false)
            setCurrentNode(null)
            setLogs(prev => [
                ...prev,
                {
                    agent: "commander",
                    type: event.type,
                    content: consultationLogContent(nextConsultationState, reason),
                    timestamp: new Date().toISOString(),
                    sourceKind: "system",
                },
            ])
        } else if (event.type === "consultation_resumed") {
            updateConsultationState(normalizeConsultationEvent(event, consultationStateRef.current))
            setIsWaitingConsultation(false)
            setIsRunning(true)
            setLogs(prev => [
                ...prev,
                {
                    agent: "system",
                    type: "consultation_resumed",
                    content: "主持人已恢复研判流程",
                    timestamp: new Date().toISOString(),
                    sourceKind: "system",
                },
            ])
        } else if (event.type === "task_failed") {
            setErrorMessage(event.message)
            setIsRunning(false)
            setIsWaitingConsultation(false)
            setCurrentNode(null)
            setLogs(prev => [
                ...prev,
                {
                    agent: "system",
                    type: "error",
                    content: event.message,
                    timestamp: new Date().toISOString(),
                },
            ])
        } else if (event.type === "error") {
            setErrorMessage(event.message)
            setLogs(prev => [
                ...prev,
                {
                    agent: "system",
                    type: "error",
                    content: event.message,
                    timestamp: new Date().toISOString(),
                },
            ])
            setIsRunning(false)
            setCurrentNode(null)
        } else if (event.type === "complete") {
            setIsComplete(true)
            setIsRunning(false)
            setIsWaitingConsultation(false)
            setCurrentNode(null)
        }
    }, [updateConsultationState])

    const runStream = useCallback(async (resume = false) => {
        if (startedRef.current && !resume) return
        if (!resume) startedRef.current = true
        setIsRunning(true)
        setIsComplete(false)
        setErrorMessage(null)

        abortRef.current = new AbortController()

        try {
            const authToken = await getAuthToken()
            const headers: Record<string, string> = { "Content-Type": "application/json" }
            if (authToken) headers.Authorization = `Bearer ${authToken}`

            const body = JSON.stringify({
                task_id: taskId,
                input_type: inputType,
                file_url: fileUrl || `mock://${taskId}`,
                files,
                case_prompt: casePrompt,
                priority_focus: priorityFocus,
                max_rounds: maxRounds,
                resume,
            })

            const response = await fetch(`${API_BASE}/api/v1/detect/stream`, {
                method: "POST",
                headers,
                body,
                signal: abortRef.current.signal,
            })

            if (!response.ok || !response.body) {
                throw new Error(`HTTP ${response.status}`)
            }

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ""

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split("\n")
                buffer = lines.pop() || ""

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue
                    try {
                        const event = JSON.parse(line.slice(6)) as AgentEvent
                        processEvent(event)

                        // Broadcast via Supabase if host
                        if (role === 'host' && channel) {
                            void channel.send({
                                type: 'broadcast',
                                event: 'agent_stream',
                                payload: event,
                            }).catch((err: unknown) => {
                                console.error('Failed to broadcast event:', err)
                            })
                        }
                    } catch {
                        // ignore parse errors
                    }
                }
            }
        } catch (err: unknown) {
            if (err instanceof Error && err.name !== "AbortError") {
                console.error("[useAgentStream] Error:", err)
                setErrorMessage(err.message)
            }
        } finally {
            setIsRunning(false)
        }
    }, [taskId, inputType, fileUrl, files, casePrompt, priorityFocus, maxRounds, channel, role, processEvent])

    const start = useCallback(() => {
        void runStream(false)
    }, [runStream])

    const resume = useCallback(() => {
        void runStream(true)
    }, [runStream])

    useEffect(() => {
        let cancelled = false

        async function loadAgentHistory() {
            try {
                const url = new URL(`${API_BASE}/api/v1/consultation/${taskId}/agent-history`)
                if (inviteToken) url.searchParams.set("invite_token", inviteToken)
                const headers: Record<string, string> = {}
                const authToken = await getAuthToken()
                if (authToken) headers.Authorization = `Bearer ${authToken}`
                const response = await fetch(url.toString(), { headers })
                if (!response.ok) throw new Error(`history HTTP ${response.status}`)
                const history = await response.json() as AgentHistoryResponse
                if (cancelled) return

                const mapped = mapAgentHistoryToStreamState(history)
                setLogs((prev) => mergeTimelineEntries(prev, mapped.logs))
                setForensicsResult(mapped.forensicsResult)
                setOsintResult(mapped.osintResult)
                setChallengerFeedback(mapped.challengerFeedback)
                setFinalVerdict(mapped.finalVerdict)
                setAgentWeights(mapped.agentWeights)
                setCurrentRound(mapped.currentRound)
                setIsComplete(mapped.isComplete)
                setIsWaitingConsultation(mapped.isWaitingConsultation)
                updateConsultationState(mapped.consultationState)
                if (mapped.isComplete) {
                    startedRef.current = true
                    setIsRunning(false)
                } else if (role === "expert") {
                    setIsRunning(!mapped.isWaitingConsultation)
                }
            } catch (err) {
                if (!cancelled) {
                    console.error("[useAgentStream] Failed to load agent history:", err)
                    if (role === "expert") setIsRunning(false)
                }
            }
        }

        void loadAgentHistory()

        return () => {
            cancelled = true
        }
    }, [inviteToken, role, taskId, updateConsultationState])

    useEffect(() => {
        if (role === 'expert') {
            // Expert just listens to broadcast channel
            if (channel) {
                channel.on('broadcast', { event: 'agent_stream' }, (payload: { payload?: unknown }) => {
                    const event = payload.payload as AgentEvent | undefined
                    if (!event) return
                    processEvent(event)
                })
                return () => { void channel.unsubscribe() }
            }
            return () => {}
        } else {
            // Host starts the execution stream
            if (autoStart) start()
            return () => {
                abortRef.current?.abort()
                startedRef.current = false
            }
        }
    }, [autoStart, start, role, channel, processEvent])

    return {
        events,
        logs,
        forensicsResult,
        osintResult,
        challengerFeedback,
        agentWeights,
        finalVerdict,
        currentRound,
        maxRounds: maxRoundsState,
        isRunning,
        isComplete,
        currentNode,
        isWaitingConsultation,
        errorMessage,
        consultationState,
        start,
        resume,
    }
}
