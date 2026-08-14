/**
 * 分享报告页目录（TOC）构建工具。
 *
 * 报告 Markdown 由后端 `report_generator.generate_markdown_report` 生成，
 * 层级固定为 `#` 标题 + `##` 主章节 + `###` 小节。目录只收录 `##`/`###`，
 * 并把页面级区块（裁决卡片、最终裁决报告、详细分析报告）作为同深度锚点前置。
 */

export const REPORT_SECTION_IDS = {
  verdict: "report-section-verdict",
  summary: "report-section-summary",
  detail: "report-section-detail",
} as const

export type ReportTocEntryKind = "page" | "heading"

export interface ReportTocEntry {
  id: string
  text: string
  /** 0 = 主章节（含页面级区块），1 = 小节 */
  depth: 0 | 1
  kind: ReportTocEntryKind
}

export interface HeadingIdIndex {
  /** Markdown 源码行号（1 起）→ 锚点 id */
  byLine: Map<number, string>
}

const HEADING_PATTERN = /^(#{2,3})\s+(.+?)\s*$/
const FENCE_PATTERN = /^\s*(```|~~~)/

/** 去掉 Markdown 行内标记，得到用于展示与锚点计算的纯文本 */
export function normalizeHeadingText(raw: string) {
  return raw
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/\s+/g, " ")
    .trim()
}

/**
 * 生成锚点 slug。保留中日韩文字与英数，其余（emoji、标点、箭头）折叠成连字符。
 * 中文标题不能靠 ASCII slug，否则同一份报告里大量章节会退化成空串。
 */
export function slugifyHeadingText(raw: string) {
  return normalizeHeadingText(raw)
    .toLowerCase()
    .replace(/[^\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}a-z0-9]+/gu, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "")
}

interface RawHeading {
  level: 2 | 3
  text: string
  /** Markdown 源码行号，1 起 */
  line: number
}

/** 扫描 Markdown，跳过围栏代码块，取出 h2/h3 */
function collectHeadings(markdown: string): RawHeading[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n")
  const headings: RawHeading[] = []
  let fence: string | null = null

  lines.forEach((line, index) => {
    const fenceMatch = FENCE_PATTERN.exec(line)
    if (fenceMatch) {
      const marker = fenceMatch[1]
      if (!fence) {
        fence = marker
      } else if (fence === marker) {
        fence = null
      }
      return
    }
    if (fence) return

    const match = HEADING_PATTERN.exec(line)
    if (!match) return

    const text = normalizeHeadingText(match[2])
    if (!text) return

    headings.push({
      level: match[1].length === 2 ? 2 : 3,
      text,
      line: index + 1,
    })
  })

  return headings
}

/** 同名标题按出现顺序追加 `-2`、`-3`…，保证锚点唯一 */
function createIdAllocator() {
  // 预占页面级区块 id，避免极端情况下标题 slug 撞上它们
  const used = new Map<string, number>(
    Object.values(REPORT_SECTION_IDS).map((id) => [id, 1] as const),
  )

  return (text: string, fallbackSeed: number) => {
    const slug = slugifyHeadingText(text)
    const base = slug ? `report-${slug}` : `report-section-${fallbackSeed}`
    const seen = used.get(base) ?? 0
    used.set(base, seen + 1)
    return seen === 0 ? base : `${base}-${seen + 1}`
  }
}

export function buildReportToc({
  markdown,
  hasSummary,
}: {
  markdown: string
  hasSummary: boolean
}): ReportTocEntry[] {
  const entries: ReportTocEntry[] = [
    { id: REPORT_SECTION_IDS.verdict, text: "裁决结论", depth: 0, kind: "page" },
  ]

  if (hasSummary) {
    entries.push({ id: REPORT_SECTION_IDS.summary, text: "最终裁决报告", depth: 0, kind: "page" })
  }

  const headings = collectHeadings(markdown)
  if (!headings.length) return entries

  entries.push({ id: REPORT_SECTION_IDS.detail, text: "详细分析报告", depth: 0, kind: "page" })

  const allocateId = createIdAllocator()
  headings.forEach((heading, index) => {
    entries.push({
      id: allocateId(heading.text, index + 1),
      text: heading.text,
      depth: heading.level === 2 ? 0 : 1,
      kind: "heading",
    })
  })

  return entries
}

/**
 * 渲染期查表：把 Markdown 标题映射到目录使用的同一批 id。
 * 只按源码行号命中（react-markdown 会在节点上带 position），不做标题文本兜底——
 * 列表项内被引用的同名标题会抢占顶层章节的锚点，产生重复 DOM id。
 */
export function buildHeadingIdIndex(markdown: string): HeadingIdIndex {
  const allocateId = createIdAllocator()
  const byLine = new Map<number, string>()

  collectHeadings(markdown).forEach((heading, index) => {
    byLine.set(heading.line, allocateId(heading.text, index + 1))
  })

  return { byLine }
}
