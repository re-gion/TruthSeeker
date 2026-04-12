"use client"

import { useEffect, useRef, useState, useCallback } from "react"

export type AgentEvent =
    | { type: "start"; task_id: string; max_rounds?: number }
    | { type: "node_start"; node: string }
    | { type: "agent_log"; node: string; log: AgentLogEntry }
    | { type: "evidence_update"; evidence: unknown[]; node?: string }
    | { type: "challenges_update"; challenges: unknown[] }
    | { type: "forensics_result"; result: Record<string, unknown> }
    | { type: "osint_result"; result: Record<string, unknown> }
    | { type: "challenger_feedback"; feedback: Record<string, unknown> }
    | { type: "weights_update"; weights: Record<string, number> }
    | { type: "round_update"; round: number }
    | { type: "final_verdict"; verdict: Record<string, unknown> }
    | { type: "node_complete"; node: string }
    | { type: "complete"; task_id: string }

export interface AgentLogEntry {
    agent: string
    type: string
    content: string
    timestamp: string
    round?: number
}

interface UseAgentStreamOptions {
    taskId: string
    inputType?: string
    fileUrl?: string
    autoStart?: boolean
    maxRounds?: number
    role?: 'host' | 'expert' | 'viewer'
    channel?: any
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
    start: () => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export function useAgentStream({
    taskId,
    inputType = "video",
    fileUrl,
    autoStart = true,
    maxRounds = 3,
    role = 'host',
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
    const abortRef = useRef<AbortController | null>(null)
    const startedRef = useRef(false)

    const processEvent = useCallback((event: AgentEvent) => {
        setEvents(prev => [...prev, event])

        if (event.type === "start") {
            if (event.max_rounds) setMaxRoundsState(event.max_rounds)
        } else if (event.type === "node_start") {
            setCurrentNode(event.node)
        } else if (event.type === "agent_log") {
            setLogs(prev => [...prev, event.log])
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
        } else if (event.type === "complete") {
            setIsComplete(true)
            setIsRunning(false)
            setCurrentNode(null)
        }
    }, [])

    const start = useCallback(async () => {
        if (startedRef.current) return
        startedRef.current = true
        setIsRunning(true)
        setIsComplete(false)

        abortRef.current = new AbortController()

        try {
            const body = JSON.stringify({
                task_id: taskId,
                input_type: inputType,
                file_url: fileUrl || `mock://${taskId}`,
                max_rounds: maxRounds,
            })

            const response = await fetch(`${API_BASE}/api/v1/detect/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
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
                            channel.send({
                                type: 'broadcast',
                                event: 'agent_stream',
                                payload: event
                            }).catch((err: any) => {
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
            }
        } finally {
            setIsRunning(false)
        }
    }, [taskId, inputType, fileUrl, maxRounds])

    useEffect(() => {
        if (role === 'expert') {
            setIsRunning(true)
            // Expert just listens to broadcast channel
            if (channel) {
                const subscription = channel.on('broadcast', { event: 'agent_stream' }, (payload: any) => {
                    const event = payload.payload as AgentEvent
                    processEvent(event)
                })
                return () => {
                    // unsubscribe handled by channel wrapper
                }
            }
        } else {
            // Host starts the execution stream
            if (autoStart) start()
            return () => abortRef.current?.abort()
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
        start,
    }
}
