import { computed, onScopeDispose, ref, watchEffect } from 'vue'
import { theme } from 'ant-design-vue'
import { useSettingsStore } from '@/stores/settings'

/** 所有主题判断和 Ant Design 变量都由此处统一发布。 */
export function useTheme() {
  const settings = useSettingsStore()
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(media.matches)
  const onSystemTheme = () => {
    systemDark.value = media.matches
  }
  media.addEventListener('change', onSystemTheme)
  onScopeDispose(() => media.removeEventListener('change', onSystemTheme))
  const isDark = computed(
    () =>
      settings.data?.Theme === 'dark' ||
      ((!settings.data?.Theme || settings.data.Theme === 'system') && systemDark.value)
  )
  const themeConfig = computed(() => ({
    algorithm: isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: { colorPrimary: '#00b3a4', borderRadius: 6, fontSize: 14 },
  }))
  watchEffect(() => {
    document.documentElement.classList.toggle('dark', isDark.value)
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
  })
  return { themeConfig, isDark }
}
