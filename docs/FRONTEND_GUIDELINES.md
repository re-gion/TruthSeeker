# FRONTEND_GUIDELINES.md - UI/UX规范与组件标准

##1.设计哲学

TruthSeeker的前端设计遵循"数字法医实验室"的隐喻——冷静、精确、充满科技感，同时通过动态可视化展现AI推理的思维过程。界面本身就是产品能力的展示。

---

##2.配色方案

###主色调
|名称 |色值 |用途 |
|------|------|------|
| Indigo AI | `#6366F1` |主品牌色，代表科技与AI智慧 |
| Cyber Lime | `#D4FF12` |强调色，代表活力、预警与赛博感 |

###深色主题（默认）
|名称 |色值 |用途 |
|------|------|------|
| Deep Space | `#0A0A0F` |主背景 |
| Deep Space 2 | `#111828` |次级深色背景 |
| Charcoal | `#1A1F2E` |卡片/面板背景 |
| Ink Blue | `#12131B` |极暗处/遮罩 |
| Steel Gray | `#1F2937` |次级背景 |

###文本色
|名称 |色值 |用途 |
|------|------|------|
| Platinum | `#C0C0C0` |正文文本 |
| Pure White | `#FFFFFF` |标题/强调 |
| Muted | `#6B7280` |禁用/次要文本 |

###功能色
|名称 |色值 |用途 |
|------|------|------|
| Alert Red | `#EF4444` |高危/伪造确认 |
| Safety Green | `#10B981` |安全/真实确认 |
| Warning Amber | `#F59E0B` |可疑/需复核 |
| Info Cyan | `#06B6D4` |信息提示 |

###渐变定义
项目不定义自定义渐变 CSS 变量；渐变统一用 Tailwind gradient 工具类组合 `@theme` 颜色令牌实现。示例：

```css
/* 主渐变 -科技蓝紫：bg-gradient-to-br from-indigo-500 via-violet-500 to-purple-600 */
/* 赛博光晕：bg-gradient-to-r from-indigo-500 to-lime-400 */
/* 深色面板：bg-gradient-to-b from-slate-600/90 to-slate-700/95 */
```

---

##3.2026前沿设计语言

### Liquid Glass（液体玻璃）
替代传统毛玻璃效果，创造更具流动感的半透明发光效果。

```tsx
//基础Liquid Glass卡片
const LiquidGlassCard = ({ children }) => (
 <div className="
 relative overflow-hidden rounded-2xl
 bg-gradient-to-br from-white/10 to-white/5
 backdrop-blur-xl
 border border-white/20
 shadow-[0_8px_32px_rgba(99,102,241,0.2)]
 before:absolute before:inset-0
 before:bg-gradient-to-br before:from-white/20 before:to-transparent
 before:opacity-50
 ">
 {children}
 </div>
);
```

**关键特性：**
-边缘呼吸光晕（Agent活跃时增强）
-有机曲线边框（border-radius非对称）
-多层渐变叠加创造深度

### Bento Box布局
控制台采用灵活的网格系统，每个模块独立又相互关联。

```
┌─────────────────────────────────────────┐
│ [电子取证Agent] │ [情报溯源Agent] │
│ AgentCard + 证据板 │ AgentCard + 溯源图谱 │
├──────────────────┼──────────────────────┤
│ [逻辑质询Agent] │ [研判指挥Agent] │
│ AgentCard + 质询时间线 │ AgentCard + 裁决摘要 │
│          [中央证据板]（跨四象限）        │
└─────────────────────────────────────────┘
```

实际实现见 `DetectConsole.tsx`：四象限为四个 Agent 面板 + 中央证据板；3D 仅作为背景（BentoScene），不可拖拽旋转（见第 4 节）。

**响应式断点：**
- Desktop (>1440px):4列网格
- Laptop (1024-1440px):2x2网格
- Tablet (768-1024px):堆叠布局
- Mobile (<768px):单列滑动

### Purposeful Micro-interactions

**重要：使用 `motion` v12+新包名和导入方式**

```tsx
// ✅正确：使用 motion v12新导入方式
import { motion } from "motion/react"

//磁吸按钮
<motion.button
 whileHover={{ scale:1.05 }}
 whileTap={{ scale:0.95 }}
 transition={{ type: "spring", stiffness:400, damping:17 }}
/>

//卡片抬升
<motion.div
 whileHover={{
 y: -8,
 boxShadow: "020px40px rgba(99,102,241,0.3)"
 }}
/>
```

**❌废弃：不再使用旧包名**
```tsx
//不要使用
import { motion } from "framer-motion" //已废弃！
```

**加载/思考状态：**
- Agent思考时：边框流光动画
- API调用中：脉冲圆点 +打字机日志
-数据处理：波形可视化

---

##4.3D空间设计

###空间布局概念
当前 `BentoScene` 采用“3D 背景 + CSS Bento 网格”的混合实现：React Three Fiber 负责背景玻璃碎片、发光核与鼠标位置驱动的轻微视差旋转，主要信息面板仍由 DOM/CSS 渲染，保证可读性、响应式和可测试性。不要把它误写成 OrbitControls 驱动的可拖拽四象限 3D 面板。

```tsx
//当前 3D 背景结构
<Canvas camera={{ position: [0,0,8], fov:50 }}>
 <ambientLight intensity={0.5} />
 <pointLight position={[10,10,10]} color="#6366F1" />

 {/*背景玻璃碎片、发光核心和数据流装饰 */}
 <SceneContent />
</Canvas>
```

###交互动效
- **鼠标跟随**：轻微视差偏移
- **信息面板**：由 DOM/CSS Bento 网格承载，避免 3D 文本造成可读性和无障碍问题
- **过渡动画**：使用 `motion`（来自 `motion/react`）和 `gsap` 实现平滑动画过渡

---

##5.组件规范

### Button
项目按钮组件为 `FluidGlassButton`（`components/ui/FluidGlassButton.tsx`），无 variant prop；主次/危险等视觉差异通过外层类组合区分。示例：

```tsx
// 主按钮 -渐变背景 +发光边框 +悬停流光
<FluidGlassButton onClick={startDetect}>开始检测</FluidGlassButton>

// 危险操作 -红色强调类组合
<button className="bg-red-500/20 border border-red-400/40 ...">删除任务</button>
```

### Card变体
```tsx
// Agent卡片
<AgentCard
 name="电子取证Agent"
 icon={<Microscope />}
 status="analyzing" // idle | analyzing | complete | error
 confidence={0.85}
>
 {/*内容 */}
</AgentCard>

```

### 数据可视化组件
项目中实际存在并使用的可视化组件：

- `EvidenceTimeline`（`components/detect/EvidenceTimeline.tsx`）— 垂直证据时间轴，Agent 颜色编码 + 动画
- `ProvenanceGraphView`（`components/detect/ProvenanceGraphView.tsx`）— 溯源图谱，@xyflow/react 画布（拖拽/缩放/节点详情/引用面板）
- `AgentCard`（`components/agents/AgentCard.tsx`）— Agent 状态卡片（idle | analyzing | complete | error）
- 数据大屏图表（ECharts：趋势/玫瑰图/裁决柱/雷达/Sankey，见 `DashboardClient.tsx`）

置信度等单值指标直接由卡片内数字 + 颜色呈现，不依赖独立仪表盘组件。

---

## 6. 字体规范

### 字体族
```css
/* 界面、正文与展示标题：自托管 IBM Plex Sans SC */
--font-interface: 'IBM Plex Sans SC', 'Microsoft YaHei UI', 'PingFang SC', 'Noto Sans SC', system-ui, sans-serif;

/* 日志、代码、哈希、ID、时间戳：自托管 IBM Plex Mono；中文回退界面字体 */
--font-telemetry: 'IBM Plex Mono', 'IBM Plex Sans SC', ui-monospace, 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;

/* 仅用于前端可见的 TruthSeeker 品牌字标；研判报告不使用 */
--font-brand: 'Unbounded', 'IBM Plex Sans SC', system-ui, sans-serif;
```

字体文件位于 `truthseeker-web/public/fonts/ibm-plex/`，使用 IBM 官方 split WOFF2 与 OFL 许可证；运行时不得请求第三方字体服务。字体资产只提供 400、500、600 三个字重：新增代码应使用 normal/medium/semibold；历史 `font-bold`/`font-black` 会由浏览器匹配到最接近的 600，不应继续扩散。不再使用正楷、系统默认衬线字体或未随项目加载的等宽字体名称。

TruthSeeker 英文字标使用自托管 `Unbounded` 600（SemiBold），字体与 OFL 许可证位于 `truthseeker-web/public/fonts/unbounded/`。前端统一通过 `BrandWordmark` 或 `.brand-wordmark` 使用；不要把 Unbounded 扩展到中文正文、普通英文正文或 `app/report/` 研判报告页面。

### 字号层级

> 以下为设计规范建议值；项目未定义 `--text-*` 令牌，页面实现直接使用 Tailwind 尺寸类。

| 令牌 | 大小/行高 | 字重 | 用途 |
|------|------|------|------|
| Display | `clamp(40px, 7vw, 110px)` | 600 | Landing 主标题 |
| Title | 24/32px | 600 | 页面标题 |
| Title Small | 18/26px | 600 | 区块与卡片标题 |
| Body Reading | 16/26px | 400 | 报告、协同长文 |
| Body | 14/22px | 400 | 检测台默认正文 |
| Body Small | 13/20px | 400 | 紧凑卡片、次级列表 |
| Label | 13/18px | 500 | 表头、导航、字段名 |
| Caption | 12/16px | 400/500 | 标签、时间戳 |

数字纵向比较统一启用 `tabular-nums`。`font-mono` 只用于技术数据；普通中文说明使用界面字体。`tracking-widest` 只用于短英文/数字标签，不用于连续中文。

---

##7.动画规范

###缓动函数
```ts
const easings = {
 //标准
 default: [0.4,0,0.2,1],
 //进入
 enter: [0,0,0.2,1],
 //离开
 exit: [0.4,0,1,1],
 //弹性
 bounce: [0.68, -0.55,0.265,1.55],
 //赛博感
 cyber: [0.87,0,0.13,1],
};
```

###时长规范
|类型 |时长 |用途 |
|------|------|------|
| Instant |100ms |微交互反馈 |
| Fast |200ms |悬停状态 |
| Normal |300ms |界面切换 |
| Slow |500ms |重要过渡 |
| Dramatic |800ms |3D变换 |

### Agent专属动效
| Agent |活跃状态效果 |
|-------|-------------|
|电子取证Agent |紫色扫描线从上到下扫过面板 |
|情报溯源Agent |绿色数据包沿连接线流动，最终图谱视图显示节点和边 |
|逻辑质询Agent |黄色闪电图标闪烁 |
|研判指挥Agent |蓝色光环向外扩散 |

---

##8.响应式策略

###桌面优先（>1280px）
-完整 3D 背景场景展示
-四 Agent 面板 + 中央证据板布局
-悬浮操作面板（协同入口、回顶按钮等）

###平板适配（768-1280px）
-面板改为 2D 网格堆叠
-触摸友好的按钮尺寸（当前未实现抽屉导航）

###移动端（<768px）
-单列垂直滚动
-3D 背景保留但弱化（未实现底部固定导航与轮播卡片）

---

##9.可访问性要求

-所有颜色对比度符合WCAG AA标准
-支持键盘导航（Tab顺序合理）
-屏幕阅读器友好的ARIA标签
-减少动画偏好设置（prefers-reduced-motion）
-焦点状态清晰可见
