const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export type ExternalVisualType = "arc-progress" | "lollipop-rank" | "radial-progress" | "signal-bars"

export interface ExternalInsightMetric {
  label: string
  value: number
  unit: string
}

export interface ExternalInsightModule {
  id: string
  layer: "risk-foundation" | "governance-environment"
  moduleTitle: string
  summary: string
  visualType: ExternalVisualType
  source: {
    publisher: string
    publishedAt: string
    reportTitle: string
    url: string
  }
  metrics: ExternalInsightMetric[]
}

export interface DashboardKpis {
  totalTasks: number
  highRiskTasks: number
  averageResponseMs: number
  completedToday: number
}

export interface DashboardTrendPoint {
  label: string
  value: number
}

export interface DashboardTrendSeries {
  id: string
  title: string
  unit: string
  points: DashboardTrendPoint[]
}

export interface DashboardDistributionItem {
  label: string
  value: number
  share: number
}

export interface DashboardCapabilityMetric {
  id: string
  label: string
  value: number
  helper: string
}

export interface DashboardSankeyNode {
  name: string
}

export interface DashboardSankeyLink {
  source: string
  target: string
  value: number
}

export interface DashboardViewModel {
  generatedAt: string
  externalInsights: ExternalInsightModule[]
  capabilityState: "ready" | "error"
  kpis: DashboardKpis
  trendSeries: DashboardTrendSeries[]
  threatMix: DashboardDistributionItem[]
  statusBreakdown: DashboardDistributionItem[]
  evidenceMix: DashboardDistributionItem[]
  flowSankey: {
    nodes: DashboardSankeyNode[]
    links: DashboardSankeyLink[]
  }
  capabilityMetrics: DashboardCapabilityMetric[]
}

export interface DashboardApiResponse {
  generated_at?: unknown
  kpis?: {
    total_tasks?: unknown
    high_risk_tasks?: unknown
    average_response_ms?: unknown
    completed_today?: unknown
  } | null
  trend_series?: unknown
  threat_mix?: unknown
  status_breakdown?: unknown
  evidence_mix?: unknown
  flow_sankey?: {
    nodes?: unknown
    links?: unknown
  } | null
  capability_metrics?: unknown
}

type FetchLike = typeof fetch

const HIGH_RISK_VERDICT_ALIASES = [
  "fake",
  "forged",
  "deepfake",
  "deep fake",
  "synthetic",
  "manipulated",
  "suspicious",
  "high risk",
  "高风险",
  "伪造",
  "疑似",
  "可疑",
]

export const DASHBOARD_EXTERNAL_INSIGHTS: ExternalInsightModule[] = [
  {
    id: "genai-adoption",
    layer: "risk-foundation",
    moduleTitle: "生成式 AI 普及态势",
    summary: "生成式工具已经进入大规模日常使用阶段，风险门槛显著下降。",
    visualType: "arc-progress",
    source: {
      publisher: "中国互联网络信息中心（CNNIC）",
      publishedAt: "2025-01-17",
      reportTitle: "第55次中国互联网络发展状况统计报告",
      url: "https://www.cnnic.net.cn/n4/2025/0117/c88-11229.html",
    },
    metrics: [
      { label: "生成式 AI 用户规模", value: 2.49, unit: "亿人" },
      { label: "用户占比", value: 17.7, unit: "%" },
      { label: "20-29 岁使用比例", value: 41.5, unit: "%" },
      { label: "回答问题场景占比", value: 77.6, unit: "%" },
    ],
  },
  {
    id: "audiovisual-ecosystem",
    layer: "risk-foundation",
    moduleTitle: "网络视听传播土壤",
    summary: "Deepfake 的主要扩散场已经和短视频、直播、微短剧平台深度重叠。",
    visualType: "lollipop-rank",
    source: {
      publisher: "中国网络视听节目服务协会",
      publishedAt: "2025-03-26",
      reportTitle: "中国网络视听发展研究报告（2025）",
      url: "https://tradeinservices.mofcom.gov.cn/article/lingyu/whmaoyi/202503/174160.html",
    },
    metrics: [
      { label: "网络视听用户", value: 10.91, unit: "亿人" },
      { label: "短视频用户", value: 10.4, unit: "亿人" },
      { label: "微短剧用户", value: 6.62, unit: "亿人" },
      { label: "网络直播用户", value: 8.33, unit: "亿人" },
    ],
  },
  {
    id: "genai-filing",
    layer: "governance-environment",
    moduleTitle: "生成式 AI 备案进展",
    summary: "供给侧快速扩张，生成能力的正规化和规模化同步发生。",
    visualType: "radial-progress",
    source: {
      publisher: "国家互联网信息办公室",
      publishedAt: "2025-01-08",
      reportTitle: "关于发布2024年生成式人工智能服务已备案信息的公告",
      url: "https://www.cac.gov.cn/2025-01/08/c_1738034725920930.htm",
    },
    metrics: [
      { label: "累计完成备案", value: 302, unit: "款" },
      { label: "2024 年新增备案", value: 238, unit: "款" },
      { label: "地方登记应用", value: 105, unit: "款" },
    ],
  },
  {
    id: "cyber-law-governance",
    layer: "governance-environment",
    moduleTitle: "网络法治与治理力度",
    summary: "国家与平台治理都在持续加压，内容可信审查已经是现实治理任务。",
    visualType: "signal-bars",
    source: {
      publisher: "国家互联网信息办公室",
      publishedAt: "2025-04-27",
      reportTitle: "中国网络法治发展报告（2024）",
      url: "https://www.cac.gov.cn/2025-04/27/c_1747548228751408.htm",
    },
    metrics: [
      { label: "依法约谈平台", value: 11159, unit: "家" },
      { label: "警告或罚款平台", value: 4046, unit: "家" },
      { label: "关闭违法网站", value: 10946, unit: "家" },
      { label: "法治宣传阅读量", value: 46.8, unit: "亿次" },
    ],
  },
]

function readString(value: unknown) {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

function normalizeToken(value: unknown) {
  return readString(value).toLowerCase().replace(/[\s_-]+/g, "")
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null
}

function normalizeTrendSeries(payload: unknown): DashboardTrendSeries[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((series) => {
      if (!isRecord(series)) return null

      return {
        id: readString(series.id),
        title: readString(series.title),
        unit: readString(series.unit),
        points: Array.isArray(series.points)
          ? series.points
              .map((point) => {
                const record = readRecord(point)
                if (!record) return null
                return {
                  label: readString(record.label),
                  value: Math.round(toNumber(record.value) ?? 0),
                }
              })
              .filter((point): point is DashboardTrendPoint => Boolean(point))
          : [],
      }
    })
    .filter((series): series is DashboardTrendSeries => series !== null && series.id.length > 0)
}

function normalizeDistributionItems(payload: unknown): DashboardDistributionItem[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((item) => {
      const record = readRecord(item)
      if (!record) return null

      return {
        label: readString(record.label) || "未分类",
        value: Math.round(toNumber(record.value) ?? 0),
        share: toNumber(record.share) ?? 0,
      }
    })
    .filter((item): item is DashboardDistributionItem => Boolean(item))
}

function normalizeCapabilityMetrics(payload: unknown): DashboardCapabilityMetric[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((metric) => {
      const record = readRecord(metric)
      if (!record) return null

      return {
        id: readString(record.id),
        label: readString(record.label),
        value: Math.round(toNumber(record.value) ?? 0),
        helper: readString(record.helper),
      }
    })
    .filter((metric): metric is DashboardCapabilityMetric => metric !== null && metric.id.length > 0)
}

function normalizeSankey(payload: DashboardApiResponse["flow_sankey"]): DashboardViewModel["flowSankey"] {
  const nodes = Array.isArray(payload?.nodes)
    ? payload.nodes
        .map((node) => {
          const record = readRecord(node)
          if (!record) return null
          return { name: readString(record.name) }
        })
        .filter((node): node is DashboardSankeyNode => node !== null && node.name.length > 0)
    : []

  const links = Array.isArray(payload?.links)
    ? payload.links
        .map((link) => {
          const record = readRecord(link)
          if (!record) return null
          return {
            source: readString(record.source),
            target: readString(record.target),
            value: Math.max(0, Math.round(toNumber(record.value) ?? 0)),
          }
        })
        .filter(
          (link): link is DashboardSankeyLink =>
            link !== null && link.source.length > 0 && link.target.length > 0 && link.value >= 0,
        )
    : []

  return { nodes, links }
}

export function isHighRiskVerdictAlias(value: unknown): boolean {
  const normalized = normalizeToken(value)
  if (!normalized) return false
  return HIGH_RISK_VERDICT_ALIASES.some((alias) => normalizeToken(alias) === normalized)
}

export function createFallbackDashboardViewModel(
  generatedAt = new Date().toISOString(),
  capabilityState: DashboardViewModel["capabilityState"] = "error",
): DashboardViewModel {
  return {
    generatedAt,
    externalInsights: DASHBOARD_EXTERNAL_INSIGHTS,
    capabilityState,
    kpis: {
      totalTasks: 0,
      highRiskTasks: 0,
      averageResponseMs: 0,
      completedToday: 0,
    },
    trendSeries: [],
    threatMix: [],
    statusBreakdown: [],
    evidenceMix: [],
    flowSankey: {
      nodes: [],
      links: [],
    },
    capabilityMetrics: [
      { id: "reports-generated", label: "已生成报告", value: 0, helper: "已入库的鉴定报告总量" },
      { id: "consultation-triggered", label: "会诊触发任务", value: 0, helper: "触发专家会诊的唯一任务数" },
      { id: "reports-covered", label: "报告覆盖任务", value: 0, helper: "已形成报告闭环的唯一任务数" },
    ],
  }
}

export function normalizeDashboardResponse(
  payload: DashboardApiResponse | null | undefined,
  fallbackGeneratedAt = new Date().toISOString(),
): DashboardViewModel {
  if (!payload) {
    return createFallbackDashboardViewModel(fallbackGeneratedAt, "error")
  }

  return {
    generatedAt: readString(payload.generated_at) || fallbackGeneratedAt,
    externalInsights: DASHBOARD_EXTERNAL_INSIGHTS,
    capabilityState: "ready",
    kpis: {
      totalTasks: Math.round(toNumber(payload.kpis?.total_tasks) ?? 0),
      highRiskTasks: Math.round(toNumber(payload.kpis?.high_risk_tasks) ?? 0),
      averageResponseMs: Math.round(toNumber(payload.kpis?.average_response_ms) ?? 0),
      completedToday: Math.round(toNumber(payload.kpis?.completed_today) ?? 0),
    },
    trendSeries: normalizeTrendSeries(payload.trend_series),
    threatMix: normalizeDistributionItems(payload.threat_mix),
    statusBreakdown: normalizeDistributionItems(payload.status_breakdown),
    evidenceMix: normalizeDistributionItems(payload.evidence_mix),
    flowSankey: normalizeSankey(payload.flow_sankey),
    capabilityMetrics: normalizeCapabilityMetrics(payload.capability_metrics),
  }
}

async function fetchDashboardAggregate(fetchImpl: FetchLike): Promise<DashboardApiResponse | null> {
  try {
    const response = await fetchImpl(`${DEFAULT_API_BASE}/api/v1/dashboard/overview`, {
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    })

    if (!response.ok) {
      return null
    }

    return (await response.json()) as DashboardApiResponse
  } catch {
    return null
  }
}

export async function getDashboardViewModel(fetchImpl: FetchLike = fetch): Promise<DashboardViewModel> {
  const payload = await fetchDashboardAggregate(fetchImpl)
  return normalizeDashboardResponse(payload)
}
