# Consultation Bugs Fix Implementation Plan

> **状态：历史执行计划。** 本文件保留旧 `consultation` 流程的修复记录；当前新功能使用 `collaboration_*`，旧命名仅作兼容，当前事实以源码和 `docs/APP_FLOW.md` 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复四个专家会诊相关 bug：摘要二次发送、裁决报告不显示、专家侧提前报告已生成、专家侧案例导入配置不同步。

**Architecture:** 前端改动集中在两个文件：`useAgentStream.ts`（`mapAgentHistoryToStreamState` 的 `isComplete`/`caseImportStatus` 重建逻辑）和 `ExpertPanel.tsx`（摘要消息过滤渲染）。不涉及后端改动，不引入新 API。

**Tech Stack:** TypeScript, React 19, Vitest

---

## 文件改动范围

| 文件 | 类型 | 改动说明 |
|------|------|----------|
| `truthseeker-web/hooks/useAgentStream.ts` | Modify | 新增 `deriveCaseImportStatusFromHistory`；修改 `mapAgentHistoryToStreamState` 第 556-557 行的 `isComplete` 和 `caseImportStatus` 计算逻辑 |
| `truthseeker-web/hooks/useAgentStream.test.ts` | Modify | 补充 4 个新测试用例覆盖修复场景 |
| `truthseeker-web/lib/consultation-messages.ts` | Modify | `ConsultationComment` 加 `sessionId` 字段；`normalizeConsultationMessage` 读取 `session_id`；新增 `filterDisplayComments` |
| `truthseeker-web/lib/consultation-messages.test.ts` | Modify | 补充摘要过滤测试用例 |
| `truthseeker-web/components/collaboration/ExpertPanel.tsx` | Modify | `comments.map` 渲染前先调用 `filterDisplayComments`；`summary` 消息渲染特殊草稿样式 |

---

## Task 1：修复 `mapAgentHistoryToStreamState` — `caseImportStatus` 重建

**Files:**
- Modify: `truthseeker-web/hooks/useAgentStream.ts:556-557`
- Test: `truthseeker-web/hooks/useAgentStream.test.ts`

- [ ] **Step 1: 在 `useAgentStream.test.ts` 末尾加一个失败测试**

找到文件末尾 `})` 闭合前，在 `mapAgentHistoryToStreamState` describe 块内添加：

```typescript
  it("derives caseImportStatus from audit_logs instead of hardcoding skipped", () => {
    const mappedCreated = mapAgentHistoryToStreamState({
      task: { status: "completed" },
      audit_logs: [
        { action: "case_import_created", agent: "system", created_at: "2026-06-02T10:00:00.000Z", metadata: { import_status: "created" } },
      ],
    })
    expect(mappedCreated.caseImportStatus).toBe("created")

    const mappedDuplicate = mapAgentHistoryToStreamState({
      task: { status: "completed" },
      audit_logs: [
        { action: "case_import_duplicate", agent: "system", created_at: "2026-06-02T10:00:00.000Z" },
      ],
    })
    expect(mappedDuplicate.caseImportStatus).toBe("duplicate")

    const mappedNoAudit = mapAgentHistoryToStreamState({
      task: { status: "completed" },
      audit_logs: [],
    })
    expect(mappedNoAudit.caseImportStatus).toBe("skipped")

    const mappedRunning = mapAgentHistoryToStreamState({
      task: { status: "running" },
      audit_logs: [],
    })
    expect(mappedRunning.caseImportStatus).toBe("idle")
  })
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd truthseeker-web && npx vitest run hooks/useAgentStream.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：`FAIL` — "expected 'skipped' to be 'created'"

- [ ] **Step 3: 在 `useAgentStream.ts` 的 `isConsultationWaiting` 函数之前（约第 487 行后），加入新的辅助函数**

```typescript
function deriveCaseImportStatusFromHistory(
    auditLogs: unknown[],
    taskStatus: string,
): CaseImportStatus {
    const IMPORT_ACTIONS: Record<string, CaseImportStatus> = {
        case_import_created: "created",
        case_import_duplicate: "duplicate",
        case_import_skipped: "skipped",
        case_import_error: "error",
    }
    for (const log of auditLogs) {
        if (!isObject(log)) continue
        const action = readString(log.action)
        if (!action) continue
        if (action in IMPORT_ACTIONS) return IMPORT_ACTIONS[action]
    }
    return taskStatus === "completed" ? "skipped" : "idle"
}
```

- [ ] **Step 4: 修改 `mapAgentHistoryToStreamState` 第 557 行**

将：
```typescript
        caseImportStatus: status === "completed" || Boolean(finalVerdict) ? "skipped" : "idle",
```
改为：
```typescript
        caseImportStatus: deriveCaseImportStatusFromHistory(history.audit_logs ?? [], status),
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd truthseeker-web && npx vitest run hooks/useAgentStream.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：全部 `PASS`

- [ ] **Step 6: 提交**

```bash
git add truthseeker-web/hooks/useAgentStream.ts truthseeker-web/hooks/useAgentStream.test.ts
git commit -m "fix(stream): derive caseImportStatus from audit_logs instead of hardcoding"
```

---

## Task 2：修复 `mapAgentHistoryToStreamState` — `isComplete` 不应在会诊等待时为 true

**Files:**
- Modify: `truthseeker-web/hooks/useAgentStream.ts:556`
- Test: `truthseeker-web/hooks/useAgentStream.test.ts`

- [ ] **Step 1: 添加失败测试**

在 `useAgentStream.test.ts` 的 `mapAgentHistoryToStreamState` describe 块末尾添加：

```typescript
  it("isComplete is false when task is waiting for consultation even if finalVerdict exists", () => {
    const mapped = mapAgentHistoryToStreamState({
      task: { status: "waiting_consultation" },
      analysis_states: [
        {
          round_number: 1,
          result_snapshot: {
            final_verdict: { verdict: "suspicious", confidence: 0.8 },
          },
        },
      ],
    })
    expect(mapped.isComplete).toBe(false)
    expect(mapped.isWaitingConsultation).toBe(true)
  })

  it("isComplete is true for completed task with finalVerdict from report", () => {
    const mapped = mapAgentHistoryToStreamState({
      task: { status: "completed" },
      report: { verdict_payload: { verdict: "authentic", confidence: 0.9 } },
    })
    expect(mapped.isComplete).toBe(true)
    expect(mapped.caseImportStatus).not.toBe("idle")
  })
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd truthseeker-web && npx vitest run hooks/useAgentStream.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：`FAIL` — "expected true to be false"

- [ ] **Step 3: 修改 `mapAgentHistoryToStreamState` 第 556 行**

将：
```typescript
        isComplete: status === "completed" || Boolean(finalVerdict),
```
改为：
```typescript
        isComplete: (status === "completed" || Boolean(finalVerdict)) && !isConsultationWaiting(status, consultationStatus),
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd truthseeker-web && npx vitest run hooks/useAgentStream.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：全部 `PASS`

- [ ] **Step 5: 提交**

```bash
git add truthseeker-web/hooks/useAgentStream.ts truthseeker-web/hooks/useAgentStream.test.ts
git commit -m "fix(stream): isComplete must be false while consultation is active"
```

---

## Task 3：修复 `filterDisplayComments` — 摘要消息去重渲染

**Files:**
- Modify: `truthseeker-web/lib/consultation-messages.ts`
- Modify: `truthseeker-web/lib/consultation-messages.test.ts`

**背景：** `close` 接口立刻插入 `message_type=summary` 消息，用户确认后再插入 `message_type=summary_confirmed`，导致聊天区出现两条摘要。选择的方案（B）是：两条消息都存在，但当 `summary_confirmed` 到达后，过滤掉之前同类 `summary` 消息，只显示 `summary_confirmed`。

- [ ] **Step 1: 在 `consultation-messages.test.ts` 中添加失败测试**

在文件末尾 `})` 之前追加：

```typescript
  it("filterDisplayComments hides summary draft once summary_confirmed arrives", () => {
    const { filterDisplayComments } = require("./consultation-messages")

    const draftMsg = {
      id: "msg-1",
      authorId: "commander",
      role: "commander" as const,
      text: "草稿摘要",
      timestamp: "2026-06-02T10:00:00.000Z",
      messageType: "summary",
    }
    const confirmedMsg = {
      id: "msg-2",
      authorId: "commander",
      role: "commander" as const,
      text: "确认后摘要",
      timestamp: "2026-06-02T10:01:00.000Z",
      messageType: "summary_confirmed",
    }

    // 仅草稿时两者都显示（草稿会显示为特殊样式）
    expect(filterDisplayComments([draftMsg])).toHaveLength(1)
    // confirmed 到达后，草稿被过滤
    const filtered = filterDisplayComments([draftMsg, confirmedMsg])
    expect(filtered).toHaveLength(1)
    expect(filtered[0].messageType).toBe("summary_confirmed")
  })
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd truthseeker-web && npx vitest run lib/consultation-messages.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：`FAIL` — "filterDisplayComments is not a function"

- [ ] **Step 3: 在 `consultation-messages.ts` 的 `ConsultationComment` 接口加 `sessionId` 字段**

在第 10 行 `messageType?: string` 之后加：
```typescript
    sessionId?: string
```

- [ ] **Step 4: 在 `normalizeConsultationMessage` 函数（第 45 行）的返回对象中加 sessionId**

```typescript
export function normalizeConsultationMessage(item: Record<string, unknown>): ConsultationComment {
    return {
        id: readString(item.id) ?? Math.random().toString(36).substring(7),
        clientMessageId: readClientMessageId(item),
        authorId: readString(item.authorId) ?? readString(item.expert_name) ?? "expert",
        role: normalizeRole(item.role),
        text: readString(item.text) ?? readString(item.message) ?? "",
        timestamp: readString(item.timestamp) ?? readString(item.created_at) ?? new Date().toISOString(),
        messageType: readString(item.messageType) ?? readString(item.message_type),
        sessionId: readString(item.sessionId) ?? readString(item.session_id),
        anchorAgent: readString(item.anchorAgent) ?? readString(item.anchor_agent),
        phase: readString(item.phase) ?? readString(item.anchor_phase),
        confidence: readNumber(item.confidence),
        suggestedAction: readString(item.suggestedAction) ?? readString(item.suggested_action),
        optimistic: item.optimistic === true,
    }
}
```

- [ ] **Step 5: 在 `consultation-messages.ts` 文件末尾追加 `filterDisplayComments`**

```typescript
/**
 * 过滤显示列表：当 summary_confirmed 消息存在时，隐藏同 session 的 summary 草稿消息。
 */
export function filterDisplayComments(comments: ConsultationComment[]): ConsultationComment[] {
    const confirmedSessionIds = new Set<string>()
    for (const c of comments) {
        if (c.messageType === "summary_confirmed") {
            if (c.sessionId) confirmedSessionIds.add(c.sessionId)
            else confirmedSessionIds.add("__any__")
        }
    }
    if (confirmedSessionIds.size === 0) return comments

    return comments.filter(c => {
        if (c.messageType !== "summary") return true
        if (confirmedSessionIds.has("__any__")) return false
        return c.sessionId ? !confirmedSessionIds.has(c.sessionId) : false
    })
}
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd truthseeker-web && npx vitest run lib/consultation-messages.test.ts --reporter=verbose 2>&1 | tail -20
```

期望：全部 `PASS`

- [ ] **Step 7: 提交**

```bash
git add truthseeker-web/lib/consultation-messages.ts truthseeker-web/lib/consultation-messages.test.ts
git commit -m "feat(consultation): add filterDisplayComments to suppress draft when confirmed arrives"
```

---

## Task 4：`ExpertPanel.tsx` — 应用过滤函数 + 草稿样式渲染

**Files:**
- Modify: `truthseeker-web/components/collaboration/ExpertPanel.tsx`

- [ ] **Step 1: 在 ExpertPanel.tsx 顶部 import 行（第 9-14 行）补充 filterDisplayComments**

将：
```typescript
import {
    mergeConsultationComments,
    normalizeConsultationMessage,
    type ConsultationComment,
    type PanelRole,
} from "@/lib/consultation-messages"
```
改为：
```typescript
import {
    filterDisplayComments,
    mergeConsultationComments,
    normalizeConsultationMessage,
    type ConsultationComment,
    type PanelRole,
} from "@/lib/consultation-messages"
```

- [ ] **Step 2: 在消息列表渲染处（第 543 行 `{comments.map(comment => {`）的前面，将 `comments` 通过 `filterDisplayComments` 过滤**

将：
```tsx
                    {comments.map(comment => {
                        const isMe = comment.role === currentRole &&
                            comment.authorId === getTempUserId()
                        const cfg = ROLE_CONFIG[comment.role] || ROLE_CONFIG.expert
```
改为：
```tsx
                    {filterDisplayComments(comments).map(comment => {
                        const isMe = comment.role === currentRole &&
                            comment.authorId === getTempUserId()
                        const cfg = ROLE_CONFIG[comment.role] || ROLE_CONFIG.expert
```

- [ ] **Step 3: 在气泡渲染处（第 582 行 `<div className={\`px-3 py-2 ...`）为 `summary` 类型消息加草稿样式标记**

将：
```tsx
                                    {/* 气泡 */}
                                    <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed border ${cfg.bubbleBg} ${cfg.bubbleBorder} ${cfg.bubbleText} ${isMe ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}>
                                        {comment.text}
                                    </div>
```
改为：
```tsx
                                    {/* 气泡 */}
                                    <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed border ${comment.messageType === "summary" ? "border-dashed opacity-70" : ""} ${cfg.bubbleBg} ${cfg.bubbleBorder} ${cfg.bubbleText} ${isMe ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}>
                                        {comment.messageType === "summary" && (
                                            <span className="block text-[10px] text-[#F59E0B]/80 mb-1">待确认摘要草稿</span>
                                        )}
                                        {comment.text}
                                    </div>
```

- [ ] **Step 4: 构建前端确认类型无错误**

```bash
cd truthseeker-web && npx tsc --noEmit 2>&1 | tail -20
```

期望：无 TypeScript 错误

- [ ] **Step 5: 运行全部单元测试**

```bash
cd truthseeker-web && npx vitest run --reporter=verbose 2>&1 | tail -30
```

期望：全部 `PASS`

- [ ] **Step 6: 提交**

```bash
git add truthseeker-web/components/collaboration/ExpertPanel.tsx
git commit -m "fix(expert-panel): apply filterDisplayComments and render summary draft style"
```

---

## Task 5：端到端验证（浏览器中验证）

**Files:** 无代码改动，仅验证

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd truthseeker-web && npm run dev
```

- [ ] **Step 2: 打开现有检测页面确认"案例导入配置不同步"已修复**

访问 http://localhost:3000/detect/1e5292e7-bb9b-4f3c-8445-f527dfa254ee

预期：
- 如果该任务的 audit_logs 中包含 `case_import_created` 或 `case_import_duplicate`，流程卡片应显示对应真实状态（"案例已入库"或"案例已存在"），而不是"案例导入跳过"
- 如果 audit_logs 中确实有 `case_import_skipped`，则显示"案例导入跳过"是正确的（说明当时确实未勾选，需要追溯任务创建时的配置）

- [ ] **Step 3: 验证专家侧不再提前显示"报告已生成"**

在一次新的检测中，当流程进入会诊等待阶段时，打开专家链接，确认专家侧顶部不再显示绿色"报告已生成"标记。

- [ ] **Step 4: 验证摘要不再二次出现**

在一次新的检测会诊中，点击"结束会诊"：
1. 确认聊天区出现一条灰色虚线边框、带"待确认摘要草稿"标签的摘要消息
2. 在弹出的 textarea 编辑后点击"确认摘要"
3. 确认聊天区消失草稿消息，出现一条正常样式的摘要消息，共计出现一次
