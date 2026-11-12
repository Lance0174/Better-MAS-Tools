---
name: mas-function-design
description: Better-MAS-Tools 后端函数职责、返回契约、异步与副作用。
---

# mas-function-design

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

同一函数承担一个可描述的职责，输入 / 返回类型清楚。纯转换放 tools，状态编排放 core，网络 / 盘操作放 services。避免一次性抽象和大规模顺手拆分。

预期失败抛 ValueError 或既有业务异常；保留取消异常。变更请求失败不得自动重放，任务受理不等于执行成功。写盘使用现有原子存储，锁按现有任务范围释放；异步请求需超时、取消和关闭。

测试可观察行为与失败后的数据保留，不复刻实现。新帮助函数仅在降低重复或改善可读性时提取。
