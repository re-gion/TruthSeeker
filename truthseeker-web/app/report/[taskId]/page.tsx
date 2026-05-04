"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { motion } from "motion/react"
import { BrandLogo } from "@/components/logo/BrandLogo"
import StarBackground from "@/components/ui/StarBackground"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface ReportData {
    report: {
        verdict: string | null
        confidence_overall: number | null
        summary: string | null
        generated_at: string | null
        report_hash?: string | null
    }
    task: {
        id: string | null
        title: string | null
        input_type: string | null
        status: string | null
    }
    markdown: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

const verdictConfig: Record<string, { color: string; bg: string; border: string; emoji: string; label: string }> = {
    forged: { color: "#EF4444", bg: "rgba(239,68,68,0.1)", border: "rgba(239,68,68,0.3)", emoji: "🚨", label: "确认伪造" },
    suspicious: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.3)", emoji: "⚠️", label: "高度可疑" },
    authentic: { color: "#10B981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.3)", emoji: "✅", label: "内容真实" },
    inconclusive: { color: "#6B7280", bg: "rgba(107,114,128,0.1)", border: "rgba(107,114,128,0.3)", emoji: "❓", label: "无法判定" },
}

export default function SharedReportPage() {
    const { taskId: token } = useParams<{ taskId: string }>()
    const [data, setData] = useState<ReportData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!token) return
        fetch(`${API_BASE}/api/v1/share/${token}`)
            .then(res => {
                if (!res.ok) throw new Error("分享链接无效或已过期")
                return res.json()
            })
            .then(setData)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false))
    }, [token])

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0A0A0F] flex items-center justify-center">
                <StarBackground />
                <motion.div
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="text-[#C0C0C0] text-lg"
                >
                    正在加载报告...
                </motion.div>
            </div>
        )
    }

    if (error || !data) {
        return (
            <div className="min-h-screen bg-[#0A0A0F] flex items-center justify-center">
                <StarBackground />
                <div className="glass-card rounded-xl p-8 text-center max-w-md">
                    <div className="text-4xl mb-4">🔗</div>
                    <h2 className="text-xl font-bold text-[#C0C0C0] mb-2">无法访问报告</h2>
                    <p className="text-[#6B7280] mb-6">{error || "分享链接无效"}</p>
                    <Link
                        href="/"
                        className="inline-block text-sm text-[#D4FF12] border border-[#D4FF12]/30 px-4 py-2 rounded-full hover:bg-[#D4FF12]/10 transition-colors"
                    >
                        返回首页
                    </Link>
                </div>
            </div>
        )
    }

    const vc = verdictConfig[data.report.verdict || "inconclusive"] || verdictConfig.inconclusive

    return (
        <div className="min-h-screen bg-[#0A0A0F]">
            <StarBackground />

            {/* Header */}
            <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0A0A0F]/80 backdrop-blur-md">
                <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-2">
                        <BrandLogo className="h-7 w-7" size={28} priority />
                        <span className="text-sm font-bold text-[#C0C0C0]">TruthSeeker</span>
                    </Link>
                    <div className="text-xs text-[#6B7280]">报告分享</div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-4 py-8">
                {/* Verdict Card */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl p-6 border mb-6 glass-card"
                    style={{ backgroundColor: vc.bg, borderColor: vc.border }}
                >
                    <div className="flex items-start gap-4">
                        <div className="text-4xl">{vc.emoji}</div>
                        <div className="flex-1">
                            <h1 className="text-2xl font-bold" style={{ color: vc.color }}>
                                {vc.label}
                            </h1>
                            {data.report.confidence_overall != null && (
                                <div className="mt-1 font-mono text-sm" style={{ color: vc.color }}>
                                    综合置信度 {(data.report.confidence_overall * 100).toFixed(1)}%
                                </div>
                            )}
                            {data.report.summary && (
                                <div className="mt-3 text-sm text-[#C0C0C0] leading-relaxed report-summary">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {data.report.summary}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Task info */}
                    <div className="mt-4 pt-4 border-t border-white/10 flex flex-wrap gap-4 text-xs text-[#6B7280]">
                        {data.task.title && <span>任务: {data.task.title}</span>}
                        {data.task.input_type && <span>类型: {data.task.input_type}</span>}
                        {data.report.generated_at && (
                            <span>
                                裁决时间: {new Date(data.report.generated_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}
                            </span>
                        )}
                        {data.report.report_hash && <span>报告 Hash: {data.report.report_hash}</span>}
                    </div>
                </motion.div>

                {/* Markdown Report */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="glass-card rounded-xl p-6 border border-white/5"
                >
                    <h2 className="text-lg font-bold text-[#C0C0C0] mb-4">详细分析报告</h2>
                    <div className="report-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {data.markdown}
                        </ReactMarkdown>
                    </div>
                </motion.div>

                {/* CTA */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="mt-8 text-center"
                >
                    <p className="text-sm text-[#6B7280] mb-4">
                        使用 TruthSeeker 进行跨模态 Deepfake 鉴伪与溯源
                    </p>
                    <Link
                        href="/detect"
                        className="inline-block text-sm font-bold bg-gradient-to-r from-[#6366F1] to-[#D4FF12] text-black px-6 py-2.5 rounded-full hover:opacity-90 transition-opacity"
                    >
                        开始鉴伪
                    </Link>
                </motion.div>
            </main>
        </div>
    )
}
