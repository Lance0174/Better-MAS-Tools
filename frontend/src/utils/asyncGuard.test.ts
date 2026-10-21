import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDebouncer, createSequenceGuard, pollUntilSettled } from './asyncGuard'

afterEach(() => {
  vi.useRealTimers()
})

describe('createSequenceGuard', () => {
  it('只认最后一次请求：先发后到的旧响应不再是最新', () => {
    const guard = createSequenceGuard()
    const first = guard.next()
    const second = guard.next()
    expect(guard.isLatest(first)).toBe(false)
    expect(guard.isLatest(second)).toBe(true)
  })

  it('卸载后所有令牌都失效，迟到的响应不会再写状态', () => {
    const guard = createSequenceGuard()
    const token = guard.next()
    guard.dispose()
    expect(guard.isLatest(token)).toBe(false)
  })
})

describe('createDebouncer', () => {
  it('延迟窗口内的多次触发只执行最后一次', () => {
    vi.useFakeTimers()
    const debouncer = createDebouncer(300)
    const calls: number[] = []
    debouncer.schedule(() => calls.push(1))
    vi.advanceTimersByTime(200)
    debouncer.schedule(() => calls.push(2))
    vi.advanceTimersByTime(300)
    expect(calls).toEqual([2])
  })

  it('取消后不再执行，卸载后不会补发请求', () => {
    vi.useFakeTimers()
    const debouncer = createDebouncer(300)
    const calls: number[] = []
    debouncer.schedule(() => calls.push(1))
    debouncer.cancel()
    vi.advanceTimersByTime(1000)
    expect(calls).toEqual([])
  })
})

describe('pollUntilSettled', () => {
  const pending = { status: 'pending' as const }
  const options = (isDisposed: () => boolean) => ({
    intervalMs: 800,
    timeoutMs: 5000,
    isDisposed,
    isSettled: (value: { status: string }) => value.status === 'done',
  })

  it('第一次取值就是终态时立即返回，不重复请求', async () => {
    vi.useFakeTimers()
    const probe = vi.fn(async () => ({ status: 'done' }))
    const outcome = await pollUntilSettled(probe, options(() => false))
    expect(outcome).toEqual({ status: 'settled', value: { status: 'done' } })
    expect(probe).toHaveBeenCalledTimes(1)
  })

  it('未到终态时按间隔重试，等到终态才返回', async () => {
    vi.useFakeTimers()
    const values = [pending, pending, { status: 'done' }]
    const probe = vi.fn(async () => values.shift() ?? { status: 'done' })
    const result = pollUntilSettled(probe, options(() => false))
    await vi.advanceTimersByTimeAsync(800 * 3)
    expect(await result).toEqual({ status: 'settled', value: { status: 'done' } })
    expect(probe).toHaveBeenCalledTimes(3)
  })

  it('组件卸载后停止轮询，不再发请求也不再提示', async () => {
    vi.useFakeTimers()
    let disposed = false
    const probe = vi.fn(async () => {
      // 第一次请求返回后组件被卸载（例如用户离开页面）。
      disposed = true
      return pending
    })
    const result = pollUntilSettled(probe, options(() => disposed))
    await vi.advanceTimersByTimeAsync(800 * 5)
    expect(await result).toEqual({ status: 'disposed' })
    expect(probe).toHaveBeenCalledTimes(1)
  })

  it('始终不到终态时在超时后返回 timeout', async () => {
    vi.useFakeTimers()
    const probe = vi.fn(async () => pending)
    const result = pollUntilSettled(probe, options(() => false))
    await vi.advanceTimersByTimeAsync(6000)
    expect(await result).toEqual({ status: 'timeout' })
  })
})
