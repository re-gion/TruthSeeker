# TECH_STACK.md -技术栈与依赖版本

> **版本锁定日期**:2026-03-01
> **规范等级**:强制 (Breaking Changes已确认)

---

##1.前端技术栈 (React19现代化生态)

###核心框架
|技术 |版本 |用途 |
|------|------|------|
| Next.js | ^15.2.0 | React框架，App Router模式 |
| React | ^19.0.0 | UI库 |
| React DOM | ^19.0.0 | DOM渲染器 |
| TypeScript | ^5.7.0 |类型安全 |

### UI/样式 (Tailwind v4 + CSS-first配置)
|技术 |版本 |用途 |
|------|------|------|
| Tailwind CSS | ^4.0.0 |原子化 CSS (Rust引擎) |
| @tailwindcss/postcss | ^4.0.0 | PostCSS插件 |
| shadcn/ui | canary |组件库基础 (Tailwind v4支持) |
| lucide-react | latest |图标库 |
| clsx | ^2.1.0 |条件类名合并 |
| tailwind-merge | ^2.6.0 | Tailwind类名去重 |

###动画与3D (⚠️包名已变更)
|技术 |版本 |用途 |导入规范 |
|------|------|------|----------|
| **motion** | ^12.9.2 |动画与交互 (原 Framer Motion) | `import { motion } from "motion/react"` |
| @react-three/fiber | ^9.5.0 | React Three.js封装 (React19兼容) | - |
| @react-three/drei | ^10.0.0 | R3F辅助组件 | - |
| three | ^0.172.0 |3D渲染引擎 | - |

> **重要**: Framer Motion已更名为 `motion`，所有导入必须使用 `import { motion } from "motion/react"`

###状态管理
|技术 |版本 |用途 |
|------|------|------|
| Zustand | ^5.0.0 |全局状态管理 |
| TanStack Query | ^5.66.0 |服务端状态缓存 |
| Immer | ^10.1.0 |不可变状态更新 |

### Supabase客户端 (⚠️ auth-helpers已弃用)
|技术 |版本 |用途 |
|------|------|------|
| @supabase/supabase-js | ^2.98.0 | Supabase客户端 |
| @supabase/ssr | ^0.5.0 | Next.js SSR认证辅助 |

> **重要**: `@supabase/auth-helpers`已废弃，必须使用 `@supabase/ssr`

---

##2.后端技术栈 (LangGraph v1.0架构)

###核心框架
|技术 |版本 |用途 |
|------|------|------|
| Python | ^3.11.0 |运行时 (最低3.10+) |
| FastAPI |0.134.0 | Web框架 |
| Uvicorn | ^0.34.0 | ASGI服务器 |
| Pydantic | ^2.10.6 |数据验证 |

###智能体框架 (⚠️ LangGraph v1.0+语法)
|技术 |版本 |用途 |
|------|------|------|
| **langgraph** | >=1.0.9 |多智能体工作流编排 |
| langchain-core | >=0.3.79 | LLM核心抽象 |
| langchain-openai | ^0.3.0 | OpenAI接口适配 |
| langchain-anthropic | ^0.3.0 | Anthropic接口适配 |

> **强制规范**:
> - Agent State必须使用 `TypedDict`定义，**禁止使用 Pydantic models**
> -摒弃废弃的 `create_react_agent`接口
> -使用 LangGraph v1.0+新 API: `StateGraph`, `START`, `END`

###数据库/存储
|技术 |版本 |用途 |
|------|------|------|
| supabase-py | ^2.13.0 | Supabase Python客户端 |
| asyncpg | ^0.30.0 |异步 PostgreSQL |
| pgvector | ^0.3.0 |向量扩展支持 |

###文件处理
|技术 |版本 |用途 |
|------|------|------|
| python-multipart | ^0.0.20 |文件上传解析 |
| aiofiles | ^24.1.0 |异步文件操作 |
| ffmpeg-python | ^0.2.0 |视频处理 |
| Pillow | ^11.1.0 |图像处理 |

### HTTP客户端
|技术 |版本 |用途 |
|------|------|------|
| httpx | ^0.28.0 |异步 HTTP请求 |
| aiohttp | ^3.11.0 |异步 Web客户端/服务器 |

---

##3.外部 API与服务

### Deepfake检测 API（候选）
|服务 |特点 |成本 |
|------|------|------|
| Microsoft Video Authenticator |微软官方，精度高 |按调用计费 |
| Sentinel (Truepic) |专业级，有免费额度 |分层定价 |
| Sensity |专注 Deepfake |企业级定价 |
| **推荐：Reality Defender** | API友好，适合集成 |有试用额度 |

###多模态大模型（候选）
|模型 |提供商 |适用场景 |
|------|--------|----------|
| GPT-4V | OpenAI |通用视觉分析 |
| Kimi-K2.5 |月之暗面 |中文优化好 |
| Gemini Pro Vision | Google |多模态能力强 |
| **推荐：Kimi-K2.5** |月之暗面 |国内访问稳定，中文法医术语理解好 |

###威胁情报 API
|服务 |用途 |
|------|------|
| VirusTotal API v3 | URL/域名/IP信誉查询 |
| URLVoid |恶意 URL检测 |
| AbuseIPDB |恶意 IP查询 |
| WhoisXML API |域名注册信息 |

---

##4. MCP/Skill使用规划

###开发阶段调用
| Skill/MCP |用途 |触发时机 |
|-----------|------|----------|
| `ui-ux-pro-max` | UI/UX设计指导 |前端组件开发前 |
| `frontend-design` |视觉设计实现 |复杂动效实现时 |
| `next-best-practices` | Next.js规范检查 |页面开发前后 |
| `vercel-react-best-practices` | React性能优化 |组件 Review时 |
| `tailwind-design-system` |样式系统构建 |主题配置时 |
| `supabase-postgres-best-practices` |数据库优化 | Schema设计时 |
| `mcp__exa__get_code_context_exa` |第三方 API示例搜索 |集成外部服务前 |
| `mcp__context7__query-docs` |文档查询 |遇到不熟悉的库时 |

###部署阶段调用
| MCP |用途 |
|-----|------|
| `mcp__vercel__deploy_to_vercel` |前端部署 |
| `mcp__vercel__get_runtime_logs` |运行时日志监控 |
| `mcp__supabase__apply_migration` |数据库迁移 |

---

##5.初始化命令速查

###前端项目初始化
```bash
#1.创建 Next.js15 + React19项目
npx create-next-app@latest truthseeker-web \
 --typescript \
 --tailwind \
 --eslint \
 --app \
 --no-src-dir

#2.安装 Tailwind v4 PostCSS插件
npm install -D @tailwindcss/postcss

#3.初始化 shadcn/ui (canary版本支持 Tailwind v4)
npx shadcn@canary init

#4.安装动画和3D库
npm install motion @react-three/fiber@^9.5.0 @react-three/drei@^10.0.0 three

#5.安装 Supabase客户端
npm install @supabase/supabase-js@^2.98.0 @supabase/ssr@^0.5.0
```

###后端项目初始化
```bash
#1.创建虚拟环境
python -m venv venv
source venv/bin/activate # Windows: venv\Scripts\activate

#2.安装核心依赖
pip install fastapi==0.134.0 uvicorn[standard]

#3.安装 LangGraph v1.0+
pip install langgraph>=1.0.9 langchain-core>=0.3.79

#4.安装其他依赖
pip install pydantic>=2.10.6 httpx aiofiles python-multipart
pip install supabase-py asyncpg
```

---

##6. Breaking Changes备忘

### Tailwind v4
- ❌不再使用 `tailwind.config.js`
- ✅改用 CSS-first配置：`@theme`指令在 `globals.css`中
- ❌ `@tailwind`指令被移除
- ✅改用 `@import "tailwindcss"`

### Motion (原 Framer Motion) v12
- ❌ `import { motion } from "framer-motion"`
- ✅ `import { motion } from "motion/react"`

### React Three Fiber v9
- ⚠️仅支持 React19
- ⚠️ `@react-three/drei`需要 v10配合

### LangGraph v1.0+
- ❌ `from langgraph.prebuilt import create_react_agent`
- ✅使用 `StateGraph` + `TypedDict`自定义工作流
- ⚠️ State必须用 `TypedDict`，不能用 Pydantic BaseModel

### Supabase Auth
- ❌ `@supabase/auth-helpers`
- ✅ `@supabase/ssr`

---

##7.环境变量清单

###前端 (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=
```

###后端 (.env)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
VIRUSTOTAL_API_KEY=
DEEPFAKE_API_KEY=
LANGSMITH_API_KEY= (可选)
```
