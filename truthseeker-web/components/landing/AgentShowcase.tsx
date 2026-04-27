"use client"

import { motion } from "motion/react"

export function AgentShowcase() {
    const agents = [
        {
            role: "电子取证Agent",
            name: "Forensics Agent",
            icon: <img src="/agent-icons/forensics.svg" alt="电子取证Agent" className="w-8 h-8" />,
            theme: "indigo",
            glowClass: "agent-glow-indigo",
            bgClass: "from-[#6366F1]/20 to-[#A855F7]/5",
            textClass: "text-[#6366F1] dark:text-[#818CF8]",
            features: ["全模态样本取证", "RD/VT 工具矩阵", "跨模态伪造研判"],
            delay: 0.1
        },
        {
            role: "情报溯源Agent",
            name: "OSINT Agent",
            icon: <img src="/agent-icons/osint.svg" alt="情报溯源Agent" className="w-8 h-8" />,
            theme: "green",
            glowClass: "agent-glow-green",
            bgClass: "from-[#10B981]/20 to-[#34D399]/5",
            textClass: "text-[#10B981] dark:text-[#34D399]",
            features: ["威胁情报哈希库查寻", "传播域名/IP溯源追踪", "社交网络发酵链分析"],
            delay: 0.2
        },
        {
            role: "逻辑质询Agent",
            name: "Challenger Agent",
            icon: <img src="/agent-icons/challenger.svg" alt="逻辑质询Agent" className="w-8 h-8" />,
            theme: "amber",
            glowClass: "agent-glow-amber",
            bgClass: "from-[#F59E0B]/20 to-[#fbbf24]/5",
            textClass: "text-[#F59E0B] dark:text-[#fbbf24]",
            features: ["证据充分性红蓝对抗", "跨模态逻辑冲突挖掘", "触发高精度二次复判"],
            delay: 0.3
        },
        {
            role: "研判指挥Agent",
            name: "Commander Agent",
            icon: <img src="/agent-icons/commander.svg" alt="研判指挥Agent" className="w-8 h-8" />,
            theme: "cyan",
            glowClass: "agent-glow-cyan",
            bgClass: "from-[#06B6D4]/20 to-[#22d3ee]/5",
            textClass: "text-[#06B6D4] dark:text-[#22d3ee]",
            features: ["自适应权重融合决策", "完整法律级证据链生成", "动态控制收敛阈值"],
            delay: 0.4
        }
    ]

    return (
        <section className="relative py-24">
            <div className="container mx-auto px-6 max-w-7xl relative z-10">

                {/* Section Header */}
                <div className="text-center mb-16 md:mb-24">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="inline-block px-5 py-2 rounded-full bg-[#2a2a2e] text-white/80 text-xs font-mono tracking-wider mb-6 border border-[#3a3a3e]"
                    >
                        核心架构
                    </motion.div>

                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        多智能体 <span className="gradient-text">交叉验证机制</span>
                    </motion.h2>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.2 }}
                        className="text-muted-foreground text-lg max-w-2xl mx-auto leading-relaxed"
                    >
                        构建多路分发、异步处理的智能化流水线。超越单一模型的判断，实现模拟人类专家“疑案会诊”的群智决策。
                    </motion.p>
                </div>

                {/* Display Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {agents.map((agent, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 40 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 0.6, delay: agent.delay, type: "spring", stiffness: 100 }}
                            className={`p-8 rounded-3xl bg-[#FFFFFF] text-black group relative overflow-hidden shadow-lg hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 border border-black/10`}
                        >
                            {/* Decorative half-wrap border */}
                            <div className="absolute top-0 right-0 w-24 h-24 border-t-[6px] border-r-[6px] border-black/90 opacity-0 group-hover:opacity-100 rounded-tr-3xl transition-all duration-500" />
                            <div className="absolute bottom-0 left-0 w-24 h-24 border-b-[6px] border-l-[6px] border-black/90 opacity-0 group-hover:opacity-100 rounded-bl-3xl transition-all duration-500" />

                            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 relative z-10 bg-black/5 border border-black/10 transition-all duration-300 shadow-sm`}>
                                {agent.icon}
                            </div>

                            <div className="relative z-10 flex flex-col h-full">
                                <div className={`text-xs font-mono mb-2 uppercase tracking-wide font-bold text-black/60 group-hover:text-black transition-colors`}>
                                    {agent.name}
                                </div>
                                <h3 className="text-xl font-black text-black mb-6">{agent.role}</h3>
                                <ul className="space-y-4 flex-1">
                                    {agent.features.map((feature, i) => (
                                        <li key={i} className="flex items-start gap-3 text-[15px] font-medium text-black/80 hover:text-black transition-colors">
                                            <span className={`mt-1 text-[10px] text-black/40`}>▶</span>
                                            <span className="leading-snug">{feature}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
