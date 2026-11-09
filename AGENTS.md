# 独立社区工具开发约定

本文件是仓库级 Agent 入口，也是本仓唯一的协作基线。它由早期简版约定扩写而成，原有条目全部保留。细则见 [docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md)，模块边界见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，接口见 [docs/API.md](docs/API.md)，发版见 [docs/RELEASE.md](docs/RELEASE.md)。

## 1. 怎么使用这份文档

指令优先级从高到低：

1. 用户当前这一轮的明确指令。
2. 本文件 AGENTS.md。
3. `docs/` 下的专项文档（含 docs/CODE-STANDARDS.md）。
4. 被改动文件附近的既有代码与同目录模块的既有写法。

执行细则：

- 更具体的一方优先。子目录若有自己的 AGENTS.md，以它为准；本文件与 docs/ 冲突时，看哪一份更贴近本次改动的范围。
- 本文件没写的问题，跟随该模块现状，不做顺手统一。不要用通用风格指南覆盖本地已经稳定的写法。
- 只读任务（诊断、解释、检索、评审意见）不需要走提交与发版流程；一旦要改文件，以下全部适用。
- 文档与代码里只写仓库相对路径，不写开发机绝对路径。工具链位置（JDK、Android SDK、Gradle 缓存）只通过环境变量传入。
- 本文件里的命令默认在 Windows + PowerShell、仓库根目录执行；标注"frontend 目录"或"android 目录"的除外。

## 2. 项目身份与发布边界

- 本仓是独立项目，不属于 AUTO-MAS 组织；没有默认发布地址。
- 未经用户明确要求，不创建提交、不创建或修改远程仓库、不推送、不打 tag、不发布 Release、不修改版本号。
- 不协助 force push，即便用户要求也先拒绝并说明该操作只能由人手动完成。
- 版本号与 CHANGELOG.md 顶部版本段只由发版流程更新（见 §11）。功能改动不要碰 `pyproject.toml`、`app/version.py`、`frontend/package.json`、`uv.lock`、Android 版本字段。
- 开工前先确认当前分支与工作区状态，不要回滚、覆盖或格式化与本任务无关的改动。其他 agent 可能正在同一工作区改文件：动手前重读要改的文件，同一文件里不属于本任务的逻辑保持原样。

## 3. 许可证、版权头与致谢

- 保留 LICENSE、NOTICE.md、上游文件的版权头、第三方致谢以及仍然有效的注释，不要删除、不要改写成自己的署名。移植或改编外部代码必须在文件头部标注来源与许可证（例如 `Adapted from ...`、`移植自 ...`），并保留原项目的许可声明。
- `docs/upstream-files.json` 是上游来源清单，`scripts/verify_upstream.py` 负责校验：
  - 只扫描 `.py`、`.json`、`.ts`、`.vue` 文件的前 40 行；命中 `Adapted from`、`移植自`、`Priestess-bot`、`Kuro_login`、`Starward` 任一标记，就必须登记在清单的 `files`（有上游摘要的移植文件）或 `attributed_files`（只有归属说明的文件）里。
  - 改过移植文件后跑 `.venv\Scripts\python.exe scripts\verify_upstream.py --local` 校验摘要。
  - `--update` 会就地刷新 `standalone_sha256`，只在确认改动合法、且用户同意时使用；不要把它当成"让校验变绿"的快捷键。
- 新增依赖前确认其许可证与本仓兼容，并在 NOTICE.md 的致谢里补齐来源。

## 4. 开工前：Skill 与对照源

- 开发前使用仓库内 `.agents/skills/mas-skills/SKILL.md` 及任务需要的子 Skill（`mas-code-standards`、`mas-module-boundary`、`mas-function-design`、`mas-api-contract`、`mas-data-model`、`mas-schema-naming`、`mas-frontend-standards`、`mas-frontend-ui`、`mas-game-sign`），只选最小必要的一组，并在回复里说明选了哪些、为什么。
- `.agents` 已被 `.gitignore` 忽略，新克隆不携带这些 Skill。本地缺目录时按 docs/CODE-STANDARDS.md 执行，并在开发报告里注明"未加载 Skill"。
- 如需对照源仓库，使用环境变量 `AUTO_MAS_ROOT` 定位本机检出；校验脚本对应参数是 `scripts\verify_upstream.py --repo <path>`。源仓路径不能成为运行依赖：不得 import、不得拼进运行时代码、不得进入打包产物。
- AUTO-MAS 是 AGPL 项目，只可借鉴结构与思路：措辞自己写，不复制大段英文，不搬运 AGPL 代码。本仓是独立实现，不是 AUTO-MAS 的分支。
- 本仓的既有实践优先于通用风格指南。冲突时以本仓为准，并把新结论补进 docs/CODE-STANDARDS.md。

## 5. 后端分层与依赖方向

| 分层 | 职责 | 不该做的事 |
| --- | --- | --- |
| `app/tools` | 平台协议、纯转换、解析（米游社、库街区、森空岛、塔吉多、终末地、抽卡链接等） | 写盘、读配置、拼 HTTP 响应 |
| `app/core` | 账号、登录、执行编排、状态与调度、签到编排 | 直接解析平台原始报文 |
| `app/services` | 本机存储、外部连接与通知、诊断日志、远端访问 | 承载业务规则 |
| `app/api` | 只做 HTTP 契约转换：参数校验、调用下层、拼响应模型 | 写业务逻辑、直接写文件 |
| `app/models` | Pydantic 契约与配置模型 | 依赖其它层 |
| `app/utils` | 通用工具：日志、脱敏、原子写盘、环境加载 | 记住业务状态 |
| `main.py` | 进程入口：端口、桌面管道、远端开关 | 业务逻辑 |

依赖方向（箭头表示"可以 import"）：

```
app/api      → app/core / app/services / app/models
app/core     → app/tools / app/services / app/models / app/utils
app/services → app/tools / app/utils / app/models
app/tools    → app/utils / app/models
app/models   → 无（不 import 其它层）
app/utils    → 只依赖标准库与第三方库
```

- 反向 import 属于越界。需要跨层拿数据时，把依赖下移到合适的一层，或由上层注入，不要在 `models` 里 import `services`。
- 业务规则只写一处。API 层不要重复下层已经做过的校验；下层已经抛 `ValueError` 的地方，路由不要再包一层 try/except。
- 新代码优先落在本层已有模块里，不新建平行模块；确实要新模块时，在开发报告里说明为什么现有模块放不下。

## 6. 安卓落位约定

| 路径 | 职责 |
| --- | --- |
| `app/core/android_runtime.py` | 手机前台运行编排入口（app/core：编排） |
| `app/services/android.py` | 安卓存储/网络原生适配（app/services：本机存储、外部连接） |
| `frontend/src/services/android.ts` | 前端安卓桥：引擎启动、消息端口、本地请求适配 |
| `frontend/src/utils/download.ts` | 文件保存/分享工具（纯前端工具） |
| `android/` | Gradle + WebView + Pyodide 运行时工程 |
| `scripts/prepare-android.py` | 构建前端并同步安卓离线资源 |
| `scripts/verify-android.cjs` | 在 Electron 里跑打包资源的前端/引擎隔离回归 |

- `android/app/src/main/assets/` 是生成目录，由 `scripts/prepare-android.py` 写入，禁止手改。
- 新安卓代码按上表分层落位，不散落到 `app/` 或 `frontend/src/` 根目录。
- 安卓端不监听端口，网络与持久化经原生桥转交系统；不要为了省事在手机路径上开 socket。

## 7. 前端栈与生成代码

- 前端使用 Vue 3（`<script setup>`）+ TypeScript + Ant Design Vue 4，构建用 Vite，包管理 Yarn 4.9.1。
- API 从 OpenAPI 生成，禁止手改 `frontend/src/api`。后端模型变更后：先 `scripts/export_openapi.py`，再在 frontend 目录 `yarn openapi`。
- Ant Design Vue 组件在 `frontend/src/main.ts` 统一注册；新组件先加进那里的字母序列表，再在页面里直接用。
- 只维护 zh-CN，不新增 en-US。所有用户可见文案必须进 `frontend/src/i18n/locales/`（`zh-CN.ts`、`standalone.ts`），组件与视图里禁止硬编码中文；代码里用 `t('namespace.key')`。
- 已知缺口：词表缺键时没有全局回退，vue-i18n 会把裸 key 直接渲染到界面上；`frontend/src/i18n/index.ts` 里的 `fallbackLocale` 在单语种下帮不上忙。当前只有 `frontend/src/i18n/locales.test.ts` 在测试期拦截漏键，所以新增文案必须同时补词表并让该守卫测试通过。
- 新文件软上限 400 行：超过要在 PR 或开发报告里说明理由，并尽量按职责拆分。不强制重构现有超限文件（`frontend/src/App.vue`、`frontend/src/views/gamesign/useQrLogin.ts` 等），它们是已知债务，只在正好要改它们时顺手拆。
- 状态用 Pinia（`frontend/src/stores/`）；页面请求走 `frontend/src/composables/` 的 `use*Api`，错误文案统一用 `errorMessage(cause, t('...'))`。

## 8. 凭据、日志与隐私

- 账号、密码、cookie、token、二维码会话、日志不得提交。`data/`、`logs/`、`local/`、`.env` 已被 `.gitignore` 忽略，不要为了提交而放宽规则。
- 开发环境从空账号开始，不读取、不导入原 MAS 或用户的真实账号数据。
- 日志必须脱敏：写日志前用 `app/utils/security.py` 的 `sanitize_log_message`；同一个函数也用于把异常文本转成可回给客户端的原因。
- 不要把凭据写进报错文本、URL、文件名或测试夹具。捕获请求体做诊断时，不得回显密码字段（参考 `app/main.py` 对 `RequestValidationError` 只取字段位置与错误类型）。
- 后端日志按 `configure_file_logging` 落盘，5 MB 轮转、保留 7 天；不要把完整请求体写进日志。
- 错误契约：继续用 HTTP 状态码作为机器可读的 `code`，不新增 `errorCode` 字段。错误体固定 `{"code": <状态码>, "status": "error", "message": "<脱敏后的中文说明>"}`。
  - 预期失败用 400/401/403/409/422；业务失败不得返回 500。
  - 500 只回固定文案加日志编号（`操作未完成，请查看日志（编号 ...）`），细节只进日志。
  - 部分成功用 `status: "partial"` 表示（已有实现见 `app/api/gacha.py`），不要用 200 + 空数据糊过去。

## 9. 开发报告台账

- 开发报告追加到环境变量 `BETTER_MAS_DEV_REPORT` 指向的文件。它是一份追加式台账，不是工作草稿：每次实质工作追加一段，包含时间、目标、改动文件（含路径与行号）、验证命令与真实输出、遗留问题。
- 报错必须记录：命令、退出码、关键报错文本。报错后修复的，在同一条记录里补上后续结果，不要回头删掉原始报错。
- 历史报告不得删除、不得覆盖、不得整段重写。要纠正旧结论就新加一段，写明"更正上一条"。
- 环境变量未设置时，在回复里说明"未找到 BETTER_MAS_DEV_REPORT"，不要自己挑路径写。

## 10. 测试纪律与完成定义

测试纪律：

- 写后先测试再审查：先跑测试与检查命令，再自查代码、再请人评审。
- 测试不发送真实网络请求。用夹具、假客户端、本机 `TestClient`（`base_url="http://127.0.0.1"`）替代，需要联网的用例标注并跳过。
- 测试不访问真实用户凭据与真实账号数据；用临时目录（`tmp_path`）和假令牌。
- 测试启动的服务、子进程、浏览器必须验证后关闭；测试里创建的 `TestClient` 用 `with` 或显式 shutdown。
- 回归测试随实现一起提交，放在 `tests/`；前端用例与源码同目录（`*.test.ts`）。

完成定义（按改动范围取交集，全部实际执行过才能说"完成"）：

| 改动范围 | 必跑 |
| --- | --- |
| 后端代码 | `ruff check app main.py scripts` + `pytest -q` |
| 前端代码 | `yarn lint` + `yarn typecheck` + `yarn test`，影响构建时加 `yarn build` |
| 移植文件 | `scripts/verify_upstream.py --local` |
| 打包/桌面 | `scripts/build-desktop.ps1` 与 `scripts/verify-desktop.py` |
| 安卓 | 见 §11 的 Gradle 任务集 |
| 用户可见改动 | 一个 `changelog.d/` 碎片 |

- 结果如实记录，不编造测试输出。没跑就说没跑，跑失败就贴失败信息。

## 11. 常用命令

环境准备（一次）：

```powershell
uv sync --locked --dev --extra captcha --link-mode=copy
Push-Location frontend; try { yarn install --immutable } finally { Pop-Location }
```

源码启动：

```powershell
powershell -File scripts/start-source.ps1        # 装依赖、构建、起 Electron
.venv\Scripts\python.exe main.py --port 37164   # 只起后端
# frontend 目录
yarn dev                                          # 浏览器访问 http://127.0.0.1:37165
```

后端检查：

```powershell
.venv\Scripts\python.exe -m ruff check app main.py scripts
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_upstream.py --local
```

前端检查与构建（frontend 目录）：

```powershell
yarn lint
yarn typecheck
yarn test
yarn format
yarn build
```

OpenAPI 客户端再生成（改了 app/models 或路由之后）：

```powershell
.venv\Scripts\python.exe scripts/export_openapi.py
# frontend 目录
yarn openapi
```

桌面打包与校验：

```powershell
powershell -File scripts/build-desktop.ps1          # 打包；加 -Zip 出完整分发包
.venv\Scripts\python.exe scripts/verify-desktop.py frontend/out/win-unpacked
powershell -File scripts/start-desktop.ps1          # 启动已打包版本
```

安卓（先设 `JAVA_HOME`、`ANDROID_SDK_ROOT`、`ANDROID_HOME`、`GRADLE_USER_HOME`）：

```powershell
.venv\Scripts\python.exe scripts/prepare-android.py --skip-frontend
# android 目录
.\gradlew.bat --no-daemon :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
# 产物：android/app/build/outputs/apk/debug/app-debug.apk
# 打包资源界面回归（不进 CI）
frontend\node_modules\electron\dist\electron.exe scripts/verify-android.cjs
```

变更碎片与发版：

```powershell
.venv\Scripts\python.exe scripts/changelog.py add fix "修复 xxx"
.venv\Scripts\python.exe scripts/changelog.py current
.venv\Scripts\python.exe scripts/changelog.py release --version X.Y.Z
.venv\Scripts\python.exe scripts/changelog.py guard --tag vX.Y.Z
.venv\Scripts\python.exe scripts/changelog.py release-note --version X.Y.Z --output release-note.md
```

## 12. 提交与发版流程要点

提交信息（沿用仓库既有实践）：

- Conventional Commits：英文 `type(scope)` + 中文描述，句末不加句号。
- 例：`feat(api): 新增账号导入接口`、`fix(release): 修复 Android versionCode 计算`。
- 一个逻辑改动一个提交；不要把无关格式化、无关文件混进同一个提交。
- 用户可见改动附一个 `changelog.d/` 碎片：`<id>.<类型>.md`（`feat`/`change`/`fix`/`perf`/`security`），正文一行面向用户的中文描述。不要手改 CHANGELOG.md 顶部版本段。

发版流程（未经用户要求不执行）：

- `CHANGELOG.md` 顶部版本段是版本号与 Release 正文的唯一来源，分类固定为 新增/变更/优化/修复/安全。
- `changelog.py release --version X.Y.Z` 归并碎片、写日期、同步版本生成物；`guard` 校验 tag 与 CHANGELOG、各处版本号、`changelog.d` 是否已清空。
- `.github/workflows/windows-release.yml` 与 `.github/workflows/android-release.yml` 由 `v*` tag 触发：先 guard，再构建，最后发 draft Release。
- `.github/workflows/deploy-cf.yml` 只有手动触发，不要给它加回 push 触发。

## 13. 禁止事项清单

| 禁止 | 原因 / 替代做法 |
| --- | --- |
| 手改 `frontend/src/api/**` | 生成物；改后端模型后 export_openapi.py + yarn openapi |
| 手改 `android/app/src/main/assets/**` | 由 prepare-android.py 生成 |
| 组件里写死中文 | 文案进 `frontend/src/i18n/locales/` |
| 提交凭据、日志、`data/`、`local/` | 隐私与许可证要求 |
| 未经要求 commit / push / 建远程 / 发版 / 改版本号 | 发布边界 |
| 擅自 `verify_upstream.py --update` | 它会改清单摘要，等于放宽校验 |
| 删除或覆盖历史开发报告 | 台账只追加 |
| 测试发真实消息、读真实凭据、留下未关闭的服务 | 测试纪律 |
| 把 AUTO-MAS 检出路径写成运行依赖或复制 AGPL 代码 | 许可证与独立性 |
| 反向 import 或把业务逻辑塞进 `app/api` | 分层边界 |
| 顺手大规模重构、全仓格式化 | 一个提交一件事 |
| 新增 `errorCode` 字段、引入 `/api/v2` | 契约变更只做加法，状态码即 code |
| 在日志、报错、文件名里带出凭据 | 脱敏要求 |

以上之外拿不准的，先按最小改动推进，在回复里点名请用户裁决，并把这个问题记进开发报告。
