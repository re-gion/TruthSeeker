"use client"

import { motion } from "motion/react"

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TimelineEntry {
  round?: number
  agent: string
  type: string
  content: string
  timestamp: string
  phase?: string
  phaseRound?: number
  sourceKind?: "agent" | "timeline" | "audit" | "system"
  action?: string
}

interface EvidenceTimelineProps {
  logs: TimelineEntry[]
  isComplete: boolean
}

/* ------------------------------------------------------------------ */
/*  Agent color config                                                 */
/* ------------------------------------------------------------------ */

const AGENT_CONFIG: Record<string, { color: string; label: string; icon: string }> = {
  forensics:  { color: "#6366F1", label: "取证Agent",  icon: "🔍" },
  osint:      { color: "#10B981", label: "溯源Agent",  icon: "🕵️" },
  challenger: { color: "#F59E0B", label: "质询Agent",  icon: "⚖️" },
  commander:  { color: "#06B6D4", label: "Commander 主持",  icon: "◇" },
  system:     { color: "#94A3B8", label: "系统审计",  icon: "•" },
  audit:      { color: "#94A3B8", label: "系统审计",  icon: "•" },
}

const LOG_TYPE_STYLES: Record<string, { border: string; bg: string }> = {
  thinking:  { border: "border-white/10",  bg: "bg-white/[0.02]" },
  action:    { border: "border-white/10",  bg: "bg-white/[0.03]" },
  finding:   { border: "border-white/20",  bg: "bg-white/[0.04]" },
  challenge: { border: "border-[#F59E0B]/40", bg: "bg-[#F59E0B]/[0.06]" },
  conclusion:{ border: "border-white/20",  bg: "bg-white/[0.05]" },
  audit:     { border: "border-slate-400/25", bg: "bg-slate-400/[0.05]" },
  phase_review: { border: "border-[#F59E0B]/40", bg: "bg-[#F59E0B]/[0.06]" },
  consultation_required: { border: "border-[#F59E0B]/40", bg: "bg-[#F59E0B]/[0.06]" },
  consultation_approval_required: { border: "border-[#F59E0B]/40", bg: "bg-[#F59E0B]/[0.06]" },
  consultation_started: { border: "border-[#06B6D4]/35", bg: "bg-[#06B6D4]/[0.06]" },
  consultation_summary_pending: { border: "border-[#D4FF12]/35", bg: "bg-[#D4FF12]/[0.05]" },
  consultation_summary_confirmed: { border: "border-[#10B981]/35", bg: "bg-[#10B981]/[0.06]" },
  consultation_skipped: { border: "border-slate-400/25", bg: "bg-slate-400/[0.05]" },
  consultation_resumed: { border: "border-[#10B981]/35", bg: "bg-[#10B981]/[0.06]" },
}

const PHASE_ROUND_PREFIX: Record<string, string> = {
  forensics: "Forensics R",
  osint: "OSINT R",
  commander: "Commander R",
}

function timeValue(entry: TimelineEntry) {
  const parsed = Date.parse(entry.timestamp)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatRoundLabel(entry: TimelineEntry) {
  if (entry.agent === "challenger" && entry.phase && entry.phaseRound) {
    return `${PHASE_ROUND_PREFIX[entry.phase] ?? `${entry.phase} R`}${entry.phaseRound}`
  }
  if (entry.sourceKind === "audit" || entry.type === "audit") return "审计"
  if (entry.sourceKind === "timeline") return "阶段"
  return entry.round ? `流程 ${entry.round}` : "流程"
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function EvidenceTimeline({ logs, isComplete }: EvidenceTimelineProps) {
  const orderedLogs = [...logs].sort((a, b) => timeValue(a) - timeValue(b))

  return (
    <div className="relative px-4 py-6 max-w-3xl mx-auto">
      {/* Vertical line */}
      <div className="absolute left-[27px] top-0 bottom-0 w-px bg-white/10" />

      {orderedLogs.map((entry, index) => {
        const cfg = AGENT_CONFIG[entry.agent] || AGENT_CONFIG[entry.sourceKind || ""] || AGENT_CONFIG.forensics
        const typeStyle = LOG_TYPE_STYLES[entry.type] || LOG_TYPE_STYLES.action
        const isChallenge = entry.type === "challenge" || entry.type === "phase_review"
        const isConsultation = entry.type.startsWith("consultation_")
        const isAudit = entry.type === "audit" || entry.sourceKind === "audit"
        const roundLabel = formatRoundLabel(entry)

        return (
          <motion.div
            key={`${entry.timestamp}-${entry.agent}-${entry.type}-${index}`}
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: Math.min(index * 0.03, 0.3), duration: 0.3 }}
            className={`relative pl-12 pb-3 ${isChallenge ? "py-1" : ""}`}
          >
            <div
              className="absolute left-[22px] top-[10px] w-[11px] h-[11px] rounded-full border-2"
              style={{
                borderColor: cfg.color,
                backgroundColor: entry.type === "conclusion" || isAudit ? cfg.color : "transparent",
              }}
            />

            <div className={`${typeStyle.bg} ${typeStyle.border} border rounded-lg px-3 py-2`}>
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
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-white/45 font-mono ml-auto">
                  {roundLabel}
                </span>
                {isChallenge && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#F59E0B]/20 text-[#F59E0B] font-medium">
                    质询
                  </span>
                )}
                {isConsultation && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#06B6D4]/15 text-[#67E8F9] font-medium">
                    会诊
                  </span>
                )}
                {isAudit && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-400/15 text-slate-300 font-medium">
                    审计
                  </span>
                )}
              </div>

              <p className="text-[12px] text-white/70 leading-relaxed break-words">
                {entry.content}
              </p>
            </div>
          </motion.div>
        )
      })}

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
              Commander 裁决完成 - 分析流程结束
            </p>
          </div>
        </motion.div>
      )}
    </div>
  )
}
