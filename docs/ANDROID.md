# Android 本地版

本轮提供 Android 10 及以上的本地测试客户端。手机独立执行社区请求，账号及抽卡记录经 Android Keystore 加密后保存在应用私有目录。首次启动为空账号，不读取电脑端或 MAS 数据。

## 使用

1. 安装本轮测试 APK，在“社区签到”添加账号并录入凭据，或使用已有登录入口；验证受各平台风控及手机网络影响。
2. 手动点击“立即签到”。在“设置 → 自动签到”开启“打开应用时签到”后，每天首次打开或返回前台最多自动尝试一次。执行期间保持应用在前台，失败后手动重试。
3. “日常便笺”展示应用内卡片；本轮不包含系统桌面组件和后台定时服务。
4. “抽卡记录”支持官方链接、JSON 导入、列表查看、BMASC/UIGF 导出。明日方舟及终末地国服可选含 OAuth Token 的森空岛账号并填写 UID，临时换取角色授权。原神、崩铁、绝区零和鸣潮继续使用官方记录链接或兼容备份文件，不能把普通签到 Token 当成记录授权。
5. “运行日志”可查询本次日志，并通过系统文件选择器导出当前及上一卷本机日志。接口状态、耗时和调用栈会记录，账号凭据会脱敏。

### 启动失败时

诊断修订版 `0.1.3-local-r2`（versionCode 2）会显示运行时加载、依赖初始化和本机配置读取等启动阶段。页面底部的原生“启动诊断”按钮不依赖 Python 或页面接口，启动失败时仍可打开；选择“导出日志”并保存 `Better-MAS-Tools-startup.txt`。正常进入首页后该按钮隐藏，运行中的日志继续从日志页导出。

日志记录应用、Android 和 WebView 版本、资源加载错误、消息通道连接和引擎异常，并过滤凭据。报告问题时请附 APK 文件名、完整错误文字及导出的诊断文件。保留原应用数据进行覆盖安装即可；若系统提示签名不一致，请先反馈，避免卸载造成记录丢失。

本次修正了重复页面完成事件重建消息通道的风险，并修复打包引擎回归中发现的依赖版本和 Python 方法代理生命周期问题。用户设备上的具体失败原因仍需设备诊断确认。

本机不运行监听端口。MAS 连接入口在现有桌面/Web 版本保留；Cloudflare、Docker 以及远端账号管理不属于本轮安卓本地交付。

## 源码构建

准备 Python 3.12、Node.js 22、Yarn 4、JDK 17、Android SDK platform 35 和 build-tools 35.0.0。Android Gradle Plugin 固定为 8.7.3，仓库内 Gradle Wrapper 固定为 8.14。在当前终端设置 `JAVA_HOME`（JDK 17）和 `ANDROID_SDK_ROOT`（Android SDK）后运行，并将 `ANDROID_HOME` 设为同一 SDK 路径；不要把本机代理或密钥提交到仓库。所有命令均从仓库根目录执行，工具链目录只通过环境变量提供。

根目录 [`.env.example`](../.env.example) 列出了 Android 构建变量。`.env` 的非空值由 Python 入口优先加载，但 PowerShell/Gradle 命令不会自动读取它；请在当前终端导出 `JAVA_HOME`、`ANDROID_SDK_ROOT`、`ANDROID_HOME` 和 `GRADLE_USER_HOME` 后再执行以下命令。变量为空时跳过，随后使用系统环境变量；仍缺失时按工具链自身错误提示处理。

```powershell
if (-not $env:JAVA_HOME -or -not $env:ANDROID_SDK_ROOT) {
    throw 'Set JAVA_HOME (JDK 17) and ANDROID_SDK_ROOT (Android SDK) first.'
}
$env:ANDROID_HOME = $env:ANDROID_SDK_ROOT
$env:GRADLE_USER_HOME = Join-Path (Get-Location) 'local/gradle'

# 仓库根目录，使用项目虚拟环境
uv sync --locked --dev --extra captcha --link-mode=copy
Push-Location frontend
try { yarn install --immutable; yarn build } finally { Pop-Location }
.venv\Scripts\python.exe scripts/prepare-android.py --skip-frontend
Push-Location android
try { .\gradlew.bat --no-daemon :app:assembleDebug :app:testDebugUnitTest :app:lintDebug } finally { Pop-Location }
```

输出：`android/app/build/outputs/apk/debug/app-debug.apk`。此 APK 使用 Android 调试签名，适合本轮安装验收；正式发布需要维护者自己的持久签名密钥。更新时需保持签名一致，卸载应用会移除本地加密数据，请先导出记录。

资源准备脚本校验 SHA-256，可用 `--runtime-cache <目录>` 指定缓存、`--offline` 禁止下载。`--python-cache <已安装包目录>` 仅供受限网络构建复用公共依赖，逐文件校验 RECORD；普通构建直接从锁定的官方 wheel 获取纯 Python 包。`--proxy <地址>` 只对本次下载有效。首次 Gradle 构建需要下载 Wrapper 发行包，缓存齐全后可为 Gradle 命令追加 `--offline`。运行时不依赖其他仓库、开发机路径或 Python 安装。

提交源码时排除 `android/app/src/main/assets`、APK、Gradle 缓存、`local.properties` 和签名文件，规则已写入 `android/.gitignore`。资源及依赖随 APK 打包，首次启动无需下载 Python 引擎；签到、登录和在线抽卡查询仍需要网络。

## 验证边界

后端与前端回归使用合成数据及模拟网络；Chromium 验证覆盖真实打包 Worker 和现有 Vue 页面，但不能替代 Android WebView、Keystore、系统文件选择器或真实平台签到验证。本轮按用户选择交付 APK 自行安装，不对连接的 ADB 设备执行安装、启动或数据操作。

准备资源后可运行 `frontend/node_modules/electron/dist/electron.exe scripts/verify-android.cjs` 复现隔离回归。测试禁用外部网络，检查五个手机页面、合成记录导入导出、配置恢复和启动失败诊断；结果与截图写入忽略目录 `local/android-ui-probe`，测试结束自动关闭浏览器。
