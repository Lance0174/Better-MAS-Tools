import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SettingsData } from '@/api'
import { useCommunityApi } from '@/composables/useCommunityApi'

export const useSettingsStore = defineStore('settings', () => {
  const data = ref<SettingsData | null>(null)
  const localConnections = ref(true)
  const api = useCommunityApi()
  let confirmed: SettingsData | null = null
  let loadVersion = 0
  let nextId = 0
  let queue = Promise.resolve()
  const pending = new Map<number, Partial<SettingsData>>()
  const publish = () => {
    data.value = confirmed ? Object.assign({ ...confirmed }, ...pending.values()) : null
  }
  const load = async () => {
    const version = ++loadVersion
    const response = await api.getSettings()
    if (version !== loadVersion) return
    confirmed = response.data
    localConnections.value = response.localConnections !== false
    publish()
  }
  // 全局外观按钮与设置页共用同一保存队列；仅合并本次更改的字段。
  const patch = (fields: Partial<SettingsData>) => {
    const id = ++nextId
    pending.set(id, { ...fields })
    loadVersion++
    publish()
    const task = queue.catch(() => {}).then(async () => {
      loadVersion++
      await api.updateSettings({ ...confirmed, ...fields })
      const response = await api.getSettings()
      loadVersion++
      confirmed = response.data
      localConnections.value = response.localConnections !== false
    }).finally(() => {
      pending.delete(id)
      publish()
    })
    queue = task
    return task
  }
  const save = (next: SettingsData) => {
    const changed = Object.fromEntries(
      Object.entries(next).filter(([key, value]) => value !== data.value?.[key as keyof SettingsData])
    ) as Partial<SettingsData>
    return Object.keys(changed).length ? patch(changed) : Promise.resolve()
  }
  return { data, localConnections, load, save, patch }
})
