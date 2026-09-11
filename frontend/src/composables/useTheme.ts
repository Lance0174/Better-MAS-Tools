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
    token: { colorPrimary: '#4c7bd9', borderRadius: 8, fontSize: 14 },
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
  })
  return { themeConfig, isDark }
}
