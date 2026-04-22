# IMPLEMENTATION_PLAN.md
# TruthSeeker分阶段实施计划

## 文档版本信息
- **版本**: v2.0 (已验证)
- **最后更新**: 2026-03-01
- **验证状态**: 已通过Exa MCP深度验证技术栈版本

---

## 总体时间线

```
Week1-2   Week3-4   Week5-6   Week7-8
   |         |         |         |
   v         v         v         v
[Layer1] -> [Layer2] -> [Layer3] -> [Polish]
核心功能   全模态支持  协作+视觉   竞赛优化
```

**关键原则**: 严格按Layer优先级执行，L3的3D效果可裁剪以确保M1-M3里程碑按时交付。

---

## Layer1: 核心鉴伪能力（MVP）

**目标**: 实现视频检测的基础流程，确保有一个可演示的最小可用产品

### Week1: 基础设施搭建

#### Day1-2: 项目初始化 ⭐【已修正】

**前端：Next.js 16 + shadcn/ui初始化**

```bash
# 1. 创建Next.js 16项目（内置Tailwind v4 + React 19）
npx create-next-app@latest truthseeker-web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir

cd truthseeker-web

# 2. 初始化shadcn/ui（必须使用canary版本支持Tailwind v4 + React 19）
npx shadcn@canary init

# 3. 安装核心依赖
# ⚠️ 注意：framer-motion已更名为motion（v12.x）
npm install motion @react-three/fiber@^9.5.0 @react-three/drei@^10.0.0 three

# 4. Supabase客户端
npm install @supabase/supabase-js @supabase/ssr
```

**Tailwind v4 CSS-first主题配置** ⭐【新增】

编辑 `app/globals.css`:
```css
@import "tailwindcss";
@import "tw-animate-css";  /* 注意：tailwindcss-animate已弃用 */

@theme {
  /* TruthSeeker品牌色 */
  --color-indigo-ai: #6366F1;
  --color-cyber-lime: #D4FF12;
  --color-deep-space: #0A0A0F;
  --color-neural-white: #F8FAFC;

  /* shadcn/ui基础变量 */
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));
  --color-popover: hsl(var(--popover));
  --color-primary: hsl(var(--primary));
  --color-secondary: hsl(var(--secondary));
  --color-muted: hsl(var(--muted));
  --color-accent: hsl(var(--accent));
  --color-destructive: hsl(var(--destructive));
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-ring: hsl(var(--ring));
}

@custom-variant dark (&:is(.dark *));
```

**后端：FastAPI项目结构搭建** ⭐【已修正】

```bash
mkdir truthseeker-api
cd truthseeker-api

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖（版本已锁定）
pip install fastapi==0.134.0 uvicorn[standard] python-multipart
pip install langgraph>=1.0.9 langchain-core>=0.3.79 pydantic>=2.10.6
pip install python-dotenv httpx aiofiles

# 注意：LangGraph v1.0+强制使用TypedDict定义State，禁止使用Pydantic BaseModel
```

**Supabase项目创建**
- 在Supabase Dashboard创建新项目
- 记录Project URL和Publishable Key（格式：`sb_publishable_...`）
- 启用Email Auth provider

**环境变量模板**

`.env.local` (前端):
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

`.env` (后端):
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=...
OPENAI_API_KEY=sk-...
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.ai/v1
APP_ENV=development
```

---

#### Day3-4: 基础UI框架

- [ ] 实现基础布局组件（Header, Main Layout）
- [ ] 实现文件上传组件（支持视频拖拽上传）
- [ ] 配置Tailwind v4主题色（通过globals.css中的@theme）
- [ ] 实现简单的加载状态展示

**Motion导入示例** ⭐【已修正】
```tsx
// ✅ 正确：从motion/react导入
import { motion } from "motion/react"

// ❌ 错误：不要从framer-motion导入
// import { motion } from "framer-motion"
```

---

#### Day5-7: Supabase集成 ⭐【时间延长】

- [ ] 配置Supabase Client（@supabase/ssr方式）
- [ ] 实现用户认证（邮箱/密码注册登录）
- [ ] 设计`tasks`表基础Schema
- [ ] 实现任务创建和查询API
- [ ] **Day7**: 连接测试与错误处理边界

**Supabase Client配置示例** ⭐【新增】
```ts
// lib/supabase/client.ts
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  )
}
```

---

### Week2: 双Agent核心流程

#### Day8-10: LangGraph基础 ⭐【重要提示】

- [ ] 安装LangGraph、LangChain依赖
- [ ] 设计基础State结构（**必须使用TypedDict**）
- [ ] 实现视听鉴伪Agent
  - 视频抽帧逻辑
  - 调用Deepfake检测API（ 请先利用Exa MCP搜索Deepfake检测API，如果有可用API请使用，后期我去申请API并配置，否则请模拟实现）
  - 输出结构化证据
- [ ] 实现研判指挥Agent
  - 接收法医报告
  - 生成最终判定

**LangGraph v1.0+ State定义规范** ⭐【已修正】
```python
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages

# ✅ 正确：使用TypedDict + Annotated
class TruthSeekerState(TypedDict):
    task_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    evidence_list: List[dict]
    forensics_report: dict
    final_verdict: dict
    current_round: int
    max_rounds: int

# ❌ 错误：禁止使用Pydantic BaseModel定义State
# from pydantic import BaseModel
# class TruthSeekerState(BaseModel):  # 不要这样做！
#     task_id: str
```

---

#### Day11-12: 基础Bento布局 ⭐【SSE延后】

- [ ] 实现静态四宫格Bento Grid布局
- [ ] 面板基础样式（等待后续添加Liquid Glass效果）
- [ ] 响应式适配检查

---

#### Day13-14: SSE实时推送 + MVP整合 ⭐【调整】

- [ ] FastAPI SSE端点实现
- [ ] 前端EventSource连接
- [ ] 实现打字机效果的日志展示
- [ ] 端到端流程打通
- [ ] 修复关键Bug
- [ ] 准备Layer1演示脚本

**SSE实现要点**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

@app.post("/api/v1/detect/stream")
async def detect_stream(request: DetectRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {{'type': 'start', 'task_id': '{task_id}'}}\n\n"

        async for event in agent_workflow.astream(initial_state):
            yield f"data: {json.dumps(event)}\n\n"

        yield f"data: {{'type': 'complete'}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx防缓冲
        }
    )
```

**Layer1交付物**:
- 可上传视频并查看检测结果的基础版本
- 双Agent简单协作流程
- 基础Bento布局展示
- SSE实时日志推送

---

## Layer2: 全模态与四Agent完整辩论

**目标**: 扩展至全模态支持，实现完整的四Agent动态辩论机制

### Week3: 多模态扩展

#### Day15-17: 音频与图片支持

- [ ] 扩展上传组件支持音频、图片
- [ ] 音频特征提取（频谱分析）
- [ ] 图片EXIF元数据解析
- [ ] 更新State结构支持多模态输入

---

#### Day18-19: 文本链接处理

- [ ] URL提取与验证
- [ ] 网页内容抓取（标题、正文、截图）
- [ ] Whois信息查询集成

---

#### Day20-21: 情报溯源Agent

- [ ] 实现OSINT分析逻辑
- [ ] 集成VirusTotal API
- [ ] 威胁情报关联展示

---

### Week4: 质询官与收敛机制

#### Day22-24: 逻辑质询Agent

- [ ] 设计质疑策略（置信度阈值、矛盾检测）
- [ ] 实现条件边逻辑（打回重审）
- [ ] 质询历史记录追踪

---

#### Day25-26: 动态收敛算法

- [ ] 实现权重变化计算
- [ ] 收敛判定逻辑（连续两轮变化<阈值）
- [ ] 最大轮数兜底机制

**收敛判定示例**
```python
def should_converge(state: TruthSeekerState) -> str:
    """判断是否收敛，决定是继续还是结束"""
    current_weights = state["agent_weights"]
    previous_weights = state["previous_weights"]

    if not previous_weights:
        return "continue"

    # 计算权重变化
    changes = [
        abs(current_weights[a] - previous_weights[a])
        for a in current_weights
    ]
    max_change = max(changes)

    # 收敛条件：最大变化<5%且至少辩论了2轮
    if max_change < 0.05 and state["current_round"] >= 2:
        return "converge"

    # 最大轮数兜底
    if state["current_round"] >= state["max_rounds"]:
        return "converge"

    return "continue"
```

---

#### Day27-28: 完整流程整合

- [ ] 四Agent协同调试
- [ ] 复杂案例测试（音画不同步、深度伪造+恶意链接）
- [ ] 性能优化（减少不必要的API调用）

**Layer2交付物**:
- 支持视频/音频/图片/文本的全模态检测
- 四Agent动态辩论可视化
- 自动收敛判定机制

---

## Layer3: 专家会诊与3D UI ⭐【顺序调整】

**目标**: 实现人机协同的专家会诊模式和2026前沿视觉体验

**调整说明**: 考虑到竞赛演示价值，将专家会诊（核心差异化功能）优先于3D效果（但是3D效果也很重要，最后尽可能要实现一个炫酷、高端的3D效果！要保证评委的第一印象要好）。

### Week5: 专家会诊与Realtime ⭐【优先】

#### Day29-31: Supabase Realtime集成

- [ ] Broadcast通道配置（Agent状态流）
- [ ] Presence实现（在线用户感知）
- [ ] 多端状态同步测试

**Realtime架构**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   用户A     │◄───►│  Supabase   │◄───►│   用户B     │
│  (主持人)   │     │  Realtime   │     │  (专家)     │
└─────────────┘     └─────────────┘     └─────────────┘
                           ▲
                           │
                    ┌──────┴──────┐
                    │   Agent     │
                    │   状态流     │
                    └─────────────┘
```

---

#### Day32-34: 专家会诊模式

- [ ] 邀请机制（生成邀请码/链接）
- [ ] 会诊权限控制
- [ ] 人工介入节点设计
- [ ] 会诊意见记录与展示

---

#### Day35-36: 报告与导出

- [ ] Markdown报告生成
- [ ] PDF导出功能
- [ ] 报告分享链接

---

### Week6: 3D Bento Box实现 ⭐

#### Day37-39: React Three Fiber基础

- [ ] R3F场景搭建
- [ ] 四个面板的3D空间定位
- [ ] 相机控制与视角切换
- [ ] 基础光照和材质

**R3F v9.5 + React 19兼容说明** ⭐【新增】
```tsx
// ✅ 正确的R3F v9.5导入方式
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment } from '@react-three/drei'

// 注意：@react-three/drei v10目前为RC状态，但支持React 19
```

---

#### Day40-42: Liquid Glass效果

- [ ] 自定义Shader实现流动光泽
- [ ] Agent活跃状态的呼吸光晕
- [ ] 边框发光与半透明效果
- [ ] 鼠标交互反馈（悬停高亮）

---

#### Day43-44: 动画与过渡

- [ ] 面板间切换的流畅动画
- [ ] Motion与R3F的协同
- [ ] 滚动视差效果（报告页面）
- [ ] 微交互动画（按钮、卡片）

**Motion + R3F协同示例** ⭐【已修正】
```tsx
import { motion } from "motion/react"  // ✅ 注意导入路径
import { Canvas } from '@react-three/fiber'

// 2D UI动画
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  transition={{ duration: 0.5 }}
>
  {/* 3D Canvas */}
  <Canvas>
    <AgentPanel3D />
  </Canvas>
</motion.div>
```

**Layer3交付物**:
- 专家会诊实时协作（核心）
- 完整的报告导出功能
- 3D空间切换的沉浸式界面（很重要，尽可能实现）
- Liquid Glass视觉效果（很重要，尽可能实现）

---

## Polish: 竞赛优化与演示准备

### Week7: 竞赛功能完善 ⭐【任务合并】

#### Day45-51: 竞赛演示套件

原Day45-47、Day48-49、Day50-51合并为一个统一任务组：

- [ ] **演示案例库**
  - 内置5-10个典型案例（Deepfake、诈骗视频等）
  - 案例分类标签
  - 一键加载演示

- [ ] **数据大屏**
  - 系统统计仪表盘
  - 实时检测数量展示
  - 威胁类型分布图表

- [ ] **实时对抗演示**
  - 快速制作假视频的工具建议
  - 即时上传检测流程优化
  - 对比展示效果增强

---

### Week8: 最终优化与文档

#### Day52-54: 性能优化

- [ ] 视频压缩与转码优化
- [ ] API响应缓存
- [ ] 前端代码分割与懒加载

---

#### Day55-56: 安全加固

- [ ] 输入验证与过滤
- [ ] 速率限制实现
- [ ] 敏感数据脱敏检查

---

#### Day57-60: 文档与部署

- [ ] 编写用户操作手册
- [ ] 部署到Vercel
- [ ] 准备竞赛答辩PPT
- [ ] 录制演示视频

**部署检查清单**
```bash
# Vercel部署前检查
- [ ] next.config.ts中output: 'standalone'配置
- [ ] 环境变量在Vercel Dashboard中配置
- [ ] Supabase允许Vercel域名CORS
- [ ] Python后端部署到Render/Railway
```

---

## 风险与应对 ⭐【已更新】

| 风险点 | 影响 | 应对措施 |
|--------|------|----------|
| Deepfake API不稳定 | 高 | 提前申请多个服务账号，实现智能降级；准备模拟数据 |
| 3D性能问题 | 中 | 尽可能实现，如果不能实现， 在用户明确说降级后采取CSS降级方案（backdrop-filter实现伪玻璃效果），确保基础功能可用 |
| Supabase额度超限 | 中 | 监控使用量，必要时切换到自建Postgres；启用连接池 |
| 大模型API延迟高 | 中 | 增加加载动画，优化提示词减少token；实现流式响应 |
| @react-three/drei v10 RC稳定性 | 中 | 密切关注官方发布，如遇问题可降级至CSS 3D变换方案 |
| 时间不足 | 高 | 严格按Layer优先级，L3的3D效果可完全裁剪，保留专家会诊功能 |

---

## 关键里程碑检查点

- [ ] **M1 (Day14)**: MVP可演示视频检测
  - 阻塞项：双Agent流程跑通、SSE正常推送

- [ ] **M2 (Day28)**: 四Agent辩论完整运行
  - 阻塞项：收敛算法稳定、多模态输入正常

- [ ] **M3 (Day44)**: 专家会诊可用（3D UI很重要，尽可能实现，保证评委的第一印象；除非用户明确说降级后采取CSS降级方案，否则3D UI必须实现 ）
  - 阻塞项：Realtime同步正常、邀请机制可用

- [ ] **M4 (Day60)**: 竞赛提交版本完成
  - 阻塞项：部署成功、演示视频录制

---

## 开发规范

### Git工作流
- 分支命名: `layer1/video-upload`, `layer2/osint-agent`
- Commit规范: `feat:`, `fix:`, `docs:`, `refactor:`前缀
- 每日push，避免本地代码丢失

### 代码审查清单
- [ ] TypeScript类型完整
- [ ] 错误边界处理（React Error Boundary）
- [ ] Loading状态覆盖
- [ ] 移动端适配检查
- [ ] 控制台无报错
- [ ] **LangGraph State使用TypedDict而非Pydantic** ⭐【新增】

### 测试策略
- **Unit Test**: 核心工具函数（Jest）
- **Integration Test**: API端点（pytest）
- **E2E Test**: 关键用户流程（Playwright）

---

## 附录：关键版本锁定 ⭐【新增】

### 前端依赖
```json
{
  "next": "16.1.6",
  "react": "^19.0.0",
  "tailwindcss": "^4.0.0",
  "@tailwindcss/postcss": "^4.0.0",
  "motion": "^12.34.3",
  "@react-three/fiber": "^9.5.0",
  "@react-three/drei": "^10.7.7",
  "@supabase/supabase-js": "^2.98.0",
  "@supabase/ssr": "^0.8.0"
}
```

### 后端依赖
```txt
fastapi==0.134.0
uvicorn[standard]
langgraph>=1.0.9
langchain-core>=0.3.79
pydantic>=2.10.6
python-multipart
httpx
aiofiles
```

### 重要变更备忘
1. **framer-motion → motion**: 包名已变更，导入改为 `from "motion/react"`
2. **tailwindcss-animate → tw-animate-css**: Tailwind v4使用新的动画包
3. **@supabase/auth-helpers → @supabase/ssr**: auth-helpers已弃用
4. **LangGraph State**: v1.0+强制使用TypedDict，禁止Pydantic BaseModel
5. **shadcn CLI**: 必须使用`npx shadcn@canary init`支持Tailwind v4
