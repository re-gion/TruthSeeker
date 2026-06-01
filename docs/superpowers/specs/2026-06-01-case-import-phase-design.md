# 公开案例导入阶段设计文档

**日期**: 2026-06-01  
**状态**: 待实现  
**涉及模块**: `truthseeker-api/app/services/case_library.py`, `truthseeker-api/app/api/v1/detect.py`, `truthseeker-web/hooks/useAgentStream.ts`, `truthseeker-web/components/detect/DetectConsole.tsx`

---

## 一、背景与问题

当前公开案例库存在三个问题：

1. **标题直接用检材文件名**：`build_case_library_entry` 中 `title = task.title`，即原始文件名，不具备概括性。
2. **摘要是技术报告原文**：`_summary_from_report` 截取 `analysis_summary` 字段（最多 360 字），是面向内部的技术分析文本，不适合公开展示，且未按 Markdown 渲染。
3. **缺少导入阶段**：研判完成后 `ensure_case_library_entry` 同步调用、无进度反馈，用户不知道 LLM 正在生成标题/摘要；三个报告按钮（MD/PDF/分享）在导入完成前就已可点击，逻辑顺序错误。

---

## 二、目标

- 用 Kimi K2.5 自动生成概括性案例标题（10-20 字）和面向公众的案例摘要（50-120 字）
- 在研判完成后、报告按钮开放前，插入"公开案例导入"阶段，通过 SSE 推送进度
- 三个报告按钮（MD/PDF/分享）在导入阶段结束后才解锁（无论成功/跳过/失败）

---

## 三、流程设计

```
研判完成
  → SSE: final_verdict
  → SSE: complete
  → 后端判断是否需要导入（wants_public_case）
      ├── 是 → SSE: case_import_start
      │         → 调用 Kimi K2.5 生成标题+摘要（async，约 5-15s）
      │         → 写入 case_library_entries
      │         → SSE: case_import_created / case_import_duplicate / case_import_error
      └── 否 → SSE: case_import_skipped（reason: not_requested）

前端：
  收到 complete → 证据板追加"公开案例导入中"步骤，报告按钮保持禁用
  收到 case_import_* → 证据板更新最终状态，报告按钮解锁
```

---

## 四、后端改动

### 4.1 `case_library.py` — LLM 生成标题和摘要

新增异步函数：

```python
async def generate_case_title_and_summary(
    task: dict,
    report: dict,
    llm,
) -> tuple[str, str]:
```

**Prompt 输入**：
- 裁决结论（verdict）、置信度（confidence_overall）
- 检材类型（media_category）、难度（difficulty）
- 检材文件名列表（脱敏后，最多 5 个）
- 案例提示词（case_prompt，最多 200 字）
- 关键证据摘要（key_evidence，最多 3 条）

**输出格式**（JSON）：
```json
{
  "title": "政府通知图文伪造案",
  "summary": "一份声称来自政府部门的通知文件，经多模态鉴伪分析，图片存在明显 AI 生成痕迹，文字内容与官方格式不符，综合置信度 92.3%，判定为伪造。"
}
```

**Fallback**（LLM 失败时）：
- title: `f"{verdict_label}·{category_label}·{difficulty}难度案例"`
- summary: `f"本案为{category_label}类型检材，研判结论为{verdict_label}，综合置信度 {confidence:.1%}。"`

**脱敏**：生成结果经 `redact_public_text` 处理后写入。

### 4.2 `case_library.py` — 改造 `ensure_case_library_entry` 为 async

将 `ensure_case_library_entry` 改为 `async def`，内部调用 `await generate_case_title_and_summary(...)`，替换原有的 `title` 和 `summary` 生成逻辑。

`detect.py` 和 `share.py` 均改为 `await ensure_case_library_entry(...)`（两者路由函数都是 `async def`，直接 await 即可）。

**注意**：`share.py` 中的 `ensure_case_library_entry` 调用**直接删除**。分享报告只负责生成 `share_token` 返回链接，与入库完全无关。入库已在研判完成后自动完成，分享时无需重复检测或入库。

### 4.3 `detect.py` — 在 `complete` 后推送导入进度

在 `final_verdict_data` 存在时，推送 `complete` 后继续：

```python
# 已有逻辑
await queue.put(_sse({"type": "complete", "task_id": task_id, ...}))

# 新增：案例导入阶段
task_meta = _fetch_task(task_id) or task  # 获取最新 task（含 share_to_casebase 标志）
if wants_public_case(task_meta):
    await queue.put(_sse({"type": "case_import_start", "task_id": task_id}))
    try:
        report_row = _fetch_or_build_report(task_id, final_verdict_data)
        result = await ensure_case_library_entry_async(supabase, task_meta, report_row)
        status = result.get("status", "error")  # created / duplicate / error
        await queue.put(_sse({"type": f"case_import_{status}", "task_id": task_id}))
    except Exception as exc:
        logger.error("Case import failed for %s: %s", task_id, exc)
        await queue.put(_sse({"type": "case_import_error", "task_id": task_id}))
else:
    await queue.put(_sse({"type": "case_import_skipped", "task_id": task_id, "reason": "not_requested"}))
```

### 4.4 新增 SSE 事件类型

| 事件 | 含义 | 前端行为 |
|------|------|----------|
| `case_import_start` | 开始导入，LLM 生成中 | 证据板显示"导入中" |
| `case_import_created` | 成功入库 | 证据板显示"已入库"，解锁按钮 |
| `case_import_duplicate` | 重复，跳过 | 证据板显示"已存在"，解锁按钮 |
| `case_import_skipped` | 未勾选公开，跳过 | 证据板显示"跳过"，解锁按钮 |
| `case_import_error` | 导入失败 | 证据板显示"导入失败"，解锁按钮 |

---

## 五、前端改动

### 5.1 `useAgentStream.ts` — 新增事件类型和状态

**AgentEvent 联合类型新增**：
```typescript
| { type: "case_import_start"; task_id: string }
| { type: "case_import_created"; task_id: string }
| { type: "case_import_duplicate"; task_id: string }
| { type: "case_import_skipped"; task_id: string; reason?: string }
| { type: "case_import_error"; task_id: string }
```

**新增状态**：
```typescript
type CaseImportStatus = "idle" | "importing" | "created" | "duplicate" | "skipped" | "error"
const [caseImportStatus, setCaseImportStatus] = useState<CaseImportStatus>("idle")
```

**事件处理**：
```typescript
} else if (event.type === "case_import_start") {
    setCaseImportStatus("importing")
} else if (event.type === "case_import_created") {
    setCaseImportStatus("created")
} else if (event.type === "case_import_duplicate") {
    setCaseImportStatus("duplicate")
} else if (event.type === "case_import_skipped") {
    setCaseImportStatus("skipped")
} else if (event.type === "case_import_error") {
    setCaseImportStatus("error")
}
```

**新增派生状态**：
```typescript
// 报告按钮可用条件：研判完成 且 导入阶段已结束（任意终态）
const isReportReady = isComplete && caseImportStatus !== "idle" && caseImportStatus !== "importing"
```

`isReportReady` 通过 hook 返回值暴露给 `DetectConsole`。

**历史恢复**（`mapHistoryToStreamState`）：已完成的任务 `caseImportStatus` 默认为 `"skipped"`（不重新触发导入），`isReportReady` 直接为 `true`。

### 5.2 `DetectConsole.tsx` — 证据板新增阶段 + 按钮锁定

**`buildSystemWorkflow` 新增逻辑**：

在 `isComplete` 后，根据 `caseImportStatus` 追加步骤：

```typescript
if (isComplete) {
    if (caseImportStatus === "importing") {
        steps.push({
            key: "case-import-running",
            title: "公开案例导入中",
            detail: "AI 正在生成案例标题与摘要",
            tone: "running",
        })
    } else if (caseImportStatus === "created") {
        steps.push({
            key: "case-import-done",
            title: "案例已入库",
            detail: "已发布至公开案例库",
            tone: "complete",
        })
    } else if (caseImportStatus === "duplicate") {
        steps.push({
            key: "case-import-dup",
            title: "案例已存在",
            detail: "相同检材已在案例库中",
            tone: "complete",
        })
    } else if (caseImportStatus === "skipped") {
        steps.push({
            key: "case-import-skip",
            title: "案例导入跳过",
            detail: "未勾选公开至案例库",
            tone: "complete",
        })
    } else if (caseImportStatus === "error") {
        steps.push({
            key: "case-import-err",
            title: "案例导入失败",
            detail: "不影响报告查看",
            tone: "complete",
        })
    }
}
```

**报告按钮锁定**：

三个按钮（MD 报告、PDF 报告、分享报告）的渲染条件从 `isComplete` 改为 `isReportReady`：

```tsx
// 改前
{isComplete && <button>MD 报告</button>}
// 改后
{isReportReady && <button>MD 报告</button>}
```

---

## 六、兼容性

- `share.py` 中删除 `ensure_case_library_entry` 调用，分享只负责生成 `share_token`，与入库完全解耦
- `ensure_case_library_entry` 改为 async，`detect.py` 和 `share.py` 路由函数均为 `async def`，直接 `await` 调用，无嵌套事件循环问题
- 已完成任务（从历史恢复）：`caseImportStatus` 默认 `skipped`，`isReportReady` 直接为 `true`，不影响已完成任务的报告查看
- 未勾选公开的任务：`case_import_skipped` 立即推送，按钮立即解锁，用户无感知延迟

---

## 七、错误处理

- LLM 调用超时或失败 → fallback 规则生成标题/摘要 → 正常入库 → 推送 `case_import_created`
- 数据库写入失败 → 推送 `case_import_error` → 按钮解锁，不阻断报告查看
- SSE 连接中断 → 前端重连后从历史恢复，`isReportReady` 为 `true`

---

## 八、不在本次范围内

- 公开案例库列表页的展示优化
- 案例摘要的人工编辑功能
- 导入失败的重试机制
