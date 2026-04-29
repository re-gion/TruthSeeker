# 数据大屏 01/02 层优化设计规格（修订版）

> **目标**：修复交互缺陷、解决顺序倒置、提升数据密度，并通过**图表类型多样化**消除横向条形家族扎堆导致的审美疲劳。

---

## 一、问题清单与修复策略

| 问题 | 影响模块 | 修复策略 |
|------|----------|----------|
| 交互不足：arc-progress / radial-progress / signal-bars 无 tooltip | genai-adoption、genai-filing、cyber-law-governance | 统一补充 `tooltip.formatter`，显示「标签 + 数值 + 单位 + 解释」 |
| 悬停信息只有裸数值，无单位/解释 | lollipop-rank（网络视听） | 定制 formatter，从 `module.metrics[idx]` 取出完整信息渲染 |
| 图表与下方卡片顺序相反 | lollipop-rank、signal-bars | `yAxis.inverse: true`，使 ECharts category 轴索引 0 对应顶部 |
| 数据密度低 | 全部 4 个现有模块 + 新增 2 个模块 | ① 指标卡片从 4 个扩展至 6 个，增加 `description`；② 新增 2 个独立模块 |
| **图表同质化严重** | audiovisual-ecosystem、cyber-law-governance、新增模块 | **图表类型全面多样化**，详见第二节 |

---

## 二、图表类型多样化方案（核心变更）

**设计原则**：6 个模块的图表必须来自不同的视觉家族，避免"横向条/柱/棒/信号"扎堆。

| 模块 | 原图表 | 新图表 | 视觉家族 | 选择理由 |
|------|--------|--------|----------|----------|
| genai-adoption | arc-progress (三环仪表盘) | **保留** arc-progress | Gauge | 中心大数字 + 三环已经有冲击力，无需替换 |
| audiovisual-ecosystem | lollipop-rank (棒棒糖) | **pictorialBar 象形柱图** | Bar变种 | 用内容形态图标（屏幕/手机/视频/信号）代替矩形条，彻底跳出"横向条"家族 |
| ai-creation-scale (新增) | — | **数字翻牌 + 迷你 SVG 进度环** | Custom | 三个核心冲击数字直接展示，不占用 ECharts 画布，极简且震撼 |
| genai-filing | radial-progress (三仪表盘) | **保留** radial-progress | Gauge | 三个小仪表盘并排已经很独特，与 01 层的 arc-progress 形成大小对比 |
| cyber-law-governance | signal-bars (彩色横向条) | **funnel 漏斗图** | Funnel | 漏斗图天然表达"治理层层收紧"的叙事，视觉上与所有横向图完全区分 |
| genai-ecosystem (新增) | — | **radar 雷达图** | Radar | 多维度生态指标用雷达图展示"生态健康度"，与 03 层证据雷达图形成上下呼应但数据完全不同 |

**布局策略**：所有模块保持**单图 + 指标卡片**结构，**取消"主图+副图"上下堆叠**，避免挤占卡片空间。增加的数据密度通过**扩展指标卡片数量**和**增加 description**来实现。

---

## 三、类型系统扩展（`lib/dashboard/index.ts`）

```ts
export interface ExternalInsightMetric {
  label: string
  value: number
  unit: string
  description?: string        // 新增：tooltip 与卡片下方的解释文案
}

// 新增：象形柱图专用数据项
export interface PictorialBarItem {
  label: string
  value: number
  unit: string
  symbol: string              // ECharts symbol，如 'path://...' 或内置形状
  description?: string
}

export type ExternalVisualType = 
  | "arc-progress" 
  | "pictorial-bar"           // 新增：替换 lollipop
  | "digital-cards"           // 新增：数字翻牌
  | "radial-progress" 
  | "funnel"                  // 新增：替换 signal-bars
  | "radar"                   // 新增：生态雷达

export interface ExternalInsightModule {
  id: string
  layer: "risk-foundation" | "governance-environment"
  moduleTitle: string
  summary: string
  visualType: ExternalVisualType
  source: { ... }
  metrics: ExternalInsightMetric[]
  pictorialItems?: PictorialBarItem[]  // 仅 pictorial-bar 类型使用
}
```

---

## 四、01 风险底座（Risk Foundation）

### 4.1 生成式 AI 普及态势（genai-adoption）

**主图**：保留 `arc-progress`（三环仪表盘）
- 中心大字：`2.49 亿人`
- 三环：用户占比 17.7% / 20-29 岁使用比例 41.5% / 生成图片视频 31.0%
- **交互修复**：`tooltip.trigger="item"`，hover 某环时显示该环标签、数值、单位、description

**指标卡片（6 个，3 列 × 2 行）**：
1. 生成式 AI 用户规模 · 2.49 亿人 · "截至2024年12月使用生成式AI产品的用户总量"
2. 用户占比 · 17.7% · "占整体网民比例"
3. 听说过生成式AI · 3.31 亿人 · "有认知但未深度使用的潜在用户池"
4. 认知占比 · 23.5% · "听说过生成式AI的网民比例"
5. 20-29 岁使用比例 · 41.5% · "最活跃年龄段，也是伪造内容的高传播群体"
6. 生成图片/视频 · 31.0% · "直接使用AI生成多媒体内容的用户占比，与Deepfake风险直接相关"

> 年龄分布（6-19岁21.1%、20-29岁41.5%、30-39岁23.9%、40-49岁19.1%、50-59岁10.7%）不单独画图，融入到 description 和中心大字的辅助文案中。

### 4.2 网络视听传播土壤（audiovisual-ecosystem）

**主图**：`pictorialBar` 象形柱状图（替换 lollipop）
- 用语义化图标代替传统矩形条：
  - 网络视听用户 → 屏幕/显示器图标 (path://矩形屏幕)
  - 短视频用户 → 手机图标 (path://手机轮廓)
  - 微短剧用户 → 视频播放图标 (path://播放三角)
  - 网络直播用户 → 信号塔/广播图标 (path://信号波纹)
- `yAxis.inverse: true`（修复顺序，使顶部对应卡片第一个指标）
- `tooltip.formatter` 显示完整标签+数值+单位+description
- 柱子颜色沿用渐变色系，图标发出微光 (shadowBlur)

**指标卡片（6 个）**：
1. 网络视听用户 · 10.91 亿人 · "网民使用率 98.4%"
2. 短视频用户 · 10.40 亿人 · "使用率 93.8%，Deepfake 主要扩散场"
3. 微短剧用户 · 6.62 亿人 · "使用率 59.7%，碎片化内容真伪难辨"
4. 网络直播用户 · 8.33 亿人 · "占网民 75.2%，实时伪造风险高"
5. 市场规模 · 12226.49 亿元 · "2024 年网络视听产业总规模"
6. 同比增长 · 6.1% · "产业仍在高速扩张"

### 4.3 AI + 视听创作规模（ai-creation-scale）【新增模块】

**定位**：回答「内容生产门槛下降到什么程度」

**主图**：`digital-cards` 数字翻牌 + 迷你 SVG 进度环
- 三个大数字横向等分排列，每个数字占 1/3 宽：
  - **16.2 亿**（创作者账号）— 下方迷你环："每 1 个中国人平均 1.15 个创作者账号"
  - **1.3 亿条**（每日上线）— 下方迷你环："每秒约 1500 条新视频"
  - **33.3%**（AI 制图视频）— 下方迷你环："近 1/3 网民已使用 AI 创作"
- 迷你环用 SVG `<circle>` 的 `stroke-dasharray` 实现，不需要 ECharts
- 数字采用等宽字体，带 count-up 入场动画（可选）

**指标卡片（6 个）**：
1. 短视频创作者账号 · 16.2 亿 · "全国注册创作者账号总量"
2. 每日上线短视频 · 1.3 亿条 · "日均新增内容量，审核压力巨大"
3. AI 制作图视频网民 · 33.3% · "近三分之一网民已使用AI制作图片或视频"
4. 网络音频用户 · 3.35 亿人 · "使用率 30.3%，音频伪造同样值得警惕"
5. 行业从业企业 · 75.70 万家 · "2024 年网络视听行业企业总数"
6. 2024 年新成立企业 · 12.57 万家 · "行业仍在吸引大量新进入者"

---

## 五、02 治理环境（Governance Environment）

### 5.1 生成式 AI 备案进展（genai-filing）

**主图**：保留 `radial-progress`（三仪表盘）
- 累计完成备案 302 款 / 2024 年新增 238 款 / 地方登记应用 105 款
- **交互修复**：补充 item tooltip，显示标签+数值+单位+description

**指标卡片（6 个）**：
1. 累计完成备案 · 302 款 · "截至2024年底通过中央备案的生成式AI服务"
2. 2024 年新增备案 · 238 款 · "2024 年单年新增数量，供给侧快速扩张"
3. 地方登记应用 · 105 款 · "通过API调用已备案模型能力的地方登记应用"
4. 注册用户总数 · 6 亿+ · "头部应用注册用户合计超过6亿"
5. 头部应用日活 · 3000 万+ · "头部应用日活突破3000万"
6. 行业从业企业 · 75.70 万家 · "2024 年网络视听行业企业总数"

### 5.2 网络法治与治理力度（cyber-law-governance）

**主图**：`funnel` 漏斗图（替换 signal-bars）
- 数据自上而下排列，形成"治理漏斗"叙事：
  ```
  依法约谈平台    11159 家  （最宽，治理入口）
  警告或罚款平台   4046 家  （收窄，实质处罚）
  关闭违法网站    10946 家  （最严厉措施）
  法治宣传阅读量   46.8 亿次 （底部，治理成果）
  ```
- 颜色从上到下渐变：橙 → 红 → 紫 → 青，表达治理力度递进
- `tooltip.formatter` 显示完整信息
- `sort: 'none'`（保持自定义顺序，不按数值自动排序）
- `label.position: 'inside'`，数值在漏斗内部右侧显示

> **为什么用漏斗图**：这四个指标不是简单的并列对比，而是「约谈 → 处罚 → 关停 → 宣传成效」的治理漏斗叙事。漏斗图在视觉上与所有横向/圆形图表完全区分，评委一眼就能记住。

**指标卡片（6 个）**：
1. 依法约谈平台 · 11159 家 · "2024 年全国网信系统约谈平台数量"
2. 警告或罚款平台 · 4046 家 · "受到行政处罚的平台数量"
3. 关闭违法网站 · 10946 家 · "会同电信主管部门关闭的违法网站"
4. 法治宣传阅读量 · 46.8 亿次 · "网上法治宣传累计阅读量"
5. 法治宣传场次 · 1400+ 场 · "集中开展各类法治宣传场次"
6. 主题网络报道 · 3.1 万篇次 · "推出的主题网络报道数量"

### 5.3 生成式 AI 生态扩张（genai-ecosystem）【新增模块】

**定位**：回答「技术生态压强有多大」

**主图**：`radar` 雷达图
- 4 个维度：开源模型生态、开发者规模、衍生模型繁荣度、用户渗透度
- 指标归一化到 0-100 分制：
  - 开源模型 2 万+ → 85 分
  - 开发者 800 万 → 90 分
  - 衍生模型 9 万+ → 95 分
  - 注册用户 6 亿+ → 100 分
- 与 03 层证据雷达图使用不同配色：生态雷达用青绿色系 (#00D1FF, #00FF94)，证据雷达用蓝紫色系
- `tooltip.formatter` 显示原始数值（非归一化分数）+ 单位

**指标卡片（4 个）**：
1. 开源模型数量 · 2 万+ · "魔搭社区汇聚开源模型数量"
2. 开发者参与 · 800 万 · "吸引全球开发者参与生态共建"
3. 衍生模型数量 · 9 万+ · "通义千问开源模型衍生数量"
4. 注册用户总数 · 6 亿+ · "已备案生成式AI服务注册用户合计"

> 注：本模块仅 4 个指标卡片，网格布局自动适配（3 列网格下第一行 3 个、第二行 1 个左对齐，视觉依然整洁）。

---

## 六、布局调整（`DashboardClient.tsx`）

### 6.1 核心布局保持不变

保持 `xl:grid-cols-[38fr_62fr]`，左侧文字信息区不变，右侧保持「单图 + 指标卡片」结构。

**为什么取消副图**：从用户截图可见，右侧 62% 区域在容纳图表 + 4 列卡片后已较紧凑。若再叠加副图，将严重挤压卡片空间并增加模块高度。数据密度的提升通过**指标卡片从 4 个扩展至 6 个**来实现。

### 6.2 卡片网格调整

```tsx
// 从 xl:grid-cols-4 改为 xl:grid-cols-3
<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
  {module.metrics.map((metric) => (
    <MetricCard key={`${module.id}-${metric.label}`} metric={metric} />
  ))}
</div>
```

- 6 个指标 → 3 列 × 2 行，整齐饱满
- 4 个指标 → 3 列（第一行 3 个、第二行 1 个），依然可接受
- 3 个指标 → 3 列 × 1 行，宽敞大气

### 6.3 指标卡片内部结构

每张卡片增加可选的 description 行：

```tsx
<div className="rounded-[20px] border border-white/8 bg-white/4 p-4">
  <p className="text-sm leading-6 text-white/56">{metric.label}</p>
  <p className="mt-2 text-xl font-semibold tracking-tight text-white">
    {formatInsightValue(metric.value, metric.unit)}
  </p>
  {metric.description && (
    <p className="mt-1.5 text-xs leading-5 text-white/40">{metric.description}</p>
  )}
</div>
```

---

## 七、图表选项构建函数改动

### 7.1 `buildArcProgressOption`（genai-adoption）
- 增加 `tooltip.trigger: "item"`
- `formatter` 根据 `params.seriesIndex` 从 `rings` 数组取出对应 metric：
  ```ts
  formatter: (params: any) => {
    const metric = rings[params.seriesIndex];
    return `<div style="font-weight:600">${metric.label}</div>
            <div style="font-size:16px;font-weight:700;color:${CHART_COLORS[params.seriesIndex]}">
              ${formatInsightValue(metric.value, metric.unit)}
            </div>
            ${metric.description ? `<div style="font-size:11px;color:#aaa;margin-top:4px;max-width:200px">${metric.description}</div>` : ''}`;
  }
  ```

### 7.2 `buildRadialProgressOption`（genai-filing）
- 同上，增加 item tooltip

### 7.3 `buildPictorialBarOption`（audiovisual-ecosystem）【新增函数】
- `type: "pictorialBar"`
- `yAxis: { type: "category", inverse: true, ... }`
- `xAxis: { type: "value", ... }`
- `series: [{ type: "pictorialBar", symbol: (params) => items[params.dataIndex].symbol, symbolSize: ["80%", "80%"], ... }]`
- `tooltip.formatter` 显示完整信息
- 图标颜色：`CHART_COLORS` 循环，每个图标带 `shadowBlur: 16, shadowColor: "rgba(..., 0.4)"`

### 7.4 `buildFunnelOption`（cyber-law-governance）【新增函数】
- `type: "funnel"`
- `sort: "none"`（保持自定义顺序）
- `label: { position: "inside", formatter: "{b}\n{c}{unit}" }`
- 颜色从上到下：`["#FF8A5B", "#FB7185", "#7A77FF", "#61D4FF"]`
- `tooltip.formatter` 从 metrics 数组取 description

### 7.5 `buildRadarOption`（genai-ecosystem）【新增函数】
- `radar.indicator`：4 个维度，max 统一为 100
- `series: [{ type: "radar", data: [{ value: [85, 90, 95, 100], name: "生态健康度" }] }]`
- `areaStyle.color: "rgba(0, 209, 255, 0.2)"`
- `lineStyle.color: "#00D1FF"`
- `tooltip.formatter` 将归一化分数映射回原始数值展示

### 7.6 `buildDigitalCardsOption`（ai-creation-scale）【新增函数】
- 不返回 EChartsOption，返回 React 组件（见 7.7）

### 7.7 `DigitalCardsChart` 组件【新增】
- 3 个等宽列，每列：
  - 顶部：大数字（等宽字体，`text-4xl font-bold tracking-tight`）
  - 中部：标签（`text-sm text-white/60`）
  - 底部：SVG 迷你环（`<svg viewBox="0 0 100 100">`，`stroke-dasharray` 控制进度）
- 迷你环颜色：左 `#FF8A5B`、中 `#7A77FF`、右 `#00D1FF`
- 入场动画：数字从 0 count-up 到目标值（duration: 1200ms）

---

## 八、数据层改动（`DASHBOARD_EXTERNAL_INSIGHTS`）

### 8.1 现有模块字段扩充

- `genai-adoption`：metrics 从 4 个扩展为 6 个，增加 `description`，`visualType` 保持 `"arc-progress"`
- `audiovisual-ecosystem`：metrics 从 4 个扩展为 6 个，增加 `description`，`visualType` 改为 `"pictorial-bar"`，增加 `pictorialItems`
- `genai-filing`：metrics 从 3 个扩展为 6 个，增加 `description`，`visualType` 保持 `"radial-progress"`
- `cyber-law-governance`：metrics 从 4 个扩展为 6 个，增加 `description`，`visualType` 改为 `"funnel"`

### 8.2 新增模块数据

在 `DASHBOARD_EXTERNAL_INSIGHTS` 数组追加：

**ai-creation-scale**（layer: risk-foundation）
- moduleTitle: "AI + 视听创作规模"
- summary: "内容生产门槛断崖式下降，伪造传播进入规模化阶段。"
- visualType: "digital-cards"
- metrics: 6 项（见 4.3）
- source: 中国网络视听节目服务协会《中国网络视听发展研究报告（2025）》

**genai-ecosystem**（layer: governance-environment）
- moduleTitle: "生成式 AI 生态扩张"
- summary: "技术生态以指数级速度扩张，模型、开发者、用户三重螺旋增长。"
- visualType: "radar"
- metrics: 4 项（见 5.3）
- source: 国家网信办《国家信息化发展报告（2024年）》

---

## 九、验证清单

- [ ] 01 层显示 3 个模块（2 原有 + 1 新增）
- [ ] 02 层显示 3 个模块（2 原有 + 1 新增）
- [ ] 6 个模块的图表类型互不相同（Gauge、PictorialBar、Custom、Gauge、Funnel、Radar）
- [ ] pictorialBar 图表顺序与下方卡片顺序一致（`inverse: true`）
- [ ] hover arc-progress 任意环，tooltip 显示标签+数值+单位+描述
- [ ] hover radial-progress 任意仪表盘，tooltip 显示完整信息
- [ ] hover pictorialBar 任意图标，tooltip 显示完整信息
- [ ] hover funnel 任意层级，tooltip 显示完整信息
- [ ] hover radar 任意维度，tooltip 显示原始数值（非归一化分数）
- [ ] 数字翻牌组件正常显示 3 个大数字 + 迷你 SVG 环
- [ ] 指标卡片下方出现灰色小字 description
- [ ] 新增模块 `ai-creation-scale` 和 `genai-ecosystem` 正常渲染
- [ ] 大屏无报错，ECharts 无 warn
