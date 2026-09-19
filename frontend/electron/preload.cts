/** 沙箱预加载：仅暴露轻量模式开关同步，不给页面任何系统能力。 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('bmatDesktop', {
  setLightMode: (enabled: boolean) => ipcRenderer.send('bmat-light-mode', enabled),
})
