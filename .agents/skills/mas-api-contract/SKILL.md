---
name: mas-api-contract
description: Better-MAS-Tools FastAPI HTTP 契约、错误语义与客户端生成。
---

# mas-api-contract

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

先检查 app/models/schema.py 与相邻路由。契约兼容优先，不新增 /api/v2 或 errorCode。operation_id 必须唯一；返回显式响应模型。

预期失败使用 400 / 401 / 403 / 409 / 422；错误体 code 等于 HTTP 状态，status=error，message 为脱敏中文。500 只返回固定说明与日志编号。部分成功用 status=partial，不用空列表掩盖错误。

路由只调用下层并转换契约，不写盘、不复制业务校验。变更模型或路由后执行 scripts/export_openapi.py，再在 frontend 执行 yarn openapi，禁止手改生成目录。离线契约测试用临时数据及 TestClient(base_url=http://127.0.0.1)，显式关闭生命周期。
