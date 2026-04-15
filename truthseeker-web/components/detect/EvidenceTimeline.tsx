"use client"

import { motion } from "motion/react"

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TimelineEntry {
  round: number
  agent: string
  type: string
  content: string
  timestamp: string
}

interface EvidenceTimelineProps {
  logs: TimelineEntry[]
  isComplete: boolean
}

/* ------------------------------------------------------------------ */
/*  Agent color config                                                 */
/* ------------------------------------------------------------------ */

const AGENT_CONFIG: Record<string, { color: string; label: string; icon: string }> = {
  forensics:  { color: "#6366F1", label: "鉴伪Agent",  icon: "🔍" },
  osint:      { color: "#10B981", label: "溯源Agent",  icon: "🕵️" },
  challenger: { color: "#F59E0B", label: "质询Agent",  icon: "⚖️" },
  commander:  { color: "#06B6D4", label: "指挥Agent",  icon: "👑" },
}

const LOG_TYPE_STYLES: Record<string, { border: string; bg: string }> = {
  thinking:  { border: "border-white/10",  bg: "bg-white/[0.02]" },
  action:    { border: "border-white/10",  bg: "bg-white/[0.03]" },
  finding:   { border: "border-white/20",  bg: "bg-white/[0.04]" },
  challenge: { border: "border-[#F59E0B]/40", bg: "bg-[#F59E0B]/[0.06]" },
  conclusion:{ border: "border-white/20",  bg: "bg-white/[0.05]" },
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function EvidenceTimeline({ logs, isComplete }: EvidenceTimelineProps) {
  // Group logs by round
  const rounds: Record<number, TimelineEntry[]> = {}
  for (const log of logs) {
    const r = log.round || 1
    if (!rounds[r]) rounds[r] = []
    rounds[r].push(log)
  }

  const roundNums = Object.keys(rounds).map(Number).sort((a, b) => a - b)

  return (
    <div className="relative px-4 py-6 max-w-3xl mx-auto">
      {/* Vertical line */}
      <div className="absolute left-[27px] top-0 bottom-0 w-px bg-white/10" />

      {roundNums.map((round, ri) => (
        <div key={round} className="mb-8">
          {/* Round separator */}
          <div className="flex items-center gap-3 mb-4">
            <div className="relative z-10 w-[54px] h-[28px] flex items-center justify-center">
              <div className="bg-[#1a1a2e] border border-white/20 rounded-full px-2.5 py-0.5 text-[10px] font-mono text-white/70">
                R{round}
              </div>
            </div>
            {ri === roundNums.length - 1 && isComplete && (
              <span className="text-[10px] text-[#10B981] font-mono uppercase tracking-wider">
                Final Round
              </span>
            )}
          </div>

          {/* Log entries */}
          {rounds[round].map((entry, ei) => {
            const cfg = AGENT_CONFIG[entry.agent] || AGENT_CONFIG.forensics
            const typeStyle = LOG_TYPE_STYLES[entry.type] || LOG_TYPE_STYLES.action
            const isChallenge = entry.type === "challenge"

            return (
              <motion.div
                key={`${round}-${ei}`}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: ei * 0.06, duration: 0.3 }}
                className={`relative pl-12 pb-3 ${isChallenge ? "py-1" : ""}`}
              >
                {/* Dot on the line */}
                <div
                  className="absolute left-[22px] top-[10px] w-[11px] h-[11px] rounded-full border-2"
                  style={{
                    borderColor: cfg.color,
                    backgroundColor: entry.type === "conclusion" ? cfg.color : "transparent",
                  }}
                />

                {/* Card */}
                <div
                  className={`${typeStyle.bg} ${typeStyle.border} border rounded-lg px-3 py-2`}
                >
                  {/* Header row */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs">{cfg.icon}</span>
                    <span className="text-[11px] font-semibold" style={{ color: cfg.color }}>
                      {cfg.label}
                    </span>
                    <span className="text-[9px] text-white/30 font-mono">
                      {new Date(entry.timestamp).toLocaleTimeString("zh-CN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>
                    {isChallenge && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#F59E0B]/20 text-[#F59E0B] font-medium ml-auto">
                        质疑
                      </span>
                    )}
                  </div>

                  {/* Content */}
                  <p className="text-[12px] text-white/70 leading-relaxed break-words">
                    {entry.content}
                  </p>
                </div>
              </motion.div>
            )
          })}
        </div>
      ))}

      {/* Terminal node — verdict */}
      {isComplete && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="relative pl-12 pb-6"
        >
          <div className="absolute left-[19px] top-0 w-[17px] h-[17px] rounded-full bg-[#06B6D4] shadow-[0_0_12px_#06B6D4]" />
          <div className="bg-[#06B6D4]/10 border border-[#06B6D4]/30 rounded-lg px-4 py-3">
            <p className="text-sm font-semibold text-[#06B6D4]">
              👑 裁决完成 — 分析流程结束
            </p>
          </div>
        </motion.div>
      )}
    </div>
  )
}
