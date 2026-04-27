"use client"

import { motion } from "motion/react"
import { useCountUp } from "@/hooks/useCountUp"
import { useEffect, useRef, useState } from "react"

function StatItem({ stat, index, isVisible }: { stat: any; index: number; isVisible: boolean }) {
    const count = useCountUp(stat.value, stat.duration, isVisible)

    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={isVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
            transition={{ duration: 0.6, delay: 0.1 * index }}
            className="flex flex-col items-center justify-center text-center group"
        >
            <div className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tighter text-foreground mb-3 font-mono flex items-baseline">
                {stat.prefix && <span className="text-2xl md:text-3xl text-primary mr-2 opacity-80">{stat.prefix}</span>}
                <span className="bg-gradient-to-br from-foreground to-muted-foreground bg-clip-text text-transparent drop-shadow-sm group-hover:scale-105 transition-transform duration-300">
                    {stat.isFloat ? (count === stat.value ? stat.value.toFixed(1) : count) : count}
                </span>
                {stat.isFloat && count === stat.value && <span className="text-2xl md:text-3xl text-primary ml-1">%</span>}
                {stat.suffix && <span className="text-2xl md:text-3xl text-primary ml-1 opacity-80">{stat.suffix}</span>}
            </div>
            <div className="text-sm md:text-base text-muted-foreground font-semibold uppercase tracking-widest relative">
                {stat.label}
                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0.5 bg-gradient-to-r from-primary to-transparent transition-all duration-300 group-hover:w-[80%]" />
            </div>
        </motion.div>
    )
}

export function StatsCounter() {
    const [isVisible, setIsVisible] = useState(false)
    const sectionRef = useRef<HTMLElement>(null)

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsVisible(true)
                    observer.disconnect()
                }
            },
            { threshold: 0.2 }
        )

        if (sectionRef.current) {
            observer.observe(sectionRef.current)
        }

        return () => observer.disconnect()
    }, [])

    const stats = [
        { value: 99.2, label: "检测准确率", duration: 2500, isFloat: true },
        { value: 60, label: "平均响应速度", duration: 2000, suffix: "s", prefix: "<" },
        { value: 4, label: "协同核心 Agent", duration: 1500 },
        { value: 24, label: "实时在线防护", duration: 2000, prefix: "7×", suffix: "h" },
    ]

    return (
        <section ref={sectionRef} className="relative py-24 overflow-hidden">
            {/* Container */}
            <div className="container mx-auto px-6 max-w-7xl relative z-10">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-12 md:gap-8">
                    {stats.map((stat, index) => (
                        <StatItem key={index} stat={stat} index={index} isVisible={isVisible} />
                    ))}
                </div>
            </div>

            {/* Marquee Background */}
            <div className="absolute top-1/2 -translate-y-1/2 left-0 w-full overflow-hidden opacity-10 dark:opacity-10 pointer-events-none -z-10 flex">
                <div className="whitespace-nowrap animate-marquee flex items-center">
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4">ROBUST FEDERATED LEARNING</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4 text-outline">MULTI-AGENT DEBATE</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4">FedPaRS ARCHITECTURE</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4 text-outline">CROSS-MODAL DETECTION</span>

                    {/* duplicate for continuous loop */}
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4">ROBUST FEDERATED LEARNING</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4 text-outline">MULTI-AGENT DEBATE</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4">FedPaRS ARCHITECTURE</span>
                    <span className="text-[120px] font-black uppercase text-foreground mx-8 px-4 text-outline">CROSS-MODAL DETECTION</span>
                </div>
            </div>

            <style jsx global>{`
        .text-outline {
          color: transparent;
          -webkit-text-stroke: 2px currentColor;
        }
      `}</style>
        </section>
    )
}
