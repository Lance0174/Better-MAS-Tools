# 独立社区工具开发约定

- 本仓是独立项目，不属于 AUTO-MAS 组织；没有默认发布地址。未经用户要求不创建提交或远程仓库、不推送或发布。
- 保留 LICENSE、NOTICE.md、上游文件的版权头、第三方致谢及有效注释。
- 开发前使用 `E:\GitHub\AUTO-MAS\.agents\skills\mas-skills\SKILL.md` 及任务需要的子 Skill；源仓路径只用于开发规范和溯源，不能成为运行依赖。
- `app/tools` 保留平台协议与纯转换；`app/core` 负责账号及执行编排；`app/services` 负责本机存储与外部通知；`app/api` 只做 HTTP 契约转换。
- 前端使用 Vue 3、TypeScript、Ant Design Vue。API 从 OpenAPI 生成，禁止手改 `frontend/src/api`。
- 账号、密码、凭据和日志不得提交。开发环境从空账号开始，不读取原 MAS 账号。
- 开发报告追加到 `E:\GitHub\doc\游戏社区模块全量完善\16_独立游戏社区工具拆分.md`，报错必须记录；历史报告不能删除。
- 写后先测试再审查。测试不发送真实消息，不访问真实用户凭据；测试启动的服务验证后关闭。
