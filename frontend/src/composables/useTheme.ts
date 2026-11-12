import { computed, onScopeDispose, ref, watchEffect } from 'vue'
import { theme } from 'ant-design-vue'
import { useSettingsStore } from '@/stores/settings'

/** 已审核的 Miuix 风格：浅灰画布、圆角卡片和蓝色操作强调。 */
const PALETTE = {
  light: {
    canvas: '#f5f5f5',
    raised: '#ffffff',
    bright: '#f2f3f5',
    ink: '#16181d',
    ink2: '#646974',
    ink3: '#646974',
    line: '#e4e6eb',
    lineSoft: '#eceef1',
    link: '#2468d5',
  },
  dark: {
    canvas: '#101114',
    raised: '#1c1d21',
    bright: '#28292e',
    ink: '#f0f1f4',
    ink2: '#aaadb6',
    ink3: '#aaadb6',
    line: '#383940',
    lineSoft: '#303137',
    link: '#77aaff',
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
  const palette = computed(() => (isDark.value ? PALETTE.dark : PALETTE.light))
  const themeConfig = computed(() => ({
    algorithm: isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#2468d5',
      colorTextLightSolid: '#ffffff',
      colorLink: palette.value.link,
      colorSuccess: isDark.value ? '#80d7a3' : '#207946',
      colorError: '#c64141',
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
      borderRadius: 12,
      borderRadiusLG: 24,
      borderRadiusSM: 8,
      fontSize: 14,
      fontFamily: "'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif",
      controlHeight: 40,
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
    style.setProperty('--ant-color-link', String(tokens.colorLink))
    style.setProperty('--ant-color-success', String(tokens.colorSuccess))
    style.setProperty('--ant-color-text', String(tokens.colorText))
    style.setProperty('--ant-color-text-secondary', String(tokens.colorTextSecondary))
    style.setProperty('--ant-color-text-tertiary', String(tokens.colorTextTertiary))
    style.setProperty('--ant-color-warning', String(tokens.colorWarning))
    const dark = isDark.value
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
    style.setProperty('--app-panel', String(tokens.colorPrimaryBg))
    // 报错文字专用色：危险实心色上的白字要 5:1，当文字又要 4.5:1，一个红做不到两件事。
    style.setProperty('--app-danger-ink', dark ? '#ff9088' : '#b5341f')
    style.setProperty('--app-accent', String(tokens.colorPrimary))
    // 保留用户的浮层材质偏好；卡片始终使用稳定的实色底。
    const glass = (name: string, value: string) =>
      style.setProperty(`--app-glass-${name}-pref`, value)
    glass('tint', dark ? 'rgba(28,29,33,0.94)' : 'rgba(255,255,255,0.94)')
    glass('tint-strong', palette.value.raised)
    glass('tint-soft', palette.value.bright)
    glass('border-top', dark ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.9)')
    glass('border-body', dark ? 'rgba(74,74,80,0.9)' : 'rgba(184,184,177,0.9)')
    glass('highlight', dark ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.5)')
    glass('shadow', dark ? 'rgba(0,0,0,0.55)' : 'rgba(21,21,21,0.14)')
    glass('vignette', dark ? 'rgba(0,0,0,0.42)' : 'rgba(21,21,21,0.06)')
    glass('saturate', dark ? '120%' : '110%')
  })
  return { themeConfig, isDark, glassEnabled }
}
