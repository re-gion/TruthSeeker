"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"
import { signIn } from "@/lib/supabase/auth-actions"
import Link from "next/link"
import Image from "next/image"
import { ThemeToggle } from "@/components/landing/ThemeToggle"

export default function LoginPage() {
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [showPassword, setShowPassword] = useState(false)

    async function handleSubmit(formData: FormData) {
        setLoading(true)
        setError(null)
        const result = await signIn(formData)
        if (result?.error) {
            setError(result.error)
            setLoading(false)
        }
    }

    return (
        <main className="relative min-h-screen flex items-center justify-center overflow-hidden bg-[#020107] dark:bg-[#020107] selection:bg-[#6366F1]/30">
            <div className="absolute inset-0 z-0 pointer-events-none">
                <Image
                    src="/auth-bg.png"
                    alt=""
                    fill
                    sizes="100vw"
                    className="absolute left-1/2 top-1/2 h-[102%] w-[113.75%] max-w-none -translate-x-1/2 -translate-y-1/2 -scale-y-100 object-cover opacity-90 dark:opacity-90"
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
                <motion.div
                    className="flex items-center gap-3 mb-8"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15, duration: 0.5 }}
                >
                    <div className="w-10 h-10 flex items-center justify-center">
                        <svg width="34" height="34" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="drop-shadow-lg">
                            <path d="M 45 25 C 10 30 15 70 45 80" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                            <circle cx="48" cy="18" r="8" fill="#6366F1" />
                            <path d="M 40 38 L 85 38" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                            <path d="M 60 38 L 65 75" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                            <path d="M 65 80 C 85 75 90 55 85 45" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                        </svg>
                    </div>
                    <motion.span
                        className="text-2xl font-bold bg-gradient-to-r from-[#C8E640] via-[#D4B896] to-[#C084FC] bg-clip-text text-transparent bg-[length:200%_auto]"
                        animate={{ backgroundPosition: ["0% center", "100% center", "0% center"] }}
                        transition={{ duration: 6, ease: "linear", repeat: Infinity }}
                    >
                        TruthSeeker
                    </motion.span>
                </motion.div>

                <motion.div
                    className="rounded-3xl p-6 bg-black/15 border-white/10 border backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                >
                    <div className="mb-6 text-center">
                        <h1 className="text-[32px] leading-[40px] font-normal bg-gradient-to-b from-white from-75% to-white/55 bg-clip-text text-transparent">
                            欢迎回来
                        </h1>
                        <p className="text-sm text-white/70 mt-1.5 tracking-wide">
                            登录以继续 Deepfake 鉴定任务
                        </p>
                    </div>

                    <form action={handleSubmit} className="space-y-[18px]">
                        <div className="relative group">
                            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40 group-focus-within:text-[#6366F1] transition-colors">
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
                                className="w-full h-10 pl-10 pr-3 rounded-md bg-[#09090b] border-[#3f3f46] border text-sm text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-[#6366F1]/40 focus:border-[#6366F1]/50 transition-all duration-200"
                            />
                        </div>

                        <div className="relative group">
                            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40 group-focus-within:text-[#6366F1] transition-colors">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                                </svg>
                            </div>
                            <input
                                name="password"
                                type={showPassword ? "text" : "password"}
                                required
                                autoComplete="current-password"
                                placeholder="密码"
                                className="w-full h-10 pl-10 pr-10 rounded-md bg-[#09090b] border-[#3f3f46] border text-sm text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-[#6366F1]/40 focus:border-[#6366F1]/50 transition-all duration-200"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                                tabIndex={-1}
                            >
                                {showPassword ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" x2="23" y1="1" y2="23"/></svg>
                                ) : (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                                )}
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="w-4 h-4 rounded bg-[#09090b] border-[#3f3f46] border accent-[#6366F1] focus:ring-[#6366F1]/30"
                                />
                                <span className="text-xs font-medium text-white select-none">记住我</span>
                            </label>
                            <button type="button" className="text-xs text-white/70 underline underline-offset-2 hover:text-white transition-colors cursor-default">
                                忘记密码？<span className="text-white/40 no-underline"> (暂未开放)</span>
                            </button>
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
                            className="relative w-full h-11 rounded-lg bg-white text-black text-sm font-medium disabled:opacity-50 transition-all duration-200 overflow-hidden group cursor-pointer"
                        >
                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-black/[0.06] to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                            <span className="relative flex items-center justify-center gap-2">
                                {loading ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                                        验证身份中...
                                    </>
                                ) : "登录"}
                            </span>
                        </motion.button>
                    </form>

                    <div className="mt-5 text-center text-sm text-white/45">
                        还没有账户？{" "}
                        <Link href="/signup" className="text-[#818CF8] hover:text-[#A5B4FC] font-medium transition-colors">
                            立即注册
                        </Link>
                    </div>
                </motion.div>

                <motion.div
                    className="mt-6 flex items-center justify-center gap-2 text-[11px] font-mono tracking-wider text-white/20"
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
