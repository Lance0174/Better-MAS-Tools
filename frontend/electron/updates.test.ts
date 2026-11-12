import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHash } from 'node:crypto'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'

const mocks = {
  handlers: new Map<string, (...args: unknown[]) => Promise<unknown>>(),
  folder: vi.fn(),
}
const electron = {
  app: { getPath: () => '', isPackaged: false },
  ipcMain: {
    handle: (name: string, handler: (...args: unknown[]) => Promise<unknown>) => mocks.handlers.set(name, handler),
  },
  shell: { showItemInFolder: mocks.folder },
}
const source = readFileSync(new URL('./updates.cts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const exported = {} as typeof import('./updates.cts')
const require = createRequire(import.meta.url)
vm.runInNewContext(code, {
  exports: exported,
  URL, AbortSignal, process, setTimeout,
  fetch: (...args: Parameters<typeof fetch>) => fetch(...args),
  require: (name: string) => name === 'electron' ? electron : require(name),
})
const { allowedRedirect, downloadAsset, registerUpdates, validateAsset, updateScript } = exported

let directory = ''
afterEach(async () => {
  vi.unstubAllGlobals()
  if (directory) await rm(directory, { recursive: true, force: true })
})
const bytes = new TextEncoder().encode('official package fixture')
const asset = {
  downloadUrl:
    'https://github.com/Lance0174/Better-MAS-Tools/releases/download/v0.2.0-beta.5/BMT-0.2.0-beta.5-windows-x64.exe',
  assetName: 'BMT-0.2.0-beta.5-windows-x64.exe',
  size: bytes.length,
  sha256: createHash('sha256').update(bytes).digest('hex'),
}

describe('official update download boundary', () => {
  it('rejects arbitrary URLs, paths, unexpected sizes and redirect authorities', () => {
    expect(validateAsset(asset)).toEqual(asset)
    for (const patch of [
      { downloadUrl: 'https://evil.test/update.exe' },
      { assetName: '../program.exe' },
      { sha256: '' },
      { size: -1 },
    ]) {
      expect(() => validateAsset({ ...asset, ...patch })).toThrow()
    }
    for (const url of [
      'file:///update.exe',
      'http://github.com/x',
      'https://github.com.evil.test/x',
      'https://user@github.com/x',
      'https://github.com:444/x',
    ])
      expect(allowedRedirect(url)).toBe(false)
  })
  it('streams and verifies bytes before exposing a complete package', async () => {
    directory = await mkdtemp(join(tmpdir(), 'bmat-update-test-'))
    const fetcher = vi.fn().mockResolvedValue(new Response(bytes))
    vi.stubGlobal('fetch', fetcher)
    const file = await downloadAsset(asset, directory)
    expect(await readFile(file)).toEqual(Buffer.from(bytes))
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: 'omit', redirect: 'manual' })
  })
  it('removes incomplete files and keeps an already downloaded package after failure', async () => {
    directory = await mkdtemp(join(tmpdir(), 'bmat-update-test-'))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes)))
    const file = await downloadAsset(asset, directory)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3]))))
    await expect(downloadAsset(asset, directory)).rejects.toThrow()
    expect(await readdir(directory)).toEqual([asset.assetName])
    expect(await readFile(file)).toEqual(Buffer.from(bytes))
  })
  it('does not follow a redirect outside official asset hosts', async () => {
    directory = await mkdtemp(join(tmpdir(), 'bmat-update-test-'))
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(null, { status: 302, headers: { location: 'https://evil.test/x' } })
      )
    vi.stubGlobal('fetch', fetcher)
    await expect(downloadAsset(asset, directory)).rejects.toThrow()
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('rejects update IPC from another origin and from subframes', async () => {
    registerUpdates(url => url === 'http://127.0.0.1:37164/')
    const download = mocks.handlers.get('bmat-update-download')!
    await expect(download({ senderFrame: { url: 'https://evil.test/' } }, asset)).rejects.toThrow()
    await expect(
      download({ senderFrame: { url: 'http://127.0.0.1:37164/', parent: {} } }, asset)
    ).rejects.toThrow()
  })
  it.skipIf(process.platform !== 'win32')('replaces a portable package and preserves its backup', async () => {
    directory = await mkdtemp(join(tmpdir(), "bmat-update-'test-"))
    const source = join(directory, 'download.exe')
    const target = join(directory, 'current.exe')
    const script = join(directory, 'install.ps1')
    await writeFile(source, bytes)
    await writeFile(target, 'original package')
    // 拦截启动动作，只验证真实 PowerShell 替换流程，不运行任何 EXE。
    await writeFile(script, '\ufefffunction Start-Process { param([string]$FilePath) }\n' + updateScript(source, target, 99999999, asset.sha256))
    await promisify(execFile)('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script], { windowsHide: true })
    expect(await readFile(target)).toEqual(Buffer.from(bytes))
    const backup = (await readdir(directory)).find(name => name.endsWith('.previous'))!
    expect(await readFile(join(directory, backup), 'utf8')).toBe('original package')
  }, 20000)
  it.skipIf(process.platform !== 'win32')('restores the old package if launching the replacement fails', async () => {
    directory = await mkdtemp(join(tmpdir(), 'bmat-update-rollback-'))
    const source = join(directory, 'download.exe')
    const target = join(directory, 'current.exe')
    const script = join(directory, 'install.ps1')
    await writeFile(source, bytes)
    await writeFile(target, 'original package')
    await writeFile(script, '\ufefffunction Start-Process { param([string]$FilePath) throw "fixture launch failure" }\n' + updateScript(source, target, 99999999, asset.sha256))
    await expect(promisify(execFile)('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script], { windowsHide: true })).rejects.toThrow()
    expect(await readFile(target, 'utf8')).toBe('original package')
    expect(await readFile(source + '.install.log', 'utf8')).toContain('fixture launch failure')
  }, 20000)
})
