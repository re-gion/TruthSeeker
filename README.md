# TruthSeeker

TruthSeeker 是面向 CISCN 2026 的跨模态鉴伪与情报溯源系统。当前仓库包含：

- `truthseeker-web/`：Next.js 16 + React 19 前端，包含上传、检测台、会诊、报告和数据大屏。
- `truthseeker-api/`：FastAPI + LangGraph 后端，包含任务、检测流、四 Agent 编排、报告、分享和审计。
- `docs/`：产品流程、后端结构、前端指南、技术栈和实现计划。

## 当前运行时

当前实现目标是 **FedPaRS-compatible 多智能体运行时**，不是已经内置完整 FedPaRS 训练/推理底座：

- Kimi 2.5 作为四个 Agent 共享的原生多模态推理基座，并禁用 thinking。
- Reality Defender 用于媒体取证鉴伪。
- VirusTotal 用于文件哈希、URL、域名等威胁情报。
- Exa API 用于脱敏联网搜索和 OSINT 补充。
- LangGraph 负责阶段式辩论与收敛。
- Supabase 保存任务、分析快照、日志、报告、会诊和审计记录。

## 新 Agent 流程

对外仍保留 `forensics/osint/challenger/commander` 四个协议 key，避免破坏 SSE、报告和前端历史回放：

1. `forensics`：电子取证 Agent，接收全模态输入，等待 Reality Defender、VirusTotal 等工具 all-settled 后生成取证报告。
2. `challenger`：审查取证报告，按质量阈值和轮次上限决定是否打回。
3. `osint`：情报溯源与图谱 Agent，基于取证结果、脱敏搜索和 Exa/VT 结果生成 provenance graph。
4. `challenger`：审查图谱节点、关系、引用和模型推断边。
5. `commander`：生成最终鉴伪与溯源报告。
6. `challenger`：只审阅最终报告，必要时打回 Commander 修订。

每阶段最多 3 轮，质量变化阈值为 0.08。

## 常用命令

后端：

```powershell
cd truthseeker-api
python -m pip install -r requirements.txt
python -m pytest tests
python -m uvicorn app.main:app --reload
```

前端：

```powershell
cd truthseeker-web
npm install
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

## 文档入口

- [应用流程](docs/APP_FLOW.md)
- [后端结构](docs/BACKEND_STRUCTURE.md)
- [前端指南](docs/FRONTEND_GUIDELINES.md)
- [技术栈](docs/TECH_STACK.md)
- [产品需求](docs/PRD.md)
