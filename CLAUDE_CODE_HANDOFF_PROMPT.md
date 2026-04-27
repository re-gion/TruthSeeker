# Claude Code Handoff Prompt

请你作为接手的本地工程代理，继续完成 TruthSeeker 后端逻辑重建的剩余工作。你运行在用户真实终端环境中，没有当前 Codex 会话的网络限制；请优先使用真实 npm/Git/Python/Node 网络能力完成依赖安装、构建、测试和推送。

## 项目现场

- 项目路径：`D:\a311\系统赛\2026系统赛\信安`
- 操作系统：Windows
- Shell：PowerShell
- 当前分支：`main`
- 远端：`origin https://github.com/re-gion/TruthSeeker.git`
- 本地实现提交：`f0fdc96 feat: 重建阶段式鉴伪溯源后端`
- 当前 Codex 已经执行过 `git add -A` 和 `git commit`，但 `git push origin main` 失败，原因是用户当前 Codex/Windows CLI 网络栈无法连接 GitHub。

## 用户偏好

- 默认用通俗、清晰、自然的中文汇报。
- 汇报重点是：做了什么、是否可用、做过哪些真实验证、还有什么风险或需要用户介入。
- 不要把计划、猜测、临时验证或理论可行说成已完成。
- 不要泄露 `.env`、`.env.local`、`.mcp.json` 等真实密钥。
- 不要覆盖用户无关改动，不要使用 `git reset --hard` 或类似破坏性操作。
- 遇到网络失败时，不要用替代实现糊过去；应在真实网络环境下安装和验证原计划依赖。

## 原始目标

把 TruthSeeker 旧的“视听鉴伪 + 情报溯源并行协同”升级为“四 Agent 阶段式流程”：

1. `电子取证 Agent <-> Challenger 收敛`
2. `OSINT 图谱 Agent <-> Challenger 收敛`
3. `Commander 最终报告 <-> Challenger 收敛`
4. 输出最终鉴伪与溯源报告，并在 `final_verdict.provenance_graph` 下发审定图谱。

关键约束：

- 对外继续保留 `forensics/osint/challenger/commander` 四个协议 key。
- `forensics` 用户可见语义改为电子取证 Agent。
- 四个 Agent 都接收用户输入、全局提示词、样本引用和自身系统提示词。
- Kimi 默认模型改为 `kimi-k2.6`。
- 电子取证工具必须 all-settled：Reality Defender、VirusTotal 都要结构化返回成功、降级或失败。
- OSINT Agent 通过 Exa 等后端搜索工具做脱敏搜索，并生成 provenance graph。
- 图谱采用混合模型：实体关系、W3C PROV 风格溯源链、Claim/Evidence/Challenge。
- 收敛规则：每阶段最多 3 轮，质量变化阈值 `0.08`。
- 最终主 verdict 继续使用 `authentic/suspicious/forged/inconclusive`，图谱质量和溯源信息进入子字段。
- 前端最终必须使用 `@xyflow/react` / React Flow 呈现图谱视图，而不是临时 SVG 替代。

## Codex 已完成并提交的内容

本地提交：`f0fdc96 feat: 重建阶段式鉴伪溯源后端`

主要改动：

- 文档重写和同步：
  - `README.md`
  - `docs/APP_FLOW.md`
  - `docs/BACKEND_STRUCTURE.md`
  - `docs/TECH_STACK.md`
  - `docs/PRD.md`
  - `docs/FRONTEND_GUIDELINES.md`
  - `docs/IMPLEMENTATION_PLAN.md`
  - `truthseeker-api/README.md`
  - `task.md`
  - `lessons.md`
  - 白皮书和相关旧计划文档
- 后端状态与路由：
  - `truthseeker-api/app/agents/state.py`
  - `truthseeker-api/app/agents/edges/conditions.py`
  - `truthseeker-api/app/agents/graph.py`
  - `truthseeker-api/app/api/v1/detect.py`
  - `truthseeker-api/app/services/analysis_persistence.py`
- 多模态 LLM 适配：
  - `truthseeker-api/app/config.py`
  - `truthseeker-api/app/agents/tools/llm_client.py`
- 电子取证 Agent：
  - `truthseeker-api/app/agents/nodes/forensics.py`
  - 媒体文件进入 Reality Defender。
  - 文件哈希和文本 IOC 进入 VirusTotal。
  - 工具结果 all-settled，失败和降级不会伪装成成功。
- OSINT 图谱 Agent：
  - `truthseeker-api/app/agents/nodes/osint.py`
  - `truthseeker-api/app/agents/tools/osint_search.py`
  - `truthseeker-api/app/agents/tools/provenance_graph.py`
- Challenger 和 Commander：
  - `truthseeker-api/app/agents/nodes/challenger.py`
  - `truthseeker-api/app/agents/nodes/commander.py`
- 前端检测台：
  - `truthseeker-web/components/detect/DetectConsole.tsx`
  - `truthseeker-web/components/detect/ProvenanceGraphView.tsx`
  - `truthseeker-web/lib/provenance-graph.ts`
  - `truthseeker-web/lib/provenance-graph.test.ts`
  - 相关 Agent 展示、报告、上传和文案文件

注意：`ProvenanceGraphView.tsx` 当前是临时 SVG 数据链路验证组件，不是最终 React Flow 实现。不要把它当作完成项。

## Codex 已运行的关键验证

已通过：

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git diff --check
```

结果：通过，只有 Windows LF/CRLF 提示。

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m unittest tests.test_rebuilt_workflow_contracts -v
```

结果：通过，2 个测试通过。

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npx vitest run lib/provenance-graph.test.ts --reporter verbose --no-color
```

结果：在沙箱外通过，1 个测试通过。沙箱内曾因 `esbuild spawn EPERM` 失败。

此前还完成过：

- `python -m compileall app` 通过。
- `npx tsc --noEmit --pretty false` 通过。
- `npx eslint . --format stylish --no-color` 通过，只有既有 `<img>` warning。
- `npx next build --webpack` 通过。

但请在你的环境重新跑完整验证后再宣称最终完成。

## Codex 失败或未完成事项

### P0：推送本地提交

Codex 已本地提交 `f0fdc96`，但推送失败。

失败命令与结果：

```powershell
git push origin main
```

结果：

```text
fatal: unable to access 'https://github.com/re-gion/TruthSeeker.git/': Failed to connect to 127.0.0.1 port 7897 after 0 ms: Couldn't connect to server
```

再次尝试临时取消 Git 代理：

```powershell
git -c http.proxy= -c https.proxy= push origin main
```

结果：

```text
fatal: unable to access 'https://github.com/re-gion/TruthSeeker.git/': getaddrinfo() thread failed to start
```

你的第一步应该检查：

```powershell
cd D:\a311\系统赛\2026系统赛\信安
git status --short --branch
git log --oneline -3
git push origin main
```

如果远端已有新提交，不要强推；先 `git fetch origin`，查看差异，再按正常协作流程 rebase 或 merge。

### P0：安装 `@xyflow/react` 并替换临时 SVG 图谱

Codex 在沙箱外真实重试过安装，但当前机器网络失败：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm install @xyflow/react --registry=https://registry.npmjs.org/
```

失败：

```text
npm error code EAI_FAIL
npm error request to https://registry.npmjs.org/@xyflow%2freact failed, reason: getaddrinfo EAI_FAIL registry.npmjs.org
```

默认 registry 也失败：

```powershell
npm install @xyflow/react
```

失败：

```text
npm error request to https://registry.npmmirror.com/@xyflow%2freact failed, reason: getaddrinfo EAI_FAIL registry.npmmirror.com
```

显式代理也失败：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
npm install @xyflow/react --registry=https://registry.npmjs.org/
```

失败：

```text
connect UNKNOWN 127.0.0.1:7897 - Local
```

你没有这个网络限制，所以请按原计划执行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm install @xyflow/react
```

安装成功后：

1. 确认 `truthseeker-web/package.json` 和 `truthseeker-web/package-lock.json` 正常更新。
2. 在全局样式中引入 React Flow CSS，例如 `truthseeker-web/app/globals.css`：

```css
@import "@xyflow/react/dist/style.css";
```

3. 把 `truthseeker-web/components/detect/ProvenanceGraphView.tsx` 从临时 SVG 实现替换为 `@xyflow/react` 实现，保留现有功能：
   - 最终完成后才展示审定版本。
   - 节点筛选。
   - 边类型筛选。
   - 节点详情。
   - 引用面板。
   - 图谱质量和置信标识。
   - `model_inferred` 边或节点必须有明显标识，不能伪装成外部事实。
4. 复用或调整 `truthseeker-web/lib/provenance-graph.ts` 的 `toReactFlowGraph()`，不要重复写一套不一致的数据转换。
5. 不要手改 `package.json` 假装安装完成。

建议的 React Flow 验证目标：

- 图谱为空时显示空态。
- `isComplete=false` 时不展示未审定图谱。
- 完整图谱能渲染节点和边。
- 筛选不会破坏布局或节点详情。
- 引用面板能展示 citation URL 和摘要。
- 移动端或窄屏不应出现文本重叠。

### P1：重新验证 Kimi 2.6 多模态调用

Codex 已改造 `llm_client.py` 支持 signed URL/sample refs/content parts，但未在真实 Kimi 2.6 API 环境下验证。

请检查实际 Moonshot/Kimi API 文档和项目当前 SDK/HTTP 调用格式，确认：

- `kimi-k2.6` 模型名是否正确。
- 多模态 content parts 格式是否符合实际 API。
- signed URL 输入是否可以被模型读取。
- 失败时是否有结构化降级，不会让 Agent 误判为真实分析成功。

相关文件：

- `truthseeker-api/app/config.py`
- `truthseeker-api/app/agents/tools/llm_client.py`
- `truthseeker-api/app/agents/nodes/forensics.py`
- `truthseeker-api/app/agents/nodes/osint.py`
- `truthseeker-api/app/agents/nodes/challenger.py`
- `truthseeker-api/app/agents/nodes/commander.py`

### P1：真实外部工具最小连通性验证

不要把真实外部网络服务作为单测依赖，但需要做最小连通性验证：

- Reality Defender：`REALITY_DEFENDER_API_KEY`
- VirusTotal：`VIRUSTOTAL_API_KEY`
- Exa：`EXA_API_KEY`
- Kimi/Moonshot：项目实际使用的 Kimi API key/env

要求：

- 没有密钥时应结构化 degraded/failed。
- 超时、限流、网络失败都应结构化返回。
- 工具失败不能被写成“检测干净”或“外部情报证实不存在风险”。

### P1：完整本地验证

后端建议执行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-api
python -m compileall app
python -m unittest tests.test_rebuilt_workflow_contracts -v
python -m pytest tests
```

如果 `python -m pytest tests` 在 Windows/Python 3.13 下出现 `WinError 10106`，先区分环境 socket/process 问题和代码问题，不要直接判定测试失败是业务逻辑导致。

前端建议执行：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Codex 当前环境里普通 `next build` 曾遇到 Windows `WinError 10106` / Turbopack 相关问题，但 `npx next build --webpack` 通过。你应该在你的环境先跑正常 `npm run build`；只有确认是环境问题时，再用 webpack 作为诊断对照。

### P1：浏览器验证

安装 React Flow 并构建通过后，启动前端：

```powershell
cd D:\a311\系统赛\2026系统赛\信安\truthseeker-web
npm run dev
```

然后用浏览器验证检测台：

- Agent 流程文案显示电子取证、逻辑质询、情报溯源、研判指挥。
- SSE 旧事件仍可消费。
- `final_verdict.provenance_graph` 完成后图谱视图才出现。
- 图谱节点、边、引用和质量标识展示正常。
- 窄屏下布局不重叠。

如果能启动后端 mock 或完整 API，更好地跑一次端到端检测流程。

## 当前代码中需要重点复核的风险点

1. `TruthSeekerState` 新增字段是否所有恢复路径都有默认值。
2. `challenger_route` 阶段推进是否不会在 `consultation_resumed`、max round、低质量变化等分支出现死循环。
3. `forensics_node` 的智能重跑策略是否只重跑失败、降级、被 Challenger 命中的工具或新发现 IOC。
4. VT 无 `scan_available` / 无 hash 的结果必须是 degraded/failed，不得标为 success。
5. OSINT 搜索只发送脱敏线索，不能把用户完整隐私文本直接发给 Exa。
6. provenance graph 中 `model_inferred` 必须保留到前端和最终报告。
7. `final_verdict.provenance_graph` 必须通过 SSE 和历史恢复链路保留。
8. React Flow 实现不能新增必须消费的新 SSE 事件。
9. 文档中 FedPaRS 只能写成 compatible 运行时架构，不得声称未实现的训练/推理底座已经完成。

## 建议的执行顺序

1. 查看 `git status --short --branch` 和 `git log --oneline -3`，确认本地提交和工作区。
2. 先把本地提交推送到远端：`git push origin main`。
3. 安装 `@xyflow/react`。
4. 替换 `ProvenanceGraphView.tsx` 为 React Flow 实现并引入官方 CSS。
5. 跑前端 lint/typecheck/unit/build。
6. 跑后端 compileall/unittest/pytest。
7. 用真实或 mock 环境跑一次完整三阶段流程。
8. 根据实际实现结果回填 `task.md`、`lessons.md`、`docs/TECH_STACK.md`、`docs/IMPLEMENTATION_PLAN.md`。
9. 如果有新增改动，使用 Angular 规范中文提交，例如：

```powershell
git add -A
git commit -m "feat: 完成 React Flow 溯源图谱"
git push origin main
```

## 最终交付要求

完成后请用中文简洁汇报：

1. 完成了什么。
2. 当前结果是否可直接使用。
3. 真实运行过哪些验证，逐条列出命令和结果。
4. 仍有哪些限制、风险或需要用户提供的密钥/网络/环境。

不要只说“已完成”；必须用验证结果支撑结论。
