"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"
import { resetPassword } from "@/lib/supabase/auth-actions"
import Link from "next/link"
import Image from "next/image"
import { BrandLogo } from "@/components/logo/BrandLogo"
import { ThemeToggle } from "@/components/landing/ThemeToggle"

export default function ForgotPasswordPage() {
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [success, setSuccess] = useState(false)

    async function handleSubmit(formData: FormData) {
        setLoading(true)
        setError(null)
        const result = await resetPassword(formData)
        if (result?.error) {
            setError(result.error)
            setLoading(false)
        } else {
            setSuccess(true)
            setLoading(false)
        }
    }

    return (
        <main className="relative min-h-screen flex items-center justify-center overflow-hidden bg-[#020107] dark:bg-[#020107] selection:bg-[#6366F1]/30">
            {/* Background Art */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <Image
                    src="/auth-bg.png"
                    alt=""
                    fill
                    sizes="100vw"
                    className="absolute inset-0 h-full w-full object-cover object-center opacity-90 dark:opacity-90 -scale-y-100"
                    draggable={false}
                />
                <div className="absolute inset-0 bg-gradient-to-b from-[#6366F1]/5 via-transparent to-[#020107]/60" />
            </div>

            {/* Light theme fallback */}
            <div className="absolute inset-0 z-0 pointer-events-none dark:hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-[#f0f0ff] via-[#e4e0ff] to-[#f5f0ff]" />
                <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full bg-[#6366F1]/10 blur-[120px]" />
                <div className="absolute bottom-1/3 right-1/4 w-[400px] h-[400px] rounded-full bg-[#A855F7]/8 blur-[100px]" />
            </div>

            {/* Theme toggle */}
            <div className="absolute top-6 right-6 z-50">
                <ThemeToggle />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 30, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="relative z-10 w-full max-w-[420px] mx-4"
            >
                {/* Logo + Branding */}
                <motion.div
                    className="flex items-center gap-3 mb-8"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15, duration: 0.5 }}
                >
                    <div className="w-10 h-10 flex items-center justify-center">
                        <BrandLogo className="h-9 w-9" imageClassName="drop-shadow-lg" size={36} priority />
                    </div>
                    <motion.span
                        className="text-2xl font-bold bg-gradient-to-r from-[#C8E640] via-[#D4B896] to-[#C084FC] bg-clip-text text-transparent bg-[length:200%_auto]"
                        animate={{ backgroundPosition: ["0% center", "100% center", "0% center"] }}
                        transition={{ duration: 6, ease: "linear", repeat: Infinity }}
                    >
                        TruthSeeker
                    </motion.span>
                </motion.div>

                {/* Glass Card */}
                <motion.div
                    className="rounded-3xl p-6 dark:bg-black/15 bg-white/70 dark:border-white/10 border-white/40 border dark:backdrop-blur-xl backdrop-blur-2xl dark:shadow-[0_8px_32px_rgba(0,0,0,0.5)] shadow-[0_8px_32px_rgba(99,102,241,0.08)]"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                >
                    <AnimatePresence mode="wait">
                        {success ? (
                            <motion.div
                                key="success"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="text-center py-6 space-y-4"
                            >
                                <motion.div
                                    initial={{ scale: 0.5 }}
                                    animate={{ scale: 1 }}
                                    transition={{ type: "spring", stiffness: 200, damping: 12 }}
                                    className="w-16 h-16 rounded-full bg-[#10B981]/15 border border-[#10B981]/30 flex items-center justify-center mx-auto"
                                >
                                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                                </motion.div>
                                <div>
                                    <p className="text-foreground font-semibold text-lg">邮件已发送</p>
                                    <p className="text-muted-foreground text-sm mt-1">请检查邮箱中的密码重置链接</p>
                                </div>
                                <Link
                                    href="/login"
                                    className="inline-flex items-center gap-1 text-sm text-[#6366F1] hover:text-[#818CF8] font-medium transition-colors"
                                >
                                    返回登录
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                                </Link>
                            </motion.div>
                        ) : (
                            <motion.div key="form">
                                <div className="mb-6 text-center">
                                    <h1 className="text-[32px] leading-[40px] font-normal bg-gradient-to-b from-foreground from-75% to-muted-foreground bg-clip-text text-transparent">
                                        重置密码
                                    </h1>
                                    <p className="text-sm text-foreground/70 mt-1.5 tracking-wide">
                                        输入邮箱，我们将发送重置链接
                                    </p>
                                </div>

                                <form action={handleSubmit} className="space-y-[18px]">
                                    <div className="relative group">
                                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 group-focus-within:text-[#6366F1] transition-colors">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                                <rect width="20" height="16" x="2" y="4" rx="2" />
                                                <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                                            </svg>
                                        </div>
                                        <input
                                            name="email"
                                            type="email"
                                            required
                                            autoComplete="email"
                                            placeholder="you@example.com"
                                            className="w-full h-10 pl-10 pr-3 rounded-md dark:bg-[#09090b] bg-white/80 dark:border-[#3f3f46] border-gray-200 border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#6366F1]/40 focus:border-[#6366F1]/50 transition-all duration-200"
                                        />
                                    </div>

                                    <AnimatePresence>
                                        {error && (
                                            <motion.div
                                                initial={{ opacity: 0, height: 0 }}
                                                animate={{ opacity: 1, height: "auto" }}
                                                exit={{ opacity: 0, height: 0 }}
                                                className="flex items-center gap-2 text-[#EF4444] text-sm px-3 py-2.5 rounded-lg bg-[#EF4444]/8 border border-[#EF4444]/15 overflow-hidden"
                                            >
                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>
                                                {error}
                                            </motion.div>
                                        )}
                                    </AnimatePresence>

                                    <motion.button
                                        type="submit"
                                        disabled={loading}
                                        whileHover={{ scale: 1.015 }}
                                        whileTap={{ scale: 0.985 }}
                                        className="relative w-full h-11 rounded-lg dark:bg-foreground bg-[#09090b] dark:text-background text-white text-sm font-medium disabled:opacity-50 transition-all duration-200 overflow-hidden group cursor-pointer"
                                    >
                                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.07] to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                                        <span className="relative flex items-center justify-center gap-2">
                                            {loading ? (
                                                <>
                                                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                                                    发送中...
                                                </>
                                            ) : "发送重置链接"}
                                        </span>
                                    </motion.button>
                                </form>

                                <div className="mt-5 text-center text-sm text-muted-foreground">
                                    想起密码了？{" "}
                                    <Link href="/login" className="text-[#6366F1] hover:text-[#818CF8] font-medium transition-colors">
                                        返回登录
                                    </Link>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>

                <motion.div
                    className="mt-6 flex items-center justify-center gap-2 text-[11px] font-mono tracking-wider dark:text-white/20 text-black/30"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.7 }}
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
                    SYSTEM ONLINE · 4 AGENTS READY
                </motion.div>
            </motion.div>
        </main>
    )
}
