"use client"

import dynamic from "next/dynamic"
import type { EChartsOption } from "echarts"

const ReactECharts = dynamic(() => import("echarts-for-react"), {
  ssr: false,
})

interface DashboardChartProps {
  option: EChartsOption
  height?: number
  className?: string
}

export function DashboardChart({ option, height = 320, className }: DashboardChartProps) {
  return (
    <div className={className}>
      <ReactECharts
        option={option}
        notMerge
        lazyUpdate
        opts={{ renderer: "svg" }}
        style={{ height, width: "100%" }}
      />
    </div>
  )
}
