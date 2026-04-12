"use client"

import { motion, AnimatePresence } from "motion/react"
import { Smartphone, Download, AlertTriangle, ArrowRight, X } from "lucide-react"

export function AdversarialToolkit({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
    const steps = [
        {
            title: "下载换脸应用",
            description: "推荐使用 iOS/Android 上的开源或商用换脸应用 (如 Reface, Avatarify等) 进行快速生成。",
            icon: <Download className="w-5 h-5 text-[#6366F1]" />,
        },
        {
            title: "准备目标素材",
            description: "在应用中选择目标模板（如政客演讲、名人访谈），并上传您的人脸照片。",
            icon: <Smartphone className="w-5 h-5 text-[#D4FF12]" />,
        },
        {
            title: "生成并导出",
            description: "生成 10-15 秒的短视频并保存到相册，整个过程通常小于 60 秒。",
            icon: <ArrowRight className="w-5 h-5 text-white" />,
        }
    ]

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative w-full max-w-2xl bg-[#111828] border border-white/10 rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)]"
                    >
                        {/* Top decorative gradient */}
                        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#6366F1] via-[#A855F7] to-[#D4FF12]" />

                        <div className="p-6 md:p-8">
                            <div className="flex justify-between items-start mb-6">
                                <div>
                                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                                        <span className="text-2xl">⚡</span>
                                        实时对抗演示指南
                                    </h2>
                                    <p className="text-[#C0C0C0] text-sm mt-2">
                                        TruthSeeker 系统专为<span className="text-[#D4FF12] font-semibold">实时对抗环境</span>设计，检测流程高度优化，常规视频通常在 <span className="text-white font-mono bg-white/10 px-1 py-0.5 rounded">90秒</span> 内输出研判结果。
                                    </p>
                                </div>
                                <button
                                    onClick={onClose}
                                    className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-[#C0C0C0] hover:text-white transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-4 mb-8 flex items-start gap-4">
                                <AlertTriangle className="w-6 h-6 text-[#EF4444] shrink-0 mt-0.5" />
                                <div className="text-sm text-[#EF4444]/90 leading-relaxed">
                                    <strong>免责声明：</strong> 本工具箱提供的工具建议仅用于 CISCN 竞赛现场防伪检测能力的验证测试。请勿将生成的伪造视频用于任何非法或欺骗性用途。
                                </div>
                            </div>

                            <h3 className="text-lg font-semibold text-white mb-4">快速生成伪造视频测试材料：</h3>

                            <div className="space-y-4">
                                {steps.map((step, index) => (
                                    <div key={index} className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                                        <div className="w-10 h-10 rounded-lg bg-black/50 flex items-center justify-center shrink-0 border border-white/10 shadow-inner">
                                            {step.icon}
                                        </div>
                                        <div>
                                            <h4 className="text-white font-medium text-sm mb-1">
                                                <span className="text-xs font-mono text-white/40 mr-2">0{index + 1}</span>
                                                {step.title}
                                            </h4>
                                            <p className="text-[#C0C0C0] text-sm leading-relaxed">
                                                {step.description}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="mt-8 flex justify-end gap-3">
                                <button
                                    onClick={onClose}
                                    className="px-5 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white text-sm font-medium transition-colors"
                                >
                                    关闭
                                </button>
                                <button
                                    onClick={onClose}
                                    className="px-5 py-2 rounded-lg bg-gradient-to-r from-[#6366F1] to-[#4F46E5] text-white text-sm font-medium transition-colors shadow-[0_4px_14px_rgba(99,102,241,0.39)]"
                                >
                                    我已了解，去上传测试视频
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    )
}
