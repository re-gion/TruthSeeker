"use client"

import Link from "next/link"
import { motion } from "motion/react"
import type { EChartsOption } from "echarts"
import {
  ArrowUpRight,
  Clock3,
  FileCheck2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react"

import { DashboardChart } from "@/components/dashboard/DashboardChart"
import type {
  DashboardCapabilityMetric,
  DashboardDistributionSeries,
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
    accent: "from-[#EF4444]/25 via-[#F59E0B]/10 to-transparent",
    badge: "风险扩散面",
    description: "先回答“为什么必须做 Deepfake 治理”。这一层只展示来自国家级、行业级公开报告的静态权威数据。",
  },
  "governance-environment": {
    code: "02",
    title: "治理环境",
    accent: "from-[#06B6D4]/20 via-[#6366F1]/10 to-transparent",
    badge: "治理压力面",
    description: "再回答“为什么这不是噱头，而是现实治理任务”。这一层同样全部指向原始公告或报告。",
  },
  capability: {
    code: "03",
    title: "系统能力层",
    accent: "from-[#6366F1]/25 via-[#1D4ED8]/12 to-transparent",
    badge: "系统证明面",
    description: "最后展示系统当前真实能做什么。所有指标均由现有业务表聚合，不使用伪实时或虚构节点数据。",
  },
} as const

const KPI_META = [
  {
    id: "totalTasks",
    label: "累计检测任务数",
    helper: "来自 tasks 表的累计记录",
    icon: ShieldCheck,
    format: (value: number) => value.toLocaleString("zh-CN"),
    tone: "text-[#D4FF12]",
  },
  {
    id: "highRiskTasks",
    label: "高风险任务数",
    helper: "覆盖 forged / suspicious / 伪造 / 疑似 等结果别名",
    icon: ShieldAlert,
    format: (value: number) => value.toLocaleString("zh-CN"),
    tone: "text-[#F59E0B]",
  },
  {
    id: "averageResponseMs",
    label: "平均响应时间",
    helper: "仅统计具备完整起止时间的已完成任务",
    icon: Clock3,
    format: (value: number) => `${value.toLocaleString("zh-CN")} ms`,
    tone: "text-[#60A5FA]",
  },
  {
    id: "completedToday",
    label: "今日完成任务数",
    helper: "按 Asia/Shanghai 日期口径统计",
    icon: Sparkles,
    format: (value: number) => value.toLocaleString("zh-CN"),
    tone: "text-[#A78BFA]",
  },
] as const

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

function formatShare(share: number) {
  return `${Math.round(share * 100)}%`
}

function findTrend(viewModel: DashboardViewModel, id: string) {
  return viewModel.trendSeries.find((series) => series.id === id)
}

function findDistribution(viewModel: DashboardViewModel, id: string) {
  return viewModel.distributionSeries.find((series) => series.id === id)
}

function buildExternalOption(module: ExternalInsightModule): EChartsOption {
  const unitOrder = [...new Set(module.metrics.map((metric) => metric.unit))]

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 28,
      right: unitOrder.length > 1 ? 54 : 16,
      bottom: 10,
      left: 16,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
      backgroundColor: "rgba(10, 10, 15, 0.92)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: {
        color: "#F5F5F5",
      },
      valueFormatter: (value) =>
        Array.isArray(value)
          ? value.join(", ")
          : typeof value === "number"
            ? value.toLocaleString("zh-CN")
            : value == null
              ? "-"
              : String(value),
    },
    legend:
      unitOrder.length > 1
        ? {
            top: 0,
            right: 0,
            itemWidth: 10,
            itemHeight: 10,
            textStyle: {
              color: "rgba(255,255,255,0.66)",
            },
          }
        : undefined,
    xAxis: {
      type: "category",
      data: module.metrics.map((metric) => metric.label),
      axisLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.12)",
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        color: "rgba(255,255,255,0.72)",
        interval: 0,
        fontSize: 11,
      },
    },
    yAxis: unitOrder.map((unit, index) => ({
      type: "value",
      name: unit,
      position: index === 0 ? "left" : "right",
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.08)",
        },
      },
      axisLine: {
        show: false,
      },
      axisLabel: {
        color: "rgba(255,255,255,0.48)",
      },
      nameTextStyle: {
        color: "rgba(255,255,255,0.48)",
        padding: [0, 0, 6, 0],
      },
    })),
    series: unitOrder.map((unit, index) => ({
      name: unit,
      type: "bar",
      yAxisIndex: index,
      barMaxWidth: 22,
      data: module.metrics.map((metric) => (metric.unit === unit ? metric.value : null)),
      itemStyle: {
        borderRadius: [8, 8, 0, 0],
        color:
          module.layer === "risk-foundation"
            ? ["#FB7185", "#F59E0B"][index] ?? "#F59E0B"
            : ["#38BDF8", "#818CF8"][index] ?? "#38BDF8",
      },
    })),
  }
}

function buildTrendOption(completions?: DashboardTrendSeries, responseTime?: DashboardTrendSeries): EChartsOption {
  const labels = responseTime?.points.map((point) => point.label) ?? completions?.points.map((point) => point.label) ?? []

  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 30,
      right: 24,
      bottom: 10,
      left: 16,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: {
        color: "#F5F5F5",
      },
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: {
        color: "rgba(255,255,255,0.66)",
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
      axisTick: {
        show: false,
      },
      axisLabel: {
        color: "rgba(255,255,255,0.64)",
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
        axisLabel: {
          color: "rgba(255,255,255,0.48)",
        },
      },
      {
        type: "value",
        name: responseTime?.unit ?? "ms",
        splitLine: {
          show: false,
        },
        axisLabel: {
          color: "rgba(255,255,255,0.48)",
        },
      },
    ],
    series: [
      {
        name: completions?.title ?? "近 7 日完成任务趋势",
        type: "bar",
        yAxisIndex: 0,
        barMaxWidth: 20,
        data: completions?.points.map((point) => point.value) ?? [],
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: "#6366F1",
        },
      },
      {
        name: responseTime?.title ?? "近 7 日平均响应时间",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        data: responseTime?.points.map((point) => point.value) ?? [],
        symbol: "circle",
        symbolSize: 8,
        lineStyle: {
          width: 3,
          color: "#D4FF12",
        },
        itemStyle: {
          color: "#D4FF12",
          borderColor: "#0A0A0F",
          borderWidth: 2,
        },
        areaStyle: {
          color: "rgba(212, 255, 18, 0.12)",
        },
      },
    ],
  }
}

function buildThreatOption(series?: DashboardDistributionSeries): EChartsOption {
  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    grid: {
      top: 18,
      right: 16,
      bottom: 10,
      left: 100,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: {
        color: "#F5F5F5",
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
        color: "rgba(255,255,255,0.48)",
      },
    },
    yAxis: {
      type: "category",
      data: series?.items.map((item) => item.label) ?? [],
      axisTick: {
        show: false,
      },
      axisLine: {
        show: false,
      },
      axisLabel: {
        color: "rgba(255,255,255,0.72)",
      },
    },
    series: [
      {
        type: "bar",
        data: series?.items.map((item) => item.value) ?? [],
        barMaxWidth: 18,
        label: {
          show: true,
          position: "right",
          color: "rgba(255,255,255,0.88)",
        },
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: "#FB7185",
        },
      },
    ],
  }
}

function buildStatusOption(series?: DashboardDistributionSeries): EChartsOption {
  return {
    backgroundColor: "transparent",
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 10, 15, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: {
        color: "#F5F5F5",
      },
      formatter: "{b}<br/>{c} 件 ({d}%)",
    },
    legend: {
      bottom: 0,
      left: "center",
      textStyle: {
        color: "rgba(255,255,255,0.66)",
      },
    },
    series: [
      {
        type: "pie",
        radius: ["48%", "72%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderColor: "#0A0A0F",
          borderWidth: 3,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            color: "#FFFFFF",
            fontWeight: 700,
          },
        },
        data:
          series?.items.map((item, index) => ({
            name: item.label,
            value: item.value,
            itemStyle: {
              color: ["#6366F1", "#38BDF8", "#F59E0B", "#EF4444", "#A78BFA"][index % 5],
            },
          })) ?? [],
      },
    ],
  }
}

function SectionHeading({
  code,
  title,
  badge,
  description,
}: {
  code: string
  title: string
  badge: string
  description: string
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-sm tracking-[0.3em] text-[#D4FF12]">{code}</span>
        <span className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs tracking-[0.18em] text-white/68 uppercase">
          {badge}
        </span>
      </div>
      <div className="max-w-4xl space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">{title}</h2>
        <p className="text-sm leading-7 text-white/64 md:text-base">{description}</p>
      </div>
    </div>
  )
}

function ExternalInsightCard({ module, index }: { module: ExternalInsightModule; index: number }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-120px" }}
      transition={{ duration: 0.55, delay: index * 0.08 }}
      className="liquid-glass relative overflow-hidden rounded-[28px] p-6"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/36 to-transparent" />
      <div className="flex flex-col gap-6 xl:flex-row">
        <div className="xl:w-[48%]">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="font-mono text-xs tracking-[0.25em] text-white/45">
                {module.layer === "risk-foundation" ? "RISK FOUNDATION" : "GOVERNANCE ENVIRONMENT"}
              </p>
              <h3 className="text-2xl font-semibold tracking-tight text-white">{module.moduleTitle}</h3>
            </div>
            <div className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-white/58">
              {module.metrics.length} 项指标
            </div>
          </div>

          <Link
            href={module.source.url}
            target="_blank"
            rel="noreferrer"
            className="group mb-5 block rounded-2xl border border-white/10 bg-black/18 p-4 transition-colors hover:border-[#D4FF12]/40 hover:bg-black/28"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-xs tracking-[0.18em] text-white/46 uppercase">权威来源</span>
              <ArrowUpRight className="size-4 text-white/48 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[#D4FF12]" />
            </div>
            <p className="text-sm text-white/82">{module.source.reportTitle}</p>
            <p className="mt-2 text-xs leading-6 text-white/54">
              {module.source.publisher} · {module.source.publishedAt}
            </p>
          </Link>

          <p className="rounded-2xl border border-white/8 bg-white/4 px-4 py-3 text-sm leading-7 text-white/68">
            {module.note}
          </p>
        </div>

        <div className="flex-1 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {module.metrics.map((metric) => (
              <div key={`${module.id}-${metric.label}`} className="rounded-2xl border border-white/8 bg-white/4 p-4">
                <p className="text-sm leading-6 text-white/64">{metric.label}</p>
                <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
                  {formatInsightValue(metric.value, metric.unit)}
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-[24px] border border-white/8 bg-black/16 p-4">
            <DashboardChart option={buildExternalOption(module)} height={276} />
          </div>
        </div>
      </div>
    </motion.article>
  )
}

function CapabilityMetricCard({ metric, index }: { metric: DashboardCapabilityMetric; index: number }) {
  const Icon = [FileCheck2, Users, ShieldCheck][index % 3]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.45, delay: index * 0.06 }}
      className="rounded-[24px] border border-white/8 bg-white/5 p-5"
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="rounded-2xl border border-white/10 bg-black/18 p-3 text-[#D4FF12]">
          <Icon className="size-5" />
        </div>
        <span className="text-xs tracking-[0.2em] text-white/44 uppercase">Capability</span>
      </div>
      <p className="text-sm leading-6 text-white/64">{metric.label}</p>
      <p className="mt-3 text-4xl font-semibold tracking-tight text-white">{metric.value.toLocaleString("zh-CN")}</p>
      <p className="mt-4 text-sm leading-7 text-white/52">{metric.helper}</p>
    </motion.div>
  )
}

export function DashboardClient({ viewModel }: DashboardClientProps) {
  const riskModules = viewModel.externalInsights.filter((module) => module.layer === "risk-foundation")
  const governanceModules = viewModel.externalInsights.filter((module) => module.layer === "governance-environment")
  const completionTrend = findTrend(viewModel, "daily-completions")
  const responseTrend = findTrend(viewModel, "response-time")
  const threatSeries = findDistribution(viewModel, "threat-types")
  const statusSeries = findDistribution(viewModel, "task-status")

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-0 h-[42rem] w-[42rem] -translate-x-1/2 rounded-full bg-[#6366F1]/18 blur-[160px]" />
        <div className="absolute -left-24 top-[28rem] h-[24rem] w-[24rem] rounded-full bg-[#0EA5E9]/10 blur-[140px]" />
        <div className="absolute right-[-6rem] top-[60rem] h-[30rem] w-[30rem] rounded-full bg-[#D4FF12]/8 blur-[180px]" />
        <div className="absolute inset-0 grid-bg opacity-40" />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 sm:px-6 lg:px-8">
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="glass-card overflow-hidden rounded-[32px] px-6 py-8 md:px-8"
        >
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-[#D4FF12]/25 bg-[#D4FF12]/10 px-4 py-1.5 text-xs tracking-[0.18em] text-[#D4FF12] uppercase">
                  TruthSeeker Data Screen
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs tracking-[0.18em] text-white/55 uppercase">
                  三层逻辑
                </span>
              </div>

              <div className="max-w-4xl space-y-4">
                <h1 className="text-4xl font-semibold leading-tight tracking-tight text-white md:text-6xl">
                  用可溯源权威数据说明风险，用真实业务数据证明系统能力。
                </h1>
                <p className="max-w-3xl text-sm leading-8 text-white/68 md:text-base">
                  前两层为外部权威公开数据策展，点击即可跳转原始网页或报告；第三层只展示由
                  `tasks`、`reports`、`consultation_invites` 聚合得到的真实运行结果。
                </p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
              <div className="rounded-[28px] border border-white/10 bg-black/18 p-5">
                <p className="text-xs tracking-[0.2em] text-white/46 uppercase">展示逻辑</p>
                <div className="mt-5 space-y-4">
                  {[
                    "风险底座：说明生成式内容与网络视听传播规模。",
                    "治理环境：说明国家与平台治理强度。",
                    "系统能力层：说明当前系统检测、报告与会诊闭环。",
                  ].map((item, index) => (
                    <div key={item} className="flex items-start gap-3">
                      <div className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-white/8 text-xs text-white/72">
                        {index + 1}
                      </div>
                      <p className="text-sm leading-7 text-white/66">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-gradient-to-br from-white/8 via-white/4 to-transparent p-5">
                <p className="text-xs tracking-[0.2em] text-white/46 uppercase">数据说明</p>
                <div className="mt-5 space-y-3 text-sm leading-7 text-white/68">
                  <p>外部数据：全部标注发布主体、发布时间、报告名称、来源链接。</p>
                  <p>内部数据：不展示伪实时吞吐量、全球节点数、占位 Agent 指标。</p>
                  <p>刷新时间：{formatGeneratedAt(viewModel.generatedAt)}（Asia/Shanghai）</p>
                </div>
              </div>
            </div>
          </div>
        </motion.section>

        <section className="relative overflow-hidden rounded-[36px] border border-white/8 bg-black/22 px-6 py-8 md:px-8">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META["risk-foundation"].accent}`} />
          <div className="relative z-10 space-y-6">
            <SectionHeading {...SECTION_META["risk-foundation"]} />
            <div className="grid gap-6 xl:grid-cols-2">
              {riskModules.map((module, index) => (
                <ExternalInsightCard key={module.id} module={module} index={index} />
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[36px] border border-white/8 bg-black/22 px-6 py-8 md:px-8">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META["governance-environment"].accent}`} />
          <div className="relative z-10 space-y-6">
            <SectionHeading {...SECTION_META["governance-environment"]} />
            <div className="grid gap-6 xl:grid-cols-2">
              {governanceModules.map((module, index) => (
                <ExternalInsightCard key={module.id} module={module} index={index} />
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[40px] border border-white/10 bg-[#080B12]/80 px-6 py-8 md:px-8 md:py-10">
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${SECTION_META.capability.accent}`} />
          <div className="relative z-10 space-y-7">
            <SectionHeading {...SECTION_META.capability} />

            {viewModel.dataWarnings.length > 0 ? (
              <div className="rounded-[28px] border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-5 py-4 text-sm leading-7 text-white/72">
                <p className="font-medium text-[#FCD34D]">部分内部数据当前不可用</p>
                <div className="mt-2 space-y-1">
                  {viewModel.dataWarnings.map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid gap-4 xl:grid-cols-4">
              {KPI_META.map((item, index) => {
                const Icon = item.icon
                const value = viewModel.kpis[item.id]

                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.45, delay: index * 0.05 }}
                    className="glass-card rounded-[28px] p-5"
                  >
                    <div className="mb-6 flex items-center justify-between gap-4">
                      <div className={`rounded-2xl border border-white/10 bg-black/20 p-3 ${item.tone}`}>
                        <Icon className="size-5" />
                      </div>
                      <span className="text-xs tracking-[0.2em] text-white/42 uppercase">Live Tables</span>
                    </div>
                    <p className="text-sm leading-6 text-white/62">{item.label}</p>
                    <p className="mt-3 text-4xl font-semibold tracking-tight text-white">{item.format(value)}</p>
                    <p className="mt-4 text-sm leading-7 text-white/48">{item.helper}</p>
                  </motion.div>
                )
              })}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
              <motion.div
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.5 }}
                className="glass-card rounded-[32px] p-6"
              >
                <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.25em] text-white/42">TREND</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">响应与处置趋势</h3>
                  </div>
                  <p className="text-sm text-white/54">同图展示近 7 日完成任务量与平均响应时间</p>
                </div>
                <DashboardChart option={buildTrendOption(completionTrend, responseTrend)} height={360} />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.5, delay: 0.05 }}
                className="glass-card rounded-[32px] p-6"
              >
                <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.25em] text-white/42">STATUS</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">任务状态分布</h3>
                  </div>
                </div>
                <DashboardChart option={buildStatusOption(statusSeries)} height={360} />
              </motion.div>
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.86fr_1.14fr]">
              <motion.div
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.5 }}
                className="glass-card rounded-[32px] p-6"
              >
                <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs tracking-[0.25em] text-white/42">THREAT MIX</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">威胁类型分布</h3>
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs text-white/54">
                    只统计可解析结果
                  </span>
                </div>
                <DashboardChart option={buildThreatOption(threatSeries)} height={332} />
                <div className="mt-6 space-y-3">
                  {threatSeries?.items.slice(0, 4).map((item) => (
                    <div key={item.label} className="flex items-center justify-between gap-4 rounded-2xl border border-white/8 bg-white/4 px-4 py-3">
                      <span className="text-sm text-white/68">{item.label}</span>
                      <div className="text-right">
                        <p className="text-sm font-medium text-white">{item.value} 件</p>
                        <p className="text-xs text-white/46">{formatShare(item.share)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>

              <div className="grid gap-6">
                <div className="glass-card rounded-[32px] p-6">
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs tracking-[0.25em] text-white/42">CAPABILITY</p>
                      <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">报告与会诊闭环</h3>
                    </div>
                    <span className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs text-white/54">
                      来自 reports / consultation_invites
                    </span>
                  </div>
                  <div className="grid gap-4 md:grid-cols-3">
                    {viewModel.capabilityMetrics.map((metric, index) => (
                      <CapabilityMetricCard key={metric.id} metric={metric} index={index} />
                    ))}
                  </div>
                </div>

                <div className="rounded-[32px] border border-dashed border-white/14 bg-white/4 p-6">
                  <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-2xl border border-white/10 bg-black/18 p-3 text-[#D4FF12]">
                      <FileCheck2 className="size-5" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-white">本页刻意不展示两类图</p>
                      <p className="text-sm text-white/56">避免在无真实检测结果时绘制伪证据链</p>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {[
                      "证据链流向图：仅在单任务检测完成并进入报告页后生成。",
                      "来源溯查关系图：仅在拿到真实取证与溯源结果后绘制。",
                    ].map((item) => (
                      <div key={item} className="rounded-2xl border border-white/8 bg-black/14 px-4 py-3 text-sm leading-7 text-white/64">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
