"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { motion, AnimatePresence } from "motion/react"
import { createClient } from "@/lib/supabase/client"
import { getAuthToken } from "@/lib/auth"
import { UserRole } from "@/hooks/useRealtimeSession"
import { canModerateConsultation, ConsultationState } from "@/hooks/useAgentStream"
import { confirmExperienceDrafts, type ExperienceDraft } from "@/lib/experiences"
import {
    filterDisplayComments,
    mergeConsultationComments,
    normalizeConsultationMessage,
    type ConsultationComment,
    type PanelRole,
} from "@/lib/consultation-messages"
import Image from "next/image"

export type ExpertComment = ConsultationComment

interface RoleConfig {
    label: string
    shortLabel: string
    avatar: string
    bubbleBg: string
    bubbleBorder: string
    bubbleText: string
    dotColor: string
    nameColor: string
}

const ROLE_CONFIG: Record<PanelRole, RoleConfig> = {
    host: {
        label: "用户",
        shortLabel: "用",
        avatar: "/host-avatar.png",
        bubbleBg: "bg-[#6366F1]/20",
        bubbleBorder: "border-[#6366F1]/30",
        bubbleText: "text-indigo-100",
        dotColor: "bg-[#6366F1]",
        nameColor: "text-[#818CF8]",
    },
    expert: {
        label: "专家",
        shortLabel: "专",
        avatar: "/expert-avatar.png",
        bubbleBg: "bg-[#D4FF12]/10",
        bubbleBorder: "border-[#D4FF12]/20",
        bubbleText: "text-gray-100",
        dotColor: "bg-[#D4FF12]",
        nameColor: "text-[#D4FF12]",
    },
    viewer: {
        label: "访客",
        shortLabel: "访",
        avatar: "/host-avatar.png",
        bubbleBg: "bg-white/5",
        bubbleBorder: "border-white/10",
        bubbleText: "text-gray-400",
        dotColor: "bg-gray-500",
        nameColor: "text-gray-500",
    },
    commander: {
        label: "研判指挥Agent/主持人",
        shortLabel: "研",
        avatar: "/agent-icons/commander.svg",
        bubbleBg: "bg-[#06B6D4]/10",
        bubbleBorder: "border-[#06B6D4]/25",
        bubbleText: "text-cyan-50",
        dotColor: "bg-[#06B6D4]",
        nameColor: "text-[#67E8F9]",
    },
}

const DEFAULT_MESSAGE_METADATA = {
    messageType: "analysis",
    anchorAgent: "commander",
    confidence: 0.7,
}

function formatTime(timestamp: string) {
    try {
        const d = new Date(timestamp)
        return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
    } catch {
        return ""
    }
}

function getTempUserId() {
    if (typeof window === "undefined") return "anon"

    const storedUserId = window.localStorage.getItem("temp_user_id")
    if (storedUserId) return storedUserId

    const userId = window.crypto?.randomUUID?.() || Math.random().toString(36).substring(7)
    window.localStorage.setItem("temp_user_id", userId)
    return userId
}

function readString(value: unknown): string | undefined {
    return typeof value === "string" && value.trim() ? value : undefined
}

function getSessionId(consultationState?: ConsultationState) {
    const session = consultationState?.session
    return session && typeof session.id === "string" ? session.id : undefined
}

function summaryDraftFromSession(session: Record<string, unknown> | undefined) {
    const payload = session?.summary_payload
    if (!payload || typeof payload !== "object") return undefined
    const summary = payload as Record<string, unknown>
    return readString(summary.generated_summary) ?? readString(summary.user_confirmed_summary)
}

interface ExpertTask {
    question: string
    expectedOutput?: string
}

function readExpertTasks(context: ConsultationState["context"] | undefined): ExpertTask[] {
    if (!context || typeof context !== "object") return []
    if (Array.isArray(context.expertTasks)) return context.expertTasks
    const record = context as unknown as Record<string, unknown>
    const source = record.expert_tasks ?? record.expertTasks ?? record.tasks
    if (!Array.isArray(source)) return []

    return source
        .map((item): ExpertTask | null => {
            if (typeof item === "string" && item.trim()) {
                return { question: item.trim() }
            }
            if (!item || typeof item !== "object") return null
            const task = item as Record<string, unknown>
            const question = readString(task.question)
                ?? readString(task.problem)
                ?? readString(task.title)
                ?? readString(task.prompt)
                ?? readString(task.description)
            if (!question) return null
            return {
                question,
                expectedOutput: readString(task.expected_output)
                    ?? readString(task.expectedOutput)
                    ?? readString(task.output)
                    ?? readString(task.expectation),
            }
        })
        .filter((item): item is ExpertTask => item !== null)
}

function firstHelpNeeded(context: ConsultationState["context"] | undefined) {
    return helpNeededItems(context)[0]
}

function helpNeededItems(context: ConsultationState["context"] | undefined): string[] {
    const value = context?.helpNeeded as unknown
    if (Array.isArray(value)) return value
    if (typeof value === "string" && value.trim()) return [value.trim()]
    return []
}

export function ExpertPanel({
    taskId,
    inviteToken,
    currentRole,
    consultationState,
    onResume,
}: {
    taskId: string
    inviteToken?: string | null
    currentRole: UserRole
    consultationState?: ConsultationState
    onResume?: () => void
}) {
    const [comments, setComments] = useState<ExpertComment[]>([])
    const [inputValue, setInputValue] = useState("")
    const [contextExpanded, setContextExpanded] = useState(false)
    const [editableSummary, setEditableSummary] = useState("")
    const [editableExperienceDrafts, setEditableExperienceDrafts] = useState<ExperienceDraft[]>([])
    const [experiencePending, setExperiencePending] = useState(false)
    const [experienceStatus, setExperienceStatus] = useState<string | null>(null)
    const [statusOverride, setStatusOverride] = useState<ConsultationState["status"] | null>(null)
    const [moderationPending, setModerationPending] = useState(false)
    const sentIdsRef = useRef<Set<string>>(new Set())
    const scrollRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const canModerate = canModerateConsultation(currentRole)
    const effectiveStatus = statusOverride ?? consultationState?.status
    const supabase = useMemo(() => {
        if (typeof window === "undefined") return null
        return createClient()
    }, [])
    const broadcastChannel = useMemo(() => {
        return supabase?.channel(`task:${taskId}`) ?? null
    }, [supabase, taskId])

    // 自动滚动到底部
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [comments])

    // 输入框自动高度
    useEffect(() => {
        const el = textareaRef.current
        if (!el) return
        el.style.height = "auto"
        el.style.height = `${Math.min(el.scrollHeight, 120)}px`
    }, [inputValue])

    useEffect(() => {
        if (consultationState?.summaryDraft) {
            setEditableSummary(consultationState.summaryDraft)
        }
    }, [consultationState?.summaryDraft])

    useEffect(() => {
        setEditableExperienceDrafts(consultationState?.experienceDrafts ?? [])
        setExperienceStatus(null)
    }, [consultationState?.lastEventType, consultationState?.experienceDrafts])

    useEffect(() => {
        setStatusOverride(null)
    }, [consultationState?.lastEventType, consultationState?.status])

    const loadMessages = useCallback(async () => {
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        try {
            const authToken = await getAuthToken()
            const url = new URL(`${apiBase}/api/v1/consultation/${taskId}/messages`)
            if (inviteToken) url.searchParams.set("invite_token", inviteToken)
            const headers: Record<string, string> = {}
            if (authToken) headers.Authorization = `Bearer ${authToken}`
            const response = await fetch(url.toString(), { headers })
            if (!response.ok) return
            const data = await response.json()
            if (!Array.isArray(data.messages)) return

            const history = (data.messages as unknown[])
                .filter((item: unknown): item is Record<string, unknown> => typeof item === "object" && item !== null)
                .map((item: Record<string, unknown>) => normalizeConsultationMessage(item))
            setComments(prev => mergeConsultationComments(prev, history))
        } catch {
            // 历史消息加载失败不影响实时会诊输入。
        }
    }, [inviteToken, taskId])

    useEffect(() => {
        const channel = broadcastChannel
        if (!channel) return

        channel
            .on("broadcast", { event: "expert_comment" }, (payload: { payload?: unknown }) => {
                if (!payload.payload || typeof payload.payload !== "object") return
                const comment = normalizeConsultationMessage(payload.payload as Record<string, unknown>)
                if (sentIdsRef.current.has(comment.id)) return
                setComments(prev => mergeConsultationComments(prev, [comment]))
            })
            .on(
                "postgres_changes",
                { event: "INSERT", schema: "public", table: "consultation_messages", filter: `task_id=eq.${taskId}` },
                (payload: { new?: unknown }) => {
                    if (!payload.new || typeof payload.new !== "object") return
                    const comment = normalizeConsultationMessage(payload.new as Record<string, unknown>)
                    setComments(prev => mergeConsultationComments(prev, [comment]))
                },
            )
            .on(
                "postgres_changes",
                { event: "UPDATE", schema: "public", table: "consultation_messages", filter: `task_id=eq.${taskId}` },
                (payload: { new?: unknown }) => {
                    if (!payload.new || typeof payload.new !== "object") return
                    const comment = normalizeConsultationMessage(payload.new as Record<string, unknown>)
                    setComments(prev => mergeConsultationComments(prev, [comment]))
                },
            )

        void loadMessages()

        const pollTimer = window.setInterval(() => {
            void loadMessages()
        }, 10000)

        void channel.subscribe()

        return () => {
            window.clearInterval(pollTimer)
            void channel.unsubscribe()
        }
    }, [broadcastChannel, loadMessages, taskId])

    const canSendMessage = currentRole !== "viewer"

    const sendConsultationMessage = async (comment: ExpertComment) => {
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        const authToken = await getAuthToken()
        const headers: Record<string, string> = { "Content-Type": "application/json" }
        if (authToken) headers.Authorization = `Bearer ${authToken}`
        const backendRole = comment.role === "host" ? "user" : comment.role
        return fetch(`${apiBase}/api/v1/consultation/${taskId}/inject`, {
            method: "POST",
            headers,
            body: JSON.stringify({
                message: comment.text,
                role: backendRole,
                expert_name: comment.authorId,
                invite_token: inviteToken ?? undefined,
                session_id: getSessionId(consultationState),
                message_type: DEFAULT_MESSAGE_METADATA.messageType,
                anchor_agent: DEFAULT_MESSAGE_METADATA.anchorAgent,
                confidence: DEFAULT_MESSAGE_METADATA.confidence,
                metadata: {
                    client_message_id: comment.clientMessageId,
                },
            }),
        })
    }

    const broadcastConsultationEvent = (event: Record<string, unknown>) => {
        if (!broadcastChannel) return
        void broadcastChannel.send({
            type: "broadcast",
            event: "agent_stream",
            payload: event,
        })
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!canSendMessage || !inputValue.trim() || !broadcastChannel) return
        const clientMessageId = window.crypto?.randomUUID?.() || Math.random().toString(36).substring(7)

        const newComment: ExpertComment = {
            id: `temp-${clientMessageId}`,
            clientMessageId,
            authorId: getTempUserId(),
            role: currentRole,
            text: inputValue.trim(),
            timestamp: new Date().toISOString(),
            messageType: DEFAULT_MESSAGE_METADATA.messageType,
            anchorAgent: DEFAULT_MESSAGE_METADATA.anchorAgent,
            confidence: DEFAULT_MESSAGE_METADATA.confidence,
            optimistic: true,
        }

        sentIdsRef.current.add(newComment.id)
        setComments(prev => mergeConsultationComments(prev, [newComment]))

        // Realtime broadcast for other clients
        void broadcastChannel.send({
            type: 'broadcast',
            event: 'expert_comment',
            payload: newComment
        })

        // Inject into backend agent state via consultation API, then reconcile with the persisted row.
        sendConsultationMessage(newComment)
            .then(async response => {
                if (!response.ok) return
                const data = await response.json().catch(() => null) as { message_id?: unknown } | null
                const messageId = typeof data?.message_id === "string" ? data.message_id : null
                if (messageId) {
                    setComments(prev => mergeConsultationComments(prev, [{
                        ...newComment,
                        id: messageId,
                        optimistic: false,
                    }]))
                }
                void loadMessages()
            })
            .catch(err => console.error("Failed to inject expert message:", err))

        setInputValue("")
    }

    const callSessionAction = async (action: "approve" | "skip" | "close" | "summary", body?: Record<string, unknown>) => {
        const sessionId = getSessionId(consultationState)
        if (!sessionId) throw new Error("missing consultation session")
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        const authToken = await getAuthToken()
        const headers: Record<string, string> = { "Content-Type": "application/json" }
        if (authToken) headers.Authorization = `Bearer ${authToken}`
        const response = await fetch(`${apiBase}/api/v1/consultation/${taskId}/sessions/${sessionId}/${action}`, {
            method: "POST",
            headers,
            body: JSON.stringify(body ?? {}),
        })
        if (!response.ok) throw new Error(`consultation ${action} HTTP ${response.status}`)
        return response.json() as Promise<{ session?: Record<string, unknown> }>
    }

    const updateExperienceDraft = (index: number, patch: Partial<ExperienceDraft>) => {
        setEditableExperienceDrafts((current) => current.map((item, itemIndex) => (
            itemIndex === index ? { ...item, ...patch } : item
        )))
    }

    const removeExperienceDraft = (index: number) => {
        setEditableExperienceDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))
    }

    const handleConfirmExperienceDrafts = async () => {
        const sessionId = getSessionId(consultationState)
        if (!sessionId || experiencePending) return
        const drafts = editableExperienceDrafts
            .map((draft) => ({
                ...draft,
                title: draft.title.trim(),
                target_agents: draft.target_agents.map((agent) => agent.trim()).filter(Boolean),
                problem_pattern: draft.problem_pattern.trim(),
                recommended_method: draft.recommended_method.trim(),
                evidence_to_check: draft.evidence_to_check.map((item) => item.trim()).filter(Boolean),
                when_to_escalate: draft.when_to_escalate.trim(),
                limitations: draft.limitations.trim(),
            }))
            .filter((draft) => draft.title && draft.target_agents.length > 0 && draft.problem_pattern && draft.recommended_method)
        if (drafts.length === 0) {
            setExperienceStatus("没有可入库的个人经验草稿")
            return
        }
        setExperiencePending(true)
        try {
            const token = await getAuthToken()
            if (!token) throw new Error("请先登录")
            const result = await confirmExperienceDrafts({
                task_id: taskId,
                session_id: sessionId,
                drafts,
            }, token)
            setEditableExperienceDrafts([])
            setExperienceStatus(`已入库 ${result.inserted} 条个人经验，索引 ${result.indexed_chunks} 个向量块`)
        } catch (err) {
            setExperienceStatus(err instanceof Error ? err.message : "个人经验入库失败")
        } finally {
            setExperiencePending(false)
        }
    }

    const handleModerationAction = async (action: "approve" | "skip" | "end_consultation" | "confirm_summary") => {
        if (!canModerate || moderationPending) return
        setModerationPending(true)
        try {
            if (action === "approve") {
                const data = await callSessionAction("approve")
                setStatusOverride("started")
                broadcastConsultationEvent({
                    type: "consultation_started",
                    task_id: taskId,
                    session: data.session,
                    payload: { session: data.session },
                })
                return
            }
            if (action === "skip") {
                const data = await callSessionAction("skip", { reason: "用户选择跳过本次重复专家会诊" })
                setStatusOverride("skipped")
                broadcastConsultationEvent({
                    type: "consultation_skipped",
                    task_id: taskId,
                    reason: "用户选择跳过本次重复专家会诊",
                    session: data.session,
                    payload: { session: data.session, summary: data.session?.summary_payload },
                })
                onResume?.()
                return
            }
            if (action === "end_consultation") {
                const data = await callSessionAction("close")
                const draft = summaryDraftFromSession(data.session)
                if (draft) setEditableSummary(draft)
                setStatusOverride("summary_pending")
                broadcastConsultationEvent({
                    type: "consultation_summary_pending",
                    task_id: taskId,
                    session: data.session,
                    summary: data.session?.summary_payload,
                    payload: { session: data.session, summary: data.session?.summary_payload },
                })
                return
            }
            if (action === "confirm_summary") {
                const summary = editableSummary.trim()
                if (!summary) return
                const data = await callSessionAction("summary", { summary })
                setStatusOverride("summary_confirmed")
                broadcastConsultationEvent({
                    type: "consultation_summary_confirmed",
                    task_id: taskId,
                    session: data.session,
                    summary: data.session?.summary_payload,
                    payload: { session: data.session, summary: data.session?.summary_payload },
                })
                onResume?.()
            }
        } catch (err) {
            console.error("Failed to send moderation action:", err)
        } finally {
            setModerationPending(false)
        }
    }

    const context = consultationState?.context
    const expertTasks = readExpertTasks(context)
    const helpNeeded = helpNeededItems(context)
    const showApprovalActions = canModerate && effectiveStatus === "approval_required"
    const canEndConsultation = canModerate && effectiveStatus === "started"
    const canConfirmSummary = canModerate && effectiveStatus === "summary_pending"
    const hasContext = Boolean(
        expertTasks.length > 0 ||
        context?.background ||
        context?.progress ||
        helpNeeded.length > 0 ||
        (context?.blockers.length ?? 0) > 0 ||
        (context?.sampleLinks.length ?? 0) > 0,
    )

    return (
        <div className="flex flex-col h-full bg-black/40 border border-white/10 rounded-xl overflow-hidden backdrop-blur-md relative">
            {/* 顶部标题栏 */}
            <div className="px-3 py-2.5 border-b border-white/10 bg-white/5 flex justify-between items-start gap-3">
                <div>
                    <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                        <span className="text-[#D4FF12]">●</span> 专家会诊频道
                    </span>
                    <div className="mt-1 text-[10px] text-gray-500">
                        Commander 主持 · 用户决策 · 专家协助
                    </div>
                </div>
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">
                    {effectiveStatus ? effectiveStatus.replaceAll("_", " ") : "realtime"}
                </span>
            </div>

            {(hasContext || consultationState?.reason) && (
                <div className="border-b border-white/10 bg-[#060B12]/80 p-3 space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] font-semibold text-[#D4FF12]">会诊上下文</span>
                            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/55">
                                {expertTasks.length} 项专家任务
                            </span>
                        </div>
                        <button
                            type="button"
                            onClick={() => setContextExpanded(value => !value)}
                            className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-white/55 hover:border-[#D4FF12]/40 hover:text-[#D4FF12]"
                        >
                            {contextExpanded ? "收起" : "展开"}
                        </button>
                    </div>
                    {!contextExpanded && (
                        <div className="space-y-1">
                            {consultationState?.reason && (
                                <p className="text-[11px] leading-relaxed text-[#FCD34D]">{consultationState.reason}</p>
                            )}
                            <p className="line-clamp-2 text-[11px] leading-relaxed text-white/55">
                                {context?.progress ?? firstHelpNeeded(context) ?? context?.background ?? context?.blockers?.[0] ?? "等待 Commander 补充会诊上下文。"}
                            </p>
                        </div>
                    )}
                    {contextExpanded && (
                        <div className="space-y-2">
                            {consultationState?.reason && (
                                <p className="text-[11px] leading-relaxed text-[#FCD34D]">{consultationState.reason}</p>
                            )}
                            {expertTasks.length > 0 && (
                                <div className="space-y-1.5">
                                    {expertTasks.map((task, index) => (
                                        <div key={`${task.question}-${index}`} className="rounded-lg border border-[#D4FF12]/15 bg-[#D4FF12]/5 px-2.5 py-2">
                                            <div className="text-[11px] font-medium text-white">{task.question}</div>
                                            {task.expectedOutput && (
                                                <div className="mt-1 text-[10px] leading-relaxed text-white/45">
                                                    期望输出：{task.expectedOutput}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div className="grid grid-cols-1 gap-1.5 text-[11px] text-white/60">
                                {context?.background && <div><span className="text-white/35">背景：</span>{context.background}</div>}
                                {context?.progress && <div><span className="text-white/35">进展：</span>{context.progress}</div>}
                                {(context?.blockers.length ?? 0) > 0 && <div><span className="text-white/35">阻塞：</span>{context?.blockers.join("；")}</div>}
                                {helpNeeded.length > 0 && (
                                    <div>
                                        <span className="text-white/35">需要帮助：</span>
                                        <ol className="mt-1 space-y-1 pl-5 list-decimal">
                                            {helpNeeded.map((item) => (
                                                <li key={item}>{item}</li>
                                            ))}
                                        </ol>
                                    </div>
                                )}
                            </div>
                            {(context?.sampleLinks.length ?? 0) > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                    {context?.sampleLinks.map((link) => (
                                        <a
                                            key={`${link.label}-${link.url}`}
                                            href={link.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="rounded-full border border-[#06B6D4]/25 bg-[#06B6D4]/10 px-2 py-0.5 text-[10px] text-[#67E8F9] hover:bg-[#06B6D4]/20"
                                        >
                                            {link.label}
                                        </a>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* 消息列表 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 flex flex-col gap-4">
                <AnimatePresence>
                    {filterDisplayComments(comments).map(comment => {
                        const isMe = comment.role === currentRole &&
                            comment.authorId === getTempUserId()
                        const cfg = ROLE_CONFIG[comment.role] || ROLE_CONFIG.expert

                        return (
                            <motion.div
                                key={comment.id}
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.25 }}
                                className={`flex gap-2.5 ${isMe ? 'flex-row-reverse' : 'flex-row'}`}
                            >
                                {/* 头像 */}
                                <div className="flex-shrink-0 mt-0.5">
                                    <div className={`w-8 h-8 rounded-full overflow-hidden border-2 ${isMe ? 'border-[#6366F1]/50' : 'border-[#D4FF12]/50'} shadow-[0_0_10px_rgba(99,102,241,0.2)]`}>
                                        <Image
                                            src={cfg.avatar}
                                            alt={cfg.label}
                                            width={32}
                                            height={32}
                                            className="w-full h-full object-cover"
                                        />
                                    </div>
                                </div>

                                {/* 消息内容 */}
                                <div className={`flex flex-col max-w-[75%] ${isMe ? 'items-end' : 'items-start'}`}>
                                    {/* 用户名和时间 */}
                                    <div className={`flex items-center gap-1.5 mb-1 ${isMe ? 'flex-row-reverse' : 'flex-row'}`}>
                                        <span className={`text-[10px] font-medium ${cfg.nameColor}`}>
                                            {cfg.label}
                                        </span>
                                        <span className="text-[9px] text-gray-600">
                                            {formatTime(comment.timestamp)}
                                        </span>
                                    </div>

                                    {/* 气泡 */}
                                    <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed border ${comment.messageType === "summary" ? "border-dashed opacity-70" : ""} ${cfg.bubbleBg} ${cfg.bubbleBorder} ${cfg.bubbleText} ${isMe ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}>
                                        {comment.messageType === "summary" && (
                                            <span className="block text-[10px] text-[#F59E0B]/80 mb-1">待确认摘要草稿</span>
                                        )}
                                        {comment.text}
                                    </div>
                                </div>
                            </motion.div>
                        )
                    })}
                </AnimatePresence>

                {comments.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center gap-2">
                        <div className="flex items-center gap-3 opacity-50">
                            <div className="w-10 h-10 rounded-full overflow-hidden border border-white/10">
                                <Image src="/host-avatar.png" alt="主持人" width={40} height={40} className="w-full h-full object-cover" />
                            </div>
                            <span className="text-gray-600 text-lg">⇄</span>
                            <div className="w-10 h-10 rounded-full overflow-hidden border border-white/10">
                                <Image src="/expert-avatar.png" alt="专家" width={40} height={40} className="w-full h-full object-cover" />
                            </div>
                        </div>
                        <span className="text-xs text-gray-500 italic">等待会诊开始...</span>
                    </div>
                )}
            </div>

            {/* 输入栏 */}
            {canSendMessage ? (
                <form onSubmit={handleSubmit} className="p-2.5 border-t border-white/10 bg-black/50 space-y-2.5">
                    {canModerate && (
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 space-y-2">
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-[10px] font-semibold text-white/60">用户主持操作</span>
                                {canEndConsultation && (
                                    <button
                                        type="button"
                                        onClick={() => handleModerationAction("end_consultation")}
                                        disabled={moderationPending}
                                        className="rounded-full border border-[#F59E0B]/30 px-2 py-0.5 text-[10px] text-[#FCD34D] hover:bg-[#F59E0B]/10 disabled:opacity-50"
                                    >
                                        结束会诊
                                    </button>
                                )}
                            </div>
                            {showApprovalActions && (
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        type="button"
                                        onClick={() => handleModerationAction("approve")}
                                        disabled={moderationPending}
                                        className="rounded-full bg-[#D4FF12] px-2 py-1 text-[10px] font-semibold text-black hover:bg-[#bce600] disabled:opacity-40"
                                    >
                                        再次会诊
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => handleModerationAction("skip")}
                                        disabled={moderationPending}
                                        className="rounded-full border border-[#F59E0B]/30 px-2 py-1 text-[10px] font-semibold text-[#FCD34D] hover:bg-[#F59E0B]/10 disabled:opacity-40"
                                    >
                                        跳过本次
                                    </button>
                                </div>
                            )}
                            {(canConfirmSummary || editableSummary) && (
                                <>
                                    <textarea
                                        value={editableSummary}
                                        onChange={(e) => setEditableSummary(e.target.value)}
                                        placeholder="编辑 Commander 待确认的会诊摘要..."
                                        rows={5}
                                        className="w-full resize-y rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 text-[11px] text-white placeholder:text-gray-600 focus:outline-none focus:border-[#D4FF12]/40 min-h-[80px]"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => handleModerationAction("confirm_summary")}
                                        disabled={moderationPending || !editableSummary.trim() || !canConfirmSummary}
                                        className="w-full rounded-full bg-[#D4FF12] px-2 py-1 text-[10px] font-semibold text-black hover:bg-[#bce600] disabled:opacity-40"
                                    >
                                        确认摘要并交给 Commander
                                    </button>
                                </>
                            )}
                            {editableExperienceDrafts.length > 0 && (
                                <div className="space-y-2 rounded-lg border border-[#06B6D4]/20 bg-[#06B6D4]/5 p-2">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="text-[10px] font-semibold text-[#67E8F9]">待入库个人经验草稿</span>
                                        <span className="text-[10px] text-white/40">{editableExperienceDrafts.length} 条</span>
                                    </div>
                                    <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                                        {editableExperienceDrafts.map((draft, index) => (
                                            <div key={`${draft.title}-${index}`} className="space-y-1.5 rounded-lg border border-white/10 bg-black/25 p-2">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-[10px] text-white/45">经验 {index + 1}</span>
                                                    <button
                                                        type="button"
                                                        onClick={() => removeExperienceDraft(index)}
                                                        className="rounded-full border border-red-400/25 px-2 py-0.5 text-[10px] text-red-300 hover:bg-red-500/10"
                                                    >
                                                        删除草稿
                                                    </button>
                                                </div>
                                                <input
                                                    value={draft.title}
                                                    onChange={(e) => updateExperienceDraft(index, { title: e.target.value })}
                                                    className="w-full rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="经验标题"
                                                />
                                                <input
                                                    value={draft.target_agents.join(", ")}
                                                    onChange={(e) => updateExperienceDraft(index, { target_agents: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) })}
                                                    className="w-full rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="适用 Agent，例如 forensics, osint, challenger"
                                                />
                                                <textarea
                                                    value={draft.problem_pattern}
                                                    onChange={(e) => updateExperienceDraft(index, { problem_pattern: e.target.value })}
                                                    className="min-h-14 w-full resize-y rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="适用问题模式"
                                                />
                                                <textarea
                                                    value={draft.recommended_method}
                                                    onChange={(e) => updateExperienceDraft(index, { recommended_method: e.target.value })}
                                                    className="min-h-14 w-full resize-y rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="推荐处理方法"
                                                />
                                                <textarea
                                                    value={draft.evidence_to_check.join("\n")}
                                                    onChange={(e) => updateExperienceDraft(index, { evidence_to_check: e.target.value.split("\n").map((item) => item.trim()).filter(Boolean) })}
                                                    className="min-h-12 w-full resize-y rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="需要核验的证据，每行一项"
                                                />
                                                <textarea
                                                    value={draft.when_to_escalate}
                                                    onChange={(e) => updateExperienceDraft(index, { when_to_escalate: e.target.value })}
                                                    className="min-h-10 w-full resize-y rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="什么时候仍需专家会诊"
                                                />
                                                <textarea
                                                    value={draft.limitations}
                                                    onChange={(e) => updateExperienceDraft(index, { limitations: e.target.value })}
                                                    className="min-h-10 w-full resize-y rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[11px] text-white focus:border-[#06B6D4]/45 focus:outline-none"
                                                    placeholder="限制与误用风险"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                    {experienceStatus && (
                                        <div className="rounded-md border border-white/10 bg-black/25 px-2 py-1 text-[10px] text-white/60">
                                            {experienceStatus}
                                        </div>
                                    )}
                                    <button
                                        type="button"
                                        onClick={handleConfirmExperienceDrafts}
                                        disabled={experiencePending}
                                        className="w-full rounded-full border border-[#06B6D4]/30 bg-[#06B6D4]/12 px-2 py-1 text-[10px] font-semibold text-[#67E8F9] hover:bg-[#06B6D4]/18 disabled:opacity-40"
                                    >
                                        {experiencePending ? "正在入库" : "确认入库个人经验库"}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                    {!canModerate && (
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[10px] text-white/40">
                            专家可提交意见，不能结束会诊或确认摘要。
                        </div>
                    )}
                    <div className="flex gap-2 items-end">
                        <div className="w-7 h-7 rounded-full overflow-hidden border border-white/10 flex-shrink-0 mb-0.5">
                            <Image
                                src={ROLE_CONFIG[currentRole]?.avatar || "/host-avatar.png"}
                                alt="我"
                                width={28}
                                height={28}
                                className="w-full h-full object-cover"
                            />
                        </div>
                        <textarea
                            ref={textareaRef}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault()
                                    if (inputValue.trim()) {
                                        e.currentTarget.form?.requestSubmit()
                                    }
                                }
                            }}
                            placeholder={currentRole === 'host' ? "以用户身份回复专家… (Enter 发送，Shift+Enter 换行)" : "提交专家意见… (Enter 发送，Shift+Enter 换行)"}
                            rows={1}
                            className="flex-1 bg-white/5 border border-white/10 rounded-2xl px-4 py-1.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all resize-none overflow-hidden"
                            style={{ minHeight: "36px", maxHeight: "120px" }}
                        />
                        <button
                            type="submit"
                            disabled={!inputValue.trim()}
                            className="px-4 py-1.5 bg-[#D4FF12] text-black font-semibold rounded-full text-xs hover:bg-[#bce600] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0 mb-0.5"
                        >
                            发送
                        </button>
                    </div>
                </form>
            ) : (
                <div className="p-3 border-t border-white/10 bg-black/50 text-center text-xs text-gray-500">
                    访客仅可查看会诊记录
                </div>
            )}
        </div>
    )
}
