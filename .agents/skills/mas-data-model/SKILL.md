---
name: mas-data-model
description: Better-MAS-Tools Pydantic 配置、响应模型与兼容数据迁移。
---

# mas-data-model

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

配置归 app/models/config.py，HTTP 契约优先归 schema.py；专门领域已有模型时就近扩展。模型不得依赖 services/core/api。字段使用明确类型、边界和默认值；可变默认值用 default_factory。

新增持久化字段给安全默认值，旧数据迁移在既有读取 / 校验路径做兼容。保留平台标识与既有 PascalCase 配置字段，不为了统一风格改公开名称。凭据 repr=False，响应不回显密钥，清空 / 保留凭据语义必须区分。

测试旧数据加载、无效值、默认值及失败后旧配置保留。模型改变后重新生成客户端并验证来源清单。
