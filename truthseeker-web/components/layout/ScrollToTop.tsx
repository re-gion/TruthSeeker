"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "motion/react"

export function ScrollToTop() {
    const [visible, setVisible] = useState(false)

    useEffect(() => {
        const onScroll = () => {
            setVisible(window.scrollY > 300)
        }
        window.addEventListener("scroll", onScroll, { passive: true })
        return () => window.removeEventListener("scroll", onScroll)
    }, [])

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: "smooth" })
    }

    return (
        <AnimatePresence>
            {visible && (
                <motion.button
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.2 }}
                    onClick={scrollToTop}
                    className="fixed bottom-6 right-6 z-50 w-11 h-11 rounded-full bg-[#6366F1]/80 hover:bg-[#6366F1] text-white flex items-center justify-center shadow-[0_4px_20px_rgba(99,102,241,0.4)] backdrop-blur-sm border border-white/10 transition-colors cursor-pointer"
                    aria-label="回到顶部"
                    title="回到顶部"
                >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="18 15 12 9 6 15" />
                    </svg>
                </motion.button>
            )}
        </AnimatePresence>
    )
}
