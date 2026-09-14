# Android 本地客户端工程

本项目 Android 端是「WebView + Pyodide（WASM Python 引擎）」的本地客户端：前端构建产物、Python 后端源码与运行依赖全部打进 APK，在手机 WebView 内运行，网络与持久化经原生桥转交系统。本文件说明工程结构与文件位置约定，后续改动按此落位。

## 工程结构

| 路径 | 职责 |
| --- | --- |
| `android/settings.gradle.kts` / `build.gradle.kts` / `gradle.properties` | Gradle 工程配置 |
| `android/app/build.gradle.kts` | 应用模块配置（applicationId `io.github.lance0174.bmat`，compileSdk 35） |
| `android/app/src/main/java/io/github/lance0174/bmat/` | 安卓原生代码 |
| `android/app/src/main/res/` | 图标等资源 |
| `android/app/src/main/assets/` | **生成目录**：由 `scripts/prepare-android.py` 同步前端构建产物、Pyodide 运行时、后端源码；不手工编辑 |
| `android/runtime/` | 运行期静态资源：`manifest.json`（版本清单）、`pyodide-lock.json`（依赖锁）、`engine-worker.js`（引擎桥）、`LICENSE-Pyodide.txt` |
| `android/app/src/test/` | Java 单元测试 |

## 安卓原生代码职责（`io.github.lance0174.bmat`）

| 文件 | 职责 |
| --- | --- |
| `MainActivity.java` | WebView 宿主、深色跟随、原生操作分发（存储/网络/日志/文件选择） |
| `NativeNetwork.java` | 原生 HTTP 网络（经此对外请求，替代 Python 直接联网） |
| `NativePolicy.java` | 资源拦截策略（本地 asset / 极验白名单 / CSP 头） |
| `LocalStateStore.java` | 账号与设置的本机 Keystore 存储 |
| `NativeDiagnostics.java` | 启动诊断与日志落盘 |

## 跨层文件位置约定

| 文件 | 职责（所属层） |
| --- | --- |
| `app/core/android_runtime.py` | 手机前台运行编排入口（app/core：编排） |
| `app/services/android.py` | 安卓存储与网络原生适配（app/services：本机存储/外部连接） |
| `frontend/src/services/android.ts` | 前端安卓桥：引擎启动、消息端口、本地请求适配 |
| `frontend/src/utils/download.ts` | 文件保存/分享工具（纯前端工具） |
| `scripts/prepare-android.py` | 构建前端并同步安卓离线资源 |
| `scripts/verify-android.cjs` | APK 内容校验脚本 |
| `docs/ANDROID.md` | 安卓架构与可行性说明 |

## 构建

见 `docs/ANDROID.md` 与根目录开发报告。要点：前端构建 → `prepare-android.py` → 隔离工具链 Gradle `assembleDebug`；APK 产物在 `android/app/build/outputs/apk/debug/`。

## 约束

- `android/app/src/main/assets/` 是生成目录，**不手工改**；运行期静态文件改 `android/runtime/` 后再同步。
- 账号/凭据/日志不提交；真机验收（深色跟随、验证码、启动时长）以用户安装实测为准。
