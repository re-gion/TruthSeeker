"use client"

import { PresenceState } from "@/hooks/useRealtimeSession"
import { motion } from "motion/react"

export function PresenceAvatars({ users }: { users: PresenceState[] }) {
    if (!users || users.length === 0) return null

    return (
        <div className="flex items-center gap-2 bg-white/5 rounded-full px-3 py-1.5 border border-white/10">
            <span className="text-[10px] text-[#C0C0C0] uppercase tracking-wide mr-1 blur-none">协作房间</span>
            <div className="flex -space-x-2 overflow-hidden">
                {users.map((u, i) => (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        key={u.user_id + i}
                        style={{ zIndex: 10 - i }}
                        className={`w-7 h-7 rounded-full border-2 border-[#111828] flex items-center justify-center shadow-lg
                            ${u.role === 'host' ? 'bg-gradient-to-br from-[#6366F1] to-[#A855F7] text-white shadow-[0_0_8px_rgba(99,102,241,0.5)]'
                                : 'bg-gradient-to-br from-[#D4FF12] to-[#10B981] text-black shadow-[0_0_8px_rgba(212,255,18,0.5)]'}
                        `}
                        title={`${u.role === 'host' ? '主持人' : '专家'} (${u.user_id})`}
                    >
                        <svg width="14" height="14" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M 45 25 C 10 30 15 70 45 80" stroke="currentColor" strokeWidth="10" strokeLinecap="round" />
                            <circle cx="48" cy="18" r="8" fill="currentColor" />
                            <path d="M 40 38 L 85 38" stroke="currentColor" strokeWidth="10" strokeLinecap="round" />
                            <path d="M 60 38 L 65 75" stroke="currentColor" strokeWidth="10" strokeLinecap="round" />
                            <path d="M 65 80 C 85 75 90 55 85 45" stroke="currentColor" strokeWidth="10" strokeLinecap="round" />
                        </svg>
                    </motion.div>
                ))}
            </div>
            <div className="flex items-center gap-1.5 ml-1">
                <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                <span className="text-xs font-mono text-green-400">{users.length} 在线</span>
            </div>
        </div>
    )
}
