import { effectScope, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const settings = { data: ref<{ Theme?: 'light' | 'dark' | 'system' } | null>(null) }
vi.mock('@/stores/settings', () => ({ useSettingsStore: () => settings }))
vi.mock('ant-design-vue', () => ({
  theme: {
    defaultAlgorithm: () => ({ colorBgContainer: '#fff' }),
    darkAlgorithm: () => ({ colorBgContainer: '#000' }),
    defaultSeed: {},
  },
}))

class MediaQuery extends EventTarget {
  matches = false
  addListener(listener: EventListener) {
    this.addEventListener('change', listener)
  }
  removeListener(listener: EventListener) {
    this.removeEventListener('change', listener)
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('useTheme', () => {
  it('uses the system scheme and accepts Android system-theme notifications', async () => {
    const media = new MediaQuery()
    vi.stubGlobal('window', Object.assign(new EventTarget(), { matchMedia: () => media }))
    vi.stubGlobal('document', { documentElement: { classList: { toggle: vi.fn() }, style: { setProperty: vi.fn() } } })
    settings.data.value = { Theme: 'system' }
    const scope = effectScope()
    const state = scope.run(async () => (await import('./useTheme')).useTheme())!
    expect((await state).isDark.value).toBe(false)
    media.matches = true
    window.dispatchEvent(new CustomEvent('bmat-system-theme-change'))
    await nextTick()
    expect((await state).isDark.value).toBe(true)
    scope.stop()
  })
})
