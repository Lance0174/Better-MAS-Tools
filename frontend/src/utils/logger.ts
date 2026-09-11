/** 社区流程日志出口；不依赖 MAS preload，也不序列化请求对象。 */
import { DiagnosticsService } from '@/api'

export interface AppLogger {
  debug(message: string, ...detail: unknown[]): void
  info(message: string, ...detail: unknown[]): void
  warn(message: string, ...detail: unknown[]): void
  error(message: string, ...detail: unknown[]): void
}

export function getLogger(module: string): AppLogger {
  const sensitiveKey =
    '[\\w-]*(?:token|cookie|password|passwd|pwd|secret|ticket|scan_code|sms_?code|authkey|api_?key|authorization|cred|mid|phone|cellphone|useridentity|captcha_output|lot_number|geetest_(?:challenge|validate|seccode)|x-community-session)[\\w-]*'
  const safeText = (value: string) =>
    value
      .replace(new RegExp(`(["']${sensitiveKey}["']\\s*:\\s*["'])(.*?)(["'])`, 'gi'), '$1***$3')
      .replace(new RegExp(`(\\b${sensitiveKey}["']?\\s*[:=]\\s*["']?)[^\\s,;"'}]+`, 'gi'), '$1***')
      .replace(/(https?:\/\/)[^/\s@]+@/gi, '$1***@')
      .replace(/(https?:\/\/[^\s?#]+)[?#][^\s]*/gi, '$1')
      .replace(/\b1[3-9]\d{9}\b/g, '***')
      .replace(/\b[A-Za-z0-9_-]{32,}\b/g, '***')
      .slice(0, 12000)
  const safeModule = safeText(module).slice(0, 80)
  const write = (level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR', value: string) => {
    const text = safeText(value)
    const output = {
      DEBUG: console.debug,
      INFO: console.info,
      WARNING: console.warn,
      ERROR: console.error,
    }[level]
    output(`[BMAT][${safeModule}] ${text}`)
    // 日志接口失败保留控制台输出，不产生新的日志请求循环。
    void DiagnosticsService.writeClientLog({ level, module: safeModule, message: text }).catch(
      () => undefined
    )
  }
  return {
    debug: text => write('DEBUG', text),
    info: text => write('INFO', text),
    warn: text => write('WARNING', text),
    error: text => write('ERROR', text),
  }
}
