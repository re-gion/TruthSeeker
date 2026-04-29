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
| weasyprint | >=62.0 | PDF 输出 |
| markdown | >=3.7 | Markdown 转 HTML（PDF 生成） |
| Pillow | >=10.0.0 | 图片处理（PDF fallback、媒体元数据） |
| PyJWT | >=2.8.0,<3.0.0 | JWT 验证 |
| filetype | >=1.2.0 | 文件类型魔数校验 |
| pydantic-settings | >=2.8.0 | 环境变量配置管理 |
| python-dotenv | >=1.0.0 | .env 文件加载 |

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
EXA_BASE_URL=https://api.exa.ai
KIMI_PROVIDER=official
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6
KIMI_CODING_API_KEY=
KIMI_CODING_BASE_URL=https://api.kimi.com/coding/v1
KIMI_CODING_MODEL=kimi-k2.6
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

`APP_ENV=production` 时 `SUPABASE_JWT_SECRET` 不能为 `NOT_SET`，否则后端会拒绝启动。

## 备注

- 四个 Agent 共享 Kimi 2.6 原生多模态推理基座，运行时可通过 `KIMI_PROVIDER=official|coding` 在官方 API 与 Kimi coding plan 之间切换；两种方式都只配置 Kimi 2.6，不再配置 `moonshot-v1-128k` 模型回退。
- 当前运行时是 Kimi 2.6 自主推理 + 外部检测 API + LangGraph 的 FedPaRS-compatible 架构；FedPaRS 训练/推理底座仍是可替换检测器方向。
- 不要把真实密钥提交到仓库，只保留示例文件和本地 `.env` / `.env.local`。
