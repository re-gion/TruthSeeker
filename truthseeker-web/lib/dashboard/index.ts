const DASHBOARD_TIME_ZONE = "Asia/Shanghai"

export interface ExternalInsightMetric {
  label: string
  value: number
  unit: string
}

export interface ExternalInsightModule {
  id: string
  layer: "risk-foundation" | "governance-environment"
  moduleTitle: string
  source: {
    publisher: string
    publishedAt: string
    reportTitle: string
    url: string
  }
  metrics: ExternalInsightMetric[]
  note: string
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

export interface DashboardDistributionSeries {
  id: string
  title: string
  items: DashboardDistributionItem[]
}

export interface DashboardCapabilityMetric {
  id: string
  label: string
  value: number
  helper: string
}

export interface DashboardViewModel {
  generatedAt: string
  externalInsights: ExternalInsightModule[]
  dataWarnings: string[]
  kpis: DashboardKpis
  trendSeries: DashboardTrendSeries[]
  distributionSeries: DashboardDistributionSeries[]
  capabilityMetrics: DashboardCapabilityMetric[]
}

export interface DashboardTaskRow {
  id: string
  status?: string | null
  input_type?: string | null
  result?: unknown
  verdict?: unknown
  response_ms?: number | string | null
  responseTimeMs?: number | string | null
  duration_ms?: number | string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface DashboardReportRow {
  id?: string | null
  task_id?: string | null
  verdict?: unknown
  generated_at?: string | null
}

export interface DashboardConsultationInviteRow {
  id?: string | null
  task_id?: string | null
  status?: string | null
  state?: string | null
  created_at?: string | null
  expires_at?: string | null
  accepted_at?: string | null
  used_at?: string | null
}

interface DashboardSourceSnapshot {
  tasks: DashboardTaskRow[]
  reports: DashboardReportRow[]
  consultationInvites: DashboardConsultationInviteRow[]
  generatedAt?: string
  dataWarnings?: string[]
}

interface DashboardSourceClient {
  from(table: string): {
    select(columns?: string): PromiseLike<{ data: unknown[] | null; error: unknown | null }>
  }
}

interface ThreatSnapshot {
  taskId: string
  verdictLabel: string
  threatLabel: string
}

interface DashboardTableFetch<T> {
  rows: T[]
  warning?: string
}

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

const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  queued: "待处理",
  analyzing: "分析中",
  processing: "分析中",
  running: "分析中",
  completed: "已完成",
  complete: "已完成",
  failed: "失败",
  error: "失败",
  cancelled: "已取消",
}

const INPUT_TYPE_LABELS: Record<string, string> = {
  video: "视频内容",
  audio: "音频内容",
  image: "图像内容",
  text: "文本内容",
}

export const DASHBOARD_EXTERNAL_INSIGHTS: ExternalInsightModule[] = [
  {
    id: "genai-adoption",
    layer: "risk-foundation",
    moduleTitle: "生成式 AI 普及态势",
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
    note: "风险不再来自少数技术玩家，而是建立在大规模生成式工具普及之上的内容生产能力外溢。",
  },
  {
    id: "audiovisual-ecosystem",
    layer: "risk-foundation",
    moduleTitle: "网络视听传播土壤",
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
    note: "Deepfake 的扩散场域已经和短视频、直播、微短剧的超大规模内容分发网络高度重叠。",
  },
  {
    id: "genai-filing",
    layer: "governance-environment",
    moduleTitle: "生成式 AI 备案进展",
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
    note: "供给侧正在快速扩张，内容生成能力的正规化与规模化同步提升，治理难度也随之上升。",
  },
  {
    id: "cyber-law-governance",
    layer: "governance-environment",
    moduleTitle: "网络法治与治理力度",
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
    note: "这不是孤立技术竞赛，而是置于国家治理和平台治理双重语境中的可信内容审查问题。",
  },
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function readRecord(value: unknown): Record<string, unknown> | null {
  if (isRecord(value)) return value

  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      return isRecord(parsed) ? parsed : null
    } catch {
      return null
    }
  }

  return null
}

function readString(value: unknown): string {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

function normalizeToken(value: unknown): string {
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

function toDate(value: unknown): Date | null {
  const text = readString(value)
  if (!text) return null
  const date = new Date(text)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatZonedDate(date: Date): string {
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: DASHBOARD_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date)
}

function formatZonedDayLabel(date: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: DASHBOARD_TIME_ZONE,
    month: "2-digit",
    day: "2-digit",
  })
    .format(date)
    .replace("/", "-")
}

function isCompletedStatus(status: unknown): boolean {
  return ["completed", "complete", "done", "finished", "resolved", "success", "succeeded"].includes(
    normalizeToken(status),
  )
}

function isExpired(value: unknown, now: Date): boolean {
  const expiresAt = toDate(value)
  return expiresAt ? expiresAt.getTime() <= now.getTime() : false
}

function displayStatus(status: unknown): string {
  const normalized = normalizeToken(status)
  return STATUS_LABELS[normalized] ?? (readString(status) || "未分类")
}

function displayThreatFromInputType(inputType: unknown): string {
  const normalized = normalizeToken(inputType)
  return INPUT_TYPE_LABELS[normalized] ?? "未分类"
}

function readResultCandidate(value: unknown, keys: string[]): string {
  const record = readRecord(value)
  if (!record) return ""

  for (const key of keys) {
    const direct = readString(record[key])
    if (direct) return direct

    const nestedRecord = readRecord(record[key])
    if (!nestedRecord) continue

    const nestedKeys = ["label", "value", "name", "type", "category"]
    for (const nestedKey of nestedKeys) {
      const nested = readString(nestedRecord[nestedKey])
      if (nested) return nested
    }
  }

  return ""
}

function extractVerdictLabel(value: unknown): string {
  return (
    readResultCandidate(value, ["verdict", "verdict_label", "label", "result", "status", "type"]) ||
    readString(value)
  )
}

function extractThreatLabel(value: unknown): string {
  return readResultCandidate(value, ["threat_type", "category", "type", "verdict_cn", "verdict"])
}

export function isHighRiskVerdictAlias(value: unknown): boolean {
  const normalized = normalizeToken(value)
  if (!normalized) return false
  return HIGH_RISK_VERDICT_ALIASES.some((alias) => normalizeToken(alias) === normalized)
}

function calculateTaskResponseMs(task: DashboardTaskRow): number | null {
  if (!isCompletedStatus(task.status)) return null

  const directValue = toNumber(task.response_ms ?? task.responseTimeMs ?? task.duration_ms)
  if (directValue !== null && directValue > 0) {
    return directValue
  }

  const startedAt = toDate(task.started_at)
  const completedAt = toDate(task.completed_at)
  if (!startedAt || !completedAt) return null

  const diff = completedAt.getTime() - startedAt.getTime()
  return diff > 0 ? diff : null
}

export function calculateAverageResponseMs(tasks: DashboardTaskRow[]): number {
  const samples = tasks
    .map((task) => calculateTaskResponseMs(task))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value) && value > 0)

  if (samples.length === 0) return 0

  return Math.round(samples.reduce((sum, value) => sum + value, 0) / samples.length)
}

function buildThreatSnapshots(tasks: DashboardTaskRow[], reports: DashboardReportRow[]): ThreatSnapshot[] {
  const threatByTaskId = new Map<string, ThreatSnapshot>()

  for (const task of tasks) {
    const verdictLabel = extractVerdictLabel(task.result ?? task.verdict)
    const fallbackLabel = displayThreatFromInputType(task.input_type)
    const threatLabel = extractThreatLabel(task.result ?? task.verdict) || fallbackLabel

    threatByTaskId.set(task.id, {
      taskId: task.id,
      verdictLabel,
      threatLabel,
    })
  }

  for (const report of reports) {
    const taskId = readString(report.task_id)
    if (!taskId || threatByTaskId.has(taskId)) continue

    const verdictLabel = extractVerdictLabel(report.verdict)
    threatByTaskId.set(taskId, {
      taskId,
      verdictLabel,
      threatLabel: extractThreatLabel(report.verdict) || verdictLabel || "未分类",
    })
  }

  return [...threatByTaskId.values()]
}

function buildDistributionItems(labels: string[]): DashboardDistributionItem[] {
  const counts = new Map<string, number>()
  const firstSeenOrder = new Map<string, number>()

  labels.forEach((label, index) => {
    const normalized = readString(label) || "未分类"
    if (!firstSeenOrder.has(normalized)) {
      firstSeenOrder.set(normalized, index)
    }
    counts.set(normalized, (counts.get(normalized) ?? 0) + 1)
  })

  const total = [...counts.values()].reduce((sum, value) => sum + value, 0)

  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || (firstSeenOrder.get(left[0]) ?? 0) - (firstSeenOrder.get(right[0]) ?? 0))
    .map(([label, value]) => ({
      label,
      value,
      share: total > 0 ? value / total : 0,
    }))
}

function createRecentDays(generatedAt: string, days = 7): Date[] {
  const anchor = toDate(generatedAt) ?? new Date()
  const result: Date[] = []

  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = new Date(anchor)
    date.setUTCDate(anchor.getUTCDate() - offset)
    result.push(date)
  }

  return result
}

function buildTrendSeries(tasks: DashboardTaskRow[], generatedAt: string): DashboardTrendSeries[] {
  const days = createRecentDays(generatedAt, 7)
  const completedCounts = new Map<string, number>()
  const responseBuckets = new Map<string, { total: number; count: number }>()

  for (const day of days) {
    const key = formatZonedDate(day)
    completedCounts.set(key, 0)
    responseBuckets.set(key, { total: 0, count: 0 })
  }

  for (const task of tasks) {
    const completedAt = toDate(task.completed_at)
    if (completedAt && isCompletedStatus(task.status)) {
      const key = formatZonedDate(completedAt)
      if (completedCounts.has(key)) {
        completedCounts.set(key, (completedCounts.get(key) ?? 0) + 1)
      }
    }

    const responseMs = calculateTaskResponseMs(task)
    if (responseMs === null || !completedAt) continue

    const responseKey = formatZonedDate(completedAt)
    const bucket = responseBuckets.get(responseKey)
    if (!bucket) continue

    bucket.total += responseMs
    bucket.count += 1
  }

  return [
    {
      id: "daily-completions",
      title: "近 7 日完成任务趋势",
      unit: "件",
      points: days.map((day) => {
        const key = formatZonedDate(day)
        return {
          label: formatZonedDayLabel(day),
          value: completedCounts.get(key) ?? 0,
        }
      }),
    },
    {
      id: "response-time",
      title: "近 7 日平均响应时间",
      unit: "ms",
      points: days.map((day) => {
        const key = formatZonedDate(day)
        const bucket = responseBuckets.get(key)
        return {
          label: formatZonedDayLabel(day),
          value: bucket && bucket.count > 0 ? Math.round(bucket.total / bucket.count) : 0,
        }
      }),
    },
  ]
}

function buildDistributionSeries(
  tasks: DashboardTaskRow[],
  reports: DashboardReportRow[],
): DashboardDistributionSeries[] {
  const threatSnapshots = buildThreatSnapshots(tasks, reports)
  const statusLabels = tasks.map((task) => displayStatus(task.status))

  return [
    {
      id: "threat-types",
      title: "威胁类型分布",
      items: buildDistributionItems(threatSnapshots.map((snapshot) => snapshot.threatLabel)),
    },
    {
      id: "task-status",
      title: "任务状态分布",
      items: buildDistributionItems(statusLabels),
    },
  ]
}

function buildCapabilityMetrics(
  reports: DashboardReportRow[],
  consultationInvites: DashboardConsultationInviteRow[],
  now: Date,
): DashboardCapabilityMetric[] {
  const reportTaskIds = new Set(
    reports
      .map((report) => readString(report.task_id))
      .filter(Boolean),
  )

  const consultationTaskIds = new Set(
    consultationInvites
      .filter((invite) => !isExpired(invite.expires_at, now))
      .map((invite) => readString(invite.task_id))
      .filter(Boolean),
  )

  return [
    {
      id: "reports-generated",
      label: "已生成报告数",
      value: reports.length,
      helper: "来自 reports 表，用于证明系统输出的是可归档白盒报告。",
    },
    {
      id: "consultation-triggered",
      label: "会诊触发任务数",
      value: consultationTaskIds.size,
      helper: "来自 consultation_invites，按唯一 task_id 聚合专家会诊触发情况。",
    },
    {
      id: "reports-covered",
      label: "报告覆盖任务数",
      value: reportTaskIds.size,
      helper: "已入库报告关联到的唯一任务数，用于证明检测链路已经闭环。",
    },
  ]
}

function readTableRows<T>(payload: unknown): T[] {
  return Array.isArray(payload) ? (payload.filter(isRecord) as T[]) : []
}

async function selectRows<T>(
  client: DashboardSourceClient,
  table: string,
  columns: string,
  warningMessage: string,
): Promise<DashboardTableFetch<T>> {
  try {
    const { data, error } = await client.from(table).select(columns)
    if (error) {
      return { rows: [], warning: warningMessage }
    }
    return { rows: readTableRows<T>(data) }
  } catch {
    return { rows: [], warning: warningMessage }
  }
}

export function buildDashboardViewModel({
  tasks,
  reports,
  consultationInvites,
  generatedAt,
  dataWarnings = [],
}: DashboardSourceSnapshot): DashboardViewModel {
  const now = toDate(generatedAt) ?? new Date()
  const normalizedGeneratedAt = now.toISOString()
  const shanghaiToday = formatZonedDate(now)
  const threatSnapshots = buildThreatSnapshots(tasks, reports)

  const highRiskTasks = threatSnapshots.filter((snapshot) => isHighRiskVerdictAlias(snapshot.verdictLabel)).length
  const completedToday = tasks.filter((task) => {
    if (!isCompletedStatus(task.status)) return false
    const completedAt = toDate(task.completed_at)
    return completedAt ? formatZonedDate(completedAt) === shanghaiToday : false
  }).length

  return {
    generatedAt: normalizedGeneratedAt,
    externalInsights: DASHBOARD_EXTERNAL_INSIGHTS,
    dataWarnings,
    kpis: {
      totalTasks: tasks.length,
      highRiskTasks,
      averageResponseMs: calculateAverageResponseMs(tasks),
      completedToday,
    },
    trendSeries: buildTrendSeries(tasks, normalizedGeneratedAt),
    distributionSeries: buildDistributionSeries(tasks, reports),
    capabilityMetrics: buildCapabilityMetrics(reports, consultationInvites, now),
  }
}

export async function getDashboardViewModel(client?: DashboardSourceClient): Promise<DashboardViewModel> {
  let activeClient = client

  if (!activeClient) {
    const supabaseModule = await import("../supabase/server")
    activeClient = (await supabaseModule.createClient()) as DashboardSourceClient
  }

  const [tasksResult, reportsResult, consultationInvitesResult] = await Promise.all([
    selectRows<DashboardTaskRow>(
      activeClient,
      "tasks",
      "id,status,input_type,result,verdict,response_ms,duration_ms,started_at,completed_at,created_at,updated_at",
      "tasks 表当前不可用，系统能力层的任务统计已降级为部分展示。",
    ),
    selectRows<DashboardReportRow>(
      activeClient,
      "reports",
      "id,task_id,verdict,generated_at",
      "reports 表当前不可用，报告闭环指标可能不完整。",
    ),
    selectRows<DashboardConsultationInviteRow>(
      activeClient,
      "consultation_invites",
      "id,task_id,status,state,created_at,expires_at,accepted_at,used_at",
      "consultation_invites 表当前不可用，会诊触发指标可能不完整。",
    ),
  ])

  return buildDashboardViewModel({
    tasks: tasksResult.rows,
    reports: reportsResult.rows,
    consultationInvites: consultationInvitesResult.rows,
    generatedAt: new Date().toISOString(),
    dataWarnings: [tasksResult.warning, reportsResult.warning, consultationInvitesResult.warning].filter(
      (warning): warning is string => Boolean(warning),
    ),
  })
}
