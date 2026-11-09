# Better-MAS-Tools 开发接口

所有业务接口在`/api`下，用OpenAPI定义模型；前端通过生成客户端和composable调用。后端默认环回端口37164，桌面外壳使用自身随机端口。

先GET `/api/session`。本机模式返回临时`key`，远端模式返回`loginRequired=true`，再POST同一路径提交`{"password":"自己的访问密码"}`换取会话。除`/api/session`外的所有`/api/*`请求都必须带`X-Community-Session: <key>`，缺失或失效返回401；带`Origin`的请求还必须与部署配置匹配（本机模式用当前Host，远端模式用`COMMUNITY_PUBLIC_ORIGIN`），否则返回403。这层校验在`app/main.py`的`local_session`中间件里，与具体路由无关。会话只在内存保留，不写浏览器存储。

| 路径 | 用途 |
| --- | --- |
| `/api/accounts` | 账号列表与新增；更新、删除等契约以OpenAPI为准 |
| `/api/settings` | 读取/保存设置，YunmaToken始终脱敏；null保留旧密钥，空字符串清除 |
| `/api/status` | 运行状态、北京时间today和各平台结果 |
| `/api/sign` | POST立即执行一次签到（force，不按今日是否已签去重） |
| `/api/logs` | GET读取当前实例最近2000条脱敏日志；requestId关联一次请求 |
| `/api/logs/export` | GET返回filename/content；本机导出当前日志文件，Workers导出实例内存日志 |
| `/api/logs/frontend` | POST level、module、message写入前端诊断；仍经过后端统一脱敏 |
| `/api/login/kuro/sms/create` | accountId＋phone创建10分钟会话 |
| `/api/login/kuro/sms/automatic` | sessionId尝试自动验证和发短信；sent=false时按message转人工 |
| `/api/login/kuro/sms/send` | sessionId＋完整极验4verification发送短信 |
| `/api/login/kuro/sms/login` | sessionId＋smsCode登录，自动保存正式Token及设备标识 |
| `/api/login/kuro/sms/cancel` | 取消会话和正在运行的自动验证 |
| `/api/gacha` | GET按game、playerUid、pool、page、pageSize查询记录及统计 |
| `/api/gacha/fetch` | POST读取官方记录；source只在本次请求使用 |
| `/api/gacha/fetch-cookie` | POST用米游社Cookie换取authkey后读取官方记录；cookie留空则用账号组已绑定凭据，仅原神/崩铁/绝区零，尚未用真实账号验收 |
| `/api/gacha/import` | POST game＋payload（JSON字符串）导入，原数据合并去重 |
| `/api/gacha/heybox` | POST heyboxId、playerUid、payload导入小黑盒「抽卡分析」响应；六星用真实记录，其余抽数补四星占位行与五星补名 |
| `/api/gacha/heybox` | DELETE按playerUid撤销该 UID 的小黑盒补录行；官方六星记录不受影响 |
| `/api/gacha/export` | GET game、playerUid、fileFormat=bmasc或uigf，返回filename/content |
| `/api/accounts/reorder` | POST保存拖动顺序order；签到或便笺执行中返回409 |
| `/api/activity` | POST按accountIds查询日常便笺快照，含任务、资源、角色与服务 |
| `/api/wiki/status` | GET返回资料库索引状态：ready、version、updatedAt、counts与体检结果 |
| `/api/wiki/sync` | POST同步终末地资料索引，可选force；返回同步后的状态 |
| `/api/wiki/search` | GET按q、limit（1–50）检索名称、昵称、简称与同音字 |
| `/api/wiki/entry` | GET按kind、id读取资料卡；kind限定character、weapon、equipSuit、dungeon、enemy |
| `/api/wiki/calendar` | GET按game读取单个游戏的活动日历 |
| `/api/wiki/calendar-all` | GET一次返回八个游戏的活动日历，各游戏失败互相隔离 |
| `/api/relay/command` | POST提交type、payload放进转发队列；type限定mas.snapshot、mas.start、mas.stop、sign.run |
| `/api/relay/poll` | POST按nodeId长轮询领取指令，最多挂起25秒（`POLL_HOLD_SECONDS`） |
| `/api/relay/result` | POST提交nodeId、commandId、ok、data、error回传执行结果 |
| `/api/relay/nodes` | GET列出执行节点及在线状态 |
| `/api/relay/commands/{command_id}` | GET查询单条指令的状态与结果 |
| `/api/cloud/sync` | POST提交accounts、miyoushe_bbs，在云端临时内存执行签到并返回结果，不落盘 |
| `/api/mas/snapshot` | GET 经本机 MAS 的 `/mcp` 读取队列与运行快照 |
| `/api/mas/start` | POST提交taskId、mode（AutoProxy或CycleRun）请求MAS启动，返回taskId |
| `/api/mas/stop` | POST提交taskId，经 MAS MCP 请求停止任务 |
| `/api/miyoushe/verification` | GET列出待人工处理的米游币验证会话 |
| `/api/miyoushe/verification/submit` | POST提交sessionId＋verification，验证后继续该次执行 |
| `/api/login/{provider}/qr/create` | POST创建扫码二维码；provider为miyoushe或skland |
| `/api/login/{provider}/qr/check` | POST按ticket、device查询扫码状态并取回凭据 |
| `/api/login/{provider}/qr/save` | POST按accountUid、cookie、scanCode保存登录凭据 |
| `/api/login/taygedo` | POST按accountId、phone、password一次性登录并保存凭据 |

抽卡 game 枚举为 `genshin`、`starrail`、`zzz`、`wuthering`、`arknights`、`endfield`。米家三游戏优先通过米游社 Cookie 换取临时 authkey，也可使用官方链接、UIGF/Starward JSON；只有网页 cookie_token 而没有 stoken 的凭据暂不支持换取。鸣潮使用官方链接或请求 JSON。明日方舟、终末地优先使用森空岛 accountId 与 playerUid；终末地也可传含 u8_token 的官方链接。六款游戏均可导入本工具的 BMASC JSON。终末地另可粘贴小黑盒「抽卡分析」overview 响应补录历史：六星保留原始时间，五星补名与四星占位是推算记录，明确标识并可撤销；被跳过卡池的旧补录不被删除。Cookie、临时授权和 overview 响应不落盘。

MAS 接入仅调用 `/mcp` 的 Streamable HTTP 入口，完成初始化、工具发现后调用队列查询、运行快照、启动和停止四个工具。不绕过 MCP 回退到 REST，也不开放任意工具调用。MAS 启动初期可能尚未挂载 MCP，404 时提示稍后重试；任务变更不自动重试，启动成功只表示已受理。仅接受环回服务地址，禁止跳转到外部地址。

小黑盒补录在展开记录前按单次 20 万条限制数量（含免费十连），拒绝负抽数和无效十连位置。五星补名按剩余抽数限制展开，同秒不同五星与四星占位具有独立标识；超限或校验失败时不写入、不清除已有记录。

`SettingsData.OnboardingDismissed` 默认为 false，完成或跳过引导后置为 true 并随配置保存。旧设置草稿不能将 true 回写为 false；设置页仍可手动重新查看引导。浏览器本地标记仅用于旧版迁移，不作为桌面随机端口下唯一的持久化来源。

签到结果的`games[].status`保留游戏与社区的合并完成状态。新版库街区结果另外提供`details`，每项包含`kind`（`game`或`community`）、`status`、`reward`和`reason`，用于分别展示游戏签到与库洛币签到；账号共享的社区签到只附在一条游戏结果中，统计时只计算一次。旧记录没有分项数据，`details`为空，不应据此推断游戏或社区单独成功；各分项的执行时间沿用所属结果的`signedAt`。

记录ID保持字符串，避免超过JavaScript整数精度。仅统计已保存记录，不能保证官方保留期外历史完整。部分池失败以warnings返回，全部失败不会显示读取成功。

`/api/wiki/calendar` 与 `/api/wiki/calendar-all` 的数据来自`app/services/game_calendar.py`：本机缓存`calendar-<game>.json`的TTL为`CACHE_TTL`＝30分钟，TTL内直接用缓存；过期后向上游取数，取不到就回落到上次成功结果，并在`message`里说明数据是多久之前取的。每条结果都带`source`，区分`sra`（刚取到）、`cache`（TTL内的本机缓存）、`stale-cache`（上游失败后的兜底）、`local`（本机解包索引）与`none`（无任何数据）。取不到数据不算错误：那一个游戏的`data`为空列表、`message`说明原因，不影响其它游戏，也不会让整个请求失败。

`/api/relay/*` 只在注入了转发存储的部署里可用：Cloudflare Workers（`DurableRelayStore`）或设了`COMMUNITY_RELAY_HUB=1`的本地演练后端（`MemoryRelayStore`）。普通本地后端没有注入存储，这些路径统一返回“当前后端未启用转发服务”，见`app/api/relay.py`。

米游币人工续跑及MAS控制的具体模型、完整路径见运行后端的`/openapi.json`或生成的`frontend/openapi.json`。接口均需检查HTTP状态及业务code，不能只看HTTP200。新增契约后运行：

```powershell
.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
yarn openapi
```

不要手改`frontend/src/api`，不要把真实账号、验证码、访问密码、云码密钥或授权链接放进文档与测试。
