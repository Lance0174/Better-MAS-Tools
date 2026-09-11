import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SettingsData } from '@/api'
import { useCommunityApi } from '@/composables/useCommunityApi'

export const useSettingsStore = defineStore('settings', () => {
  const data = ref<SettingsData | null>(null)
  const localConnections = ref(true)
  const api = useCommunityApi()
  const load = async () => {
    const response = await api.getSettings()
    data.value = response.data
    localConnections.value = response.localConnections !== false
  }
  const save = async (next: SettingsData) => {
    await api.updateSettings(next)
    await load()
  }
  return { data, localConnections, load, save }
})
