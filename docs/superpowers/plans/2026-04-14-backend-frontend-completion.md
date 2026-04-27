# TruthSeeker 批次1+2 补全实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全数据库Schema/RLS、文件上传端点、JWT鉴权、前端真实文件上传、Dashboard真实数据接入、后端Supabase Realtime广播。

**Architecture:** 批次1先打通后端基础设施（Supabase迁移、文件存储、鉴权中间件），批次2再让前端消费真实数据（文件上传替换mock、Dashboard接入Supabase查询、后端广播Agent事件到Realtime）。

**Tech Stack:** FastAPI 0.134, LangGraph >=1.0.9, Supabase Python SDK >=2.15, Next.js 16, @supabase/ssr ^0.8, Supabase Realtime Broadcast

---

## 文件变更地图

### 批次1 — 后端基础设施

| 文件 | 操作 | 职责 |
|------|------|------|
| `truthseeker-api/app/middleware/auth.py` | 新建 | 验证 Supabase JWT，注入 user_id |
| `truthseeker-api/app/api/v1/upload.py` | 新建 | 接收文件 → Supabase Storage → 返回 URL |
| `truthseeker-api/app/api/v1/router.py` | 修改 | 注册 upload 路由 |
| `truthseeker-api/app/main.py` | 修改 | 注册 AuthMiddleware（可选路由白名单） |
| `truthseeker-api/.env.example` | 新建 | 环境变量模板 |
| `truthseeker-web/.env.example` | 新建 | 前端环境变量模板 |

### 批次2 — 前端数据接入

| 文件 | 操作 | 职责 |
|------|------|------|
| `truthseeker-web/components/upload/FileUploader.tsx` | 修改 | 先上传文件到后端，再用真实URL启动检测 |
| `truthseeker-web/hooks/useAgentStream.ts` | 修改 | 接受 fileUrl 参数（已有），确保传真实URL |
| `truthseeker-web/components/dashboard/StatsOverview.tsx` | 修改 | 从Supabase查询tasks表统计数据 |
| `truthseeker-api/app/api/v1/detect.py` | 修改 | 检测完成后向Supabase Realtime广播final_verdict |

---

## 批次1：后端基础设施

### Task 1: Supabase 数据库 Schema 迁移

**Files:**
- Use: Supabase MCP `apply_migration`

- [ ] **Step 1: 通过 Supabase MCP 执行迁移**

执行以下 SQL（通过 mcp__supabase__apply_migration，name: `create_tasks_table`）：

```sql
create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text not null default 'Untitled Task',
  status text not null default 'pending'
    check (status in ('pending','running','completed','failed')),
  input_type text not null default 'video'
    check (input_type in ('video','audio','image','text')),
  description text,
  file_url text,
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 自动更新 updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger tasks_updated_at
  before update on public.tasks
  for each row execute function public.set_updated_at();
```

- [ ] **Step 2: 配置 RLS 策略**

执行以下 SQL（通过 mcp__supabase__apply_migration，name: `tasks_rls`）：

```sql
alter table public.tasks enable row level security;

-- 用户只能读写自己的任务
create policy "users_own_tasks_select"
  on public.tasks for select
  using (auth.uid() = user_id);

create policy "users_own_tasks_insert"
  on public.tasks for insert
  with check (auth.uid() = user_id);

create policy "users_own_tasks_update"
  on public.tasks for update
  using (auth.uid() = user_id);

-- 匿名任务（user_id 为 null）允许插入，用于未登录演示
create policy "anon_tasks_insert"
  on public.tasks for insert
  with check (user_id is null);
```

- [ ] **Step 3: 创建 Supabase Storage bucket**

执行以下 SQL（通过 mcp__supabase__apply_migration，name: `create_media_bucket`）：

```sql
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'media',
  'media',
  false,
  524288000,  -- 500MB
  array['video/mp4','video/webm','audio/mpeg','audio/wav','image/jpeg','image/png','image/webp','text/plain']
)
on conflict (id) do nothing;

-- Storage RLS: 用户只能访问自己上传的文件
create policy "media_upload_own"
  on storage.objects for insert
  with check (bucket_id = 'media' and (auth.uid()::text = (storage.foldername(name))[1] or (storage.foldername(name))[1] = 'anon'));

create policy "media_read_own"
  on storage.objects for select
  using (bucket_id = 'media' and (auth.uid()::text = (storage.foldername(name))[1] or (storage.foldername(name))[1] = 'anon'));
```

- [ ] **Step 4: 验证迁移**

通过 mcp__supabase__execute_sql 执行：
```sql
select table_name, row_security from information_schema.tables
where table_schema = 'public' and table_name = 'tasks';
```
预期：返回 `tasks` 行，`row_security = YES`

---

### Task 2: 文件上传端点

**Files:**
- Create: `truthseeker-api/app/api/v1/upload.py`
- Modify: `truthseeker-api/app/api/v1/router.py`

- [ ] **Step 1: 创建 upload.py**

```python
"""文件上传端点 - 接收文件并存储到 Supabase Storage"""
import uuid
import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional
from app.utils.supabase_client import supabase

router = APIRouter()

ALLOWED_MIME = {
    "video/mp4", "video/webm",
    "audio/mpeg", "audio/wav",
    "image/jpeg", "image/png", "image/webp",
    "text/plain",
}
MAX_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
):
    """上传媒体文件到 Supabase Storage，返回可访问 URL"""
    # 验证 MIME 类型
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型: {content_type}")

    # 读取文件内容
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过 500MB 限制")

    # 构建存储路径: {user_id_or_anon}/{uuid}.{ext}
    ext = (file.filename or "file").rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    folder = user_id or "anon"
    storage_path = f"{folder}/{uuid.uuid4()}.{ext}"

    try:
        response = supabase.storage.from_("media").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"存储上传失败: {str(e)}")

    # 生成签名 URL（1小时有效）
    try:
        signed = supabase.storage.from_("media").create_signed_url(storage_path, 3600)
        file_url = signed["signedURL"]
    except Exception:
        # fallback: 使用公开路径（如果 bucket 是 public）
        file_url = f"{supabase.supabase_url}/storage/v1/object/public/media/{storage_path}"

    return {
        "file_url": file_url,
        "storage_path": storage_path,
        "content_type": content_type,
        "size": len(content),
    }
```

- [ ] **Step 2: 注册路由到 router.py**

读取 `truthseeker-api/app/api/v1/router.py`，在现有路由后添加：

```python
from app.api.v1.upload import router as upload_router
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
```

- [ ] **Step 3: 手动测试上传端点**

启动后端后执行：
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/test.mp4" \
  -F "user_id=test-user"
```
预期：返回 `{"file_url": "https://...", "storage_path": "...", ...}`

- [ ] **Step 4: Commit**

```bash
git add truthseeker-api/app/api/v1/upload.py truthseeker-api/app/api/v1/router.py
git commit -m "feat: add file upload endpoint with Supabase Storage"
```

---

### Task 3: 后端 JWT 鉴权中间件

**Files:**
- Create: `truthseeker-api/app/middleware/auth.py`
- Modify: `truthseeker-api/app/main.py`

- [ ] **Step 1: 创建 auth.py**

```python
"""Supabase JWT 验证中间件"""
import jwt
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# 不需要鉴权的路由前缀
PUBLIC_PATHS = {"/health", "/api/v1/detect/stream", "/api/v1/tasks", "/api/v1/upload"}


class AuthMiddleware(BaseHTTPMiddleware):
    """验证 Supabase JWT，将 user_id 注入 request.state"""

    def __init__(self, app, supabase_jwt_secret: str):
        super().__init__(app)
        self.jwt_secret = supabase_jwt_secret

    async def dispatch(self, request: Request, call_next):
        # 公开路由跳过鉴权
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            request.state.user_id = None
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization token")

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            request.state.user_id = payload.get("sub")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        return await call_next(request)
```

- [ ] **Step 2: 在 config.py 添加 JWT secret 配置**

在 `truthseeker-api/app/config.py` 的 `Settings` 类中添加：
```python
SUPABASE_JWT_SECRET: str = ""
```

- [ ] **Step 3: 在 main.py 注册中间件**

在 `app.add_middleware(RateLimitMiddleware, ...)` 之后添加：
```python
from app.middleware.auth import AuthMiddleware
if settings.SUPABASE_JWT_SECRET:
    app.add_middleware(AuthMiddleware, supabase_jwt_secret=settings.SUPABASE_JWT_SECRET)
```

- [ ] **Step 4: 安装 PyJWT**

```bash
cd truthseeker-api
venv_new\Scripts\activate  # Windows
pip install PyJWT>=2.8.0
echo "PyJWT>=2.8.0" >> requirements.txt
```

- [ ] **Step 5: Commit**

```bash
git add truthseeker-api/app/middleware/auth.py truthseeker-api/app/config.py truthseeker-api/app/main.py truthseeker-api/requirements.txt
git commit -m "feat: add Supabase JWT auth middleware"
```

---

### Task 4: 创建 .env.example 文件

**Files:**
- Create: `truthseeker-api/.env.example`
- Create: `truthseeker-web/.env.example`

- [ ] **Step 1: 创建后端 .env.example**

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard

# AI APIs
OPENAI_API_KEY=sk-...
QWEN_API_KEY=
REALITY_DEFENDER_API_KEY=

# App
FRONTEND_URL=http://localhost:3000
MAX_ROUNDS=3
CONVERGENCE_THRESHOLD=0.08
```

- [ ] **Step 2: 创建前端 .env.example**

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: 确认 .gitignore 包含 .env**

检查 `truthseeker-api/.gitignore` 和 `truthseeker-web/.gitignore` 中有 `.env` 和 `.env.local`。

- [ ] **Step 4: Commit**

```bash
git add truthseeker-api/.env.example truthseeker-web/.env.example
git commit -m "docs: add .env.example for backend and frontend"
```

---

## 批次2：前端数据接入

### Task 5: FileUploader 真实文件上传

**Files:**
- Modify: `truthseeker-web/components/upload/FileUploader.tsx`

当前问题：`launchAnalysis` 函数中文件只创建了任务元数据，`file_url` 传的是 `mock://${file.name}`，后端 Agent 拿到的是假 URL。

- [ ] **Step 1: 修改 launchAnalysis 函数**

找到 `FileUploader.tsx` 中的 `launchAnalysis` 函数，将文件上传逻辑替换为：

```typescript
const launchAnalysis = useCallback(async (file: File | null, prompt: string) => {
    setError(null)
    if (!file && !prompt.trim()) {
        setError("请上传多媒体内容或填写文本说明")
        return
    }
    if (file) {
        if (!ACCEPTED_TYPES.includes(file.type)) {
            setError(`不支持的文件类型：${file.type}`)
            return
        }
        if (file.size > 500 * 1024 * 1024) {
            setError("文件大小不能超过 500MB")
            return
        }
    }
    setUploading(true)
    setProgress(0)
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    try {
        let fileUrl: string | null = null
        const inputType = getInputType(file, prompt)

        // Step 1: 上传文件（如果有）
        if (file) {
            setProgress(10)
            const formData = new FormData()
            formData.append("file", file)
            const uploadResp = await fetch(`${apiBase}/api/v1/upload`, {
                method: "POST",
                body: formData,
            })
            if (!uploadResp.ok) {
                const err = await uploadResp.json().catch(() => ({}))
                throw new Error(err.detail || "文件上传失败")
            }
            const uploadData = await uploadResp.json()
            fileUrl = uploadData.file_url
            setProgress(50)
        }

        // Step 2: 创建任务
        const title = file?.name || prompt.slice(0, 18) || "文本分析任务"
        const resp = await fetch(`${apiBase}/api/v1/tasks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title,
                input_type: inputType,
                description: prompt.trim() || `上传文件: ${file?.name}`,
                metadata: {
                    share_to_casebase: shareToCasebase,
                    analysis_focus: selectedFocus,
                    has_file: Boolean(file),
                },
            }),
        }).catch(() => null)

        setProgress(90)
        const taskId = resp?.ok ? (await resp.json()).id : crypto.randomUUID()
        setProgress(100)
        await new Promise((r) => setTimeout(r, 350))

        const query = new URLSearchParams({ type: inputType })
        if (fileUrl) query.set("url", fileUrl)
        else if (prompt.trim()) query.set("prompt", prompt.trim())
        if (prompt.trim()) query.set("prompt", prompt.trim())

        router.push(`/detect/${taskId}?${query.toString()}`)
    } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "上传失败，请重试"
        setError(msg)
        setUploading(false)
        setProgress(0)
    }
}, [router, selectedFocus, shareToCasebase])
```

- [ ] **Step 2: 验证**

启动前端和后端，上传一个小图片文件，确认：
1. 进度条先到 50%（上传完成），再到 100%
2. 跳转到 `/detect/{taskId}?type=image&url=https://...`（URL 是真实 Supabase signed URL，不是 mock://）

- [ ] **Step 3: Commit**

```bash
git add truthseeker-web/components/upload/FileUploader.tsx
git commit -m "feat: implement real file upload in FileUploader"
```

---

### Task 6: Dashboard 接入真实 Supabase 数据

**Files:**
- Modify: `truthseeker-web/components/dashboard/StatsOverview.tsx`

当前问题：stats 数组是硬编码数字（142857、38402 等），不反映真实数据。

- [ ] **Step 1: 修改 StatsOverview.tsx，从 Supabase 查询真实统计**

将文件顶部的 `"use client"` 保留，添加 Supabase 查询逻辑：

```typescript
"use client"

import { motion, useInView } from "motion/react"
import { useEffect, useRef, useState } from "react"
import { ShieldAlert, Zap, CloudLightning, Activity, Server, FileVideo2 } from "lucide-react"
import { createClient } from "@/lib/supabase/client"

interface DashboardStats {
    totalTasks: number
    deepfakeDetected: number
    avgResponseMs: number
    activeSessions: number
}

function useDashboardStats() {
    const [stats, setStats] = useState<DashboardStats>({
        totalTasks: 0,
        deepfakeDetected: 0,
        avgResponseMs: 89,
        activeSessions: 1,
    })

    useEffect(() => {
        const supabase = createClient()

        async function fetchStats() {
            // 总任务数
            const { count: total } = await supabase
                .from("tasks")
                .select("*", { count: "exact", head: true })

            // 已完成任务数（作为检测总量）
            const { count: completed } = await supabase
                .from("tasks")
                .select("*", { count: "exact", head: true })
                .eq("status", "completed")

            // 查询 result 中 verdict 为 forged 或 suspicious 的任务
            const { count: flagged } = await supabase
                .from("tasks")
                .select("*", { count: "exact", head: true })
                .not("result", "is", null)
                .in("result->>verdict", ["forged", "suspicious"])

            setStats({
                totalTasks: total ?? 0,
                deepfakeDetected: flagged ?? 0,
                avgResponseMs: 89,
                activeSessions: 1,
            })
        }

        fetchStats()

        // 订阅实时更新
        const channel = supabase
            .channel("tasks-stats")
            .on("postgres_changes", { event: "*", schema: "public", table: "tasks" }, fetchStats)
            .subscribe()

        return () => { supabase.removeChannel(channel) }
    }, [])

    return stats
}

// AnimatedNumber 组件保持不变
function AnimatedNumber({ value }: { value: number }) {
    const [displayValue, setDisplayValue] = useState(0)
    useEffect(() => {
        let start = 0
        const end = value
        const duration = 2000
        const increment = end / (duration / 16)
        const timer = setInterval(() => {
            start += increment
            if (start >= end) { clearInterval(timer); setDisplayValue(end) }
            else setDisplayValue(Math.floor(start))
        }, 16)
        return () => clearInterval(timer)
    }, [value])
    return <span>{displayValue.toLocaleString()}</span>
}

export function StatsOverview() {
    const containerRef = useRef(null)
    const dbStats = useDashboardStats()

    const stats = [
        { label: "累计检测总量", value: dbStats.totalTasks, icon: <Activity className="w-5 h-5" />, color: "from-blue-500 to-cyan-400" },
        { label: "深度伪造拦截", value: dbStats.deepfakeDetected, icon: <ShieldAlert className="w-5 h-5" />, color: "from-red-500 to-orange-400" },
        { label: "平均响应延时 (ms)", value: dbStats.avgResponseMs, icon: <Zap className="w-5 h-5" />, color: "from-emerald-400 to-green-500" },
        { label: "活跃节点并发", value: dbStats.activeSessions, icon: <Server className="w-5 h-5" />, color: "from-[#6366F1] to-[#A855F7]" },
    ]
    // ... 其余 JSX 保持不变，只替换 stats 数组来源
```

注意：JSX 渲染部分（`stats.map(...)` 以下）保持原文件不变，只替换文件顶部的 import 和 stats 数据来源。

- [ ] **Step 2: 验证**

打开 Dashboard，确认：
1. 初始加载时数字从 0 动画到真实值（如果数据库有数据）
2. 新建一个检测任务后，"累计检测总量"实时+1（Realtime 订阅生效）

- [ ] **Step 3: Commit**

```bash
git add truthseeker-web/components/dashboard/StatsOverview.tsx
git commit -m "feat: connect dashboard stats to real Supabase data"
```

---

### Task 7: 后端检测完成后更新任务状态并广播

**Files:**
- Modify: `truthseeker-api/app/api/v1/detect.py`

当前问题：检测完成后，tasks 表的 status 仍是 `pending`，result 字段为空；后端也没有向 Supabase Realtime 广播 final_verdict。

- [ ] **Step 1: 修改 detect.py，在 complete 事件后更新任务状态**

在 `sse_event_generator` 函数末尾（`yield complete 事件` 之前）添加任务状态更新逻辑：

```python
# 在 "# 完成" 注释之前插入：
# 更新任务状态到 Supabase
if final_verdict_data:
    try:
        supabase.table("tasks").update({
            "status": "completed",
            "result": final_verdict_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).execute()
    except Exception as e:
        print(f"[detect] Failed to update task status: {e}")
```

在函数顶部添加变量追踪 final_verdict：
```python
final_verdict_data = None  # 在 initial_state 定义之后
```

在处理 `final_verdict` 事件的 yield 之后添加：
```python
if updates.get("final_verdict"):
    final_verdict_data = updates["final_verdict"]  # 追踪最终裁决
    yield f"data: {json.dumps({'type': 'final_verdict', 'verdict': updates['final_verdict']})}\\n\\n"
```

在文件顶部添加 import：
```python
from app.utils.supabase_client import supabase
```

- [ ] **Step 2: 添加 Supabase Realtime 广播**

在更新任务状态之后，添加广播：

```python
# 广播到 Supabase Realtime（供专家会诊模式的其他用户接收）
try:
    supabase.realtime.channel(f"task:{task_id}").send_broadcast(
        "final_verdict",
        {"task_id": task_id, "verdict": final_verdict_data}
    )
except Exception as e:
    print(f"[detect] Realtime broadcast failed (non-critical): {e}")
```

- [ ] **Step 3: 验证**

运行一次完整检测后，通过 Supabase MCP 执行：
```sql
select id, status, result->>'verdict' as verdict from public.tasks order by created_at desc limit 5;
```
预期：最新任务的 status = `completed`，result 包含 verdict 字段。

- [ ] **Step 4: Commit**

```bash
git add truthseeker-api/app/api/v1/detect.py
git commit -m "feat: update task status and broadcast verdict on detection complete"
```

---

## 自检清单

- [ ] Task 1: tasks 表存在，RLS 启用，media bucket 创建
- [ ] Task 2: POST /api/v1/upload 返回真实 Supabase signed URL
- [ ] Task 3: 受保护路由返回 401（无 token 时），公开路由正常访问
- [ ] Task 4: .env.example 文件存在且包含所有必要变量
- [ ] Task 5: 上传文件后 URL 参数是真实 https:// 而非 mock://
- [ ] Task 6: Dashboard 数字反映 tasks 表真实数据
- [ ] Task 7: 检测完成后 tasks 表 status = completed，result 有值
