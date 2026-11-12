---
name: mas-frontend-ui
description: Better-MAS-Tools 已审核的 Miuix 风格、Ant Design Vue 组件与双端交互。
---

# mas-frontend-ui

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

先读 `docs/UI-STANDARDS.md`，其中的风格和组件映射是唯一视觉基线。

Miuix 官方参考：https://compose-miuix-ui.github.io/miuix/zh_CN/components/ 。它是 Compose 库（Apache-2.0），本仓保留 Vue 3 + Ant Design Vue 4，独立实现其外观；不要安装或虚构 Miuix Vue 组件。

浅灰 / 深黑画布、实色卡片、蓝色操作、22–24px 卡片圆角；桌面侧栏、手机悬浮底栏。无品牌抬头、工业网格、编号或黄色装饰。主页先活动轮播和签到结果，再便笺 / 提醒，保留游戏背景和账号下拉。Android 无 MAS 管理，桌面名称为“MAS 管理”。

用 a-card、a-tabs、a-select、a-modal / a-drawer、a-switch、message；新增组件在 main.ts 注册。真实加载、空、失败、部分成功状态不得被预览演示替代。

检查 1440 / 390 / 320px 深浅主题和键盘焦点，弹窗长内容可滚动且按钮可达。主题变量审核见 references/css-variable-audit.md；桌面浮层见 references/electron-overlays.md。
