"use client"

import { useEffect, useRef } from "react"
import { ChevronsLeft, List } from "lucide-react"

import type { ReportTocEntry } from "@/lib/report-toc"

interface ReportTocProps {
  entries: ReportTocEntry[]
  activeId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 点击条目时立即锁定高亮，避免平滑滚动落定前显示上一节 */
  onNavigate?: (id: string) => void
}

/**
 * 滚到目标区块。用原生 `scrollIntoView` 而不是自己算 `scrollTo` 的绝对像素：
 * 报告长达数万像素，平滑滚动途中字体分片加载会改变文本行高、进而改变文档总高，
 * 点击时算好的目标像素会漂掉（实测大跨度跳转落点偏 350px+）。`scrollIntoView`
 * 由浏览器在动画过程中持续校正，吸顶偏移由锚点自身的 `scroll-margin-top` 提供。
 */
function scrollToEntry(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
}

/**
 * 目录列表本身可滚动（报告章节多达 30+ 条），高亮项滚出视野时把它带回来。
 * 用 rect 差值算 scrollTop，不用 offsetTop（它相对定位祖先 nav，会多算标题栏高度），
 * 也不用 scrollIntoView（会连带滚动页面，和正文滚动互相打断）。
 */
function useKeepActiveVisible(activeId: string | null) {
  const listRef = useRef<HTMLOListElement>(null)

  useEffect(() => {
    const list = listRef.current
    if (!list || !activeId) return

    const active = list.querySelector<HTMLElement>(`[data-toc-id="${CSS.escape(activeId)}"]`)
    if (!active) return

    const listRect = list.getBoundingClientRect()
    const activeRect = active.getBoundingClientRect()
    const overflowTop = activeRect.top - listRect.top
    const overflowBottom = activeRect.bottom - listRect.bottom

    if (overflowTop < 0) {
      list.scrollTop += overflowTop
    } else if (overflowBottom > 0) {
      list.scrollTop += overflowBottom
    }
  }, [activeId])

  return listRef
}

export function ReportToc({
  entries,
  activeId,
  open,
  onOpenChange,
  onNavigate,
}: ReportTocProps) {
  const listRef = useKeepActiveVisible(open ? activeId : null)

  if (!entries.length) return null

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        aria-expanded={false}
        aria-label="展开报告目录"
        className="glass-card sticky top-20 flex h-fit w-11 flex-col items-center gap-2 rounded-xl border border-white/5 py-3 text-[#6B7280] transition-colors hover:text-[#D4FF12]"
      >
        <List className="h-4 w-4" aria-hidden />
        <span className="text-[10px] leading-tight tracking-widest [writing-mode:vertical-rl]">目录</span>
      </button>
    )
  }

  return (
    <nav
      aria-label="报告目录"
      className="glass-card sticky top-20 flex h-fit max-h-[calc(100vh-6rem)] flex-col rounded-xl border border-white/5"
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-2.5">
        <span className="flex items-center gap-1.5 text-xs font-bold text-[#C0C0C0]">
          <List className="h-3.5 w-3.5" aria-hidden />
          报告目录
        </span>
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-expanded
          aria-label="收起报告目录"
          className="rounded p-0.5 text-[#6B7280] transition-colors hover:text-[#D4FF12]"
        >
          <ChevronsLeft className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <ol ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-1.5 py-2">
        {entries.map((entry) => {
          const isActive = entry.id === activeId
          return (
            <li key={entry.id}>
              <button
                type="button"
                data-toc-id={entry.id}
                onClick={() => {
                  onNavigate?.(entry.id)
                  scrollToEntry(entry.id)
                }}
                aria-current={isActive ? "location" : undefined}
                className={`w-full rounded-md border-l-2 py-1.5 pr-2 text-left text-xs leading-snug transition-colors ${
                  entry.depth === 1 ? "pl-5" : "pl-2.5 font-medium"
                } ${
                  isActive
                    ? "border-[#D4FF12] bg-[#D4FF12]/10 text-[#D4FF12]"
                    : "border-transparent text-[#8B8B93] hover:border-white/20 hover:bg-white/5 hover:text-[#C0C0C0]"
                }`}
              >
                {entry.text}
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
