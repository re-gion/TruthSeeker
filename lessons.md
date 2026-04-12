# TruthSeeker开发错误记录本

> **使用说明**:记录开发过程中犯下的所有错误，分析根本原因，制定预防措施。定期回顾，避免重复犯错。

---

##错误记录表

|日期 |模块 |错误描述 |根本原因 |解决方案 |预防措施 |状态 |
|------|------|----------|----------|----------|----------|------|
| | | | | | | |

---

##按类别归档

### 🔴 LangGraph相关

<!--记录 State定义、Agent实现、工作流编排等错误 -->

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| | | | |

**关键规范** (来自 BACKEND_STRUCTURE.md):
- ✅ State必须用 `TypedDict`定义
- ❌禁止用 `Pydantic BaseModel`定义 State
- ✅使用 `langchain.agents`新接口
- ❌ `create_react_agent`已废弃

---

### 🟠前端相关

#### Motion/动画

<!--记录 framer-motion迁移到 motion的问题 -->

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| 2026-03-03 | HeroSection Hook 违规 | Hook (useState/useEffect) 必须在早期 return 之前调用 | React Docs |
| 2026-03-03 | SVG 路径 d 属性错误 | d 属性不支持百分比，需配合 viewBox 使用数值坐标 | SVG Spec |
| 2026-03-10 | Next.js App Router 转场时出现页面跳闪到目标界面 | 不要用 useEffect+setTimeout 延迟切换渲染 children，新页面实际上已经同时渲染。应使用 key={pathname} 重新挂载全屏遮罩，利用 overlay 滑出动画自然遮盖突然更新的 DOM | Next.js App Router 渲染机制 |

**关键规范** (来自 FRONTEND_GUIDELINES.md):
- ✅导入: `import { motion } from "motion/react"`
- ❌旧导入: `from "framer-motion"`

#### Tailwind v4

<!--记录 CSS-first配置相关问题 -->

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| | | | |

**关键规范**:
- ✅使用 `@import "tailwindcss"`
- ✅主题变量在 `@theme`中定义
- ❌不再使用 `tailwind.config.js`
- ✅动画包: `tw-animate-css`
- ❌旧包: `tailwindcss-animate`

#### React Three Fiber

<!--记录 R3F v9 + React19兼容性问题 -->

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| 2026-03-12 | Fluid Glass 渲染为实心色块 | MeshTransmissionMaterial 在缺少 Environment 或特定 GL 配置时无法正确处理背景折射 | 确保 Canvas GL 配置 alpha:true，并考虑使用 Environment 贴图 |
| | | | |

**关键规范**:
- ✅ R3F: `^9.5.0`
- ✅ Drei: `^10.0.0` (RC版本支持 React19)
- ❌ Drei v9不支持 React19
- ⚠️ MeshTransmissionMaterial: 必须配置环境贴图或背景，否则折射效果会失效变为实心色块。

#### Supabase

<!--记录 Auth和 Realtime相关问题 -->

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| | | | |

**关键规范**:
- ✅使用 `@supabase/ssr`
- ❌ `@supabase/auth-helpers`已废弃
- ⚠️ Next.js15中 `cookies()`必须 await

---

### 🟡后端/API相关

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| 2026-03-15 | 后端虚拟环境 python 路径失效 (指向不存在的 C:\Python314\python.exe) | 重新创建虚拟环境 `venv_new` 并重新安装 `requirements.txt` | Python venv docs |

---

### 🟢数据库相关

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| | | | |

---

### 🔵部署/DevOps相关

|日期 |错误描述 |解决方案 |参考文档 |
|------|----------|----------|----------|
| | | | |

---

##常见陷阱速查

基于 TECH_STACK.md的 Breaking Changes:

1. **Motion v12**
 -包名: `framer-motion` → `motion`
 -导入: `from "framer-motion"` → `from "motion/react"`

2. **Tailwind CSS v4**
 -配置: JS config → CSS-first `@theme`
 - PostCSS: `tailwindcss` → `@tailwindcss/postcss`
 -导入: `@tailwind`三行 → `@import "tailwindcss"`
 -动画: `tailwindcss-animate` → `tw-animate-css`

3. **React Three Fiber v9**
 -仅支持 React19
 - Drei需要 v10 (RC)

4. **Supabase Auth**
 - `auth-helpers` → `ssr`

5. **LangGraph v1.0+**
 - State: Pydantic → TypedDict
 - Agent: `create_react_agent` → `langchain.agents`

6. **shadcn/ui**
 - CLI: `shadcn@latest` → `shadcn@canary` (for Tailwind v4)

---

##经验总结区

###架构设计经验

<!--记录架构决策的得失 -->

###性能优化经验

<!--记录性能瓶颈和优化方案 -->

###调试技巧

<!--记录高效的调试方法 -->

---

*最后更新: 2026-03-03*
*总错误数: 2*
*重复错误率: 0%*
