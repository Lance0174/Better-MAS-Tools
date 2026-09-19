/** 更好的MAS工具包：独立窗口、独立数据、单实例、托盘驻留及后端清理。 */
import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, screen, shell, Tray } from 'electron'
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { BackendService } from './backend.cjs'

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

function createTray(): void {
  if (tray) return
  const iconPath = trayIconPath()
  tray = new Tray(existsSync(iconPath) ? iconPath : nativeImage.createEmpty())
  tray.setToolTip(`${productName}（轻量模式运行中）`)
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: '打开主界面', click: () => showWindow() },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() },
    ])
  )
  tray.on('click', () => showWindow())
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
    backgroundColor: '#ffffff',
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
    if (new URL(url).origin !== origin) {
      event.preventDefault()
      openExternal(url)
    }
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
    createTray()
    log('轻量模式启动：驻留托盘，主窗口未创建')
    return
  }
  createWindow()
}

// 轻量模式开关由设置页经 preload 同步；主进程持久化并即时切换窗口形态。
ipcMain.on('bmat-light-mode', (_event, enabled: unknown) => {
  lightMode = enabled === true
  try {
    writeFileSync(lightFile, JSON.stringify({ light: lightMode }))
  } catch {
    log('轻量模式状态写入失败')
  }
  if (lightMode) {
    createTray()
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
