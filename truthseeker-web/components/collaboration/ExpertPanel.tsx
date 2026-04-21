"use client"

import { useState, useEffect, useMemo, useRef } from "react"
import { motion, AnimatePresence } from "motion/react"
import { createClient } from "@/lib/supabase/client"
import { getAuthToken } from "@/lib/auth"
import { UserRole } from "@/hooks/useRealtimeSession"
import Image from "next/image"

export interface ExpertComment {
    id: string
    authorId: string
    role: UserRole
    text: string
    timestamp: string
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

const ROLE_CONFIG: Record<UserRole, RoleConfig> = {
    host: {
        label: "主持人",
        shortLabel: "主",
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

export function ExpertPanel({
    taskId,
    inviteToken,
    currentRole
}: {
    taskId: string
    inviteToken?: string | null
    currentRole: UserRole
}) {
    const [comments, setComments] = useState<ExpertComment[]>([])
    const [inputValue, setInputValue] = useState("")
    const sentIdsRef = useRef<Set<string>>(new Set())
    const scrollRef = useRef<HTMLDivElement>(null)
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
                    const role: UserRole = rawRole === "host" || rawRole === "viewer" || rawRole === "expert" ? rawRole : "expert"
                    return {
                        id: typeof item.id === "string" ? item.id : Math.random().toString(36).substring(7),
                        authorId: typeof item.expert_name === "string" ? item.expert_name : "expert",
                        role,
                        text: typeof item.message === "string" ? item.message : "",
                        timestamp: typeof item.created_at === "string" ? item.created_at : new Date().toISOString(),
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

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!canSendMessage || !inputValue.trim() || !broadcastChannel) return

        const newComment: ExpertComment = {
            id: Math.random().toString(36).substring(7),
            authorId: getTempUserId(),
            role: currentRole,
            text: inputValue.trim(),
            timestamp: new Date().toISOString()
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
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        const authToken = await getAuthToken()
        const headers: Record<string, string> = { "Content-Type": "application/json" }
        if (authToken) headers.Authorization = `Bearer ${authToken}`
        fetch(`${apiBase}/api/v1/consultation/${taskId}/inject`, {
            method: "POST",
            headers,
            body: JSON.stringify({
                message: newComment.text,
                role: newComment.role,
                expert_name: newComment.authorId,
                invite_token: inviteToken ?? undefined,
            }),
        }).catch(err => console.error("Failed to inject expert message:", err))

        setInputValue("")
    }

    return (
        <div className="flex flex-col h-full bg-black/40 border border-white/10 rounded-xl overflow-hidden backdrop-blur-md relative">
            {/* 顶部标题栏 */}
            <div className="px-3 py-2.5 border-b border-white/10 bg-white/5 flex justify-between items-center">
                <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                    <span className="text-[#D4FF12]">💬</span> 专家会诊频道
                </span>
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">实时通信</span>
            </div>

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
                <form onSubmit={handleSubmit} className="p-2.5 border-t border-white/10 bg-black/50 flex gap-2 items-center">
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
                        placeholder={currentRole === 'host' ? "回复专家..." : "提交质询意见..."}
                        className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                    />
                    <button
                        type="submit"
                        disabled={!inputValue.trim()}
                        className="px-4 py-1.5 bg-[#D4FF12] text-black font-semibold rounded-full text-xs hover:bg-[#bce600] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        发送
                    </button>
                </form>
            ) : (
                <div className="p-3 border-t border-white/10 bg-black/50 text-center text-xs text-gray-500">
                    访客仅可查看会诊记录
                </div>
            )}
        </div>
    )
}
