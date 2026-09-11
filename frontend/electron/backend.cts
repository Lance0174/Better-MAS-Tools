/** 独立桌面后端生命周期；不读取或管理 AUTO-MAS 的服务。 */
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

interface BackendOptions {
  packaged: boolean
  projectRoot: string
  resourcesPath: string
  dataDirectory: string
  onUnexpectedExit: () => void
}

export class BackendService {
  private child?: ChildProcessWithoutNullStreams
  private stopping = false

  get pid(): number | undefined {
    return this.child?.pid
  }

  async start(options: BackendOptions): Promise<string> {
    const executable = options.packaged
      ? join(options.resourcesPath, 'backend', 'community-backend.exe')
      : join(options.projectRoot, '.venv', 'Scripts', 'python.exe')
    const webDirectory = options.packaged
      ? join(options.resourcesPath, 'renderer')
      : join(options.projectRoot, 'frontend', 'dist')
    if (!existsSync(executable) || !existsSync(join(webDirectory, 'index.html'))) {
      throw new Error('运行文件不完整，请重新构建或解压完整的桌面程序目录。')
    }
    const arguments_ = options.packaged ? [] : [join(options.projectRoot, 'main.py')]
    this.child = spawn(executable, [...arguments_, '--desktop', '--port', '0'], {
      cwd: options.packaged ? join(options.resourcesPath, 'backend') : options.projectRoot,
      windowsHide: true,
      stdio: 'pipe',
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONUNBUFFERED: '1',
        COMMUNITY_DATA_DIR: options.dataDirectory,
        COMMUNITY_WEB_DIR: webDirectory,
      },
    })
    const child = this.child
    // 详细业务日志由后端统一脱敏落盘；桌面进程不复制原始请求输出。
    child.stderr.resume()
    child.stdin.on('error', () => undefined)
    const port = await new Promise<number>((resolve, reject) => {
      let buffer = ''
      const timer = setTimeout(() => reject(new Error('本地服务启动超时。')), 45000)
      const onData = (chunk: string) => {
        buffer += chunk
        const lines = buffer.split(/\r?\n/)
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          const match = /^COMMUNITY_READY (\d{1,5})$/.exec(line)
          if (match) {
            clearTimeout(timer)
            child.stdout.off('data', onData)
            child.stdout.resume()
            resolve(Number(match[1]))
            return
          }
        }
        if (buffer.length > 4096) buffer = ''
      }
      child.stdout.setEncoding('utf8')
      child.stdout.on('data', onData)
      child.once('error', () => {
        clearTimeout(timer)
        reject(new Error('无法启动本地服务，请检查程序目录和文件权限。'))
      })
      child.once('exit', () => {
        clearTimeout(timer)
        reject(new Error('本地服务已退出，请检查独立数据目录中的日志。'))
      })
    })
    const origin = `http://127.0.0.1:${port}`
    const response = await fetch(`${origin}/healthz`, { signal: AbortSignal.timeout(5000) })
    const health: unknown = await response.json()
    if (
      !response.ok ||
      !health ||
      typeof health !== 'object' ||
      !('application' in health) ||
      health.application !== 'better-mas-community'
    ) {
      throw new Error('本地服务校验失败，请重新启动程序。')
    }
    child.once('exit', () => {
      if (!this.stopping) options.onUnexpectedExit()
    })
    return origin
  }

  async stop(): Promise<void> {
    this.stopping = true
    const child = this.child
    if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return
    await new Promise<void>(resolve => {
      const timer = setTimeout(() => {
        // Windows venv 包装器可能还有实际 Python 子进程，超时退出必须一起回收。
        if (process.platform === 'win32') {
          const cleanup = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
            windowsHide: true,
            stdio: 'ignore',
          })
          cleanup.on('error', () => child.kill())
        } else child.kill()
      }, 12000)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve()
      })
      // 先让服务完成清理；仅在宽限期内没有退出时终止自身子进程。
      child.stdin.end()
    })
  }
}
