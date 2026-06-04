# Claude Code Handoff Prompt

你是接手 TruthSeeker 项目的本地工程代理。用户现在需要你用可用的 Supabase MCP 帮他完成并验证“个人经验库”数据库迁移，因为前端访问个人经验库页面时显示“个人经验库暂时不可用”。

## 角色和沟通约定

- 默认用通俗、清晰、自然的中文汇报。
- 汇报优先说明：做了什么、当前是否可用、实际验证、残留风险、是否需要用户介入。
- 不要把计划、猜测或“理论上可行”说成已经完成。
- 不要泄露 `.env`、`.env.local`、`.mcp.json`、Supabase service role key、JWT secret 或任何真实密钥。
- 不要覆盖、回滚或清空用户无关改动。
- 当前任务只做 Supabase 迁移和验证，除非发现迁移 SQL 本身有明确错误，否则不要改业务代码。

## 当前环境和仓库状态

- 项目路径：`D:\a311\系统赛\2026系统赛\信安`
- 当前分支：`main`
- 当前 HEAD：`275b9ec`
- 当前日期：2026-06-04
- 用户截图现象：前端打开“个人经验库”页面，筛选栏下方显示黄色提示“个人经验库暂时不可用”。
- Codex 已做代码级排查：前后端代码已经有个人经验库功能，最可疑原因是 Supabase 里还没有执行 `20260603_experience_library.sql`，或执行不完整。

开始前请先运行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git status --short --branch
```

当前工作区有大量未提交改动，其中个人经验库相关文件包含未跟踪文件。不要误删、回滚或覆盖这些改动。

## 用户问题的代码级根因线索

前端页面和请求：

- 页面：`truthseeker-web/app/experiences/page.tsx`
- 客户端组件：`truthseeker-web/components/experiences/ExperienceLibraryClient.tsx`
- 请求封装：`truthseeker-web/lib/experiences.ts`
- 请求地址：`GET ${NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/v1/experiences?agent=all&q=&page=1&page_size=9`
- 前端在接口非 2xx 时会显示：`个人经验库暂时不可用`

后端接口：

- 路由文件：`truthseeker-api/app/api/v1/experiences.py`
- 路由挂载：`truthseeker-api/app/api/v1/router.py`
- 路径：`GET /api/v1/experiences`
- 后端会读取 `request.state.user_id`，匿名用户返回 401 `需要登录`
- 已登录用户会查询 Supabase 表：`experience_library_entries`
- 查询失败时后端日志会出现类似：`Failed to list experiences for user ...`
- 查询失败时后端返回 503：`个人经验库暂时不可用`

数据库迁移文件：

```text
truthseeker-api/sql/migrations/20260603_experience_library.sql
```

这份迁移会创建：

- `public.experience_library_entries`
- `public.experience_library_rag_chunks`
- `public.match_experience_library_rag_chunks(...)`
- `vector` 扩展
- 两张表的索引、RLS policy、updated_at trigger

## 你需要完成的任务

### 1. 用 Supabase MCP 先检查真实数据库状态

请先查这些对象是否存在，不要直接盲跑迁移：

```sql
select
  to_regclass('public.experience_library_entries') as experience_entries,
  to_regclass('public.experience_library_rag_chunks') as experience_rag_chunks;
```

再查函数和扩展：

```sql
select extname from pg_extension where extname = 'vector';

select
  n.nspname as schema_name,
  p.proname as function_name,
  pg_get_function_identity_arguments(p.oid) as args
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'match_experience_library_rag_chunks';
```

如果表已存在，还要查列是否齐全：

```sql
select column_name, data_type, udt_name
from information_schema.columns
where table_schema = 'public'
  and table_name in ('experience_library_entries', 'experience_library_rag_chunks')
order by table_name, ordinal_position;
```

再查 policy，避免重复创建 policy 报错：

```sql
select schemaname, tablename, policyname, cmd
from pg_policies
where schemaname = 'public'
  and tablename in ('experience_library_entries', 'experience_library_rag_chunks')
order by tablename, policyname;
```

### 2. 根据检查结果执行迁移

如果两张表和函数都不存在，优先执行完整迁移文件：

```text
D:\a311\系统赛\2026系统赛\信安\truthseeker-api\sql\migrations\20260603_experience_library.sql
```

如果数据库处于“部分迁移”状态，不要重复执行整份 SQL，因为 `create policy ...` 没有 `if not exists`，重复跑可能报 `policy already exists`。这种情况下请只补缺失对象，或者先明确列出哪些对象已存在、哪些缺失，再执行最小 SQL。

重要依赖：

- `public.profiles(id)` 必须存在。
- `public.tasks(id)` 必须存在。
- `public.consultation_sessions(id)` 必须存在。
- `public.set_updated_at()` 必须存在。
- Supabase 项目需要支持 `pgvector` / `vector` 扩展。

如果 `create extension if not exists vector;` 失败，先确认 Supabase 项目是否启用 pgvector。不要改代码绕过，因为个人经验检索需要 `embedding vector(1024)`。

### 3. 迁移后做数据库验证

迁移完成后重新执行：

```sql
select
  to_regclass('public.experience_library_entries') as experience_entries,
  to_regclass('public.experience_library_rag_chunks') as experience_rag_chunks;
```

确认 `experience_library_rag_chunks.embedding` 是 `vector`：

```sql
select column_name, udt_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'experience_library_rag_chunks'
  and column_name = 'embedding';
```

确认函数存在：

```sql
select
  n.nspname as schema_name,
  p.proname as function_name,
  pg_get_function_identity_arguments(p.oid) as args
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'match_experience_library_rag_chunks';
```

预期结果：

- 两张表都返回 `public.xxx`，不是 `null`
- `embedding` 的 `udt_name` 应该是 `vector`
- 函数存在，参数包含 `query_embedding vector(1024), match_user_id uuid, match_agent text, match_count integer`

### 4. 验证后端接口

需要验证真实接口从 503 恢复为可用。

优先用浏览器登录态或用户提供的本地前端页面验证。也可以从前端 Network 面板看：

- 请求：`GET /api/v1/experiences?agent=all&q=&page=1&page_size=9`
- 预期：200
- 响应示例：

```json
{
  "items": [],
  "page": 1,
  "page_size": 9,
  "total": 0
}
```

注意：

- 空数组是正常状态，表示当前账号还没有个人经验。
- 401 `需要登录` 表示没有登录或 token 没传，不是数据库迁移问题。
- 503 `个人经验库暂时不可用` 才是当前要解决的主要症状。

如果能查看后端日志，请确认不再出现：

```text
Failed to list experiences for user ...
```

### 5. 验证前端页面

打开：

```text
http://localhost:3000/experiences
```

或用户当前运行的前端地址对应的 `/experiences`。

预期：

- 已登录时不再显示“个人经验库暂时不可用”。
- 如果还没有数据，应显示“当前筛选下还没有个人经验”。
- 筛选按钮“全部 / 取证 Agent / 溯源 Agent / 质询 Agent”和搜索框应保留可操作。

如果页面仍报错，请用浏览器 Network 面板区分：

- 后端是否仍返回 503
- 是否变成 401 登录问题
- 是否前端 `NEXT_PUBLIC_API_BASE_URL` 指错后端
- 后端服务是否没启动或 CORS 失败

## 建议运行的本地代码检查

如果你需要确认代码侧没有明显问题，可以运行这些局部测试。

后端优先使用项目虚拟环境：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
.\venv_new\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_experience_library.py -q
```

前端局部测试：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run test:unit -- lib/experiences.test.ts
```

如果本地测试因为依赖、网络、权限或环境失败，请记录真实错误，不要把它混同为迁移失败。

## 不要做的事

- 不要推送 `main`，除非用户明确要求并确认。
- 不要把真实 Supabase key、JWT、token 写入交接文档或聊天。
- 不要删除未跟踪文件。
- 不要重置工作区。
- 不要为了让页面不报错而把前端 503 文案改成空状态；必须先解决数据库对象缺失或后端查询失败的根因。
- 不要在没有验证接口状态的情况下告诉用户“已经好了”。

## 最终汇报格式

请按下面结构向用户汇报：

### 1. 完成了什么

说明检查了哪些 Supabase 对象，执行了哪些迁移或补齐了哪些缺失对象。

### 2. 当前结果是否可用

明确写：

- 已可直接使用，或
- 基本可用但还有限制，或
- 尚未完成，暂不能直接使用

### 3. 实际验证

只写真正执行过的验证，例如：

- Supabase 表/函数/扩展查询结果
- `GET /api/v1/experiences` 的 HTTP 状态和响应
- 前端 `/experiences` 页面的实际显示
- 后端或前端测试命令结果

### 4. 残留问题与是否需要用户介入

如果需要用户登录、提供 Supabase 权限、填写 env、启动服务或确认生产项目，请明确写清楚。
