"use client"

import { motion } from "motion/react"

export function TechStack() {
    const categories = [
        {
            name: "前端",
            tools: ["Next.js 15", "React 19", "Tailwind v4", "R3F", "Motion v12", "shadcn/ui"]
        },
        {
            name: "后端与编排",
            tools: ["FastAPI 0.134", "LangGraph v1.0.9+", "TypedDict State", "SSE Streaming"]
        },
        {
            name: "数据与安全",
            tools: ["Supabase SSR", "PostgreSQL RLS", "pgvector", "FedPaRS Federated"]
        },
        {
            name: "Agent与检测工具",
            tools: ["Kimi-K2.5", "Qwen3-VL", "Reality Defender", "VirusTotal", "Multi-Agent Debate"]
        }
    ]

    return (
        <section className="relative py-24 overflow-hidden">
            <div className="absolute top-1/2 left-0 w-full h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
            <div className="absolute top-0 right-0 w-1/3 h-full bg-gradient-to-l from-primary/5 to-transparent skew-x-12" />

            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        强大的底层 <span className="gradient-text">技术支撑</span>
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-muted-foreground text-lg max-w-2xl mx-auto"
                    >
                        严格遵循技术规范，基于前沿技术栈构建高性能、安全可控的多智能体系统。
                    </motion.p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {categories.map((category, idx) => (
                        <motion.div
                            key={idx}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-50px" }}
                            transition={{ delay: idx * 0.1 }}
                            className={`p-8 rounded-3xl bg-[#FFFFFF] text-black group relative overflow-hidden shadow-lg hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 border border-black/10 ${idx % 2 !== 0 ? 'md:mt-12' : ''}`}
                        >
                            <div className="absolute top-0 right-0 w-24 h-24 border-t-[6px] border-r-[6px] border-black/90 border-transparent rounded-tr-3xl transition-all duration-500 group-hover:border-t-black group-hover:border-r-black opacity-0 group-hover:opacity-100" />
                            <div className="absolute bottom-0 left-0 w-24 h-24 border-b-[6px] border-l-[6px] border-black/90 border-transparent rounded-bl-3xl transition-all duration-500 group-hover:border-b-black group-hover:border-l-black opacity-0 group-hover:opacity-100" />

                            <h3 className="text-sm font-mono text-black/60 uppercase tracking-widest border-b border-black/10 pb-4 mb-6 group-hover:text-black font-bold transition-colors">
                                {category.name}
                            </h3>
                            <ul className="space-y-4">
                                {category.tools.map((tool, index) => (
                                    <li key={index} className="flex items-center gap-3 text-black font-bold text-lg">
                                        <div className="w-8 h-8 rounded-xl bg-black/5 flex items-center justify-center group-hover:bg-black group-hover:text-[#FFFFFF] transition-colors duration-300">
                                            <span className="w-1.5 h-1.5 rounded-full bg-black/40 group-hover:bg-[#FFFFFF] transition-colors duration-300" />
                                        </div>
                                        {tool}
                                    </li>
                                ))}
                            </ul>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
