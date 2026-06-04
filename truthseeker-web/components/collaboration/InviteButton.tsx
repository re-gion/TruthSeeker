"use client"

import { useRef, useState } from "react"
import { motion, AnimatePresence } from "motion/react"
import { getAuthToken } from "@/lib/auth"

async function fetchWithRetry(input: RequestInfo | URL, init: RequestInit, attempts = 2): Promise<Response> {
    let lastError: unknown
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        try {
            return await fetch(input, init)
        } catch (error) {
            lastError = error
            if (attempt >= attempts) break
            await new Promise(resolve => window.setTimeout(resolve, 400))
        }
    }
    throw lastError
}

export function InviteButton({ taskId }: { taskId: string }) {
    const [copied, setCopied] = useState(false)
    const [isInviting, setIsInviting] = useState(false)
    const [failed, setFailed] = useState(false)
    const invitingRef = useRef(false)

    const handleInvite = async () => {
        if (invitingRef.current) return
        invitingRef.current = true
        setIsInviting(true)
        setFailed(false)
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
            const authToken = await getAuthToken()
            const headers: Record<string, string> = {}
            if (authToken) headers.Authorization = `Bearer ${authToken}`
            const response = await fetchWithRetry(`${apiBase}/api/v1/consultation/${taskId}/invite`, {
                method: "POST",
                headers,
            })
            if (!response.ok) {
                throw new Error("invite creation failed")
            }
            const { invite_url: inviteUrl } = await response.json()
            const absoluteUrl = new URL(inviteUrl, window.location.origin)

            const text = absoluteUrl.toString()
            try {
                await navigator.clipboard.writeText(text)
            } catch {
                const textarea = document.createElement("textarea")
                textarea.value = text
                textarea.style.position = "fixed"
                textarea.style.opacity = "0"
                document.body.appendChild(textarea)
                textarea.select()
                document.execCommand("copy")
                document.body.removeChild(textarea)
            }
            setCopied(true)
            window.setTimeout(() => setCopied(false), 2000)
        } catch (error) {
            console.error("Failed to copy invite link:", error)
            setFailed(true)
        } finally {
            invitingRef.current = false
            setIsInviting(false)
        }
    }

    return (
        <button
            onClick={handleInvite}
            disabled={isInviting}
            aria-busy={isInviting}
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
                ) : isInviting ? (
                    <motion.div
                        key="inviting"
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -20, opacity: 0 }}
                        className="flex items-center gap-1.5"
                    >
                        <span className="w-3.5 h-3.5 rounded-full border border-indigo-300/40 border-t-indigo-300 animate-spin" />
                        正在生成
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
                        {failed ? "重试邀请会诊" : "邀请专家会诊"}
                    </motion.div>
                )}
            </AnimatePresence>
        </button>
    )
}
