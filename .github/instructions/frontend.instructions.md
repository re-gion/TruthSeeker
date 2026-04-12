---
applyTo: "truthseeker-web/**"
---

# TruthSeeker 前端开发规范

> 完整规范参见 `docs/FRONTEND_GUIDELINES.md`。本文件为 Copilot 专用速查规则。

## 版本锁定（禁止擅自升级）

| 包 | 版本 | 重要说明 |
|----|------|---------|
| Next.js | ^15.2.0 | App Router，Server Components 优先 |
| React | ^19.0.0 | 使用 `use()` hook，不需要 `useEffect` 获取数据 |
| Tailwind CSS | ^4.0.0 | CSS-first，无 `tailwind.config.js` |
| shadcn/ui | @canary | 必须用 `npx shadcn@canary`，不是 `@latest` |
| motion | ^12.9.2 | 包名已改，从 `"motion/react"` 导入 |
| @react-three/fiber | ^9.5.0 | R3F v9 |
| @react-three/drei | ^10.0.0 | **必须 v10**，v9 不兼容 React 19 |
| @supabase/ssr | ^0.5.0 | 替代已废弃的 auth-helpers |

---

## 关键导入规则

```tsx
// ✅ motion 正确导入
import { motion, AnimatePresence } from "motion/react"

// ❌ 错误 - 旧包名
import { motion } from "framer-motion"

// ✅ Supabase 浏览器客户端
import { createBrowserClient } from '@supabase/ssr'

// ✅ Supabase 服务端客户端
import { createServerClient } from '@supabase/ssr'

// ✅ Next.js 15 - Server Components 必须 await
import { cookies } from 'next/headers'
const cookieStore = await cookies()

// ❌ 错误 - 缺少 await
const cookieStore = cookies()
```

---

## Tailwind v4 配置规范

```css
/* app/globals.css - 正确写法 */
@import "tailwindcss";
@import "tw-animate-css";   /* ✅ 不是 tailwindcss-animate */

@theme {
  /* 品牌色 */
  --color-indigo-ai: #6366F1;
  --color-cyber-lime: #D4FF12;

  /* 深色主题背景 */
  --color-deep-space: #111828;
  --color-charcoal: #30363D;
  --color-ink-blue: #12131B;
  --color-steel-gray: #1F2937;

  /* 功能色 */
  --color-alert-red: #EF4444;
  --color-safety-green: #10B981;
  --color-warning-amber: #F59E0B;
  --color-info-cyan: #06B6D4;

  /* 渐变 */
  --gradient-primary: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%);
  --gradient-cyber: linear-gradient(90deg, #6366F1 0%, #D4FF12 100%);
}
```

---

## Next.js 15 开发规范

### Server vs Client Components

```tsx
// Server Component（默认，无需标注）
// ✅ 可以直接 async/await，可访问数据库、cookies
export default async function Page() {
  const cookieStore = await cookies()
  const data = await fetch(...)
  return <div>{data}</div>
}

// Client Component（需要交互、hooks、浏览器 API）
"use client"
import { useState } from "react"
export function InteractiveWidget() { ... }
```

### 路由结构约定

```
truthseeker-web/app/
├── (landing)/          # 路由组 - 首页布局
│   ├── layout.tsx
│   └── page.tsx
├── detect/             # 检测提交页
│   └── page.tsx
├── detect/[taskId]/    # 检测结果/实时页
│   └── page.tsx
├── dashboard/          # 历史任务看板
│   └── page.tsx
├── cases/              # 演示案例库
│   └── page.tsx
├── login/
│   └── page.tsx
└── signup/
    └── page.tsx
```

### Metadata 规范

```tsx
// 静态 metadata
export const metadata: Metadata = {
  title: 'TruthSeeker - Deepfake 检测',
  description: '...',
}

// 动态 metadata
export async function generateMetadata({ params }): Promise<Metadata> {
  return { title: `任务 ${params.taskId}` }
}
```

---

## 3D 场景规范（React Three Fiber）

```tsx
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Float } from '@react-three/drei'

// ✅ 标准 3D 场景结构
<Canvas
  camera={{ position: [0, 0, 10], fov: 50 }}
  gl={{ antialias: true, alpha: true }}
>
  <ambientLight intensity={0.5} />
  <pointLight position={[10, 10, 10]} color="#6366F1" intensity={1} />

  {/* 中心 - 媒体预览 */}
  <MediaPreview position={[0, 0, 0]} />

  {/* 四象限 Agent 面板 */}
  <ForensicPanel  position={[-4,  2, -2]} rotation={[0,  0.3, 0]} />
  <IntelPanel     position={[ 4,  2, -2]} rotation={[0, -0.3, 0]} />
  <InquisitorPanel position={[-4, -2, -2]} rotation={[0,  0.3, 0]} />
  <CommanderPanel position={[ 4, -2, -2]} rotation={[0, -0.3, 0]} />

  <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} />
</Canvas>

// ✅ 3D 组件必须在 'use client' 文件中，或通过动态导入
import dynamic from 'next/dynamic'
const BentoScene = dynamic(() => import('@/components/bento/BentoScene'), {
  ssr: false,
})
```

---

## 设计语言：Liquid Glass

```tsx
// 基础 Liquid Glass 卡片组件
const LiquidGlassCard = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn(
    "relative overflow-hidden rounded-2xl",
    "bg-gradient-to-br from-white/10 to-white/5",
    "backdrop-blur-xl",
    "border border-white/20",
    "shadow-[0_8px_32px_rgba(99,102,241,0.2)]",
    className
  )}>
    <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent opacity-50 pointer-events-none" />
    {children}
  </div>
)
```

---

## motion 动画规范

```tsx
import { motion } from "motion/react"

// 标准缓动定义
const EASINGS = {
  default: [0.4, 0, 0.2, 1],
  enter:   [0, 0, 0.2, 1],
  exit:    [0.4, 0, 1, 1],
  bounce:  [0.68, -0.55, 0.265, 1.55],
  cyber:   [0.87, 0, 0.13, 1],
} as const

// 标准时长（ms）
// Instant: 100  | Fast: 200 | Normal: 300 | Slow: 500 | Dramatic: 800

// 磁吸按钮
<motion.button
  whileHover={{ scale: 1.05 }}
  whileTap={{ scale: 0.95 }}
  transition={{ type: "spring", stiffness: 400, damping: 17 }}
/>

// 卡片抬升
<motion.div
  whileHover={{ y: -8, boxShadow: "0 20px 40px rgba(99,102,241,0.3)" }}
  transition={{ duration: 0.2, ease: EASINGS.enter }}
/>

// 减少动画（无障碍）
// 始终添加 prefers-reduced-motion 支持
```

---

## Agent 组件规范

```tsx
// AgentCard 状态类型
type AgentStatus = 'idle' | 'analyzing' | 'complete' | 'error'

// 四个 Agent 的标识色
const AGENT_COLORS = {
  forensics:  '#A855F7',  // 紫色 - 视听鉴伪Agent（扫描线动效）
  osint:      '#10B981',  // 绿色 - 情报溯源Agent（数据流动效）
  challenger: '#F59E0B',  // 黄色 - 逻辑质询Agent（闪电动效）
  commander:  '#06B6D4',  // 青色 - 研判指挥Agent（光环扩散）
} as const
```

---

## Supabase 实时订阅规范

```tsx
"use client"
import { createBrowserClient } from '@supabase/ssr'

// 频道命名规范：task:{taskId}
const channel = supabase
  .channel(`task:${taskId}`)
  .on('broadcast', { event: 'agent_log' }, ({ payload }) => {
    // 处理 Agent 日志
  })
  .on('broadcast', { event: 'verdict_ready' }, ({ payload }) => {
    // 处理最终裁决
  })
  .subscribe()

// 组件卸载时必须清理订阅
useEffect(() => {
  return () => { supabase.removeChannel(channel) }
}, [])
```

---

## 响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| Mobile | < 768px | 单列垂直滚动，底部固定导航 |
| Tablet | 768–1280px | 2D 网格，侧边抽屉导航 |
| Desktop | > 1280px | 完整 3D 场景，四象限布局 |

---

## 可访问性要求

- 所有颜色对比度符合 WCAG AA 标准
- 3D 场景提供 `prefers-reduced-motion` 降级方案
- 所有交互元素有键盘导航支持和可见焦点状态
- Agent 状态变化添加 `aria-live` 区域通知

---

## 常见陷阱

1. **3D 组件 SSR** - 包含 `Canvas` 的组件必须 `ssr: false` 动态导入
2. **Drei v9** - 不支持 React 19，必须用 v10
3. **motion 包名** - 从 `"motion/react"` 导入，非 `"framer-motion"`
4. **shadcn CLI** - 必须 `npx shadcn@canary`，`@latest` 不支持 Tailwind v4
5. **cookies()** - Next.js 15 中必须 `await cookies()`
6. **tw-animate-css** - 不是 `tailwindcss-animate`
