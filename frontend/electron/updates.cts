/** 官方便携版更新：限制来源、流式校验，退出旧进程后替换并重启。 */
import { app, ipcMain, net, shell } from 'electron'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, open, rename, rm, writeFile } from 'node:fs/promises'
import { createReadStream } from 'node:fs'
import { dirname, join, resolve, isAbsolute } from 'node:path'
import { spawn } from 'node:child_process'

const releaseRoot = 'https://github.com/Lance0174/Better-MAS-Tools/releases/download/'
const version = '\\d+\\.\\d+\\.\\d+(?:-(?:alpha|beta|rc)\\.\\d+)?'
const assetPattern = new RegExp(`^BMT-(${version})-windows-x64\\.exe$`)
const allowedHosts = new Set([
  'github.com',
  'release-assets.githubusercontent.com',
  'objects.githubusercontent.com',
])

export type UpdateAsset = { downloadUrl: string; sha256: string; size: number; assetName: string }

export function validateAsset(value: unknown): UpdateAsset {
  if (!value || typeof value !== 'object') throw new Error('更新参数无效')
  const data = value as UpdateAsset
  const match = typeof data.assetName === 'string' && assetPattern.exec(data.assetName)
  if (
    !match ||
    data.downloadUrl !== `${releaseRoot}v${match[1]}/${data.assetName}` ||
    !/^[0-9a-f]{64}$/.test(data.sha256) ||
    !Number.isSafeInteger(data.size) ||
    data.size <= 0 ||
    data.size > 512 * 1024 * 1024
  )
    throw new Error('更新包来源或校验信息无效')
  return data
}

export function allowedRedirect(value: string): boolean {
  try {
    const url = new URL(value)
    return (
      url.protocol === 'https:' &&
      allowedHosts.has(url.hostname) &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === '443')
    )
  } catch {
    return false
  }
}

export async function downloadAsset(
  data: UpdateAsset,
  directory: string,
  fetcher: (input: string, options: RequestInit) => Promise<Response> = fetch
): Promise<string> {
  let address = data.downloadUrl
  const signal = AbortSignal.timeout(10 * 60 * 1000)
  let response: Response | undefined
  for (let hop = 0; hop < 6; hop++) {
    if (!allowedRedirect(address)) throw new Error('更新下载跳转到非官方来源，已停止')
    response = await fetcher(address, { redirect: 'manual', credentials: 'omit', signal })
    if (![301, 302, 303, 307, 308].includes(response.status)) break
    const next = response.headers.get('location')
    await response.body?.cancel()
    if (!next) throw new Error('更新下载地址失效，请重新检查更新')
    address = new URL(next, address).href
    response = undefined
  }
  if (!response?.ok || !response.body) throw new Error('更新包下载失败，请稍后重试')
  await mkdir(directory, { recursive: true })
  const temporary = join(directory, `${randomUUID()}.part`)
  const output = await open(temporary, 'wx')
  try {
    const digest = createHash('sha256')
    let size = 0
    for await (const chunk of response.body) {
      size += chunk.length
      if (size > data.size) throw new Error('更新包大小不符，已停止下载')
      digest.update(chunk)
      await output.writeFile(chunk)
    }
    if (size !== data.size || digest.digest('hex') !== data.sha256)
      throw new Error('更新包完整性校验失败，请重新下载')
    await output.close()
    const target = join(directory, data.assetName)
    await rename(temporary, target)
    return target
  } catch (error) {
    await output.close().catch(() => {})
    await rm(temporary, { force: true })
    throw error
  }
}

/** 参数来自主进程路径与数字 PID，单引号按 PowerShell 字面量转义。 */
export function updateScript(source: string, target: string, pid: number, digest: string): string {
  const quote = (value: string) => `'${value.replace(/'/g, "''")}'`
  const backup = `${target}.${randomUUID()}.previous`
  return `$ErrorActionPreference = 'Stop'
$source = ${quote(source)}
$target = ${quote(target)}
$backup = ${quote(backup)}
$temporary = $target + '.new'
function Get-BmatDigest([string]$path) {
  $stream = [IO.File]::OpenRead($path)
  $hash = [Security.Cryptography.SHA256]::Create()
  try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
  finally { $stream.Dispose(); $hash.Dispose() }
}
try {
  Wait-Process -Id ${pid} -Timeout 90 -ErrorAction SilentlyContinue
  if (Get-Process -Id ${pid} -ErrorAction SilentlyContinue) { throw 'The application is still running' }
  if ((Get-BmatDigest $source) -ne ${quote(digest)}) { throw 'Package checksum mismatch' }
  if ($source -ne $target) {
    Copy-Item -LiteralPath $source -Destination $temporary -Force
    if ((Get-BmatDigest $temporary) -ne ${quote(digest)}) { throw 'Copied package checksum mismatch' }
    # The portable launcher may hold its EXE briefly after Electron exits.
    for ($attempt = 0; ; $attempt++) {
      try {
        if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $backup }
        break
      } catch {
        if ($attempt -ge 29) { throw }
        Start-Sleep -Milliseconds 500
      }
    }
    Move-Item -LiteralPath $temporary -Destination $target
  }
  Start-Process -FilePath $target
} catch {
  $_.Exception.Message | Set-Content -LiteralPath ($source + '.install.log') -Encoding UTF8
  if (Test-Path -LiteralPath $backup) {
    Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $backup -Destination $target
    Start-Process -FilePath $target
  }
  exit 1
} finally {
  Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
`
}

export function registerUpdates(isTrusted: (url: string) => boolean): void {
  let staged: { file: string; sha256: string } | undefined
  let busy = false
  ipcMain.handle('bmat-update-download', async (event, value: unknown) => {
    if (event.senderFrame?.parent || !isTrusted(event.senderFrame?.url ?? ''))
      throw new Error('更新请求来源无效')
    if (busy) throw new Error('已有更新操作正在进行')
    const data = validateAsset(value)
    busy = true
    staged = undefined
    try {
      const directory = join(app.getPath('userData'), 'updates')
      // Electron 网络栈沿用系统网络/代理设置，且明确不发送浏览器 Cookie。
      const file = await downloadAsset(data, directory, net.fetch.bind(net))
      staged = { file, sha256: data.sha256 }
      return { ready: true }
    } catch {
      throw new Error('更新包下载或校验失败，请检查网络后重试')
    } finally {
      busy = false
    }
  })
  ipcMain.handle('bmat-update-install', async event => {
    if (event.senderFrame?.parent || !isTrusted(event.senderFrame?.url ?? ''))
      throw new Error('更新请求来源无效')
    if (busy || !staged) throw new Error('请先完成更新包下载与校验')
    busy = true
    try {
      const digest = createHash('sha256')
      for await (const chunk of createReadStream(staged.file)) digest.update(chunk)
      if (digest.digest('hex') !== staged.sha256) {
        staged = undefined
        throw new Error('更新包已变化，请重新下载')
      }
      if (!app.isPackaged || process.platform !== 'win32') {
        shell.showItemInFolder(staged.file)
        return { restarting: false }
      }
      // ZIP 版保留原快捷方式目标，将原入口换成完整便携包；旧资源继续留在原目录。
      // 便携版必须使用外层 EXE 路径，不能改临时解包目录中的 Electron。
      const portable = process.env.PORTABLE_EXECUTABLE_FILE
      const target =
        portable && isAbsolute(portable) && portable.toLowerCase().endsWith('.exe')
          ? resolve(portable)
          : process.execPath
      const probe = join(dirname(target), `.bmat-update-${randomUUID()}`)
      try {
        const handle = await open(probe, 'wx')
        await handle.close()
        await rm(probe)
      } catch {
        throw new Error('软件所在目录不可写，请通过发布页面手动更新')
      }
      const script = join(app.getPath('userData'), 'updates', `${randomUUID()}.ps1`)
      await writeFile(
        script,
        '\ufeff' + updateScript(staged.file, target, process.pid, staged.sha256),
        'utf8'
      )
      await new Promise<void>((accept, reject) => {
        const child = spawn(
          join(
            process.env.SystemRoot ?? 'C:\\Windows',
            'System32/WindowsPowerShell/v1.0/powershell.exe'
          ),
          [
            '-NoProfile',
            '-NonInteractive',
            '-ExecutionPolicy',
            'Bypass',
            '-WindowStyle',
            'Hidden',
            '-File',
            script,
          ],
          { detached: true, stdio: 'ignore', windowsHide: true }
        )
        child.once('error', reject)
        child.once('spawn', () => {
          child.unref()
          accept()
        })
      })
      setTimeout(() => app.quit(), 400)
      return { restarting: true }
    } finally {
      busy = false
    }
  })
}
