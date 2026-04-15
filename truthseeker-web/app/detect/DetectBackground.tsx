"use client"

import DotGrid from "@/components/ui/DotGrid"
import { useDocumentTheme } from "@/hooks/useDocumentTheme"

export function DetectBackground() {
  const isDark = useDocumentTheme() === "dark"

  const dotGridConfig = isDark
    ? {
        // ReactBits DotGrid 基础参数（夜间）
        dotSize: 5,
        gap: 25,
        proximity: 120,
        shockRadius: 250,
        shockStrength: 5,
        resistance: 750,
        returnDuration: 1.5,
        baseColor: "#2B1A4A",
        activeColor: "#D4FF12",
      }
    : {
        // ReactBits DotGrid 基础参数（白天）
        dotSize: 5,
        gap: 22.5,
        proximity: 120,
        shockRadius: 250,
        shockStrength: 5,
        resistance: 750,
        returnDuration: 1.5,
        baseColor: "#CBD5E1",
        activeColor: "#6366F1",
      }

  return (
    <div className="absolute inset-0 z-0 overflow-hidden" style={{ background: isDark ? "#060010" : "#ffffff" }}>
      <DotGrid
        {...dotGridConfig}
        className="w-full h-full"
      />
    </div>
  )
}
