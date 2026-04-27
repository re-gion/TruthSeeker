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
| @xyflow/react | 待安装 | 情报溯源图谱交互画布 |

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
| weasyprint | >=62.0 | PDF 输出 |

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
VIRUSTOTAL_API_KEY=
EXA_API_KEY=
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.ai/v1
KIMI_MODEL=kimi-k2.6
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

`APP_ENV=production` 时 `SUPABASE_JWT_SECRET` 不能为 `NOT_SET`，否则后端会拒绝启动。

## 备注

- 当前运行时是 Kimi 2.6 + 外部检测 API + LangGraph 的 FedPaRS-compatible 架构；FedPaRS 训练/推理底座仍是可替换检测器方向。
- 不要把真实密钥提交到仓库，只保留示例文件和本地 `.env` / `.env.local`。
