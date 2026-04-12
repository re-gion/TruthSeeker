"use client"

import { useRef } from "react"
import { motion, useScroll, useTransform } from "motion/react"
import { StatsOverview } from "@/components/dashboard/StatsOverview"
import { NetworkGraphUI } from "@/components/dashboard/NetworkGraphUI"
import { InteractiveCharts } from "@/components/dashboard/InteractiveCharts"

export function DashboardClient() {
    const containerRef = useRef<HTMLDivElement>(null)
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start start", "end end"]
    })

    // Parallax effects
    const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "50%"])
    const opac1 = useTransform(scrollYProgress, [0, 0.2], [1, 0.2])

    return (
        <div ref={containerRef} className="relative z-10 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
            {/* Dynamic Abstract Background with Parallax */}
            <motion.div
                style={{ y: bgY }}
                className="absolute -inset-[50%] z-0 pointer-events-none"
            >
                <div className="absolute top-0 left-1/4 w-[1000px] h-[500px] bg-[#6366F1]/15 rounded-full blur-[150px] -translate-x-1/2 -translate-y-1/2 mix-blend-screen" />
                <div className="absolute bottom-1/4 right-0 w-[800px] h-[600px] bg-[#D4FF12]/5 rounded-full blur-[150px] mix-blend-screen" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#A855F7]/10 rounded-full blur-[120px] mix-blend-screen" />

                {/* Grid Pattern */}
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-soft-light" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:64px_64px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_40%,#000_20%,transparent_100%)]" />
            </motion.div>

            {/* Section 1: Hero Stats */}
            <motion.section
                style={{ opacity: opac1 }}
                className="pt-6 relative z-10"
            >
                <div className="mb-4">
                    <h1 className="text-3xl md:text-4xl font-black text-foreground tracking-tight leading-tight mb-2">
                        TruthSeeker 全球感知中心
                    </h1>
                    <p className="text-muted-foreground text-base max-w-2xl font-light">
                        Real-time threat detection telemetry and AI forensic engine status. Monitoring multi-modal attacks across all connected nodes.
                    </p>
                </div>

                <StatsOverview />
            </motion.section>

            {/* Section 2: Global OSINT Network */}
            <motion.section
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8 }}
                className="relative z-10"
            >
                <div className="mb-6 flex items-center justify-between">
                    <h2 className="text-2xl font-bold font-mono tracking-tight flex items-center gap-3 text-foreground">
                        <span className="text-[#D4FF12]">01 //</span> Global Threat Network
                    </h2>
                </div>
                <NetworkGraphUI />
            </motion.section>

            {/* Section 3: Interactive Visualizations */}
            <motion.section
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8 }}
                className="relative z-10"
            >
                <div className="mb-6 flex items-center justify-between">
                    <h2 className="text-2xl font-bold font-mono tracking-tight flex items-center gap-3 text-foreground">
                        <span className="text-[#D4FF12]">02 //</span> Deep Analytics Engine
                    </h2>
                </div>
                <InteractiveCharts />
            </motion.section>
        </div>
    )
}
