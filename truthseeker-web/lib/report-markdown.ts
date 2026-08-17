function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function renderInline(value: string) {
  return escapeHtml(value)
    .replace(/`([^`]+?)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
}

function isTableLine(line: string) {
  return /^\s*\|.*\|\s*$/.test(line)
}

function isTableSeparator(line: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)
}

function splitTableCells(line: string) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "")
  return trimmed.split("|").map((cell) => cell.trim())
}

function renderTable(lines: string[]) {
  const header = splitTableCells(lines[0])
  const bodyRows = lines.slice(2).map(splitTableCells)

  return [
    "<table>",
    "<thead><tr>",
    ...header.map((cell) => `<th>${renderInline(cell)}</th>`),
    "</tr></thead>",
    "<tbody>",
    ...bodyRows.flatMap((row) => [
      "<tr>",
      ...row.map((cell) => `<td>${renderInline(cell)}</td>`),
      "</tr>",
    ]),
    "</tbody>",
    "</table>",
  ].join("")
}

const FENCE_MARKER_RE = /^(`{3,}|~{3,})\s*(.*)$/
const FENCE_HEADING_RE = /^#{1,6}\s/

/**
 * 补齐未闭合的代码围栏，防止渲染器把后文全部吞进一个代码块。
 *
 * LLM 报告可能输出未闭合的 ```/~~~ 围栏（如 mermaid/ASCII 图谱），后端字段
 * 截断也可能切掉闭合围栏。围栏未闭合时 react-markdown 会把后续整段内容渲染
 * 成一个代码块（报告页表现为荧光绿样式越界）。修复策略：围栏开着却遇到
 * Markdown 标题时，说明模型已离开代码块开始写新小节，先在标题前补闭合围栏；
 * 到文末仍未闭合（典型为截断切掉闭合围栏）则在文末补齐。
 * 与后端 report_generator._balance_code_fences 保持同一规则。
 */
export function balanceCodeFences(markdown: string): string {
  const result: string[] = []
  let openMarker: string | null = null
  for (const line of markdown.split("\n")) {
    const stripped = line.replace(/^\s+/, "")
    const indent = line.length - stripped.length
    if (openMarker !== null && indent <= 3 && FENCE_HEADING_RE.test(stripped)) {
      result.push(openMarker[0].repeat(Math.max(3, openMarker.length)))
      openMarker = null
    }
    result.push(line)
    if (indent > 3) continue // CommonMark：缩进超过 3 格的围栏不生效
    const match = FENCE_MARKER_RE.exec(stripped)
    if (!match) continue
    const [, marker, rest] = match
    if (openMarker === null) {
      openMarker = marker
    } else if (
      marker[0] === openMarker[0]
      && marker.length >= openMarker.length
      && rest.trim() === "" // 闭合围栏不能带信息串
    ) {
      openMarker = null
    }
  }
  if (openMarker !== null) {
    result.push(openMarker[0].repeat(Math.max(3, openMarker.length)))
  }
  return result.join("\n")
}

export function renderReportMarkdown(markdown: string) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n")
  const html: string[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    if (isTableLine(line) && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const tableLines = [line, lines[index + 1]]
      index += 2
      while (index < lines.length && isTableLine(lines[index])) {
        tableLines.push(lines[index])
        index += 1
      }
      html.push(renderTable(tableLines))
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed)
    if (heading) {
      const level = heading[1].length
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = []
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(`<li>${renderInline(lines[index].trim().replace(/^[-*]\s+/, ""))}</li>`)
        index += 1
      }
      html.push(`<ul>${items.join("")}</ul>`)
      continue
    }

    const paragraph: string[] = []
    while (
      index < lines.length
      && lines[index].trim()
      && !/^(#{1,3})\s+/.test(lines[index].trim())
      && !/^[-*]\s+/.test(lines[index].trim())
      && !(isTableLine(lines[index]) && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
    ) {
      paragraph.push(renderInline(lines[index].trim()))
      index += 1
    }
    html.push(`<p>${paragraph.join("<br />")}</p>`)
  }

  return html.join("")
}
