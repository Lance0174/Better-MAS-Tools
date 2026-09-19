import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import standalone from './locales/standalone'

export const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  // OnboardingWizard 组件以顶层 onboarding.* 取文案，需在此显式挂载
  messages: { 'zh-CN': { ...zhCN, standalone, onboarding: standalone.onboarding } },
})
export const translate = (key: string, values: Record<string, string | number> = {}) =>
  i18n.global.t(key, values)
