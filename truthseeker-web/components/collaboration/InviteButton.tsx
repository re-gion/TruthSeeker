"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"

export function InviteButton({ taskId }: { taskId: string }) {
    const [copied, setCopied] = useState(false)

    const handleInvite = async () => {
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
            const response = await fetch(`${apiBase}/api/v1/consultation/${taskId}/invite`, {
                method: "POST",
            })
            if (!response.ok) {
                throw new Error("invite creation failed")
            }
            const { invite_url: inviteUrl } = await response.json()
            const absoluteUrl = new URL(inviteUrl, window.location.origin)

            await navigator.clipboard.writeText(absoluteUrl.toString())
            setCopied(true)
            window.setTimeout(() => setCopied(false), 2000)
        } catch (error) {
            console.error("Failed to copy invite link:", error)
        }
    }

    return (
        <button
            onClick={handleInvite}
            className="px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/20 hover:text-indigo-300 text-xs font-semibold transition-all flex items-center gap-1.5 shadow-[0_0_10px_rgba(99,102,241,0.15)] relative overflow-hidden"
        >
            <AnimatePresence mode="wait">
                {copied ? (
                    <motion.div
                        key="copied"
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -20, opacity: 0 }}
                        className="flex items-center gap-1.5 text-green-400"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        已复制邀请链接
                    </motion.div>
                ) : (
                    <motion.div
                        key="invite"
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -20, opacity: 0 }}
                        className="flex items-center gap-1.5"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                        </svg>
                        邀请专家会诊
                    </motion.div>
                )}
            </AnimatePresence>
        </button>
    )
}
