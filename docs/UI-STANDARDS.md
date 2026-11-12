# 界面与组件约定

2026-11-12 用户已审核桌面、手机的 Miuix 风格方案。本文件约束正式界面及仓库内 UI Skill；原型使用示例数据，正式实现必须读取现有 API 并保留加载、空、失败和部分成功状态。

## 技术与来源

本仓使用 Vue 3、TypeScript、Ant Design Vue 4 和 `@ant-design/icons-vue`。Miuix 是 Kotlin Compose Multiplatform 组件库，许可证 Apache-2.0；本轮采用其设计方向，在现有 Vue 技术栈中独立实现外观和交互，不引入 Compose 运行时、不宣称安装了 Miuix Vue 包。未来迁移 Compose 只是备选方案，需要单独评估。

- [Miuix 官方组件](https://compose-miuix-ui.github.io/miuix/zh_CN/components/)
- [Miuix 接入说明](https://compose-miuix-ui.github.io/miuix/zh_CN/guide/getting-started)
- [Miuix 源码与许可证](https://github.com/compose-miuix-ui/miuix)
- [Ant Design Vue 组件](https://www.antdv.com/components/overview-cn)

| 设计参考 | 本仓组件与落位 |
| --- | --- |
| Scaffold / NavigationRail | `App.vue`、`AppNavigation.vue` 桌面侧栏 |
| NavigationBar | 手机悬浮五项底栏；首页、便笺、抽卡、日历、更多 |
| Card / SmallTitle | `a-card`、语义分组与共享圆角卡片 |
| TabRow | `a-tabs`；独立小筛选可用 `a-segmented`，使用前统一注册 |
| DropdownMenu | `a-select`、`a-dropdown`；账号显示昵称、区服、UID |
| OverlayDialog | `a-modal`、`Modal.confirm`；长内容可用 `a-drawer` |
| SwitchPreference | `a-form-item` + `a-switch` |
| Snackbar | `message`；可恢复错误使用 `a-alert` 和重试操作 |

新组件在 `frontend/src/main.ts` 按字母序统一注册。图标用现有图标库，按钮保留可访问名称和键盘焦点。

## 视觉基线

- 浅色画布 `#f5f5f5`、卡片白色；深色画布 `#101114`、卡片 `#1c1d21`。主操作蓝色，正文与按钮文字满足可读对比度。
- 卡片圆角 22–24px、控件 12–16px；布局间距按 4/8 倍数。桌面内容留白 24–40px，手机 16–20px。
- 不添加品牌大抬头、英文页码、编号导航、工业网格、黄色强调、切角或额外装饰刻度。页面只保留清楚的中文标题与真实操作。
- 主题唯一来源为 `frontend/src/composables/useTheme.ts`，公共样式在 `frontend/src/style.css`；颜色用实际已定义的 `--ant-*` / `--app-*`，不在页面另建配色。
- 浮层与主卡片层级清晰。Android 和减少动态效果时降低特效；按应用深浅主题检查，不仅检查系统主题。

## 页面与平台

- 首页首屏显示带背景轮播的活动日历及签到结果，下方显示日常便笺和活动提醒。保留已有五款游戏背景与来源说明。
- 每个游戏的便笺独立通过下拉切换账号；不引入“主账号”“备用账号”称呼。
- Android 的导航、路由、打包资源与 Python 接口均不提供 MAS 管理或远端控制。桌面通过 MAS 自带 MCP 管理，入口叫“MAS 管理”。
- Cookie 官方授权优先，其次提供抽卡链接、JSON 与已支持的第三方导入。不能搬入预览的演示数据或伪造成功状态。
- 跳过或关闭新手指引后持久化已处理状态；设置中允许主动重看。开启轻量模式先弹窗说明托盘唤回方式。

## 验证

前端门禁是 `yarn lint`、`yarn typecheck`、`yarn test`、`yarn build`。检查 1440px、390px、320px 的深浅主题、所有正式路由及长文本。对弹窗检查低高度、滚动、关闭与确认操作。Android 额外构建 `vite build --mode android`，执行 `scripts/verify-android.cjs`，确认直接访问 MAS 路由也无法进入。
