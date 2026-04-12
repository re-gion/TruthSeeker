---
applyTo: "truthseeker-api/**"
---

# TruthSeeker 后端开发规范

> 完整规范参见 `docs/BACKEND_STRUCTURE.md`。本文件为 Copilot 专用速查规则。

## 版本锁定（禁止擅自升级）

| 包 | 版本 | 重要说明 |
|----|------|---------|
| FastAPI | 0.134.0 | 固定版本 |
| LangGraph | >=1.0.9 | State **必须** TypedDict，禁止 Pydantic |
| Python | ^3.11 | 最低 3.10+ |

---

## LangGraph State 定义（最高优先级规则）

```python
# ✅ 正确：使用 TypedDict
from typing import TypedDict, Annotated, List, Optional
from operator import add

class EvidenceItem(TypedDict):
    type: str          # 'visual' | 'audio' | 'text' | 'osint'
    source: str        # 产生该证据的 Agent/Tool
    description: str
    confidence: float
    metadata: dict

class AgentLog(TypedDict):
    agent: str
    round: int
    type: str          # 'thinking' | 'action' | 'finding' | 'challenge' | 'conclusion'
    content: str
    timestamp: str

class TruthSeekerState(TypedDict):
    # 任务基础信息
    task_id: str
    user_id: str
    input_files: dict         # {modality: storage_path}
    priority_focus: str       # 'visual' | 'audio' | 'text' | 'balanced'

    # 辩论状态
    current_round: int
    max_rounds: int           # 默认 5
    convergence_threshold: float  # 默认 0.05

    # 各 Agent 评估结果
    forensics_result: Optional[dict]
    osint_result: Optional[dict]
    challenger_feedback: Optional[dict]

    # 证据板（Annotated[list, add] 表示追加而非覆盖）
    evidence_board: Annotated[List[EvidenceItem], add]
    confidence_history: List[dict]   # [{round: 1, scores: {...}}, ...]
    challenges: Annotated[List[dict], add]
    expert_opinions: List[dict]

    # 终止条件
    is_converged: bool
    termination_reason: Optional[str]

    # 最终结果
    final_verdict: Optional[dict]

    # SSE 日志流（追加模式）
    logs: Annotated[List[AgentLog], add]

# ❌ 严禁：不允许用 Pydantic BaseModel 定义 State
# from pydantic import BaseModel
# class TruthSeekerState(BaseModel):  # 运行时报错！
```

---

## LangGraph 图结构

```
START → [FORENSICS + OSINT + EXPERT_CHECK]（并行）
      → GATHER_EVIDENCE
      → CHALLENGER
      → (条件边) → COMMANDER → END
                → RETURN_TO_AGENTS（打回补充）
```

### 图编译与调用

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(TruthSeekerState)

# 添加节点
builder.add_node("forensics", forensics_node)
builder.add_node("osint", osint_node)
builder.add_node("gather", gather_evidence_node)
builder.add_node("challenger", challenger_node)
builder.add_node("commander", commander_node)

# 并行起始
builder.set_entry_point("forensics")  # 实际通过 Send() 并行

# 条件边
builder.add_conditional_edges(
    "challenger",
    challenger_route,
    {
        "proceed_to_commander": "commander",
        "return_to_forensics": "forensics",
        "return_to_osint": "osint",
    }
)
builder.add_edge("commander", END)

graph = builder.compile()

# 调用（同步）
result = graph.invoke(initial_state)

# 调用（流式，用于 SSE）
async for chunk in graph.astream(initial_state):
    yield chunk
```

### 收敛判断函数

```python
def check_convergence(state: TruthSeekerState) -> str:
    """判断是否达到收敛条件，返回路由字符串"""
    if state["current_round"] >= state["max_rounds"]:
        return "max_rounds_reached"

    history = state["confidence_history"]
    if len(history) >= 2:
        prev = history[-2]["scores"]
        curr = history[-1]["scores"]
        deltas = {k: abs(curr.get(k, 0) - prev.get(k, 0)) for k in set(prev) | set(curr)}
        if max(deltas.values(), default=1.0) < state["convergence_threshold"]:
            return "converged"

    return "continue"
```

---

## FastAPI 路由规范

```python
# app/api/v1/tasks.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", status_code=201)
async def create_task(
    payload: TaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """创建检测任务，后台启动 LangGraph 图"""
    task = await task_service.create(payload, current_user.id)
    background_tasks.add_task(run_graph, task.id)
    return task

# SSE 流式推送 Agent 日志
@router.get("/{task_id}/logs")
async def stream_logs(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    async def event_generator():
        async for event in task_service.stream_logs(task_id):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### API 端点总览

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/tasks` | 创建检测任务 |
| GET | `/api/v1/tasks/{id}` | 获取任务详情 |
| GET | `/api/v1/tasks/{id}/logs` | SSE Agent 日志流 |
| GET | `/api/v1/tasks/{id}/report` | 获取最终报告 |
| POST | `/api/v1/tasks/{id}/export` | 导出报告 (PDF/Markdown) |
| POST | `/api/v1/tasks/{id}/invite` | 邀请专家会诊 |
| POST | `/api/v1/opinions` | 提交专家意见（访客） |
| WS | `/ws/collaborate` | 专家实时协作 WebSocket |
| GET | `/api/v1/stats` | 系统统计数据 |
| GET | `/api/v1/cases/demo` | 获取演示案例库 |

---

## Pydantic 模型（仅用于 API 请求/响应，不用于 State）

```python
# app/models/task.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# ✅ Pydantic 只用于 API 的输入输出模型
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    input_type: Literal['video', 'audio', 'image', 'text', 'mixed']
    priority_focus: Literal['visual', 'audio', 'text', 'balanced'] = 'balanced'

class TaskResponse(BaseModel):
    id: str
    status: str
    progress: int
    created_at: datetime
```

---

## Supabase 数据库要点

### 任务状态流转

```
pending → preprocessing → analyzing → deliberating → completed / failed
```

### 核心表

| 表名 | 用途 |
|------|------|
| `profiles` | 用户（扩展 Supabase Auth） |
| `tasks` | 检测任务主表 |
| `analysis_states` | LangGraph State 持久化 |
| `agent_logs` | Agent 日志（SSE 数据源） |
| `reports` | 最终裁决报告 |
| `consultation_invites` | 专家邀请 |
| `expert_opinions` | 专家意见 |
| `audit_logs` | 操作审计（合规） |

### RLS 策略原则

```sql
-- 用户只能查看和操作自己的任务
create policy "Users can view own tasks"
  on public.tasks for select
  using (auth.uid() = user_id);

-- 管理员可见所有任务（在 using 子句中加 OR）
-- 分析状态对任务所有者只读
-- agent_logs 对任务所有者只读
```

### Supabase 客户端（Python）

```python
# app/utils/supabase_client.py
from supabase import create_client, Client
from app.config import settings

def get_supabase_admin() -> Client:
    """服务端使用 service_role key（绕过 RLS）"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
```

---

## Realtime 广播规范

```python
# 频道命名规范
CHANNEL_TASK = "task:{task_id}"        # 任务级实时更新
CHANNEL_USER = "user:{user_id}"        # 用户级通知
CHANNEL_STATS = "stats"                # 全局统计

# 事件类型
EVENTS = {
    "AGENT_LOG":      "agent_log",      # Agent 新日志
    "STATE_UPDATE":   "state_update",   # 状态变更
    "PROGRESS":       "progress",       # 进度更新
    "EXPERT_INVITE":  "expert_invite",  # 专家邀请
    "EXPERT_OPINION": "expert_opinion", # 专家意见
    "VERDICT_READY":  "verdict_ready",  # 最终裁决
}
```

---

## 安全规范

1. **文件上传限制**：视频 ≤500MB，图片 ≤20MB，校验 MIME 类型，存储桶隔离
2. **API 密钥管理**：外部 API 密钥存 Supabase Vault 或环境变量，不硬编码
3. **速率限制**：每用户每小时最多创建 10 个任务
4. **LLM 输出过滤**：对所有 LLM 输出做内容过滤，防止 Prompt Injection 影响下游判断
5. **JWT 验证**：所有 `/api/v1/` 路由必须通过 `Depends(get_current_user)` 验证

---

## 环境变量（`.env`）

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
VIRUSTOTAL_API_KEY=
DEEPFAKE_API_KEY=
```

---

## 目录结构

```
truthseeker-api/app/
├── main.py              # FastAPI 入口，注册路由、中间件
├── config.py            # 环境变量（Pydantic Settings）
├── api/v1/              # API 路由层
│   ├── router.py        # 聚合所有子路由
│   ├── tasks.py
│   ├── analysis.py
│   └── reports.py
├── agents/              # LangGraph 核心
│   ├── state.py         # TypedDict State 定义
│   ├── graph.py         # 图结构编译
│   ├── nodes/           # 四个 Agent 节点
│   │   ├── forensics.py
│   │   ├── osint.py
│   │   ├── challenger.py
│   │   └── commander.py
│   ├── edges/
│   │   └── conditions.py  # 收敛判断、路由逻辑
│   └── tools/           # Agent 可调用工具
│       ├── deepfake_api.py
│       ├── audio_analysis.py
│       ├── threat_intel.py
│       └── llm_vision.py
├── services/            # 业务服务层
├── models/              # Pydantic 请求/响应模型
└── utils/
    └── supabase_client.py
```

---

## 常见陷阱

1. **LangGraph State 用 Pydantic** - 运行时报错，必须用 `TypedDict`
2. **`create_react_agent` 已废弃** - LangGraph v1.0+ 改用 `create_agent`
3. **`add_messages` vs `add`** - messages 字段用 `add_messages`，列表追加用 `operator.add`
4. **uvicorn 入口路径** - 启动命令为 `uvicorn app.main:app`，不是 `uvicorn main:app`
5. **Supabase RLS** - 服务端操作使用 `service_role` key 绕过 RLS，前端用 `anon` key
