import { existsSync, readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

const projectRoot = process.cwd()

function readSource(relativePath: string) {
  const path = join(projectRoot, relativePath)
  return existsSync(path) ? readFileSync(path, "utf8") : ""
}

describe("typography contract", () => {
  it("self-hosts the approved IBM Plex families and weights", () => {
    const typography = readSource("app/typography.css")
    const ibmTypography = typography.split("/* Self-hosted IBM Plex")[1] ?? ""
    const fontRoot = join(projectRoot, "public/fonts/ibm-plex")
    const assets = existsSync(fontRoot)
      ? readdirSync(fontRoot, { recursive: true }).map(String)
      : []
    const fontUrls = [...typography.matchAll(/url\("(\/fonts\/ibm-plex\/[^"?]+\.woff2)"\)/g)]
      .map((match) => match[1])
    const weights = [...ibmTypography.matchAll(/font-weight:\s*(\d+)/g)]
      .map((match) => match[1])
    const missingAssets = fontUrls.filter((url) => !existsSync(join(projectRoot, "public", url)))

    expect(typography).toContain("IBM Plex Sans SC")
    expect(typography).toContain("IBM Plex Mono")
    expect(typography).toContain("unicode-range")
    expect(new Set(weights)).toEqual(new Set(["400", "500", "600"]))
    expect(typography).not.toContain("src: local")
    expect(typography).not.toMatch(/url\(["']?https?:\/\//)
    expect(fontUrls).toHaveLength(663)
    expect(new Set(fontUrls).size).toBe(663)
    expect(missingAssets).toEqual([])
    expect(assets.filter((asset) => asset.endsWith(".woff2"))).toHaveLength(663)
    expect(assets.some((asset) => asset.toLowerCase() === "license.txt")).toBe(true)
  })

  it("self-hosts Unbounded for the 600-weight frontend wordmark only", () => {
    const typography = readSource("app/typography.css")
    const globals = readSource("app/globals.css")
    const report = readSource("app/report/[taskId]/page.tsx")

    expect(typography).toContain("font-family: 'Unbounded'")
    expect(typography).toContain('/fonts/unbounded/Unbounded-Latin.woff2')
    expect(existsSync(join(projectRoot, "public/fonts/unbounded/Unbounded-Latin.woff2"))).toBe(true)
    expect(existsSync(join(projectRoot, "public/fonts/unbounded/OFL.txt"))).toBe(true)
    expect(globals).toContain("--font-brand: 'Unbounded'")
    expect(globals).toMatch(/\.brand-wordmark\s*{[\s\S]*?font-weight:\s*600/)
    expect(report).not.toMatch(/BrandWordmark|brand-wordmark/)
  })

  it("uses semantic interface and telemetry tokens without legacy font aliases", () => {
    const layout = readSource("app/layout.tsx")
    const globals = readSource("app/globals.css")

    expect(layout).not.toContain("next/font/local")
    expect(layout).toContain('className="font-sans')
    expect(globals).toContain('@import "./typography.css"')
    expect(globals).toContain("--font-interface:")
    expect(globals).toContain("--font-telemetry:")
    expect(globals).toContain("--font-display: var(--font-interface)")
    expect(globals).toContain("--font-mono: var(--font-telemetry)")
    expect(globals).not.toMatch(/ZhengKaiTi|SiyuanSong|TimesLatinOnly|font-geist/)
    expect(globals).not.toMatch(/JetBrains Mono|Fira Code/)
  })

  it("keeps display and telemetry usage inside the shared font system", () => {
    const hero = readSource("components/landing/HeroSection.tsx")
    const detect = readSource("app/detect/page.tsx")
    const dashboard = readSource("components/dashboard/DashboardClient.tsx")

    expect(hero).not.toContain("font-serif")
    expect(hero).toContain("brand-wordmark")
    expect(hero).toContain("lg:text-[88px]")
    expect(hero).toContain("xl:text-[92px]")
    expect(hero).not.toContain("lg:text-[92px]")
    expect(hero).not.toContain("xl:text-[96px]")
    expect(detect).not.toContain("font-serif")
    expect(detect).toContain("brand-wordmark")
    expect(dashboard).not.toContain('fontFamily: "monospace"')
  })
})
