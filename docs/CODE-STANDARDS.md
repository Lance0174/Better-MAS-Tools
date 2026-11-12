# 代码规范

本文件是 [AGENTS.md](../AGENTS.md) 的细则，回答"具体怎么写"。每条按 **规则 / 为什么 / 反例** 展开；反例用来划边界，不是禁用的语法本身。

## 0. 适用范围

适用：

- `app/`、`main.py`、`scripts/`、`tests/` 下的 Python 代码。
- `frontend/src`、`frontend/electron` 下手写的 Vue/TS 代码。
- `android/` 下手写的 Java、Gradle 脚本。
- 上述区域的注释、docstring、提交信息、文档。

不适用（改了也会被生成流程覆盖）：

- `frontend/src/api/`：OpenAPI 生成物。
- `android/app/src/main/assets/`：`scripts/prepare-android.py` 生成。
- `deploy/worker/` 下的依赖产物与打包结果。
- `CHANGELOG.md` 的版本汇总段：由 `scripts/changelog.py release` 写入。

## 1. 通用原则

### 1.1 可读性优先

- **规则**：让半年后的陌生人能顺着读下去，优先于少写几行。命名、分支层次、早返回都比"技巧"重要。
- **为什么**：本仓是多人（多 agent）协作的社区工具，读的次数远多于写的次数。
- **反例**：把三层条件塞进一个嵌套三元表达式，只为省掉一个 `if`。

### 1.2 显式编排优于抽象

- **规则**：流程写在调用处，步骤一行一步；不要为"以后可能复用"提前造框架。
- **为什么**：编排逻辑是排障的第一现场，抽象一层就多一次跳转。
- **反例**：为两个调用点写一个 `RunnerFactory` + 注册表 + 装饰器。

### 1.3 不过度抽象

- **规则**：同一段逻辑出现第三处再抽函数；两处重复通常比错误的抽象便宜。
- **为什么**：过早抽象会把两个本会分叉的需求焊死在一起。
- **反例**：把"读设置、拼参数、发请求"合成一个 `do_everything()`，调用方无法只做其中一步。

### 1.4 就近原则

- **规则**：常量、辅助函数放在第一个使用它的模块里；跨模块共享才上移。
- **为什么**：远处的共享模块会变成杂物间，改动影响面无法评估。
- **反例**：只有一个 API 模块用到的字段名常量放进 `app/utils/constants.py`。

### 1.5 一次只改一件事

- **规则**：一个提交（一次改动）只解决一个问题。顺手发现的无关问题记进开发报告，另起改动。
- **为什么**：评审与回滚都以"一件事"为单位。
- **反例**：修一个 500 错误时顺带把整个文件重排、改引号风格。

### 1.6 错误必须可诊断

- **规则**：任何失败都要留下"哪一步、什么输入、什么原因"的痕迹；对用户给可行动的中文提示，对日志给细节。
- **为什么**：这个工具跑在用户机器上，用户能提供的只有截图和日志。
- **反例**：`except Exception: pass`，或只回一句"操作失败"。

### 1.7 注释是资产

- **规则**：注释解释"为什么"，不复述"是什么"；协议怪癖、平台限制、绕过原因必须写清。仍然有效的注释不要删。
- **为什么**：这些知识不在代码里就只能靠口口相传。
- **反例**：`# 循环` 写在 `for` 上方；同时删掉"该接口要求先带 cookie 才能拿 QR"这类关键说明。

### 1.8 不重复下层校验

- **规则**：下层已经校验或已经抛错的地方，上层不再重复判断。
- **为什么**：重复校验会分叉出两套错误文案，改一处漏一处。
- **反例**：`app/tools` 已经对空 token 抛 `ValueError`，`app/api` 里再判一次并回不同文案。

### 1.9 依赖最小化

- **规则**：新增第三方依赖要有明确理由，并确认许可证兼容；能用标准库就不引包。
- **为什么**：桌面与安卓都要打包进去，依赖直接变成体积与供应链风险。
- **反例**：为一个字符串替换引入一个新库。

## 2. Python

### 2.1 类型标注

- **规则**：公开函数、模块级常量、数据类字段都写类型；空值用 `X | None`，容器写元素类型（`list[str]`、`dict[str, object]`）。项目要求 Python 3.12，PEP 604 写法可直接用。
- **为什么**：类型是给读者的第一份契约，也是 `ruff` 与 IDE 的检查依据。
- **反例**：

```python
def load(data, strict=False):  # 参数与返回值都没有类型
    ...
```

### 2.2 命名

- **规则**：函数与变量 `snake_case`，类 `PascalCase`，模块级常量 `UPPER_SNAKE_CASE`；布尔用 `is_` / `has_` / `can_` 前缀；函数用动词开头（`load_`、`build_`、`resolve_`、`ensure_`、`require_`、`clear_`、`reset_`）。
- **为什么**：前缀让调用处一眼看出这是动作还是取值。
- **反例**：`def user_info()` 既读又写；`flag2`、`tmp`、`data1`。

- **规则**：平台标识保持既有拼写不改写：`genshin`、`starrail`、`zzz`、`wuthering`、`arknights`、`endfield`。
- **为什么**：这些字符串同时出现在协议、配置与前端，改名即断兼容。
- **反例**：把 `starrail` 统一成 `star_rail`。

### 2.3 导入与分层

- **规则**：用绝对导入（`from app.utils.logger import get_logger`）；导入顺序交给 ruff 的 `I` 规则；遵守 AGENTS.md §5 的依赖方向。
- **为什么**：相对导入在跨包移动时容易断；分层约束是防止循环依赖的唯一手段。
- **反例**：`app/models/schema.py` 里 `from app.services.storage import StateStorage`。

### 2.4 函数与副作用

- **规则**：函数做一件可命名的事；布尔参数与多参数调用用关键字参数；副作用（写盘、发请求、改全局状态）在函数名或 docstring 里写出来。
- **为什么**：调用处 `run(True, False)` 读不出含义；隐藏副作用是排障黑洞。
- **反例**：

```python
save(state, True, False)   # 调用处读不出这两个布尔值分别控制什么
```

### 2.5 异常

- **规则**：预期失败用 `ValueError`（`app/main.py` 统一转 400）；"已有任务在跑"这类并发冲突用具名异常 `CommunitySignInProgressError`（注册为 409，见 `app/tools/community_contract.py:60`）。`try/except` 只写在层边界，捕获后要么处理、要么补上下文再抛。
- **为什么**：异常类型就是契约；在中间层吞掉异常会让上层只能回 500。
- **反例**：

```python
try:
    payload = json.loads(text)
except Exception:
    return {}          # 吞掉了解析失败，调用方以为成功
```

- **反例**：在 `app/tools` 里直接 `raise HTTPException(status_code=400)`——工具层不该知道 HTTP。

### 2.6 日志与脱敏

- **规则**：模块级 `logger = get_logger("中文模块名")`；写日志前用 `sanitize_log_message`（`app/utils/security.py:35`）处理可能带凭据的文本；请求内日志用 `logger.contextualize(requestId=...)`，响应头带 `X-Request-ID`。
- **为什么**：日志会被用户导出并贴到公开 issue 里，脱敏是硬要求；requestId 让用户截图能对上日志行。
- **反例**：`logger.info(f"登录参数 {body}")`，`body` 里有密码。

- **规则**：文件日志由 `configure_file_logging`（`app/utils/logger.py:50`）统一配置，5 MB 轮转、保留 7 天；不要在模块里另建 handler 或另写日志文件。
- **为什么**：多份 handler 会造成重复行与不可控的磁盘占用。
- **反例**：某个 service 里 `logging.basicConfig(filename=...)`。

### 2.7 异步与取消

- **规则**：阻塞调用放进 `asyncio.to_thread`；后台任务保存句柄，退出时 `task.cancel()` 后 `await asyncio.gather(task, return_exceptions=True)`；开始新任务前用 `runtime.require_idle()`（`app/core/runtime.py:25`）检查是否已有任务。
- **为什么**：事件循环里跑同步 IO 会卡住所有接口；不 await 的取消会留下半截状态。
- **反例**：`asyncio.create_task(...)` 之后丢掉返回值，进程退出时任务被硬切断。

### 2.8 原子写盘与权限

- **规则**：写 JSON/文本用 `atomic_write_text`（`app/utils/atomic_io.py:14`）或 `StateStorage`（`app/services/storage.py:23`）；先落盘成功再更新内存；数据目录 `0o700`、文件 `0o600`。
- **为什么**：用户可能在写入瞬间关机，半截 JSON 会让应用下次起不来；账号文件权限过宽等于泄露。
- **反例**：

```python
path.write_text(json.dumps(payload), encoding="utf-8")  # 断电即损坏
state.accounts = accounts                                # 先改内存再写盘，失败后内外不一致
```

### 2.9 Pydantic 模型

- **规则**：用 Pydantic v2；字段写中文 `Field(description=...)`；固定取值的字段用 `Literal`；可变默认值用 `default_factory`；密码类字段用 `SecretStr` 且 `repr=False`。
- **为什么**：`description` 会进 OpenAPI 与前端类型注释，是唯一的字段说明来源。
- **反例**：`tags: list[str] = []`（可变默认值共享）；`password: str` 直接进 `repr` 后被日志打印。

### 2.10 docstring

- **规则**：新代码与新文件统一 Google 风格（`Args` / `Returns` / `Raises`）。已经移植过来的文件里原有的 Sphinx 风格 docstring（`:param:` / `:returns:`）保持不动，不为了统一而重排旧文件。
- **为什么**：统一新代码降低阅读成本；重排旧文件会产生大量与被移植逻辑无关的 diff，让上游对照失效。
- **反例（新文件不要这么写）**：

```python
def resolve_account(account_id: str) -> Account:
    """同步账号。

    :param account_id: 账号 ID
    :returns: 账号
    """
```

- **正例**：

```python
def resolve_account(account_id: str) -> Account:
    """按 ID 取账号副本。

    Args:
        account_id: 前端生成的账号 ID。

    Returns:
        匹配的账号副本。

    Raises:
        ValueError: 账号不存在。
    """
```

### 2.11 测试命名与组织

- **规则**：用例放 `tests/`，文件名 `test_<模块>.py`，函数名 `test_<行为>_<预期>`；一个用例只锁一个行为；用 `tmp_path` 建临时数据目录；`create_app(data_dir=..., start_scheduler=False)` 起服务，`TestClient(..., base_url="http://127.0.0.1")` 配合请求头 `x-community-session` 走真实中间件。
- **为什么**：`base_url` 必须回环，否则被 `TrustedHostMiddleware` 拒绝；关掉调度器才能让用例确定可重复。
- **反例**：

```python
def test_all(tmp_path):     # 名字读不出行为，一次断言十件事
    ...
client = TestClient(app)    # 默认 base_url 是 testserver，会被 Host 校验拦下
```

### 2.12 ruff

- **规则**：`line-length = 88`，规则集 `E4/E7/E9/F/I`（见 `pyproject.toml`），`known-first-party = ["app"]`；不新增 `# noqa` 除非写明原因。
- **为什么**：规则集刻意收窄，保持现状可全绿；随手加规则会让全仓变红。
- **反例**：`import os  # noqa: F401` 只是为了暂时不删。

## 3. 前端

### 3.1 Vue 3 script setup

- **规则**：单文件组件用 `<script setup lang="ts">`；顺序为 `import` → `defineProps/defineEmits` → 响应式状态 → 计算属性 → 方法 → `onMounted` 等生命周期；页面放 `frontend/src/views/<模块>/index.vue`，可复用组件放 `frontend/src/components/`。
- **为什么**：固定顺序让 review 时能直接跳到关心的段落。
- **反例**：在 `<script setup>` 里混用 Options API 的 `mounted()`。

- **规则**：`defineProps` 用泛型声明；事件用 `defineEmits<{ change: [value: string] }>()`。
- **为什么**：运行时 props 声明拿不到类型推导，`vue-tsc` 检查不出来。
- **反例**：`defineProps(['title', 'items'])`。

### 3.2 TypeScript 严格性

- **规则**：`frontend/tsconfig.app.json` 已开 `strict`；不用 `any` 兜底，确实未知用 `unknown` 再收窄；不用 `!` 断言掩盖可能为空的值。
- **为什么**：`any` 会让下游所有推断失效，等于关掉类型检查。
- **反例**：`const data = response as any`。

### 3.3 Ant Design Vue 注册

- **规则**：组件在 `frontend/src/main.ts` 的导入列表与注册循环里按字母序统一注册，页面里直接用 `<a-button>` 等标签，不逐个组件局部 import。（`frontend/src/main.ts:53` 起是注册循环。）
- **为什么**：注册表是"哪些组件可用"的唯一事实来源，散落的局部注册会导致同名组件行为不一致。
- **反例**：页面里 `import { Button } from 'ant-design-vue'` 后又混用全局标签。

- **规则**：提示与确认用函数式 API（`message.success`、`Modal.confirm`）；危险操作（删除账号、清空记录）必须二次确认。
- **为什么**：命令式调用不会在模板里留下隐藏状态，也便于在 catch 分支里给反馈。
- **反例**：点击"删除"直接发请求。

### 3.4 i18n

- **规则**：只维护 zh-CN。所有用户可见文案进 `frontend/src/i18n/locales/zh-CN.ts`（通用）或 `frontend/src/i18n/locales/standalone.ts`（独立版页面），组件和视图里禁止硬编码中文；用 `t('namespace.key')`，key 用命名空间 + 小驼峰。
- **为什么**：文案集中后才能被词表守卫测试覆盖，也才有将来加语种的可能。
- **反例**：

```vue
<a-button>立即签到</a-button>
```

- **规则**：新增 key 后跑 `yarn test`，`frontend/src/i18n/locales.test.ts` 会把源码里引用但词表缺失的 key 全部列出来。
- **为什么**：已知缺口——缺键时没有全局回退，vue-i18n 会把裸 key（如 `standalone.fooFailed`）直接渲染到界面上；`fallbackLocale` 在单语种配置下帮不上忙，只有这条测试能在合并前拦住。
- **反例**：在模板里拼 `t('standalone.' + name)` 却不把 `name` 的所有取值写进词表。

### 3.5 样式与设计令牌

- **规则**：颜色、边框、圆角用 Ant Design 的 CSS 变量（`var(--ant-color-bg-container)`、`var(--ant-color-border)` 等，见 `frontend/src/style.css`），间距按 4/8 的倍数；穿透组件内部样式时把 `:deep()` 限定在具体父类下。
- **为什么**：写死色值在深色模式下必然读不清；无限定的 `:deep()` 会污染全站。
- **反例**：`:deep(.ant-btn) { ... }` 没有父级选择器。

### 3.6 状态管理与组合式函数

- **规则**：跨页面状态放 Pinia（`frontend/src/stores/`），页面内状态留在组件里；接口调用写在 `frontend/src/composables/use*Api.ts`，错误文案统一走 `errorMessage(cause, t('...'))`（`frontend/src/composables/useCommunityApi.ts:26`），兜底文案由调用方从词表传入。
- **为什么**：桥接层不该硬编码中文，否则 i18n 规则在中间层破功。
- **反例**：`catch { message.error('请求失败') }`。

- **规则**：轮询用 `setTimeout` 链并在 `onUnmounted` 清理；按钮防连点用 `createSequenceGuard` / `createDebouncer`（`frontend/src/utils/asyncGuard.ts`）。
- **为什么**：`setInterval` 在慢请求下会堆叠，组件卸载后仍会触发。
- **反例**：`setInterval(poll, 1000)` 且没有清理。

### 3.7 禁止手改生成物

- **规则**：`frontend/src/api/` 由 `yarn openapi` 生成，禁止手改，包括"只改一行类型"。
- **为什么**：下次生成会覆盖，且会让契约与后端模型脱节。
- **反例**：直接在 `frontend/src/api/models/` 里补一个可选字段。

### 3.8 前端测试

- **规则**：用例与源码同目录、命名 `*.test.ts`，用 Vitest；默认 node 环境，当前不引 jsdom，需要 DOM 时先说明理由再引入。
- **为什么**：node 环境跑得快且不需要额外依赖；现有用例（词表守卫、logger、asyncGuard）都不需要 DOM。
- **反例**：为了让一个组件快照跑起来，顺手给全仓加 jsdom 与测试库。

### 3.9 文件规模

- **规则**：新文件软上限 400 行，超过要在提交说明或开发报告里写理由并尽量拆分；`frontend/src/App.vue`、`frontend/src/views/gamesign/useQrLogin.ts` 等存量超限文件不强制重构，只在正好要改时顺手拆。
- **为什么**：硬性重构会制造巨大 diff，收益却低于风险。
- **反例**：新建一个 900 行的页面组件且不解释。

## 4. API 契约

### 4.1 路由与 operationId

- **规则**：路由挂在 `/api/<资源复数>`；每个端点写 `operation_id`（小驼峰动词开头，如 `listAccounts`、`updateSettings`）与 `tags`（模块名）；路由函数只做参数校验、调用下层、拼响应模型。
- **为什么**：`operation_id` 决定生成客户端的方法名，写错会让前端调用点莫名变形。
- **反例**：

```python
@router.get("/api/account/list")     # 单数 + 动词路径
async def get_accounts():            # 没有 operation_id，生成名退化成 getAccountsApiAccountsGet
```

### 4.2 请求 / 响应模型

- **规则**：请求体 `XxxIn`，响应体 `XxxOut` 并继承 `OutBase`（`app/models/schema.py:31`），列表用 `XxxsOut`；每个端点显式写 `response_model`（或返回标注），不返回裸 `dict`。
- **为什么**：`OutBase` 带 `code`/`message`，前端 `assertSuccess` 依赖它判断业务结果。
- **反例**：`return {"ok": True}`。

### 4.3 错误与 status=partial

- **规则**：错误体固定 `{"code": <HTTP 状态码>, "status": "error", "message": "<脱敏中文>"}`。继续用 HTTP 状态码作为机器可读的 `code`，不新增 `errorCode` 字段。
  - 400：`ValueError`（`app/main.py` 的处理器统一转换，附日志编号）。
  - 401：会话失效；403：来源不受支持；409：已有任务在跑（`CommunitySignInProgressError`）。
  - 422：请求体字段校验失败（`RequestValidationError`）。
  - 500：只回固定文案 + 日志编号，细节进日志。
- **为什么**：生成客户端按状态码抛 `ApiError`，`errorMessage` 再从 `body.message` 取文案；多一个字段就多一层没人读的分支。
- **反例**：业务失败 `return OutBase(code=500, ...)` 并配 HTTP 200。

- **规则**：部分成功用 `status="partial"` 表示（已有实现见 `app/api/gacha.py:57`），并在 `message` 或数据里说明哪些条目失败。
- **为什么**：批量导入/抓取里"一半成功"是常态，直接报错会让用户重做全部。
- **反例**：部分失败时把失败条目静默丢掉，仍回 `success`。

### 4.4 会话与安全头

- **规则**：`/api/` 下除 `/api/session` 外都要求 `x-community-session`；新增静态路由要同步 CSP 白名单（`app/main.py` 中间件）；健康检查 `/healthz` 保持 `include_in_schema=False`。
- **为什么**：漏掉会话语义等于开了一个无鉴权入口；CSP 漏配会让新资源在浏览器里被静默拦掉。
- **反例**：新增 `@app.get("/api/export")` 却忘了它走的是同一中间件的前缀判断（前缀是 `/api/`，会被要求会话——真需要公开就放到前缀外并说明）。

### 4.5 向后兼容

- **规则**：契约变更只做加法：加可选字段、加新端点；不改既有字段名与类型，不删字段，不引入 `/api/v2`。ID 一律字符串。
- **为什么**：桌面端与安卓端的旧前端会和新的后端同时存在（用户不一定会立刻升级）。
- **反例**：把 `accountId: str` 改成 `id: int`。

### 4.6 OpenAPI 再生成

- **规则**：改了 `app/models` 或路由后：`.venv\Scripts\python.exe scripts/export_openapi.py`，再在 `frontend` 目录 `yarn openapi`；生成物一起提交，不手改。
- **为什么**：`frontend/openapi.json` 是两端唯一的契约快照。
- **反例**：只改后端，前端手写一个临时类型顶上。

## 5. 数据模型

### 5.1 组织与命名

- **规则**：`app/models/schema.py` 放 API 契约，`app/models/config.py` 放设置与持久化配置，`app/models/gacha.py` 放抽卡域模型；契约字段用 camelCase（与前端一致），持久化配置字段用 PascalCase（与既有设置文件一致）。
- **为什么**：两类模型一处对前端、一处对磁盘，混住会让"改字段"同时踩两边。
- **反例**：把 `SettingsData` 里的 `MasBaseUrl` 改成 `masBaseUrl`。

### 5.2 字段类型与默认值

- **规则**：时间字段存 UTC 或明确时区（项目内展示统一 UTC+8）；长度上限与前端 `maxlength` 对齐（如 `max_length=80` 由 `tests/test_api_contract.py` 锁死）；列表默认值用 `default_factory`。
- **为什么**：前后端长度不一致时用户能输入但保存失败，报错还看不出原因。
- **反例**：前端限 80 字，后端不限。

### 5.3 `extra="forbid"` 的兼容风险

- **规则**：`app/models/config.py` 与 `app/models/gacha.py` 用了 `extra="forbid"`（`app/models/config.py:11`）。给这些模型加字段时要考虑旧文件：老数据缺少新字段可以靠默认值补，但**旧版本读到含新字段的文件会直接校验失败**。新增字段一律给默认值，并在读取路径上容忍旧文件。
- **为什么**：用户回退版本、或云端同步来一份新数据，都会踩这个坑。
- **反例**：给设置模型加一个必填字段，导致老用户升级后一启动就 `ValidationError`。

## 6. 提交信息

- **规则**：Conventional Commits，英文 `type(scope)` + 中文描述，句末不加句号。
  - 例：`feat(api): 新增账号导入接口`、`fix(release): 修复 Android versionCode 计算`、`docs(standards): 补充前端文件规模约定`。
- **规则**：一个逻辑改动一个提交；用户可见改动附一个 `changelog.d/<id>.<类型>.md` 碎片（`feat`/`change`/`fix`/`perf`/`security`），正文一行面向用户的中文描述。
- **为什么**：仓库既有历史就是这个格式，`scripts/changelog.py` 按类型归并。
- **反例**：`update code`、`修复bug。`、`feat: 加功能（顺带格式化全仓）`。

## 7. 提交前检查表

逐条勾选，全部实际执行过再报告完成：

- [ ] `.venv\Scripts\python.exe -m ruff check app main.py scripts` 通过。
- [ ] `.venv\Scripts\python.exe -m pytest -q` 通过（贴条数）。
- [ ] `frontend` 下 `yarn lint` 通过。
- [ ] `frontend` 下 `yarn typecheck` 通过。
- [ ] `frontend` 下 `yarn test` 通过（新增文案时确认词表守卫生效）。
- [ ] 改了前端构建相关配置时，`frontend` 下 `yarn build` 通过。
- [ ] 改了 `app/models` 或路由时，重跑了 `scripts/export_openapi.py` 与 `yarn openapi`，生成物无手改痕迹。
- [ ] 改了移植文件时，`.venv\Scripts\python.exe scripts\verify_upstream.py --local` 通过。
- [ ] 改了打包链路时，`scripts/build-desktop.ps1` 与 `scripts/verify-desktop.py frontend/out/win-unpacked` 通过。
- [ ] 改了安卓时，`.\gradlew.bat --no-daemon :app:assembleDebug :app:testDebugUnitTest :app:lintDebug` 通过。
- [ ] 没有提交凭据、日志、`data/`、`local/`；新增注释里没有密码。
- [ ] 用户可见改动有且只有一个 `changelog.d/` 碎片，未改 `CHANGELOG.md` 与任何版本号。
- [ ] 提交信息符合 `type(scope): 中文描述`，一个提交一件事。
- [ ] 开发报告（`BETTER_MAS_DEV_REPORT`）已追加本次记录，含命令与真实输出。
- [ ] 测试启动的服务、子进程已关闭。

## 8. 本仓交互与集成约定

- **首次引导**：完成、跳过、关闭按钮均视为已处理，状态由后端配置持久化；不能仅依赖浏览器 localStorage，桌面随机端口会改变来源。手动重看不清除已处理状态。
- **轻量模式**：开启前确认，说明窗口关闭、托盘入口和无法唤回的风险。桌面壳收到相同的启用状态不得再次销毁窗口；托盘、第二次启动都应能唤回。
- **MAS 集成**：经已安装 MAS 自带的 `/mcp`，只调用本工具需要的队列和运行控制工具。只读公开契约，不读取其账号、配置文件或私有状态，不复制上游实现。受理请求不等于任务成功，变更请求超时不得自动重放。
- **抽卡来源**：优先复用所选社区账号的官方授权，再提供链接、JSON 和已支持的第三方导入。Cookie、临时 authkey 和导入原文不落盘、不回显；重建记录必须标明来源及不确定性。部分导入不得删掉未成功导入部分的旧记录；导入数量须在展开列表前限制，派生标识应区分同秒的不同道具。
- **连接回退**：只对确认需要的官方域名处理连接阶段失败；保留 TLS 主机名和证书校验，不绕过用户显式代理。不把 localhost 或任意用户地址发送给公共 DNS，不重放已发出的业务请求。
- **UI 审批**：需要用户先审核的视觉改版先放独立 HTML/SVG 原型；用示例数据，无真实账号或网络依赖。记录桌面、窄屏、深浅主题的检查结果，审核通过后才应用正式界面。
- **发布边界**：Cloudflare 部署暂缓，用户入口与发布材料不承诺其交付。保留历史实现供后续恢复，不执行远端写入或发布。

这些约定以本仓的 Vue 3、Ant Design Vue、FastAPI、原子加密存储及多运行时实践为准。`.agents/skills/mas-*` 随源码维护，统一引用本仓文档；AUTO-MAS 仅作结构参考，其组织流程、配置容器、版本分支及发布约定不适用。已审核的 Miuix 风格、实际组件映射及双端边界见 [UI-STANDARDS.md](UI-STANDARDS.md)。
