import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { WikiCalendarGameOut } from '@/api'
import { useCalendarApi } from '@/composables/useCalendarApi'

export const useCalendarStore = defineStore('calendar', () => {
  const games = ref<WikiCalendarGameOut[]>([])
  const loading = ref(false)
  const failure = ref<unknown>(null)
  const notice = ref('')
  const api = useCalendarApi()
  let pending: Promise<void> | null = null
  function load() {
    if (pending) return pending
    loading.value = true
    failure.value = null
    pending = api
      .all()
      .then(response => {
        games.value = response.data ?? []
        notice.value = response.message ?? ''
      })
      .catch(cause => {
        failure.value = cause
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }
  return { games, loading, failure, notice, load }
})
