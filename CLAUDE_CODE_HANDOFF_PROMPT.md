# Claude Code Handoff Prompt

你是接手 TruthSeeker 项目的本地工程代理。请在用户电脑上的真实终端和网络环境里继续收尾、验证并必要时修复 Codex 已实现但尚未完成真实 Supabase 端到端验证的“公开案例库真实化”工作。

## 角色和沟通约定

- 默认用通俗、清晰、自然的中文向用户汇报。
- 汇报优先说明：做了什么、当前是否可用、实际验证、残留风险、是否需要用户介入。
- 不要把计划、猜测或“理论上可行”说成已经完成。
- 不要泄露 `.env`、`.env.local`、Supabase service role key、JWT secret、API key 或本地配置里的真实密钥。
- 不要覆盖、回滚或混入用户无关改动；提交前必须用 `git status --short` 和选择性 staging 确认范围。

## 当前环境

- 项目路径：`D:\a311\系统赛\2026系统赛\信安`
- 操作系统：Windows
- 当前 shell：PowerShell
- 当前分支：Codex 开始交接时在 `codex/public-case-library`，用户要求合并回 `main`。
- Codex 已尝试使用 Windows/Codex 沙盒和受限终端；真实 Supabase 线上连接和迁移执行未完成。
- 这台机器历史上存在 Codex 沙盒网络/DNS/代理问题。浏览器能联网不代表 Codex 沙盒内 `npm`、`pip`、`git`、`curl`、Supabase REST 可用。你应优先使用用户真实终端/真实网络环境验证远端 Supabase。

## 用户目标

用户最初要求把原本纯前端硬编码的“全模态演示案例库”真实实现，并改定位为“公开案例库”：

- 保留原来的 4 个内置案例，只作为不可点击的展示卡片。
- 真实新增案例来自用户历史检测任务。
- 只有用户上传时勾选“愿意脱敏后公开至案例库”，且检测完整生成最终研判报告后，才自动进入公开案例库。
- 原始图片/文本/音频/视频检材不写入数据库，只复用 Supabase Storage 私有 `media` bucket 的 `storage_path`。
- 案例表保存：标题、媒体标签、摘要、结论、置信度、难度/风险、脱敏文件元数据、报告 Markdown、去重指纹、发布时间和状态。
- 公开案例详情页以 Markdown 渲染研判报告，而不是只给报告链接。
- 支持分类筛选和分页：全部、文本生成、图像伪造、图文混合、音频伪造、视频伪造。
- 去重规则：同一组初始媒体检材 SHA-256 + 同一份规范化 `case_prompt` 才算重复；重复时继续正常检测并生成用户报告，但不重复入库。
- 公开案例库匿名可见；详情页可通过后端生成短期签名 URL 预览原检材。
- Supabase Free 层约束：不要复制大文件；勾选公开案例库时单文件按 50MB 上限处理。

用户最新要求：

- 生成一份 Claude Code 可直接复制使用的交接提示词。
- 默认写入项目根目录 `CLAUDE_CODE_HANDOFF_PROMPT.md`。
- 帮用户把当前功能分支合并回主分支。

## Codex 已完成的代码改动

### 后端

新增/修改：

- `truthseeker-api/sql/migrations/20260528_case_library_entries.sql`
  - 新增 `public.case_library_entries` 表。
  - 新增 `status`、`media_category`、`public_files`、`report_markdown`、`content_fingerprint` 等字段。
  - 新增公开案例查询索引和 published 指纹唯一索引。
  - 调整 `tasks.input_type` 约束，允许 `mixed`。
- `truthseeker-api/app/services/case_library.py`
  - 公开案例指纹：`build_case_fingerprint(files, case_prompt)`。
  - 保守脱敏：邮箱、手机号、身份证号、签名 URL token、临时 storage path。
  - 分类推导：文本生成、图像伪造、图文混合、音频伪造、视频伪造。
  - 入库幂等：`ensure_case_library_entry()`。
  - API 响应脱敏：不把 `storage_path` 返回给列表/详情，只在预览接口内部使用。
- `truthseeker-api/app/api/v1/cases.py`
  - `GET /api/v1/cases`
  - `GET /api/v1/cases/{case_id}`
  - `POST /api/v1/cases/{case_id}/preview-url`
  - 只读取 `status='published'` 的案例。
  - 预览 URL 有效期 600 秒。
- `truthseeker-api/app/api/v1/router.py`
  - 注册 `/cases` router。
- `truthseeker-api/app/middleware/auth.py`
  - 放行公开案例 GET。
  - 放行 `POST /api/v1/cases/{id}/preview-url`。
- `truthseeker-api/app/api/v1/upload.py`
  - 上传时计算完整 SHA-256。
  - `share_to_casebase=true` 时单文件限制 50MB。
  - 上传响应返回 `sha256`。
- `truthseeker-api/app/services/evidence_files.py`
  - 标准化上传文件时保留 `sha256`。
  - 混合模态 `input_type` 改为 `mixed`，避免 SQL 约束冲突。
- `truthseeker-api/app/api/v1/tasks.py`
  - 创建任务时，如果 `share_to_casebase` 为真，检查公开案例重复并写入 metadata：
    - `casebase_duplicate`
    - `casebase_duplicate_case_id`
    - `casebase_fingerprint`
  - `storage_paths.files` 保留 `sha256`。
- `truthseeker-api/app/api/v1/detect.py`
  - 检测任务文件快照保留 `sha256`。
- `truthseeker-api/app/services/analysis_persistence.py`
  - `upsert_report()` 写入报告后，如果任务勾选公开案例库，自动创建公开案例。
  - 优先使用现有 `generate_markdown_report(task_id)` 生成完整 Markdown。
  - 若完整 Markdown 生成失败，会退回 `case_library.py` 中根据 report row 构造的简版 Markdown。
  - 对未勾选公开案例库的普通报告不额外生成案例 Markdown。
- `truthseeker-api/app/api/v1/share.py`
  - 当分享接口从已完成任务补建 report row 时，也会调用公开案例入库服务。
- `truthseeker-api/tests/test_case_library.py`
  - 覆盖指纹稳定性、脱敏、分类/字段构造、重复不入库、公开 API 列表/详情/预览。

### 前端

新增/修改：

- `truthseeker-web/lib/cases.ts`
  - 公开案例 API client。
  - 分类枚举和标签。
  - 列表/详情响应归一化。
  - 预览 URL 请求。
- `truthseeker-web/lib/cases.test.ts`
  - 覆盖分类标签、列表归一化、API 请求形状。
- `truthseeker-web/components/cases/CaseLibraryClient.tsx`
  - `/cases` 客户端主体。
  - 支持分类筛选、分页、真实公开案例卡片、4 个内置展示案例。
  - 内置展示案例不可点击。
- `truthseeker-web/components/cases/CaseDetailClient.tsx`
  - `/cases/[caseId]` 详情页主体。
  - 渲染脱敏 Markdown 报告。
  - 文件列表支持请求短期预览 URL。
  - 音频/视频/图片按类型预览。
- `truthseeker-web/app/cases/page.tsx`
  - 页面标题从演示案例库改为公开案例库。
  - 使用 `CaseLibraryClient`。
- `truthseeker-web/app/cases/[caseId]/page.tsx`
  - 新增公开案例详情页路由。
- `truthseeker-web/middleware.ts`
  - 放行匿名访问 `/cases` 和 `/cases/*`。
- `truthseeker-web/components/layout/HeaderClient.tsx`
  - 导航文案改为“公开案例库”。
- `truthseeker-web/components/upload/FileUploader.tsx`
  - 勾选公开案例库时，前端先检查 50MB 上限。
  - 上传 `FormData` 传 `share_to_casebase`。
  - 保留后端返回的 `sha256` 并提交到任务 metadata / storage paths。
  - 如果后端返回 `metadata.casebase_duplicate`，跳转检测页时带 `casebase=duplicate`。
- `truthseeker-web/components/upload/FileUploader.test.ts`
  - 覆盖公开案例库 50MB 前端限制。
- `truthseeker-web/components/detect/DetectConsole.tsx`
  - 如果 URL 包含 `casebase=duplicate`，显示“检测照常进行但不会重复入库”的提示。

### 文档

已更新：

- `task.md`
  - 将“案例库真实加载功能暂不实现”更新为已完成公开案例库真实加载。
- `docs/APP_FLOW.md`
  - 补充公开案例库上传限制、去重、入库、公开 API、短期预览和暂不实现项。
- `docs/PRD.md`
  - 将“案例库”定位更新为“公开案例库”。
- `lessons.md`
  - 记录 Supabase 免费层、不要复制音视频大文件、重复公开不阻断正常检测等经验。
- `CLAUDE_CODE_HANDOFF_PROMPT.md`
  - 本交接文档。

## Codex 已运行并通过的验证

这些结果来自 Codex 当前会话，Claude Code 可轻量复核，不必重复实现：

后端：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m pytest tests/test_case_library.py
# 5 passed

python -m pytest tests/test_case_library.py tests/test_analysis_persistence.py tests/test_report_and_consultation_api.py
# 21 passed, 2 warnings

python -m pytest tests
# 117 passed, 2 warnings

python -m compileall app
# passed
```

前端：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npx vitest run lib/cases.test.ts components/upload/FileUploader.test.ts
# 5 passed

npm run test:unit
# 44 passed

npm run typecheck
# passed

npm run lint
# exit 0; 0 errors, 7 existing warnings

npm run build
# passed
```

其他：

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git diff --check
# passed
```

说明：

- `npm run lint` 剩余 warning 来自既有文件：
  - `components/collaboration/ExpertPanel.test.tsx` 的 `<img>` warning。
  - `components/dashboard/DashboardClient.tsx` 的未使用变量 warning。
  - `components/landing/AgentShowcase.tsx` 的 `<img>` warning。
  - Codex 未处理这些旧 warning，避免扩大范围。
- 后端 Supabase 依赖 warnings 是 supabase Python SDK 的 deprecation warning，不是本功能失败。

## Codex 未完成或未真实验证的内容

P0 - 必须由 Claude Code 继续完成：

1. **把新增迁移应用到真实 Supabase**
   - 文件：`truthseeker-api/sql/migrations/20260528_case_library_entries.sql`
   - 必须确认远端存在 `case_library_entries` 表、索引、RLS policy。
   - Codex 没有连接真实 Supabase 执行迁移。

2. **做真实端到端公开案例验证**
   - 用小型文本或图片文件，登录后勾选“愿意脱敏后公开至案例库”。
   - 完整跑一次检测直到报告生成。
   - 确认 `/cases` 出现真实公开案例卡片。
   - 点进 `/cases/[caseId]`，确认 Markdown 报告渲染。
   - 点击短期预览，确认签名 URL 可访问原检材。
   - 用同一文件和同一提示词再次检测，确认检测继续但不重复入库，并在检测页显示重复提示。

3. **合并主分支后的最终复核**
   - 用户要求合并回 `main`，Codex 正在执行/已执行本交接时应确认最终状态。
   - 如果合并后未 push，向用户说明本地已合并但未推送。

P1 - 建议检查：

1. **API 权限边界**
   - 匿名只能读 `status='published'`。
   - 列表和详情不返回 `storage_path`。
   - 只有 preview 接口内部使用 `storage_path` 生成短期 signed URL。

2. **报告 Markdown 完整性**
   - 入库优先调用 `generate_markdown_report(task_id)`。
   - 如果真实 Supabase 数据缺字段导致 canonical Markdown 生成失败，会回退为简版 Markdown。
   - 端到端验证时要确认 `case_library_entries.report_markdown` 是否是完整报告。

3. **Free 层容量风险**
   - 勾选公开案例库时单文件限制 50MB。
   - 普通检测仍保留原有分类型限制。
   - 数据库不写音视频二进制，只写 Storage 引用。

## 当前工作区状态（Codex 交接时）

Codex 交接前 `git status --short --branch` 显示：

```text
## codex/public-case-library
 M docs/APP_FLOW.md
 M docs/PRD.md
 M lessons.md
 M task.md
 M truthseeker-api/app/api/v1/detect.py
 M truthseeker-api/app/api/v1/router.py
 M truthseeker-api/app/api/v1/share.py
 M truthseeker-api/app/api/v1/tasks.py
 M truthseeker-api/app/api/v1/upload.py
 M truthseeker-api/app/middleware/auth.py
 M truthseeker-api/app/services/analysis_persistence.py
 M truthseeker-api/app/services/evidence_files.py
 M truthseeker-web/app/cases/page.tsx
 M truthseeker-web/components/detect/DetectConsole.tsx
 M truthseeker-web/components/layout/HeaderClient.tsx
 M truthseeker-web/components/upload/FileUploader.test.ts
 M truthseeker-web/components/upload/FileUploader.tsx
 M truthseeker-web/middleware.ts
?? truthseeker-api/app/api/v1/cases.py
?? truthseeker-api/app/services/case_library.py
?? truthseeker-api/sql/migrations/20260528_case_library_entries.sql
?? truthseeker-api/tests/test_case_library.py
?? truthseeker-web/app/cases/[caseId]/
?? truthseeker-web/components/cases/
?? truthseeker-web/lib/cases.test.ts
?? truthseeker-web/lib/cases.ts
?? CLAUDE_CODE_HANDOFF_PROMPT.md
```

没有发现明显无关改动。请仍然在你接手时重新运行：

```powershell
git status --short --branch
git diff --stat
git diff --check
```

## Claude Code 应优先执行的下一步

### 1. 确认 Git 状态和合并结果

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git status --short --branch
git log --oneline -5
```

如果 Codex 已提交并合并到 `main`，确认 `main` 包含公开案例库改动。

如果 Codex 没有完成合并：

```powershell
git add docs/APP_FLOW.md docs/PRD.md lessons.md task.md CLAUDE_CODE_HANDOFF_PROMPT.md `
  truthseeker-api/app/api/v1/detect.py `
  truthseeker-api/app/api/v1/router.py `
  truthseeker-api/app/api/v1/share.py `
  truthseeker-api/app/api/v1/tasks.py `
  truthseeker-api/app/api/v1/upload.py `
  truthseeker-api/app/middleware/auth.py `
  truthseeker-api/app/services/analysis_persistence.py `
  truthseeker-api/app/services/evidence_files.py `
  truthseeker-api/app/api/v1/cases.py `
  truthseeker-api/app/services/case_library.py `
  truthseeker-api/sql/migrations/20260528_case_library_entries.sql `
  truthseeker-api/tests/test_case_library.py `
  truthseeker-web/app/cases/page.tsx `
  truthseeker-web/app/cases/[caseId]/page.tsx `
  truthseeker-web/components/cases/CaseLibraryClient.tsx `
  truthseeker-web/components/cases/CaseDetailClient.tsx `
  truthseeker-web/components/detect/DetectConsole.tsx `
  truthseeker-web/components/layout/HeaderClient.tsx `
  truthseeker-web/components/upload/FileUploader.test.ts `
  truthseeker-web/components/upload/FileUploader.tsx `
  truthseeker-web/lib/cases.ts `
  truthseeker-web/lib/cases.test.ts `
  truthseeker-web/middleware.ts

git commit -m "feat: 实现公开案例库真实闭环"
git switch main
git merge --no-ff codex/public-case-library
```

如果用户要求推送：

```powershell
git push origin main
```

注意：提交信息必须使用 Angular 规范，包含 type 和中文 subject。

### 2. 重新跑最小验证

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m pytest tests/test_case_library.py tests/test_analysis_persistence.py tests/test_report_and_consultation_api.py
python -m pytest tests
python -m compileall app

cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run test:unit
npm run typecheck
npm run lint
npm run build
```

### 3. 应用 Supabase 迁移

选择项目现有方式执行 `truthseeker-api/sql/migrations/20260528_case_library_entries.sql`。

如果项目使用 Supabase CLI，可尝试：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
supabase db push
```

如果没有 CLI 或项目未链接，请在 Supabase SQL Editor 中执行迁移文件内容。执行后检查：

```sql
select count(*) from public.case_library_entries;
select policyname from pg_policies where tablename = 'case_library_entries';
```

### 4. 做真实端到端验证

建议用一个小 `.txt` 或小 `.png`：

1. 启动后端：
   ```powershell
   cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
   python -m uvicorn app.main:app --reload
   ```
2. 启动前端：
   ```powershell
   cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
   npm run dev
   ```
3. 浏览器打开前端，登录。
4. 上传小文件，填写固定 `case_prompt`，勾选“愿意脱敏后公开至案例库”。
5. 等检测完成并生成报告。
6. 打开 `/cases`，确认真实卡片出现。
7. 打开详情页，确认报告 Markdown 和短期预览可用。
8. 重复相同文件和相同提示词，确认不会重复新增公开案例，但检测正常继续。

如果外部 Kimi、Reality Defender、VirusTotal、Exa 不可用，系统可能走降级路径；不要把外部 API/网络失败说成案例库代码失败。要基于后端日志和测试结果判断。

## 需要避免的事项

- 不要把 `.env`、`.env.local`、`.mcp.json` 或任何真实密钥贴到聊天或提交里。
- 不要把未验证的 Supabase 迁移说成已经上线。
- 不要把 Codex 只做过本地测试的内容说成已经端到端可用。
- 不要把旧 lint warning 当作本次新增错误；但如果有新增 error 必须修。
- 不要把 4 个内置展示案例改成可点击详情，它们按用户要求只是表面卡片。
- 不要把原始音视频复制进数据库或新 bucket；本轮设计是复用私有 `media` bucket 的 `storage_path`。
- 不要阻断重复案例的正常检测；重复只影响公开案例入库。

## 预期交付物

1. 本地 `main` 分支包含公开案例库真实化改动。
2. 新增 Supabase 迁移已在远端成功执行，或明确说明用户需要手动执行。
3. 前后端测试、typecheck、lint、build 的实际结果。
4. 至少一次真实端到端公开案例入库验证，或明确说明阻塞原因。
5. 最终中文汇报：完成了什么、是否可用、验证证据、残留风险、是否需要用户介入。
