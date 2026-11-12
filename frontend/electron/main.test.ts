import { EventEmitter } from 'node:events'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'

/** 执行真实主进程代码，只替换 Electron/文件/后端边界；不启动窗口、服务或读用户配置。 */
async function launch(light: boolean) {
  const windows: FakeWindow[] = []
  const ipc = new EventEmitter()
  const app = Object.assign(new EventEmitter(), {
    getPath: () => '/isolated',
    setName: vi.fn(),
    setPath: vi.fn(),
    setAppUserModelId: vi.fn(),
    requestSingleInstanceLock: () => true,
    userAgentFallback: 'test',
    isPackaged: false,
    quit: vi.fn(),
    whenReady: () => Promise.resolve(),
  })
  class FakeWindow extends EventEmitter {
    destroyed = false
    shown = 0
    webContents = Object.assign(new EventEmitter(), {
      session: { setPermissionRequestHandler: vi.fn(), setPermissionCheckHandler: vi.fn() },
      setWindowOpenHandler: vi.fn(),
    })
    constructor() {
      super()
      windows.push(this)
    }
    isMinimized() {
      return false
    }
    restore() {}
    focus() {}
    setBackgroundColor() {}
    show() {
      this.shown++
    }
    loadURL() {
      return Promise.resolve()
    }
    destroy() {
      this.destroyed = true
      this.emit('closed')
    }
  }
  const files = {
    appendFileSync: vi.fn(),
    mkdirSync: vi.fn(),
    rmSync: vi.fn(),
    writeFileSync: vi.fn(),
    existsSync: () => true,
    readFileSync: () => JSON.stringify({ light }),
  }
  const electron = {
    app,
    ipcMain: ipc,
    BrowserWindow: FakeWindow,
    nativeTheme: Object.assign(new EventEmitter(), { shouldUseDarkColors: false }),
    screen: { getPrimaryDisplay: () => ({ workAreaSize: { width: 1280, height: 900 } }) },
    session: { defaultSession: { webRequest: { onHeadersReceived: vi.fn() } } },
    Menu: { setApplicationMenu: vi.fn(), buildFromTemplate: vi.fn() },
    nativeImage: { createEmpty: vi.fn() },
    shell: { openExternal: vi.fn() },
    dialog: { showErrorBox: vi.fn(), showMessageBox: vi.fn() },
    Tray: class extends EventEmitter {
      setToolTip() {}
      setContextMenu() {}
      displayBalloon() {}
      destroy() {}
    },
  }
  const source = readFileSync(new URL('./main.cts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  vm.runInNewContext(code, {
    __dirname: '/isolated/frontend/dist-electron',
    exports: {},
    URL,
    process: { env: { COMMUNITY_DATA_DIR: '/isolated/data' }, argv: [] },
    require: (name: string) => {
      if (name === 'electron') return electron
      if (name === 'node:fs') return files
      if (name === 'node:path') return path
      if (name === './updates.cjs') return { registerUpdates: vi.fn() }
      if (name === './backend.cjs')
        return {
          BackendService: class {
            pid = 42
            async start() {
              return 'http://127.0.0.1:39876'
            }
            async stop() {}
          },
        }
      throw new Error(`Unexpected dependency: ${name}`)
    },
  })
  await new Promise(resolve => setImmediate(resolve))
  expect(electron.dialog.showErrorBox).not.toHaveBeenCalled()
  const sync = (enabled: boolean, url = 'http://127.0.0.1:39876/') =>
    ipc.emit('bmat-light-mode', { senderFrame: { url } }, enabled)
  return { windows, app, sync, files }
}

describe('轻量模式窗口生命周期', () => {
  it('第二次启动唤回后，前端重复同步 true 不再销毁新窗口', async () => {
    const { windows, app, sync } = await launch(false)
    expect(windows).toHaveLength(1)
    sync(true)
    expect(windows[0].destroyed).toBe(true)
    app.emit('second-instance')
    expect(windows).toHaveLength(2)
    sync(true)
    expect(windows[1].destroyed).toBe(false)
    app.emit('second-instance')
    expect(windows[1].shown).toBe(1)
  })

  it('以轻量模式启动时，唤回窗口后也能保留界面', async () => {
    const { windows, app, sync } = await launch(true)
    expect(windows).toHaveLength(0)
    app.emit('second-instance')
    sync(true)
    expect(windows).toHaveLength(1)
    expect(windows[0].destroyed).toBe(false)
  })

  it('外域页面不能启用轻量模式或写入桌面设置', async () => {
    const { windows, sync, files } = await launch(false)
    const writes = files.writeFileSync.mock.calls.length
    sync(true, 'https://untrusted.example')
    expect(windows[0].destroyed).toBe(false)
    expect(files.writeFileSync).toHaveBeenCalledTimes(writes)
  })
})
