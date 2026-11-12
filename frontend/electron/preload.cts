/** 隔离预加载：仅暴露轻量模式与受限的官方更新能力。 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('bmatDesktop', {
  setLightMode: (enabled: boolean) => ipcRenderer.send('bmat-light-mode', enabled),
  downloadUpdate: (asset: unknown) => ipcRenderer.invoke('bmat-update-download', asset),
  installUpdate: () => ipcRenderer.invoke('bmat-update-install'),
})
