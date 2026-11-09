import { computed, onScopeDispose, ref, watchEffect } from 'vue'
import { theme } from 'ant-design-vue'
import { useSettingsStore } from '@/stores/settings'

/** 审核方案 B：深浅主题共享细线、适度密度和黄色操作强调。 */
const PAPER = {
  light: {
    canvas: '#eceeea',
    raised: '#fafbf7',
    bright: '#f0f2ed',
    ink: '#242a28',
    ink2: '#5e6964',
    ink3: '#5e6964',
    line: '#c8cec5',
    lineSoft: '#e0e4dc',
    link: '#7a6100',
  },
  dark: {
    canvas: '#191b1e',
    raised: '#222529',
    bright: '#2a2d31',
    ink: '#edf0f2',
    ink2: '#a0a7b0',
    ink3: '#a0a7b0',
    line: '#393d42',
    lineSoft: '#2d3136',
    link: '#f5d747',
  },
} as const

/** 所有主题判断、Ant Design 变量与液态玻璃令牌都由此处统一发布。 */
export function useTheme() {
  const settings = useSettingsStore()
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(media.matches)
  const onSystemTheme = () => {
    systemDark.value = media.matches
  }
  const mediaChange = media.addEventListener
    ? () => media.addEventListener('change', onSystemTheme)
    : () => media.addListener(onSystemTheme)
  const removeMediaChange = media.removeEventListener
    ? () => media.removeEventListener('change', onSystemTheme)
    : () => media.removeListener(onSystemTheme)
  mediaChange()
  window.addEventListener('bmat-system-theme-change', onSystemTheme)
  onScopeDispose(() => {
    removeMediaChange()
    window.removeEventListener('bmat-system-theme-change', onSystemTheme)
  })
  const isDark = computed(
    () =>
      settings.data?.Theme === 'dark' ||
      ((!settings.data?.Theme || settings.data.Theme === 'system') && systemDark.value)
  )
  const palette = computed(() => (isDark.value ? PAPER.dark : PAPER.light))
  const themeConfig = computed(() => ({
    algorithm: isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      // 出版黄只做实心块：按钮/开关上的文字必须是深色，否则白字压黄只有 1.2:1。
      colorPrimary: '#f5d747',
      colorTextLightSolid: '#242a28',
      colorLink: palette.value.link,
      colorSuccess: '#1f7a48',
      colorError: '#c8321a',
      colorInfo: '#2f6fbe',
      colorWarning: '#a9781a',
      colorBgLayout: palette.value.canvas,
      colorBgContainer: palette.value.raised,
      colorBgElevated: palette.value.bright,
      colorText: palette.value.ink,
      colorTextSecondary: palette.value.ink2,
      colorTextTertiary: palette.value.ink3,
      colorBorder: palette.value.line,
      colorBorderSecondary: palette.value.lineSoft,
      // 小圆角只用于容器与控件，保持审核方案的细线布局。
      borderRadius: 3,
      fontSize: 14,
      fontFamily: "'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif",
      controlHeight: 35,
    },
  }))
  // 液态玻璃：关闭后（或用户设置 GlassEffect=false）退化为半透明实色材质，不做背景模糊。
  const glassEnabled = computed(() => settings.data?.GlassEffect !== false)
  watchEffect(() => {
    document.documentElement.classList.toggle('dark', isDark.value)
    document.documentElement.classList.toggle('glass-lite', !glassEnabled.value)
    // 只写"用户偏好"，最终 --app-glass-blur 交由 style.css 的降级规则决定
    // （不支持 backdrop-filter、安卓 WebView、减少动态效果时统一归零）。
    document.documentElement.style.setProperty(
      '--app-glass-blur-pref',
      glassEnabled.value ? '18px' : '0px'
    )
    // ConfigProvider 的合并顺序是「算法派生 → 覆盖 token 再压一层」，
    // 直接调 algorithm() 只做前者，取到的会是 AntD 默认底色（深色下甚至是 #000）。
    const derived = themeConfig.value.algorithm({
      ...theme.defaultSeed,
      ...themeConfig.value.token,
    })
    const tokens = { ...derived, ...themeConfig.value.token }
    const style = document.documentElement.style
    style.setProperty('--ant-color-bg-container', String(tokens.colorBgContainer))
    style.setProperty('--ant-color-bg-layout', String(tokens.colorBgLayout))
    style.setProperty('--ant-color-bg-elevated', String(tokens.colorBgElevated))
    style.setProperty('--ant-color-border', String(tokens.colorBorder))
    style.setProperty('--ant-color-border-secondary', String(tokens.colorBorderSecondary))
    style.setProperty('--ant-color-error', String(tokens.colorError))
    style.setProperty('--ant-color-primary', String(tokens.colorPrimary))
    style.setProperty('--ant-color-primary-bg', String(tokens.colorPrimaryBg))
    style.setProperty('--ant-color-primary-border', String(tokens.colorPrimaryBorder))
    style.setProperty('--ant-color-success', String(tokens.colorSuccess))
    style.setProperty('--ant-color-text', String(tokens.colorText))
    style.setProperty('--ant-color-text-secondary', String(tokens.colorTextSecondary))
    style.setProperty('--ant-color-text-tertiary', String(tokens.colorTextTertiary))
    style.setProperty('--ant-color-warning', String(tokens.colorWarning))
    // 32px 细格随主题切换，强度压到 5% 以下，保持内容可读。
    const dark = isDark.value
    style.setProperty('--app-grid-line', dark ? 'rgba(255,255,255,0.018)' : 'rgba(0,0,0,0.025)')
    style.setProperty('--app-panel', dark ? 'rgba(255,225,0,0.10)' : 'rgba(255,225,0,0.16)')
    style.setProperty('--app-panel-border', dark ? 'rgba(255,225,0,0.34)' : 'rgba(21,21,21,0.24)')
    style.setProperty('--app-tick', dark ? 'rgba(255,255,255,0.25)' : 'rgba(21,21,21,0.22)')
    style.setProperty('--app-corner', dark ? 'rgba(255,225,0,0.85)' : 'rgba(21,21,21,0.55)')
    style.setProperty('--app-scanline', dark ? 'rgba(255,225,0,0.04)' : 'rgba(21,21,21,0.03)')
    // 报错文字专用色：危险实心色上的白字要 5:1，当文字又要 4.5:1，一个红做不到两件事。
    style.setProperty('--app-danger-ink', dark ? '#ff9088' : '#b5341f')
    style.setProperty('--app-accent', '#f5d747')
    // 液态玻璃令牌：纸面皮肤下玻璃更接近"蒙版纸"——底色近乎不透明，只留一点模糊湿度。
    const glass = (name: string, value: string) =>
      style.setProperty(`--app-glass-${name}-pref`, value)
    glass('tint', dark ? 'rgba(34,34,38,0.86)' : 'rgba(252,252,250,0.86)')
    glass('tint-strong', dark ? 'rgba(28,28,32,0.94)' : 'rgba(255,255,252,0.94)')
    glass('tint-soft', dark ? 'rgba(34,34,38,0.7)' : 'rgba(252,252,250,0.7)')
    glass('border-top', dark ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.9)')
    glass('border-body', dark ? 'rgba(74,74,80,0.9)' : 'rgba(184,184,177,0.9)')
    glass('highlight', dark ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.5)')
    glass('shadow', dark ? 'rgba(0,0,0,0.55)' : 'rgba(21,21,21,0.14)')
    glass('vignette', dark ? 'rgba(0,0,0,0.42)' : 'rgba(21,21,21,0.06)')
    glass('saturate', dark ? '120%' : '110%')
  })
  return { themeConfig, isDark, glassEnabled }
}
