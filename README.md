# 更好的MAS游戏社区版

独立的游戏社区工具，暂名 Better MAS Community，提供 Windows 桌面、Linux Web 后端与 Cloudflare Workers 版本。由 AUTO-MAS 的游戏社区功能拆出，**独立于 AUTO-MAS 团队，不代表原团队发布**。原代码版权、AGPL-3.0-or-later 许可及第三方致谢保留在 [LICENSE](LICENSE)、[NOTICE.md](NOTICE.md) 和 [来源清单](docs/upstream-files.json) 中。

## 当前范围

| 功能 | 当前能力 |
| --- | --- |
| 账号 | 多账号组、启停、编辑、删除和拖动排序 |
| 登录 | 米游社、森空岛扫码获取完整凭据；库街区手机号短信登录（自动或人工验证）；塔吉多一次性账号密码登录；已有凭据录入 |
| 签到 | 库街区、森空岛、米游社游戏签到、塔吉多及云游戏签到，保留奖励、已签、失败和时长上限等结果 |
| 米游币 | 米游社日常任务执行与验证码人工复核，按账号合并进签到结果 |
| 日常便笺 | 明日方舟、终末地、原神、星穹铁道、绝区零；按游戏显示资源和日常，不显示经验 |
| 抽卡记录 | 原神、崩铁、绝区零、鸣潮、明日方舟和终末地；全平台 BMASC JSON 导入导出，米家三游戏兼容 Starward/UIGF |
| 自动签到 | 启动时签到、每天按北京时间定时签到；失败后可手动重试 |
| 过码 | 免费本地滑块、人工验证与云码（付费）三种方式，密钥在“设置”中配置 |
| 远端 | Docker Compose 部署、Cloudflare Tunnel 叠加、纯 Cloudflare Workers 版本，支持 Linux |
| MAS 接入 | 保留本地 AUTO-MAS 接口入口，可在“MAS”页连接并控制本机 MAS |
| 外观 | 浅色、深色、跟随系统和低性能模式；低性能模式不加载便笺背景 |

库街区、塔吉多日常便笺未接入。本期按需求不包含通知模块。

人工验证码在独立弹窗中显示，加载失败可重试；免费滑块总时限 15 秒，启用云码时总时限 30 秒，超时转人工。本地识别运行在独立进程中，单次计算最多 10 秒，超时或取消会回收进程，避免原生库加载卡住整个后端。也可直接选“改用人工验证”。云码目前只用于库街区极验4图标识别，米游社极验3由用户人工完成。手机号与验证码不持久化；登录响应中的正式凭据自动提取，无需安装抓包证书。

## 直接运行

从 [GitHub Releases](https://github.com/Lance0174/Better-MAS-Community/releases) 下载 Windows x64 便携 EXE 后直接打开，或下载 ZIP、完整解压后打开其中的 `BetterMASCommunity.exe`。`SHA256SUMS.txt` 用于核对下载文件完整性。源码仓库不包含生成的安装包或可执行程序。

本地构建后，程序位于：

```text
frontend\out\win-unpacked\BetterMASCommunity.exe
```

也可以在项目根目录执行 `powershell -File scripts/start-desktop.ps1`。保持整个 `win-unpacked` 目录完整，不能只复制其中的 exe。桌面包带有自己的 Python 运行时，用户不需要安装 Python、Node.js 或原 MAS。

首次打开是空账号：

1. 在“社区签到”中点击“添加账号”，输入便于识别的账号名称。
2. 选择对应社区。米游社、森空岛点击“扫码登录”，在对应社区 App 中完成扫码确认；塔吉多可以在账号密码区域登录。
3. 内置登录成功会保存该社区凭据；账号名称及其他手动修改仍需点击“保存”。登录密码只用于当次请求，不存盘。
4. 返回列表点击“立即签到”，在下方查看各社区的游戏、奖励与失败原因。
5. 打开“日常便笺”查询绑定角色。外部 Cookie 可能只有签到字段，缺少便笺需要的 stoken、mid 等信息；内置扫码会沿用原 MAS 的完整补全链路。上游风控、凭据失效或未绑定角色会按实际状态显示。
6. 在“设置 → 自动签到”中开启需要的触发方式，保存后生效。**自动签到需要程序保持运行**，关闭窗口会结束本工具及其后端。

便笺背景继续从 `https://doc.auto-mas.top/community-notes/` 加载，资源来源说明随图标保留。网络不可用时显示底色和本地图标；低性能模式直接省略背景。

## 数据与日志

- 桌面版：`%APPDATA%\BetterMASCommunity`。
- `state.json`：Windows 当前用户 DPAPI 加密的账号、凭据、设置和结果；不是可以直接编辑的明文 JSON。
- `logs\community.log`：脱敏后的社区日志；`desktop.log`：桌面进程启动与退出日志。
- 不读取原 MAS 的账号、配置、环境文件、缓存或日志；不接入 Sentry。
- 配置不支持直接拷到其他 Windows 用户或另一台电脑解密。备份前退出程序，并保留完整数据目录；不要删除唯一的原配置。
- 代理只在本工具“设置”中配置，不修改 Windows 或全局环境变量。

## 从源码开发

需要 Windows、Python 3.12、[uv](https://docs.astral.sh/uv/)、Node.js 22 和 Yarn 4.9.1。依赖都安装在本仓的 `.venv` 和 `frontend/node_modules` 中。

一条命令安装依赖、构建并启动：

```powershell
powershell -File scripts/start-source.ps1
```

更新源码前请完全关闭已有程序。启动脚本发现同一数据目录的实例仍在运行时，会提示退出，避免构建后又回到旧后端。若验证码页面提示“无响应”或“运行版本拦截资源”，关闭原程序后重新执行该命令；仅刷新页面不能替换已经加载的 Python 模块。

也可分步执行：

```powershell
uv sync --locked --dev --extra captcha --link-mode=copy
cd frontend
yarn install --immutable
yarn build
yarn desktop
```

`yarn desktop` 启动 Electron 并自动管理自己的开发后端；前端代码修改后重新构建。需要 Vite 热更新时，用两个终端分别运行：

```powershell
# 项目根目录；开发数据默认在本仓 data 中，不与桌面用户数据混用。
.venv\Scripts\python.exe main.py --port 37164
```

```powershell
# frontend 目录，浏览器访问 http://127.0.0.1:37165
yarn dev
```

完成测试后在这两个终端按 Ctrl+C 关闭服务。开发后端同样没有 Sentry，不需要复制原 MAS 的 `.env`。

后端契约修改后，顺序执行以下生成流程；不要手工编辑 `frontend/src/api`：

```powershell
.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
yarn openapi
```

版本记录统一写在 `CHANGELOG.md` 顶部，运行 `.venv\Scripts\python.exe scripts/changelog.py sync` 同步独立后端与桌面版本。该脚本不修改原 MAS 的版本文件。

## 构建桌面包

在项目根目录运行：

```powershell
powershell -File scripts/build-desktop.ps1
# 需要完整 ZIP 分发包时：
powershell -File scripts/build-desktop.ps1 -Zip
```

脚本依次安装锁定依赖、检查类型、构建 Vue 与 Electron、打包 Python 后端，最后生成 `frontend/out/win-unpacked`。不需要管理员权限，不配置自动更新或远程发布。

GitHub 的 **Actions → Windows Release → Run workflow** 可进行构建验证，产物保存在该次运行的 Artifacts 中。发布版本时，先更新 `CHANGELOG.md` 并同步版本，然后推送匹配版本的 `vX.Y.Z` 标签；工作流会在 Windows 环境构建 ZIP 和便携 EXE，实际检查包内滑块识别、空数据启动与退出，通过后发布到 Releases。已正式发布的版本不会被工作流覆盖。

本轮提供 Windows 自动构建。APK 尚无对应工程，后续定位为连接云端后台的 MAS 远程控制客户端。

## 部署到远端与 Linux

除 Windows 桌面包外，同一后端支持 Linux 服务器与 Cloudflare 远端运行；非环回监听一律要求访问密码认证。

### Docker Compose（Linux/Windows）

复制 `deploy/.env.example` 为 `deploy/.env`，填写 `COMMUNITY_PUBLIC_ORIGIN`（HTTPS 公开地址）与至少 12 位的 `COMMUNITY_ACCESS_PASSWORD`，然后：

```bash
cd deploy
docker compose up -d --build
```

数据保存在 `community-data` 卷中，Linux 上使用 AES-GCM 加密，密钥由首次启动自动生成并保存在卷内；不要删除卷，否则无法解密原有账号数据。需要通过 Cloudflare 暴露时，在同一 `deploy/.env` 填入自己的 `CLOUDFLARE_TUNNEL_TOKEN`，执行：

```bash
docker compose -f compose.yml -f compose.cloudflare.yml up -d --build
```

### 纯 Cloudflare Workers

前端与 Python 后端一起运行于 Workers，Durable Object 保存加密状态，Cron 检查每日计划。需要单独准备 WASM 依赖：

```bash
# 项目根目录；先在 frontend 完成 yarn build
uv run --no-project --python 3.13 --with uv==0.12.12 python scripts/install-worker-deps.py
uv run --no-project --python 3.13 python scripts/prepare-worker.py
cd deploy/worker
npm ci
# 按 .dev.vars.example 创建本地测试配置后启动
npm run dev
```

Workers 包含免费滑块、人工验证和库街区云码适配；云码需要用户填写密钥并承担识别费用。单实例整份状态限制 8 MB，不能连接访问者电脑上的 MAS 或 Clash。完整配置、密钥、发布与备份步骤见 [部署说明](docs/DEPLOYMENT.md)，开发接口见 [API 说明](docs/API.md)。本文不承诺适用 Cloudflare 免费套餐，部署前应核对当时的 Python Workers 资源限制。

## 验证与后续开发

后端代码检查使用 `.venv\Scripts\ruff.exe check app main.py scripts`；在 `frontend` 执行 `yarn lint`、`yarn typecheck`、`yarn test`。本次专用回归保留在本地 `local/tests`，不进入发布包。拆分结构与边界见 [架构说明](docs/ARCHITECTURE.md)。

项目由个人仓库 [Lance0174/Better-MAS-Community](https://github.com/Lance0174/Better-MAS-Community) 托管，独立于 AUTO-MAS 组织。本期未使用真实用户账号访问上游签到、扫码和日常接口，第三方协议的实跑可用性仍取决于账号状态、网络和上游服务。Linux 镜像与 Tunnel 尚未在实际 Linux/Docker 主机验收。

### Linux 源码运行

Linux 上无需 Electron 桌面外壳，直接以 Web 方式运行后端：

```bash
bash scripts/start-source.sh            # 默认 127.0.0.1:37164
bash scripts/start-source.sh --host 0.0.0.0 --remote   # 先配置远端环境变量
```

Windows 可用 `powershell -File scripts/start-source.ps1` 一次完成依赖准备、构建和启动；`-SkipInstall -SmokeTest` 使用全新空数据目录验证源码启动后自动退出。
