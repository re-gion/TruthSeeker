"use client"

import { motion, useMotionValue, useSpring, useTransform } from "motion/react"
import Link from "next/link"
import Image from "next/image"
import { useEffect } from "react"
import ShinyText from "@/components/ui/ShinyText"
import FluidGlassButton from "@/components/ui/FluidGlassButton"
import Orb from "@/components/ui/Orb"
import GradientText from "@/components/ui/GradientText"
import { useDocumentTheme } from "@/hooks/useDocumentTheme"
import { useHasMounted } from "@/hooks/useHasMounted"

export function HeroSection() {
    const mounted = useHasMounted()
    const titleText = "TruthSeeker"
    const mouseX = useMotionValue(0)
    const mouseY = useMotionValue(0)
    const springX = useSpring(mouseX, { damping: 25, stiffness: 100 })
    const springY = useSpring(mouseY, { damping: 25, stiffness: 100 })

    const card1X = useTransform(springX, v => v * 0.85)
    const card1Y = useTransform(springY, v => v * 0.65)
    const card2X = useTransform(springX, v => v * -0.85)
    const card2Y = useTransform(springY, v => v * -0.65)
    const card3X = useTransform(springX, v => v * 0.55)
    const card3Y = useTransform(springY, v => v * 0.5)
    const card4X = useTransform(springX, v => v * -0.95)
    const card4Y = useTransform(springY, v => v * -0.5)



    useEffect(() => {
        if (!mounted) return

        const handleMouseMove = (e: MouseEvent) => {
            const x = (e.clientX / window.innerWidth - 0.5) * 2
            const y = (e.clientY / window.innerHeight - 0.5) * 2
            mouseX.set(x * 50)
            mouseY.set(y * 50)
        }
        window.addEventListener("mousemove", handleMouseMove)

        return () => {
            window.removeEventListener("mousemove", handleMouseMove)
        }
    }, [mounted, mouseX, mouseY])

    const isDark = useDocumentTheme() === "dark"

    const orbBgColor = isDark ? '#000000' : '#ffffff'
    const orbHue = isDark ? 0 : 347
    const orbIntensity = isDark ? 2 : 1

    if (!mounted) return <div className="min-h-screen" />

    // Animation variants
    const containerVars = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: {
                staggerChildren: 0.15,
            }
        }
    }

    const itemVars = {
        hidden: { opacity: 0, y: 30 },
        show: {
            opacity: 1,
            y: 0,
            transition: { type: "spring", stiffness: 300, damping: 24 } as const
        }
    }

    return (
        <section className={`relative min-h-screen flex items-center justify-center pt-24 pb-20 overflow-hidden transition-colors duration-500 ${isDark ? 'bg-black' : 'bg-white'}`}>
            {/* ReactBits Orb Background */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <Orb 
                   hue={orbHue} 
                   backgroundColor={orbBgColor}
                   hoverIntensity={orbIntensity} 
                   rotateOnHover={true}
                />
            </div>


            {/* Subtle Overlay Grid */}
            <div className="absolute inset-0 pointer-events-none z-[1] grid-bg opacity-10 dark:opacity-20" />

            {/* 4 Agent floating cards — compact one-line version */}
            <div className="absolute inset-0 pointer-events-none z-10 overflow-hidden select-none">
                <div className="relative w-full h-full max-w-7xl mx-auto px-6">
                    {/* Top-Left: Forensics */}
                    <motion.div
                        style={{ x: card1X, y: card1Y }}
                        className="absolute left-[3%] top-[7%] hidden md:flex items-center gap-4 rounded-2xl border border-white/10 shadow-2xl glass-card px-4 py-3 w-60 min-h-[110px] pointer-events-auto hover:border-indigo-500/50 transition-colors group"
                    >
                        <div className="size-11 shrink-0 rounded-xl bg-indigo-500/20 flex items-center justify-center self-start mt-0.5">
                            <Image src="/agent-icons/forensics.svg" alt="视听鉴伪Agent" width={24} height={24} className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[11px] text-indigo-500 dark:text-indigo-300 font-mono font-bold tracking-[0.18em] uppercase">Forensics</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">视听鉴伪Agent</div>
                            <div className="mt-1.5 text-xs leading-5 opacity-80 text-foreground/80">提取视听异常特征，快速定位深伪痕迹。<br />交叉比对视频、音频与图像中的伪造信号。</div>
                        </div>
                    </motion.div>

                    {/* Top-Right: OSINT */}
                    <motion.div
                        style={{ x: card2X, y: card2Y }}
                        className="absolute right-[3%] top-[7%] hidden md:flex items-center gap-4 rounded-2xl border border-white/10 shadow-2xl glass-card px-4 py-3 w-60 min-h-[110px] pointer-events-auto hover:border-emerald-500/50 transition-colors group"
                    >
                        <div className="size-11 shrink-0 rounded-xl bg-emerald-500/20 flex items-center justify-center self-start mt-0.5">
                            <Image src="/agent-icons/osint.svg" alt="情报溯源Agent" width={24} height={24} className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[11px] text-emerald-500 dark:text-emerald-300 font-mono font-bold tracking-[0.18em] uppercase">OSINT</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">情报溯源Agent</div>
                            <div className="mt-1.5 text-xs leading-5 opacity-80 text-foreground/80">追踪传播链路与外部情报，反查内容来源。<br />关联域名、社媒与公开线索还原扩散路径。</div>
                        </div>
                    </motion.div>

                    {/* Bottom-Left: Challenger */}
                    <motion.div
                        style={{ x: card3X, y: card3Y }}
                        className="absolute left-[4%] bottom-[13%] hidden md:flex items-center gap-4 rounded-2xl border border-white/10 shadow-2xl glass-card px-4 py-3 w-60 min-h-[110px] pointer-events-auto hover:border-[#D4FF12]/50 transition-colors group"
                    >
                        <div className="size-11 shrink-0 rounded-xl bg-[#D4FF12]/20 flex items-center justify-center self-start mt-0.5">
                            <Image src="/agent-icons/challenger.svg" alt="逻辑质询Agent" width={24} height={24} className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[11px] text-gray-800 dark:text-[#D4FF12]/80 font-mono font-bold tracking-[0.18em] uppercase">Challenge</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">逻辑质询Agent</div>
                            <div className="mt-1.5 text-xs leading-5 opacity-80 text-foreground/80">识别证据冲突与推理漏洞，触发复核。<br />针对低置信结论主动发起质询与链路校验。</div>
                        </div>
                    </motion.div>

                    {/* Bottom-Right: Commander */}
                    <motion.div
                        style={{ x: card4X, y: card4Y }}
                        className="absolute right-[4%] bottom-[15%] hidden md:flex items-center gap-4 rounded-2xl border border-white/10 shadow-2xl glass-card px-4 py-3 w-60 min-h-[110px] pointer-events-auto hover:border-indigo-500/50 transition-colors group"
                    >
                        <div className="size-11 shrink-0 rounded-xl bg-indigo-500/20 flex items-center justify-center self-start mt-0.5">
                            <Image src="/agent-icons/commander.svg" alt="研判指挥Agent" width={24} height={24} className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[11px] text-indigo-500 dark:text-indigo-300 font-mono font-bold tracking-[0.18em] uppercase">Commander</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">研判指挥Agent</div>
                            <div className="mt-1.5 text-xs leading-5 opacity-80 text-foreground/80">融合多方证据与权重，输出最终结论。<br />形成可追溯的研判依据与整体风险判断。</div>
                        </div>
                    </motion.div>
                </div>
            </div>

            <div className="container mx-auto px-6 max-w-7xl relative z-10 flex flex-col items-center justify-center text-center">
                <motion.div
                    variants={containerVars}
                    initial="hidden"
                    animate="show"
                    className="max-w-4xl"
                >


                    {/* Main Title with gradient text animation */}
                    <div className="relative">
                        <motion.div
                            initial={{ width: "0%" }}
                            animate={{ width: "100%" }}
                            transition={{ duration: 1.5, ease: "circInOut" }}
                            className="absolute -inset-4 bg-gradient-to-r from-primary/0 via-primary/10 to-transparent blur-2xl z-0"
                        />
                        <motion.h1
                            className="text-6xl md:text-8xl lg:text-[110px] font-bold tracking-tighter mb-4 leading-none flex justify-center flex-wrap relative z-10 font-serif drop-shadow-[0_0_40px_rgba(212,255,18,0.4)]"
                        >
                            <GradientText 
                                colors={["#D4FF12", "#c084fc", "#D4FF12", "#c084fc", "#D4FF12"]} 
                                animationSpeed={16}
                                showBorder={false}
                                className=""
                            >
                                {titleText}
                            </GradientText>
                        </motion.h1>
                    </div>

                    {/* Subtitle / Main Description */}
                    <motion.div variants={itemVars} className="mt-8 mb-12 relative flex flex-col items-center">
                        <h2 className="mx-auto inline-grid place-items-center gap-2 text-center font-semibold leading-[1.08] text-foreground dark:text-gray-100">
                            <span className="inline-flex w-full justify-center text-[clamp(2rem,4.2vw,3.9rem)] tracking-[0.08em] whitespace-nowrap text-center">
                                基于多智能体交叉验证的
                            </span>
                            <ShinyText
                                text="跨模态Deepfake鉴伪与溯源系统"
                                className="inline-flex w-full justify-center whitespace-nowrap text-center text-[clamp(1.66rem,3.3vw,3.08rem)] font-bold tracking-[0em] text-black dark:text-white drop-shadow-md"
                                shineColor={isDark ? "#ffffff" : "#aaaaaa"}
                                speed={3}
                            />
                        </h2>
                        <p className="mt-8 text-base md:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed font-light">
                            一个具备专家团队思维的智能研判中枢：利用 FedPaRS 架构保障隐私，通过 LangGraph 编排实现视听、情报、质询、研判四阶闭环分析。
                        </p>
                    </motion.div>

                    {/* Call to Actions */}
                    <motion.div variants={itemVars} className="flex flex-col sm:flex-row items-center justify-center gap-8 mt-10">
                        <Link href="/detect">
                            <div style={{ width: 220, height: 60 }}>
                                <FluidGlassButton color="#6366F1" className="!w-full !h-full border border-white/20 dark:border-white/10">
                                    <span className="text-xl">开始检测</span>
                                    <span className="text-2xl group-hover:translate-x-1 transition-transform">→</span>
                                </FluidGlassButton>
                            </div>
                        </Link>

                        <Link href="#workflow">
                            <div style={{ width: 220, height: 60 }}>
                                <FluidGlassButton color="rgba(212, 255, 18, 0.4)" className="!w-full !h-full border border-black/20 dark:border-white/20">
                                    <span className="text-foreground dark:text-white text-xl">了解检测架构</span>
                                </FluidGlassButton>
                            </div>
                        </Link>
                    </motion.div>
                </motion.div>
            </div>

            {/* Scroll indicator */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.5, duration: 1 }}
                className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3 group cursor-pointer"
                onClick={() => window.scrollTo({ top: window.innerHeight, behavior: 'smooth' })}
            >
                <span className="text-xs text-muted-foreground font-mono uppercase tracking-widest group-hover:text-primary transition-colors">Scroll to explore</span>
                <motion.div
                    animate={{ y: [0, 8, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                    className="w-px h-16 bg-gradient-to-b from-[#6366F1] to-transparent"
                />
            </motion.div>
        </section>
    )
}
