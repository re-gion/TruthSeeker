"use client"

import { motion } from "motion/react"

const collaborationHighlights = [
    {
        number: "01",
        title: "AI 初筛 + 人工触发介入",
        description: "系统先由多 Agent 完成首轮取证与交叉验证；一旦出现证据冲突、低置信结论或高风险案件，即可切入专家会诊流程。"
    },
    {
        number: "02",
        title: "共享证据板协同研判",
        description: "专家可同步查看当前证据板、历史轮次与关键线索，在统一上下文中补充质疑、确认意见与新增证据。"
    },
    {
        number: "03",
        title: "人机意见回注闭环",
        description: "人工会诊结论不会停留在聊天层，而是作为新证据注入工作流，驱动智能体继续复核、收敛并生成更可采信的最终报告。"
    }
]

export function DebateSystem() {
    return (
        <section className="relative py-32 overflow-hidden">
            <div className="absolute inset-0 grid-bg opacity-30" />
            <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-gradient-to-b from-[#6366F1]/10 to-transparent blur-[120px] rounded-full pointer-events-none -z-10" />

            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="mb-20">
                    <div className="mb-4 text-lg sm:text-xl md:text-2xl font-bold tracking-[0.08em] text-white">
                        核心创新点三：
                    </div>
                    <h2 className="text-center text-3xl md:text-5xl font-bold tracking-tight">
                        人机协同 <span className="gradient-text">专家会诊机制</span>
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-5xl mx-auto leading-relaxed text-center mt-6">
                        TruthSeeker 不只依赖自动检测，而是将多智能体证据板、实时协作频道与专家介入机制打通，形成“机器快速筛查 + 人类深度研判 + 结果回注收敛”的闭环会诊模式。
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-8 items-stretch">
                    <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl shadow-2xl overflow-hidden min-h-[520px] flex flex-col">
                        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/5">
                            <div>
                                <div className="text-xs uppercase tracking-[0.2em] text-white/40 font-mono">Realtime Consultation</div>
                                <div className="text-xl font-bold text-white mt-1">专家会诊协同面板</div>
                            </div>
                            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1.5">
                                <span className="relative flex h-2.5 w-2.5">
                                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-400" />
                                </span>
                                <span className="text-xs font-mono text-green-300">3 位在线会诊</span>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-[0.9fr_1.1fr] gap-0 flex-1">
                            <div className="border-b md:border-b-0 md:border-r border-white/10 p-6 bg-black/20">
                                <div className="flex items-center justify-between mb-5">
                                    <div className="text-sm font-semibold text-white">共享证据板</div>
                                    <div className="text-[10px] font-mono text-white/40 uppercase">State Board</div>
                                </div>

                                <div className="space-y-4">
                                    <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-xs font-mono uppercase tracking-wider text-indigo-300">Forensics</span>
                                            <span className="text-[11px] text-indigo-200/70">置信度 91%</span>
                                        </div>
                                        <p className="text-sm text-white/80 leading-relaxed">检测到嘴型与音轨存在轻微错位，关键帧面部边缘出现生成式融合痕迹。</p>
                                    </div>

                                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-xs font-mono uppercase tracking-wider text-emerald-300">OSINT</span>
                                            <span className="text-[11px] text-emerald-200/70">传播链已关联</span>
                                        </div>
                                        <p className="text-sm text-white/80 leading-relaxed">可疑内容最早出现在新注册域名关联账号，扩散路径与历史诈骗样本高度相似。</p>
                                    </div>

                                    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-xs font-mono uppercase tracking-wider text-amber-300">Challenge</span>
                                            <span className="text-[11px] text-amber-200/70">等待人工确认</span>
                                        </div>
                                        <p className="text-sm text-white/80 leading-relaxed">需排查压缩伪影干扰，建议由人工复核证据充分性并决定是否追加高精度复判。</p>
                                    </div>
                                </div>
                            </div>

                            <div className="p-6 flex flex-col bg-gradient-to-b from-white/5 to-transparent">
                                <div className="flex items-center justify-between mb-5">
                                    <div className="text-sm font-semibold text-white">专家会诊频道</div>
                                    <div className="rounded-full bg-indigo-500/10 border border-indigo-500/20 px-3 py-1 text-[11px] text-indigo-300">邀请专家会诊</div>
                                </div>

                                <div className="flex-1 space-y-4">
                                    <motion.div
                                        initial={{ opacity: 0, y: 12 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true }}
                                        className="flex gap-3"
                                    >
                                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-sm font-bold text-white shadow-[0_0_18px_rgba(99,102,241,0.35)]">
                                            主
                                        </div>
                                        <div className="max-w-[85%]">
                                            <div className="text-[11px] text-indigo-300 mb-1">主持人 · 09:41</div>
                                            <div className="rounded-2xl rounded-tl-sm border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm text-white/90 leading-relaxed">
                                                已同步当前证据板，请专家重点判断“边缘融合痕迹”是否可能由平台二次压缩造成。
                                            </div>
                                        </div>
                                    </motion.div>

                                    <motion.div
                                        initial={{ opacity: 0, y: 12 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true }}
                                        transition={{ delay: 0.08 }}
                                        className="flex gap-3"
                                    >
                                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#D4FF12] to-[#10B981] flex items-center justify-center text-sm font-bold text-black shadow-[0_0_18px_rgba(212,255,18,0.28)]">
                                            专
                                        </div>
                                        <div className="max-w-[85%]">
                                            <div className="text-[11px] text-[#D4FF12] mb-1">外部专家 · 09:42</div>
                                            <div className="rounded-2xl rounded-tl-sm border border-[#D4FF12]/20 bg-[#D4FF12]/8 px-4 py-3 text-sm text-white/90 leading-relaxed">
                                                仅凭单帧边缘特征不足以定性，建议提高嘴型-语音同步权重，并追加历史相似样本交叉比对。
                                            </div>
                                        </div>
                                    </motion.div>

                                    <motion.div
                                        initial={{ opacity: 0, y: 12 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true }}
                                        transition={{ delay: 0.16 }}
                                        className="flex gap-3"
                                    >
                                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#06B6D4] to-[#6366F1] flex items-center justify-center text-sm font-bold text-white shadow-[0_0_18px_rgba(6,182,212,0.28)]">
                                            AI
                                        </div>
                                        <div className="max-w-[85%]">
                                            <div className="text-[11px] text-cyan-300 mb-1">系统回注 · 09:43</div>
                                            <div className="rounded-2xl rounded-tl-sm border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-white/90 leading-relaxed">
                                                已采纳专家质询，触发高精度复判与跨样本复核流程，更新结果将回写 Evidence Board 并继续收敛。
                                            </div>
                                        </div>
                                    </motion.div>
                                </div>

                                <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 flex items-center justify-between gap-3">
                                    <div className="text-sm text-white/45">提交质询意见 / 标记疑点 / 确认结论</div>
                                    <div className="px-4 py-2 rounded-full bg-[#D4FF12] text-black text-xs font-bold whitespace-nowrap">发送会诊意见</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-6">
                        {collaborationHighlights.map((item, index) => (
                            <motion.div
                                key={item.number}
                                initial={{ opacity: 0, x: 20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{ delay: index * 0.1, duration: 0.5 }}
                                className="p-6 rounded-2xl glass-card flex gap-4 relative group overflow-hidden border border-border hover:border-primary/50 transition-all duration-300"
                            >
                                <div className="absolute top-0 right-0 w-16 h-16 border-t-[4px] border-r-[4px] border-primary opacity-0 group-hover:opacity-100 transition-all duration-500 rounded-tr-2xl" />
                                <div className="absolute bottom-0 left-0 w-16 h-16 border-b-[4px] border-l-[4px] border-primary opacity-0 group-hover:opacity-100 transition-all duration-500 rounded-bl-2xl" />
                                <div className="text-primary text-2xl font-black opacity-60 relative z-10">{item.number}</div>
                                <div className="relative z-10">
                                    <h4 className="font-semibold text-foreground mb-2 text-lg">{item.title}</h4>
                                    <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    )
}
