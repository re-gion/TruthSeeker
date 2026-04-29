# Claude Code Handoff Prompt

你是接手当前 TruthSeeker 工作区的 Claude Code 本地工程代理。请使用用户电脑上的真实终端、真实网络环境和本地浏览器继续完成 Codex 没有完成验证的部分。不要依赖这段对话之外的隐含上下文；下面是当前现场交接。

## 0. 检查清单

开始前先按这个清单确认：

1. 先读当前工作区状态：`git status --short`、相关 diff、`AGENTS.md`、`task.md`、`lessons.md`。
2. 只接手本次数据大屏 03 系统能力层缺失问题及其验证，不要把无关登录、截图、文档删除等改动混入提交。
3. 先验证 Codex 已做的后端 dashboard 修复，再决定是否继续改代码。
4. 必须用真实 Supabase/后端环境重新确认 `/api/v1/dashboard/overview` 返回值，不要把 Codex 沙盒网络失败当成项目代码失败。
5. 最终中文汇报要区分：已验证、未验证、环境阻塞、需要用户介入。

## 1. 项目与环境

- 项目路径：`D:\a311\系统赛\2026系统赛\信安`
- 操作系统与 shell：Windows，PowerShell
- 主要子项目：
  - `truthseeker-web/`：Next.js 16.1.6，React 19.2.3，Tailwind CSS 4，ECharts 数据大屏
  - `truthseeker-api/`：FastAPI 0.134.0，Python 3.11+，Supabase，LangGraph
- 用户偏好：
  - 默认用通俗、清晰、自然的中文汇报。
  - 少讲底层细节，多讲完成了什么、是否可用、如何验证、还需要用户介入什么。
  - 不要把计划、猜测或理论上可行说成已完成或已验证。
  - 尊重未提交改动，不要覆盖、回滚或混入无关文件。
  - 不要打印、复制或提交 `.env`、`.env.local`、`.mcp.json` 里的密钥。

## 2. 用户最初目标和后续要求

用户最初指出：系统数据大屏的 `03 系统能力层` 存在部分系统数据缺失。截图显示典型现象包括：

- KPI 中 `累计任务 = 0`、`平均响应 = 0 ms`、`今日完成 = 0`
- `高风险任务 = 3`
- `任务状态` 空态
- `闭环指标` 中 `已生成报告 = 14`、`会诊触发任务 = 0`、`报告覆盖任务 = 14`

用户补充说：之前多次测试过系统，后端数据库应该存在相关数据，可以使用 Supabase MCP 查询。要求先彻底调研根因，再解决，并充分使用子代理和相关 skills。

当前最新要求：把 Codex 会话整理成可直接复制给 Claude Code 的交接提示词，并默认写入项目根目录 `CLAUDE_CODE_HANDOFF_PROMPT.md`。

## 3. Codex 已完成的调研结论

Codex 使用了并行只读子代理分别调研：

- 前端 dashboard 数据链路
- 后端和 Supabase schema/写入契约
- dashboard 测试入口

结论摘要：

1. `/dashboard` 前端入口是 `truthseeker-web/app/dashboard/page.tsx`，会创建 Supabase server client，读取 session access token，然后调用 `getDashboardViewModel(fetch, token)`。
2. 前端 `truthseeker-web/lib/dashboard/index.ts` 请求 `${NEXT_PUBLIC_API_BASE_URL}/api/v1/dashboard/overview`，成功后归一化，失败则 fallback 到空态。
3. 后端聚合入口是 `truthseeker-api/app/api/v1/dashboard.py` 的 `get_dashboard_overview()`。
4. dashboard 内部真实指标主要来自：
   - `tasks`：累计任务、状态、趋势、响应时间、今日完成
   - `reports`：已生成报告、报告覆盖、证据分布、证据流向
   - `consultation_invites` 和现在补充的 `consultation_sessions`：会诊触发任务
5. 关键根因候选最终收敛为两类：
   - 旧后端 dashboard 查询 `tasks` 时读取了 schema 中不存在的 `verdict`、`response_ms`、`duration_ms` 字段。Supabase/PostgREST 对不存在列会让整个 `tasks` 查询失败，导致任务相关 KPI、趋势、状态归零；`reports` 查询仍成功，所以闭环报告数还能显示 14。
   - `会诊触发任务` 旧口径只看未过期 `consultation_invites`，但真实会诊触发流程会先创建 `consultation_sessions`。如果已有 session 但没有专家 invite，或 invite 已过期，就会显示 0。

## 4. Codex 已做的文件修改

请先用 `git diff` 复核，下面按当前现场记录。

### 本轮 Codex 为修复 dashboard 缺失直接改过

1. `truthseeker-api/app/api/v1/dashboard.py`
   - 引入 `Request`，从 `request.state.user_id` 获取当前用户。
   - `tasks` select 字段改为 migration/schema 中存在的字段：
     - `id,user_id,status,input_type,result,started_at,completed_at,created_at`
   - 按当前用户过滤 tasks，再用 task_ids 过滤 reports、consultation_invites、consultation_sessions。
   - 读取 `consultation_sessions`：
     - `task_id,status,created_at,closed_at`
   - `_build_capability_metrics()` 现在用 `consultation_sessions` 和 `consultation_invites` 的唯一 `task_id` 合并统计会诊触发。
   - 移除了临时 `debug_version` 返回字段。

2. `truthseeker-api/tests/test_dashboard_api.py`
   - Fake Supabase 增加 `SUPABASE_TABLE_COLUMNS`，当 select 不存在列时抛错，用来模拟 PostgREST 真实行为。
   - 测试数据移除 `response_ms`，强制平均响应从 `started_at` / `completed_at` 计算。
   - 增加 `consultation_sessions` 测试数据。
   - 主测试断言 `capability_metrics` 三项值。
   - 新增 `test_dashboard_counts_consultation_sessions_without_active_invites()`，覆盖只有会诊 session、没有 invite 时仍应统计会诊触发。

3. `truthseeker-web/components/dashboard/DashboardClient.tsx`
   - 只修了一个 ESLint 警告：`metrics.map((m, i) => ...)` 改为 `metrics.map((m) => ...)`。
   - 注意：该文件已有大量 UI/图表改动是在 Codex 接手本轮 bug 前就存在的工作区改动，不要默认都归入本轮修复提交。

### 本轮观察到但不是 Codex 本轮主要修复的已有改动

这些文件在 Codex 开始修复前已经处于 modified/untracked/deleted 状态。不要擅自回滚，也不要未经确认混入 dashboard bugfix 提交：

- `CLAUDE_CODE_HANDOFF_PROMPT.md`：本次交接已覆盖写入。
- `dashboard-header-test.png`：已删除。
- `truthseeker-web/.env.example`
- `truthseeker-web/app/dashboard/page.tsx`
- `truthseeker-web/app/login/page.tsx`
- `truthseeker-web/app/signup/page.tsx`
- `truthseeker-web/components/dashboard/DashboardClient.tsx`：除 Codex 一行 lint 修复外，大量改动疑似已有。
- `truthseeker-web/lib/dashboard/index.ts`
- `truthseeker-web/lib/supabase/auth-actions.ts`
- `项目完成进度与代码问题深度调研报告-2026-04-21.md`：已删除。
- `docs/superpowers/specs/`
- `truthseeker-web/app/forgot-password/`
- `truthseeker-web/app/reset-password/`
- 多个截图文件：`truthseeker-web/dashboard-*.png`、`after-login*.png`、`login-page.png`

当前 `git status --short` 现场摘录：

```text
 M CLAUDE_CODE_HANDOFF_PROMPT.md
 D dashboard-header-test.png
 M truthseeker-api/app/api/v1/dashboard.py
 M truthseeker-api/tests/test_dashboard_api.py
 M truthseeker-web/.env.example
 M truthseeker-web/app/dashboard/page.tsx
 M truthseeker-web/app/login/page.tsx
 M truthseeker-web/app/signup/page.tsx
 M truthseeker-web/components/dashboard/DashboardClient.tsx
 M truthseeker-web/lib/dashboard/index.ts
 M truthseeker-web/lib/supabase/auth-actions.ts
 D 项目完成进度与代码问题深度调研报告-2026-04-21.md
?? docs/superpowers/specs/
?? truthseeker-web/after-login-2.png
?? truthseeker-web/after-login.png
?? truthseeker-web/app/forgot-password/
?? truthseeker-web/app/reset-password/
?? truthseeker-web/dashboard-01-02-final.png
?? truthseeker-web/dashboard-01-layer.png
?? truthseeker-web/dashboard-01.png
?? truthseeker-web/dashboard-final.png
?? truthseeker-web/dashboard-full.png
?? truthseeker-web/dashboard-m2.png
?? truthseeker-web/dashboard-m3.png
?? truthseeker-web/dashboard-m4.png
?? truthseeker-web/dashboard-m5.png
?? truthseeker-web/dashboard-m6.png
?? truthseeker-web/dashboard-p0.png
?? truthseeker-web/dashboard-v2.png
?? truthseeker-web/login-page.png
```

## 5. Codex 已运行的验证和结果

### 已验证通过

在 `truthseeker-web`：

```powershell
node .\node_modules\vitest\vitest.mjs run lib/dashboard/index.test.ts components/dashboard/DashboardClient.test.tsx
```

结果：`2 passed`，共 `6 tests passed`。

```powershell
node .\node_modules\typescript\bin\tsc --noEmit --diagnostics
```

结果：通过。

```powershell
node .\node_modules\eslint\bin\eslint.js app/dashboard/page.tsx lib/dashboard/index.ts components/dashboard/DashboardClient.tsx components/dashboard/DashboardClient.test.tsx lib/dashboard/index.test.ts
```

结果：通过。最初有一个 `DashboardClient.tsx` 未使用变量 warning，Codex 已修复并重跑通过。

在 `truthseeker-api`：

```powershell
D:\Anaconda\python.exe -m py_compile app\api\v1\dashboard.py tests\test_dashboard_api.py
```

结果：通过。

在仓库根目录：

```powershell
git diff --check -- truthseeker-api/app/api/v1/dashboard.py truthseeker-api/tests/test_dashboard_api.py truthseeker-web/app/dashboard/page.tsx truthseeker-web/lib/dashboard/index.ts truthseeker-web/components/dashboard/DashboardClient.tsx
```

结果：通过，仅有 LF/CRLF 工作区提示。

### 尝试过但失败

后端 pytest：

```powershell
python -m pytest tests/test_dashboard_api.py -q
.\venv_new\Scripts\python.exe -m pytest tests/test_dashboard_api.py -q
D:\Anaconda\python.exe -m pytest tests/test_dashboard_api.py -q
```

失败原因：

- 系统 Python：`No module named pytest`
- `venv_new`：`No module named pytest`
- Anaconda Python：导入 `unittest.mock` -> `asyncio` -> `windows_events` 时失败：

```text
OSError: [WinError 10106] 无法加载或初始化请求的服务提供程序。
```

后端 unittest：

```powershell
.\venv_new\Scripts\python.exe -m unittest tests.test_dashboard_api -v
D:\Anaconda\python.exe -m unittest tests.test_dashboard_api -v
```

同样失败在 Python 标准库导入 `asyncio/windows_events`，还没进入项目测试逻辑。

真实 Supabase 只读核对：

- Codex 当前会话没有暴露可调用的 Supabase MCP 工具。
- Codex 尝试读取 `.env` 中 Supabase URL/key 后，用 Python `urllib` 做只读 REST 统计，未打印任何密钥。
- 失败：

```text
URLError: <urlopen error [WinError 10106] 无法加载或初始化请求的服务提供程序。>
```

这个更像当前 Codex Windows/Python 网络栈问题，不应直接判断为项目代码问题。

## 6. Claude Code 需要继续做的任务

### P0：用真实终端和网络环境验证 Supabase 数据和后端接口

目标：确认修复后 dashboard API 不再把已有数据误显示为空。

建议命令和步骤：

1. 不打印密钥，只确认 env key 是否存在：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
Get-Content .env | Select-String 'SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ANON_KEY|SUPABASE_JWT_SECRET'
```

只看 key 名，不要输出真实值到聊天或日志。

2. 用真实 Supabase 做只读统计。可以用已有 Python/Node 环境或 Supabase MCP。统计内容只输出聚合结果：

- `tasks` 总数
- `tasks.status` 分布
- `tasks` 中 `completed_at` 非空的 completed 数
- `reports` 总数
- `reports.task_id` 与 `tasks.id` 的覆盖数
- `consultation_invites` 总数
- `consultation_sessions` 总数
- `consultation_sessions.task_id` 与 `tasks.id` 的覆盖数

不要输出原始 `user_id`、token、邮箱、报告内容、key_evidence 原文。

3. 启动后端并请求 dashboard overview：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m uvicorn app.main:app --reload
```

另一个终端：

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/dashboard/overview
```

如果生产/本地 auth middleware 要求 token，则使用浏览器登录后从前端走真实页面，或用合法 session token 调用；不要把 token 粘贴到汇报里。

检查点：

- `kpis.total_tasks` 不应在数据库有任务时为 0。
- `status_breakdown` 应有任务状态分布。
- `trend_series` 应按 completed task 的 `completed_at` 出现近 7 日趋势。
- `capability_metrics.reports-generated` 应接近 reports 表数量。
- `capability_metrics.consultation-triggered` 应包含 `consultation_sessions` 触发任务，不再只依赖未过期 invite。
- `data_warnings` 应为空；如果不为空，要说明是哪张表读取失败。

### P1：跑后端测试

在真实终端修复 Python/pytest/WinError 后运行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m pytest tests/test_dashboard_api.py -q
```

如果本地 Python 仍因 `WinError 10106` 失败，请换一个健康 Python 环境或修复 Winsock 后再跑。不要因为 Codex 里失败就删除测试。

建议再跑：

```powershell
python -m pytest tests/test_report_and_consultation_api.py -q
python -m pytest tests/test_p0_p1_contracts.py -q
```

### P2：前端页面级验证

在真实环境启动前后端：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run dev
```

打开 dashboard 页面，确认截图中 03 系统能力层：

- 累计任务、今日完成、平均响应、状态分布不再因 tasks 查询失败而空。
- 闭环指标中会诊触发任务按 session/invite 合并口径显示。
- 如果登录态影响用户过滤，请分别说明“当前用户视角”和“全局数据视角”的差异。

### P3：整理提交范围

如果用户要求 commit/push，必须选择性暂存本次相关文件，不要 `git add -A` 混入无关文件。

本次 dashboard bugfix 相关候选：

```text
truthseeker-api/app/api/v1/dashboard.py
truthseeker-api/tests/test_dashboard_api.py
truthseeker-web/components/dashboard/DashboardClient.tsx
CLAUDE_CODE_HANDOFF_PROMPT.md
```

是否包含 `truthseeker-web/app/dashboard/page.tsx`、`truthseeker-web/lib/dashboard/index.ts` 要先复核这些改动是否确实属于用户当前要提交的范围。它们在 Codex 本轮修复开始前已经是 modified。

提交信息按用户规则使用 Angular 风格且 subject 中文，例如：

```text
fix: 修复数据大屏系统能力层统计口径
```

## 7. 需要避免的事项

- 不要覆盖或回滚用户已有改动。
- 不要把截图、登录页、重置密码、旧报告删除等无关工作混进 dashboard bugfix 提交。
- 不要泄露 `.env`、`.env.local`、Supabase service role key、JWT secret、session token。
- 不要把 Codex 未能运行的后端 pytest 说成已通过。
- 不要把真实 Supabase 查询未完成说成已验证。
- 不要因为 `会诊触发任务` 曾经显示 0 就只改前端展示；根因在后端聚合口径和 DB 字段契约。
- 不要重新引入 schema 外字段 `response_ms`、`duration_ms`、`verdict` 到 `tasks` select，除非你先确认线上 schema 已新增这些列并同步迁移。

## 8. 预期交付物

完成后请向用户中文汇报：

1. 你复核并确认了哪些 Codex 改动。
2. 真实 Supabase/后端接口验证结果是什么。
3. 前端页面是否已显示正确数据。
4. 哪些测试通过，哪些没跑，没跑的原因。
5. 是否还有需要用户介入的环境问题。
6. 如有提交，列出 commit hash；如 push 失败，给出现场错误。

最终不要超过必要篇幅，重点说“做了什么、是否可用、怎么验证、还剩什么风险”。
