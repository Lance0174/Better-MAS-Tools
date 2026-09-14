# 来源与项目归属

“更好的MAS工具包”（Better-MAS-Tools）是独立衍生项目，独立于 AUTO-MAS 团队，不代表 AUTO-MAS 团队或任何游戏公司。

社区协议、签到编排、日常便笺和部分前端组件来自 [AUTO-MAS](https://github.com/AUTO-MAS-Project/AUTO-MAS)，来源版本为 `78bc197e5c37ca4ece98f5b4f07f90fe631b814a`。迁移记录见 [来源清单](docs/upstream-files.json)。原始版权头、有效注释及第三方协议参考致谢予以保留；独立适配在本项目中进行，不反向修改源仓库。

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

云码按 [官方317文档](https://www.jfbym.com/test/317.html) 的30332图片坐标接口独立适配；返回坐标不等于完整极验票据。本项目不隶属于上述项目、极验或云码。

Cloudflare 集成使用官方 workers-py/runtime SDK；实现核对 workers-py `940847dbbc250f982ccb03a5ba667aa5d70d81cb` 与 cloudflare-docs `72c81248ba0863139348650dd24be5d390d40681`，未复制其运行器源码。相关依赖继续适用各自许可证。

## Android 本地运行时

Android 本地版使用 [Pyodide 0.28.3](https://github.com/pyodide/pyodide/tree/0.28.3)（MPL-2.0）在 Web Worker 中运行本项目 Python 源码，许可全文见 [LICENSE-Pyodide.txt](android/runtime/LICENSE-Pyodide.txt)。依赖版本和摘要固定于 `android/runtime/manifest.json`；Python 包的许可证随其 wheel 和源码包保留，前端生产依赖的许可随 APK 的 `licenses/frontend` 目录附带。

本地受限网络构建可复用经逐文件 RECORD 校验的公共包缓存。pydantic-core 的一个历史缓存重打包摘要单独登记为 `repackedSha256`；APK 的 `licenses/android-runtime.json` 记录实际采用的摘要，默认联网构建使用原始官方 wheel。重打包未修改依赖源码或二进制内容。
