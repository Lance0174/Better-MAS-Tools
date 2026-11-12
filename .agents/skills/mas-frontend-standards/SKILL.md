---
name: mas-frontend-standards
description: Better-MAS-Tools 的 Vue、TypeScript、Pinia、API、路由与前端验证。
---

# mas-frontend-standards

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

Vue 3 script setup + TypeScript + Vite，Yarn 4.9.1。全局业务状态放 Pinia，页面请求经 composables/use*Api，使用生成 Service 与 assertSuccess；错误用 errorMessage 读取安全中文原因。不要直接修改 frontend/src/api；后端契约变化后 export_openapi.py + yarn openapi。

文案进 frontend/src/i18n/locales，不新增语种；让 locales.test.ts 守卫通过。新文件尽量不超过 400 行。主题由 useTheme.ts 统一发布，不在组件读系统主题或发明未定义 CSS 变量。

Android 独立构建 `vite build --mode android`，排除 MAS 管理及远端控制路由；服务能力不能只靠隐藏入口。主进程 / 原生桥按来源与参数限制能力，不提供任意文件或进程执行。

执行 yarn lint、yarn typecheck、yarn test；构建相关再执行 yarn build。用现有 Vitest node 环境、假边界与纯逻辑测试；UI 用隔离浏览器检查，不读取真实账号、不遗留进程。
