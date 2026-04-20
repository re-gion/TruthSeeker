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
    graphic: [
      {
        type: "text",
        left: "center",
        top: "38%",
        style: {
          text: formatInsightValue(headline.value, headline.unit),
          fill: "#FFFFFF",
          fontSize: 28,
          fontWeight: 700,
        },
      },
      {
        type: "text",
        left: "center",
        top: "52%",
        style: {
          text: headline.label,
          fill: "rgba(255,255,255,0.58)",
          fontSize: 12,
        },
      },
    ],
    series: rings.map((metric, index) => ({
      type: "gauge",
      startAngle: 210,
      endAngle: -30,
      radius: `${96 - index * 18}%`,
      min: 0,
      max: 100,
      pointer: {
        show: false,
      },
      axisLine: {
        lineStyle: {
          width: 12,
          color: [[1, "rgba(255,255,255,0.08)"]],
        },
      },
      progress: {
        show: true,
        roundCap: true,
        width: 12,
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

function buildLollipopOption(module: ExternalInsightModule): EChartsOption {
  const labels = module.metrics.map((metric) => metric.label)
  const values = module.metrics.map((metric) => metric.value)

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
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: "rgba(255,255,255,0.74)",
      },
    },
    series: [
      {
        type: "bar",
        data: values,
        barWidth: 8,
        itemStyle: {
          color: "rgba(122, 119, 255, 0.38)",
          borderRadius: 999,
        },
        z: 1,
      },
      {
        type: "pictorialBar",
        data: values,
        symbol: "circle",
        symbolPosition: "end",
        symbolSize: 16,
        itemStyle: {
          color: "#7A77FF",
          shadowBlur: 12,
          shadowColor: "rgba(122,119,255,0.45)",
        },
        z: 3,
      },
    ],
  }
}

function buildRadialProgressOption(module: ExternalInsightModule): EChartsOption {
  const maxValue = Math.max(...module.metrics.map((metric) => metric.value), 1)

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    series: module.metrics.map((metric, index) => ({
      type: "gauge",
      center: [`${18 + index * 32}%`, "52%"],
      radius: "28%",
      min: 0,
      max: maxValue,
      startAngle: 210,
      endAngle: -30,
      pointer: { show: false },
      progress: {
        show: true,
        width: 14,
        roundCap: true,
        itemStyle: {
          color: CHART_COLORS[index + 1] ?? CHART_COLORS[index],
        },
      },
      axisLine: {
        lineStyle: {
          width: 14,
          color: [[1, "rgba(255,255,255,0.08)"]],
        },
      },
      splitLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      title: {
        offsetCenter: [0, "118%"],
        color: "rgba(255,255,255,0.72)",
        fontSize: 11,
      },
      detail: {
        offsetCenter: [0, "56%"],
        formatter: formatInsightValue(metric.value, metric.unit),
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: 700,
      },
      data: [{ value: metric.value, name: metric.label }],
    })),
  }
}

function buildSignalBarsOption(module: ExternalInsightModule): EChartsOption {
  const values = module.metrics.map((metric) => metric.value)
  const maxValue = Math.max(...values, 1)

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 12,
      right: 18,
      bottom: 8,
      left: 16,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      max: 1,
      splitLine: { show: false },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    yAxis: {
      type: "category",
      data: module.metrics.map((metric) => metric.label),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: "rgba(255,255,255,0.72)",
      },
    },
    series: [
      {
        type: "bar",
        data: module.metrics.map((metric) => metric.value / maxValue),
        barWidth: 18,
        itemStyle: {
          borderRadius: 999,
          color: (params: { dataIndex: number }) => CHART_COLORS[params.dataIndex % CHART_COLORS.length],
        },
        label: {
          show: true,
          position: "right",
          color: "#FFFFFF",
          formatter: (params: { dataIndex: number }) =>
            formatInsightValue(module.metrics[params.dataIndex].value, module.metrics[params.dataIndex].unit),
        },
      },
    ],
  }
}

function buildExternalOption(module: ExternalInsightModule): EChartsOption {
  switch (module.visualType) {
    case "arc-progress":
      return buildArcProgressOption(module)
    case "lollipop-rank":
      return buildLollipopOption(module)
    case "radial-progress":
      return buildRadialProgressOption(module)
    case "signal-bars":
      return buildSignalBarsOption(module)
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
      formatter: "{b}<br/>{c} 件",
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

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
      formatter: "{b}<br/>{c} 件",
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

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#F5F5F5" },
    },
    series: [
      {
        type: "sankey",
        emphasis: {
          focus: "adjacency",
        },
        data: flowSankey.nodes,
        links: flowSankey.links,
        left: "4%",
        right: "4%",
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

function ExternalInsightCard({ module, index }: { module: ExternalInsightModule; index: number }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.45, delay: index * 0.08 }}
      className="rounded-[28px] border border-white/8 bg-white/4 p-6 backdrop-blur-xl"
    >
      <div className="grid gap-6 xl:grid-cols-[0.38fr_0.62fr] xl:items-center">
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
          <div className="rounded-[24px] border border-white/8 bg-black/18 p-4">
            <DashboardChart option={buildExternalOption(module)} height={280} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {module.metrics.map((metric) => (
              <div key={`${module.id}-${metric.label}`} className="rounded-[20px] border border-white/8 bg-white/4 p-4">
                <p className="text-sm leading-6 text-white/56">{metric.label}</p>
                <p className="mt-3 text-xl font-semibold tracking-tight text-white">
                  {formatInsightValue(metric.value, metric.unit)}
                </p>
              </div>
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className="rounded-[24px] border border-white/8 bg-white/4 p-5"
    >
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className={`rounded-2xl border border-white/10 bg-black/18 p-3 ${tone}`}>
          <Icon className="size-5" />
        </div>
        <span className="text-xs tracking-[0.18em] text-white/38 uppercase">KPI</span>
      </div>
      <p className="text-sm text-white/58">{label}</p>
      <p className="mt-3 text-4xl font-semibold tracking-tight text-white">{value}</p>
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
          <div key={metric.id} className="rounded-[22px] border border-white/8 bg-white/4 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="rounded-2xl border border-white/10 bg-black/18 p-3 text-[#D4FF3C]">
                <Icon className="size-4" />
              </div>
              <p className="text-3xl font-semibold tracking-tight text-white">{metric.value.toLocaleString("zh-CN")}</p>
            </div>
            <p className="text-sm text-white/72">{metric.label}</p>
            <p className="mt-1 text-xs leading-6 text-white/46">{metric.helper}</p>
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
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-[#D4FF3C]/25 bg-[#D4FF3C]/10 px-4 py-1.5 text-xs tracking-[0.18em] text-[#D4FF3C] uppercase">
                  TruthSeeker Data Screen
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs tracking-[0.18em] text-white/58 uppercase">
                  外部权威 + 内部汇总
                </span>
              </div>
              <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-white md:text-6xl">
                深度伪造风险与系统能力数据大屏
              </h1>
            </div>

            <div className="space-y-3 lg:text-right">
              <div className="flex flex-wrap gap-2 lg:justify-end">
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
