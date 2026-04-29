"use client"

import { useState, useEffect, useMemo, useRef } from "react"
import { motion, AnimatePresence } from "motion/react"
import { createClient } from "@/lib/supabase/client"
import { getAuthToken } from "@/lib/auth"
import { UserRole } from "@/hooks/useRealtimeSession"
import { canModerateConsultation, ConsultationState } from "@/hooks/useAgentStream"
import Image from "next/image"

type PanelRole = UserRole | "commander"

export interface ExpertComment {
    id: string
    authorId: string
    role: PanelRole
    text: string
    timestamp: string
    messageType?: string
    anchorAgent?: string
    phase?: string
    confidence?: number
    suggestedAction?: string
}

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

const MESSAGE_TYPE_OPTIONS = [
    { value: "analysis", label: "分析意见" },
    { value: "question", label: "追问" },
    { value: "evidence", label: "证据补充" },
    { value: "risk", label: "风险提示" },
    { value: "summary", label: "摘要建议" },
]

const ANCHOR_OPTIONS = [
    { value: "commander", label: "Commander" },
    { value: "forensics", label: "电子取证" },
    { value: "osint", label: "情报溯源" },
    { value: "challenger", label: "逻辑质询" },
]

function formatPercent(value?: number) {
    if (typeof value !== "number" || !Number.isFinite(value)) return null
    return `${Math.round(value * 100)}%`
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
    const [messageType, setMessageType] = useState("analysis")
    const [anchorAgent, setAnchorAgent] = useState("commander")
    const [phase, setPhase] = useState("")
    const [confidence, setConfidence] = useState("0.70")
    const [suggestedAction, setSuggestedAction] = useState("")
    const [editableSummary, setEditableSummary] = useState("")
    const [statusOverride, setStatusOverride] = useState<ConsultationState["status"] | null>(null)
    const [moderationPending, setModerationPending] = useState(false)
    const sentIdsRef = useRef<Set<string>>(new Set())
    const scrollRef = useRef<HTMLDivElement>(null)
    const canModerate = canModerateConsultation(currentRole)
    const effectiveStatus = statusOverride ?? consultationState?.status
    const broadcastChannel = useMemo(() => {
        if (typeof window === "undefined") {
            return null
        }

        const supabase = createClient()
        return supabase.channel(`task:${taskId}`)
    }, [taskId])

    // 自动滚动到底部
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [comments])

    useEffect(() => {
        if (consultationState?.summaryDraft) {
            setEditableSummary(consultationState.summaryDraft)
        }
    }, [consultationState?.summaryDraft])

    useEffect(() => {
        setStatusOverride(null)
    }, [consultationState?.lastEventType, consultationState?.status])

    useEffect(() => {
        const channel = broadcastChannel
        if (!channel) return

        channel.on('broadcast', { event: 'expert_comment' }, (payload: { payload?: unknown }) => {
            const comment = payload.payload as ExpertComment | undefined
            if (!comment || sentIdsRef.current.has(comment.id)) return
            setComments(prev => [...prev, comment])
        })

        void channel.subscribe()

        return () => {
            void channel.unsubscribe()
        }
    }, [broadcastChannel])

    useEffect(() => {
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        let cancelled = false

        async function loadMessages() {
            try {
                const authToken = await getAuthToken()
                const url = new URL(`${apiBase}/api/v1/consultation/${taskId}/messages`)
                if (inviteToken) url.searchParams.set("invite_token", inviteToken)
                const headers: Record<string, string> = {}
                if (authToken) headers.Authorization = `Bearer ${authToken}`
                const response = await fetch(url.toString(), { headers })
                if (!response.ok) return
                const data = await response.json()
                if (cancelled || !Array.isArray(data.messages)) return

                const history = data.messages.map((item: Record<string, unknown>) => {
                    const rawRole = item.role
                    const role: PanelRole =
                        rawRole === "user" || rawRole === "host"
                            ? "host"
                            : rawRole === "commander"
                                ? "commander"
                                : rawRole === "viewer" || rawRole === "expert"
                                    ? rawRole
                                    : "expert"
                    return {
                        id: typeof item.id === "string" ? item.id : Math.random().toString(36).substring(7),
                        authorId: typeof item.expert_name === "string" ? item.expert_name : "expert",
                        role,
                        text: typeof item.message === "string" ? item.message : "",
                        timestamp: typeof item.created_at === "string" ? item.created_at : new Date().toISOString(),
                        messageType: typeof item.message_type === "string" ? item.message_type : undefined,
                        anchorAgent: typeof item.anchor_agent === "string" ? item.anchor_agent : undefined,
                        phase: typeof item.anchor_phase === "string" ? item.anchor_phase : typeof item.phase === "string" ? item.phase : undefined,
                        confidence: typeof item.confidence === "number" ? item.confidence : undefined,
                        suggestedAction: typeof item.suggested_action === "string" ? item.suggested_action : undefined,
                    }
                })
                setComments(history)
            } catch {
                // 历史消息加载失败不影响实时会诊输入。
            }
        }

        void loadMessages()
        return () => {
            cancelled = true
        }
    }, [inviteToken, taskId])

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
                message_type: comment.messageType,
                anchor_agent: comment.anchorAgent,
                anchor_phase: comment.phase,
                confidence: comment.confidence,
                suggested_action: comment.suggestedAction,
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
        const parsedConfidence = Number.parseFloat(confidence)

        const newComment: ExpertComment = {
            id: Math.random().toString(36).substring(7),
            authorId: getTempUserId(),
            role: currentRole,
            text: inputValue.trim(),
            timestamp: new Date().toISOString(),
            messageType,
            anchorAgent,
            phase: phase.trim() || undefined,
            confidence: Number.isFinite(parsedConfidence) ? Math.min(1, Math.max(0, parsedConfidence)) : undefined,
            suggestedAction: suggestedAction.trim() || undefined,
        }

        sentIdsRef.current.add(newComment.id)
        setComments(prev => [...prev, newComment])

        // Realtime broadcast for other clients
        void broadcastChannel.send({
            type: 'broadcast',
            event: 'expert_comment',
            payload: newComment
        })

        // Inject into backend agent state via consultation API
        sendConsultationMessage(newComment).catch(err => console.error("Failed to inject expert message:", err))

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
    const showApprovalActions = canModerate && effectiveStatus === "approval_required"
    const canEndConsultation = canModerate && effectiveStatus === "started"
    const canConfirmSummary = canModerate && effectiveStatus === "summary_pending"
    const hasContext = Boolean(
        context?.background ||
        context?.progress ||
        context?.helpNeeded ||
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
                <div className="border-b border-white/10 bg-[#060B12]/80 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-[#D4FF12]">会诊上下文</span>
                        <span className="text-[10px] text-white/40">主持：Commander</span>
                    </div>
                    {consultationState?.reason && (
                        <p className="text-[11px] leading-relaxed text-[#FCD34D]">{consultationState.reason}</p>
                    )}
                    <div className="grid grid-cols-1 gap-1.5 text-[11px] text-white/60">
                        {context?.background && <div><span className="text-white/35">背景：</span>{context.background}</div>}
                        {context?.progress && <div><span className="text-white/35">进展：</span>{context.progress}</div>}
                        {(context?.blockers.length ?? 0) > 0 && <div><span className="text-white/35">阻塞：</span>{context?.blockers.join("；")}</div>}
                        {context?.helpNeeded && <div><span className="text-white/35">需要帮助：</span>{context.helpNeeded}</div>}
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

            {/* 消息列表 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 flex flex-col gap-4">
                <AnimatePresence>
                    {comments.map(comment => {
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
                                    <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed border ${cfg.bubbleBg} ${cfg.bubbleBorder} ${cfg.bubbleText} ${isMe ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}>
                                        {comment.text}
                                        {(comment.messageType || comment.anchorAgent || comment.phase || comment.confidence !== undefined || comment.suggestedAction) && (
                                            <div className="mt-2 flex flex-wrap gap-1.5 border-t border-white/10 pt-2 text-[9px]">
                                                {comment.messageType && <span className="rounded bg-white/10 px-1.5 py-0.5 text-white/55">{comment.messageType}</span>}
                                                {comment.anchorAgent && <span className="rounded bg-[#06B6D4]/10 px-1.5 py-0.5 text-[#67E8F9]">{comment.anchorAgent}</span>}
                                                {comment.phase && <span className="rounded bg-white/10 px-1.5 py-0.5 text-white/55">{comment.phase}</span>}
                                                {formatPercent(comment.confidence) && <span className="rounded bg-[#D4FF12]/10 px-1.5 py-0.5 text-[#D4FF12]">{formatPercent(comment.confidence)}</span>}
                                                {comment.suggestedAction && <span className="rounded bg-[#F59E0B]/10 px-1.5 py-0.5 text-[#FCD34D]">{comment.suggestedAction}</span>}
                                            </div>
                                        )}
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
                                        rows={2}
                                        className="w-full resize-none rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 text-[11px] text-white placeholder:text-gray-600 focus:outline-none focus:border-[#D4FF12]/40"
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
                        </div>
                    )}
                    {!canModerate && (
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[10px] text-white/40">
                            专家可提交意见，不能结束会诊或确认摘要。
                        </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                        <select
                            value={messageType}
                            onChange={(e) => setMessageType(e.target.value)}
                            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-[11px] text-white focus:outline-none focus:border-indigo-500"
                        >
                            {MESSAGE_TYPE_OPTIONS.map(option => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                        <select
                            value={anchorAgent}
                            onChange={(e) => setAnchorAgent(e.target.value)}
                            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-[11px] text-white focus:outline-none focus:border-indigo-500"
                        >
                            {ANCHOR_OPTIONS.map(option => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                        <input
                            type="text"
                            value={phase}
                            onChange={(e) => setPhase(e.target.value)}
                            placeholder="阶段 / phase"
                            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-[11px] text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500"
                        />
                        <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.05"
                            value={confidence}
                            onChange={(e) => setConfidence(e.target.value)}
                            placeholder="confidence"
                            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-[11px] text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500"
                        />
                    </div>
                    <input
                        type="text"
                        value={suggestedAction}
                        onChange={(e) => setSuggestedAction(e.target.value)}
                        placeholder="suggested_action，例如 resume_analysis / request_more_evidence"
                        className="w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-[11px] text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500"
                    />
                    <div className="flex gap-2 items-center">
                        <div className="w-7 h-7 rounded-full overflow-hidden border border-white/10 flex-shrink-0">
                            <Image
                                src={ROLE_CONFIG[currentRole]?.avatar || "/host-avatar.png"}
                                alt="我"
                                width={28}
                                height={28}
                                className="w-full h-full object-cover"
                            />
                        </div>
                        <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            placeholder={currentRole === 'host' ? "以用户身份回复专家..." : "提交专家意见..."}
                            className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                        />
                        <button
                            type="submit"
                            disabled={!inputValue.trim()}
                            className="px-4 py-1.5 bg-[#D4FF12] text-black font-semibold rounded-full text-xs hover:bg-[#bce600] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
