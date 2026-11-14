import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SettingsData } from '@/api'

const api = vi.hoisted(() => ({ getSettings: vi.fn(), updateSettings: vi.fn() }))
vi.mock('@/composables/useCommunityApi', () => ({ useCommunityApi: () => api }))
import { useSettingsStore } from './settings'

let saved: SettingsData
beforeEach(() => {
  setActivePinia(createPinia())
  saved = { Theme: 'light', GlassEffect: true }
  api.getSettings.mockReset().mockImplementation(async () => ({ data: { ...saved } }))
  api.updateSettings.mockReset().mockImplementation(async (value: SettingsData) => { saved = value })
})

describe('外观与偏好保存', () => {
  it('快速切换外观时立即显示最后选择，串行落盘，重载后保持', async () => {
    const store = useSettingsStore()
    await store.load()
    const first = store.patch({ Theme: 'dark' })
    const second = store.patch({ Theme: 'light' })
    expect(store.data?.Theme).toBe('light')
    await Promise.all([first, second])
    await store.load()
    expect(store.data?.Theme).toBe('light')
    expect(api.updateSettings.mock.calls.map(([value]) => value.Theme)).toEqual(['dark', 'light'])
  })

  it('同时修改其他偏好不会把新主题覆盖回旧主题', async () => {
    const store = useSettingsStore()
    await store.load()
    const theme = store.patch({ Theme: 'dark' })
    const preference = store.save({ ...store.data, GlassEffect: false })
    await Promise.all([theme, preference])
    expect(saved).toMatchObject({ Theme: 'dark', GlassEffect: false })
  })

  it('较早开始的读取不能覆盖刚保存的主题', async () => {
    const store = useSettingsStore()
    await store.load()
    let release!: (value: { data: SettingsData }) => void
    api.getSettings.mockImplementationOnce(() => new Promise(resolve => { release = resolve }))
    const old = store.load()
    await store.patch({ Theme: 'dark' })
    release({ data: { Theme: 'light' } })
    await old
    expect(store.data?.Theme).toBe('dark')
  })

  it('保存失败回退已确认主题，后续保存仍可使用', async () => {
    const store = useSettingsStore()
    await store.load()
    api.updateSettings.mockRejectedValueOnce(new Error('模拟存储失败'))
    await expect(store.patch({ Theme: 'dark' })).rejects.toThrow('模拟存储失败')
    expect(store.data?.Theme).toBe('light')
    await store.patch({ Theme: 'dark' })
    expect(saved.Theme).toBe('dark')
  })

  it('保存期间开始的旧读取也不能覆盖已落盘的主题', async () => {
    const store = useSettingsStore()
    await store.load()
    let finishUpdate!: () => void
    api.updateSettings.mockImplementationOnce((value: SettingsData) => new Promise<void>(resolve => {
      finishUpdate = () => { saved = value; resolve() }
    }))
    const theme = store.patch({ Theme: 'dark' })
    await vi.waitFor(() => expect(api.updateSettings).toHaveBeenCalledOnce())
    let finishLoad!: (value: { data: SettingsData }) => void
    api.getSettings.mockImplementationOnce(() => new Promise(resolve => { finishLoad = resolve }))
    const stale = store.load()
    finishUpdate()
    await theme
    finishLoad({ data: { Theme: 'light', GlassEffect: true } })
    await stale
    expect(store.data?.Theme).toBe('dark')
  })
})
