"use client"

import Link from "next/link"
import { motion } from "motion/react"
import { ThemeToggle } from "./ThemeToggle"
import { BrandLogo } from "@/components/logo/BrandLogo"
import { useScrollProgress } from "@/hooks/useScrollProgress"
import { useEffect, useState } from "react"

export function LandingNavbar() {
    const scrollProgress = useScrollProgress()
    const [isScrolled, setIsScrolled] = useState(false)

    useEffect(() => {
        const handleScroll = () => setIsScrolled(window.scrollY > 50)
        handleScroll()
        window.addEventListener("scroll", handleScroll, { passive: true })
        return () => window.removeEventListener("scroll", handleScroll)
    }, [])

    return (
        <motion.header
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled
                ? "py-3 bg-background/80 backdrop-blur-xl border-b border-border shadow-sm"
                : "py-6 bg-transparent"
                }`}
        >
            <div className="container mx-auto px-6 max-w-7xl flex items-center justify-between">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-3 group">
                    <div className="w-10 h-10 flex items-center justify-center relative transition-transform duration-500 group-hover:scale-110">
                        <BrandLogo className="h-9 w-9" imageClassName="drop-shadow-lg" size={36} priority />
                    </div>
                    <div className="flex flex-col">
                        <span className="font-black tracking-tighter text-2xl leading-none">TruthSeeker</span>
                        <span className="text-[10px] text-[#6366F1] font-mono tracking-[0.2em] font-bold opacity-80 uppercase mt-0.5">
                     
                        </span>
                    </div>
                </Link>

                {/* Desktop Nav */}
                <nav className="hidden md:flex items-center gap-8">
                    <Link href="#features" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                        核心能力
                    </Link>
                    <Link href="#workflow" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                        工作流程
                    </Link>
                    <Link href="#technology" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                        底层技术
                    </Link>
                    <Link href="#cases" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                        应用场景
                    </Link>
                </nav>

                {/* Actions */}
                <div className="flex items-center gap-4">
                    <ThemeToggle />

                    <Link href="/detect">
                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="px-5 py-2.5 rounded-full bg-foreground text-background font-medium text-sm transition-all hover:bg-foreground/90 shadow-lg flex items-center gap-2 group"
                        >
                            <span>进入控制台</span>
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="16" height="16" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                className="transform transition-transform group-hover:translate-x-1"
                            >
                                <path d="M5 12h14" />
                                <path d="m12 5 7 7-7 7" />
                            </svg>
                        </motion.button>
                    </Link>
                </div>
            </div>

            {/* Scroll Progress Bar */}
            <div
                className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-[#6366F1] to-[#D4FF12] origin-left"
                style={{ width: `${scrollProgress * 100}%` }}
            />
        </motion.header>
    )
}
