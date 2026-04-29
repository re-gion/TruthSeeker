const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export type ExternalVisualType =
  | "arc-progress"
  | "pictorial-bar"
  | "digital-cards"
  | "radial-progress"
  | "funnel"
  | "radar"

export interface ExternalInsightMetric {
  label: string
  value: number
  unit: string
  description?: string
}

export interface PictorialBarItem {
  label: string
  value: number
  unit: string
  symbol: string
  description?: string
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
  pictorialItems?: PictorialBarItem[]
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
  capabilityState: "ready" | "warning" | "error"
  dataWarnings: string[]
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
  data_warnings?: unknown
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
      { label: "生成式 AI 用户规模", value: 2.49, unit: "亿人", description: "截至2024年12月使用生成式AI产品的用户总量" },
      { label: "用户占比", value: 17.7, unit: "%", description: "占整体网民比例" },
      { label: "听说过生成式AI", value: 3.31, unit: "亿人", description: "有认知但未深度使用的潜在用户池" },
      { label: "认知占比", value: 23.5, unit: "%", description: "听说过生成式AI的网民比例" },
      { label: "20-29 岁使用比例", value: 41.5, unit: "%", description: "最活跃年龄段，也是伪造内容的高传播群体" },
      { label: "生成图片/视频", value: 31.0, unit: "%", description: "直接使用AI生成多媒体内容的用户占比，与Deepfake风险直接相关" },
    ],
  },
  {
    id: "audiovisual-ecosystem",
    layer: "risk-foundation",
    moduleTitle: "网络视听传播土壤",
    summary: "Deepfake 的主要扩散场已经和短视频、直播、微短剧平台深度重叠。",
    visualType: "pictorial-bar",
    source: {
      publisher: "中国网络视听节目服务协会",
      publishedAt: "2025-03-26",
      reportTitle: "中国网络视听发展研究报告（2025）",
      url: "https://tradeinservices.mofcom.gov.cn/article/lingyu/whmaoyi/202503/174160.html",
    },
    metrics: [
      { label: "网络视听用户", value: 10.91, unit: "亿人", description: "网民使用率 98.4%" },
      { label: "短视频用户", value: 10.4, unit: "亿人", description: "使用率 93.8%，Deepfake 主要扩散场" },
      { label: "微短剧用户", value: 6.62, unit: "亿人", description: "使用率 59.7%，碎片化内容真伪难辨" },
      { label: "网络直播用户", value: 8.33, unit: "亿人", description: "占网民 75.2%，实时伪造风险高" },
      { label: "市场规模", value: 12226.49, unit: "亿元", description: "2024 年网络视听产业总规模" },
      { label: "同比增长", value: 6.1, unit: "%", description: "产业仍在高速扩张" },
    ],
    pictorialItems: [
      { label: "网络视听用户", value: 10.91, unit: "亿人", symbol: "path://M3,6h18v12h-18z M7,18h10v2h-10z M10,9h4v4h-4z", description: "网民使用率 98.4%" },
      { label: "短视频用户", value: 10.4, unit: "亿人", symbol: "path://M6,3h12a2,2 0 0 1 2,2v14a2,2 0 0 1 -2,2h-12a2,2 0 0 1 -2,-2v-14a2,2 0 0 1 2,-2z M10,8l8,5l-8,5z", description: "使用率 93.8%" },
      { label: "微短剧用户", value: 6.62, unit: "亿人", symbol: "path://M4,5h16v14h-16z M9,10l6,3.5l-6,3.5z M6,2h12v2h-12z", description: "使用率 59.7%" },
      { label: "网络直播用户", value: 8.33, unit: "亿人", symbol: "path://M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2z M12,20c-4.41,0 -8,-3.59 -8,-8s3.59,-8 8,-8 8,3.59 8,8 -3.59,8 -8,8z M11,7h2v6h-2z M11,15h2v2h-2z", description: "占网民 75.2%" },
    ],
  },
  {
    id: "ai-creation-scale",
    layer: "risk-foundation",
    moduleTitle: "AI + 视听创作规模",
    summary: "内容生产门槛断崖式下降，伪造传播进入规模化阶段。",
    visualType: "digital-cards",
    source: {
      publisher: "中国网络视听节目服务协会",
      publishedAt: "2025-03-26",
      reportTitle: "中国网络视听发展研究报告（2025）",
      url: "https://tradeinservices.mofcom.gov.cn/article/lingyu/whmaoyi/202503/174160.html",
    },
    metrics: [
      { label: "短视频创作者账号", value: 16.2, unit: "亿", description: "全国注册创作者账号总量" },
      { label: "每日上线短视频", value: 1.3, unit: "亿条", description: "日均新增内容量，审核压力巨大" },
      { label: "AI 制作图视频网民", value: 33.3, unit: "%", description: "近三分之一网民已使用AI制作图片或视频" },
      { label: "网络音频用户", value: 3.35, unit: "亿人", description: "使用率 30.3%，音频伪造同样值得警惕" },
      { label: "行业从业企业", value: 75.7, unit: "万家", description: "2024 年网络视听行业企业总数" },
      { label: "2024 年新成立企业", value: 12.57, unit: "万家", description: "行业仍在吸引大量新进入者" },
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
      { label: "累计完成备案", value: 302, unit: "款", description: "截至2024年底通过中央备案的生成式AI服务" },
      { label: "2024 年新增备案", value: 238, unit: "款", description: "2024 年单年新增数量，供给侧快速扩张" },
      { label: "地方登记应用", value: 105, unit: "款", description: "通过API调用已备案模型能力的地方登记应用" },
      { label: "注册用户总数", value: 6, unit: "亿+", description: "头部应用注册用户合计超过6亿" },
      { label: "头部应用日活", value: 3000, unit: "万+", description: "头部应用日活突破3000万" },
      { label: "行业从业企业", value: 75.7, unit: "万家", description: "2024 年网络视听行业企业总数" },
    ],
  },
  {
    id: "cyber-law-governance",
    layer: "governance-environment",
    moduleTitle: "网络法治与治理力度",
    summary: "国家与平台治理都在持续加压，内容可信审查已经是现实治理任务。",
    visualType: "funnel",
    source: {
      publisher: "国家互联网信息办公室",
      publishedAt: "2025-04-27",
      reportTitle: "中国网络法治发展报告（2024）",
      url: "https://www.cac.gov.cn/2025-04/27/c_1747548228751408.htm",
    },
    metrics: [
      { label: "依法约谈平台", value: 11159, unit: "家", description: "2024 年全国网信系统约谈平台数量" },
      { label: "关闭违法网站", value: 10946, unit: "家", description: "会同电信主管部门关闭的违法网站" },
      { label: "警告或罚款平台", value: 4046, unit: "家", description: "受到行政处罚的平台数量" },
      { label: "法治宣传阅读量", value: 46.8, unit: "亿次", description: "网上法治宣传累计阅读量" },
      { label: "法治宣传场次", value: 1400, unit: "余场", description: "集中开展各类法治宣传场次" },
      { label: "主题网络报道", value: 3.1, unit: "万篇次", description: "推出的主题网络报道数量" },
    ],
  },
  {
    id: "genai-ecosystem",
    layer: "governance-environment",
    moduleTitle: "生成式 AI 生态扩张",
    summary: "技术生态以指数级速度扩张，模型、开发者、用户三重螺旋增长。",
    visualType: "radar",
    source: {
      publisher: "国家互联网信息办公室",
      publishedAt: "2024-12-01",
      reportTitle: "国家信息化发展报告（2024年）",
      url: "https://www.cac.gov.cn/rootimages/uploadimg/1756111543472978/1756111543472978.pdf",
    },
    metrics: [
      { label: "开源模型数量", value: 2, unit: "万+", description: "魔搭社区汇聚开源模型数量" },
      { label: "衍生模型数量", value: 9, unit: "万+", description: "通义千问开源模型衍生数量" },
      { label: "开发者参与", value: 800, unit: "万", description: "吸引全球开发者参与生态共建" },
      { label: "注册用户总数", value: 6, unit: "亿+", description: "已备案生成式AI服务注册用户合计" },
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

function normalizeDataWarnings(payload: unknown): string[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((item) => {
      if (typeof item === "string") return item.trim()
      const record = readRecord(item)
      return record ? readString(record.message) : ""
    })
    .filter((item): item is string => item.length > 0)
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
    dataWarnings: [],
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

  const dataWarnings = normalizeDataWarnings(payload.data_warnings)

  return {
    generatedAt: readString(payload.generated_at) || fallbackGeneratedAt,
    externalInsights: DASHBOARD_EXTERNAL_INSIGHTS,
    capabilityState: dataWarnings.length > 0 ? "warning" : "ready",
    dataWarnings,
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

async function fetchDashboardAggregate(fetchImpl: FetchLike, token?: string): Promise<DashboardApiResponse | null> {
  try {
    const headers: Record<string, string> = {
      Accept: "application/json",
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    const response = await fetchImpl(`${DEFAULT_API_BASE}/api/v1/dashboard/overview`, {
      headers,
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

export async function getDashboardViewModel(fetchImpl: FetchLike = fetch, token?: string): Promise<DashboardViewModel> {
  const payload = await fetchDashboardAggregate(fetchImpl, token)
  return normalizeDashboardResponse(payload)
}
