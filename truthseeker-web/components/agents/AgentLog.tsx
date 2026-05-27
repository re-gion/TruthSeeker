"use client"

import { useLayoutEffect, useRef, useMemo, useCallback } from "react"
import { motion } from "motion/react"
import { Radar } from "lucide-react"

interface LogEntry {
    agent: string
    type: string
    content: string
    timestamp: string
    id?: string // 可选，用于稳定key
}

const AGENT_COLORS: Record<string, string> = {
    forensics: "#6366F1",   // Indigo AI
    commander: "#06B6D4",   // Cyan
    osint: "#10B981",       // Green
    challenger: "#F59E0B",  // Amber
}

const AGENT_LABELS: Record<string, string> = {
    forensics: "电子取证Agent",
    commander: "研判指挥Agent",
    osint: "情报溯源Agent",
    challenger: "逻辑质询Agent",
}

const LOG_ICONS: Record<string, string> = {
    thinking: "◇",
    action: "▸",
    finding: "◈",
    challenge: "▲",
    conclusion: "☑",
}

interface AgentLogProps {
    logs: LogEntry[]
    maxHeight?: string | number
}

export function AgentLog({ logs, maxHeight = "360px" }: AgentLogProps) {
    const scrollRef = useRef<HTMLDivElement>(null)
    const contentRef = useRef<HTMLDivElement>(null)

    // 为日志生成稳定key（如果没有提供id）
    const logsWithKeys = useMemo(() => {
        return logs.map((log, index) => ({
            ...log,
            stableKey: log.id || `${log.agent}-${log.timestamp}-${index}-${log.content.slice(0, 10)}`
        }))
    }, [logs])
    const scrollSignature = useMemo(() => {
        return logsWithKeys.map((log) => log.stableKey).join("|")
    }, [logsWithKeys])

    // 自动滚动到底部
    useLayoutEffect(() => {
        if (logsWithKeys.length === 0) return

        const scroller = scrollRef.current
        if (!scroller) return

        let frame = 0
        const scrollToBottom = () => {
            scroller.scrollTop = scroller.scrollHeight
        }
        const scheduleScroll = () => {
            if (frame) window.cancelAnimationFrame(frame)
            frame = window.requestAnimationFrame(scrollToBottom)
        }

        scrollToBottom()
        scheduleScroll()

        const resizeObserver = typeof ResizeObserver === "undefined"
            ? null
            : new ResizeObserver(scheduleScroll)

        if (contentRef.current) {
            resizeObserver?.observe(contentRef.current)
        }

        return () => {
            if (frame) window.cancelAnimationFrame(frame)
            resizeObserver?.disconnect()
        }
    }, [logsWithKeys.length, scrollSignature])

    // 安全地获取颜色和标签
    const getAgentColor = useCallback((agent: string): string => {
        return AGENT_COLORS[agent] || "#6366F1"
    }, [])

    const getAgentLabel = useCallback((agent: string): string => {
        return AGENT_LABELS[agent] || agent
    }, [])

    const getLogIcon = useCallback((type: string): string => {
        return LOG_ICONS[type] || "•"
    }, [])

    // 处理maxHeight单位
    const containerStyle = useMemo(() => {
        const height = typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight
        return {
            maxHeight: height,
            height: height === "100%" ? "100%" : undefined,
        }
    }, [maxHeight])

    return (
        <div
            data-testid="agent-log-shell"
            className="flex h-full w-full max-w-full min-h-0 min-w-0 flex-1 basis-0 flex-col overflow-hidden box-border"
            style={containerStyle}
        >
            {logs.length === 0 ? (
                <div className="flex h-full w-full min-h-0 min-w-0 flex-1 flex-col items-center justify-center space-y-2 text-sm text-[#6B7280]">
                    <motion.div
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className="text-2xl"
                    >
                        <Radar className="w-6 h-6 text-[#6366F1]" />
                    </motion.div>
                    <span>等待 Agent 启动...</span>
                </div>
            ) : (
                <div
                    ref={scrollRef}
                    data-testid="agent-log-scroll"
                    className="h-full w-full max-h-full max-w-full min-h-0 min-w-0 flex-1 basis-0 overflow-y-auto overscroll-contain font-mono text-xs box-border"
                    style={{ scrollbarGutter: "stable" }}
                >
                    <div ref={contentRef} data-testid="agent-log-content" className="w-full max-w-full min-w-0 space-y-2">
                        {logsWithKeys.map((log) => {
                            const color = getAgentColor(log.agent)
                            const label = getAgentLabel(log.agent)
                            const icon = getLogIcon(log.type)

                            return (
                                <div
                                    key={log.stableKey}
                                    data-testid="agent-log-entry"
                                    className="grid w-full max-w-full min-w-0 grid-cols-[2px_minmax(0,1fr)] gap-2 items-start"
                                >
                                    <div
                                        className="w-0.5 rounded-full mt-1 self-stretch"
                                        style={{ backgroundColor: color }}
                                    />

                                    <div className="min-w-0 max-w-full flex-1">
                                        <div className="flex w-full min-w-0 max-w-full items-center gap-2 mb-0.5">
                                            <span className="text-[10px] font-medium" style={{ color }}>
                                                [{label}]
                                            </span>
                                            <span className="text-[10px] text-[#6B7280]" aria-hidden="true">
                                                {icon}
                                            </span>
                                        </div>

                                        <div
                                            data-testid="agent-log-entry-content"
                                            className="block w-full max-w-full min-w-0 whitespace-pre-wrap text-[#C0C0C0] leading-relaxed break-words [overflow-wrap:anywhere] [word-break:break-word]"
                                        >
                                            <span className="block w-full max-w-full min-w-0">{log.content}</span>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
