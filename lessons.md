# TruthSeeker 开发错误记录本

> 犯错后立即记录。开发前快速浏览。最后更新: 2026-04-28

---

## 错误记录

| 日期 | 模块 | 错误描述 | 解决方案 |
|------|------|----------|----------|
| 2026-03-03 | 前端/React | HeroSection Hook 违规：useState/useEffect 在早期 return 之后调用 | Hook 必须在所有 return 之前调用 |
| 2026-03-03 | 前端/SVG | SVG 路径 d 属性使用百分比 | d 属性不支持百分比，需配合 viewBox 使用数值坐标 |
| 2026-03-10 | 前端/Next.js | App Router 转场时页面跳闪 | 不要用 useEffect+setTimeout 延迟切换，用 key={pathname} 重新挂载遮罩 |
| 2026-03-12 | 前端/R3F | MeshTransmissionMaterial 渲染为实心色块 | 需要 Environment 贴图或 Canvas GL alpha:true |
| 2026-03-15 | 后端/Python | 虚拟环境 python 路径失效（指向不存在的路径） | 重新创建 venv_new 并重装 requirements.txt |
| 2026-04-20 | Windows/npm | `npm run typecheck` 可能因本地 `.cmd` shim 启动失败而无报错退出 | 用 `npx tsc --noEmit --diagnostics` 或直接 `node ./node_modules/typescript/bin/tsc` 区分代码错误与命令启动层问题 |
| 2026-04-21 | 后端/pytest | Python 3.13 下 `WinError 10106` 可能由残留进程/损坏的 `.next` 缓存导致；清理环境和重启后可恢复 | 先杀残留 Node 进程、清理 `.next`，再重跑 |
| 2026-04-21 | 前端/Next.js | `next build` 超时（>300s）可能因 `.next` 缓存膨胀（1.6GB）导致 | 删除 `.next` 目录后重新构建，4.7s 即可完成 |

---

## 关键规范速查

| 类别 | 正确 | 错误 |
|------|------|------|
| LangGraph State | `TypedDict` | `Pydantic BaseModel` |
| Motion 导入 | `from "motion/react"` | `from "framer-motion"` |
| Tailwind 配置 | `@import "tailwindcss"` + `@theme {}` | `tailwind.config.js` + `@tailwind` |
| 动画包 | `tw-animate-css` | `tailwindcss-animate` |
| PostCSS | `@tailwindcss/postcss` | `tailwindcss` |
| Drei 版本 | v10（支持 React 19） | v9（不支持） |
| Supabase Auth | `@supabase/ssr` | `@supabase/auth-helpers` |
| shadcn CLI | `shadcn@canary` | `shadcn@latest` |

## 2026-04-28 后端重建注意事项

- `forensics/osint/challenger/commander` 是后端 SSE、前端检测台、报告生成和历史恢复共同依赖的协议 key。可以改变用户可见语义，但不要轻易改 key。
- 外部工具不可把“未配置、超时、网络失败”的降级结果伪装成真实检测通过；必须返回结构化 `success/degraded/failed`。
- provenance graph 中无引用但来自模型推理的边必须标记 `model_inferred=true`，报告中不能写成外部事实。
- FedPaRS 在当前仓库应写成 compatible 运行时或可替换底座，不要把未实现的训练/推理能力写成已完成。
- Windows npm 在当前机器上可能同时出现 registry DNS 失败和本地代理 `127.0.0.1:7897` 连接失败；依赖安装失败不能直接判断为前端代码问题，需把 package-lock 更新留到网络恢复后再做。不要手改 `package.json` 伪装安装完成，也不要把临时 SVG 图谱组件当作 `@xyflow/react` 的最终替代方案。
