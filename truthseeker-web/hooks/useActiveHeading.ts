"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export interface HeadingMeasurement {
  id: string
  /** getBoundingClientRect().top，相对视口 */
  top: number
}

export interface ActiveHeadingContext {
  /** 页面已滚到文档底部（末尾章节再也到不了吸顶线） */
  atBottom?: boolean
}

/**
 * 越线容差。平滑滚动落点常有亚像素误差（实测 80.28 vs 偏移 80），
 * 严格比较会让高亮退回上一节。
 */
const CROSS_TOLERANCE_PX = 2

/** 用户主动接管滚动的信号；出现任一即释放点击锁定 */
const USER_SCROLL_EVENTS = ["wheel", "touchstart", "keydown", "mousedown"] as const

/**
 * 选出“当前所在”标题：最后一个已经滚过吸顶线的标题。
 *
 * 两个边界：
 * - 页面还停在首个标题之上时返回首个标题，避免目录空高亮。
 * - 已滚到文档底部时直接返回最后一个标题。长报告末尾几节距底不足一屏，
 *   永远越不过吸顶线，否则点末尾条目后高亮会卡在前一节。
 */
export function resolveActiveHeadingId(
  measurements: readonly HeadingMeasurement[],
  offset: number,
  { atBottom = false }: ActiveHeadingContext = {},
): string | null {
  if (!measurements.length) return null
  if (atBottom) return measurements[measurements.length - 1].id

  let active = measurements[0].id
  for (const measurement of measurements) {
    if (measurement.top - offset <= CROSS_TOLERANCE_PX) {
      active = measurement.id
    } else {
      break
    }
  }
  return active
}

/** 判定是否已到文档底部；留 2px 容差吸收缩放与小数像素 */
function isAtDocumentBottom() {
  return window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2
}

/**
 * 滚动跟随高亮，外加“点击锁定”。
 *
 * 只靠测量选高亮在长报告里不可靠：平滑滚动要跨几万像素、字体与图片加载还会让
 * 布局微移，落定前的每一帧目标标题都尚未越过吸顶线，于是目录显示成上一节。
 * 点击目录时用户意图已经明确，直接锁定该条。
 *
 * 解锁有两个出口：
 * - 目标已抵达吸顶线（此时测量本身就会得出同一条，交回去不会闪）。
 * - 用户自己滚动（滚轮/触摸/按键/拖拽滚动条）。
 *
 * 靠近文档末尾的条目永远抵达不了吸顶线（剩余可滚距离不足），锁定就一直保持到
 * 用户滚动为止——这正是点击末尾条目时想要的效果。
 *
 * 锁定期间仍然照常测量，只是渲染时让锁定值优先——否则 `measuredId` 会停在点击前
 * 的位置，释放锁定的瞬间先闪一个错误条目再跳回来。
 *
 * 测量用 scroll 监听 + rAF 节流，并配一条 setTimeout 兜底：rAF 在长文档和
 * 后台标签页里会被节流，只靠它会丢掉滚动停止后的最后一帧。
 */
export function useActiveHeading(ids: readonly string[], offset = 96) {
  const [measuredId, setMeasuredId] = useState<string | null>(null)
  const [pinnedId, setPinnedId] = useState<string | null>(null)
  const pinnedRef = useRef<string | null>(null)
  const key = ids.join("|")

  const pinActiveId = useCallback((id: string) => {
    pinnedRef.current = id
    setPinnedId(id)
  }, [])

  useEffect(() => {
    const orderedIds = key ? key.split("|") : []
    if (!orderedIds.length) return

    let frame = 0
    let trailing = 0

    const releasePin = () => {
      if (!pinnedRef.current) return
      pinnedRef.current = null
      setPinnedId(null)
    }

    const measure = () => {
      frame = 0

      const measurements: HeadingMeasurement[] = []
      let pinnedTop: number | null = null
      for (const id of orderedIds) {
        const element = document.getElementById(id)
        if (!element) continue
        const top = element.getBoundingClientRect().top
        measurements.push({ id, top })
        if (id === pinnedRef.current) pinnedTop = top
      }

      // 抵达吸顶线即交还控制权：此后测量结论与锁定值一致，不会闪回
      if (pinnedTop != null && Math.abs(pinnedTop - offset) <= CROSS_TOLERANCE_PX) {
        releasePin()
      }

      setMeasuredId(resolveActiveHeadingId(measurements, offset, { atBottom: isAtDocumentBottom() }))
    }

    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(measure)
      window.clearTimeout(trailing)
      trailing = window.setTimeout(measure, 150)
    }

    schedule()
    window.addEventListener("scroll", schedule, { passive: true })
    window.addEventListener("resize", schedule)
    for (const eventName of USER_SCROLL_EVENTS) {
      window.addEventListener(eventName, releasePin, { passive: true })
    }

    return () => {
      if (frame) window.cancelAnimationFrame(frame)
      window.clearTimeout(trailing)
      window.removeEventListener("scroll", schedule)
      window.removeEventListener("resize", schedule)
      for (const eventName of USER_SCROLL_EVENTS) {
        window.removeEventListener(eventName, releasePin)
      }
    }
  }, [key, offset])

  const candidate = pinnedId ?? measuredId
  const activeId = ids.length
    ? (candidate && ids.includes(candidate) ? candidate : ids[0])
    : null

  return { activeId, pinActiveId }
}
