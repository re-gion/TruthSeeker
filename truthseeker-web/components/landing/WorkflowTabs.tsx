"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"
import Image from "next/image"
import { Download, Settings, Scale, ClipboardCheck, Film, Mic } from "lucide-react"

function DebateArchitectureDiagram() {
    return (
        <div className="w-full h-full rounded-xl border border-black/10 bg-[linear-gradient(180deg,rgba(249,250,251,0.96),rgba(243,244,246,0.96))] relative overflow-hidden p-4">
            <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: "radial-gradient(#000 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
            <div className="relative h-full min-h-[430px] -translate-x-6 -translate-y-6 pb-6">
                <div className="absolute left-[42.6%] top-[49.8%] z-20 flex h-[68px] w-[108px] -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-2xl border border-amber-500/30 bg-[#FFE6CF] shadow-[0_8px_24px_rgba(0,0,0,0.08)]">
                    <div className="text-[13px] font-black tracking-tight text-black/85">全局证据板</div>
                    <div className="mt-0.5 text-[9px] font-medium text-black/50">Evidence Board</div>
                </div>

                <div className="absolute left-[5.5%] top-[12%] z-20 w-[164px] rounded-2xl border border-indigo-500/25 bg-white px-3 py-2.5 shadow-[0_6px_20px_rgba(99,102,241,0.08)]">
                    <div className="flex items-center gap-2 text-[13px] font-bold text-black/85"><Image src="/agent-icons-v2/forensics.svg" alt="视听鉴伪" width={16} height={16} className="h-4 w-4" />视听鉴伪 Agent</div>
                    <div className="mt-1.5 text-[11px] leading-5 text-black/60">检测视频、音频、图像异常痕迹</div>
                </div>

                <div className="absolute left-[5.5%] bottom-[18%] z-20 w-[164px] rounded-2xl border border-emerald-500/25 bg-white px-3 py-2.5 shadow-[0_6px_20px_rgba(16,185,129,0.08)]">
                    <div className="flex items-center gap-2 text-[13px] font-bold text-black/85"><Image src="/agent-icons-v2/osint.svg" alt="情报溯源" width={16} height={16} className="h-4 w-4" />情报溯源 Agent</div>
                    <div className="mt-1.5 text-[11px] leading-5 text-black/60">分析 URL、威胁情报与来源线索</div>
                </div>

                <div className="absolute right-[22%] top-[12%] z-20 w-[164px] rounded-2xl border border-amber-500/25 bg-white px-3 py-2.5 shadow-[0_6px_20px_rgba(245,158,11,0.08)]">
                    <div className="flex items-center gap-2 text-[13px] font-bold text-black/85"><Image src="/agent-icons-v2/challenger.svg" alt="逻辑质询" width={16} height={16} className="h-4 w-4" />逻辑质询 Agent</div>
                    <div className="mt-1.5 text-[11px] leading-5 text-black/60">质询跨模态矛盾与逻辑缺口</div>
                </div>

                <div className="absolute right-[22%] bottom-[18%] z-20 w-[164px] rounded-2xl border border-cyan-500/25 bg-white px-3 py-2.5 shadow-[0_6px_20px_rgba(6,182,212,0.08)]">
                    <div className="flex items-center gap-2 text-[13px] font-bold text-black/85"><Image src="/agent-icons-v2/commander.svg" alt="研判指挥" width={16} height={16} className="h-4 w-4" />研判指挥 Agent</div>
                    <div className="mt-1.5 text-[11px] leading-5 text-black/60">综合裁决并生成最终报告</div>
                </div>

                <div className="absolute right-[5%] top-[15%] z-20 w-[92px] rounded-xl border border-black/10 bg-white/90 px-2 py-2 text-center shadow-sm">
                    <div className="text-[11px] font-bold text-black/80">人机协同</div>
                    <div className="mt-1 text-[10px] font-medium text-black/55">专家会诊</div>
                </div>

                <div className="absolute right-[5%] top-[40%] z-20 w-[92px] rounded-xl border border-black/10 bg-white/90 px-2 py-2 text-center shadow-sm">
                    <div className="text-[11px] font-bold text-black/80">证据时间轴</div>
                    <div className="mt-1 text-[10px] font-medium text-black/55">导出</div>
                </div>

                <div className="absolute right-[5%] bottom-[22%] z-20 w-[92px] rounded-xl border border-black/10 bg-white/90 px-2 py-2 text-center shadow-sm">
                    <div className="text-[11px] font-bold text-black/80">收敛机制</div>
                    <div className="mt-1 text-[10px] font-medium text-black/55">稳定收敛</div>
                </div>

                <svg className="absolute inset-0 h-full w-full pointer-events-none z-40" viewBox="0 0 1000 420" preserveAspectRatio="none" aria-hidden="true">
                    <defs>
                        <marker id="workflow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(55,65,81,0.75)" />
                        </marker>
                    </defs>

                    <path d="M 235 125 C 285 138, 326 162, 372 190" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                    <path d="M 235 300 C 292 278, 330 248, 372 230" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                    <path d="M 626 116 C 582 132, 520 158, 480 190" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" strokeDasharray="6 5" markerEnd="url(#workflow-arrow)" />
                    <path d="M 626 302 C 580 286, 522 258, 480 230" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                    <path d="M 828 106 C 720 146, 600 172, 480 198" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                    <path d="M 828 304 C 714 254, 600 234, 480 226" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                    <path d="M 480 210 C 612 210, 724 212, 828 218" fill="none" stroke="rgba(55,65,81,0.75)" strokeWidth="1.8" markerEnd="url(#workflow-arrow)" />
                </svg>

                <div className="pointer-events-none absolute inset-0 z-50 text-[11.5px] font-bold text-black/70">
                    {[
                        { label: "写入", className: "left-[30%] top-[32%]" },
                        { label: "写入", className: "left-[30%] top-[63%]" },
                        { label: "质询、复核", className: "left-[49%] top-[28.5%]" },
                        { label: "写入", className: "left-[50%] top-[63%]" },
                        { label: "稳定收敛", className: "left-[67%] top-[56%]" },
                        { label: "动态回注", className: "left-[64%] top-[29.5%]" },
                        { label: "导出", className: "left-[67%] top-[46%]" },
                    ].map((item) => (
                        <span key={`${item.label}-${item.className}`} className={`absolute ${item.className}`}>
                            {item.label}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    )
}

export function WorkflowTabs() {
    const [activeTab, setActiveTab] = useState(0)

    const steps = [
        {
            title: "多模态检材接入",
            description: "支持视频、音频、图片、文本及网页链接的多维输入，构建全息立体证据视图。",
            icon: <Download className="w-6 h-6" />,
            features: ["自适应格式解析", "元数据深度提取", "隐写信息扫描"],
            visual: (
                <div className="w-full h-full min-h-[320px] flex items-center justify-center bg-gray-50/80 rounded-xl border border-black/10 overflow-hidden relative p-8">
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent" />
                    <div className="flex flex-col gap-6 w-[82%]">
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-black/5 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
                            <div className="w-8 h-8 rounded bg-red-500/10 flex items-center justify-center text-red-500"><Film className="w-4 h-4" /></div>
                            <div className="flex-1">
                                <div className="h-2 w-24 bg-black/20 rounded mb-1.5" />
                                <div className="h-1.5 w-16 bg-black/10 rounded" />
                            </div>
                            <div className="text-xs font-mono text-black/50">Uploading 94%</div>
                        </div>
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-black/5 shadow-[0_2px_10px_rgba(0,0,0,0.02)] opacity-60">
                            <div className="w-8 h-8 rounded bg-cyan-500/10 flex items-center justify-center text-cyan-600"><Mic className="w-4 h-4" /></div>
                            <div className="flex-1">
                                <div className="h-2 w-32 bg-black/20 rounded mb-1.5" />
                                <div className="h-1.5 w-20 bg-black/10 rounded" />
                            </div>
                            <div className="text-xs text-emerald-600 font-mono">Complete</div>
                        </div>
                    </div>
                </div>
            )
        },
        {
            title: "自动化智能预处理",
            description: "应用端到端联邦脱敏算法，提取关键视听特征与网络拓扑索引，确保隐私合规的同时提升分发效率。",
            icon: <Settings className="w-6 h-6" />,
            features: ["视频抽帧与人脸对齐", "音频声纹特征向量化", "域名/URL威胁查寻"],
            visual: (
                <div className="w-full h-full flex items-center justify-center bg-white rounded-xl border border-black/10 overflow-hidden relative p-6 shadow-inner">
                    <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
                    <div className="w-full flex-col flex gap-2">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="flex gap-2">
                                <div className="w-16 h-12 bg-gray-50 rounded border border-black/10 flex items-center justify-center text-xs text-black/60 font-semibold shadow-sm">Frame {i}</div>
                                <div className="flex-1 h-12 flex items-center gap-1 px-4 border border-indigo-500/20 bg-indigo-500/5 rounded relative overflow-hidden shadow-sm">
                                    <div className="absolute inset-0 bg-indigo-500/10 animate-pulse origin-left" style={{ animationDuration: `${i}s` }} />
                                    <div className="w-2 h-2 rounded-full bg-indigo-500" />
                                    <div className="w-2 h-2 rounded-full bg-indigo-500/50" />
                                    <div className="flex-1" />
                                    <div className="text-[10px] font-mono text-indigo-600 font-bold z-10 relative">Extracted features</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )
        },
        {
            title: "多智能体交叉验证",
            description: "视听鉴伪Agent与情报溯源Agent并行取证，逻辑质询Agent开展对抗性攻防验证，研判指挥Agent融合置信度作出最终收敛裁决。",
            icon: <Scale className="w-6 h-6" />,
            features: ["跨 Agent 异步并行", "红蓝对抗逻辑质询", "动态收敛终止算法"],
            visual: <DebateArchitectureDiagram />
        },
        {
            title: "专家级分析报告",
            description: "输出包含完整推演逻辑、高危篡改区域定位和攻击者溯源路径的专家级分析报告。",
            icon: <ClipboardCheck className="w-6 h-6" />,
            features: ["置信度解释图谱", "司法级证据链固化", "PDF/JSON 一键导出"],
            visual: (
                <div className="w-full h-full flex p-6 bg-white rounded-xl border border-black/10 overflow-hidden relative justify-center items-center shadow-inner">
                    <div className="w-full max-w-sm bg-white border border-black/10 rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.05)] flex flex-col gap-4 transform rotate-1">
                        <div className="flex justify-between items-center border-b border-black/5 pb-3">
                            <div className="h-3 w-32 bg-black/10 rounded" />
                            <div className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-50 text-red-600 border border-red-100">TAMPERED: 99.2%</div>
                        </div>
                        <div className="flex gap-4 items-center">
                            <div className="w-20 h-20 bg-gray-100 rounded-lg border border-black/5" />
                            <div className="flex-1 flex flex-col gap-2.5 pt-1">
                                <div className="h-2 w-full bg-indigo-500/20 rounded" />
                                <div className="h-2 w-5/6 bg-indigo-500/20 rounded" />
                                <div className="h-2 w-4/6 bg-indigo-500/20 rounded" />
                            </div>
                        </div>
                        <div className="mt-2 pt-3 border-t border-black/5 flex gap-2">
                            <div className="w-6 h-6 rounded bg-indigo-500/10 border border-indigo-500/20" />
                            <div className="w-6 h-6 rounded bg-emerald-500/10 border border-emerald-500/20" />
                        </div>
                    </div>
                </div>
            )
        }
    ]

    return (
        <section id="workflow" className="relative py-24 overflow-hidden">
            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        系统检测工作流
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-muted-foreground text-lg max-w-2xl mx-auto"
                    >
                        从多模态数据摄入到专家级报告生成，全程自动化运转。
                    </motion.p>
                </div>

                <div className="flex flex-col lg:flex-row gap-12 items-stretch">

                    {/* Left: Tab List */}
                    <div className="w-full lg:w-1/3 flex flex-col gap-3">
                        {steps.map((step, index) => (
                            <motion.button
                                key={index}
                                initial={{ opacity: 0, x: -20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                onClick={() => setActiveTab(index)}
                                className={`text-left p-5 rounded-xl border transition-all duration-300 relative overflow-hidden ${activeTab === index
                                    ? "bg-white text-black border-primary/50 shadow-[0_4px_20px_rgba(255,255,255,0.1)]"
                                    : "bg-transparent border-transparent hover:bg-card/50"
                                    }`}
                            >
                                {activeTab === index && (
                                    <motion.div
                                        layoutId="activeTabIndicator"
                                        className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-primary to-secondary"
                                    />
                                )}
                                <div className="flex items-center gap-4 relative z-10">
                                    <div className={`text-2xl transition-colors ${activeTab === index ? "opacity-100 text-black" : "opacity-50"}`}>
                                        {step.icon}
                                    </div>
                                    <div>
                                        <h3 className={`font-semibold text-lg transition-colors ${activeTab === index ? "text-black" : "text-muted-foreground"}`}>
                                            {step.title}
                                        </h3>
                                    </div>
                                </div>
                            </motion.button>
                        ))}
                    </div>

                    {/* Right: Tab Content */}
                    <div className="relative w-full lg:w-2/3 min-h-[620px]">
                        <AnimatePresence initial={false}>
                            {steps.map((step, index) => (
                                <motion.div
                                    key={step.title}
                                    initial={false}
                                    animate={{ opacity: activeTab === index ? 1 : 0 }}
                                    transition={{ duration: 0.2 }}
                                    className={`absolute inset-0 bg-white rounded-2xl border border-black/10 p-8 min-h-[620px] flex flex-col text-black shadow-xl ${activeTab === index ? "pointer-events-auto z-10" : "pointer-events-none z-0"}`}
                                    aria-hidden={activeTab !== index}
                                >
                                    <h3 className="text-2xl font-bold mb-4">{step.title}</h3>
                                    <p className="text-black/70 leading-relaxed mb-8 max-w-xl">
                                        {step.description}
                                    </p>

                                    <div className="flex flex-wrap gap-3 mb-8">
                                        {step.features.map((feature, idx) => (
                                            <span key={idx} className="px-3 py-1 text-xs font-semibold rounded-full bg-[#2A2A2A] text-white/90 border border-white/10">
                                                {feature}
                                            </span>
                                        ))}
                                    </div>

                                    <div className="flex-1 rounded-xl overflow-hidden relative group">
                                        {step.visual}
                                    </div>
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </section>
    )
}
