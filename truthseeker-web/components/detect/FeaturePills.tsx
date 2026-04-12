"use client"

import { Film, Mic, ImageIcon, Radar, FileSearch } from "lucide-react"

const features = [
    { icon: <Film className="w-4 h-4 text-[#6366F1]" />, label: "视频深度伪造检测" },
    { icon: <Mic className="w-4 h-4 text-[#10B981]" />, label: "音频声纹克隆识别" },
    { icon: <ImageIcon className="w-4 h-4 text-[#F59E0B]" />, label: "图片 AI 生成鉴别" },
    { icon: <Radar className="w-4 h-4 text-[#06B6D4]" />, label: "实时 Agent 推理" },
    { icon: <FileSearch className="w-4 h-4 text-[#A855F7]" />, label: "专家级分析报告" },
]

export function FeaturePills() {
    return (
        <div className="flex flex-wrap justify-center gap-3 mb-20">
            {features.map(f => (
                <div
                    key={f.label}
                    className="flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-[#1A1A1A] border border-gray-200 dark:border-white/10 text-sm text-muted-foreground shadow-sm transition-transform hover:-translate-y-1 hover:bg-gray-50 dark:hover:bg-[#2A2A2A]"
                >
                    {f.icon}
                    <span>{f.label}</span>
                </div>
            ))}
        </div>
    )
}
