---
description: 审查代码质量，检查类型安全、性能、安全和规范
argument-hint: <文件或目录路径>
---

审查以下代码，按优先级从高到低关注这些方面：

## 审查清单

1. **TypeScript 类型安全**
   - 是否存在 any 类型
   - 类型断言（as）是否合理
   - 函数参数和返回值是否有明确类型

2. **Next.js 14 最佳实践**
   - Server/Client 组件划分是否正确
   - 数据获取方式是否恰当（Server Component 内 fetch vs useEffect）
   - 是否正确使用 next/image 和 next/link

3. **性能隐患**
   - 是否有不必要的重渲染
   - 列表渲染是否有稳定 key
   - 是否缺少 React.memo / useMemo / useCallback
   - 大型对象是否在渲染函数外部定义

4. **安全风险**
   - 是否有 XSS 风险（dangerouslySetInnerHTML）
   - 用户输入是否经过校验
   - 敏感信息是否暴露在客户端

5. **代码风格**
   - 是否符合项目 CLAUDE.md 中的编码规范
   - 命名是否清晰、一致
   - 是否有可读性问题

## 输出格式

按严重程度分类：
- 🔴 **必须修复**：类型错误、安全漏洞、逻辑Bug
- 🟡 **建议优化**：性能隐患、不规范的写法
- 🟢 **小贴士**：可选的改进点

每个问题给出：具体位置 → 问题描述 → 修改建议（附代码）

## 审查目标

$ARGUMENTS