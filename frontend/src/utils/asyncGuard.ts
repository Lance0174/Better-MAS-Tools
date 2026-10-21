/**
 * 异步副作用的三类守卫：只认最后一次请求、可取消的防抖、卸载即停止的轮询。
 * 这三件事都和组件卸载、响应先发后到纠缠在一起，抽成纯逻辑模块才能在 node 环境用假定时器覆盖。
 */

/** 请求序号守卫：先发后到的响应不得覆盖新结果。 */
export interface SequenceGuard {
  /** 开始一次新请求，此前所有令牌立即失效。 */
  next(): number
  /** 令牌是否仍是最新一次（且组件未卸载）。 */
  isLatest(token: number): boolean
  /** 组件卸载：此后所有令牌都失效。 */
  dispose(): void
}

export function createSequenceGuard(): SequenceGuard {
  let current = 0
  let disposed = false
  return {
    next: () => ++current,
    isLatest: token => !disposed && token === current,
    dispose: () => {
      disposed = true
    },
  }
}

/** 防抖守卫：同一延迟窗口内多次触发只保留最后一次，组件卸载时可整体取消。 */
export interface Debouncer {
  schedule(callback: () => void): void
  cancel(): void
}

export function createDebouncer(delayMs: number): Debouncer {
  let timer: ReturnType<typeof setTimeout> | undefined
  const cancel = () => {
    if (timer !== undefined) clearTimeout(timer)
    timer = undefined
  }
  return {
    schedule: callback => {
      cancel()
      timer = setTimeout(() => {
        timer = undefined
        callback()
      }, delayMs)
    },
    cancel,
  }
}

/** 轮询结果：拿到终态、等待超时、或组件已卸载（卸载时调用方不该再提示）。 */
export type PollOutcome<T> =
  | { status: 'settled'; value: T }
  | { status: 'timeout' }
  | { status: 'disposed' }

export interface PollOptions<T> {
  intervalMs: number
  timeoutMs: number
  /** 组件已卸载时为 true：立即停止，不再发请求。 */
  isDisposed: () => boolean
  isSettled: (value: T) => boolean
}

/** 反复取值直到终态；每轮开始前检查是否已卸载，超时返回 timeout 交给调用方决定文案。 */
export async function pollUntilSettled<T>(
  probe: () => Promise<T>,
  options: PollOptions<T>
): Promise<PollOutcome<T>> {
  const deadline = Date.now() + options.timeoutMs
  while (Date.now() < deadline) {
    if (options.isDisposed()) return { status: 'disposed' }
    const value = await probe()
    if (options.isSettled(value)) return { status: 'settled', value }
    await new Promise<void>(resolve => setTimeout(resolve, options.intervalMs))
  }
  return { status: 'timeout' }
}
