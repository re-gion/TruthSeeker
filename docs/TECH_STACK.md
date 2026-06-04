# TECH_STACK

> 该文件用于记录当前仓库真实依赖和环境变量约定，以仓库中的 `package.json`、`requirements.txt` 和 `app/config.py` 为准。

## 前端

| 技术 | 版本 | 用途 |
| --- | --- | --- |
| Next.js | 16.1.6 | App Router 前端框架 |
| React | 19.2.3 | UI 框架 |
| React DOM | 19.2.3 | DOM 渲染 |
| TypeScript | ^5 | 类型系统 |
| Tailwind CSS | ^4 | 样式系统 |
| @tailwindcss/postcss | ^4 | Tailwind PostCSS 插件 |
| `motion` | ^12.34.3 | 动效与交互 |
| @supabase/supabase-js | ^2.98.0 | Supabase 客户端 |
| @supabase/ssr | ^0.8.0 | SSR 认证辅助 |
| lucide-react | ^0.576.0 | 图标库 |
| @xyflow/react | ^12.10.2 | 情报溯源图谱交互画布 |
| `three` | ^0.183.2 | 3D 引擎 |
| `gsap` | ^3.14.2 | 高级动画库 |
| `echarts` / `echarts-for-react` | ^6.0.0 / ^3.0.6 | 数据大屏图表 |
| `react-markdown` / `remark-gfm` | ^10.1.0 / ^4.0.1 | Markdown 渲染（报告分享页） |
| `postprocessing` | ^6.38.3 | 3D 后处理特效 |

### 前端脚本

- `npm run dev` - 开发服务
- `npm run build` - 生产构建
- `npm run start` - 生产运行
- `npm run lint` - ESLint
- `npm run typecheck` - TypeScript 检查
- `npm run test` - lint + typecheck 的仓库级 smoke gate

## 后端

| 技术 | 版本 | 用途 |
| --- | --- | --- |
| Python | 3.11+ | 运行时 |
| FastAPI | 0.134.0 | Web 框架 |
| Uvicorn | >=0.34.0 | ASGI 服务器 |
| Pydantic | >=2.10.6 | 数据验证 |
| langgraph | >=1.0.9 | 多智能体编排 |
| langchain-core | >=0.3.79 | LLM 抽象层 |
| langchain-openai | >=0.3.0 | OpenAI 适配 |
| supabase | >=2.15.0 | Supabase Python 客户端 |
| httpx | >=0.28.0 | HTTP 客户端 |
| aiofiles | >=24.1.0 | 文件操作 |
| fpdf2 | >=2.8.0 | 文本型 PDF 输出 |
| Pillow | >=10.0.0 | 图片处理（PDF 兜底、媒体元数据） |
| PyJWT | >=2.8.0,<3.0.0 | JWT 验证 |
| filetype | >=1.2.0 | 文件类型魔数校验 |
| pydantic-settings | >=2.8.0 | 环境变量配置管理 |
| python-dotenv | >=1.0.0 | .env 文件加载 |
| pgvector | Supabase 扩展 | 公开案例库 RAG 与个人经验库 RAG 向量检索 |

## 环境变量

### 前端 `.env.local`

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 后端 `.env`

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=NOT_SET

REALITY_DEFENDER_API_KEY=
AIGC_IMAGE_PROVIDER=sightengine
AIGC_IMAGE_FALLBACK_PROVIDER=reality_defender
SIGHTENGINE_API_USER=
SIGHTENGINE_API_SECRET=
VIRUSTOTAL_API_KEY=
EXA_API_KEY=
EXA_BASE_URL=https://api.exa.ai
DOMAIN_PROVENANCE_ENABLED=true
WHOISXML_API_KEY=
WHOISXML_TIMEOUT_SECONDS=20
TEXT_AIGC_DETECTOR_ENABLED=true
TEXT_AIGC_AI_THRESHOLD=0.6
AGENT_LLM_PROVIDER=kimi-k2.5
AGENT_LLM_MAX_OUTPUT_TOKENS=4096
KIMI_PROVIDER=official
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5
KIMI_CODING_API_KEY=
KIMI_CODING_BASE_URL=https://api.kimi.com/coding/v1
KIMI_CODING_MODEL=kimi-k2.5
KIMI_SILICONFLOW_API_KEY=
KIMI_SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
KIMI_SILICONFLOW_MODEL=Pro/moonshotai/Kimi-K2.5
MIMO_API_KEY=
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5
MIMO_THINKING=enabled
CASE_RAG_ENABLED=true
CASE_RAG_TOP_K=5
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-8B
EMBEDDING_DIMENSIONS=1024
# 以下当前未被代码直接使用，保留用于未来 LLM 提供商切换
OPENAI_API_KEY=
QWEN_API_KEY=

APP_ENV=development
FRONTEND_URL=http://localhost:3000
MAX_ROUNDS=3
CONVERGENCE_THRESHOLD=0.08
```

兼容别名由 `app/config.py` 继续支持，主要包括：

- `Reality_Defender`
- `Virus_Total`
- `Kimi_API_KEY`
- `Kimi_Base_URL`
- `Sightengine_API_User`
- `Sightengine_API_Secret`
- `WhoisXML_API_KEY`

`APP_ENV=production` 时 `SUPABASE_JWT_SECRET` 不能为 `NOT_SET`，否则后端会拒绝启动。

## 备注

- 四个 Agent 共享可配置的原生多模态推理基座；默认使用 Kimi 2.5，并在调用 Kimi K2.5 时禁用 thinking。运行时可通过 `AGENT_LLM_PROVIDER=kimi-k2.5|mimo` 选择 K2.5 或小米 MiMo Token Plan；选择 K2.5 时再通过 `KIMI_PROVIDER=official|coding|siliconflow` 在 Kimi 官方 API、Kimi coding plan 和 SiliconFlow K2.5 之间切换；`mimo` 使用独立的 `MIMO_BASE_URL`、`MIMO_API_KEY`、`MIMO_MODEL=mimo-v2.5`、`MIMO_THINKING=enabled|disabled`。这些配置只影响 Agent LLM，不替换 Sightengine、Reality Defender、VirusTotal、Exa 或 embedding API。
- Agent LLM 能力边界：Kimi K2.5 输入 `text,image,video`、上下文 262144 tokens、本系统固定 thinking disabled；MiMo `mimo-v2.5` 输入 `text,image`、上下文 1048576 tokens、官方输出上限 131072 tokens，支持显式 thinking enabled/disabled。TruthSeeker 当前用 `AGENT_LLM_MAX_OUTPUT_TOKENS=4096` 统一限制单次 Agent LLM 输出。
- 图片 AIGC 检测默认使用 Sightengine `genai`，通过 `AIGC_IMAGE_PROVIDER=sightengine`、`SIGHTENGINE_API_USER` 和 `SIGHTENGINE_API_SECRET` 启用；Reality Defender 保留为音视频合成/篡改检测和图片检测降级备份。系统主字段使用 `aigc_*`，不再把图片 `AI_GENERATED` 结果上浮为 Deepfake 概率。
- 文本 AIGC 检测使用内部工具，通过 `TEXT_AIGC_DETECTOR_ENABLED=true` 和 `TEXT_AIGC_AI_THRESHOLD` 控制。Forensics/OSINT 都会把结果以 `ai_text_detector` 写入工具矩阵，融合 Kimi 文本判断、本地统计特征和社工诱导特征；结果只作为概率性线索，不单独定性。
- 域名溯源使用 WhoisXML WHOIS + DNS Lookup + IP Geolocation，通过 `DOMAIN_PROVENANCE_ENABLED=true` 和 `WHOISXML_API_KEY` 启用；未配置 key 时 OSINT 会记录结构化降级。DNS Lookup 优先解析完整主机名的 A/AAAA，必要时跟随 CNAME，再回退注册域；WHOIS 可用但 DNS Lookup/IP Geolocation 403 时按 `partial` 处理，通常表示对应 WhoisXML 子产品权限或额度受限。
- 公开案例库 RAG 和个人经验库 RAG 复用独立 embedding 配置，默认接入 SiliconFlow OpenAI-compatible `POST /v1/embeddings`，模型为 `Qwen/Qwen3-VL-Embedding-8B`，维度固定 1024。只需在本地 `.env` 填入 `EMBEDDING_API_KEY` 并运行对应迁移/索引流程即可启用。
- 当前运行时是 Kimi 2.5 自主推理 + 内部文本/案例工具 + 外部媒体与情报 API + LangGraph 的 FedPaRS-compatible 架构；FedPaRS 训练/推理底座仍是可替换检测器方向。
- 不要把真实密钥提交到仓库，只保留示例文件和本地 `.env` / `.env.local`。
