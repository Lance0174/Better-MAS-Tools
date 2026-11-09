import { describe, expect, it, vi } from 'vitest'
import { applyLightModeChange } from './settingsLightMode'

describe('轻量模式开启确认', () => {
  it('取消时不开启且不触发保存', async () => {
    const setEnabled = vi.fn()
    const onChange = vi.fn()
    await applyLightModeChange(true, {
      setEnabled,
      confirm: () => Promise.resolve(false),
      onChange,
    })
    expect(setEnabled).toHaveBeenCalledWith(false)
    expect(setEnabled).not.toHaveBeenCalledWith(true)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('确认后才开启并触发保存', async () => {
    const setEnabled = vi.fn()
    const onChange = vi.fn()
    await applyLightModeChange(true, {
      setEnabled,
      confirm: () => Promise.resolve(true),
      onChange,
    })
    expect(setEnabled).toHaveBeenLastCalledWith(true)
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('关闭时不弹确认，直接写回并保存', async () => {
    const confirm = vi.fn()
    const setEnabled = vi.fn()
    const onChange = vi.fn()
    await applyLightModeChange(false, { setEnabled, confirm, onChange })
    expect(confirm).not.toHaveBeenCalled()
    expect(setEnabled).toHaveBeenCalledWith(false)
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})
