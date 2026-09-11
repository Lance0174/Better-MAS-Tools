/** 社区流程日志出口；不依赖 MAS preload，也不序列化请求对象。 */
export interface AppLogger {
  debug(message: string, ...detail: unknown[]): void
  info(message: string, ...detail: unknown[]): void
  warn(message: string, ...detail: unknown[]): void
  error(message: string, ...detail: unknown[]): void
}

export function getLogger(module: string): AppLogger {
  const safeText = (value: string) =>
    value.replace(/(token|cookie|password|secret)\s*[:=]\s*\S+/gi, '$1=***')
  return {
    debug: text => console.debug(`[${module}] ${safeText(text)}`),
    info: text => console.info(`[${module}] ${safeText(text)}`),
    warn: text => console.warn(`[${module}] ${safeText(text)}`),
    error: text => console.error(`[${module}] ${safeText(text)}`),
  }
}
