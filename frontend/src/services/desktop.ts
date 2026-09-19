/** 桌面壳专属能力判定与桥接；浏览器与安卓 WebView 中均为空实现。 */

declare global {
  interface Window {
    bmatDesktop?: { setLightMode(enabled: boolean): void }
  }
}

export const isDesktop = navigator.userAgent.includes('BMAT-Desktop/1')

export function setDesktopLightMode(enabled: boolean): void {
  if (isDesktop) window.bmatDesktop?.setLightMode(enabled)
}
