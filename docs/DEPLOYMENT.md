# 源码、Linux 与 Cloudflare 运行

本项目不依赖原 AUTO-MAS 安装。所有模式首次启动均为空账号，不要复制原 MAS 数据目录。

| 模式 | 运行环境 | 自动验证 | MAS 连接 |
| --- | --- | --- | --- |
| Windows 桌面/源码 | Python3.12、Electron | OpenCV免费滑块、人工、库街区云码图标 | 本机环回接口 |
| Linux 完整后端 | Python3.12或Docker | OpenCV免费滑块、人工、库街区云码图标 | 后端所在主机；Docker网络内的localhost不是宿主机 |
| Cloudflare Workers | Python3.13/Pyodide、Durable Object | numpy/Pillow免费滑块、人工、库街区云码图标 | 不支持 |

米游社极验3目前使用人工验证，云码坐标不能直接替代其完整票据。免费滑块15秒、云码模式30秒总时限，失败转人工。无需抓包代理或安装CA证书。

## Windows 源码

安装 uv、Node.js22并启用Corepack后，在项目根目录运行：

```powershell
powershell -File scripts/start-source.ps1
# 已准备依赖；空数据启动并自动关闭
powershell -File scripts/start-source.ps1 -SkipInstall -SmokeTest
```

需要热更新时使用README的双终端方式。关闭测试服务时使用Ctrl+C；桌面正常退出会清理自身后端。

## Linux 完整后端与 Tunnel

```bash
cp deploy/.env.example deploy/.env
# 在文件中填写 COMMUNITY_PUBLIC_ORIGIN 与 COMMUNITY_ACCESS_PASSWORD
cd deploy
docker compose up -d --build
```

公开来源必须是HTTPS地址，访问密码至少12字符。Compose仅将宿主机127.0.0.1:37164映射给容器，需反向代理或Tunnel访问。云端页面中的代理/MAS localhost指运行后端的位置。

要使用Cloudflare Tunnel，先由部署者准备自己的Tunnel，在`deploy/.env`填写`CLOUDFLARE_TUNNEL_TOKEN`，并在Cloudflare将公开域名的服务指向`http://community:37164`：

```bash
docker compose -f compose.yml -f compose.cloudflare.yml up -d --build
```

Linux源码启动使用`bash scripts/start-source.sh`。对外监听时传`--host 0.0.0.0 --remote`，并为该进程设置`COMMUNITY_PUBLIC_ORIGIN`及`COMMUNITY_ACCESS_PASSWORD`。示例仅提供部署说明，本轮未创建Tunnel或其他远程资源。

备份前停止服务，完整保存`community-data`数据卷，尤其是`state.json`和`master.key`；自动生成的密钥权限为0600。可通过进程变量`COMMUNITY_ENCRYPTION_KEY`提供32字节随机密钥的Base64，此时必须另行保管同一密钥。缺少旧密钥时不会覆盖原密文。Windows默认DPAPI数据不能直接跨用户或迁移到Linux，需重新登录；抽卡记录可通过JSON导出导入。

## 纯 Cloudflare Workers

先在`frontend`完成`yarn install --immutable`和`yarn build`，然后在项目根目录执行：

```bash
uv run --no-project --python 3.13 --with uv==0.12.12 python scripts/install-worker-deps.py
uv run --no-project --python 3.13 python scripts/prepare-worker.py
cd deploy/worker
npm ci
```

依赖安装脚本仅写`deploy/worker/python_modules`。Windows也使用官方uv的`wasm32-pyodide2025`跨平台安装，避开Pyodide临时模块探测问题；不会升级系统uv。首次安装网络较慢时，可在该脚本后加`--proxy http://127.0.0.1:7890`，代理仅作用于其子进程。只有修改Worker依赖时才加`--lock`重新生成`pylock.toml`。

`compatibility_date=2026-09-01`对应Python3.13，请勿任意改成当前日期；后续日期会切换Python版本，需要重新核对WASM轮子与锁文件。

复制`.dev.vars.example`为`.dev.vars`，填入仅用于本地验收的值：

- `COMMUNITY_PUBLIC_ORIGIN`：例如`https://worker.test`。
- `COMMUNITY_ACCESS_PASSWORD`：至少12字符的测试密码。
- `COMMUNITY_ENCRYPTION_KEY`：32字节随机密钥的Base64。

可通过`python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`生成密钥。不要把真实密钥写入wrangler.jsonc或提交到仓库。

```bash
npm run dev
# 本地打包检查，不上传
npx wrangler deploy --dry-run
```

本地浏览器访问Wrangler输出的环回地址；需要将本地浏览器Origin与认证配置匹配时，可经本地HTTPS反向代理访问`COMMUNITY_PUBLIC_ORIGIN`。HTTP工具模拟可使用配置的Origin验证认证，但不代表已完成浏览器/HTTPS部署验收。

正式发布由部署者自行执行：在`wrangler.jsonc`的`vars`填写自己的`COMMUNITY_PUBLIC_ORIGIN`，再输入两个密钥：

```bash
npx wrangler secret put COMMUNITY_ACCESS_PASSWORD
npx wrangler secret put COMMUNITY_ENCRYPTION_KEY
npm run deploy
```

本轮开发未执行上述发布命令。上线前自行核对Cloudflare当时的Python Workers、Durable Object、CPU、内存、子请求与套餐限制，不保证免费套餐可运行全部任务。

### GitHub Actions 一键部署

仓库已提供 `.github/workflows/deploy-cf.yml`，推送到 `main` 且改动相关源码，或手动在 Actions 页触发 `Deploy Cloudflare Workers` 工作流，即可完成构建并发布到 Workers。工作流执行 DEPLOYMENT.md 的同一命令链：构建前端、`install-worker-deps.py` 安装 Pyodide 依赖、`prepare-worker.py` 同步资源、`npm ci` 安装 wrangler、注入公开来源、dry-run 校验，最后 `wrangler deploy`。

首次使用前，在 GitHub 仓库配置以下内容：

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| Secret | `CLOUDFLARE_API_TOKEN` | Cloudflare API 令牌，需 `Workers Scripts: Edit` 权限 |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 账号 ID（可省略，wrangler 会尝试自动发现） |
| Secret | `CLOUDFLARE_ACCESS_PASSWORD` | 远端访问密码，至少 12 字符 |
| Secret | `CLOUDFLARE_ENCRYPTION_KEY` | 32 字节随机密钥的 Base64，可用 `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` 生成 |
| Variable | `CLOUDFLARE_PUBLIC_ORIGIN` | HTTPS 公开来源，如 `https://community.example.com` |

工作流会把 `CLOUDFLARE_PUBLIC_ORIGIN` 写入 `wrangler.jsonc` 的 `vars`，并把两个密钥用 `wrangler secret put` 设置为 Worker 加密 secret。`wrangler.jsonc` 中的 `name` 决定分配的 `*.workers.dev` 子域。密钥只存在于 GitHub Secrets 与 Cloudflare，不会写入仓库。

注意：本仓库 main 分支尚无首个提交时，GitHub Actions 无法通过 `push` 触发；可先用 `workflow_dispatch` 手动运行验证，再按需创建提交。

每个部署是一个固定名称的单用户实例，多名使用者应分开部署。数据在Durable Object的SQLite中压缩加密，整份未压缩状态上限8MB；大型抽卡档案建议用Linux完整后端。保留原加密密钥，并使用Cloudflare提供的持久存储恢复能力备份状态；抽卡页可另行导出JSON。更换密钥不会自动重加密已有数据。

Cron每5分钟检查一次北京时间每日计划，不能提供桌面“启动时签到”语义。凭据保存在云端实例中，但不读取访问者电脑的账号；本机MAS和Clash入口禁用。

## 验证范围

本地模拟回归覆盖六游戏抽卡、登录、验证码、米游币、MAS及存储/认证；Windows源码启动和官方workerd本地实例曾实际运行。Linux镜像与Tunnel没有实际Linux/Docker环境验收；未使用真实账号签到、发送短信、完成真实验证码或调用收费云码。第三方网络、风控和账号状态仍需部署者使用自己的账号验收。
