# TruthSeeker 仓库清理清单

> 扫描日期：2026-06-06。该清单区分已安全清理的运行产物与需要项目负责人确认的历史资料。不要把“未引用”直接等同于“可删除”。

## 已清理

以下文件或目录属于日志、缓存、崩溃转储或构建增量产物，已在 2026-06-06 删除：

- 根目录 `_codex_next_dev.err.log`、`_codex_next_dev.out.log`
- 根目录与前后端子目录的 `bash.exe.stackdump`
- 根目录与后端的 `.pytest_cache`
- 根目录 `.playwright-mcp`
- 后端 `backend.log`、`backend_dev.log`
- 前端 `dashboard-dev.log`、`frontend.log`、`frontend_dev.log`
- 前端 `tsconfig.tsbuildinfo`
- `truthseeker-api/app/`、`scripts/`、`tests/` 下的 `__pycache__`

这些路径均由 `.gitignore` 覆盖或属于可再生运行产物。

## 建议确认后归档或删除

| 路径 | 建议 | 原因 |
| --- | --- | --- |
| `console-login.md`（已删除） | 问题确认解决后删除 | 浏览器控制台诊断快照，不属于长期文档 |
| `TruthSeeker - 基于多智能体协同的跨模态恶意AIGC鉴伪与溯源系统全面技术与项目白皮书.md` | 建议移入 `docs/archive/` 或由正式报告替换 | 已加历史状态说明，正文仍保留大量研究愿景和旧实现口径 |
| `TruthSeeker项目报告深度重构替换稿.md` | 保留到 Word 正式报告完成后再归档 | 是近期报告交付物，不应自动删除 |
| `各大检测API讲解.md` | 保留为调研资料，后续可移入 `docs/research/` | 厂商通用能力会变化，已加当前接入边界 |
| `启动方式.md` | 暂保留 | 已更新为短版本地运行指南；与 README 有部分重复，但便于直接查启动命令 |
| `docs/IMPLEMENTATION_PLAN.md` | 保留为历史路线回顾，或移入 `docs/archive/` | 已不再是当前任务来源 |
| `docs/superpowers/plans/*.md`、`docs/superpowers/specs/*.md` | 保留历史记录；完成后可整体归档 | 部分设计顺序已被后续实现修正 |
| `案例3-图片-客服通知.jpg`、`案例3-文本-客服通知.txt` | 保留 | 可能用于演示和真实端到端验证 |
| `truthseeker-api/app/models/__init__.py` | 确认无规划用途后删除空占位目录 | 当前无模型模块或引用 |
| `truthseeker-api/app/agents/edges/conditions.py::should_converge()` | 在补测试后删除未使用函数 | 当前 Graph 未调用，不能只凭静态未引用直接删 |
| `truthseeker-api/app/agents/tools/fallback.py` 中两个旧 fallback 函数 | 在补测试后按函数清理 | 文件本身仍被运行时使用，不能整文件删除 |
| `truthseeker-api/requirements.txt` 中 `aiofiles` | 依赖复核后删除 | 当前未发现直接引用 |
| `truthseeker-api/requirements.txt` 中 `pytest` | 移入开发依赖 | 测试框架不应作为生产运行依赖安装 |

## 未自动删除

- `.next`、`node_modules`、虚拟环境：体积可能较大，但属于开发环境和可再生构建目录；清理会影响当前运行或后续验证。
- `.agent/`、`.agents/`、`.claude/`、`.cursor/`、`.qoder/`、`.trae/`、`.superpowers/`：属于代理/工具配置，按仓库约定不清理。
- `.env`、`.env.local`、`.mcp.json`：可能包含本地运行配置或敏感信息，不自动删除、不读取内容。
- SQL migrations、测试文件、样例文件：即使未跟踪或当前未引用，也不能按临时文件处理。
