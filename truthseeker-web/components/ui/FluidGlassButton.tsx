"use client"

import { ReactNode, useState } from "react"
import { motion, AnimatePresence } from "motion/react"

interface FluidGlassButtonProps {
    children: ReactNode
    onClick?: () => void
    className?: string
    color?: string
}

/**
 * Premium Glass Button with pure CSS/Motion (Removing R3F to avoid rendering issues)
 */
export default function FluidGlassButton({
    children,
    onClick,
    className = "",
    color = "#6366F1"
}: FluidGlassButtonProps) {
    const [isHovered, setIsHovered] = useState(false)

    return (
        <motion.button
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onClick={onClick}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`
                relative px-8 py-4 rounded-2xl overflow-hidden
                border border-white/10 glass-card
                transition-all duration-300 group
                ${className}
            `}
        >
            {/* Background Gradient & Blur */}
            <div 
                className="absolute inset-0 opacity-10 group-hover:opacity-20 transition-opacity duration-500 -z-10"
                style={{ background: `linear-gradient(135deg, ${color}, transparent)` }}
            />
            
            {/* Glow effect on hover */}
            <div 
                className="absolute inset-0 -z-20 blur-2xl opacity-0 group-hover:opacity-30 transition-opacity duration-500"
                style={{ backgroundColor: color }}
            />

            {/* Content Container */}
            <div className="relative z-10 flex items-center justify-center gap-3 text-white font-medium">
                {children}
            </div>

            {/* Shine effect overlay */}
            <AnimatePresence>
                {isHovered && (
                    <motion.div
                        initial={{ left: '-100%', opacity: 0 }}
                        animate={{ left: '100%', opacity: 0.4 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.8, ease: "easeInOut", repeat: Infinity, repeatDelay: 1 }}
                        className="absolute top-0 bottom-0 w-1/2 bg-gradient-to-r from-transparent via-white/30 to-transparent skew-x-[-20deg] pointer-events-none z-20"
                    />
                )}
            </AnimatePresence>

            {/* Inner Border Glow */}
            <div className="absolute inset-0 rounded-2xl border border-white/5 group-hover:border-white/20 transition-colors pointer-events-none" />
        </motion.button>
    )
}
