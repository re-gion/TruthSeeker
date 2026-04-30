"use client"

import { useSearchParams, useRouter } from "next/navigation"
import { motion, AnimatePresence } from "motion/react"
import Image from "next/image"
import { useAgentStream } from "@/hooks/useAgentStream"
import { useRealtimeSession, UserRole } from "@/hooks/useRealtimeSession"
import { AgentLog } from "@/components/agents/AgentLog"
import { AgentCard } from "@/components/agents/AgentCard"
import { PresenceAvatars } from "@/components/collaboration/PresenceAvatars"
import { InviteButton } from "@/components/collaboration/InviteButton"
import { ExpertPanel } from "@/components/collaboration/ExpertPanel"
import { EvidenceTimeline } from "@/components/detect/EvidenceTimeline"
import { ProvenanceGraphView } from "@/components/detect/ProvenanceGraphView"
import dynamic from "next/dynamic"
const BentoScene = dynamic(() => import("@/components/bento/BentoScene").then(mod => mod.BentoScene), { ssr: false })
import { extractAnalysisSnapshot, extractChallengerSnapshot, extractVerdictSnapshot, downloadCanonicalMarkdownReport, downloadPdfReport } from "@/lib/report"
import type { ProvenanceGraph } from "@/lib/provenance-graph"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import StarBackground from "@/components/ui/StarBackground"
import { getAuthToken } from "@/lib/auth"

interface TaskContext {
    inputType: string
    priorityFocus: string
    casePrompt: string
    files: Record<string, unknown>[]
    title?: string
    status?: string
}

function VerdictBadge({ verdict }: { verdict: Record<string, unknown> }) {
    const normalized = extractVerdictSnapshot(verdict)
    const configs: Record<string, { color: string; bg: string; border: string; emoji: string }> = {
        forged: { color: "#EF4444", bg: "rgba(239,68,68,0.1)", border: "rgba(239,68,68,0.3)", emoji: "🚨" },
        suspicious: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.3)", emoji: "⚠️" },
        authentic: { color: "#10B981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.3)", emoji: "✅" },
        inconclusive: { color: "#6B7280", bg: "rgba(107,114,128,0.1)", border: "rgba(107,114,128,0.3)", emoji: "❓" },
    }
    const cfg = configs[normalized.verdict] || configs.inconclusive

    return (
        <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-xl p-4 border glass-card"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
        >
            <div className="text-2xl mb-1">{cfg.emoji}</div>
            <div className="font-bold text-lg" style={{ color: cfg.color }}>
                {normalized.verdict}
            </div>
            <div className="text-sm text-[#C0C0C0] mt-1">{normalized.verdictLabel}</div>
            <div className="mt-2 font-mono text-xs" style={{ color: cfg.color }}>
                综合置信度 {(normalized.confidence * 100).toFixed(1)}%
            </div>
            {normalized.evidence.map((e, i) => (
                <div key={i} className="mt-1 text-xs text-[#C0C0C0]">· {e}</div>
            ))}
        </motion.div>
    )
}

interface WorkflowLog {
    agent: string
    type: string
    content: string
    timestamp: string
    round?: number
    phase?: string
    phaseRound?: number
    sourceKind?: string
    action?: string
}

interface WorkflowStep {
    key: string
    title: string
    detail: string
    tone: "ready" | "running" | "complete" | "waiting"
}

const AGENT_FLOW_LABELS: Record<string, string> = {
    forensics: "电子取证 Agent",
    osint: "情报溯源 Agent",
    challenger: "逻辑质询 Agent",
    commander: "研判指挥 Agent",
    system: "系统",
}

const CHALLENGER_TARGET_LABELS: Record<string, string> = {
    forensics: "电子取证 Agent",
    osint: "情报溯源 Agent",
    commander: "研判指挥 Agent",
}

function agentFlowLabel(agent?: string) {
    return AGENT_FLOW_LABELS[agent || "system"] || agent || "系统"
}

function phaseTargetLabel(phase?: string) {
    return CHALLENGER_TARGET_LABELS[phase || ""] || agentFlowLabel(phase)
}

function challengerFlowTitle(phase: string | undefined, round: number) {
    if (phase === "forensics") return `逻辑质询 Agent vs 电子取证 Agent 第${round}轮`
    if (phase === "osint") return `逻辑质询 Agent vs 情报溯源 Agent 第${round}轮`
    if (phase === "commander") return `逻辑质询 Agent vs 研判指挥 Agent 第${round}轮`
    return `逻辑质询 Agent vs ${phaseTargetLabel(phase)} 第${round}轮`
}

function summarizeWorkflowLog(log: WorkflowLog): WorkflowStep | null {
    const action = log.action || log.type
    if (action === "upload_completed" || action === "upload_input") {
        return { key: `${log.timestamp}|upload`, title: "上传输入", detail: log.content || "检材文件与检测目标已接收", tone: "complete" }
    }
    if (action === "task_created" || action === "create_task") {
        return { key: `${log.timestamp}|task`, title: "创建任务", detail: log.content || "检测任务已写入队列", tone: "complete" }
    }
    if (action === "detect_start") {
        return { key: `${log.timestamp}|detect_start`, title: "开始检测", detail: log.content || "四 Agent 工作流启动", tone: "running" }
    }
    if (action === "detect_completed" || action === "report_generated") {
        return { key: `${log.timestamp}|report`, title: "报告已生成", detail: log.content || "鉴伪与溯源报告完成", tone: "complete" }
    }
    if (log.agent === "challenger") {
        const round = log.phaseRound || log.round || 1
        return {
            key: `${log.timestamp}|challenger|${log.phase || "phase"}|${round}`,
            title: challengerFlowTitle(log.phase, round),
            detail: log.content || "交叉验证阶段证据、置信度和残留风险",
            tone: "running",
        }
    }
    if (log.agent === "forensics") {
        return {
            key: `${log.timestamp}|forensics|${action}`,
            title: action === "node_complete" ? "电子取证 Agent 完成取证" : "电子取证 Agent 开始取证",
            detail: log.content || "自主读取检材并调用取证工具",
            tone: action === "node_complete" ? "complete" : "running",
        }
    }
    if (log.agent === "osint") {
        return {
            key: `${log.timestamp}|osint|${action}`,
            title: action === "node_complete" ? "情报溯源 Agent 完成溯源" : "情报溯源 Agent 开始溯源",
            detail: log.content || "自主提取线索并调用开源情报工具",
            tone: action === "node_complete" ? "complete" : "running",
        }
    }
    if (log.agent === "commander") {
        return {
            key: `${log.timestamp}|commander|${action}`,
            title: action === "node_complete" ? "研判指挥 Agent 完成裁决" : "研判指挥 Agent 开始裁决",
            detail: log.content || "融合多 Agent 证据并生成最终研判",
            tone: action === "node_complete" ? "complete" : "running",
        }
    }
    return null
}

function buildSystemWorkflow({
    logs,
    taskLoaded,
    fileCount,
    currentNode,
    isRunning,
    isComplete,
    isWaitingConsultation,
}: {
    logs: WorkflowLog[]
    taskLoaded: boolean
    fileCount: number
    currentNode: string | null
    isRunning: boolean
    isComplete: boolean
    isWaitingConsultation: boolean
}) {
    const steps: WorkflowStep[] = [
        {
            key: "base-upload",
            title: "上传输入",
            detail: fileCount > 0 ? `${fileCount} 个检材进入检测上下文` : "等待检材与检测目标",
            tone: taskLoaded || fileCount > 0 ? "complete" : "ready",
        },
        {
            key: "base-task",
            title: "创建任务",
            detail: taskLoaded ? "任务上下文已加载" : "等待任务创建完成",
            tone: taskLoaded ? "complete" : "ready",
        },
    ]

    if (isRunning || logs.length > 0 || isComplete) {
        steps.push({
            key: "base-detect",
            title: "开始检测",
            detail: "四 Agent 按阶段接力研判",
            tone: isComplete ? "complete" : "running",
        })
    }

    const seen = new Set(steps.map(step => `${step.title}|${step.detail}`))
    for (const log of logs) {
        const step = summarizeWorkflowLog(log)
        if (!step) continue
        const key = `${step.title}|${step.detail}`
        if (seen.has(key)) continue
        seen.add(key)
        steps.push(step)
    }

    if (isWaitingConsultation) {
        steps.push({
            key: "waiting-consultation",
            title: "等待专家会诊",
            detail: "逻辑质询暂停，等待人工意见回填",
            tone: "waiting",
        })
    } else if (currentNode && isRunning) {
        steps.push({
            key: `active-${currentNode}`,
            title: `${agentFlowLabel(currentNode)} 运行中`,
            detail: "正在更新证据板与时间线",
            tone: "running",
        })
    }

    if (isComplete && !steps.some(step => step.title === "报告已生成")) {
        steps.push({
            key: "complete-report",
            title: "报告已生成",
            detail: "鉴伪与溯源报告完成",
            tone: "complete",
        })
    }

    return steps.slice(-7)
}

function SystemFlowBoard({ steps }: { steps: WorkflowStep[] }) {
    let activeIndex = steps.length - 1
    for (let index = steps.length - 1; index >= 0; index -= 1) {
        if (steps[index].tone === "running" || steps[index].tone === "waiting") {
            activeIndex = index
            break
        }
    }
    const current = steps[activeIndex] || steps[steps.length - 1]
    const progress = steps.length > 1 ? ((activeIndex + 1) / steps.length) * 100 : 10

    return (
        <div className="liquid-glass rounded-lg px-3 py-1.5 border border-white/10 shadow-sm w-full md:w-[300px] md:max-w-[28vw]">
            <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                    <div className="text-[10px] text-[#6B7280] uppercase tracking-wider">系统流程</div>
                    <div className="truncate text-xs font-medium text-white">{current?.title || "等待流程启动"}</div>
                </div>
                <div className="flex items-center gap-1 text-[10px] text-[#10B981] shrink-0">
                    <span className="h-1 w-1 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]" />
                    实时推进
                </div>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-[#6366F1] via-[#10B981] to-[#F59E0B]"
                    animate={{ width: `${Math.min(100, Math.max(8, progress))}%` }}
                    transition={{ duration: 0.45 }}
                />
            </div>
        </div>
    )
}

export function DetectConsole({ taskId }: { taskId: string }) {
    const router = useRouter()
    const searchParams = useSearchParams()
    const role = (searchParams.get("role") || "host") as UserRole
    const inviteToken = searchParams.get("invite_token")
    const [showExpertPanel, setShowExpertPanel] = useState(false)
    const [viewMode, setViewMode] = useState<"3d" | "timeline" | "graph">("3d")
    const [taskContext, setTaskContext] = useState<TaskContext>({
        inputType: "text",
        priorityFocus: searchParams.get("focus") || "balanced",
        casePrompt: "",
        files: [],
    })
    const [taskLoaded, setTaskLoaded] = useState(role === "expert")
    const [taskLoadError, setTaskLoadError] = useState<string | null>(null)

    const { channel, onlineUsers } = useRealtimeSession(taskId, role)

    const {
        logs, forensicsResult, osintResult, challengerFeedback,
        finalVerdict, isRunning, isComplete,
        currentNode, currentRound, isWaitingConsultation,
        errorMessage, consultationState, resume
    } = useAgentStream({
        taskId,
        inputType: taskContext.inputType,
        files: taskContext.files,
        casePrompt: taskContext.casePrompt,
        priorityFocus: taskContext.priorityFocus,
        autoStart: role === "host" && taskLoaded && taskContext.status !== "completed" && taskContext.status !== "waiting_consultation" && taskContext.status !== "waiting_consultation_approval",
        role,
        inviteToken,
        channel,
    })
    const forensicsSnapshot = forensicsResult ? extractAnalysisSnapshot(forensicsResult) : null
    const osintSnapshot = osintResult ? extractAnalysisSnapshot(osintResult) : null
    const challengerSnapshot = challengerFeedback ? extractChallengerSnapshot(challengerFeedback) : null
    const verdictSnapshot = finalVerdict ? extractVerdictSnapshot(finalVerdict) : null
    const provenanceGraph = (
        finalVerdict?.provenance_graph && typeof finalVerdict.provenance_graph === "object"
            ? finalVerdict.provenance_graph
            : null
    ) as ProvenanceGraph | null
    const timelineLogs = logs.map(log => ({
        round: log.round ?? currentRound,
        agent: log.agent,
        type: log.type ?? "action",
        content: log.content,
        timestamp: log.timestamp ?? new Date(0).toISOString(),
        phase: log.phase,
        phaseRound: log.phaseRound,
        sourceKind: log.sourceKind,
        action: log.action,
    }))
    const workflowSteps = useMemo(() => buildSystemWorkflow({
        logs: timelineLogs,
        taskLoaded,
        fileCount: taskContext.files.length,
        currentNode,
        isRunning,
        isComplete,
        isWaitingConsultation,
    }), [currentNode, isComplete, isRunning, isWaitingConsultation, taskContext.files.length, taskLoaded, timelineLogs])

    const agentStatus = (key: string, hasResult: boolean) =>
        currentNode === key ? "analyzing" : hasResult ? "complete" : "idle"
    const backgroundDensity = viewMode === "timeline" ? 3.0 : 1.0
    const backgroundStarSpeed = viewMode === "timeline" ? 0.0015 : 0.15
    const backgroundAnimationSpeed = viewMode === "timeline" ? 0.0035 : 0.35
    const backgroundRotationSpeed = viewMode === "timeline" ? 0 : 0.05

    useEffect(() => {
        if (role === "expert") {
            setTaskLoaded(true)
            return
        }

        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        let cancelled = false

        async function loadTask() {
            try {
                const authToken = await getAuthToken()
                const headers: Record<string, string> = {}
                if (authToken) headers.Authorization = `Bearer ${authToken}`

                const response = await fetch(`${apiBase}/api/v1/tasks/${taskId}`, { headers })
                if (!response.ok) throw new Error(`HTTP ${response.status}`)
                const task = await response.json()
                if (cancelled) return

                const metadata = task.metadata && typeof task.metadata === "object" ? task.metadata : {}
                const storagePaths = task.storage_paths && typeof task.storage_paths === "object" ? task.storage_paths : {}
                const files = Array.isArray(metadata.files)
                    ? metadata.files
                    : Array.isArray(storagePaths.files)
                        ? storagePaths.files
                        : []

                setTaskContext({
                    inputType: task.input_type || "text",
                    priorityFocus: task.priority_focus || searchParams.get("focus") || "balanced",
                    casePrompt: metadata.case_prompt || task.description || "",
                    files,
                    title: task.title,
                    status: task.status,
                })
                setTaskLoaded(true)
            } catch {
                if (!cancelled) {
                    setTaskLoadError("任务数据加载失败，请确认已登录并拥有该任务权限")
                }
            }
        }

        void loadTask()
        return () => {
            cancelled = true
        }
    }, [role, searchParams, taskId])

    useEffect(() => {
        if (role !== "expert" || !inviteToken) return

        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        let cancelled = false

        void fetch(`${apiBase}/api/v1/consultation/invite/${inviteToken}`)
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error("invite invalid")
                }
                return response.json()
            })
            .catch(() => {
                if (!cancelled) {
                    alert("专家邀请链接无效或已失效")
                    router.replace(`/detect/${taskId}`)
                }
            })

        return () => {
            cancelled = true
        }
    }, [inviteToken, role, router, taskId])

    return (
        <div className="min-h-screen relative flex flex-col bg-black overflow-hidden">
            <div className="absolute inset-0 pointer-events-none z-0">
                <StarBackground
                    mouseInteraction={false}
                    mouseRepulsion={false}
                    density={backgroundDensity}
                    glowIntensity={0.15}
                    saturation={0}
                    hueShift={140}
                    twinkleIntensity={0.3}
                    rotationSpeed={backgroundRotationSpeed}
                    repulsionStrength={2}
                    autoCenterRepulsion={0}
                    starSpeed={backgroundStarSpeed}
                    speed={backgroundAnimationSpeed}
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
                            onClick={() => setViewMode(v => v === 'graph' ? '3d' : 'graph')}
                            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                                viewMode === 'graph'
                                    ? 'text-[#D4FF12] border border-[#D4FF12]/30 hover:bg-[#D4FF12]/10'
                                    : 'text-white/50 border border-white/10 hover:bg-white/5'
                            }`}
                        >
                            {viewMode === 'graph' ? '返回 Agent 视图' : '图谱视图'}
                        </button>
                        <button
                            onClick={() => setShowExpertPanel(!showExpertPanel)}
                            className="text-xs text-[#D4FF12] border border-[#D4FF12]/30 px-3 py-1.5 rounded-full hover:bg-[#D4FF12]/10 transition-colors"
                        >
                            {showExpertPanel ? '收起会诊面板' : '打开会诊面板'}
                        </button>
                        {role === 'host' && <InviteButton taskId={taskId} />}
                        {role === 'host' && (consultationState.status === "summary_confirmed" || consultationState.status === "skipped") && (
                            <button
                                onClick={resume}
                                className="text-xs text-[#F59E0B] border border-[#F59E0B]/40 px-3 py-1.5 rounded-full hover:bg-[#F59E0B]/10 transition-colors"
                            >
                                继续研判
                            </button>
                        )}
                        {isComplete && (
                            <button
                                onClick={async () => downloadCanonicalMarkdownReport(taskId, await getAuthToken())}
                                className="text-xs text-[#10B981] border border-[#10B981]/30 px-3 py-1.5 rounded-full hover:bg-[#10B981]/10 transition-colors"
                            >
                                MD 报告
                            </button>
                        )}
                        {isComplete && (
                            <button
                                onClick={async () => downloadPdfReport(taskId, await getAuthToken())}
                                className="text-xs text-[#EF4444] border border-[#EF4444]/30 px-3 py-1.5 rounded-full hover:bg-[#EF4444]/10 transition-colors"
                            >
                                PDF 报告
                            </button>
                        )}
                        {isComplete && (
                            <button
                                onClick={async () => {
                                    try {
                                        const authToken = await getAuthToken()
                                        const headers: Record<string, string> = {}
                                        if (authToken) headers.Authorization = `Bearer ${authToken}`
                                        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/v1/share/${taskId}`, {
                                            method: "POST",
                                            headers,
                                        })
                                        if (!res.ok) throw new Error("分享失败")
                                        const { share_url } = await res.json()
                                        const url = new URL(share_url, window.location.origin)
                                        await navigator.clipboard.writeText(url.toString())
                                        alert("分享链接已复制到剪贴板！")
                                    } catch {
                                        alert("生成分享链接失败，请稍后重试")
                                    }
                                }}
                                className="text-xs text-[#6366F1] border border-[#6366F1]/30 px-3 py-1.5 rounded-full hover:bg-[#6366F1]/10 transition-colors"
                            >
                                分享报告
                            </button>
                        )}
                        <PresenceAvatars users={onlineUsers} />
                    </div>

                    {/* Layer 2: 顶部系统流程展板 */}
                    <div className="hidden md:block">
                        <SystemFlowBoard steps={workflowSteps} />
                    </div>

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
                        {isWaitingConsultation && (
                            <div className="flex items-center gap-1.5 text-xs text-[#F59E0B]">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] shadow-[0_0_8px_#F59E0B]" />
                                等待会诊
                            </div>
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

            {(taskLoadError || errorMessage || isWaitingConsultation || consultationState.status === "summary_pending") && (
                <div className="mx-6 mt-3 rounded-xl border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-4 py-3 text-sm text-[#FCD34D]">
                    {taskLoadError || errorMessage || (consultationState.status === "summary_pending"
                        ? "Commander 已整理会诊摘要，等待用户确认后回注研判流程。"
                        : consultationState.status === "approval_required"
                            ? "逻辑质询再次陷入僵持，等待用户决定是否再次发起专家会诊。"
                            : "Commander 已接管会诊主持，等待专家意见；用户可在会诊后确认摘要并继续研判。")}
                </div>
            )}

            {/* Content Area */}
            {viewMode === "graph" ? (
                <div className="flex-1 overflow-hidden">
                    <ProvenanceGraphView graph={provenanceGraph} isComplete={isComplete} />
                </div>
            ) : viewMode === "3d" ? (
                <div className="flex-1 w-full relative overflow-hidden">
                    <BentoScene
                        osintNode={
                            <>
                                <AgentCard name="情报溯源Agent" agentKey="osint" icon={<Image src="/agent-icons/osint.svg" alt="情报溯源Agent" width={20} height={20} className="w-5 h-5" />} status={agentStatus("osint", !!osintResult)} confidence={osintSnapshot ? osintSnapshot.confidence : undefined} description="网络威胁情报 · 路由追踪" />
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-hidden min-h-0"><AgentLog logs={logs.filter(l => l.agent === "osint")} maxHeight="100%" /></div>
                            </>
                        }
                        forensicsNode={
                            <>
                                <AgentCard name="电子取证Agent" agentKey="forensics" icon={<Image src="/agent-icons/forensics.svg" alt="电子取证Agent" width={20} height={20} className="w-5 h-5" />} status={agentStatus("forensics", !!forensicsResult)} confidence={forensicsSnapshot ? forensicsSnapshot.confidence : undefined} description="全模态取证 · 工具矩阵鉴伪" />
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-hidden min-h-0"><AgentLog logs={logs.filter(l => l.agent === "forensics")} maxHeight="100%" /></div>
                            </>
                        }
                        challengerNode={
                            <>
                                <AgentCard name="逻辑质询Agent" agentKey="challenger" icon={<Image src="/agent-icons/challenger.svg" alt="逻辑质询Agent" width={20} height={20} className="w-5 h-5" />} status={agentStatus("challenger", !!challengerFeedback)} confidence={challengerSnapshot ? challengerSnapshot.qualityScore : undefined} description="跨模态矛盾检测 · 置信校验" />
                                {!!challengerSnapshot?.requiresMoreEvidence && (
                                    <div className="bg-[#F59E0B]/20 border border-[#F59E0B]/50 rounded-lg p-2 text-xs text-[#F59E0B]">🔄 发现矛盾，触发重审</div>
                                )}
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-hidden min-h-0"><AgentLog logs={logs.filter(l => l.agent === "challenger")} maxHeight="100%" /></div>
                            </>
                        }
                        commanderNode={
                            <>
                                <AgentCard name="研判指挥Agent" agentKey="commander" icon={<Image src="/agent-icons/commander.svg" alt="研判指挥Agent" width={20} height={20} className="w-5 h-5" />} status={agentStatus("commander", !!finalVerdict)} confidence={verdictSnapshot ? verdictSnapshot.confidence : undefined} description="多维向量收敛中心 · 最终判决" />
                                <div className="flex-1 rounded-xl liquid-glass p-2 border border-white/10 overflow-hidden min-h-0 flex flex-col gap-2">
                                    {finalVerdict && <div className="shrink-0"><VerdictBadge verdict={finalVerdict} /></div>}
                                    <div className="flex-1 min-h-0">
                                        <AgentLog logs={logs.filter(l => l.agent === "commander")} maxHeight="100%" />
                                    </div>
                                </div>
                            </>
                        }
                        activeAgent={currentNode || (isComplete ? 'commander' : null)}
                    />
                </div>
            ) : null}

            {/* Timeline View */}
            {viewMode === "timeline" && (
                <div className="flex-1 overflow-auto">
                    <EvidenceTimeline logs={timelineLogs} isComplete={isComplete} />
                </div>
            )}

            {/* Mobile Workflow */}
            <div className="md:hidden px-4 pb-4">
                <SystemFlowBoard steps={workflowSteps} />
            </div>

            {/* Expert Panel Overlay */}
            <AnimatePresence>
                {showExpertPanel && (
                    <motion.div
                        initial={{ x: 400, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 400, opacity: 0 }}
                        className="fixed right-4 top-20 bottom-4 w-96 z-40 hidden lg:block"
                    >
                        <ExpertPanel
                            taskId={taskId}
                            inviteToken={inviteToken}
                            currentRole={role}
                            consultationState={consultationState}
                            onResume={resume}
                        />
                    </motion.div>
                )}
            </AnimatePresence>
            </div>
        </div>
    )
}
