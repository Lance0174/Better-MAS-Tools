import { describe, expect, it, vi } from 'vitest'
import { createSettingsAutoSave } from './settingsAutoSave'

describe('settings auto save', () => {
  it('saves switches immediately and debounces text changes', async () => {
    vi.useFakeTimers()
    const save = vi.fn().mockResolvedValue(undefined)
    const saver = createSettingsAutoSave({ getSnapshot: () => ({}), save, onFailure: vi.fn() })
    saver.changed()
    await vi.runAllTimersAsync()
    expect(save).toHaveBeenCalledTimes(1)
    saver.textChanged()
    saver.textChanged()
    await vi.advanceTimersByTimeAsync(499)
    expect(save).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(save).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })

  it('flushes text on blur and reports after five failed attempts', async () => {
    vi.useFakeTimers()
    const save = vi.fn().mockRejectedValue(new Error('failed'))
    const onFailure = vi.fn()
    const saver = createSettingsAutoSave({ getSnapshot: () => ({}), save, onFailure })
    saver.textChanged()
    saver.textBlurred()
    // 重试链在 0/500/1000/1500/2000ms 各尝试一次；1999ms 时仅 4 次，尚未触发失败上报。
    await vi.advanceTimersByTimeAsync(1_999)
    expect(onFailure).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(500)
    expect(save).toHaveBeenCalledTimes(5)
    expect(onFailure).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })
})
