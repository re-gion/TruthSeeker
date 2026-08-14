import { describe, expect, it } from "vitest"

import { resolveActiveHeadingId } from "./useActiveHeading"

describe("resolveActiveHeadingId", () => {
  const measurements = [
    { id: "a", top: -400 },
    { id: "b", top: -120 },
    { id: "c", top: 260 },
    { id: "d", top: 900 },
  ]

  it("picks the last heading that already scrolled past the sticky offset", () => {
    expect(resolveActiveHeadingId(measurements, 80)).toBe("b")
  })

  it("keeps the first heading while the page is still above it", () => {
    expect(
      resolveActiveHeadingId(
        [
          { id: "a", top: 320 },
          { id: "b", top: 800 },
        ],
        80,
      ),
    ).toBe("a")
  })

  it("treats a heading exactly on the offset line as active", () => {
    expect(
      resolveActiveHeadingId(
        [
          { id: "a", top: -200 },
          { id: "b", top: 80 },
        ],
        80,
      ),
    ).toBe("b")
  })

  it("absorbs sub-pixel smooth-scroll overshoot within the tolerance", () => {
    // 平滑滚动落点实测 80.28 而偏移是 80；严格比较会让高亮退回上一节
    expect(
      resolveActiveHeadingId(
        [
          { id: "a", top: -488 },
          { id: "b", top: 80.28 },
          { id: "c", top: 600 },
        ],
        80,
      ),
    ).toBe("b")
  })

  it("does not activate a heading still clearly below the offset line", () => {
    expect(
      resolveActiveHeadingId(
        [
          { id: "a", top: -100 },
          { id: "b", top: 95 },
        ],
        80,
      ),
    ).toBe("a")
  })

  it("returns null when nothing is measurable", () => {
    expect(resolveActiveHeadingId([], 80)).toBeNull()
  })

  it("activates the last heading once the page is scrolled to the bottom", () => {
    // 长报告末尾几节距底不足一屏，永远越不过吸顶线；不特判会卡在前一节
    expect(resolveActiveHeadingId(measurements, 80, { atBottom: true })).toBe("d")
  })
})
