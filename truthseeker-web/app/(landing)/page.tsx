"use client"

import { HeroSection } from "@/components/landing/HeroSection"
import { StatsCounter } from "@/components/landing/StatsCounter"
import { ProblemSection } from "@/components/landing/ProblemSection"
import { AgentShowcase } from "@/components/landing/AgentShowcase"
import { WorkflowTabs } from "@/components/landing/WorkflowTabs"
import { FederatedLearning } from "@/components/landing/FederatedLearning"
import { DebateSystem } from "@/components/landing/DebateSystem"
import { UseCases } from "@/components/landing/UseCases"
import { TechStack } from "@/components/landing/TechStack"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { motion, useScroll, useTransform } from "motion/react"
import { useRef } from "react"

export default function LandingPage() {
    const containerRef = useRef<HTMLDivElement>(null)
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start start", "end end"]
    })

    // Parallax values for different layers
    const layer1Y = useTransform(scrollYProgress, [0, 1], ["0%", "-10%"])
    const layer2Y = useTransform(scrollYProgress, [0, 1], ["0%", "-20%"])
    const layer3Y = useTransform(scrollYProgress, [0, 1], ["0%", "-30%"])
    const layer4Y = useTransform(scrollYProgress, [0, 1], ["0%", "-15%"])
    const footerY = useTransform(scrollYProgress, [0, 1], ["0%", "-5%"])

    return (
        <div ref={containerRef} className="flex flex-col w-full bg-white dark:bg-black font-sans relative">
            <div id="home" />

            {/* Base layer: Hero — Pure Black / White */}
            <div className="relative w-full z-0">
                <HeroSection />
            </div>

            {/* Layer 1: LIME (#D4FF12) — Stats + Problems */}
            <motion.div
                style={{ y: layer1Y }}
                className="relative z-10 -mt-16 pt-16 pb-6 rounded-t-[8rem] shadow-[0_-20px_50px_rgba(212,255,18,0.15)] bg-[#D4FF12] dark:bg-[#D4FF12] border-t border-[#D4FF12]/30 overflow-hidden text-black"
            >
                <div className="[&_*]:text-black [&_.text-muted-foreground]:!text-black/70 [&_.text-primary]:!text-[#6366F1] [&_.glass-card]:!bg-black/5 [&_.glass-card]:!border-black/10 [&_.glass-card]:!shadow-[0_8px_32px_rgba(0,0,0,0.05)] [&_svg]:!text-black">
                    <StatsCounter />
                    <ProblemSection />
                </div>
            </motion.div>

            {/* Layer 2: Default Background — Workflow + Innovation One */}
            <motion.div
                style={{ y: layer2Y }}
                className="relative z-20 -mt-16 pt-24 pb-32 rounded-t-[8rem] shadow-[0_-20px_50px_rgba(0,0,0,0.3)] bg-background border-t border-border overflow-visible"
            >
                <WorkflowTabs />
                <AgentShowcase />
            </motion.div>

            {/* Layer 3: Default Background — Innovation Two + Innovation Three */}
            <motion.div
                style={{ y: layer3Y }}
                className="relative z-30 -mt-8 pt-28 pb-16 rounded-t-[8rem] shadow-[0_-20px_50px_rgba(0,0,0,0.3)] bg-background border-t border-border overflow-hidden"
            >
                <div>
                    <FederatedLearning />
                    <DebateSystem />
                </div>
            </motion.div>

            {/* Layer 4: LIME (#D4FF12) — Cases + Tech */}
            <motion.div
                style={{ y: layer4Y }}
                className="relative z-40 -mt-16 pt-24 pb-0 rounded-t-[8rem] shadow-[0_-20px_50px_rgba(212,255,18,0.15)] bg-[#D4FF12] dark:bg-[#D4FF12] border-t border-[#D4FF12]/30 overflow-hidden text-black"
            >
                <div className="flex flex-col [&_.text-muted-foreground]:!text-black/70 [&_.gradient-text]:!bg-clip-text [&_.gradient-text]:!text-transparent [&_.gradient-text]:bg-gradient-to-r [&_.gradient-text]:from-black [&_.gradient-text]:to-gray-600">
                    <UseCases />
                    <TechStack />
                </div>
            </motion.div>

            {/* Final layer: Footer — Black */}
            <motion.div
                style={{ y: footerY }}
                className="relative z-50 -mt-8 bg-black"
            >
                <LandingFooter />
            </motion.div>
        </div>
    )
}
