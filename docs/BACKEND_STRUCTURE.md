# BACKEND_STRUCTURE.md

##1. FastAPI目录结构

```
truthseeker-backend/
├── app/
│ ├── __init__.py
│ ├── main.py # FastAPI应用入口
│ ├── config.py #环境变量与配置
│ │
│ ├── api/ # API路由层
│ │ ├── __init__.py
│ │ ├── v1/
│ │ │ ├── __init__.py
│ │ │ ├── router.py # v1总路由聚合
│ │ │ ├── tasks.py #任务管理接口
│ │ │ ├── analysis.py #分析结果查询
│ │ │ ├── reports.py #报告导出接口
│ │ │ ├── users.py #用户管理（管理员）
│ │ │ └── websocket.py # WebSocket实时协作
│ │
│ ├── core/ #核心业务逻辑
│ │ ├── __init__.py
│ │ ├── security.py # JWT、密码哈希
│ │ ├── exceptions.py #自定义异常
│ │ └── middleware.py # CORS、日志、限流
│ │
│ ├── agents/ # LangGraph智能体
│ │ ├── __init__.py
│ │ ├── graph.py #主状态机图定义
│ │ ├── state.py # TypedDict状态定义
│ │ ├── nodes/ # Agent节点实现
│ │ │ ├── __init__.py
│ │ │ ├── forensics.py #视听鉴伪Agent Agent
│ │ │ ├── osint.py #情报溯源Agent Agent
│ │ │ ├── challenger.py #逻辑质询Agent Agent
│ │ │ └── commander.py #研判指挥Agent Agent
│ │ ├── edges/ #条件边逻辑
│ │ │ ├── __init__.py
│ │ │ └── conditions.py #收敛判断、路由逻辑
│ │ └── tools/ # Agent可调用的工具
│ │ ├── __init__.py
│ │ ├── deepfake_api.py # Deepfake检测 API
│ │ ├── audio_analysis.py #音频分析 API
│ │ ├── threat_intel.py #威胁情报查询
│ │ └── llm_vision.py #多模态大模型封装
│ │
│ ├── services/ #服务层
│ │ ├── __init__.py
│ │ ├── task_service.py #任务生命周期管理
│ │ ├── file_service.py #文件上传/处理
│ │ ├── realtime_service.py # Supabase Realtime封装
│ │ └── export_service.py #报告导出(PDF/Markdown)
│ │
│ ├── models/ # Pydantic模型
│ │ ├── __init__.py
│ │ ├── user.py #用户相关模型
│ │ ├── task.py #任务相关模型
│ │ ├── analysis.py #分析结果模型
│ │ └── report.py #报告模型
│ │
│ └── utils/ #工具函数
│ ├── __init__.py
│ ├── validators.py #输入验证
│ ├── converters.py #格式转换
│ └── logger.py #结构化日志
│
├── supabase/ # Supabase相关
│ ├── migrations/ #数据库迁移文件
│ ├── functions/ # Edge Functions
│ │ ├── video-preprocess/ #视频预处理（抽帧/压缩）
│ │ ├── audio-extract/ #音频提取
│ │ └── thumbnail-gen/ #缩略图生成
│ └── seed.sql #初始数据
│
├── tests/ #测试目录
├── requirements.txt # Python依赖
├── Dockerfile #容器化
└── README.md
```

##2. Supabase Schema设计

###2.1核心表结构

```sql
--用户表（扩展 Supabase Auth）
create table public.profiles (
 id uuid references auth.users on delete cascade primary key,
 username text unique not null,
 role text check (role in ('user', 'admin')) default 'user',
 avatar_url text,
 created_at timestamptz default now(),
 updated_at timestamptz default now()
);

--任务表
create table public.tasks (
 id uuid default gen_random_uuid() primary key,
 user_id uuid references public.profiles(id) on delete cascade not null,
 title text not null,
 description text,

 --输入内容（支持多模态）
 input_type text check (input_type in ('video', 'audio', 'image', 'text', 'mixed')) not null,
 priority_focus text check (priority_focus in ('visual', 'audio', 'text', 'balanced')) default 'balanced',

 --文件存储引用
 storage_paths jsonb default '{}', -- {video: 'path', audio: 'path', ...}

 --任务状态
 status text check (status in ('pending', 'preprocessing', 'analyzing', 'deliberating', 'completed', 'failed')) default 'pending',
 progress int check (progress between0 and100) default0,

 --时间戳
 created_at timestamptz default now(),
 started_at timestamptz,
 completed_at timestamptz,
 expires_at timestamptz default (now() + interval '7 days'), --自动删除期限

 --软删除
 deleted_at timestamptz
);

--分析状态表（LangGraph State持久化）
create table public.analysis_states (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id) on delete cascade not null,
 round_number int default1, --当前辩论轮次

 --各 Agent置信度评分
 forensics_score float check (forensics_score between0 and1),
 osint_score float check (osint_score between0 and1),
 convergence_delta float, --本轮收敛变化量

 --证据板（核心）
 evidence_board jsonb default '{
 "visual_evidence": [],
 "audio_evidence": [],
 "text_evidence": [],
 "osint_findings": [],
 "challenges": []
 }',

 --当前活跃 Agent
 current_agent text,

 --终止条件标记
 is_converged boolean default false,
 termination_reason text,

 created_at timestamptz default now(),
 updated_at timestamptz default now()
);

-- Agent日志表（用于 SSE推送和审计）
create table public.agent_logs (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id) on delete cascade not null,
 round_number int not null,
 agent_name text not null, -- 'forensics' | 'osint' | 'challenger' | 'commander'
 log_type text check (log_type in ('thinking', 'action', 'finding', 'challenge', 'conclusion')),
 content text not null,
 metadata jsonb default '{}', --关联的工具调用、API响应等
 timestamp timestamptz default now()
);

--专家会诊邀请表
create table public.consultation_invites (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id) on delete cascade not null,
 invited_by uuid references public.profiles(id) not null,
 invitee_email text not null,
 token text unique not null, --邀请令牌
 status text check (status in ('pending', 'accepted', 'expired')) default 'pending',
 expires_at timestamptz default (now() + interval '24 hours'),
 created_at timestamptz default now()
);

--专家意见表
create table public.expert_opinions (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id) on delete cascade not null,
 expert_id uuid references public.profiles(id),
 guest_name text, --未注册用户以访客身份
 opinion text not null,
 confidence int check (confidence between1 and5),
 inserted_at_round int, --插入到第几轮后
 created_at timestamptz default now()
);

--最终报告表
create table public.reports (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id) on delete cascade not null,
 verdict text check (verdict in ('authentic', 'suspicious', 'forged', 'inconclusive')) not null,
 confidence_overall float not null,
 summary text not null,
 key_evidence jsonb not null,
 recommendations jsonb default '[]',
 report_hash text, --完整性校验
 generated_at timestamptz default now()
);

--审计日志表（合规要求）
create table public.audit_logs (
 id uuid default gen_random_uuid() primary key,
 user_id uuid references public.profiles(id),
 action text not null, -- 'upload', 'view', 'download', 'delete', 'invite'
 resource_type text not null,
 resource_id uuid,
 ip_address inet,
 user_agent text,
 metadata jsonb,
 created_at timestamptz default now()
);

--系统统计表（数据大屏用）
create table public.system_stats (
 id serial primary key,
 date date unique default current_date,
 total_tasks int default0,
 completed_tasks int default0,
 avg_processing_time interval,
 threat_type_distribution jsonb default '{}',
 updated_at timestamptz default now()
);
```

###2.2 Row Level Security (RLS)策略

```sql
--用户只能看到自己的任务
alter table public.tasks enable row level security;
create policy "Users can view own tasks"
 on public.tasks for select
 using (auth.uid() = user_id or exists (
 select1 from public.profiles where id = auth.uid() and role = 'admin'
 ));

--只有创建者可以修改自己的任务
create policy "Users can insert own tasks"
 on public.tasks for insert
 with check (auth.uid() = user_id);

--分析状态对用户只读
create policy "Analysis states are viewable by task owner"
 on public.analysis_states for select
 using (exists (
 select1 from public.tasks where id = task_id and user_id = auth.uid()
 ));

-- Agent日志公开可读（用于实时展示）
create policy "Agent logs are viewable by task owner"
 on public.agent_logs for select
 using (exists (
 select1 from public.tasks where id = task_id and user_id = auth.uid()
 ));
```

###2.3 pgvector向量存储（未来扩展）

```sql
--启用 pgvector
create extension if not exists vector;

--历史案例向量库（用于相似案例检索）
create table public.case_embeddings (
 id uuid default gen_random_uuid() primary key,
 task_id uuid references public.tasks(id),
 embedding vector(1536), -- OpenAI/text-embedding-3-small
 metadata jsonb,
 created_at timestamptz default now()
);

--创建相似度搜索索引
create index on public.case_embeddings using ivfflat (embedding vector_cosine_ops);
```

##3. LangGraph v1.0+状态机设计

###3.1强制规范（LangGraph v1.0 Breaking Changes）

⚠️ **重要：LangGraph v1.0+必须使用 TypedDict定义 State，严禁使用 Pydantic BaseModel**

```python
# ✅正确：使用 TypedDict
from typing import TypedDict, Annotated, List, Optional
from operator import add

class TruthSeekerState(TypedDict):
 task_id: str
 current_round: int
 # ...

# ❌错误：不要使用 Pydantic BaseModel
# from pydantic import BaseModel
# class TruthSeekerState(BaseModel): #这是不允许的！
# pass
```

**v1.0关键变更：**
- `create_react_agent`已废弃，改用 `create_agent` (位于 `langchain.agents`)
- Python最低版本要求：3.10+
- State必须使用 `TypedDict`，不再支持 Pydantic models
- Graph编译后通过 `.invoke()` / `.astream()`调用

###3.2 State类型定义（TypedDict）

```python
from typing import TypedDict, Annotated, List, Optional
from operator import add

class EvidenceItem(TypedDict):
 type: str # 'visual' | 'audio' | 'text' | 'osint'
 source: str #哪个 Agent/Tool产生
 description: str
 confidence: float
 metadata: dict

class AgentLog(TypedDict):
 agent: str
 round: int
 type: str
 content: str
 timestamp: str

class TruthSeekerState(TypedDict):
 #任务基础信息
 task_id: str
 user_id: str
 input_files: dict # {modality: storage_path}
 priority_focus: str

 #辩论状态
 current_round: int
 max_rounds: int #默认5
 convergence_threshold: float #默认0.05

 #各 Agent评估结果
 forensics_result: Optional[dict]
 osint_result: Optional[dict]
 challenger_feedback: Optional[dict]

 #证据板（累积所有发现）
 evidence_board: Annotated[List[EvidenceItem], add]

 #置信度历史（用于收敛判断）
 confidence_history: List[dict] # [{round:1, scores: {...}}, ...]

 #质询记录
 challenges: Annotated[List[dict], add]

 #专家介入
 expert_opinions: List[dict]

 #终止条件
 is_converged: bool
 termination_reason: Optional[str]

 #最终结果
 final_verdict: Optional[dict]

 #日志流（用于 SSE）
 logs: Annotated[List[AgentLog], add]
```

###3.2图结构拓扑

```
 ┌─────────────────┐
 │ START_NODE │
 │ (初始化状态) │
 └────────┬────────┘
 │
 ┌──────────────┼──────────────┐
 ▼ ▼ ▼
 ┌────────────┐ ┌────────────┐ ┌────────────┐
 │ FORENSICS │ │ OSINT │ │ EXPERT │
 │ Agent │ │ Agent │ │ CHECK │
 │ (并行执行) │ │ (并行执行) │ │ (有人介入?) │
 └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
 │ │ │
 └───────────────┼───────────────┘
 ▼
 ┌─────────────────┐
 │ GATHER_EVIDENCE │
 │ (证据汇总) │
 └────────┬────────┘
 │
 ▼
 ┌─────────────────┐
 │ CHALLENGER │
 │ (逻辑质询Agent) │
 │审视证据充分性 │
 └────────┬────────┘
 │
 ┌────────────┴────────────┐
 │条件边:是否需要补充? │
 └────────────┬────────────┘
 │
 ┌────────────┼────────────┐
 ▼ │ ▼
 ┌────────────┐ │ ┌─────────────────┐
 │ RETURN_TO │◄──────┘ │ COMMANDER │
 │ AGENTS │ (继续调查) │ (研判指挥Agent) │
 │ (打回补充) │ │输出最终报告 │
 └────────────┘ └────────┬────────┘
 │
 ▼
 ┌─────────────────┐
 │ END_NODE │
 │ (保存/推送) │
 └─────────────────┘
```

###3.3条件边逻辑

```python
#收敛判断函数
def check_convergence(state: TruthSeekerState) -> str:
 """判断是否达到收敛条件"""

 #1.检查最大轮数
 if state["current_round"] >= state["max_rounds"]:
 return "max_rounds_reached"

 #2.计算置信度变化
 history = state["confidence_history"]
 if len(history) >=2:
 prev = history[-2]["scores"]
 curr = history[-1]["scores"]

 #计算各维度变化
 deltas = {
 k: abs(curr.get(k,0) - prev.get(k,0))
 for k in set(prev) | set(curr)
 }
 max_delta = max(deltas.values()) if deltas else1.0

 #如果连续两轮变化都小于阈值，判定收敛
 if max_delta < state["convergence_threshold"]:
 return "converged"

 #3.检查是否有专家介入等待
 if state.get("expert_opinions") and any(
 op.get("status") == "pending" for op in state["expert_opinions"]
 ):
 return "awaiting_expert"

 return "continue"

#质询官路由
def challenger_route(state: TruthSeekerState) -> str:
 """质询官决定下一步走向"""
 feedback = state.get("challenger_feedback", {})

 if feedback.get("requires_more_evidence", False):
 #指定需要补充的调查方向
 target = feedback.get("target_agent", "forensics")
 return f"return_to_{target}"

 return "proceed_to_commander"
```

##4. Supabase Edge Functions

###4.1视频预处理 Function

```typescript
// supabase/functions/video-preprocess/index.ts
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'

serve(async (req) => {
 const { taskId, videoPath } = await req.json()

 //1.使用 FFmpeg抽关键帧
 //2.生成低分辨率预览
 //3.提取音频轨道
 //4.更新任务状态

 return new Response(
 JSON.stringify({
 success: true,
 frames: [...],
 audioPath: '...',
 thumbnail: '...'
 }),
 { headers: { 'Content-Type': 'application/json' } }
 )
})
```

###4.2 Realtime Broadcast配置

```typescript
//频道命名规范
const CHANNELS = {
 //任务级频道：task:{taskId}
 task: (taskId: string) => `task:${taskId}`,

 //用户级频道：user:{userId}
 user: (userId: string) => `user:${userId}`,

 //全局统计频道：stats
 stats: 'stats'
}

//事件类型
const EVENTS = {
 AGENT_LOG: 'agent_log', // Agent新日志
 STATE_UPDATE: 'state_update', //状态变更
 PROGRESS: 'progress', //进度更新
 EXPERT_INVITE: 'expert_invite', //专家邀请
 EXPERT_OPINION: 'expert_opinion', //专家意见
 VERDICT_READY: 'verdict_ready' //最终裁决
}
```

##5. API端点概览

|方法 |路径 |描述 |
|------|------|------|
| POST | /api/v1/tasks |创建检测任务 |
| GET | /api/v1/tasks/{id} |获取任务详情 |
| GET | /api/v1/tasks/{id}/logs |获取 Agent日志流 |
| GET | /api/v1/tasks/{id}/report |获取最终报告 |
| POST | /api/v1/tasks/{id}/export |导出报告(PDF/Markdown) |
| POST | /api/v1/tasks/{id}/invite |邀请专家会诊 |
| POST | /api/v1/opinions |提交专家意见（访客） |
| WS | /ws/collaborate |专家实时协作 WebSocket |
| GET | /api/v1/stats |系统统计数据 |
| GET | /api/v1/cases/demo |获取演示案例库 |

##6.安全考虑

1. **文件上传**：限制大小（视频500MB，图片20MB），扫描 MIME类型，存储桶隔离
2. **API密钥**：外部 API密钥存储在 Supabase Vault或环境变量
3. **速率限制**：基于 Redis/内存的任务创建频率限制（每用户每小时10个）
4. **内容安全**：对 LLM输出做过滤，防止 Prompt Injection影响下游判断
