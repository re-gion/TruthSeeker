"use client"

import { useEffect, useRef, useState, useMemo, useCallback } from "react"
import { motion, AnimatePresence } from "motion/react"
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
    forensics: "视听鉴伪Agent",
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

// 优化的打字机组件 - 修复类型警告
function TypewriterText({ text, speed = 20 }: { text: string; speed?: number }) {
    const [displayed, setDisplayed] = useState("")
    // 修复1: 明确指定 timeoutRef 的类型
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const mountedRef = useRef(true)
    const indexRef = useRef(0)
    const textRef = useRef(text)

    // 使用useCallback优化性能
    const scheduleNextChar = useCallback(() => {
        if (!mountedRef.current) return

        if (indexRef.current < textRef.current.length) {
            setDisplayed(textRef.current.slice(0, indexRef.current + 1))
            indexRef.current++

            // 修复2: 明确类型赋值
            timeoutRef.current = setTimeout(scheduleNextChar, speed)
        }
    }, [speed])

    useEffect(() => {
        mountedRef.current = true
        textRef.current = text
        indexRef.current = 0
        setDisplayed("")

        // 清理之前的定时器
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
            timeoutRef.current = null
        }

        // 开始打字效果
        timeoutRef.current = setTimeout(scheduleNextChar, speed)

        // 清理函数
        return () => {
            mountedRef.current = false
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }
        }
    }, [text, speed, scheduleNextChar])

    // 如果文本很短或已经完成，不显示光标
    if (displayed.length === text.length) {
        return <span>{displayed}</span>
    }

    return (
        <span>
            {displayed}
            <span className="typewriter-cursor" />
        </span>
    )
}

interface AgentLogProps {
    logs: LogEntry[]
    maxHeight?: string | number
}

export function AgentLog({ logs, maxHeight = "360px" }: AgentLogProps) {
    const bottomRef = useRef<HTMLDivElement>(null)

    // 为日志生成稳定key（如果没有提供id）
    const logsWithKeys = useMemo(() => {
        return logs.map((log, index) => ({
            ...log,
            stableKey: log.id || `${log.agent}-${log.timestamp}-${index}-${log.content.slice(0, 10)}`
        }))
    }, [logs])

    // 自动滚动到底部
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" })
        }
    }, [logsWithKeys]) // 依赖整个数组，确保内容变化时也滚动

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
        return { maxHeight: height }
    }, [maxHeight])

    if (logs.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-[#6B7280] text-sm space-y-2">
                <motion.div
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="text-2xl"
                >
                    <Radar className="w-6 h-6 text-[#6366F1]" />
                </motion.div>
                <span>等待 Agent 启动...</span>
            </div>
        )
    }

    return (
        <div
            className="overflow-y-auto space-y-2 pr-1 font-mono text-xs"
            style={containerStyle}
        >
            <AnimatePresence initial={false}>
                {logsWithKeys.map((log, index) => {
                    const color = getAgentColor(log.agent)
                    const label = getAgentLabel(log.agent)
                    const icon = getLogIcon(log.type)
                    const isLast = index === logsWithKeys.length - 1

                    return (
                        <motion.div
                            key={log.stableKey}
                            initial={{ opacity: 0, x: -8, height: 0 }}
                            animate={{ opacity: 1, x: 0, height: "auto" }}
                            exit={{ opacity: 0, x: 8, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="flex gap-2 items-start"
                        >
                            {/* Agent color bar - 动态高度 */}
                            <div
                                className="w-0.5 rounded-full mt-1 flex-shrink-0 self-stretch"
                                style={{ backgroundColor: color }}
                            />

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-0.5">
                                    <span className="text-[10px] font-medium" style={{ color }}>
                                        [{label}]
                                    </span>
                                    <span className="text-[10px] text-[#6B7280]" aria-hidden="true">
                                        {icon}
                                    </span>
                                </div>

                                <div className="text-[#C0C0C0] leading-relaxed break-words">
                                    {isLast ? (
                                        <TypewriterText
                                            key={`typewriter-${log.stableKey}`}
                                            text={log.content}
                                            speed={15}
                                        />
                                    ) : (
                                        log.content
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    )
                })}
            </AnimatePresence>
            <div ref={bottomRef} />
        </div>
    )
}