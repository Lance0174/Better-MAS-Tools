import axios, { AxiosError, CanceledError, type AxiosAdapter } from 'axios'

type NativeResult = Record<string, unknown>
type Pending<T> = { resolve: (value: T) => void; reject: (error: Error) => void }
type LocalResponse = { status: number; headers: Record<string, string>; body: string }
// Axios 1.15 提供订阅释放接口，但其 CancelToken 声明未包含这两个方法。
type SubscribableToken = NonNullable<Parameters<AxiosAdapter>[0]['cancelToken']> & {
  subscribe: (listener: () => void) => void
  unsubscribe: (listener: () => void) => void
}

export const isAndroidLocal =
  typeof window !== 'undefined' &&
  location.origin === 'https://appassets.androidplatform.net' &&
  navigator.userAgent.includes('BMAT-Android/1')

const nativePending = new Map<string, Pending<NativeResult>>()
const apiPending = new Map<string, Pending<LocalResponse>>()
const epoch = isAndroidLocal ? crypto.randomUUID() : ''
let sequence = 0
let port: MessagePort | undefined
let worker: Worker | undefined
let lastHeartbeat = Date.now()
let ready = false
let started = false
let bootPromise: Promise<void> | undefined
let completeBoot: (() => void) | undefined
let failBoot: ((error: Error) => void) | undefined
let bootTimeout: ReturnType<typeof setTimeout> | undefined
let heartbeatTimer: ReturnType<typeof setInterval> | undefined
let engineError: Error | undefined

const nextId = () => `${epoch}-${++sequence}`
let acceptPort: ((value: MessagePort) => void) | undefined
const nativePort = new Promise<MessagePort>(resolve => {
  acceptPort = resolve
})

if (isAndroidLocal) {
  window.addEventListener('message', event => {
    // Android 的定向消息没有 Window 来源；子 frame 的 postMessage 不可替代宿主。
    if (event.source !== null || event.data !== 'bmat-native-ready' || event.ports.length !== 1)
      return
    port = event.ports[0]
    port.onmessage = event => {
      const message = JSON.parse(String(event.data)) as {
        id: string
        result?: NativeResult
        error?: string
      }
      const pending = nativePending.get(message.id)
      if (!pending) return
      nativePending.delete(message.id)
      if (message.error) pending.reject(new Error(message.error))
      else pending.resolve(message.result ?? {})
    }
    port.start()
    acceptPort?.(port)
    acceptPort = undefined
  })
  document.addEventListener('visibilitychange', () => {
    lastHeartbeat = Date.now()
    if (ready && document.visibilityState === 'visible') worker?.postMessage({ type: 'foreground' })
  })
}

export async function androidCall(
  operation: string,
  payload: NativeResult = {}
): Promise<NativeResult> {
  if (!isAndroidLocal) throw new Error('当前运行环境不支持手机本地操作')
  let timer: ReturnType<typeof setTimeout> | undefined
  const channel =
    port ||
    (await Promise.race([
      nativePort,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error('手机通信初始化超时，请重新打开应用')), 15_000)
      }),
    ]).finally(() => clearTimeout(timer)))
  const id = nextId()
  const serialized = JSON.stringify({ id, operation, payload })
  if (serialized.length > 24_000_000) throw new Error('本地请求过大，请分批导入或导出')
  return new Promise((resolve, reject) => {
    nativePending.set(id, { resolve, reject })
    channel.postMessage(serialized)
  })
}

function stopEngine(message: string) {
  const error = new Error(message)
  const wasReady = ready
  engineError = error
  worker?.terminate()
  worker = undefined
  ready = false
  if (bootTimeout) clearTimeout(bootTimeout)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  failBoot?.(error)
  bootPromise = undefined
  for (const pending of apiPending.values()) pending.reject(error)
  apiPending.clear()
  for (const pending of nativePending.values()) pending.reject(error)
  nativePending.clear()
  if (port) void androidCall('http.cancelAll').catch(() => undefined)
  if (port) void androidCall('engine.failed', { message }).catch(() => undefined)
  if (wasReady) window.dispatchEvent(new CustomEvent('bmat-engine-reset', { detail: message }))
}

function startEngine(): Promise<void> {
  if (engineError) return Promise.reject(engineError)
  if (bootPromise) return bootPromise
  bootPromise = new Promise((resolve, reject) => {
    completeBoot = resolve
    failBoot = reject
  })
  void androidCall('log.write', { message: '引擎开始启动' }).catch(() => undefined)
  bootTimeout = setTimeout(() => stopEngine('本地服务启动超时，请重试或更新系统 WebView'), 90_000)
  try {
    worker = new Worker('/runtime/engine-worker.js')
  } catch {
    const failedBoot = bootPromise
    stopEngine('无法创建本地运行线程，请打开启动诊断查看系统 WebView 错误')
    return failedBoot
  }
  const instance = worker
  instance.onmessage = event => {
    const message = event.data as {
      type: string
      id: string
      operation: string
      payload: NativeResult
      response: LocalResponse
      error?: string
      text?: string
    }
    if (message.type === 'stage') {
      const text = message.text || '正在启动本地服务'
      window.dispatchEvent(new CustomEvent('bmat-engine-stage', { detail: text }))
      void androidCall('log.write', { message: text }).catch(() => undefined)
    } else if (message.type === 'native') {
      void androidCall(message.operation, message.payload).then(
        result => {
          if (worker === instance)
            instance.postMessage({ type: 'native-result', id: message.id, result })
        },
        error => {
          if (worker === instance)
            instance.postMessage({ type: 'native-result', id: message.id, error: String(error) })
        }
      )
    } else if (message.type === 'ready') {
      ready = true
      lastHeartbeat = Date.now()
      if (bootTimeout) clearTimeout(bootTimeout)
      completeBoot?.()
    } else if (message.type === 'heartbeat') {
      lastHeartbeat = Date.now()
    } else if (message.type === 'fatal') {
      stopEngine(message.error ?? '本地服务启动失败')
    } else if (message.type === 'response') {
      const pending = apiPending.get(message.id)
      apiPending.delete(message.id)
      if (message.error) pending?.reject(new Error(message.error))
      else pending?.resolve(message.response)
    }
  }
  instance.onerror = event => {
    event.preventDefault()
    // 引擎加载或运行的真实错误写入本机日志，手机上没有其他诊断途径。
    const detail = event.message ? `: ${event.message}` : ''
    void androidCall('log.write', { message: `引擎运行错误${detail}` }).catch(() => undefined)
    stopEngine(`本地服务运行失败${detail}`)
  }
  heartbeatTimer = setInterval(() => {
    if (ready && document.visibilityState === 'visible' && Date.now() - lastHeartbeat > 12_000) {
      stopEngine('本地服务响应超时，已结束本次执行；请刷新后重试')
    }
  }, 1000)
  instance.postMessage({ type: 'boot', runStartup: !started })
  started = true
  return bootPromise
}

const localAdapter: AxiosAdapter = async config => {
  await startEngine()
  const id = nextId()
  const path = axios.getUri(config)
  const uri = new URL(path, location.origin)
  if (uri.origin !== location.origin || !uri.pathname.startsWith('/api/')) {
    throw new AxiosError('本地接口地址不受支持', 'ERR_BAD_REQUEST', config)
  }
  if (config.signal?.aborted) throw new CanceledError()
  config.cancelToken?.throwIfRequested()
  const response = await new Promise<LocalResponse>((resolve, reject) => {
    const token = config.cancelToken as SubscribableToken | undefined
    const cancel = () => {
      worker?.postMessage({ type: 'cancel', id })
      apiPending.delete(id)
      cleanup()
      reject(new CanceledError())
    }
    config.signal?.addEventListener?.('abort', cancel, { once: true })
    token?.subscribe(cancel)
    const cleanup = () => {
      config.signal?.removeEventListener?.('abort', cancel)
      token?.unsubscribe(cancel)
    }
    apiPending.set(id, {
      resolve: response => {
        cleanup()
        resolve(response)
      },
      reject: error => {
        cleanup()
        reject(error)
      },
    })
    worker?.postMessage({
      type: 'request',
      id,
      request: {
        id,
        path: uri.pathname + uri.search,
        method: config.method?.toUpperCase() ?? 'GET',
        headers: config.headers.toJSON(),
        body: typeof config.data === 'string' ? config.data : '',
      },
    })
  })
  const result = {
    data: response.body,
    status: response.status,
    statusText: '',
    headers: response.headers,
    config,
  }
  if (config.validateStatus && !config.validateStatus(response.status)) {
    throw new AxiosError('本地操作未完成', 'ERR_BAD_RESPONSE', config, undefined, result)
  }
  return result
}

export function installAndroidAdapter(): void {
  if (isAndroidLocal) axios.defaults.adapter = localAdapter
}

export function retryAndroidEngine(): void {
  engineError = undefined
}

export function markAndroidReady(): void {
  if (isAndroidLocal) void androidCall('engine.ready').catch(() => undefined)
}
