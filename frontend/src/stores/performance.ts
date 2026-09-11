import { computed, onScopeDispose, ref } from 'vue'
import { defineStore } from 'pinia'
import { useSettingsStore } from './settings'

export const usePerformanceStore = defineStore('performance', () => {
  const settings = useSettingsStore()
  const background = ref(document.hidden)
  const onVisibility = () => {
    background.value = document.hidden
  }
  document.addEventListener('visibilitychange', onVisibility)
  onScopeDispose(() => document.removeEventListener('visibilitychange', onVisibility))
  const lowPerformanceMode = computed(() => settings.data?.LowPerformanceMode === true)
  const isLowPower = computed(() => lowPerformanceMode.value || background.value)
  return { isLowPower, lowPerformanceMode }
})
