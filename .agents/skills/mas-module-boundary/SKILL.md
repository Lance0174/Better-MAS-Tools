---
name: mas-module-boundary
description: Better-MAS-Tools 后端分层、依赖方向和 Android 能力边界。
---

# mas-module-boundary

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

以 `docs/ARCHITECTURE.md` 为准：
- api 只作参数与响应契约转换，可依赖 core / services / models。
- core 编排状态、账号、签到和任务，可依赖 tools / services / models / utils。
- services 处理存储、网络、诊断和外部连接，可依赖 tools / models / utils。
- tools 处理纯解析、转换和平台协议，可依赖 models / utils。
- models 不依赖其它层；utils 只依赖标准库与第三方库。

不反向 import，不在 API 重复业务规则。优先扩展现有模块；确需新模块时说明职责。Android 运行入口、存储 / 网络桥按 AGENTS 第 6 节落位，禁止开 socket。生成资源通过 prepare-android.py 产出。
