# 来源与项目归属

“更好的MAS工具包”（Better-MAS-Tools）是独立衍生项目，独立于 AUTO-MAS 团队，不代表 AUTO-MAS 团队或任何游戏公司。

社区协议、签到编排、日常便笺和部分前端组件来自 [AUTO-MAS](https://github.com/AUTO-MAS-Project/AUTO-MAS)，来源版本为 `78bc197e5c37ca4ece98f5b4f07f90fe631b814a`。迁移记录见 [来源清单](docs/upstream-files.json)：`files` 登记可核对上游摘要的移植文件，`attributed_files` 登记只有文件头归属说明的其他上游文件。原始版权头、有效注释及第三方协议参考致谢予以保留；独立适配在本项目中进行，不反向修改源仓库。

本项目继续使用 GNU Affero General Public License v3 或更新版本，全文见 [LICENSE](LICENSE)。保留上游版权不表示由原团队维护或背书。

游戏图标与背景的权利归各自权利人，相关来源说明随资源保留，软件许可证不替代游戏美术资源的许可。

## 本轮登录、抽卡与远端参考

| 来源 | 核对版本 | 使用范围 |
| --- | --- | --- |
| [Womsxd/MihoyoBBSTools](https://github.com/Womsxd/MihoyoBBSTools) | `f062d1fda8fab88fd312a5ca3a89537f6351943b` | 米游社游戏签到网页 DS 与版本/Salt 配套核对，保留原平台模块中的版权与致谢 |
| [mxyooR/Kuro_login](https://github.com/mxyooR/Kuro_login) | `1ba2f995b831e32fcd9c7a03a976272765f4943f`；图标 Alpha 处理参考此前 `b69ef1a9c618325e4a4f0b4ad0372624ab0d847f` | 库街区短信协议及极验4滑块适配，保留 MX 版权；MIT 全文见 [Kuro_login.txt](docs/licenses/Kuro_login.txt) |
| [Scighost/Starward](https://github.com/Scighost/Starward) | `3e2da5ffecde252211edb74b850ee13d6b93f6dd` | 米家抽卡协议和 UIGF 兼容参考；MIT 全文见 [Starward.txt](docs/licenses/Starward.txt) |
| [Ljzd-PRO/nonebot-plugin-mystool](https://github.com/Ljzd-PRO/nonebot-plugin-mystool) | `ac2e1242764282079e2d393c1dbc3168c9a40f34` | 米游币状态与人工验证协议参考 |
| [Marchen-orz/MiyoQian](https://github.com/Marchen-orz/MiyoQian) | `a46001d8840c331860aa02da7c7d6dcf356c2dff` | 过码流程调研，未复制无许可源码 |
| [erzaozi/waves-plugin](https://github.com/erzaozi/waves-plugin) | `022d9cd84425c4879311e1079137195682e8b593` | 鸣潮唤取记录协议参考 |
| [gxy12345/arknights-plugin](https://github.com/gxy12345/arknights-plugin) | `3b6683cfe72a8379c8b3e4659c932cef572d7dae` | 明日方舟角色授权与寻访协议参考 |
| [bhaoo/endfield-gacha](https://github.com/bhaoo/endfield-gacha) | `72c526d49136fd23271f77e9ef33549de3721283` | 终末地角色/武器寻访协议参考，未复制实现源码 |
| [TomyJan/Yunzai-Kuro-Plugin](https://github.com/TomyJan/Yunzai-Kuro-Plugin) | `93699159c1730a7453f28be73f5207830ed5d7d2` | 库街区鸣潮结晶波片便笺（`gamer/widget/game3/getData`）公开接口协议参考：端点、表单字段与响应字段名。**仅参考其公开接口协议，未复制其源代码**；本项目按自身的工具/解析分层重写，未修改或分发该插件代码，因此不产生 MPL-2.0 的文件级义务 |

云码按 [官方317文档](https://www.jfbym.com/test/317.html) 的30332图片坐标接口独立适配；返回坐标不等于完整极验票据。本项目不隶属于上述项目、极验或云码。

Cloudflare 集成使用官方 workers-py/runtime SDK；实现核对 workers-py `940847dbbc250f982ccb03a5ba667aa5d70d81cb` 与 cloudflare-docs `72c81248ba0863139348650dd24be5d390d40681`，未复制其运行器源码。相关依赖继续适用各自许可证。

## 终末地资料库与活动日历（Priestess-bot）

终末地资料库的索引构建、检索解析与数据体检移植自 [Billtranscend/Priestess-bot](https://github.com/Billtranscend/Priestess-bot)（MIT，Copyright (c) 2026 Billtranscend），来源文件为 `plugins/endfield_wiki/` 下的 `data.py`、`lookup.py`、`changes.py` 与 `aliases.json`；明日方舟活动日历移植自 `plugins/game_calendar/arknights.py`。上游的 NoneBot 命令、出图与群功能未移植，只保留与机器人框架无关的数据与解析部分，并按本项目的工具/服务/接口分层重写。MIT 许可全文见 [Priestess-bot.txt](docs/licenses/Priestess-bot.txt)。

游戏数据在运行期从下列来源下载，**不随本仓库分发**；本仓库因此不构成对这些数据的再分发：

| 数据源 | 用途 | 许可与说明 |
| --- | --- | --- |
| [AKEData](https://www.akedata.wiki/)（`data.akedata.wiki`） | 终末地干员、武器、装备、关卡、敌人、活动与卡池解包数据 | 站点未公开明确条款；仅运行期下载并缓存在本机数据目录 |
| [yuanyan3060/ArknightsGameResource](https://github.com/yuanyan3060/ArknightsGameResource) | 明日方舟活动表与卡池表 | AGPL-3.0；仅运行期读取，不复制进本仓库 |
| [PRTS Wiki](https://prts.wiki/) `api.php` | 明日方舟活动与卡池的补充信息 | 内容为 CC BY-NC-SA 4.0（署名—非商业性使用—相同方式共享）；本项目仅通过其公开 API 读取并作非商业用途展示 |
| 游戏官方接口（`ef-webview.hypergryph.com`） | 卡池横幅等展示素材 | 权利归各游戏权利人，仅作功能展示 |

检索所需的干员昵称、简称与专武别名表随代码分发（`app/tools/data/endfield_aliases.json`，MIT，来自上述仓库）。若相关站点调整条款或要求停止使用，应移除对应数据源；界面中的资料库内容不改变游戏内实际数值，以游戏内公告为准。

本项目未移植 Priestess-bot 的哔哩哔哩攻略视频搜索：该接口的 `robots.txt` 声明 `Disallow: /`，在获得明确许可前不作为功能提供。

## 多游戏活动日历数据源（StarRailAssistant）

除终末地以外的活动日历（原神、崩坏：星穹铁道、绝区零、鸣潮、异环、星塔旅人、明日方舟）读取 [StarRailAssistant](https://starrailassistant.top) 托管的公开活动 JSON（`https://starrailassistant.top/api/v1/activity/{game}.json`）。该数据由 StarRailAssistant 项目方定期抓取维护，取数发生在对方服务器上；本项目只读取其公开接口，不直接抓取游戏官方站点，也不复制或再分发其数据。结果仅缓存在用户本机数据目录（`wiki/calendar-<game>.json`，默认有效期 30 分钟），随用户删除本机数据而消失。

接口不可用时一律静默降级：优先回落到本机缓存中上一次成功获取的结果，仍无数据时返回空列表并在该游戏的说明里注明原因；单个游戏失败不影响其余游戏，也不影响其它功能。终末地以本机 AKEData 解包索引为准、SRA 仅在其没有活动时补位，明日方舟另有本机解包游戏表（见上一节）作为第二降级来源。若对方调整条款或要求停止使用，应移除对应数据源。界面中的活动信息不改变游戏内实际内容，以游戏内公告为准。

## Android 本地运行时

Android 本地版使用 [Pyodide 0.28.3](https://github.com/pyodide/pyodide/tree/0.28.3)（MPL-2.0）在 Web Worker 中运行本项目 Python 源码，许可全文见 [LICENSE-Pyodide.txt](android/runtime/LICENSE-Pyodide.txt)。依赖版本和摘要固定于 `android/runtime/manifest.json`；Python 包的许可证随其 wheel 和源码包保留，前端生产依赖的许可随 APK 的 `licenses/frontend` 目录附带。

本地受限网络构建可复用经逐文件 RECORD 校验的公共包缓存。pydantic-core 的一个历史缓存重打包摘要单独登记为 `repackedSha256`；APK 的 `licenses/android-runtime.json` 记录实际采用的摘要，默认联网构建使用原始官方 wheel。重打包未修改依赖源码或二进制内容。
