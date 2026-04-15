"use client"

import { motion } from "motion/react"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { Music, Film, Image as ImageIcon, Newspaper } from "lucide-react"

const DEMO_CASES = [
    {
        id: "case-audio-scam",
        title: "董事长语音诈骗",
        type: "音频伪造",
        icon: <Music className="w-8 h-8 text-blue-400" />,
        color: "from-blue-500/20 to-blue-500/5",
        borderColor: "border-blue-500/30",
        glow: "shadow-[0_0_20px_rgba(59,130,246,0.3)]",
        accentColor: "text-blue-600 dark:text-blue-400",
        accentBg: "bg-blue-500/10",
        description: "通过少量样本克隆高管声音，指使财务转账的典型音频深度伪造案例。",
        duration: "1:24",
        difficulty: "High"
    },
    {
        id: "case-video-faceswap",
        title: "Politician 换脸视频",
        type: "视频伪造",
        icon: <Film className="w-8 h-8 text-red-400" />,
        color: "from-red-500/20 to-red-500/5",
        borderColor: "border-red-500/30",
        glow: "shadow-[0_0_20px_rgba(239,68,68,0.3)]",
        accentColor: "text-red-600 dark:text-red-400",
        accentBg: "bg-red-500/10",
        description: "使用高质量目标人脸替换源视频人物，用于散播虚假政治言论。",
        duration: "0:45",
        difficulty: "Critical"
    },
    {
        id: "case-mixed-phishing",
        title: "钓鱼链接+伪造截图",
        type: "图文混合",
        icon: <ImageIcon className="w-8 h-8 text-amber-400" />,
        color: "from-amber-500/20 to-amber-500/5",
        borderColor: "border-amber-500/30",
        glow: "shadow-[0_0_20px_rgba(245,158,11,0.3)]",
        accentColor: "text-amber-600 dark:text-amber-400",
        accentBg: "bg-amber-500/10",
        description: "结合生成的虚假聊天记录截图与恶意链接，进行多维度社会工程学攻击。",
        duration: "图片",
        difficulty: "Medium"
    },
    {
        id: "case-text-news",
        title: "AI 生成新闻",
        type: "文本生成",
        icon: <Newspaper className="w-8 h-8 text-emerald-400" />,
        color: "from-emerald-500/20 to-emerald-500/5",
        borderColor: "border-emerald-500/30",
        glow: "shadow-[0_0_20px_rgba(16,185,129,0.3)]",
        accentColor: "text-emerald-600 dark:text-emerald-400",
        accentBg: "bg-emerald-500/10",
        description: "利用大语言模型批量生成的虚假舆情新闻，具有极强的煽动性与迷惑性。",
        duration: "长文本",
        difficulty: "Medium"
    }
]

export function DemoCaseSelector() {
    const router = useRouter()
    const [hoveredId, setHoveredId] = useState<string | null>(null)

    const handleLoadCase = (id: string) => {
        // Navigate to a simulated test/detect page with this case loaded
        // For now, simple transition back to home with mocked state or a generic toast
        router.push(`/?demo=${id}`)
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4">
            {DEMO_CASES.map((demoCase, index) => (
                <motion.div
                    key={demoCase.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1, duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
                    onHoverStart={() => setHoveredId(demoCase.id)}
                    onHoverEnd={() => setHoveredId(null)}
                    className={`
            relative overflow-hidden rounded-2xl p-6 cursor-pointer
            bg-gradient-to-br ${demoCase.color}
            backdrop-blur-xl border ${demoCase.borderColor}
            transition-all duration-300
            ${hoveredId === demoCase.id ? demoCase.glow + ' -translate-y-1' : ''}
          `}
                    onClick={() => handleLoadCase(demoCase.id)}
                >
                    {/* Glass highlight effect on top border */}
                    <div className="absolute inset-0 bg-gradient-to-b from-white/10 to-transparent h-px w-full" />

                    <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <span className="filter drop-shadow-md">{demoCase.icon}</span>
                            <div>
                                <h3 className="text-xl font-bold text-foreground tracking-tight">{demoCase.title}</h3>
                                <span className="text-xs font-mono px-2 py-0.5 mt-1 inline-block rounded border border-border text-muted-foreground bg-muted">
                                    {demoCase.type}
                                </span>
                            </div>
                        </div>
                        {/* Action button */}
                        <motion.div
                            animate={{ opacity: hoveredId === demoCase.id ? 1 : 0.5, scale: hoveredId === demoCase.id ? 1.05 : 1 }}
                            className={`${demoCase.accentColor} text-sm font-medium flex items-center gap-1 ${demoCase.accentBg} px-3 py-1.5 rounded-full`}
                        >
                            <span>加载演示</span>
                            <span className="text-lg">→</span>
                        </motion.div>
                    </div>

                    <p className="text-muted-foreground text-sm leading-relaxed mb-6 h-[40px] line-clamp-2 relative z-10">
                        {demoCase.description}
                    </p>

                    <div className="flex items-center justify-between text-xs text-muted-foreground font-mono border-t border-border pt-4 mt-auto">
                        <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            Size / Duration: <span className="text-foreground/80">{demoCase.duration}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            Difficulty: <span className="text-foreground/80">{demoCase.difficulty}</span>
                        </div>
                    </div>

                    {/* Sweep scan animation on hover */}
                    {hoveredId === demoCase.id && (
                        <motion.div
                            initial={{ x: '-100%' }}
                            animate={{ x: '100%' }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent w-[200%] pointer-events-none -rotate-12"
                        />
                    )}
                </motion.div>
            ))}
        </div>
    )
}
