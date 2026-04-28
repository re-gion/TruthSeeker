"use client"

import { motion } from "motion/react"

export function FederatedLearning() {
    const steps = [
        {
            title: "边缘计算与安全聚合",
            desc: "客户端完成本地训练，通过加密梯度上传至核心节点。",
            number: "01"
        },
        {
            title: "密文多维验证",
            desc: "核心节点在不解密原始数据的前提下，进行三层恶意校验。",
            number: "02"
        },
        {
            title: "零日攻击拦截",
            desc: "基于概率密度估计模型，在草图空间识别并剥离恶意伪造梯度。",
            number: "03"
        },
        {
            title: "全息鲁棒重构",
            desc: "采用中位数聚合与自适应学习率调优，合成对投毒攻击鲁棒的鉴伪模型。",
            number: "04"
        }
    ]

    return (
        <section id="technology" className="relative py-32 overflow-hidden">
            <div className="container mx-auto px-6 max-w-7xl relative z-10">

                <div className="flex flex-col lg:flex-row gap-16 items-center">

                    {/* Left: Graphic representation of FedPaRS */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.8 }}
                        className="w-full lg:w-1/2"
                    >
                        <div className="relative w-full aspect-square max-w-lg mx-auto">
                            <div className="absolute inset-0 bg-gradient-to-br from-[#6366F1]/20 to-[#A855F7]/20 rounded-full blur-[80px]" />

                            <div className="absolute inset-4 rounded-full border border-dashed border-[#6366F1]/30 animate-spin-slow" style={{ animationDuration: '20s' }} />
                            <div className="absolute inset-12 rounded-full border border-dashed border-[#D4FF12]/30 animate-spin-slow-reverse" style={{ animationDuration: '15s' }} />

                            {/* Central Core */}
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 rounded-full glass-card flex items-center justify-center agent-glow-indigo shadow-2xl z-20">
                                <span className="font-bold text-transparent bg-clip-text bg-gradient-to-br from-foreground to-muted-foreground text-center leading-tight">
                                    FedPaRS<br />CORE
                                </span>
                            </div>

                            {/* Orbiting nodes (Clients) */}
                            {[0, 1, 2].map(i => (
                                <div
                                    key={i}
                                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full pointer-events-none"
                                    style={{ transform: `rotate(${i * 120}deg)` }}
                                >
                                    <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-16 h-16 rounded-full glass-card border border-[#D4FF12]/30 flex flex-col items-center justify-center animate-pulse" style={{ animationDelay: `${i * 0.5}s` }}>
                                        <span className="text-[10px] text-muted-foreground font-mono">Node</span>
                                        <span className="text-sm font-bold text-[#D4FF12]">0{i + 1}</span>
                                    </div>
                                </div>
                            ))}

                            {/* Data flow lines */}
                            <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 10 }}>
                                {/* Center point is 50%, 50% */}
                                {/* To top node */}
                                <line x1="50%" y1="50%" x2="50%" y2="10%" stroke="rgba(99,102,241,0.5)" strokeWidth="2" strokeDasharray="4 4" className="animate-pulse" />
                                {/* To bottom right node */}
                                <line x1="50%" y1="50%" x2="85%" y2="75%" stroke="rgba(99,102,241,0.5)" strokeWidth="2" strokeDasharray="4 4" className="animate-pulse" style={{ animationDelay: '0.3s' }} />
                                {/* To bottom left node */}
                                <line x1="50%" y1="50%" x2="15%" y2="75%" stroke="rgba(99,102,241,0.5)" strokeWidth="2" strokeDasharray="4 4" className="animate-pulse" style={{ animationDelay: '0.6s' }} />
                            </svg>
                        </div>
                    </motion.div>

                    {/* Right: Narrative */}
                    <motion.div
                        initial={{ opacity: 0, x: 50 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.8 }}
                        className="w-full lg:w-1/2"
                    >
                        <div className="mb-6 text-3xl sm:text-4xl md:text-6xl font-black tracking-[0.12em] text-foreground">
                            核心创新点二
                        </div>
                        <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6">
                            FedPaRS <br />
                            <span className="text-muted-foreground">兼容运行时架构</span>
                        </h2>
                        <p className="text-muted-foreground text-lg leading-relaxed mb-12">
                            运行时架构预留联邦学习接口，支持未来接入 FedPaRS 鲁棒聚合模块，在拜占庭攻击场景下提升模型可信度。
                        </p>

                        <div className="space-y-6">
                            {steps.map((step, index) => (
                                <motion.div
                                    key={index}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true }}
                                    transition={{ delay: index * 0.15 }}
                                    className="flex gap-6 group"
                                >
                                    <div className="flex-shrink-0 w-12 h-12 rounded-full border border-border/50 glass-card flex items-center justify-center text-primary font-mono font-bold group-hover:bg-primary group-hover:text-background transition-colors duration-300">
                                        {step.number}
                                    </div>
                                    <div>
                                        <h4 className="text-xl font-bold text-foreground mb-2 group-hover:text-primary transition-colors">{step.title}</h4>
                                        <p className="text-muted-foreground leading-relaxed text-sm max-w-md">{step.desc}</p>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>

                </div>
            </div>
        </section>
    )
}
