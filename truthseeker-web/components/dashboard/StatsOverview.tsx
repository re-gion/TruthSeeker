"use client"

import { motion, useInView } from "motion/react"
import { useEffect, useRef, useState } from "react"
import { ShieldAlert, Zap, CloudLightning, Activity, Server, FileVideo2 } from "lucide-react"

function AnimatedNumber({ value }: { value: number }) {
    const [displayValue, setDisplayValue] = useState(0)

    useEffect(() => {
        let start = 0
        const end = value
        const duration = 2000
        const increment = end / (duration / 16)

        const timer = setInterval(() => {
            start += increment
            if (start >= end) {
                clearInterval(timer)
                setDisplayValue(end)
            } else {
                setDisplayValue(Math.floor(start))
            }
        }, 16)

        return () => clearInterval(timer)
    }, [value])

    return <span>{displayValue.toLocaleString()}</span>
}

export function StatsOverview() {
    const containerRef = useRef(null)

    const stats = [
        { label: "累计检测总量", value: 142857, icon: <Activity className="w-5 h-5" />, color: "from-blue-500 to-cyan-400" },
        { label: "深度伪造拦截", value: 38402, icon: <ShieldAlert className="w-5 h-5" />, color: "from-red-500 to-orange-400" },
        { label: "平均响应延时 (ms)", value: 89, icon: <Zap className="w-5 h-5" />, color: "from-emerald-400 to-green-500" },
        { label: "活跃节点并发", value: 504, icon: <Server className="w-5 h-5" />, color: "from-[#6366F1] to-[#A855F7]" },
    ]

    const threatDistribution = [
        { name: "政要人物换脸", percentage: 45, color: "bg-red-500" },
        { name: "金融高管声纹伪造", percentage: 30, color: "bg-orange-500" },
        { name: "生成式虚假新闻", percentage: 15, color: "bg-blue-500" },
        { name: "多模态社工钓鱼", percentage: 10, color: "bg-[#D4FF12]" },
    ]

    return (
        <div ref={containerRef} className="w-full space-y-4">
            {/* Top Level Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {stats.map((stat, i) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.1, type: "spring", stiffness: 100 }}
                        className="relative overflow-hidden rounded-2xl p-6 bg-white/60 dark:bg-[#1F2937]/40 backdrop-blur-xl border border-black/10 dark:border-border shadow-[0_8px_32px_rgba(0,0,0,0.05)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.3)] group"
                    >
                        {/* Glassmorphism gradient */}
                        <div className={`absolute inset-0 opacity-5 dark:opacity-10 bg-gradient-to-br ${stat.color} transition-opacity duration-300 group-hover:opacity-10 dark:group-hover:opacity-20`} />

                        <div className="flex justify-between items-start mb-4 relative z-10">
                            <div className={`p-2 rounded-lg bg-gradient-to-br ${stat.color} bg-opacity-20 text-foreground shadow-lg`}>
                                {stat.icon}
                            </div>

                            {/* Decorative pulse point */}
                            <span className="relative flex h-3 w-3">
                                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-gradient-to-br ${stat.color}`}></span>
                                <span className={`relative inline-flex rounded-full h-3 w-3 bg-gradient-to-br ${stat.color}`}></span>
                            </span>
                        </div>

                        <div className="relative z-10">
                            <h4 className="text-muted-foreground text-sm font-medium mb-1">{stat.label}</h4>
                            <div className="text-3xl md:text-4xl font-bold text-foreground font-mono tracking-tight flex items-baseline gap-1">
                                <AnimatedNumber value={stat.value} />
                                {stat.label.includes("ms") && <span className="text-lg text-muted-foreground">ms</span>}
                            </div>
                        </div>

                        {/* Sweep light effect */}
                        <div className="absolute inset-x-0 -bottom-px h-px w-full bg-gradient-to-r from-transparent via-white/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    </motion.div>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Threat Distribution Chart */}
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4, duration: 0.6 }}
                    className="lg:col-span-2 rounded-2xl p-6 bg-white/60 dark:bg-[#1F2937]/40 backdrop-blur-xl border border-black/10 dark:border-border relative overflow-hidden shadow-lg"
                >
                    <div className="absolute top-0 right-0 w-64 h-64 bg-[#EF4444]/5 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2" />

                    <h3 className="text-xl font-bold text-foreground mb-6 flex items-center gap-2">
                        <CloudLightning className="text-emerald-500 dark:text-[#D4FF12] w-6 h-6" />
                        威胁类型分布实时监控
                    </h3>

                    <div className="space-y-3 mt-4 relative z-10">
                        {threatDistribution.map((item, i) => (
                            <div key={item.name} className="space-y-2">
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground flex items-center gap-2">
                                        <span className={`w-2 h-2 rounded-full ${item.color}`} />
                                        {item.name}
                                    </span>
                                    <span className="text-foreground font-mono font-medium">{item.percentage}%</span>
                                </div>
                                <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${item.percentage}%` }}
                                        transition={{ delay: 0.5 + i * 0.1, duration: 1, type: "spring", stiffness: 50 }}
                                        className={`h-full ${item.color} rounded-full relative`}
                                    >
                                        {/* Inner light flow */}
                                        <motion.div
                                            animate={{ x: ["-100%", "200%"] }}
                                            transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                                            className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-white/50 to-transparent -skew-x-12"
                                        />
                                    </motion.div>
                                </div>
                            </div>
                        ))}
                    </div>
                </motion.div>

                {/* Global Agent Status */}
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5, duration: 0.6 }}
                    className="rounded-2xl p-6 bg-white/60 dark:bg-[#1F2937]/40 backdrop-blur-xl border border-black/10 dark:border-border relative overflow-hidden shadow-lg"
                >
                    <div className="absolute top-0 right-0 w-64 h-64 bg-[#6366F1]/5 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2" />

                    <h3 className="text-xl font-bold text-foreground mb-6 flex items-center gap-2">
                        <FileVideo2 className="text-[#6366F1] w-6 h-6" />
                        系统运行态势
                    </h3>

                    <div className="flex flex-col gap-4 relative z-10">
                        {/* Status Rings */}
                        <div className="flex justify-center items-center py-2">
                            <div className="relative w-32 h-32">
                                {/* Outer ring */}
                                <motion.div
                                    animate={{ rotate: 360 }}
                                    transition={{ repeat: Infinity, duration: 10, ease: "linear" }}
                                    className="absolute inset-0 rounded-full border border-dashed border-[#6366F1]/40"
                                />
                                {/* Middle ring */}
                                <motion.div
                                    animate={{ rotate: -360 }}
                                    transition={{ repeat: Infinity, duration: 15, ease: "linear" }}
                                    className="absolute inset-2 rounded-full border-2 border-t-[#D4FF12] border-r-transparent border-b-[#D4FF12]/20 border-l-transparent"
                                />
                                {/* Inner solid */}
                                <div className="absolute inset-4 rounded-full bg-gradient-to-tr from-[#6366F1]/20 to-[#D4FF12]/10 backdrop-blur-sm border border-border flex items-center justify-center flex-col shadow-[0_0_30px_rgba(99,102,241,0.2)]">
                                    <span className="text-[#D4FF12] font-mono text-2xl font-bold">99.9%</span>
                                    <span className="text-[10px] text-muted-foreground">健康度</span>
                                </div>
                            </div>
                        </div>

                        <div className="bg-black/5 dark:bg-black/30 rounded-lg p-4 font-mono text-xs text-muted-foreground space-y-2 border border-black/5 dark:border-white/5 mt-4">
                            <p className="flex justify-between"><span>Forensics API:</span> <span className="text-emerald-600 dark:text-emerald-400">Online </span></p>
                            <p className="flex justify-between"><span>OSINT Node:</span> <span className="text-emerald-600 dark:text-emerald-400">Online </span></p>
                            <p className="flex justify-between"><span>Challenger AI:</span> <span className="text-emerald-600 dark:text-emerald-400">Idle </span></p>
                            <p className="flex justify-between"><span>Realtime Sync:</span> <span className="text-blue-600 dark:text-blue-400">Active(24)</span></p>
                        </div>
                    </div>
                </motion.div>
            </div>
        </div>
    )
}
