"use client"

import { motion } from "motion/react"
import { Ban, Unplug, EyeOff, Unlink } from "lucide-react"

export function ProblemSection() {
    const challenges = [
        {
            icon: <Ban className="w-10 h-10 text-red-400" />,
            title: "单一模型局限",
            description: "传统检测仅依赖单一维度，易被针对性对抗攻击绕过。",
            color: "from-red-500/20 to-orange-500/5",
            borderColor: "border-red-500/30"
        },
        {
            icon: <Unplug className="w-10 h-10 text-purple-400" />,
            title: "跨模态关联缺失",
            description: "音视频分离检测，无法捕捉唇形不同步、环境音与画面的逻辑冲突。",
            color: "from-purple-500/20 to-blue-500/5",
            borderColor: "border-purple-500/30"
        },
        {
            icon: <EyeOff className="w-10 h-10 text-gray-400" />,
            title: "黑盒不可解释",
            description: "仅输出概率分数，缺乏具体的篡改依据和证据链。",
            color: "from-gray-500/20 to-gray-400/5",
            borderColor: "border-gray-500/30"
        },
        {
            icon: <Unlink className="w-10 h-10 text-cyan-400" />,
            title: "溯源能力不足",
            description: "只能判断真伪，无法追踪病毒源头、分析扩散网络，治标不治本。",
            color: "from-cyan-500/20 to-teal-500/5",
            borderColor: "border-cyan-500/30"
        }
    ]

    const containerVars = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: { staggerChildren: 0.1 }
        }
    }

    const itemVars = {
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } as any }
    }

    return (
        <section id="features" className="relative py-32 overflow-hidden">
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 blur-[120px] rounded-full pointer-events-none -z-10" />
            <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-secondary/5 blur-[120px] rounded-full pointer-events-none -z-10" />

            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="flex flex-col md:flex-row gap-16 items-center">

                    {/* Left Column: Narrative */}
                    <motion.div
                        initial={{ opacity: 0, x: -50 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.8 }}
                        className="w-full md:w-1/2"
                    >
                        <div className="inline-block px-5 py-2 rounded-full bg-white text-black text-xs font-mono tracking-wider mb-6 border border-black/10 shadow-sm">
                            现实困境
                        </div>
                        <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6">
                            Deepfake 威胁<br />正在失控
                        </h2>
                        <p className="text-muted-foreground text-lg leading-relaxed mb-8">
                            随着生成式 AI 的爆发，深度伪造技术门槛大幅降低。传统的单点防御机制在面对具备多模态欺骗能力的定向攻击时，显得力不从心。
                        </p>
                        <div className="p-6 md:p-8 rounded-3xl bg-[#FFFFFF] text-black group relative overflow-hidden shadow-lg hover:-translate-y-2 transition-transform duration-500 border border-black/10">
                            <div className="absolute top-0 right-0 w-24 h-24 border-t-[6px] border-r-[6px] border-black/90 border-transparent rounded-tr-3xl transition-all duration-500 group-hover:border-t-black group-hover:border-r-black opacity-0 group-hover:opacity-100" />
                            <div className="absolute bottom-0 left-0 w-24 h-24 border-b-[6px] border-l-[6px] border-black/90 border-transparent rounded-bl-3xl transition-all duration-500 group-hover:border-b-black group-hover:border-l-black opacity-0 group-hover:opacity-100" />
                            
                            <div className="relative z-10 flex flex-col items-start h-full">
                                <h3 className="text-xl md:text-2xl font-black text-black mb-3 flex items-center gap-2 group-hover:text-primary transition-colors">
                                    <span className="text-primary">✦</span> 破局之道
                                </h3>
                                <p className="text-[15px] font-medium leading-relaxed text-black/70">
                                    TruthSeeker ：不能仅仅作为一个"检测工具"，相反我们需要建立一个具备
                                    <strong className="text-primary mx-1 font-bold">专家团队思维</strong>
                                    的智能研判中枢。
                                </p>
                            </div>
                        </div>
                    </motion.div>

                    {/* Right Column: Cards */}
                    <motion.div
                        variants={containerVars}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: "-100px" }}
                        className="w-full md:w-1/2 grid grid-cols-1 sm:grid-cols-2 gap-4"
                    >
                        {challenges.map((challenge, idx) => (
                            <motion.div
                                key={idx}
                                variants={itemVars}
                                className="p-6 rounded-3xl bg-[#FFFFFF] text-black group relative overflow-hidden shadow-lg hover:-translate-y-2 transition-transform duration-500 border border-black/10"
                            >
                                <div className="absolute top-0 right-0 w-24 h-24 border-t-[6px] border-r-[6px] border-black/90 border-transparent rounded-tr-3xl transition-all duration-500 group-hover:border-t-black group-hover:border-r-black opacity-0 group-hover:opacity-100" />
                                <div className="absolute bottom-0 left-0 w-24 h-24 border-b-[6px] border-l-[6px] border-black/90 border-transparent rounded-bl-3xl transition-all duration-500 group-hover:border-b-black group-hover:border-l-black opacity-0 group-hover:opacity-100" />
                                
                                <div className="relative z-10 flex flex-col h-full items-start">
                                    <div className="w-14 h-14 rounded-2xl bg-black/5 flex items-center justify-center mb-5 shadow-sm border border-black/10 group-hover:bg-white transition-colors duration-300">
                                        {challenge.icon}
                                    </div>
                                    <h4 className="text-xl font-black text-black mb-3 group-hover:text-primary transition-colors">{challenge.title}</h4>
                                    <p className="text-[15px] text-black/70 font-medium leading-relaxed">{challenge.description}</p>
                                </div>
                            </motion.div>
                        ))}
                    </motion.div>

                </div>
            </div>
        </section>
    )
}
