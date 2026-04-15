# TruthSeeker Web

TruthSeeker 的 Next.js 前端，负责登陆页、检测工作台、报告页和协作入口。

## 技术栈

- Next.js 16
- React 19
- TypeScript 5
- Tailwind CSS 4
- `motion`
- Supabase SSR 客户端

## 开发

```bash
npm install
npm run dev
```

默认访问地址：

- 前端: `http://localhost:3000`
- 后端 API: `http://localhost:8000`

## 常用脚本

- `npm run dev` - 启动开发服务
- `npm run build` - 生成生产构建
- `npm run start` - 启动生产服务
- `npm run lint` - 执行 ESLint
- `npm run typecheck` - 执行 TypeScript 类型检查
- `npm run test` - 运行仓库级 smoke gate（`lint` + `typecheck`）

## 环境变量

复制 [`.env.example`](./.env.example) 为 `.env.local` 后填写：

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
# NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

说明：

- 当前前端以 `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` 为主。
- 如果你仍在使用旧的 anon key，可以临时保留 `NEXT_PUBLIC_SUPABASE_ANON_KEY` 作为兼容。

## 目录概览

- `app/` - App Router 页面与路由
- `components/` - 页面组件与 UI 片段
- `hooks/` - 前端交互与实时会话逻辑
- `lib/` - 共享工具与数据映射
- `public/` - 静态资源

## 备注

- 这个仓库当前不在本次范围内补齐业务级测试框架。
- 真实密钥只放在本地 `.env.local`，不要提交到仓库。
