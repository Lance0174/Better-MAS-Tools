# 独立社区工具开发约定

- 本仓是独立项目，不属于 AUTO-MAS 组织；没有默认发布地址。未经用户要求不创建提交或远程仓库、不推送或发布。
- 保留 LICENSE、NOTICE.md、上游文件的版权头、第三方致谢及有效注释。
- 开发前使用仓库内 `.agents/skills/mas-skills/SKILL.md` 及任务需要的子 Skill；如需对照源仓库，使用环境变量 `AUTO_MAS_ROOT` 定位，源仓路径不能成为运行依赖。
- `app/tools` 保留平台协议与纯转换；`app/core` 负责账号及执行编排；`app/services` 负责本机存储与外部通知；`app/api` 只做 HTTP 契约转换。
- 安卓本地运行的文件位置约定：`app/core/android_runtime.py` 是手机前台编排入口；`app/services/android.py` 是安卓存储/网络原生适配；`frontend/src/services/android.ts` 是前端安卓桥；`frontend/src/utils/download.ts` 是保存/分享工具；安卓工程在 `android/`（Gradle + WebView + Pyodide 运行时）；构建/校验脚本在 `scripts/prepare-android.py`、`scripts/verify-android.cjs`。新安卓代码按此分层落位，不散落到 `app/` 或 `frontend/src/` 根目录。
- 前端使用 Vue 3、TypeScript、Ant Design Vue。API 从 OpenAPI 生成，禁止手改 `frontend/src/api`。
- 账号、密码、凭据和日志不得提交。开发环境从空账号开始，不读取原 MAS 账号。
- 开发报告追加到环境变量 `BETTER_MAS_DEV_REPORT` 指向的文件，报错必须记录；历史报告不能删除。
- 写后先测试再审查。测试不发送真实消息，不访问真实用户凭据；测试启动的服务验证后关闭。
