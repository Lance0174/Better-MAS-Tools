# BMASC 开发接口

所有业务接口在`/api`下，用OpenAPI定义模型；前端通过生成客户端和composable调用。后端默认环回端口37164，桌面外壳使用自身随机端口。

先GET `/api/session`。本机模式返回临时`key`，远端模式返回`loginRequired=true`，再POST同一路径提交`{"password":"自己的访问密码"}`换取会话。后续发送`X-Community-Session: <key>`，远端请求的Origin必须匹配部署配置。会话只在内存保留，不写浏览器存储。

| 路径 | 用途 |
| --- | --- |
| `/api/accounts` | 账号列表与新增；更新、删除等契约以OpenAPI为准 |
| `/api/settings` | 读取/保存设置，YunmaToken始终脱敏；null保留旧密钥，空字符串清除 |
| `/api/status` | 运行状态、北京时间today和各平台结果 |
| `/api/login/kuro/sms/create` | accountId＋phone创建10分钟会话 |
| `/api/login/kuro/sms/automatic` | sessionId尝试自动验证和发短信；sent=false时按message转人工 |
| `/api/login/kuro/sms/send` | sessionId＋完整极验4verification发送短信 |
| `/api/login/kuro/sms/login` | sessionId＋smsCode登录，自动保存正式Token及设备标识 |
| `/api/login/kuro/sms/cancel` | 取消会话和正在运行的自动验证 |
| `/api/gacha` | GET按game、playerUid、pool、page、pageSize查询记录及统计 |
| `/api/gacha/fetch` | POST读取官方记录；source只在本次请求使用 |
| `/api/gacha/import` | POST game＋payload（JSON字符串）导入，原数据合并去重 |
| `/api/gacha/export` | GET game、playerUid、fileFormat=bmasc或uigf，返回filename/content |

抽卡game枚举为`genshin`、`starrail`、`zzz`、`wuthering`、`arknights`、`endfield`。米家三游戏支持Starward/UIGF文件；鸣潮使用官方链接或请求JSON；明日方舟使用森空岛accountId与playerUid；终末地仍需粘贴官方记录链接中的u8_token，未实现从森空岛自动取得该链接。

记录ID保持字符串，避免超过JavaScript整数精度。仅统计已保存记录，不能保证官方保留期外历史完整。部分池失败以warnings返回，全部失败不会显示读取成功。

米游币人工续跑及MAS控制的具体模型、完整路径见运行后端的`/openapi.json`或生成的`frontend/openapi.json`。接口均需检查HTTP状态及业务code，不能只看HTTP200。新增契约后运行：

```powershell
.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
yarn openapi
```

不要手改`frontend/src/api`，不要把真实账号、验证码、访问密码、云码密钥或授权链接放进文档与测试。
