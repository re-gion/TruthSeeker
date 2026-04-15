"use client"

import { useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "motion/react"
import { useAgentStream } from "@/hooks/useAgentStream"
import { useRealtimeSession, UserRole } from "@/hooks/useRealtimeSession"
import { AgentLog } from "@/components/agents/AgentLog"
import { AgentCard } from "@/components/agents/AgentCard"
import { PresenceAvatars } from "@/components/collaboration/PresenceAvatars"
import { InviteButton } from "@/components/collaboration/InviteButton"
import { ExpertPanel } from "@/components/collaboration/ExpertPanel"
import { EvidenceTimeline } from "@/components/detect/EvidenceTimeline"
import dynamic from "next/dynamic"
const BentoScene = dynamic(() => import("@/components/bento/BentoScene").then(mod => mod.BentoScene), { ssr: false })
import { generateMarkdownReport, downloadMarkdownReport, downloadPdfReport } from "@/lib/report"

import Link from "next/link"
import { useState } from "react"
import StarBackground from "@/components/ui/StarBackground"

function VerdictBadge({ verdict }: { verdict: Record<string, unknown> }) {
    const v = verdict.verdict as string
    const configs: Record<string, { color: string; bg: string; border: string; emoji: string }> = {
        forged: { color: "#EF4444", bg: "rgba(239,68,68,0.1)", border: "rgba(239,68,68,0.3)", emoji: "🚨" },
        suspicious: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.3)", emoji: "⚠️" },
        authentic: { color: "#10B981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.3)", emoji: "✅" },
        inconclusive: { color: "#6B7280", bg: "rgba(107,114,128,0.1)", border: "rgba(107,114,128,0.3)", emoji: "❓" },
    }
    const cfg = configs[v] || configs.inconclusive
    const confidence = verdict.confidence as number

    return (
        <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-xl p-4 border glass-card"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
        >
            <div className="text-2xl mb-1">{cfg.emoji}</div>
            <div className="font-bold text-lg" style={{ color: cfg.color }}>
                {verdict.verdict as string}
            </div>
            <div className="text-sm text-[#C0C0C0] mt-1">{verdict.verdict_cn as string}</div>
            <div className="mt-2 font-mono text-xs" style={{ color: cfg.color }}>
                综合置信度 {((confidence || 0) * 100).toFixed(1)}%
            </div>
            {(verdict.key_evidence as Array<{type?: string; source?: string; confidence?: number}>)?.map((e, i) => (
                <div key={i} className="mt-1 text-xs text-[#C0C0C0]">· [{e.type || '?'}] {e.source || ''} ({((e.confidence || 0) * 100).toFixed(0)}%)</div>
            ))}
        </motion.div>
    )
}

function DebateStats({ currentRound, maxRounds, weights }: { currentRound: number, maxRounds: number, weights: Record<string, number> }) {
    return (
        <div className="flex items-center gap-4 liquid-glass rounded-lg px-4 py-2 border border-white/10 shadow-sm">
            <div className="flex flex-col">
                <span className="text-[10px] text-[#6B7280] uppercase tracking-wider">辩论轮次</span>
                <div className="flex items-baseline gap-1">
                    <span className="text-white font-mono font-bold">{currentRound}</span>
                    <span className="text-[#6B7280] font-mono text-xs">/ {maxRounds}</span>
                </div>
            </div>

            <div className="w-px h-6 bg-white/10" />

            <div className="flex-1 flex flex-col gap-1">
                <span className="text-[10px] text-[#6B7280] uppercase tracking-wider">当前决策权重分布</span>
                <div className="h-1.5 w-full bg-white/10 rounded-full flex overflow-hidden">
                    <motion.div
                        className="h-full bg-[#6366F1]"
                        animate={{ width: `${(weights.forensics || 0) * 100}%` }}
                        transition={{ duration: 0.5 }}
                        title="视听鉴伪Agent权重"
                    />
                    <motion.div
                        className="h-full bg-[#10B981]"
                        animate={{ width: `${(weights.osint || 0) * 100}%` }}
                        transition={{ duration: 0.5 }}
                        title="溯源情报权重"
                    />
                    <motion.div
                        className="h-full bg-[#F59E0B]"
                        animate={{ width: `${(weights.challenger || 0) * 100}%` }}
                        transition={{ duration: 0.5 }}
                        title="逻辑质询权重"
                    />
                </div>
            </div>
        </div>
    )
}

export function DetectConsole({ taskId }: { taskId: string }) {
    const searchParams = useSearchParams()
    const inputType = searchParams.get("type") || "video"
    const fileUrl = searchParams.get("url") || `mock://${taskId}`
    const role = (searchParams.get("role") || "host") as UserRole
    const [showExpertPanel, setShowExpertPanel] = useState(false)
    const [viewMode, setViewMode] = useState<"2d" | "3d" | "timeline">("3d")

    const { channel, onlineUsers } = useRealtimeSession(taskId, role)

    const {
        logs, forensicsResult, osintResult, challengerFeedback,
        agentWeights, finalVerdict, isRunning, isComplete,
        currentNode, currentRound, maxRounds
    } = useAgentStream({ taskId, inputType, fileUrl, autoStart: true, role, channel })

    const agentStatus = (key: string, hasResult: boolean) =>
        currentNode === key ? "analyzing" : hasResult ? "complete" : "idle"

    return (
        <div className="min-h-screen relative flex flex-col bg-black overflow-hidden">
            <div className="absolute inset-0 pointer-events-none z-0">
                <StarBackground
                    mouseInteraction={true}
                    mouseRepulsion={viewMode === "2d"}
                    density={1.5}
                    glowIntensity={0.2}
                    saturation={0}
                    hueShift={120}
                    twinkleIntensity={0}
                    rotationSpeed={0}
                    repulsionStrength={0}
                    autoCenterRepulsion={0}
                    starSpeed={0.5}
                    speed={0.5}
                />
            </div>
            
            <div className="relative z-10 flex-1 flex flex-col">

            {/* Header */}
            <header className="px-6 py-3 flex items-center justify-between border-b border-white/5 bg-black/50 backdrop-blur-md sticky top-0 z-50">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-[#6B7280] hover:text-white text-sm transition-colors flex items-center gap-1">
                        <span>←</span> 返回
                    </Link>
                    <div className="w-px h-4 bg-white/10" />
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-6 flex items-center justify-center relative transition-transform duration-500 hover:scale-110">
                            <svg width="24" height="24" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="drop-shadow-sm">
                                {/* The "S" curve */}
                                <path d="M 45 25 C 10 30 15 70 45 80" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                                {/* The dot */}
                                <circle cx="48" cy="18" r="8" fill="#6366F1" />
                                {/* The "T" cap and stem */}
                                <path d="M 40 38 L 85 38" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                                <path d="M 60 38 L 65 75" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                                {/* The right arc */}
                                <path d="M 65 80 C 85 75 90 55 85 45" stroke="#6366F1" strokeWidth="10" strokeLinecap="round" />
                            </svg>
                        </div>
                        <span className="text-white font-semibold text-sm tracking-wide">四智能体协同检测控制台</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded border border-[#D4FF12]/30 text-[#D4FF12] font-mono tracking-wider ml-1 bg-[#D4FF12]/5">LAYER 3</span>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {/* Layer 3: 团队协作状态 */}
                    <div className="hidden lg:flex items-center gap-4">
                        <button
                            onClick={() => setViewMode(v => v === 'timeline' ? '3d' : 'timeline')}
                            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                                viewMode === 'timeline'
                                    ? 'text-[#6366F1] border border-[#6366F1]/30 hover:bg-[#6366F1]/10'
                                    : 'text-[#06B6D4] border border-[#06B6D4]/30 hover:bg-[#06B6D4]/10'
                            }`}
                        >
                            {viewMode === 'timeline' ? '返回 Agent 视图' : '时间轴视图'}
                        </button>
                        <button
                            onClick={() => setViewMode(v => v === '3d' ? '2d' : '3d')}
                            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                                viewMode === '2d'
                                    ? 'text-[#06B6D4] border border-[#06B6D4]/30 hover:bg-[#06B6D4]/10'
                                    : 'text-white/50 border border-white/10 hover:bg-white/5'
                            }`}
                        >
                            {viewMode === '3d' ? '2D 正交' : '3D 拟真'}
                        </button>
                        <button
                            onClick={() => setShowExpertPanel(!showExpertPanel)}
                            className="text-xs text-[#D4FF12] border border-[#D4FF12]/30 px-3 py-1.5 rounded-full hover:bg-[#D4FF12]/10 transition-colors"
                        >
                            {showExpertPanel ? '收起会诊面板' : '打开会诊面板'}
                        </button>
                        {role === 'host' && <InviteButton taskId={taskId} />}
                        {isComplete && (
                            <button
                                onClick={() => {
                                    const md = generateMarkdownReport({
                                        taskId, inputType, logs,
                                        forensicsResult, osintResult,
                                        challengerFeedback, finalVerdict,
                                        agentWeights, currentRound,
                                    })
                                    downloadMarkdownReport(md, `truthseeker-report-${taskId.slice(0, 8)}.md`)
                                }}
                                className="text-xs text-[#10B981] border border-[#10B981]/30 px-3 py-1.5 rounded-full hover:bg-[#10B981]/10 transition-colors"
                            >
                                MD 报告
                            </button>
                        )}
                        {isComplete && (
                            <button
                                onClick={() => downloadPdfReport(taskId)}
                                className="text-xs text-[#EF4444] border border-[#EF4444]/30 px-3 py-1.5 rounded-full hover:bg-[#EF4444]/10 transition-colors"
                            >
                                PDF 报告
                            </button>
                        )}
                        <PresenceAvatars users={onlineUsers} />
                    </div>

                    {/* Layer 2: 顶部辩论统计 */}
                    {(currentRound > 1 || Object.keys(agentWeights).length > 0) && (
                        <div className="hidden md:block w-64">
                            <DebateStats currentRound={currentRound} maxRounds={maxRounds} weights={agentWeights} />
                        </div>
                    )}

                    <div className="flex items-center gap-2">
                        {isRunning && (
                            <motion.div
                                className="flex items-center gap-1.5 text-xs text-[#D4FF12]"
                                animate={{ opacity: [1, 0.5, 1] }}
                                transition={{ duration: 1.5, repeat: Infinity }}
                            >
                                <div className="w-1.5 h-1.5 rounded-full bg-[#D4FF12] pulse-dot shadow-[0_0_8px_#D4FF12]" />
                                AI 联合推演中
                            </motion.div>
                        )}
                        {isComplete && (
                            <div className="flex items-center gap-1.5 text-xs text-[#10B981]">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_8px_#10B981]" />
                                报告已生成
                            </div>
                        )}
                    </div>
                </div>
            </header>

            {/* Content Area */}
            {viewMode === "3d" ? (
                <div className="flex-1 w-full relative overflow-hidden">
                    <BentoScene
                        osintNode={
                            <>
                                <AgentCard name="情报溯源Agent" agentKey="osint" icon={<img src="/agent-icons/osint.svg" alt="情报溯源Agent" className="w-5 h-5" />} status={agentStatus("osint", !!osintResult)} confidence={osintResult ? (osintResult.confidence as number) : undefined} description="网络威胁情报 · 路由追踪" />
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-auto min-h-0"><AgentLog logs={logs.filter(l => l.agent === "osint")} maxHeight="100%" /></div>
                            </>
                        }
                        forensicsNode={
                            <>
                                <AgentCard name="视听鉴伪Agent" agentKey="forensics" icon={<img src="/agent-icons/forensics.svg" alt="视听鉴伪Agent" className="w-5 h-5" />} status={agentStatus("forensics", !!forensicsResult)} confidence={forensicsResult?.confidence as number | undefined} description="Deepfake 模型检测 · 异常提取" />
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-auto min-h-0"><AgentLog logs={logs.filter(l => l.agent === "forensics")} maxHeight="100%" /></div>
                            </>
                        }
                        challengerNode={
                            <>
                                <AgentCard name="逻辑质询Agent" agentKey="challenger" icon={<img src="/agent-icons/challenger.svg" alt="逻辑质询Agent" className="w-5 h-5" />} status={agentStatus("challenger", !!challengerFeedback)} confidence={challengerFeedback ? (challengerFeedback.quality_score as number) : undefined} description="跨模态矛盾检测 · 置信校验" />
                                {!!challengerFeedback?.requires_more_evidence && (
                                    <div className="bg-[#F59E0B]/20 border border-[#F59E0B]/50 rounded-lg p-2 text-xs text-[#F59E0B]">🔄 发现矛盾，触发重审</div>
                                )}
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-auto min-h-0"><AgentLog logs={logs.filter(l => l.agent === "challenger")} maxHeight="100%" /></div>
                            </>
                        }
                        commanderNode={
                            <>
                                <AgentCard name="研判指挥Agent" agentKey="commander" icon={<img src="/agent-icons/commander.svg" alt="研判指挥Agent" className="w-5 h-5" />} status={agentStatus("commander", !!finalVerdict)} confidence={finalVerdict?.confidence as number | undefined} description="多维向量收敛中心 · 最终判决" />
                                <div className="flex-1 overflow-auto min-h-0 flex flex-col">
                                    {finalVerdict ? <VerdictBadge verdict={finalVerdict} /> : <div className="rounded-xl liquid-glass p-2 border border-white/10 flex-1"><AgentLog logs={logs.filter(l => l.agent === "commander")} maxHeight="100%" /></div>}
                                </div>
                            </>
                        }
                        activeAgent={currentNode || (isComplete ? 'commander' : null)}
                    />
                </div>
            ) : (
                <div className="flex-1 p-4 grid grid-cols-1 md:grid-cols-2 gap-4 max-w-7xl mx-auto w-full auto-rows-fr">
                    {/* 左上：媒体与溯源（OSINT） */}
                    <motion.div
                        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
                        className={`liquid-glass border border-white/10 shadow-lg rounded-2xl p-5 flex flex-col gap-4 min-h-[300px] transition-all duration-500 ${agentStatus("osint", !!osintResult) === "analyzing" ? "agent-glow-green" : ""}`}
                    >
                        <AgentCard
                            name="情报溯源Agent"
                            agentKey="osint"
                            icon={<img src="/agent-icons/osint.svg" alt="情报溯源Agent" className="w-5 h-5" />}
                            status={agentStatus("osint", !!osintResult)}
                            confidence={osintResult ? (osintResult.confidence as number) : undefined}
                            description="网络威胁情报 · 路由追踪 · 元数据校验"
                        />
                        <div className="flex-1 rounded-xl glass-card p-3 min-h-[140px] overflow-hidden">
                            <AgentLog logs={logs.filter(l => l.agent === "osint")} maxHeight="100%" />
                        </div>
                    </motion.div>

                    {/* 右上：法医分析 */}
                    <motion.div
                        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                        className={`liquid-glass border border-white/10 shadow-lg rounded-2xl p-5 flex flex-col gap-4 min-h-[300px] transition-all duration-500 ${agentStatus("forensics", !!forensicsResult) === "analyzing" ? "agent-glow-indigo" : ""}`}
                    >
                        <AgentCard
                            name="视听鉴伪Agent"
                            agentKey="forensics"
                            icon={<img src="/agent-icons/forensics.svg" alt="视听鉴伪Agent" className="w-5 h-5" />}
                            status={agentStatus("forensics", !!forensicsResult)}
                            confidence={forensicsResult?.confidence as number | undefined}
                            description="Deepfake 模型检测 · 像素级异常提取"
                        />
                        <div className="flex-1 rounded-xl glass-card p-3 min-h-[140px] overflow-hidden">
                            <AgentLog logs={logs.filter(l => l.agent === "forensics")} maxHeight="100%" />
                        </div>
                    </motion.div>

                    {/* 左下：逻辑质询Agent */}
                    <motion.div
                        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
                        className={`liquid-glass border border-white/10 shadow-lg rounded-2xl p-5 flex flex-col gap-4 min-h-[300px] transition-all duration-500 ${agentStatus("challenger", !!challengerFeedback) === "analyzing" ? "agent-glow-amber" : ""}`}
                    >
                        <AgentCard
                            name="逻辑质询Agent"
                            agentKey="challenger"
                            icon={<img src="/agent-icons/challenger.svg" alt="逻辑质询Agent" className="w-5 h-5" />}
                            status={agentStatus("challenger", !!challengerFeedback)}
                            confidence={challengerFeedback ? (challengerFeedback.quality_score as number) : undefined}
                            description="跨模态矛盾检测 · 置信度自适应校验"
                        />

                        {/* 重审提示条 */}
                        <AnimatePresence>
                            {!!challengerFeedback?.requires_more_evidence && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded-lg p-2.5 flex items-center gap-2"
                                >
                                    <span className="animate-pulse">🔄</span>
                                    <span className="text-xs text-[#F59E0B]">发现证据矛盾，触发深度研判机制重审</span>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <div className="flex-1 rounded-xl glass-card p-3 min-h-[140px] overflow-hidden">
                            <AgentLog logs={logs.filter(l => l.agent === "challenger")} maxHeight="100%" />
                        </div>
                    </motion.div>

                    {/* 右下：研判指挥Agent */}
                    <motion.div
                        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                        className={`liquid-glass border border-white/10 shadow-lg rounded-2xl p-5 flex flex-col gap-4 min-h-[300px] transition-all duration-500 ${agentStatus("commander", !!finalVerdict) === "analyzing" ? "agent-glow-cyan" : ""}`}
                    >
                        <AgentCard
                            name="研判指挥Agent"
                            agentKey="commander"
                            icon={<img src="/agent-icons/commander.svg" alt="研判指挥Agent" className="w-5 h-5" />}
                            status={agentStatus("commander", !!finalVerdict)}
                            confidence={finalVerdict?.confidence as number | undefined}
                            description="多维向量收敛中心 · 最终判决生成"
                        />
                        <div className="flex-1 min-h-[120px] overflow-hidden flex flex-col">
                            <AnimatePresence mode="wait">
                                {finalVerdict ? (
                                    <motion.div
                                        key="verdict"
                                        className="flex-1"
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                    >
                                        <VerdictBadge verdict={finalVerdict} />
                                    </motion.div>
                                ) : (
                                    <motion.div
                                        key="logs"
                                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                        className="rounded-xl glass-card p-3 flex-1"
                                    >
                                        <AgentLog logs={logs.filter(l => l.agent === "commander")} maxHeight="100%" />
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                </div>
            )}

            {/* Timeline View */}
            {viewMode === "timeline" && (
                <div className="flex-1 overflow-auto">
                    <EvidenceTimeline logs={logs as any} isComplete={isComplete} />
                </div>
            )}

            {/* Mobile Stats */}
            <div className="md:hidden px-4 pb-4">
                {(currentRound > 1 || Object.keys(agentWeights).length > 0) && (
                    <DebateStats currentRound={currentRound} maxRounds={maxRounds} weights={agentWeights} />
                )}
            </div>

            {/* Expert Panel Overlay */}
            <AnimatePresence>
                {showExpertPanel && (
                    <motion.div
                        initial={{ x: 400, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 400, opacity: 0 }}
                        className="fixed right-4 top-20 bottom-4 w-80 z-40 hidden lg:block"
                    >
                        <ExpertPanel channel={channel} currentRole={role} />
                    </motion.div>
                )}
            </AnimatePresence>
            </div>
        </div>
    )
}
