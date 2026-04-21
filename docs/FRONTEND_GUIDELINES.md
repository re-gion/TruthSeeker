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
| Deep Space | `#111828` |主背景 |
| Charcoal | `#30363D` |卡片/面板背景 |
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
```css
/*主渐变 -科技蓝紫 */
--gradient-primary: linear-gradient(135deg, #6366F10%, #8B5CF650%, #A855F7100%);

/*赛博光晕 */
--gradient-cyber: linear-gradient(90deg, #6366F10%, #D4FF12100%);

/*深色面板 */
--gradient-panel: linear-gradient(180deg, rgba(48,54,61,0.9)0%, rgba(31,41,55,0.95)100%);
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
│ [媒体预览] │ [法医分析流] │
│3D悬浮展示 │实时数据瀑布 │
├──────────────────┼──────────────────────┤
│ [溯源关系图] │ [质询官日志] │
│网络拓扑可视化 │辩论时间轴 │
└─────────────────────────────────────────┘
```

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
四个Agent面板分布在3D空间的四个象限，用户通过鼠标拖拽旋转视角。

```tsx
//3D场景结构
<Canvas camera={{ position: [0,0,10], fov:50 }}>
 <ambientLight intensity={0.5} />
 <pointLight position={[10,10,10]} color="#6366F1" />

 {/*中心 -媒体预览 */}
 <MediaPreview position={[0,0,0]} />

 {/*四象限 - Agent面板 */}
 <ForensicPanel position={[-4,2, -2]} rotation={[0,0.3,0]} />
 <IntelPanel position={[4,2, -2]} rotation={[0, -0.3,0]} />
 <InquisitorPanel position={[-4, -2, -2]} rotation={[0,0.3,0]} />
 <CommanderPanel position={[4, -2, -2]} rotation={[0, -0.3,0]} />

 {/*连接线 -表示数据流 */}
 <DataFlowLines />
</Canvas>
```

###交互动效
- **鼠标跟随**：轻微视差偏移
- **聚焦模式**：点击面板放大至全屏，其他面板淡出
- **过渡动画**：使用 `motion`（来自 `motion/react`）和 `gsap` 实现平滑动画过渡

---

##5.组件规范

### Button变体
```tsx
//主按钮 -赛博风格
<Button variant="cyber">
开始检测
</Button>
//样式：渐变背景 +发光边框 +悬停流光

//幽灵按钮 -玻璃效果
<Button variant="ghost">
查看详情
</Button>
//样式：透明背景 +白色边框 +悬停填充

//危险按钮
<Button variant="danger">
删除任务
</Button>
//样式：红色渐变 +警告图标
```

### Card变体
```tsx
// Agent卡片
<AgentCard
 name="视听鉴伪Agent"
 icon={<Microscope />}
 status="analyzing" // idle | analyzing | complete | error
 confidence={0.85}
>
 {/*内容 */}
</AgentCard>

//证据卡片
<EvidenceCard
 type="visual" // visual | audio | text | network
 severity="high" // low | medium | high | critical
 timestamp="00:12:34"
>
 {/*证据详情 */}
</EvidenceCard>
```

###数据可视化组件
```tsx
//置信度仪表盘
<ConfidenceGauge value={0.87} size="lg" />

//时间轴
<Timeline events={debateEvents} activeIndex={2} />

//网络图谱
<NetworkGraph nodes={intelNodes} edges={connections} />

//代码流瀑布
<CodeStream logs={apiLogs} speed="normal" />
```

---

##6.字体规范

###字体族
```css
/*标题 -科技感无衬线 */
--font-heading: 'Inter', 'SF Pro Display', system-ui, sans-serif;

/*正文 -高可读性 */
--font-body: 'Inter', 'Segoe UI', system-ui, sans-serif;

/*代码/数据 -等宽 */
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/*数字显示 -等宽tabular */
--font-numbers: 'SF Mono', 'Roboto Mono', monospace;
```

###字号层级
|级别 |大小 |字重 |用途 |
|------|------|------|------|
| H1 |48px |700 |页面主标题 |
| H2 |32px |600 |区块标题 |
| H3 |24px |600 |卡片标题 |
| Body |16px |400 |正文 |
| Small |14px |400 |辅助文本 |
| Caption |12px |500 |标签/时间戳 |

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
|视听鉴伪Agent |紫色扫描线从上到下扫过面板 |
|情报溯源Agent |绿色数据包沿连接线流动 |
|逻辑质询Agent |黄色闪电图标闪烁 |
|研判指挥Agent |蓝色光环向外扩散 |

---

##8.响应式策略

###桌面优先（>1280px）
-完整3D场景展示
-四象限布局
-悬浮操作面板

###平板适配（768-1280px）
-简化为2D网格
-侧边抽屉导航
-触摸友好的按钮尺寸

###移动端（<768px）
-单列垂直滚动
-底部固定导航
-3D场景替换为轮播卡片

---

##9.可访问性要求

-所有颜色对比度符合WCAG AA标准
-支持键盘导航（Tab顺序合理）
-屏幕阅读器友好的ARIA标签
-减少动画偏好设置（prefers-reduced-motion）
-焦点状态清晰可见
