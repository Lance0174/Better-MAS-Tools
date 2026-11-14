# 项目更名准备

状态：新名称待定。本阶段完成影响梳理与验收准备，继续使用现有名称和发布身份。最终中文名、英文名、仓库名及是否调整图标，由用户定稿后实施。

## 先改展示名称，保留升级身份

建议首次更名只调整应用显示名称、介绍和发行标题，继续沿用既有应用身份、签名、数据目录、更新源及安装包文件名。中文名、英文名和 GitHub 仓库名可以分开确定，无需一次改动全部标识。

| 项目 | 当前值 | 更名约定 |
| --- | --- | --- |
| 中文显示名 | 更好的MAS工具包 | 定稿后同步界面、窗口、说明与发行标题 |
| Android 显示名 | Better MAS Tools | 定稿后同步 Manifest 的 label |
| Windows 应用 ID | `independent.bettermas.community` | 保留，兼容既有快捷方式及应用身份 |
| Windows 启动文件 | `BetterMASTools.exe` | 首次更名保留，兼容快捷方式与更新替换 |
| Windows 用户目录 | `%APPDATA%/BetterMASCommunity` | 保留，继续读取原账号与记录；尊重 `COMMUNITY_DATA_DIR` |
| Android applicationId / namespace | `io.github.lance0174.bmat` | 保留，确保覆盖安装到原应用 |
| Android Keystore 别名 | `bmat.local.state.v1` | 保留，否则旧账号密文无法读取 |
| Android 状态格式与文件 | `BMAT1` / `community-state.bin` | 保留，不因显示名称变化迁移或重置 |
| 平台识别与原生消息 | `BMAT-Desktop/1`、`BMAT-Android/1`、`bmat-native-ready` 等 | 保留，避免桌面能力、手机引擎与原生通信失效 |
| 官方更新仓库 | `Lance0174/Better-MAS-Tools` | 单独规划迁移，首次更名保留 |
| 安装包前缀 | `BMT-` | 首次更名保留，兼容已发布客户端的严格校验 |

Android 固定证书 SHA-256：`bad70d8a02cf2b1c2d7ba3da7b39f832bf53f03ec1925e6eb492fd178852aa75`。继续使用既有密钥和四项 CI 签名配置，不重新生成或轮换。Windows 当前未配置受信任 Authenticode 证书；显示名称调整不会自动改变签名状态。历史 b2 的不同签名不属于可以覆盖升级的基线，覆盖升级验收从固定签名的 b4 开始。

## 展示名称落点

| 范围 | 源文件 |
| --- | --- |
| 页面标题与首次指引 | `frontend/index.html`、`frontend/src/i18n/locales/standalone.ts` |
| 桌面窗口、托盘和产品属性 | `frontend/electron/main.cts`、`frontend/electron-builder.cjs` |
| Android 桌面名称 | `android/app/src/main/AndroidManifest.xml` |
| 后端服务标题、启动说明 | `app/main.py`、`main.py` |
| 用户说明、开发与发布规范 | `README.md`、`AGENTS.md`、`docs/`、`.agents/skills/mas-*` |
| 发行标题与构建说明 | `.github/workflows/windows-release.yml`、`.github/workflows/android-release.yml`、`scripts/finalize-release.py` |

只更新本项目自身名称。保留上游项目名称、许可证、原作者、版权头、第三方致谢、来源清单中的原始仓库地址，以及历史发行记录。生成 API 客户端或 Android 资源时沿用既有生成流程，不手改生成物。

名称变化沿用已审核的 Miuix 视觉与 Ant Design Vue 组件约定，不借机调整布局。Android 继续不包含 MAS 管理；桌面功能仍称“MAS 管理”。

## 更新源与资产名的迁移顺序

已发布 b4 的 Python 更新查询、Windows 下载器和 Android 安装器，均严格校验官方仓库路径与 `BMT-` 资产名。直接更名 GitHub 仓库后，接口可能重定向并返回新仓库的下载 URL；即使重定向有效，旧客户端仍可能拒绝下载地址。改安装包前缀也会被旧客户端拒绝。

因此，首次显示更名保留更新源及资产命名。若以后确实要迁移仓库或资产名，先设计并发布兼容过渡版本，在原更新源上让旧版可下载、可验证、可安装；再按用户确认的旧、新官方仓库精确调整白名单。未完成过渡与旧客户端实测前，不直接迁移远程仓库。不得通过允许任意 GitHub 仓库、任意 HTTPS URL 或禁用摘要校验来兼容更名。

需要协同修改和回归的契约如下：

| 范围 | 源文件 |
| --- | --- |
| 更新版本发现、资产名和下载源 | `app/tools/update_release.py`、`tests/test_updates.py` |
| Windows 下载、摘要与程序替换 | `frontend/electron/updates.cts`、`frontend/electron/updates.test.ts` |
| Android 更新查询原生白名单 | `android/app/src/main/java/io/github/lance0174/bmat/NativePolicy.java`、对应 `NativePolicyTest.java` |
| Android 下载 URL 与包验证 | `android/app/src/main/java/io/github/lance0174/bmat/UpdatePolicy.java`、对应 `UpdatePolicyTest.java` |
| Windows 输出文件与启动校验 | `frontend/electron-builder.cjs`、`scripts/build-desktop.ps1`、`scripts/start-desktop.ps1`、`scripts/verify-desktop.py` |
| 双端资产与两份校验清单 | 两个平台发布工作流、`scripts/finalize-release.py`、`tests/test_release_assets.py` |

发布控制仍要求两平台同一提交成功、三份安装包与两份校验清单完整。资产若增加旧、新名称别名，必须先同步调整此契约，不能跳过完整性检查。已公开的 b4 标签、安装包与摘要保持原样；更名使用后续新版本发布。

## 定稿后的验收

1. 核对桌面、手机、首次引导、设置、系统应用列表的显示名称；搜索遗漏时区分本项目名称和上游归属，不全仓盲替换。
2. 使用合成账号与抽卡记录建立 b4 升级基线。Windows 便携 EXE、ZIP 两种布局分别验证覆盖更新、旧快捷方式启动和旧数据读取。
3. Android 构建先核对固定证书，包完成后再用 `scripts/verify-android-signing.py` 核对实际签名；真机验证从固定签名 b4 覆盖安装、账号密文可读取、抽卡记录与已跳过的引导状态保留。
4. 分别从旧版和新版本检查软件内更新，覆盖稳定版与测试版通道、下载地址和摘要校验、拒绝降级、安装与重启。若迁移远程仓库，必须验证已安装旧版仍有可用升级路径。
5. 森空岛验证创建二维码、扫码确认、完整凭据保存、重启后便笺及签到；设备验证或保存失败时保留旧凭据。离线回归与用户真实扫码结果分别记录。
6. 执行对应的后端、前端、来源、Windows 打包与 Android Gradle 门禁；新增变更碎片，按 `docs/RELEASE.md` 生成新版本和发布说明。公开前核对签名、两平台资产和来源摘要，不覆盖历史版本。

当前待定项只有新名称与是否迁移仓库/资产名。实际更名和新版本发布以用户定稿及相应验收结果为准。
