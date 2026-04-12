"use client"

import { motion } from "motion/react"
import { Mic, Film, Globe, FileText } from "lucide-react"
import Link from "next/link"

export function UseCases() {
    const cases = [
        {
            icon: <Mic className="w-8 h-8 text-blue-400" />,
            title: "针对高管的语音克隆诈骗",
            tags: ["Audio", "Financial Fraud"],
            desc: "检测伪造 CEO 声音下达紧急转账指令的音频片段，通过声纹频谱与换气规律识别 AI 合成痕迹。",
            color: "from-blue-500/20 to-indigo-500/5",
            demoId: "audio-ceo-fraud"
        },
        {
            icon: <Film className="w-8 h-8 text-red-400" />,
            title: "政治人物换脸虚假声明",
            tags: ["Video", "Election Interference"],
            desc: "深度剖析逐帧微表情与面部光影，揭露意图操纵选举或引发社会恐慌的 Deepfake 政治视频。",
            color: "from-red-500/20 to-orange-500/5",
            demoId: "video-election-fake"
        },
        {
            icon: <Globe className="w-8 h-8 text-emerald-400" />,
            title: "钓鱼链接与伪造截图组合",
            tags: ["Multi-modal", "Social Engineering"],
            desc: "结合 OSINT 溯源恶意域名，并比对被篡改的交易截图证据，实现跨模态交叉验证。",
            color: "from-emerald-500/20 to-teal-500/5",
            demoId: "multi-phishing"
        },
        {
            icon: <FileText className="w-8 h-8 text-amber-400" />,
            title: "AI 批量生成的虚假资讯",
            tags: ["Text", "Disinformation"],
            desc: "利用大语言模型（LLM）的探针技术，识别并阻断通过自动化矩阵账号传播的虚假新闻。",
            color: "from-amber-500/20 to-yellow-500/5",
            demoId: "text-disinfo"
        }
    ]

    return (
        <section id="cases" className="relative py-24">
            <div className="container mx-auto px-6 max-w-7xl relative z-10">

                <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-6">
                    <div className="max-w-2xl">
                        <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6">
                            应对全场景 <br />
                            <span className="text-muted-foreground">Deepfake 挑战</span>
                        </h2>
                        <p className="text-muted-foreground text-lg leading-relaxed">
                            涵盖音视频伪造、模态融合欺诈等高频攻击场景，提供可解释的专业鉴伪能力。
                        </p>
                    </div>
                    <Link href="/detect">
                        <button className="px-6 py-3 rounded-xl bg-[#FFFFFF] text-black border border-black/10 shadow-lg hover:-translate-y-1 transition-all duration-500 whitespace-nowrap font-medium flex items-center gap-2 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-16 h-16 border-t-[4px] border-r-[4px] border-black/90 border-transparent rounded-tr-xl transition-all duration-500 group-hover:border-t-black group-hover:border-r-black opacity-0 group-hover:opacity-100" />
                            <div className="absolute bottom-0 left-0 w-16 h-16 border-b-[4px] border-l-[4px] border-black/90 border-transparent rounded-bl-xl transition-all duration-500 group-hover:border-b-black group-hover:border-l-black opacity-0 group-hover:opacity-100" />
                            <span className="relative z-10">进入检测控制台</span>
                            <span className="relative z-10">→</span>
                        </button>
                    </Link>
                </div>

                <div className="relative overflow-hidden w-full max-w-7xl mx-auto py-8">
                    <motion.div
                        animate={{ x: ["0%", "-50%"] }}
                        transition={{ ease: "linear", duration: 30, repeat: Infinity }}
                        className="flex gap-6 lg:gap-8 w-max"
                    >
                        {[...cases, ...cases].map((scenario, idx) => (
                            <div
                                key={idx}
                                className={`w-[340px] md:w-[420px] shrink-0 p-8 rounded-3xl bg-[#FFFFFF] text-black group relative overflow-hidden shadow-lg hover:-translate-y-2 transition-transform duration-500 border border-black/10`}
                            >
                                {/* Decorative half-wrap border to mimic template */}
                                <div className="absolute top-0 right-0 w-32 h-32 border-t-[8px] border-r-[8px] border-black/90 border-transparent rounded-tr-3xl transition-all duration-500 group-hover:border-t-black group-hover:border-r-black opacity-0 group-hover:opacity-100" />
                                <div className="absolute bottom-0 left-0 w-32 h-32 border-b-[8px] border-l-[8px] border-black/90 border-transparent rounded-bl-3xl transition-all duration-500 group-hover:border-b-black group-hover:border-l-black opacity-0 group-hover:opacity-100" />

                                <div className="relative z-10 flex flex-col h-full items-start">
                                    <div className="w-16 h-16 rounded-2xl bg-black/5 flex items-center justify-center mb-6 shadow-sm border border-black/10 group-hover:bg-white transition-colors duration-300">
                                        {scenario.icon}
                                    </div>

                                    <div className="flex flex-wrap gap-2 mb-4">
                                        {scenario.tags.map(tag => (
                                            <span key={tag} className="px-3 py-1 text-[11px] font-mono uppercase tracking-widest rounded-full bg-black/5 text-black/80 font-bold border border-black/10">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>

                                    <h3 className="text-2xl font-black text-black mb-4 group-hover:text-primary transition-colors">{scenario.title}</h3>
                                    <p className="text-black/70 leading-relaxed mb-8 flex-1 font-medium text-[15px]">
                                        {scenario.desc}
                                    </p>

                                    <Link href={`/detect?demo=${scenario.demoId}`} className="mt-auto w-full group/btn">
                                        <button className="w-full py-4 rounded-xl bg-black hover:bg-black/90 text-[#FFFFFF] !text-[#FFFFFF] text-sm font-bold tracking-wide transition-all duration-300 flex items-center justify-center gap-2 shadow-md hover:scale-[1.02]">
                                            体验检测演示
                                            <span className="group-hover/btn:translate-x-2 transition-transform">→</span>
                                        </button>
                                    </Link>
                                </div>
                            </div>
                        ))}
                    </motion.div>
                </div>
            </div>
        </section>
    )
}
