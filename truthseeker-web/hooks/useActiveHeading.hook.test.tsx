// @vitest-environment jsdom

import React, { useEffect, useRef } from "react"
import "@testing-library/jest-dom/vitest"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { useActiveHeading } from "./useActiveHeading"

/** 等 hook 的 setTimeout 兜底测量落地 */
async function flushMeasurement() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 200))
  })
}

/** jsdom 不做布局，getBoundingClientRect 全为 0；这里按 id 注入受控 top */
function Probe({ ids, tops = {} }: { ids: string[]; tops?: Record<string, number> }) {
  const { activeId, pinActiveId } = useActiveHeading(ids, 80)
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    for (const id of Object.keys(tops)) {
      const element = host.querySelector<HTMLElement>(`#${id}`)
      if (element) {
        element.getBoundingClientRect = () => ({ top: tops[id], bottom: tops[id] + 20 }) as DOMRect
      }
    }
    window.dispatchEvent(new Event("scroll"))
  })

  return (
    <>
      <span data-testid="active">{activeId ?? "none"}</span>
      {ids.map((id) => (
        <button key={id} type="button" onClick={() => pinActiveId(id)}>
          {`pin-${id}`}
        </button>
      ))}
      <div ref={hostRef}>
        {ids.map((id) => (
          <h2 key={id} id={id}>
            {id}
          </h2>
        ))}
      </div>
    </>
  )
}

const TOPS = { a: -400, b: -120, c: 600 }

describe("useActiveHeading", () => {
  beforeEach(() => {
    // 默认非底部：jsdom 的 scrollHeight/innerHeight 都是 0，会被判成"已到底部"
    // 从而直接高亮末项，掩盖真实的越线选择逻辑
    Object.defineProperty(document.documentElement, "scrollHeight", {
      value: 100000,
      configurable: true,
    })
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true })
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true })
  })

  it("returns null for an empty heading list", () => {
    render(<Probe ids={[]} />)

    expect(screen.getByTestId("active")).toHaveTextContent("none")
  })

  it("drops a stale measured id after the heading list changes", () => {
    const { rerender } = render(<Probe ids={["a", "b"]} />)

    rerender(<Probe ids={["x", "y"]} />)

    expect(screen.getByTestId("active")).toHaveTextContent("x")
  })

  it("tracks the last heading above the sticky offset while scrolling", async () => {
    render(<Probe ids={["a", "b", "c"]} tops={TOPS} />)

    fireEvent.scroll(window)
    await flushMeasurement()

    expect(screen.getByTestId("active")).toHaveTextContent("b")
  })

  it("pins the clicked id even when measurement would pick another", async () => {
    render(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    fireEvent.scroll(window)
    await flushMeasurement()
    expect(screen.getByTestId("active")).toHaveTextContent("b")

    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))

    expect(screen.getByTestId("active")).toHaveTextContent("c")
  })

  it("keeps the pin while the target has not reached the sticky line yet", async () => {
    render(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))

    // c 仍在 600px 处（远未到 80px 吸顶线）：平滑滚动进行中，锁定必须保持
    for (let i = 0; i < 3; i += 1) {
      fireEvent.scroll(window)
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 200))
      })
      expect(screen.getByTestId("active")).toHaveTextContent("c")
    }
  })

  it("hands control back to measurement once the target reaches the sticky line", async () => {
    const { rerender } = render(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))
    expect(screen.getByTestId("active")).toHaveTextContent("c")

    // 滚动落定：c 抵达吸顶线，测量结论与锁定一致，可安全解锁
    rerender(<Probe ids={["a", "b", "c"]} tops={{ a: -900, b: -600, c: 80 }} />)
    await flushMeasurement()
    expect(screen.getByTestId("active")).toHaveTextContent("c")

    // 解锁后继续跟随：b 重新越线时高亮应改回 b
    rerender(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    await flushMeasurement()
    expect(screen.getByTestId("active")).toHaveTextContent("b")
  })

  it("keeps a bottom-of-document target pinned because it never reaches the sticky line", async () => {
    // 末尾条目剩余可滚距离不足，永远到不了吸顶线；锁定必须保持而不是闪回
    render(<Probe ids={["a", "b", "c"]} tops={{ a: -900, b: -600, c: 285 }} />)
    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))

    fireEvent.scroll(window)
    await flushMeasurement()

    expect(screen.getByTestId("active")).toHaveTextContent("c")
  })

  it("releases the pin once the user scrolls by themselves", async () => {
    render(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))
    expect(screen.getByTestId("active")).toHaveTextContent("c")

    fireEvent.wheel(window)
    await flushMeasurement()

    expect(screen.getByTestId("active")).toHaveTextContent("b")
  })

  it("keeps measuring while pinned so releasing does not flash a stale entry", async () => {
    // 锁定期间若停止测量，释放瞬间会先闪回点击前的条目
    const { rerender } = render(<Probe ids={["a", "b", "c"]} tops={{ a: -400, b: 600, c: 900 }} />)
    await flushMeasurement()
    expect(screen.getByTestId("active")).toHaveTextContent("a")

    fireEvent.click(screen.getByRole("button", { name: "pin-c" }))
    expect(screen.getByTestId("active")).toHaveTextContent("c")

    // 模拟滚动后布局：b 已越线，此时释放锁定应直接落到 b，不经过 a
    rerender(<Probe ids={["a", "b", "c"]} tops={TOPS} />)
    await flushMeasurement()

    fireEvent.wheel(window)
    expect(screen.getByTestId("active")).toHaveTextContent("b")
  })
})
