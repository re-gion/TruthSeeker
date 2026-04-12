"use client"

import { motion } from "motion/react"

type AgentStatus = "idle" | "analyzing" | "complete" | "error"

interface AgentCardProps {
    name: string
    agentKey: string
    icon: string | React.ReactNode
    status: AgentStatus
    confidence?: number
    description?: string
    children?: React.ReactNode
}

const STATUS_CONFIG: Record<AgentStatus, { label: string; color: string; glowClass: string; pulse: boolean }> = {
    idle: { label: "待命中", color: "#6B7280", glowClass: "", pulse: false },
    analyzing: { label: "分析中", color: "#6366F1", glowClass: "agent-glow-indigo", pulse: true },
    complete: { label: "完成", color: "#10B981", glowClass: "agent-glow-green", pulse: false },
    error: { label: "错误", color: "#EF4444", glowClass: "", pulse: false },
}

const AGENT_COLORS: Record<string, string> = {
    forensics: "#6366F1",
    commander: "#06B6D4",
    osint: "#10B981",
    challenger: "#F59E0B",
}

export function AgentCard({ name, agentKey, icon, status, confidence, description, children }: AgentCardProps) {
    const config = STATUS_CONFIG[status]
    const accentColor = AGENT_COLORS[agentKey] || config.color

    return (
        <motion.div
            className={`glass-card rounded-xl p-4 border transition-all duration-500 ${config.glowClass}`}
            animate={{
                borderColor: status === "analyzing"
                    ? ["rgba(99,102,241,0.3)", "rgba(99,102,241,0.7)", "rgba(99,102,241,0.3)"]
                    : status === "complete"
                        ? "rgba(16,185,129,0.4)"
                        : "rgba(255,255,255,0.08)",
            }}
            transition={status === "analyzing" ? { duration: 2, repeat: Infinity } : { duration: 0.3 }}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className="text-xl">{icon}</span>
                    <div>
                        <div className="text-white text-sm font-semibold">{name}</div>
                        {description && (
                            <div className="text-[#6B7280] text-xs">{description}</div>
                        )}
                    </div>
                </div>

                {/* Status badge */}
                <div className="flex items-center gap-1.5">
                    {config.pulse && (
                        <motion.div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: accentColor }}
                            animate={{ scale: [1, 1.4, 1], opacity: [1, 0.6, 1] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                        />
                    )}
                    {!config.pulse && status !== "idle" && (
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                    )}
                    <span className="text-xs font-mono" style={{ color: config.color }}>
                        {config.label}
                    </span>
                </div>
            </div>

            {/* Confidence bar */}
            {confidence !== undefined && confidence > 0 && (
                <div className="mb-3">
                    <div className="flex justify-between text-xs mb-1">
                        <span className="text-[#6B7280]">置信度</span>
                        <span className="font-mono" style={{ color: accentColor }}>
                            {(confidence * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div className="w-full bg-white/10 rounded-full h-1.5 overflow-hidden">
                        <motion.div
                            className="h-full rounded-full"
                            style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}99)` }}
                            initial={{ width: "0%" }}
                            animate={{ width: `${confidence * 100}%` }}
                            transition={{ duration: 0.8, ease: "easeOut" }}
                        />
                    </div>
                </div>
            )}

            {/* Scan animation when analyzing */}
            {status === "analyzing" && (
                <div className="relative h-0.5 w-full bg-white/5 mb-3 overflow-hidden rounded">
                    <motion.div
                        className="absolute inset-y-0 w-20 rounded"
                        style={{ background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)` }}
                        animate={{ x: ["-80px", "100%"] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                    />
                </div>
            )}

            {/* Children content */}
            {children && <div className="mt-2">{children}</div>}
        </motion.div>
    )
}
