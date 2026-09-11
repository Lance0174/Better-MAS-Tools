/** 更好的MAS游戏社区版：独立窗口、独立数据、单实例及后端清理。 */
import { app, BrowserWindow, dialog, Menu, screen, shell } from 'electron'
import { appendFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { BackendService } from './backend.cjs'

const productName = '更好的MAS游戏社区版'
const dataDirectory = process.env.COMMUNITY_DATA_DIR
  ? resolve(process.env.COMMUNITY_DATA_DIR)
  : join(app.getPath('appData'), 'BetterMASCommunity')
mkdirSync(dataDirectory, { recursive: true })
app.setName(productName)
app.setPath('userData', dataDirectory)
app.setAppUserModelId('independent.bettermas.community')

const backend = new BackendService()
const sessionFile = join(dataDirectory, 'desktop-session.json')
let window: BrowserWindow | null = null
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

async function start(): Promise<void> {
  Menu.setApplicationMenu(null)
  const origin = await backend.start({
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
  const area = screen.getPrimaryDisplay().workAreaSize
  window = new BrowserWindow({
    title: productName,
    width: Math.min(1120, area.width),
    height: Math.min(780, area.height),
    minWidth: Math.min(780, area.width),
    minHeight: Math.min(540, area.height),
    show: false,
    backgroundColor: '#ffffff',
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true },
  })
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) =>
    callback(false)
  )
  window.webContents.session.setPermissionCheckHandler(() => false)
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
  window.on('closed', () => {
    window = null
  })
  window.once('ready-to-show', () => {
    if (!process.argv.includes('--smoke-test')) window?.show()
  })
  await window.loadURL(origin)
  log('窗口页面加载完成')
  if (process.argv.includes('--smoke-test')) setTimeout(() => app.quit(), 1000)
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (window?.isMinimized()) window.restore()
    window?.show()
    window?.focus()
    log('重复启动已聚焦现有窗口')
  })
  app.on('window-all-closed', () => app.quit())
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
