/** 更好的MAS工具包：独立窗口、独立数据、单实例、托盘驻留及后端清理。 */
import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  nativeImage,
  nativeTheme,
  screen,
  session,
  shell,
  Tray,
} from 'electron'
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { BackendService } from './backend.cjs'
import { registerUpdates } from './updates.cjs'

const productName = '更好的MAS工具包'
// 产品更名保留既有目录与应用 ID，保证原账号密文、单实例锁和快捷方式兼容。
const dataDirectory = process.env.COMMUNITY_DATA_DIR
  ? resolve(process.env.COMMUNITY_DATA_DIR)
  : join(app.getPath('appData'), 'BetterMASCommunity')
mkdirSync(dataDirectory, { recursive: true })
app.setName(productName)
app.setPath('userData', dataDirectory)
app.setAppUserModelId('independent.bettermas.community')
// 前端据此判定桌面专属能力（如轻量模式）。
app.userAgentFallback = `${app.userAgentFallback} BMAT-Desktop/1`

const backend = new BackendService()
const sessionFile = join(dataDirectory, 'desktop-session.json')
const lightFile = join(dataDirectory, 'desktop-light.json')
const smokeTest = process.argv.includes('--smoke-test')
let window: BrowserWindow | null = null
let tray: Tray | null = null
// 托盘图标是否真的加载到了：打包版曾漏打 community.ico，托盘变成不可见空图标，
// 轻量模式就退化成「窗口没了、也没有入口唤回」，因此进入轻量模式前要确认它可用。
let trayHasIcon = false
let lightMode = false
let origin = ''
let quitting = false

function log(message: string): void {
  try {
    appendFileSync(join(dataDirectory, 'desktop.log'), `${new Date().toISOString()} ${message}\n`)
  } catch {
    // 日志失败不能阻断退出及后端清理。
  }
}

function openExternal(url: string): void {
  try {
    if (['https:', 'http:'].includes(new URL(url).protocol)) {
      void shell.openExternal(url).catch(() => log('外部链接未能打开'))
    }
  } catch {
    log('已忽略无效链接')
  }
}

/** 只信任本机服务页面：导航与 IPC 都按 origin 比对，拒绝外域页面操作桌面能力。 */
function isTrustedUrl(value: string): boolean {
  if (!value || !origin) return false
  try {
    return new URL(value).origin === origin
  } catch {
    return false
  }
}

registerUpdates(isTrustedUrl)

/** 窗口底色跟随系统主题，避免深色系统下启动瞬间先闪一帧白屏。 */
function windowBackground(): string {
  return nativeTheme.shouldUseDarkColors ? '#141414' : '#ffffff'
}

// 渲染进程兜底 CSP：与 Android 主页面策略（NativePolicy.contentPolicy）保持一致。
// 本机后端已为每个响应下发策略，验证码页还有极验白名单，因此这里只补后端没给的响应。
const RENDERER_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "worker-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://doc.auto-mas.top https://data.akedata.wiki " +
    'https://www.akedata.wiki https://resource.starrailassistant.top ' +
    'https://prod-alicdn-community.kurobbs.com https://webusstatic.yo-star.com ' +
    'https://web.hycdn.cn https://aka.doubaocdn.com https://i0.hdslb.com',
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join('; ')

function applyRendererCsp(): void {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders = details.responseHeaders ?? {}
    const hasPolicy = Object.keys(responseHeaders).some(
      key => key.toLowerCase() === 'content-security-policy'
    )
    // 只给顶层/子框架文档补策略：后端已下发的（含验证码 iframe 的极验放行）原样保留，
    // 覆盖它会把极验脚本和图片挡掉，验证码就打不开了。
    const isDocument = details.resourceType === 'mainFrame' || details.resourceType === 'subFrame'
    if (!hasPolicy && isDocument) responseHeaders['Content-Security-Policy'] = [RENDERER_CSP]
    callback({ responseHeaders })
  })
}

function readLightMode(): boolean {
  try {
    return JSON.parse(readFileSync(lightFile, 'utf8')).light === true
  } catch {
    return false
  }
}

function trayIconPath(): string {
  const candidates = app.isPackaged
    ? [join(process.resourcesPath, 'community.ico')]
    : [join(resolve(__dirname, '../..'), 'frontend', 'assets', 'community.ico')]
  return candidates.find(candidate => existsSync(candidate)) ?? ''
}

/** 创建托盘并返回图标是否可用；图标缺失时托盘不可见，调用方应避免进入仅靠托盘的形态。 */
function createTray(): boolean {
  if (tray) return trayHasIcon
  const iconPath = trayIconPath()
  trayHasIcon = existsSync(iconPath)
  if (!trayHasIcon) log(`托盘图标缺失：${iconPath || '(未找到候选路径)'}`)
  tray = new Tray(trayHasIcon ? iconPath : nativeImage.createEmpty())
  tray.setToolTip(`${productName}（轻量模式运行中）`)
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: '打开主界面', click: () => showWindow() },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() },
    ])
  )
  tray.on('click', () => showWindow())
  return trayHasIcon
}

function showWindow(): void {
  if (window) {
    if (window.isMinimized()) window.restore()
    window.show()
    window.focus()
    return
  }
  createWindow()
}

function createWindow(): void {
  const area = screen.getPrimaryDisplay().workAreaSize
  window = new BrowserWindow({
    title: productName,
    width: Math.min(1120, area.width),
    height: Math.min(780, area.height),
    minWidth: Math.min(780, area.width),
    minHeight: Math.min(540, area.height),
    show: false,
    backgroundColor: windowBackground(),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: join(__dirname, 'preload.cjs'),
    },
  })
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) =>
    callback(false)
  )
  window.webContents.session.setPermissionCheckHandler(() => false)
  window.webContents.on('console-message', details => {
    // 仅保存工具日志出口已脱敏的消息；第三方 SDK 的原始控制台输出不写入文件。
    if (details.message.startsWith('[BMAT]')) log(details.message)
  })
  window.webContents.setWindowOpenHandler(({ url }) => {
    openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    // 默认拦截：只有能解析且与本机服务同源的地址才放行；畸形 URL 也不会因解析抛异常而漏放。
    if (isTrustedUrl(url)) return
    event.preventDefault()
    openExternal(url)
  })
  window.on('close', event => {
    // 轻量模式关窗即转入托盘驻留（销毁渲染进程降低占用）；普通模式维持关窗退出。
    if (lightMode && !quitting) {
      event.preventDefault()
      window?.destroy()
      window = null
    }
  })
  window.on('closed', () => {
    window = null
  })
  window.once('ready-to-show', () => {
    if (!smokeTest) window?.show()
  })
  void window.loadURL(origin)
  log('窗口页面加载完成')
  if (smokeTest) setTimeout(() => app.quit(), 1000)
}

async function start(): Promise<void> {
  Menu.setApplicationMenu(null)
  applyRendererCsp()
  // 系统深浅色切换时同步窗口底色（轻量模式重建窗口也会读到新值）。
  nativeTheme.on('updated', () => window?.setBackgroundColor(windowBackground()))
  lightMode = !smokeTest && readLightMode()
  origin = await backend.start({
    packaged: app.isPackaged,
    projectRoot: resolve(__dirname, '../..'),
    resourcesPath: process.resourcesPath,
    dataDirectory,
    onUnexpectedExit: () => {
      if (quitting) return
      dialog.showErrorBox(
        productName,
        '本地服务意外退出，请重新启动程序。详情见独立数据目录中的日志。'
      )
      app.quit()
    },
  })
  if (quitting) return
  writeFileSync(sessionFile, JSON.stringify({ pid: process.pid, backendPid: backend.pid, origin }))
  log(`服务已就绪 pid=${backend.pid}`)
  if (lightMode) {
    if (createTray()) {
      log('轻量模式启动：驻留托盘，主窗口未创建')
      return
    }
    // 托盘图标不可用时坚持轻量模式等于把应用藏起来：回滚设置并正常开窗。
    lightMode = false
    try {
      writeFileSync(lightFile, JSON.stringify({ light: false }))
    } catch {
      log('轻量模式状态回滚写入失败')
    }
    log('轻量模式已跳过：托盘图标不可用，改为显示主窗口')
  }
  createWindow()
}

// 轻量模式开关由设置页经 preload 同步；主进程持久化并即时切换窗口形态。
ipcMain.on('bmat-light-mode', (event, enabled: unknown) => {
  // 该通道会销毁窗口并写盘，只接受本机服务页面发来的请求。
  const senderUrl = event.senderFrame?.url ?? ''
  if (!isTrustedUrl(senderUrl)) {
    log(`已忽略来源未知的轻量模式请求：${senderUrl || '未知来源'}`)
    return
  }
  const nextLightMode = enabled === true
  // 从托盘/第二次启动重建的页面会重新同步设置，不能因此再次销毁刚唤回的窗口。
  if (nextLightMode === lightMode) return
  lightMode = nextLightMode
  try {
    writeFileSync(lightFile, JSON.stringify({ light: lightMode }))
  } catch {
    log('轻量模式状态写入失败')
  }
  if (lightMode) {
    if (!createTray()) {
      // 没有可见托盘时销毁窗口就没有唤回入口，保持窗口并回滚到「未启用」。
      lightMode = false
      try {
        writeFileSync(lightFile, JSON.stringify({ light: false }))
      } catch {
        log('轻量模式状态回滚写入失败')
      }
      log('轻量模式未启用：托盘图标缺失，窗口保持显示')
      void dialog.showMessageBox({
        type: 'warning',
        title: productName,
        message: '无法进入轻量模式',
        detail:
          '托盘图标未能加载，进入轻量模式后将没有入口重新打开窗口。请重新安装完整版本后再试。',
      })
      return
    }
    window?.destroy()
    window = null
    log('轻量模式已启用：窗口销毁，转入托盘驻留')
    try {
      tray?.displayBalloon({
        iconType: 'info',
        title: productName,
        content: '已进入轻量模式，后台继续响应远程控制与签到任务。',
      })
    } catch {
      // 气泡仅在部分平台可用，失败不影响驻留。
    }
  } else {
    tray?.destroy()
    tray = null
    log('轻量模式已关闭')
  }
})

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => showWindow())
  app.on('window-all-closed', () => {
    // 轻量模式销窗后仍需驻留（托盘 + 后端）。
    if (!lightMode) app.quit()
  })
  app.on('before-quit', event => {
    if (quitting) return
    event.preventDefault()
    quitting = true
    void backend.stop().finally(() => {
      rmSync(sessionFile, { force: true })
      log('本地服务已关闭')
      app.quit()
    })
  })
  void app
    .whenReady()
    .then(start)
    .catch(error => {
      log(`启动失败：${error instanceof Error ? error.message : '未知错误'}`)
      dialog.showErrorBox(
        productName,
        '程序启动失败。请确认程序目录完整，并查看独立数据目录中的 desktop.log。'
      )
      app.quit()
    })
}
