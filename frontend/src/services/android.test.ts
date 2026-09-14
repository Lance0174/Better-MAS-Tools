import axios from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

class MockWorker {
  static current: MockWorker
  static boot = true
  onmessage?: (event: { data: unknown }) => void
  onerror?: (event: { preventDefault: () => void }) => void
  sent: { type: string; id?: string }[] = []
  terminated = false
  constructor() {
    MockWorker.current = this
  }
  postMessage(message: { type: string; id?: string }) {
    this.sent.push(message)
    if (message.type === 'boot' && MockWorker.boot)
      queueMicrotask(() => this.onmessage?.({ data: { type: 'ready' } }))
  }
  terminate() {
    this.terminated = true
  }
}

const originalAdapter = axios.defaults.adapter
beforeEach(() => {
  vi.resetModules()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
  vi.stubGlobal('window', new EventTarget())
  vi.stubGlobal('document', Object.assign(new EventTarget(), { visibilityState: 'visible' }))
  vi.stubGlobal('location', { origin: 'https://appassets.androidplatform.net' })
  vi.stubGlobal('navigator', { userAgent: 'BMAT-Android/1' })
  vi.stubGlobal('Worker', MockWorker)
  MockWorker.boot = true
})
afterEach(() => {
  axios.defaults.adapter = originalAdapter
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Android local API adapter', () => {
  it('preserves generated JSON responses and HTTP failures', async () => {
    const { installAndroidAdapter } = await import('./android')
    installAndroidAdapter()
    const result = axios.get('/api/status')
    await vi.waitFor(() =>
      expect(MockWorker.current.sent.some(item => item.type === 'request')).toBe(true)
    )
    const request = MockWorker.current.sent.find(item => item.type === 'request')!
    MockWorker.current.onmessage?.({
      data: {
        type: 'response',
        id: request.id,
        response: { status: 200, body: '{"code":200}', headers: {} },
      },
    })
    expect((await result).data).toEqual({ code: 200 })
  })

  it('cancels queued generated requests before dispatch after startup', async () => {
    MockWorker.boot = false
    const { installAndroidAdapter } = await import('./android')
    installAndroidAdapter()
    const cancellation = axios.CancelToken.source()
    const result = axios
      .get('/api/status', { cancelToken: cancellation.token })
      .catch(error => error)
    cancellation.cancel()
    MockWorker.current.onmessage?.({ data: { type: 'ready' } })
    expect(axios.isCancel(await result)).toBe(true)
    expect(MockWorker.current.sent.some(item => item.type === 'request')).toBe(false)
  })

  it('stops on startup timeout and only retries after explicit action', async () => {
    MockWorker.boot = false
    const { installAndroidAdapter, retryAndroidEngine } = await import('./android')
    installAndroidAdapter()
    const result = axios.get('/api/session').catch(error => error)
    await vi.advanceTimersByTimeAsync(90_001)
    expect((await result).message).toContain('启动超时')
    expect(MockWorker.current.terminated).toBe(true)
    const instance = MockWorker.current
    await expect(axios.get('/api/session')).rejects.toThrow('启动超时')
    expect(MockWorker.current).toBe(instance)
    retryAndroidEngine()
    const retry = axios.get('/api/session').catch(error => error)
    expect(MockWorker.current).not.toBe(instance)
    await vi.advanceTimersByTimeAsync(90_001)
    await retry
  })

  it('rejects external API URLs without native dispatch', async () => {
    const { installAndroidAdapter } = await import('./android')
    installAndroidAdapter()
    await expect(axios.get('https://example.invalid/api/status')).rejects.toThrow('地址不受支持')
    expect(MockWorker.current.sent.some(item => item.type === 'request')).toBe(false)
  })

  it('uses the latest native port after another page-completion handshake', async () => {
    const { androidCall } = await import('./android')
    const connect = (label: string) => {
      const channel = {
        onmessage: undefined as ((event: { data: string }) => void) | undefined,
        start: vi.fn(),
        postMessage: vi.fn((serialized: string) => {
          const request = JSON.parse(serialized)
          queueMicrotask(() =>
            channel.onmessage?.({
              data: JSON.stringify({ id: request.id, result: { label } }),
            })
          )
        }),
      }
      window.dispatchEvent(
        Object.assign(new Event('message'), {
          source: null,
          data: 'bmat-native-ready',
          ports: [channel],
        })
      )
      return channel
    }
    const first = connect('first')
    expect(await androidCall('log.read')).toEqual({ label: 'first' })
    const second = connect('second')
    expect(await androidCall('log.read')).toEqual({ label: 'second' })
    expect(first.postMessage).toHaveBeenCalledTimes(1)
    expect(second.postMessage).toHaveBeenCalledTimes(1)
  })

  it('exposes the startup stage and fails promptly on a worker error', async () => {
    MockWorker.boot = false
    const { installAndroidAdapter } = await import('./android')
    installAndroidAdapter()
    const stage = vi.fn()
    window.addEventListener('bmat-engine-stage', stage)
    const result = axios.get('/api/session').catch(error => error)
    MockWorker.current.onmessage?.({ data: { type: 'stage', text: '读取本机配置' } })
    expect((stage.mock.calls[0][0] as CustomEvent).detail).toBe('读取本机配置')
    MockWorker.current.onmessage?.({ data: { type: 'fatal', error: '合成引擎启动错误' } })
    expect((await result).message).toContain('合成引擎启动错误')
    expect(MockWorker.current.terminated).toBe(true)
  })

  it('reports worker construction failure immediately', async () => {
    vi.stubGlobal(
      'Worker',
      class {
        constructor() {
          throw new Error('fixture')
        }
      }
    )
    const { installAndroidAdapter } = await import('./android')
    installAndroidAdapter()
    await expect(axios.get('/api/session')).rejects.toThrow('无法创建本地运行线程')
  })
})
