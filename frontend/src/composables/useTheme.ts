import { computed, onScopeDispose, ref, watchEffect } from 'vue'
import { theme } from 'ant-design-vue'
import { useSettingsStore } from '@/stores/settings'

/**
 * 纸面印刷（方案 A）调色板：浅色为纸、深色为墨。
 * 主色是出版黄 #ffe100 —— 它只能做「实心块 + 深色字」，不能当正文或链接色，
 * 因此正文走 ink，链接另给 colorLink，报错文字由 style.css 的 --app-danger-ink 承担。
 */
const PAPER = {
  light: {
    canvas: '#e3e3df',
    raised: '#f5f5f2',
    bright: '#fbfbf9',
    ink: '#151515',
    ink2: '#5c5c55',
    ink3: '#66665f',
    line: '#cbcbc4',
    lineSoft: '#deded8',
    link: '#7a6100',
  },
  dark: {
    canvas: '#19191b',
    raised: '#242427',
    bright: '#2b2c2f',
    ink: '#eeeeee',
    ink2: '#a6a6ac',
    ink3: '#94949b',
    line: '#3a3a3f',
    lineSoft: '#303034',
    link: '#ffe100',
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
      colorPrimary: '#ffe100',
      colorTextLightSolid: '#151515',
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
      // 纸面印刷没有圆角：所有控件统一直角，与书脊、表格线一致。
      borderRadius: 0,
      fontSize: 13,
      fontFamily: "'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif",
      controlHeight: 30,
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
    // 纸面网格：24px 细格，浅色用墨线、深色用白线，强度都压到 5% 以下不抢内容。
    const dark = isDark.value
    style.setProperty('--app-grid-line', dark ? 'rgba(255,255,255,0.045)' : 'rgba(21,21,21,0.048)')
    style.setProperty('--app-panel', dark ? 'rgba(255,225,0,0.10)' : 'rgba(255,225,0,0.16)')
    style.setProperty('--app-panel-border', dark ? 'rgba(255,225,0,0.34)' : 'rgba(21,21,21,0.24)')
    style.setProperty('--app-tick', dark ? 'rgba(255,255,255,0.25)' : 'rgba(21,21,21,0.22)')
    style.setProperty('--app-corner', dark ? 'rgba(255,225,0,0.85)' : 'rgba(21,21,21,0.55)')
    style.setProperty('--app-scanline', dark ? 'rgba(255,225,0,0.04)' : 'rgba(21,21,21,0.03)')
    // 报错文字专用色：危险实心色上的白字要 5:1，当文字又要 4.5:1，一个红做不到两件事。
    style.setProperty('--app-danger-ink', dark ? '#ff9088' : '#b5341f')
    style.setProperty('--app-accent', '#ffe100')
    // 液态玻璃令牌：纸面皮肤下玻璃更接近"蒙版纸"——底色近乎不透明，只留一点模糊湿度。
    const glass = (name: string, value: string) => style.setProperty(`--app-glass-${name}-pref`, value)
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