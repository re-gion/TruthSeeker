# Claude Code Handoff Prompt

你是接手 TruthSeeker 项目的本地工程代理。请在用户电脑上的真实终端、真实网络和可用浏览器环境里继续收尾、验证并必要时修复 Codex 已实现但仍未做真实远端验证的“公开案例库 RAG 工具化”工作。

## 角色和沟通约定

- 默认用通俗、清晰、自然的中文向用户汇报。
- 汇报优先说明：做了什么、当前是否可用、实际验证、残留风险、是否需要用户介入。
- 不要把计划、猜测或“理论上可行”说成已经完成。
- 不要泄露 `.env`、`.env.local`、`.mcp.json`、Supabase service role key、JWT secret、SiliconFlow API key 或任何真实密钥。
- 不要覆盖、回滚或混入用户无关改动；提交前必须用 `git status --short` 和选择性 staging 确认范围。
- 用户偏好实际验证，不喜欢泛泛而谈。网络、沙箱、权限或依赖问题要用现场命令证据说明。

## 当前环境和仓库状态

- 项目路径：`D:\a311\系统赛\2026系统赛\信安`
- 操作系统：Windows
- 常用 shell：PowerShell
- 当前分支：`codex/case-rag-tooling`
- 当前 HEAD：`716bea4`
- Codex 本轮没有提交，工作区有未提交改动。
- 这台机器历史上存在 Codex 沙盒网络/DNS/权限问题。浏览器或普通 PowerShell 能联网，不代表 Codex 沙盒里的 `npm`、`pip`、`git`、`curl`、Supabase REST 或外部 API 可用。

### 当前 `git status --short --branch`

```text
## codex/case-rag-tooling
 M docs/APP_FLOW.md
 M docs/BACKEND_STRUCTURE.md
 M docs/TECH_STACK.md
 M lessons.md
 M task.md
 M truthseeker-api/.env.example
 M truthseeker-api/app/agents/nodes/forensics.py
 M truthseeker-api/app/agents/nodes/osint.py
 M truthseeker-api/app/agents/tools/llm_client.py
 M truthseeker-api/app/api/v1/cases.py
 M truthseeker-api/app/config.py
 M truthseeker-api/app/services/analysis_persistence.py
 M truthseeker-api/app/services/case_library.py
 M truthseeker-api/app/services/report_generator.py
 M truthseeker-web/components/cases/CaseDetailClient.tsx
 M truthseeker-web/components/cases/CaseLibraryClient.tsx
 M truthseeker-web/lib/cases.test.ts
 M truthseeker-web/lib/cases.ts
?? truthseeker-api/app/services/builtin_cases.py
?? truthseeker-api/app/services/case_rag.py
?? truthseeker-api/scripts/
?? truthseeker-api/sql/migrations/20260601_case_library_rag_chunks.sql
?? truthseeker-api/tests/test_agent_case_rag.py
?? truthseeker-api/tests/test_case_rag.py
?? truthseeker-api/tests/test_case_rag_report.py
```

没有发现本轮之外的明显无关脏文件，但你仍需在提交前重新检查 `git status --short`。

## 用户目标和补充要求

用户最初目标：把之前做的公开案例库升级成一个 RAG，让电子取证 Agent 和情报溯源 Agent 在鉴伪与溯源过程中多一个“公开案例搜索工具”，能检索已有公开案例进行推理分析借鉴，并在研判报告中展示工具调用情况和分析汇报。

本轮规划中已经确定：

- 语料范围：真实公开案例 + 4 个内置展示案例。
- 检索底座：Supabase Postgres + pgvector 混合检索。
- embedding 配置：独立 embedding 配置，不复用 Kimi 推理配置。
- embedding 模型：SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`。
- API 文档：`https://api-docs.siliconflow.cn/docs/api/embeddings-post`
- 默认 endpoint：`https://api.siliconflow.cn/v1/embeddings`
- embedding 维度：1024。
- RAG 影响边界：只做类案参考，不直接改变裁决分数，不作为当前检材的强证据。
- 调用位置：Forensics + OSINT，Commander 汇总但不重复检索。
- 展示范围：报告 + agent/audit 日志，不新增检测台相似案例卡片。
- 内置展示案例：后端补齐 Markdown 报告，前端也要能点击进入详情页查看报告。
- API key：用户最后再填；你只需把基础设施搭好，填 key 后能直接接入。

## Codex 已完成的文件改动

### 后端 RAG 基础设施

- 新增 `truthseeker-api/sql/migrations/20260601_case_library_rag_chunks.sql`
  - `create extension if not exists vector`
  - 新增 `case_library_rag_chunks`
  - `embedding vector(1024)`
  - HNSW cosine 索引
  - 全文 GIN 索引
  - `match_case_library_rag_chunks(...)` RPC
- 新增 `truthseeker-api/app/services/case_rag.py`
  - Markdown 分块
  - `build_chunk_hash`
  - SiliconFlow/OpenAI-compatible embedding client
  - vector + keyword 混合检索
  - `case_rag_search`
  - `index_case_record`
  - `rebuild_case_rag_index`
- 新增 `truthseeker-api/scripts/rebuild_case_rag_index.py`
  - 用法：`python scripts/rebuild_case_rag_index.py --include-builtin --include-public`
- 修改 `truthseeker-api/app/config.py`
  - 新增 `CASE_RAG_ENABLED`
  - 新增 `CASE_RAG_TOP_K`
  - 新增 `EMBEDDING_BASE_URL`
  - 新增 `EMBEDDING_API_KEY`
  - 新增 `EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-8B`
  - 新增 `EMBEDDING_DIMENSIONS=1024`
- 修改 `truthseeker-api/.env.example`
  - 补充上述 RAG/embedding 示例配置。

### 内置案例资料源和公开案例 API

- 新增 `truthseeker-api/app/services/builtin_cases.py`
  - 4 个内置案例：
    - `builtin-audio-scam`
    - `builtin-video-faceswap`
    - `builtin-mixed-phishing`
    - `builtin-text-news`
  - 每个内置案例都有 Markdown 研判报告。
- 修改 `truthseeker-api/app/api/v1/cases.py`
  - `GET /api/v1/cases/{case_id}` 支持 `builtin-*` 内置案例详情。
- 修改 `truthseeker-api/app/services/case_library.py`
  - API 响应新增 `source_kind`，真实公开案例默认为 `public`。

### Agent 接入

- 修改 `truthseeker-api/app/agents/nodes/forensics.py`
  - 调用 `case_rag_search`
  - RAG 结果写入 `tool_results`
  - RAG 状态写入 `tool_summary.case_rag_status` 和 `tool_summary.case_rag_matches`
  - 写入 `forensics_result.case_rag`
  - RAG 不参与取证降级分数统计
  - 记录 `case_rag.<status>` audit event
- 修改 `truthseeker-api/app/agents/nodes/osint.py`
  - 同样接入 `case_rag_search`
  - 写入 `osint_result.case_rag`
  - RAG 不参与 OSINT 工具降级分数统计
  - 记录 `case_rag.<status>` audit event
- 修改 `truthseeker-api/app/agents/tools/llm_client.py`
  - Forensics、OSINT、Commander prompt 都明确：相似案例只作类案参考，不能当作当前任务事实或强证据。

### 持久化与报告

- 修改 `truthseeker-api/app/services/analysis_persistence.py`
  - 新增公开案例创建后自动尝试索引 RAG chunk。
  - 失败只 warning，不阻断检测/报告。
- 修改 `truthseeker-api/app/services/report_generator.py`
  - 新增“公开案例 RAG 调用情况”章节。
  - 显示 Forensics / OSINT 调用状态、命中案例、相似度、可借鉴点和边界说明。
  - 降级或无命中也会写清楚。
  - `_dict_to_markdown` 跳过 `case_rag` 原始对象，避免报告重复 dump。

### 前端

- 修改 `truthseeker-web/lib/cases.ts`
  - 增加 `sourceKind`
  - 增加 `normalizeCaseDetail`
- 修改 `truthseeker-web/components/cases/CaseLibraryClient.tsx`
  - 4 个内置展示案例 ID 改为 `builtin-*`
  - 内置卡片从不可点击展示改为链接到 `/cases/{id}`
- 修改 `truthseeker-web/components/cases/CaseDetailClient.tsx`
  - 内置案例不显示删除按钮。
  - 内置案例不显示短期预览按钮。
- 修改 `truthseeker-web/lib/cases.test.ts`
  - 覆盖内置案例 `source_kind` 映射。

### 测试

- 新增 `truthseeker-api/tests/test_case_rag.py`
- 新增 `truthseeker-api/tests/test_agent_case_rag.py`
- 新增 `truthseeker-api/tests/test_case_rag_report.py`
- 已有 `truthseeker-api/tests/test_case_library.py` 仍通过。

### 文档和项目状态

- 修改 `docs/APP_FLOW.md`
  - 写入公开案例 RAG 数据流、内置案例详情、回填脚本和 pgvector 状态。
- 修改 `docs/BACKEND_STRUCTURE.md`
  - 写入 `case_rag.py`、`builtin_cases.py`、pgvector 和 SiliconFlow embedding 配置。
- 修改 `docs/TECH_STACK.md`
  - 写入 pgvector 和 embedding 环境变量。
- 修改 `task.md`
  - 将“pgvector/向量库暂不实现”更新为公开案例库 RAG 工具化已实现。
- 修改 `lessons.md`
  - 记录 RAG 只能做类案参考、不可作为当前事实证据。

## Codex 已完成且验证通过的内容

已通过：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
.\venv_new\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_case_library.py tests/test_case_rag.py tests/test_agent_case_rag.py tests/test_case_rag_report.py -q
```

结果：`14 passed in 4.79s`

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run test:unit -- lib/cases.test.ts
```

结果：`4 passed`

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run typecheck
```

结果：通过。

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -c "import ast, pathlib; files=[...]; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8'), filename=f) for f in files]; print('ast-parse-ok', len(files))"
```

结果：`ast-parse-ok 14`

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git diff --check
```

结果：退出码 0，无 whitespace 错误；只有 Git 的 CRLF 提示。

## Codex 尝试过但失败或受限的内容

- 普通全局 `python -m pytest ...` 失败：`C:\Python313\python.exe: No module named pytest`
- `python -m pip install pytest` 在普通沙盒里失败过：用户 site-packages 权限问题。
- 后来使用宿主/已批准方式确认用户目录里有 pytest，但全局 `python` 的 `sys.path` 仍不包含用户 site-packages。
- 正确可用测试入口是项目虚拟环境：`truthseeker-api\venv_new\Scripts\python.exe`
- `python -m compileall app tests scripts` 失败过，原因是写 `tests\__pycache__` 权限被拒绝。Codex 改用 AST parse 做语法检查并通过。
- 没有执行真实 Supabase 迁移。
- 没有真实调用 SiliconFlow `Qwen/Qwen3-VL-Embedding-8B` embedding API，因为用户还没填 API key。
- 没有做浏览器端真实页面验证。
- 没有运行完整后端测试全集，也没有跑前端生产 build。

## Claude Code 需要继续做的任务，按优先级排序

### P0：复核当前代码并确认没有明显实现问题

1. 先运行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git status --short --branch
git diff --check
```

2. 快速审查以下关键文件：

```text
truthseeker-api/app/services/case_rag.py
truthseeker-api/sql/migrations/20260601_case_library_rag_chunks.sql
truthseeker-api/app/agents/nodes/forensics.py
truthseeker-api/app/agents/nodes/osint.py
truthseeker-api/app/services/report_generator.py
truthseeker-web/components/cases/CaseLibraryClient.tsx
truthseeker-web/components/cases/CaseDetailClient.tsx
truthseeker-web/lib/cases.ts
```

重点确认：

- RAG 结果不直接改变裁决分数。
- RAG 失败不会阻断检测。
- prompt 没把相似案例当当前事实。
- 内置案例没有删除/短期预览按钮。
- `source_kind` 不破坏真实公开案例列表。

### P1：运行更完整的本地验证

优先使用项目虚拟环境，不要用全局 Python：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
.\venv_new\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_case_library.py tests/test_case_rag.py tests/test_agent_case_rag.py tests/test_case_rag_report.py -q
```

如果环境允许，再跑：

```powershell
.\venv_new\Scripts\python.exe -m pytest -p no:cacheprovider tests -q
```

前端：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run test:unit -- lib/cases.test.ts
npm run typecheck
npm run lint
npm run build
```

如果完整测试/build 失败，先区分是代码问题还是 Windows/依赖/网络/权限问题，不要直接归咎代码。

### P2：真实 Supabase 迁移和 pgvector 验证

需要在真实 Supabase 项目执行：

```text
truthseeker-api/sql/migrations/20260601_case_library_rag_chunks.sql
```

执行后验证：

```sql
select extname from pg_extension where extname = 'vector';
select count(*) from public.case_library_rag_chunks;
select indexname from pg_indexes where tablename = 'case_library_rag_chunks';
select proname from pg_proc where proname = 'match_case_library_rag_chunks';
```

注意：不要把 service role key 或 JWT secret 输出到聊天。

### P3：接入 SiliconFlow embedding API 并回填索引

用户计划使用 SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`。

后端 `.env` 至少需要：

```env
CASE_RAG_ENABLED=true
CASE_RAG_TOP_K=5
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=<用户真实 key>
EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-8B
EMBEDDING_DIMENSIONS=1024
```

回填命令：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
.\venv_new\Scripts\python.exe scripts\rebuild_case_rag_index.py --include-builtin --include-public
```

预期：

- 至少 4 个内置案例被索引。
- 如果 Supabase 里已有 `case_library_entries` 且含 `report_markdown`，真实公开案例也应被索引。
- 如果 embedding API key 不对、额度不足、网络失败，脚本应报告错误而不是伪装成功。

### P4：真实检测流验证

建议最小真实验证：

1. 启动后端。
2. 启动前端。
3. 打开 `/cases`。
4. 点击 4 个内置案例任意一个，确认进入 `/cases/builtin-*` 并渲染 Markdown 报告。
5. 创建一个小型检测任务，触发 Forensics/OSINT。
6. 确认 agent log 或 audit log 有 `case_rag.<status>`。
7. 下载 Markdown 报告，确认出现“公开案例 RAG 调用情况”章节。
8. 确认 RAG 命中只作为类案参考，没有直接改最终裁决分数。

### P5：提交、推送或交给用户决策

只有在你完成必要验证并确认无严重问题后再提交。

提交信息必须用 Angular 风格且 subject 用中文，例如：

```text
feat: 实现公开案例库 RAG 工具化
```

提交前：

```powershell
git status --short
git diff --check
```

选择性 staging，不要混入无关文件。

## 需要避免的事项

- 不要把历史相似案例写成当前检材事实。
- 不要让 RAG 命中直接改变 `confidence`、`deepfake_score`、`risk_score` 或最终 verdict。
- 不要在 `.env.example` 之外提交真实 API key。
- 不要把完整 signed URL、token、service role key、JWT secret 写进报告、日志或测试输出。
- 不要在未执行 Supabase 迁移前宣称 RAG 远端可用。
- 不要在未填 `EMBEDDING_API_KEY` 前宣称 SiliconFlow embedding 已真实可用。
- 不要覆盖旧的公开案例库真实化能力；本轮是在其基础上新增 RAG。
- 不要把 Codex 沙盒里的网络/权限失败误判为项目代码失败。

## 预期最终交付

你完成后请用中文简洁汇报：

1. 做了什么。
2. 当前结果是否可直接使用。
3. 实际验证命令和结果。
4. 未验证或失败的内容及原因。
5. 是否需要用户提供 SiliconFlow key、Supabase 权限或其他外部资源。
6. 如已提交/推送，说明 commit SHA 和分支。
