# TruthSeeker API

TruthSeeker 的 FastAPI 后端，负责任务创建、文件上传、检测流、报告、情报溯源图谱和专家会诊入口。

## 技术栈

- FastAPI 0.134
- Uvicorn
- LangGraph 1.x
- Pydantic 2
- Supabase Python Client
- WeasyPrint

## 开发

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认访问地址：

- 后端 API: `http://localhost:8000`
- 前端地址: `http://localhost:3000`

## 环境变量

复制 [`.env.example`](./.env.example) 为 `.env` 后填写：

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=NOT_SET
REALITY_DEFENDER_API_KEY=
VIRUSTOTAL_API_KEY=
EXA_API_KEY=
KIMI_PROVIDER=official
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6
KIMI_CODING_API_KEY=
KIMI_CODING_BASE_URL=https://api.kimi.com/coding/v1
KIMI_CODING_MODEL=kimi-k2.6
OPENAI_API_KEY=
QWEN_API_KEY=
FRONTEND_URL=http://localhost:3000
MAX_ROUNDS=5
CONVERGENCE_THRESHOLD=0.08
```

说明：

- `APP_ENV=production` 时必须配置真实 `SUPABASE_JWT_SECRET`，否则后端会拒绝启动；本地开发设为 `NOT_SET` 时认证中间件会跳过。
- `Reality_Defender`、`Kimi_API_KEY`、`Virus_Total`、`Kimi_Base_URL` 仍保留为兼容旧环境名的别名。
- 当前运行时默认以 Kimi 2.6 作为四 Agent 的原生多模态推理基座；可通过 `KIMI_PROVIDER=official|coding` 手动选择官方 API 或 Kimi coding plan。Reality Defender、VirusTotal 和 Exa 作为专业工具接入，所有工具失败都必须结构化降级。

## 目录概览

- `app/api/v1/` - HTTP 接口
- `app/agents/` - LangGraph 智能体、阶段路由、工具和图谱构建
- `app/services/` - 报告和数据服务
- `app/utils/` - Supabase 等基础工具

## 备注

- 对外协议仍保留 `forensics/osint/challenger/commander`，其中 `forensics` 的用户可见语义已升级为电子取证 Agent。
- 图谱复用 `osint_result.provenance_graph` 和 `final_verdict.provenance_graph`，不新增数据库表。
- 真实密钥只放在本地 `.env`，不要提交到仓库。
