---
name: mas-code-standards
description: Better-MAS-Tools 的实现、修复、代码审查与提交说明约定。
---

# mas-code-standards

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

读目标文件及相邻实现，保持最小必要变更。Python 采用类型注解、短中文说明、明确的错误与副作用；Vue 使用 script setup 和 TypeScript。不要全仓格式化、修改生成物或覆盖无关改动。

后端按 `docs/ARCHITECTURE.md` 分层。敏感日志与返回错误经 sanitize_log_message，凭据不进入夹具或提交。移植文件保留版权和来源，摘要刷新必须遵守用户授权范围。

用户可见改动添加 `changelog.d/<id>.<feat|change|fix|perf|security>.md`，一行中文。版本只由发版脚本更新。提交信息为 `type(scope): 中文描述`，未经用户要求不创建提交或发布。

验证使用本仓现有门禁，不套用其它仓库的 warning 预算。先测试、后审查；真实失败与修复结果均追加到开发报告。
