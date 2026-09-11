import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import standalone from './locales/standalone'

export const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: { 'zh-CN': { ...zhCN, standalone } },
})
export const translate = (key: string, values: Record<string, string | number> = {}) =>
  i18n.global.t(key, values)
