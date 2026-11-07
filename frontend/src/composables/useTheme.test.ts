import { effectScope, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const settings = {
  data: ref<{ Theme?: 'light' | 'dark' | 'system'; GlassEffect?: boolean } | null>(null),
}
// Pinia 会把 store 里的 ref 解包成普通属性，这里用 getter 模拟同样的读取语义。
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    get data() {
      return settings.data.value
    },
  }),
}))
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

  it('writes glass tokens as -pref so the stylesheet can still degrade them', async () => {
    const setProperty = vi.fn()
    vi.stubGlobal('window', Object.assign(new EventTarget(), { matchMedia: () => new MediaQuery() }))
    vi.stubGlobal('document', {
      documentElement: { classList: { toggle: vi.fn() }, style: { setProperty } },
    })
    settings.data.value = { Theme: 'light' }
    const { useTheme } = await import('./useTheme')
    const scope = effectScope()
    const state = scope.run(() => useTheme())!
    const names = setProperty.mock.calls.map(call => call[0] as string)
    // 只能写 -pref：写最终令牌会变成 <html> 内联样式，压过 .glass-lite 等降级规则。
    expect(names).toContain('--app-glass-blur-pref')
    expect(names).toContain('--app-glass-tint-pref')
    expect(names).not.toContain('--app-glass-tint')
    expect(names).not.toContain('--app-glass-highlight')
    expect(state.glassEnabled.value).toBe(true)
    expect(setProperty).toHaveBeenCalledWith('--app-glass-blur-pref', '26px')
    settings.data.value = { Theme: 'light', GlassEffect: false }
    await nextTick()
    expect(state.glassEnabled.value).toBe(false)
    expect(setProperty).toHaveBeenCalledWith('--app-glass-blur-pref', '0px')
    scope.stop()
  })
})

