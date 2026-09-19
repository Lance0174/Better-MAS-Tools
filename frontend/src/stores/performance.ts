import { computed, onScopeDispose, ref } from 'vue'
import { defineStore } from 'pinia'

export const usePerformanceStore = defineStore('performance', () => {
  const background = ref(document.hidden)
  const onVisibility = () => {
    background.value = document.hidden
  }
  document.addEventListener('visibilitychange', onVisibility)
  onScopeDispose(() => document.removeEventListener('visibilitychange', onVisibility))
  const isLowPower = computed(() => background.value)
  return { isLowPower }
})
