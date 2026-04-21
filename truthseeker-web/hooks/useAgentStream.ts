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
    | { type: "consultation_required"; task_id: string; reason?: string; payload?: unknown }
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
}

export interface AgentHistoryResponse {
    task?: Record<string, unknown> | null
    agent_logs?: Record<string, unknown>[]
    analysis_states?: Record<string, unknown>[]
    report?: Record<string, unknown> | null
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
    start: () => void
    resume: () => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
const EMPTY_FILES: Record<string, unknown>[] = []

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null
}

function readRecord(value: unknown): Record<string, unknown> | null {
    return isObject(value) ? value : null
}

function readNumber(value: unknown): number | undefined {
    return typeof value === "number" && Number.isFinite(value) ? value : undefined
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
        type: typeof value.type === "string" ? value.type : "timeline_update",
        content,
        timestamp: typeof value.timestamp === "string" ? value.timestamp : new Date().toISOString(),
        round: typeof value.round === "number" ? value.round : undefined,
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
    }
}

export function mapAgentHistoryToStreamState(history: AgentHistoryResponse): StreamStateFromHistory {
    const logs = Array.isArray(history.agent_logs)
        ? history.agent_logs.map(readPersistedLogEntry).filter((entry): entry is AgentLogEntry => entry !== null)
        : []

    let forensicsResult: Record<string, unknown> | null = null
    let osintResult: Record<string, unknown> | null = null
    let challengerFeedback: Record<string, unknown> | null = null
    let finalVerdict: Record<string, unknown> | null = null
    let currentRound = 1

    const states = Array.isArray(history.analysis_states) ? history.analysis_states : []
    for (const row of states) {
        currentRound = Math.max(currentRound, readNumber(row.round_number) ?? 1)
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

    return {
        logs,
        forensicsResult,
        osintResult,
        challengerFeedback,
        agentWeights: agentWeights ?? {},
        finalVerdict,
        currentRound,
        isComplete: status === "completed" || Boolean(finalVerdict),
        isWaitingConsultation: status === "waiting_consultation",
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
    maxRounds = 3,
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
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const startedRef = useRef(false)

    const processEvent = useCallback((event: AgentEvent) => {
        setEvents(prev => [...prev, event])

        if (event.type === "start") {
            if (event.max_rounds) setMaxRoundsState(event.max_rounds)
            setErrorMessage(null)
            setIsWaitingConsultation(false)
        } else if (event.type === "node_start") {
            setCurrentNode(event.node)
        } else if (event.type === "agent_log") {
            setLogs(prev => [...prev, event.log])
        } else if (event.type === "timeline_update") {
            const timelineEntries = readTimelineEntries(event)
            if (timelineEntries.length > 0) {
                setLogs(prev => [...prev, ...timelineEntries])
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
        } else if (event.type === "consultation_required") {
            const reason = event.reason || "检测证据存在高冲突，等待专家会诊"
            setIsWaitingConsultation(true)
            setIsRunning(false)
            setCurrentNode(null)
            setLogs(prev => [
                ...prev,
                {
                    agent: "challenger",
                    type: "consultation_required",
                    content: reason,
                    timestamp: new Date().toISOString(),
                },
            ])
        } else if (event.type === "consultation_resumed") {
            setIsWaitingConsultation(false)
            setIsRunning(true)
            setLogs(prev => [
                ...prev,
                {
                    agent: "system",
                    type: "consultation_resumed",
                    content: "主持人已恢复研判流程",
                    timestamp: new Date().toISOString(),
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
    }, [])

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
        if (role !== "expert") return
        let cancelled = false

        async function loadAgentHistory() {
            try {
                const url = new URL(`${API_BASE}/api/v1/consultation/${taskId}/agent-history`)
                if (inviteToken) url.searchParams.set("invite_token", inviteToken)
                const response = await fetch(url.toString())
                if (!response.ok) throw new Error(`history HTTP ${response.status}`)
                const history = await response.json() as AgentHistoryResponse
                if (cancelled) return

                const mapped = mapAgentHistoryToStreamState(history)
                setLogs((prev) => prev.length > 0 ? prev : mapped.logs)
                setForensicsResult(mapped.forensicsResult)
                setOsintResult(mapped.osintResult)
                setChallengerFeedback(mapped.challengerFeedback)
                setFinalVerdict(mapped.finalVerdict)
                setAgentWeights(mapped.agentWeights)
                setCurrentRound(mapped.currentRound)
                setIsComplete(mapped.isComplete)
                setIsWaitingConsultation(mapped.isWaitingConsultation)
                setIsRunning(!mapped.isComplete && !mapped.isWaitingConsultation)
            } catch (err) {
                if (!cancelled) {
                    console.error("[useAgentStream] Failed to load agent history:", err)
                    setIsRunning(false)
                }
            }
        }

        void loadAgentHistory()

        return () => {
            cancelled = true
        }
    }, [inviteToken, role, taskId])

    useEffect(() => {
        if (role === 'expert') {
            setIsRunning(true)
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
        start,
        resume,
    }
}
