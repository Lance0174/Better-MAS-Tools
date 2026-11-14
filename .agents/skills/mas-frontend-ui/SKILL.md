---
name: mas-frontend-ui
description: Better-MAS-Tools 已审核的 Miuix 风格、Ant Design Vue 组件与双端交互。
---

# mas-frontend-ui

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

先读 `docs/UI-STANDARDS.md`，其中的风格和组件映射是唯一视觉基线。

Miuix 官方参考：https://compose-miuix-ui.github.io/miuix/zh_CN/components/ 。它是 Compose 库（Apache-2.0），本仓保留 Vue 3 + Ant Design Vue 4，独立实现其外观；不要安装或虚构 Miuix Vue 组件。

浅灰 / 深黑画布、实色卡片、蓝色操作、22–24px 卡片圆角；桌面侧栏、手机悬浮底栏。无品牌抬头、工业网格、编号或黄色装饰。主页先活动轮播和紧凑签到摘要，再两张便笺 / 提醒；首页背景限于便笺头部，读数用实色底；完整便笺复用既有 MAS 卡片及原背景，不丢任务、UID 和更新时间。活动图按原图→版本图→原便笺背景回退，不用文字或游戏图标充当图片。移除“服务已连接”和正常加载的泛化成功条。Android 无 MAS 管理，桌面名称为“MAS 管理”。

抽卡统一“获取记录”→来源→确认读取；Cookie／已登录账号获取仅开放明日方舟并选择森空岛账号及角色，其他游戏保留链接、JSON 与第三方导入。JSON 有独立入口，保留链接和第三方导入，高级读取选项主动展开；签到按平台、账号和任务分组，保留奖励、原因与日期，历史结果不标今日成功。

复用 GameTabs、ChoiceSelect、AdaptivePanel 与 confirmDialog：手机主入口直接切换，选择从底部展开，编辑全屏，系统返回逐层关闭；桌面保留侧栏、下拉和表格。真实组件仍由 a-card、a-tabs、a-select、a-modal / a-drawer、a-switch、message 提供；新增组件在 main.ts 注册。真实加载、空、失败、部分成功状态不得被预览演示替代。

检查 1440 / 390 / 320px 深浅主题和键盘焦点，弹窗长内容可滚动且按钮可达。主题变量审核见 references/css-variable-audit.md；桌面浮层见 references/electron-overlays.md。

Android 安全区域由原生容器处理并消费窗口边距，网页不重复叠加；浏览器保留环境安全区域，不硬编码机型高度，不关闭系统自动转色。
