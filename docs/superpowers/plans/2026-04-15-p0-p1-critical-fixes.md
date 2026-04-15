# P0/P1 关键修复与功能完善 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 P0 安全/功能缺陷 + 完成 P1 数据库策略/索引/结构化日志/报告分享功能（排除 Dashboard 相关）

**Architecture:** 后端使用 FastAPI + Supabase（迁移通过 MCP apply_migration 执行），前端 Next.js App Router。所有数据库变更通过 Supabase 迁移完成，代码变更直接编辑。

**Tech Stack:** FastAPI 0.134, Python 3.13, Supabase (PostgreSQL), Next.js 16, React 19, Tailwind v4

---

## 调研修正

- ~~P0 #2: 挂载 `handle_new_user` 触发器~~ → **已确认触发器 `on_auth_user_created` 已存在且启用**，无需修复
- 实际 P0 任务为 4 项，P1（排除 Dashboard）为 5 项，共 9 项

## 文件变更清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `truthseeker-api/.env` | 添加 JWT_SECRET |
| 修改 | `truthseeker-api/app/main.py` | 添加全局异常处理器 + 结构化日志初始化 |
| 创建 | `truthseeker-api/app/middleware/exception_handler.py` | 统一异常处理器 |
| 修改 | `truthseeker-api/app/api/v1/tasks.py` | 添加 logger，修复静默错误 |
| 创建 | `truthseeker-api/app/api/v1/share.py` | 报告分享 API |
| 修改 | `truthseeker-api/app/api/v1/router.py` | 注册 share router |
| 创建 | `truthseeker-web/app/report/[taskId]/page.tsx` | 报告分享页面 |
| DB 迁移 | — | result 列、RLS 策略、索引 |

---

## Task 1: 添加 `result` 列到 tasks 表

**Files:**
- DB migration via Supabase MCP

- [ ] **Step 1: 执行迁移 — 添加 result 列**

```
mcp__supabase__apply_migration:
  name: add_result_column_to_tasks
  query: |
    ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS result jsonb DEFAULT NULL;
```

- [ ] **Step 2: 验证列已添加**

```
mcp__supabase__execute_sql:
  query: SELECT column_name FROM information_schema.columns WHERE table_name = 'tasks' AND column_name = 'result';
```

预期: 返回 `result` 行

---

## Task 2: 配置 SUPABASE_JWT_SECRET

**Files:**
- 修改: `truthseeker-api/.env`

- [ ] **Step 1: 在 .env 中添加 JWT_SECRET**

JWT Secret 来自 Supabase Dashboard → Settings → API → JWT Secret。需要用户手动获取并填入。

在 `truthseeker-api/.env` 末尾添加一行：
```
SUPABASE_JWT_SECRET=<用户需从 Supabase Dashboard 获取>
```

- [ ] **Step 2: 验证认证中间件启用**

启动后端，日志中应不再出现 "SUPABASE_JWT_SECRET not configured — auth middleware disabled" 警告。

---

## Task 3: 清理 tasks 表重复 RLS 策略

**Files:**
- DB migration via Supabase MCP

当前 tasks 表有 7 个策略，其中 3 组重复。需删除旧组，保留新组 + anon 策略。

- [ ] **Step 1: 执行迁移 — 删除重复策略**

```sql
-- 删除旧的重复策略（保留 users_own_* 组 + anon_tasks_insert）
DROP POLICY IF EXISTS "Users can insert own tasks" ON public.tasks;
DROP POLICY IF EXISTS "Users can update own tasks" ON public.tasks;
DROP POLICY IF EXISTS "Users can view own tasks" ON public.tasks;
```

- [ ] **Step 2: 验证剩余策略**

预期保留 4 个策略：
- `users_own_tasks_insert` (INSERT, auth.uid() = user_id)
- `users_own_tasks_select` (SELECT, auth.uid() = user_id)
- `users_own_tasks_update` (UPDATE, auth.uid() = user_id)
- `anon_tasks_insert` (INSERT, user_id IS NULL)

---

## Task 4: 实现全局异常处理器

**Files:**
- 创建: `truthseeker-api/app/middleware/exception_handler.py`
- 修改: `truthseeker-api/app/main.py`

- [ ] **Step 1: 创建异常处理器模块**

文件: `truthseeker-api/app/middleware/exception_handler.py`

```python
"""全局异常处理器 — 统一 API 错误响应格式"""
import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理 FastAPI HTTPException，统一返回格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：捕获所有未处理异常，返回 500"""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "服务器内部错误",
            "path": str(request.url.path),
        },
    )
```

- [ ] **Step 2: 在 main.py 中注册异常处理器**

在 `truthseeker-api/app/main.py` 中，`app = FastAPI(...)` 之后、中间件注册之前添加：

```python
from app.middleware.exception_handler import http_exception_handler, unhandled_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
```

- [ ] **Step 3: 修复 tasks.py 中的静默错误吞没**

在 `truthseeker-api/app/api/v1/tasks.py` 中：
- 顶部添加 `import logging` 和 `logger = logging.getLogger(__name__)`
- 将所有 `print(f"Error...")` 替换为 `logger.error("...")`

---

## Task 5: 添加 system_stats RLS 策略 + reports INSERT 策略 + 业务索引

**Files:**
- DB migration via Supabase MCP

- [ ] **Step 1: 执行迁移 — 添加 RLS 策略和索引**

```sql
-- system_stats: 允许 anon 和 authenticated 用户读取
CREATE POLICY "system_stats_select_all"
  ON public.system_stats FOR SELECT
  TO public
  USING (true);

-- reports: 允许 task owner 通过 service_role 或自身插入
CREATE POLICY "reports_insert_by_owner"
  ON public.reports FOR INSERT
  TO public
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.tasks
      WHERE tasks.id = reports.task_id
      AND (tasks.user_id = auth.uid() OR tasks.user_id IS NULL)
    )
  );

-- 业务索引
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON public.tasks (user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.tasks (status);
CREATE INDEX IF NOT EXISTS idx_agent_logs_task_id ON public.agent_logs (task_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_task_round ON public.agent_logs (task_id, round_number);
CREATE INDEX IF NOT EXISTS idx_analysis_states_task_id ON public.analysis_states (task_id);
CREATE INDEX IF NOT EXISTS idx_reports_task_id ON public.reports (task_id);
```

- [ ] **Step 2: 验证策略和索引**

```sql
SELECT policyname FROM pg_policies WHERE tablename IN ('system_stats', 'reports');
SELECT indexname FROM pg_indexes WHERE tablename IN ('tasks', 'agent_logs', 'analysis_states', 'reports');
```

---

## Task 6: 实现结构化日志

**Files:**
- 修改: `truthseeker-api/app/main.py`

- [ ] **Step 1: 在 main.py 中添加结构化日志配置**

在 `main.py` 的 lifespan 函数之前添加日志配置：

```python
import sys

def setup_logging():
    """配置结构化日志 — 所有模块统一格式"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # 降低第三方库噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

在 lifespan 函数开头调用 `setup_logging()`。

- [ ] **Step 2: 验证日志格式**

启动后端，确认日志输出格式为：
```
2026-04-15 12:00:00 | INFO     | app.main | TruthSeeker API starting - Supabase: https://...
```

---

## Task 7: 实现报告分享链接（后端 API）

**Files:**
- 创建: `truthseeker-api/app/api/v1/share.py`
- 修改: `truthseeker-api/app/api/v1/router.py`

设计：在 `reports` 表中添加 `share_token` 列（公开访问令牌），通过 `GET /api/v1/share/{token}` 无需认证即可查看报告。

- [ ] **Step 1: 数据库迁移 — 添加 share_token**

```sql
ALTER TABLE public.reports
  ADD COLUMN IF NOT EXISTS share_token text UNIQUE DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_reports_share_token ON public.reports (share_token);
```

- [ ] **Step 2: 创建 share API 端点**

文件: `truthseeker-api/app/api/v1/share.py`

```python
"""报告分享 API — 生成/访问公开分享链接"""
import logging
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.report_generator import generate_markdown_report
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class ShareResponse(BaseModel):
    share_token: str
    share_url: str


@router.post("/{task_id}", response_model=ShareResponse)
async def create_share_link(task_id: str):
    """为指定任务生成报告分享链接"""
    # 查找已有报告
    resp = supabase.table("reports").select("id, share_token").eq("task_id", task_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    report = resp.data[0]

    # 已有分享令牌则复用
    if report.get("share_token"):
        token = report["share_token"]
    else:
        token = secrets.token_urlsafe(16)
        supabase.table("reports").update({"share_token": token}).eq("id", report["id"]).execute()

    return ShareResponse(
        share_token=token,
        share_url=f"/report/{token}",
    )


@router.get("/{token}", response_model=dict)
async def get_shared_report(token: str):
    """通过分享令牌访问报告（无需认证）"""
    resp = supabase.table("reports").select("*, tasks(*)").eq("share_token", token).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")

    report = resp.data[0]
    task = report.get("tasks", {})

    # 生成 Markdown 内容
    try:
        md_content = await generate_markdown_report(task.get("id", report["task_id"]))
    except Exception as e:
        logger.error("Failed to generate shared report: %s", e)
        md_content = f"# 报告生成失败\n\n{e}"

    return {
        "report": {
            "verdict": report.get("verdict"),
            "confidence_overall": report.get("confidence_overall"),
            "summary": report.get("summary"),
            "generated_at": report.get("generated_at"),
        },
        "task": {
            "id": task.get("id"),
            "title": task.get("title"),
            "input_type": task.get("input_type"),
            "status": task.get("status"),
        },
        "markdown": md_content,
    }
```

- [ ] **Step 3: 注册 share router**

在 `truthseeker-api/app/api/v1/router.py` 中添加：

```python
from app.api.v1.share import router as share_router
api_router.include_router(share_router, prefix="/share", tags=["share"])
```

- [ ] **Step 4: 更新认证中间件的公共路径**

在 `truthseeker-api/app/middleware/auth.py` 的 `PUBLIC_PREFIXES` 中添加分享路径前缀：

```python
PUBLIC_PREFIXES = frozenset({"/api/v1/upload/", "/api/v1/share/"})
```

---

## Task 8: 实现报告分享页面（前端）

**Files:**
- 创建: `truthseeker-web/app/report/[taskId]/page.tsx`

- [ ] **Step 1: 创建报告分享页面**

文件: `truthseeker-web/app/report/[taskId]/page.tsx`

这是一个客户端组件，通过分享 token 获取报告数据并展示。页面包含：
- 顶部 TruthSeeker 品牌 logo + 标题
- 裁决结果卡片（verdict + confidence）
- Markdown 报告内容渲染
- 下载 MD/PDF 按钮
- 底部 "使用 TruthSeeker 进行深度鉴伪" CTA 链接

使用已有的 Tailwind 样式类（`glass-card`、`liquid-glass` 等）保持视觉一致性。

- [ ] **Step 2: 在 DetectConsole 中添加分享按钮**

在 `truthseeker-web/components/detect/DetectConsole.tsx` 的报告按钮区域（约第190行附近），添加 "分享报告" 按钮：

- 点击时调用 `POST /api/v1/share/${taskId}` 获取 share_token
- 将分享链接复制到剪贴板
- 显示成功提示

---

## Task 9: 验证 + 启动测试

- [ ] **Step 1: 启动后端验证**

```bash
cd truthseeker-api && python -m uvicorn app.main:app --reload --port 8000
```

验证：
- 日志格式正确（结构化）
- 无导入错误
- `/health` 返回 200
- 启动时无 "auth middleware disabled" 警告（如果 JWT_SECRET 已配置）

- [ ] **Step 2: 启动前端验证**

```bash
cd truthseeker-web && npm run dev
```

验证：
- 无编译错误
- `/report/test-token` 路由可访问（显示 404 页面即可）

- [ ] **Step 3: Supabase 安全审计**

运行 `mcp__supabase__get_advisors` 检查安全告警是否减少。
