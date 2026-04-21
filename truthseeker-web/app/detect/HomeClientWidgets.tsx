"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "motion/react"
import { PlayCircle, Zap } from "lucide-react"
import { AdversarialToolkit } from "@/components/demo/AdversarialToolkit"
import { ComparisonView } from "@/components/demo/ComparisonView"

export function HomeClientWidgets() {
    const [isToolkitOpen, setIsToolkitOpen] = useState(false)

    return (
        <div className="w-full flex flex-col items-center">
            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 mb-16">
                <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setIsToolkitOpen(true)}
                    className="px-6 py-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 hover:bg-black/10 dark:hover:bg-white/10 text-gray-800 dark:text-white font-medium flex items-center gap-2 transition-colors shadow-lg"
                >
                    <Zap className="w-5 h-5 text-emerald-600 dark:text-[#D4FF12]" />
                    实时对抗演示工具箱
                </motion.button>

                <Link
                    href="/detect"
                    className="px-6 py-3 rounded-xl bg-gradient-to-r from-[#6366F1] to-[#4F46E5] text-white font-medium flex items-center gap-2 shadow-[0_4px_14px_rgba(99,102,241,0.39)] transition-transform hover:scale-105 active:scale-95"
                >
                    <PlayCircle className="w-5 h-5" />
                    观看完整工作流演示
                </Link>
            </div>

            {/* Comparison View Section */}
            <div className="w-full max-w-5xl">
                <div className="text-center mb-8">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">多维特征指纹提取</h2>
                    <p className="text-gray-500 dark:text-gray-400 text-sm">TruthSeeker 鉴伪引擎能够在像素级和频谱级发现肉眼无法辨别的合成伪影</p>
                </div>

                <ComparisonView />
            </div>

            <AdversarialToolkit
                isOpen={isToolkitOpen}
                onClose={() => setIsToolkitOpen(false)}
            />
        </div>
    )
}
