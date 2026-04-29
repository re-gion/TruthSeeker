"use client"

import Link from "next/link"
import { motion } from "motion/react"
import type { EChartsOption } from "echarts"
import {
  AlertTriangle,
  ArrowUpRight,
  Clock3,
  FileCheck2,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react"

import { DashboardChart } from "@/components/dashboard/DashboardChart"
import type {
  DashboardCapabilityMetric,
  DashboardDistributionItem,
  DashboardTrendSeries,
  DashboardViewModel,
  ExternalInsightModule,
} from "@/lib/dashboard"

interface DashboardClientProps {
  viewModel: DashboardViewModel
}

const SECTION_META = {
  "risk-foundation": {
    code: "01",
    title: "风险底座",
    badge: "权威公开数据",
    accent: "from-[#FF6B6B]/20 via-[#F59E0B]/10 to-transparent",
  },
  "governance-environment": {
    code: "02",
    title: "治理环境",
    badge: "治理压力面",
    accent: "from-[#38BDF8]/20 via-[#2563EB]/10 to-transparent",
  },
  capability: {
    code: "03",
    title: "系统能力层",
    badge: "真实业务汇总",
    accent: "from-[#8B5CF6]/18 via-[#1D4ED8]/12 to-transparent",
  },
} as const

const KPI_META = [
  {
    id: "totalTasks",
    label: "累计任务",
    icon: ShieldCheck,
    tone: "text-[#C7FF45]",
  },
  {
    id: "highRiskTasks",
    label: "高风险任务",
    icon: ShieldAlert,
    tone: "text-[#FF9B57]",
  },
  {
    id: "averageResponseMs",
    label: "平均响应",
    icon: Clock3,
    tone: "text-[#67E8F9]",
  },
  {
    id: "completedToday",
    label: "今日完成",
    icon: Radar,
    tone: "text-[#A78BFA]",
  },
] as const

const CHART_COLORS = ["#61D4FF", "#7A77FF", "#FF8A5B", "#D4FF3C", "#FB7185", "#22C55E"]

function formatGeneratedAt(iso: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso))
}

function formatInsightValue(value: number, unit: string) {
  const formatted =
    value >= 1000 ? value.toLocaleString("zh-CN") : value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  return `${formatted}${unit}`
}

function createEmptyOption(title: string): EChartsOption {
  return {
    backgroundColor: "transparent",
    graphic: [
      {
        type: "group",
        left: "center",
        top: "middle",
        children: [
          {
            type: "text",
            style: {
              text: title,
              fill: "rgba(255,255,255,0.82)",
              fontSize: 16,
              fontWeight: 600,
            },
          },
          {
            type: "text",
            top: 28,
            style: {
              text: "暂无已完成报告",
              fill: "rgba(255,255,255,0.45)",
              fontSize: 12,
            },
          },
        ],
      },
    ],
  }
}

function buildArcProgressOption(module: ExternalInsightModule): EChartsOption {
  const headline = module.metrics[0]
  const rings = module.metrics.slice(1)

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { seriesIndex: number }
        const metric = rings[p.seriesIndex]
        if (!metric) return ""
        return `<div style="font-weight:600">${metric.label}</div>
                <div style="font-size:16px;font-weight:700;color:${CHART_COLORS[p.seriesIndex]};margin-top:4px">
                  ${formatInsightValue(metric.value, metric.unit)}
                </div>
                ${metric.description ? `<div style="font-size:11px;color:#aaa;margin-top:4px;max-width:200px;white-space:normal">${metric.description}</div>` : ""}`
      },
    },
    series: rings.map((metric, index) => ({
      type: "gauge",
      startAngle: 210,
      endAngle: -30,
      radius: `${93 - index * 19}%`,
      min: 0,
      max: 100,
      pointer: {
        show: false,
      },
      axisLine: {
        lineStyle: {
          width: 14,
          color: [[1, "rgba(255,255,255,0.08)"]],
        },
      },
      progress: {
        show: true,
        roundCap: true,
        width: 14,
        itemStyle: {
          color: CHART_COLORS[index],
        },
      },
      splitLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: metric.value, name: metric.label }],
    })),
  }
}

function buildPictorialBarOption(module: ExternalInsightModule): EChartsOption {
  const items = module.pictorialItems ?? module.metrics.map((m) => ({ ...m, symbol: "circle" }))
  const labels = items.map((item) => item.label)
  const values = items.map((item) => item.value)

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 12,
      right: 18,
      bottom: 4,
      left: 120,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : []
        const idx = (arr[0] as { dataIndex: number })?.dataIndex ?? 0
        const item = items[idx]
        if (!item) return ""
        return `<div style="font-weight:600">${item.label}</div>
                <div style="font-size:16px;font-weight:700;color:${CHART_COLORS[idx % CHART_COLORS.length]};margin-top:4px">
                  ${formatInsightValue(item.value, item.unit)}
                </div>
                ${item.description ? `<div style="font-size:11px;color:#aaa;margin-top:4px;max-width:200px;white-space:normal">${item.description}</div>` : ""}`
      },
    },
    xAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.08)",
        },
      },
      axisLabel: {
        color: "rgba(255,255,255,0.45)",
      },
    },
    yAxis: {
      type: "category",
      data: labels,
      inverse: true,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: "rgba(255,255,255,0.74)",
        formatter: (value: string, index: number) => {
          const item = items[index]
          if (!item) return value
          return `{name|${value}}\n{value|${item.value}${item.unit}}`
        },
        rich: {
          name: {
            color: "rgba(255,255,255,0.74)",
            fontSize: 12,
            lineHeight: 18,
          },
          value: {
            color: "#FFFFFF",
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 18,
          },
        },
      },
    },
    series: [
      {
        type: "bar",
        data: values,
        barWidth: 6,
        itemStyle: {
          color: "rgba(122, 119, 255, 0.22)",
          borderRadius: 999,
        },
        z: 1,
      },
      {
        type: "pictorialBar",
        data: values.map((value, idx) => ({
          value,
          symbol: items[idx]?.symbol ?? "circle",
          itemStyle: {
            color: CHART_COLORS[idx % CHART_COLORS.length],
            shadowBlur: 16,
            shadowColor: CHART_COLORS[idx % CHART_COLORS.length] + "66",
          },
        })),
        symbolPosition: "end",
        symbolSize: [20, 20],
        z: 3,
      },
    ],
  }
}

function buildRadialProgressOption(module: ExternalInsightModule): EChartsOption {
  const metrics = module.metrics
  const maxes = [400, 400, 400, 8, 0.5, 100]
  const normalized = metrics.map((m, i) => {
    const max = maxes[i] ?? m.value * 1.2
    return Math.min(100, Math.round((m.value / max) * 100))
  })

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { dataIndex: number }
        const metric = metrics[p.dataIndex]
        if (!metric) return ""
        return `<div style="font-weight:600">${metric.label}</div>
                <div style="font-size:16px;font-weight:700;color:${CHART_COLORS[p.dataIndex % CHART_COLORS.length]};margin-top:4px">
                  ${formatInsightValue(metric.value, metric.unit)}
                </div>
                ${metric.description ? `<div style="font-size:11px;color:#aaa;margin-top:4px;max-width:200px;white-space:normal">${metric.description}</div>` : ""}`
      },
    },
    polar: {
      radius: "65%",
    },
    angleAxis: {
      type: "category",
      data: metrics.map((m) => m.label),
      startAngle: 75,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "rgba(255,255,255,0.72)",
        fontSize: 12,
        interval: 0,
      },
    },
    radiusAxis: {
      min: 0,
      max: 100,
      axisLine: { show: false },
      axisLabel: { show: false },
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.08)",
        },
      },
    },
    series: [
      {
        type: "bar",
        coordinateSystem: "polar",
        data: normalized.map((v, i) => ({
          value: v,
          itemStyle: {
            color: CHART_COLORS[i % CHART_COLORS.length],
            borderRadius: 4,
          },
        })),
        barWidth: "50%",
        label: {
          show: true,
          position: "outside",
          formatter: (params: unknown) => {
            const p = params as { dataIndex: number }
            const metric = metrics[p.dataIndex]
            if (!metric) return ""
            return `${metric.value}${metric.unit}`
          },
          color: "#FFFFFF",
          fontSize: 12,
          fontWeight: 600,
        },
      },
    ],
  }
}

function buildFunnelOption(module: ExternalInsightModule): EChartsOption {
  // 只取前 3 个治理动作指标放入漏斗（约谈 / 处罚 / 关站），阅读量在卡片中展示
  const funnelMetrics = module.metrics.slice(0, 3)
  const funnelColors = ["#FF8A5B", "#FB7185", "#7A77FF"]

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { dataIndex: number; name: string; value: number }
        const metric = funnelMetrics[p.dataIndex]
        if (!metric) return ""
        return `<div style="font-weight:600">${metric.label}</div>
                <div style="font-size:16px;font-weight:700;color:${funnelColors[p.dataIndex]};margin-top:4px">
                  ${formatInsightValue(metric.value, metric.unit)}
                </div>
                ${metric.description ? `<div style="font-size:11px;color:#aaa;margin-top:4px;max-width:200px;white-space:normal">${metric.description}</div>` : ""}`
      },
    },
    series: [
      {
        type: "funnel",
        sort: "descending",
        left: "10%",
        top: 10,
        bottom: 10,
        width: "80%",
        min: 0,
        max: Math.max(...funnelMetrics.map((m) => m.value), 1),
        gap: 4,
        label: {
          show: true,
          position: "inside",
          formatter: "{b}\n{c} 家",
          color: "#FFFFFF",
          fontSize: 12,
          fontWeight: 600,
        },
        itemStyle: {
          borderColor: "#0A0A0F",
          borderWidth: 3,
        },
        emphasis: {
          label: {
            fontSize: 14,
          },
        },
        data: funnelMetrics.map((metric, index) => ({
          value: metric.value,
          name: metric.label,
          itemStyle: {
            color: funnelColors[index],
          },
        })),
      },
    ],
  }
}

function buildEcoRadarOption(module: ExternalInsightModule): EChartsOption {
  const metrics = module.metrics
  // 归一化到 0-100，用于雷达图绘制；tooltip 显示原始值
  // 顺序对应 metrics：开源模型(万+) / 衍生模型(万+) / 开发者(万) / 注册用户(亿+)
  const maxes = [3, 10, 1000, 8]
  const normalized = metrics.map((m, i) => {
    const max = maxes[i] ?? m.value * 1.2
    return Math.min(100, Math.round((m.value / max) * 100))
  })

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: () => {
        let html = `<div style="font-weight:600;margin-bottom:6px">生态健康度</div>`
        metrics.forEach((m, idx) => {
          html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:4px">
            <span style="color:${CHART_COLORS[idx % CHART_COLORS.length]}">${m.label}</span>
            <span style="font-weight:600">${formatInsightValue(m.value, m.unit)}</span>
          </div>`
        })
        return html
      },
    },
    radar: {
      radius: "55%",
      splitNumber: 4,
      indicator: metrics.map((m) => ({
        name: `${m.label}\n${m.value}${m.unit}`,
        max: 100,
      })),
      axisName: {
        color: "rgba(255,255,255,0.82)",
        fontSize: 12,
        lineHeight: 18,
      },
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.08)",
        },
      },
      splitArea: {
        areaStyle: {
          color: ["rgba(0, 209, 255, 0.03)", "rgba(0, 209, 255, 0.01)"],
        },
      },
      axisLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.12)",
        },
      },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: normalized,
            name: "生态健康度",
            areaStyle: {
              color: "rgba(0, 209, 255, 0.18)",
            },
            lineStyle: {
              color: "#00D1FF",
              width: 3,
            },
            itemStyle: {
              color: "#00D1FF",
            },
          },
        ],
      },
    ],
  }
}

function buildExternalOption(module: ExternalInsightModule): EChartsOption {
  switch (module.visualType) {
    case "arc-progress":
      return buildArcProgressOption(module)
    case "pictorial-bar":
      return buildPictorialBarOption(module)
    case "radial-progress":
      return buildRadialProgressOption(module)
    case "funnel":
      return buildFunnelOption(module)
    case "radar":
      return buildEcoRadarOption(module)
    default:
      return createEmptyOption(module.moduleTitle)
  }
}

function buildTrendOption(completions?: DashboardTrendSeries, responseTime?: DashboardTrendSeries): EChartsOption {
  const labels = completions?.points.map((point) => point.label) ?? responseTime?.points.map((point) => point.label) ?? []

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 30,
      right: 18,
      bottom: 6,
      left: 16,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : []
        let html = `<div style="font-weight:600;margin-bottom:4px;">${arr[0]?.axisValue ?? ""}</div>`
        for (const p of arr) {
          const marker = p.marker ?? `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;"></span>`
          html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:3px;">`
          html += `<span>${marker}${p.seriesName}</span>`
          html += `<span style="font-weight:600;">${p.value} ${p.seriesName?.includes("时间") ? "ms" : "件"}</span>`
          html += `</div>`
        }
        return html
      },
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: {
        color: "rgba(255,255,255,0.68)",
      },
    },
    xAxis: {
      type: "category",
      data: labels,
      axisLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.12)",
        },
      },
      axisTick: { show: false },
      axisLabel: {
        color: "rgba(255,255,255,0.6)",
      },
    },
    yAxis: [
      {
        type: "value",
        name: completions?.unit ?? "件",
        splitLine: {
          lineStyle: {
            color: "rgba(255,255,255,0.08)",
          },
        },
        axisLabel: { color: "rgba(255,255,255,0.44)" },
      },
      {
        type: "value",
        name: responseTime?.unit ?? "ms",
        splitLine: { show: false },
        axisLabel: { color: "rgba(255,255,255,0.44)" },
      },
    ],
    series: [
      {
        name: completions?.title ?? "近7日完成任务量",
        type: "bar",
        yAxisIndex: 0,
        barMaxWidth: 18,
        data: completions?.points.map((point) => point.value) ?? [],
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: "#61D4FF",
        },
      },
      {
        name: responseTime?.title ?? "近7日平均响应时间",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: responseTime?.points.map((point) => point.value) ?? [],
        symbol: "circle",
        symbolSize: 8,
        lineStyle: {
          color: "#D4FF3C",
          width: 3,
        },
        itemStyle: {
          color: "#D4FF3C",
          borderColor: "#0A0A0F",
          borderWidth: 2,
        },
        areaStyle: {
          color: "rgba(212,255,60,0.14)",
        },
      },
    ],
  }
}

function buildRoseOption(items: DashboardDistributionItem[]): EChartsOption {
  if (!items.length) {
    return createEmptyOption("暂无威胁分布")
  }

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent: number; color: string }
        return `<div style="font-weight:600;margin-bottom:4px;">${p.name}</div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                  <span>数量：${p.value} 件</span>
                </div>
                <div style="margin-top:3px;color:rgba(255,255,255,0.65);">占比：${p.percent.toFixed(1)}%</div>`
      },
    },
    series: [
      {
        type: "pie",
        roseType: "area",
        radius: ["18%", "78%"],
        center: ["50%", "52%"],
        itemStyle: {
          borderColor: "#0A0A0F",
          borderWidth: 2,
        },
        label: {
          color: "rgba(255,255,255,0.76)",
          formatter: "{b}\n{c}",
        },
        labelLine: {
          length: 10,
          length2: 10,
        },
        data: items.map((item, index) => ({
          name: item.label,
          value: item.value,
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
          },
        })),
      },
    ],
  }
}

function buildTreemapOption(items: DashboardDistributionItem[]): EChartsOption {
  if (!items.length) {
    return createEmptyOption("暂无状态分布")
  }

  const total = items.reduce((sum, item) => sum + item.value, 0)

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; color: string }
        const share = total > 0 ? ((p.value / total) * 100).toFixed(1) : "0.0"
        return `<div style="font-weight:600;margin-bottom:4px;">${p.name}</div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                  <span>数量：${p.value} 件</span>
                </div>
                <div style="margin-top:3px;color:rgba(255,255,255,0.65);">占比：${share}%</div>`
      },
    },
    series: [
      {
        type: "treemap",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        upperLabel: { show: false },
        label: {
          show: true,
          formatter: "{b}\n{c} 件",
          color: "#FFFFFF",
        },
        itemStyle: {
          borderColor: "#0A0A0F",
          borderWidth: 4,
          gapWidth: 4,
          borderRadius: 16,
        },
        color: CHART_COLORS,
        data: items.map((item) => ({
          name: item.label,
          value: item.value,
        })),
      },
    ],
  }
}

function buildRadarOption(items: DashboardDistributionItem[]): EChartsOption {
  if (!items.length) {
    return createEmptyOption("暂无证据分布")
  }

  const topItems = items.slice(0, 6)
  const maxValue = Math.max(...topItems.map((item) => item.value), 1)

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number[] }
        let html = `<div style="font-weight:600;margin-bottom:6px;">${p.name}</div>`
        topItems.forEach((item, idx) => {
          html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:3px;">
            <span>${item.label}</span>
            <span style="font-weight:600;">${p.value[idx]} 件</span>
          </div>`
        })
        return html
      },
    },
    radar: {
      radius: "66%",
      splitNumber: 4,
      indicator: topItems.map((item) => ({
        name: item.label,
        max: Math.max(maxValue, item.value),
      })),
      axisName: {
        color: "rgba(255,255,255,0.74)",
      },
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.08)",
        },
      },
      splitArea: {
        areaStyle: {
          color: ["rgba(255,255,255,0.02)", "rgba(255,255,255,0.01)"],
        },
      },
      axisLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.12)",
        },
      },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: topItems.map((item) => item.value),
            name: "证据类型分布",
            areaStyle: {
              color: "rgba(97, 212, 255, 0.26)",
            },
            lineStyle: {
              color: "#61D4FF",
              width: 3,
            },
            itemStyle: {
              color: "#61D4FF",
            },
          },
        ],
      },
    ],
  }
}

function buildSankeyOption(flowSankey: DashboardViewModel["flowSankey"]): EChartsOption {
  if (!flowSankey.nodes.length || !flowSankey.links.length) {
    return createEmptyOption("暂无证据流向")
  }

  // 缩短过长节点名称，避免右侧/左侧被截断；tooltip 仍显示原始名称
  const nameMap: Record<string, string> = {
    inconclusive: "存疑",
    "高风险结论": "高风险",
    "真实结果": "真实",
    osint_agent: "开源情报",
    forensics_agent: "取证分析",
  }
  const mappedNodes = flowSankey.nodes.map((n) => ({
    ...n,
    name: nameMap[n.name] ?? n.name,
  }))
  const mappedLinks = flowSankey.links.map((l) => ({
    ...l,
    source: nameMap[l.source] ?? l.source,
    target: nameMap[l.target] ?? l.target,
  }))

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: (params: unknown) => {
        const p = params as { dataType?: string; data?: { source?: string; target?: string; name?: string }; value?: number; name?: string }
        if (p.dataType === "edge") {
          const source = p.data?.source ?? p.name ?? "?"
          const target = p.data?.target ?? "?"
          return `<div style="font-weight:600;margin-bottom:4px;">${source} → ${target}</div>
                  <div>流转次数：${p.value ?? 0} 次</div>`
        }
        const nodeName = p.data?.name ?? p.name ?? ""
        return `<div style="font-weight:600;margin-bottom:4px;">${nodeName}</div>
                <div>涉及证据数：${p.value ?? 0} 件</div>`
      },
    },
    series: [
      {
        type: "sankey",
        emphasis: {
          focus: "adjacency",
        },
        data: mappedNodes,
        links: mappedLinks,
        left: "4%",
        right: "10%",
        top: 18,
        bottom: 18,
        nodeWidth: 16,
        nodeGap: 20,
        draggable: false,
        lineStyle: {
          color: "gradient",
          curveness: 0.5,
          opacity: 0.42,
        },
        itemStyle: {
          borderWidth: 0,
          color: "#7A77FF",
        },
        label: {
          color: "rgba(255,255,255,0.78)",
        },
      },
    ],
  }
}

function SectionHeading({
  code,
  title,
  badge,
}: {
  code: string
  title: string
  badge: string
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm tracking-[0.28em] text-[#D4FF3C]">{code}</span>
        <h2 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">{title}</h2>
      </div>
      <span className="rounded-full border border-white/10 bg-white/6 px-4 py-1.5 text-xs tracking-[0.18em] text-white/62 uppercase">
        {badge}
      </span>
    </div>
  )
}

function MiniBar({ value, max, color, title }: { value: number; max: number; color: string; title?: string }) {
  const progress = Math.min(value / max, 1)

  return (
    <div className="mx-auto h-1.5 w-20 overflow-hidden rounded-full bg-white/8" title={title}>
      <div
        className="h-full rounded-full"
        style={{
          width: `${progress * 100}%`,
          backgroundColor: color,
          transition: "width 1.2s ease-out",
        }}
      />
    </div>
  )
}

function DigitalCardsChart({ metrics }: { metrics: ExternalInsightModule["metrics"] }) {
  const displayMetrics = metrics.slice(0, 3)
  const barColors = ["#FF8A5B", "#7A77FF", "#00D1FF"]
  const barMaxes = [20, 2, 100] // 对应 16.2亿/20、1.3亿条/2、33.3%/100

  return (
    <div className="flex h-[280px] items-center justify-around">
      {displayMetrics.map((metric, index) => (
        <div key={metric.label} className="flex flex-col items-center gap-3">
          <p className="text-center text-sm text-white/56">{metric.label}</p>
          <p className="text-center text-3xl font-bold tracking-tight text-white" style={{ fontFamily: "monospace" }}>
            {formatInsightValue(metric.value, metric.unit)}
          </p>
          <MiniBar
            value={metric.value}
            max={barMaxes[index] ?? metric.value * 1.2}
            color={barColors[index] ?? "#61D4FF"}
            title={`${metric.label}: ${formatInsightValue(metric.value, metric.unit)}${metric.description ? ` — ${metric.description}` : ""}`}
          />
          {metric.description && (
            <p className="min-h-[36px] max-w-[140px] text-center text-xs leading-4 text-white/40">{metric.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function MetricCard({ metric }: { metric: ExternalInsightModule["metrics"][0] }) {
  return (
    <div className="rounded-[20px] border border-white/8 bg-white/4 p-4 transition-colors hover:bg-white/6">
      <p className="text-sm leading-6 text-white/56">{metric.label}</p>
      <p className="mt-2 text-xl font-semibold tracking-tight text-white">
        {formatInsightValue(metric.value, metric.unit)}
      </p>
      {metric.description && (
        <p className="mt-1.5 text-xs leading-5 text-white/40">{metric.description}</p>
      )}
    </div>
  )
}

function ExternalInsightCard({ module, index }: { module: ExternalInsightModule; index: number }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.45, delay: index * 0.08 }}
      className="rounded-[28px] border border-white/8 bg-white/4 p-6 backdrop-blur-xl"
    >
      <div className="grid gap-6 xl:grid-cols-[38fr_62fr] xl:items-center">
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">
                {module.layer === "risk-foundation" ? "Risk Foundation" : "Governance Environment"}
              </p>
              <h3 className="text-2xl font-semibold tracking-tight text-white">{module.moduleTitle}</h3>
            </div>
            <span className="rounded-full border border-white/10 bg-black/16 px-3 py-1 text-xs text-white/58">
              {module.metrics.length} 项指标
            </span>
          </div>

          <p className="text-sm leading-7 text-white/66">{module.summary}</p>

          <Link
            href={module.source.url}
            target="_blank"
            rel="noreferrer"
            className="group flex items-start justify-between gap-4 rounded-[22px] border border-white/10 bg-black/18 p-4 transition-colors hover:border-[#D4FF3C]/35 hover:bg-black/24"
          >
            <div className="space-y-2">
              <p className="text-xs tracking-[0.18em] text-white/46 uppercase">来源链接</p>
              <p className="text-sm leading-6 text-white/84">{module.source.reportTitle}</p>
              <p className="text-xs text-white/52">
                {module.source.publisher} · {module.source.publishedAt}
              </p>
            </div>
            <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-white/44 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[#D4FF3C]" />
          </Link>
        </div>

        <div className="space-y-4">
          {module.visualType === "digital-cards" ? (
            <div className="rounded-[24px] border border-white/8 bg-black/18 p-4">
              <DigitalCardsChart metrics={module.metrics} />
            </div>
          ) : (
            <div className="rounded-[24px] border border-white/8 bg-black/18 p-4">
              <DashboardChart option={buildExternalOption(module)} height={module.visualType === "arc-progress" ? 260 : module.visualType === "radial-progress" ? 340 : 280} />
              {module.visualType === "arc-progress" && (
                <div className="-mt-7 text-center">
                  <p className="text-2xl font-semibold tracking-tight text-white">
                    {formatInsightValue(module.metrics[0].value, module.metrics[0].unit)}
                  </p>
                  <p className="mt-1 text-xs text-white/58">{module.metrics[0].label}</p>
                </div>
              )}
            </div>
          )}

          <div className={`grid gap-3 ${module.metrics.length === 4 ? "grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-3"}`}>
            {module.metrics.map((metric) => (
              <MetricCard key={`${module.id}-${metric.label}`} metric={metric} />
            ))}
          </div>
        </div>
      </div>
    </motion.article>
  )
}

function KpiCard({
  label,
  tone,
  value,
  index,
}: {
  label: string
  tone: string
  value: string
  index: number
}) {
  const Icon = KPI_META[index].icon

  const helperText = KPI_META[index].id === "totalTasks" ? "系统中累计创建的检测任务总数" : KPI_META[index].id === "highRiskTasks" ? "被判定为高风险的任务数量" : KPI_META[index].id === "averageResponseMs" ? "所有已完成任务的平均处理耗时" : "今日（上海时区）标记为已完成的任务数"

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className="group rounded-[24px] border border-white/8 bg-white/4 p-5 transition-all duration-300 hover:border-white/16 hover:bg-white/7"
      title={helperText}
    >
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className={`rounded-2xl border border-white/10 bg-black/18 p-3 transition-transform duration-300 group-hover:scale-110 ${tone}`}>
          <Icon className="size-5" />
        </div>
        <span className="text-xs tracking-[0.18em] text-white/38 uppercase">KPI</span>
      </div>
      <p className="text-sm text-white/58 transition-colors duration-300 group-hover:text-white/72">{label}</p>
      <p className="mt-3 text-4xl font-semibold tracking-tight text-white transition-colors duration-300 group-hover:text-[#D4FF3C]">{value}</p>
    </motion.div>
  )
}

function CapabilityMetricList({ metrics }: { metrics: DashboardCapabilityMetric[] }) {
  const icons = [FileCheck2, Users, ShieldCheck]

  return (
    <div className="space-y-4">
      {metrics.map((metric, index) => {
        const Icon = icons[index % icons.length]

        return (
          <div
            key={metric.id}
            className="group rounded-[22px] border border-white/8 bg-white/4 p-4 transition-all duration-300 hover:border-white/16 hover:bg-white/7"
            title={metric.helper}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="rounded-2xl border border-white/10 bg-black/18 p-3 text-[#D4FF3C] transition-transform duration-300 group-hover:scale-110">
                <Icon className="size-4" />
              </div>
              <p className="text-3xl font-semibold tracking-tight text-white transition-colors duration-300 group-hover:text-[#D4FF3C]">
                {metric.value.toLocaleString("zh-CN")}
              </p>
            </div>
            <p className="text-sm text-white/72 transition-colors duration-300 group-hover:text-white/84">{metric.label}</p>
            <p className="mt-1 text-xs leading-6 text-white/46 transition-colors duration-300 group-hover:text-white/60">{metric.helper}</p>
          </div>
        )
      })}
    </div>
  )
}

export function DashboardClient({ viewModel }: DashboardClientProps) {
  const riskModules = viewModel.externalInsights.filter((module) => module.layer === "risk-foundation")
  const governanceModules = viewModel.externalInsights.filter((module) => module.layer === "governance-environment")
  const completionTrend = viewModel.trendSeries.find((series) => series.id === "daily-completions")
  const responseTrend = viewModel.trendSeries.find((series) => series.id === "response-time")

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-0 h-[38rem] w-[38rem] -translate-x-1/2 rounded-full bg-[#5B6CFF]/18 blur-[180px]" />
        <div className="absolute -left-24 top-[28rem] h-[26rem] w-[26rem] rounded-full bg-[#00D1FF]/10 blur-[140px]" />
        <div className="absolute right-[-8rem] top-[58rem] h-[30rem] w-[30rem] rounded-full bg-[#D4FF3C]/8 blur-[180px]" />
        <div className="absolute inset-0 grid-bg opacity-35" />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8">
        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(135deg,rgba(18,22,38,0.95),rgba(10,12,22,0.82))] px-6 py-8 backdrop-blur-xl md:px-8"
        >
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#D4FF3C]/25 bg-[#D4FF3C]/10 px-4 py-1.5 text-xs tracking-[0.18em] text-[#D4FF3C] uppercase">
                TruthSeeker Data Screen
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs tracking-[0.18em] text-white/58 uppercase">
                外部权威 + 内部汇总
              </span>
            </div>

            <h1 className="whitespace-nowrap text-3xl font-semibold tracking-tight text-white md:text-[2.75rem]">
              深度伪造风险与系统能力数据大屏
            </h1>

            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div className="flex flex-wrap gap-2">
                {["权威公开来源", "真实业务聚合", "ECharts 多图种"].map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-white/10 bg-black/16 px-3 py-1 text-xs tracking-[0.16em] text-white/54 uppercase"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <p className="text-sm leading-7 text-white/58">刷新时间：{formatGeneratedAt(viewModel.generatedAt)}（Asia/Shanghai）</p>
            </div>
          </div>
        </motion.section>

        <section className="relative overflow-hidden rounded-[34px] border border-white/8 bg-black/22 px-6 py-8 md:px-8">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META["risk-foundation"].accent}`} />
          <div className="relative z-10 space-y-6">
            <SectionHeading {...SECTION_META["risk-foundation"]} />
            <div data-testid="risk-stack" className="flex flex-col gap-6">
              {riskModules.map((module, index) => (
                <ExternalInsightCard key={module.id} module={module} index={index} />
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[34px] border border-white/8 bg-black/22 px-6 py-8 md:px-8">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META["governance-environment"].accent}`} />
          <div className="relative z-10 space-y-6">
            <SectionHeading {...SECTION_META["governance-environment"]} />
            <div data-testid="governance-stack" className="flex flex-col gap-6">
              {governanceModules.map((module, index) => (
                <ExternalInsightCard key={module.id} module={module} index={index} />
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[38px] border border-white/10 bg-[#080B12]/84 px-6 py-8 md:px-8 md:py-10">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META.capability.accent}`} />
          <div className="relative z-10 space-y-6">
            <SectionHeading {...SECTION_META.capability} />

            {viewModel.capabilityState === "error" ? (
              <div className="flex items-center gap-3 rounded-[22px] border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-4 py-3 text-sm text-white/74">
                <AlertTriangle className="size-4 shrink-0 text-[#FCD34D]" />
                <span>内部汇总暂时未返回，第三层先展示为空态。</span>
              </div>
            ) : null}

            {viewModel.capabilityState === "warning" ? (
              <div className="flex items-center gap-3 rounded-[22px] border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-4 py-3 text-sm text-white/74">
                <AlertTriangle className="size-4 shrink-0 text-[#FCD34D]" />
                <span>{viewModel.dataWarnings[0] ?? "内部数据源部分异常，当前指标可能不完整。"}</span>
              </div>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
              {KPI_META.map((item, index) => {
                const rawValue = viewModel.kpis[item.id]
                const formatted = item.id === "averageResponseMs" ? `${rawValue.toLocaleString("zh-CN")} ms` : rawValue.toLocaleString("zh-CN")

                return <KpiCard key={item.id} label={item.label} tone={item.tone} value={formatted} index={index} />
              })}
            </div>

            <div className="grid gap-6 xl:grid-cols-12">
              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-7">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Trend</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">响应与处置趋势</h3>
                  </div>
                  <p className="text-sm text-white/52">完成量与响应时间同图对照</p>
                </div>
                <DashboardChart option={buildTrendOption(completionTrend, responseTrend)} height={340} />
              </div>

              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-5">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Threat Mix</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">威胁分布</h3>
                  </div>
                </div>
                <DashboardChart option={buildRoseOption(viewModel.threatMix)} height={340} />
              </div>

              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-4">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Status</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">任务状态</h3>
                  </div>
                </div>
                <DashboardChart option={buildTreemapOption(viewModel.statusBreakdown)} height={300} />
              </div>

              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-4">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Evidence Mix</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">证据类型分布</h3>
                  </div>
                </div>
                <DashboardChart option={buildRadarOption(viewModel.evidenceMix)} height={300} />
              </div>

              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-4">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Capability</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">闭环指标</h3>
                  </div>
                </div>
                <CapabilityMetricList metrics={viewModel.capabilityMetrics} />
              </div>

              <div className="rounded-[30px] border border-white/8 bg-white/4 p-6 xl:col-span-12">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.22em] text-white/42 uppercase">Sankey</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">证据流向</h3>
                  </div>
                  <p className="text-sm text-white/52">输入类型 → 证据来源 → 最终结论</p>
                </div>
                <DashboardChart option={buildSankeyOption(viewModel.flowSankey)} height={420} />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
