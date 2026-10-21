import { computed, onScopeDispose, ref, watchEffect } from 'vue'
import { theme } from 'ant-design-vue'
import { useSettingsStore } from '@/stores/settings'

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
  const themeConfig = computed(() => ({
    algorithm: isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: { colorPrimary: '#00b3a4', borderRadius: 6, fontSize: 14 },
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
      glassEnabled.value ? '26px' : '0px'
    )
    const tokens = themeConfig.value.algorithm({ ...theme.defaultSeed, ...themeConfig.value.token })
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
    // 终末地工业风：网格底纹、面板高亮、刻度线、HUD 角标与扫描线，浅/深两套值。
    style.setProperty('--app-grid-line', isDark.value ? 'rgba(255,255,255,0.05)' : 'rgba(15,20,25,0.045)')
    style.setProperty('--app-panel', isDark.value ? 'rgba(0,179,164,0.08)' : 'rgba(0,179,164,0.06)')
    style.setProperty('--app-panel-border', isDark.value ? 'rgba(0,179,164,0.35)' : 'rgba(0,179,164,0.5)')
    style.setProperty('--app-tick', isDark.value ? 'rgba(255,255,255,0.25)' : 'rgba(15,20,25,0.22)')
    style.setProperty('--app-corner', isDark.value ? 'rgba(0,179,164,0.7)' : 'rgba(0,179,164,0.85)')
    style.setProperty('--app-scanline', isDark.value ? 'rgba(0,179,164,0.06)' : 'rgba(0,179,164,0.05)')
    // 液态玻璃令牌（对齐 Kinara 音乐定稿的 E 稿）：深色玻璃底色更深、浅色更亮；
    // 高光带与顶部描边在浅色下更实，避免玻璃在浅色底上"发灰"。
    const dark = isDark.value
    style.setProperty('--app-glass-tint', dark ? 'rgba(25,35,57,0.38)' : 'rgba(255,255,255,0.32)')
    style.setProperty('--app-glass-tint-strong', dark ? 'rgba(20,28,46,0.66)' : 'rgba(255,255,255,0.62)')
    style.setProperty('--app-glass-tint-soft', dark ? 'rgba(25,35,57,0.26)' : 'rgba(255,255,255,0.24)')
    style.setProperty(
      '--app-glass-border-top',
      dark ? 'rgba(200,238,255,0.70)' : 'rgba(255,255,255,0.95)'
    )
    style.setProperty(
      '--app-glass-border-body',
      dark ? 'rgba(160,220,245,0.24)' : 'rgba(255,255,255,0.62)'
    )
    style.setProperty('--app-glass-highlight', dark ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.46)')
    style.setProperty('--app-glass-shadow', dark ? 'rgba(0,0,0,0.48)' : 'rgba(6,30,42,0.20)')
    style.setProperty('--app-glass-vignette', dark ? 'rgba(0,0,0,0.42)' : 'rgba(6,30,42,0.08)')
    style.setProperty('--app-glass-saturate', dark ? '140%' : '160%')
  })
  return { themeConfig, isDark, glassEnabled }
}
