---
name: mas-game-sign
description: Better-MAS-Tools 社区登录、扫码、签到、便笺与凭据保护。
---

# mas-game-sign

本 Skill 适用于独立仓库 Better-MAS-Tools。先遵循仓库根 `AGENTS.md`，再查 `docs/CODE-STANDARDS.md`；用户明确要求优先。不要引入 AUTO-MAS 的 dev 分支、组织流程、任务配置容器或其它仓库不存在的模块。所有路径相对仓库根。

先读 app/core/login.py、community_sign.py 及目标平台 tools，实现沿用 provider 入口。二维码创建、轮询、确认保存分开；一次性 scanCode 与长期 cred 不混用。生成二维码不应依赖仅保存阶段才需要的设备验证。

未知平台状态显式报错；暂时网络失败保留可重试二维码，失效 / 取消后释放任务。保存失败不覆盖旧凭据。签到、定时与手动任务复用 core 编排和互斥锁；便笺保留各角色、区服和账号选择。

日志与错误脱敏；设备验证、代理与 TLS 校验不得绕过。来源清单仅按用户批准范围刷新。测试完整离线流程、失败与取消，以及旧凭据保留；不访问真实账号或发真实签到。
