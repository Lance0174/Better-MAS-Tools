---
name: mas-skills
description: Better-MAS-Tools 工程入口；按任务选择本仓前端、接口、签到或代码规范。
---

# mas-skills

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

按实际改动选择最小一组，并说明用途：
- 实现、修复或审查代码：`mas-code-standards`。
- Vue、TypeScript、状态、路由或构建：`mas-frontend-standards`；视觉与交互再加 `mas-frontend-ui`。
- HTTP 契约：`mas-api-contract`；模型变化再加 `mas-data-model` / `mas-schema-naming`。
- 后端职责或依赖方向：`mas-module-boundary`；函数职责再加 `mas-function-design`。
- 社区登录、签到、日常便笺：`mas-game-sign`。

先检查分支和工作区，保留已有改动。测试、来源校验、追加式开发报告按 AGENTS 执行。发版仅在用户授权时执行，遵循 `docs/RELEASE.md`。CI 外部 Action 固定完整提交 SHA，不能使用浮动标签。UI 权威为 `docs/UI-STANDARDS.md`。
