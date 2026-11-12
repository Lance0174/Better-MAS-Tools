---
name: mas-schema-naming
description: Better-MAS-Tools 新增 schema 命名与现有公开字段兼容。
---

# mas-schema-naming

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

新增模型沿用当前域的 In / Out 后缀及 OutBase 错误语义；集合字段优先沿用 data / results，不引入平行命名体系。内部 Python 使用 snake_case，公开 JSON 字段保留既有拼写。

平台标识 genshin / starrail / zzz / wuthering / arknights / endfield 不改写。不要为命名一致性重命名旧接口、配置字段或持久化键。专门领域类型放 app/models 下既有模块；确需新文件时说明边界并生成客户端。
