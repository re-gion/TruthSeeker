# TruthSeeker 开发任务清单

> **使用说明**: 按顺序自上而下执行任务，每完成一项在 `[ ]` 中打勾 `[x]`。遇到阻塞问题立即记录到 `lessons.md`。

---

## 🎯 里程碑总览

- [ ] **M1 - MVP可用**: Layer1完成（视频检测 + 双Agent + SSE）
- [ ] **M2 - 完整辩论**: Layer2完成（全模态 + 四Agent + 收敛算法）
- [ ] **M3 - 专家会诊**: Layer3核心完成（Realtime协作，3D可选）
- [ ] **M4 - 竞赛就绪**: Polish完成（部署 + 演示准备）

---

## Layer 1: 核心鉴伪能力（MVP）

### Phase 1.1: 基础设施搭建

#### 1.1.1 项目初始化
- [ ] **前端**: 创建 Next.js 15 项目
  - [ ] 运行 `npx create-next-app@latest truthseeker-web --typescript --tailwind --eslint --app --no-src-dir`
  - [ ] 运行 `npx shadcn@canary init` (必须使用 canary)
  - [ ] 验证 Tailwind v4 配置正确 (`@import "tailwindcss"`)
- [ ] **安装前端依赖**
  - [ ] `npm install motion @react-three/fiber@^9.5.0 @react-three/drei@^10.0.0 three`
  - [ ] `npm install @supabase/supabase-js @supabase/ssr`
  - [ ] 验证 `package.json` 中版本正确
- [ ] **后端**: 创建 FastAPI 项目结构
  - [ ] 创建目录 `truthseeker-api/`
  - [ ] 创建虚拟环境并激活
  - [ ] 安装依赖：`pip install fastapi==0.134.0 uvicorn[standard] python-multipart`
  - [ ] 安装 LangGraph：`pip install langgraph>=1.0.9 langchain-core>=0.3.79`
  - [ ] 创建 `main.py` 基础框架
- [ ] **Supabase 项目创建**
  - [ ] 在 Supabase Dashboard 创建新项目(已创建。目前你拥有的Supabase MCP 连接的就是Supabase上用于此项目的project)
  - [ ] 记录 Project URL 和 Publishable Key（直接去Supabase MCP连接的项目下查看）
  - [ ] 启用 Email Auth provider
- [ ] **环境变量配置**
  - [ ] 创建 `truthseeker-web/.env.local`
  - [ ] 创建 `truthseeker-api/.env`
  - [ ] 添加 `.gitignore` 排除 env 文件

#### 1.1.2 基础 UI 框架
- [ ] **布局组件**
  - [ ] 创建 `app/layout.tsx` 根布局
  - [ ] 创建 `components/layout/Header.tsx`
  - [ ] 创建 `components/layout/MainLayout.tsx`
- [ ] **Tailwind v4 主题配置**
  - [ ] 编辑 `globals.css` 添加 `@theme` 指令
  - [ ] 定义品牌色：`--color-indigo-ai: #6366F1`
  - [ ] 定义荧光色：`--color-cyber-lime: #D4FF12`
  - [ ] 验证 CSS 变量生效
- [ ] **文件上传组件**
  - [ ] 创建 `components/upload/FileUploader.tsx`
  - [ ] 实现拖拽上传功能
  - [ ] 限制文件类型（视频优先）
  - [ ] 显示上传进度
- [ ] **加载状态**
  - [ ] 创建 `components/ui/LoadingSpinner.tsx`
  - [ ] 实现骨架屏效果

#### 1.1.3 Supabase 集成 ⭐关键
- [ ] **Supabase Client 配置**
  - [ ] 创建 `lib/supabase/client.ts` (Browser Client)
  - [ ] 创建 `lib/supabase/server.ts` (Server Client)
  - [ ] 注意：使用 `@supabase/ssr`，不是 auth-helpers
- [ ] **用户认证**
  - [ ] 实现邮箱注册 `/auth/signup`
  - [ ] 实现邮箱登录 `/auth/login`
  - [ ] 实现登出功能
  - [ ] 创建 Auth Context Provider
- [ ] **数据库 Schema 设计**
  - [ ] 创建 `tasks` 表
    ```sql
    id: uuid primary key
    user_id: uuid references auth.users
    status: enum ('pending', 'processing', 'completed', 'failed')
    input_data: jsonb
    result: jsonb
    created_at: timestamp
    updated_at: timestamp
    ```
  - [ ] 启用 RLS 策略
  - [ ] 用户只能访问自己的任务
- [ ] **任务 API**
  - [ ] 实现 `POST /api/tasks` 创建任务
  - [ ] 实现 `GET /api/tasks/:id` 查询任务
  - [ ] 实现 `GET /api/tasks` 列表查询
- [ ] **连接测试**
  - [ ] 测试前后端与 Supabase 连接
  - [ ] 验证 Auth 流程完整

---

### Phase 1.2: 双 Agent 核心流程

#### 1.2.1 LangGraph 基础 ⭐关键
- [ ] **State 定义** (TypedDict 强制)
  ```python
  class TruthSeekerState(TypedDict):
      task_id: str
      messages: Annotated[List[BaseMessage], add_messages]
      evidence_list: List[dict]
      forensics_report: dict
      final_verdict: dict
      current_round: int
      max_rounds: int
  ```
- [ ] **视听鉴伪Agent Agent**
  - [ ] 创建 `agents/forensics_agent.py`
  - [ ] 实现视频抽帧逻辑 (ffmpeg)
  - [ ] 调用 Deepfake 检测 API (请先利用Exa MCP搜索Deepfake检测API，如果有可用API请使用，后期我去申请API并配置，否则请模拟实现)
  - [ ] 输出结构化证据报告
- [ ] **研判指挥Agent Agent**
  - [ ] 创建 `agents/commander_agent.py`
  - [ ] 接收法医报告
  - [ ] 生成最终判定 (真/假/存疑)
  - [ ] 输出置信度分数
- [ ] **工作流编排**
  - [ ] 创建 `graph/workflow.py`
  - [ ] 定义 StateGraph
  - [ ] 连接 Forensics → Commander
  - [ ] 本地测试工作流

#### 1.2.2 基础 Bento 布局
- [ ] **静态四宫格布局**
  - [ ] 创建 `components/bento/BentoGrid.tsx`
  - [ ] 左上：原始媒体面板
  - [ ] 右上：法医分析面板
  - [ ] 左下：溯源信息面板
  - [ ] 右下：质询日志面板
- [ ] **响应式适配**
  - [ ] 移动端垂直堆叠
  - [ ] 桌面端 2x2 网格

#### 1.2.3 SSE 实时推送 ⭐关键
- [ ] **FastAPI SSE 端点**
  ```python
  @app.post("/api/v1/detect/stream")
  async def detect_stream(request: DetectRequest):
      async def event_generator():
          yield f"data: {{'type': 'start'}}\n\n"
          async for event in agent_workflow.astream(initial_state):
              yield f"data: {json.dumps(event)}\n\n"
          yield f"data: {{'type': 'complete'}}\n\n"
      return StreamingResponse(event_generator(), media_type="text/event-stream")
  ```
- [ ] **前端 EventSource 连接**
  - [ ] 创建 `hooks/useAgentStream.ts`
  - [ ] 实现 SSE 连接管理
  - [ ] 处理重连逻辑
- [ ] **打字机效果日志**
  - [ ] 创建 `components/agents/AgentLog.tsx`
  - [ ] 实现逐字显示效果
  - [ ] 区分不同 Agent 的颜色

#### 1.2.4 MVP 整合
- [ ] **端到端流程**
  - [ ] 上传视频 → 触发检测 → SSE 推送 → 展示结果
  - [ ] 错误边界处理
  - [ ] Loading 状态覆盖
- [ ] **Bug 修复**
- [ ] **Layer1 演示脚本**

**🎉 M1 里程碑检查点**: 可上传视频并查看检测结果

---

## Layer 2: 全模态与四 Agent 完整辩论

### Phase 2.1: 多模态扩展

#### 2.1.1 音频与图片支持
- [ ] **扩展上传组件**
  - [ ] 支持音频文件 (.mp3, .wav)
  - [ ] 支持图片文件 (.jpg, .png)
  - [ ] 自动识别模态类型
- [ ] **音频特征提取**
  - [ ] 频谱分析
  - [ ] 声纹提取
- [ ] **图片 EXIF 解析**
  - [ ] 元数据提取
  - [ ] GPS 信息检查
- [ ] **更新 State 结构**
  - [ ] 支持多模态输入字段

#### 2.1.2 文本链接处理
- [ ] **URL 提取与验证**
  - [ ] 从文本中提取 URL
  - [ ] 验证 URL 格式
- [ ] **网页内容抓取**
  - [ ] 获取标题、正文
  - [ ] 网页截图 (puppeteer/playwright)
- [ ] **Whois 查询**
  - [ ] 域名注册信息
  - [ ] 注册时间检查

#### 2.1.3 情报溯源Agent Agent
- [ ] **OSINT 分析逻辑**
  - [ ] 创建 `agents/osint_agent.py`
  - [ ] IP 归属查询
  - [ ] 域名信誉检查
- [ ] **VirusTotal API 集成**
  - [ ] URL 扫描
  - [ ] 威胁情报关联
- [ ] **威胁展示面板**
  - [ ] 风险等级可视化
  - [ ] 情报来源列表

---

### Phase 2.2: 质询官与收敛机制

#### 2.2.1 逻辑质询Agent Agent
- [ ] **质疑策略设计**
  - [ ] 创建 `agents/challenger_agent.py`
  - [ ] 置信度阈值检查 (< 0.7 触发质疑)
  - [ ] 矛盾检测逻辑
- [ ] **条件边实现**
  - [ ] 打回重审逻辑
  - [ ] 质询历史记录
- [ ] **质询日志面板**
  - [ ] 显示质疑理由
  - [ ] 显示重审次数

#### 2.2.2 动态收敛算法 ⭐核心创新
- [ ] **权重变化计算**
  ```python
  def should_converge(state: TruthSeekerState) -> str:
      current_weights = state["agent_weights"]
      previous_weights = state["previous_weights"]
      changes = [abs(current_weights[a] - previous_weights[a]) for a in current_weights]
      max_change = max(changes)
      if max_change < 0.05 and state["current_round"] >= 2:
          return "converge"
      if state["current_round"] >= state["max_rounds"]:
          return "converge"
      return "continue"
  ```
- [ ] **收敛判定逻辑**
  - [ ] 连续两轮变化 < 5%
  - [ ] 最少辩论 2 轮
  - [ ] 最大轮数兜底 (默认 5 轮)
- [ ] **可视化展示**
  - [ ] 权重变化图表
  - [ ] 收敛过程动画

#### 2.2.3 完整流程整合
- [ ] **四 Agent 协同调试**
  - [ ] Forensics ↔ Challenger 循环
  - [ ] OSINT 并行执行
  - [ ] Commander 终局裁决
- [ ] **复杂案例测试**
  - [ ] 音画不同步检测
  - [ ] 深度伪造 + 恶意链接
- [ ] **性能优化**
  - [ ] 减少不必要的 API 调用
  - [ ] 缓存中间结果

**🎉 M2 里程碑检查点**: 四 Agent 辩论完整运行

---

## Layer 3: 专家会诊与 3D UI

### Phase 3.1: 专家会诊（核心差异化）⭐优先

#### 3.1.1 Supabase Realtime 集成
- [x] **Broadcast 通道配置**
  - [x] Agent 状态流广播
  - [x] 事件类型定义
- [x] **Presence 实现**
  - [x] 在线用户感知
  - [x] 用户角色标识 (主持人/专家)
- [x] **多端同步测试**
  - [x] 两个浏览器窗口同步
  - [x] 状态一致性验证

#### 3.1.2 专家会诊模式
- [x] **邀请机制**
  - [x] 生成邀请码
  - [x] 生成邀请链接
  - [x] 二维码生成 (Postponed)
- [x] **权限控制**
  - [x] 主持人权限
  - [x] 专家只读/评论权限
- [x] **人工介入节点**
  - [x] 暂停自动流程 (Via Realtime UI)
  - [x] 专家提交意见
  - [x] 恢复辩论流程
- [x] **会诊意见记录**
  - [x] 评论时间轴
  - [x] 投票决策记录

#### 3.1.3 报告与导出
- [x] **Markdown 报告生成**
  - [x] 结构化报告模板
  - [x] 证据链完整呈现
- [ ] **PDF 导出功能**
  - [ ] 使用 puppeteer 生成 PDF
  - [ ] 数字签名占位
- [ ] **报告分享链接**
  - [ ] 只读分享页面

**🎉 M3 里程碑检查点**: 专家会诊可用

---

### Phase 3.2: 3D Bento Box

#### 3.2.1 React Three Fiber 基础
- [x] **R3F 场景搭建**
  - [x] Canvas 配置
  - [x] 相机设置
- [x] **四个面板 3D 定位**
  - [x] 空间坐标计算
  - [x] 面板容器组件
- [x] **相机控制**
  - [x] OrbitControls
  - [x] 视角切换动画
- [x] **光照和材质**
  - [x] 环境光
  - [x] 面板材质

#### 3.2.2 Liquid Glass 效果
- [x] **自定义 Shader**
  - [x] 流动光泽效果 (CSS glassmorphism + 3D glass shards)
  - [x] 折射/反射 (meshPhysicalMaterial with transmission)
- [x] **呼吸光晕**
  - [x] Agent 活跃状态指示 (动态发光边框 + 颜色变化)
  - [x] 脉冲动画 (AgentCard pulse + scan sweep)
- [x] **边框发光**
  - [x] 半透明边框 (glassmorphism panels)
  - [x] 鼠标悬停高亮 (hover effects)

#### 3.2.3 动画与过渡
- [x] **面板切换动画**
  - [x] 3D 旋转过渡 (float + orbit controls)
  - [x] Motion + R3F 协同 (hybrid architecture)
- [x] **滚动视差**
  - [x] 报告页面视差效果 (3D background parallax)
- [x] **微交互**
  - [x] 按钮 hover 效果
  - [x] 卡片悬浮效果 (float animation)

---

## Polish: 竞赛优化与演示准备

### Phase 4.1: 竞赛功能完善

#### 4.1.1 演示案例库
- [x] **内置典型案例**
  - [x] "董事长语音诈骗" (音频伪造)
  - [x] "Politician 换脸视频" (视频伪造)
  - [x] "钓鱼链接+伪造截图" (图文混合)
  - [x] "AI 生成新闻" (文本生成)
- [x] **案例分类标签**
- [x] **一键加载演示**

#### 4.1.2 数据大屏
- [x] **统计仪表盘**
  - [x] 累计检测数量
  - [x] 威胁类型分布
  - [x] 平均响应时间
- [x] **实时数据展示**
  - [x] 动画数字滚动
  - [x] 动态饼图/柱状图

#### 4.1.3 实时对抗演示
- [x] **快速制作假视频建议**
  - [x] FaceSwap App 推荐
  - [x] 操作指引
- [x] **即时检测流程**
  - [x] 目标：<90秒出结果
- [x] **对比展示增强**
  - [x] 真假对比视图

---

### Phase 4.2: 最终优化与部署

#### 4.2.1 性能优化
- [ ] **视频压缩与转码**
  - [ ] ffmpeg 压缩参数优化
  - [ ] 分辨率自适应
- [ ] **API 响应缓存**
  - [ ] Redis 缓存层
- [ ] **前端优化**
  - [ ] 代码分割
  - [ ] 懒加载 3D 资源

#### 4.2.2 安全加固
- [ ] **输入验证**
  - [ ] 文件类型白名单
  - [ ] 文件大小限制
- [ ] **速率限制**
  - [ ] API 限流
  - [ ] 防刷机制
- [ ] **敏感数据脱敏**
  - [ ] 日志脱敏检查

#### 4.2.3 文档与部署
- [ ] **用户操作手册**
- [ ] **Vercel 部署**
  - [ ] `next.config.ts` output: 'standalone'
  - [ ] 环境变量配置
  - [ ] Supabase CORS 设置
- [ ] **后端部署**
  - [ ] Render/Railway 部署
- [ ] **竞赛答辩 PPT**
- [ ] **演示视频录制**

**🎉 M4 里程碑检查点**: 竞赛提交版本完成

---

## 📋 每日开发检查清单

每天开始开发前：
- [ ] 查看 task.md以及IMPLEMENTATION_PLAN.md  确定当前要执行的任务
- [ ] 阅读 CLAUDE.md（如果你是Antigravity，请阅读 ./agents/rules/antigravity.md）中的 Reference Documents 确认规范
- [ ] 回顾 lessons.md 避免重复犯错

每天结束开发时：
- [ ] 更新本文件任务状态
- [ ] 记录当天遇到的问题到 `lessons.md`
- [ ] Git commit & push

---

## 🚨 阻塞问题处理流程

1. **技术栈相关问题**: 查阅 `TECH_STACK.md` Breaking Changes 章节
2. **架构相关问题**: 查阅 `BACKEND_STRUCTURE.md` 或 `FRONTEND_GUIDELINES.md`
3. **需求相关问题**: 查阅 `PRD.md`
4. **仍无法解决**: 在 `lessons.md` 记录并寻求外部帮助
