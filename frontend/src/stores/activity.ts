import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  useCommunityActivityApi,
  type ActivitySnapshot,
} from '@/views/gamesign/useCommunityActivityApi'
import { groupSnapshots, snapshotKey } from '@/utils/communityDashboard'

/** 首页与独立便笺页共用快照、每游戏账号选择及本次会话内的排序。 */
export const useActivityStore = defineStore('activity', () => {
  const snapshots = ref<ActivitySnapshot[]>([])
  const selected = ref<Record<string, string>>({})
  const order = ref<string[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const failure = ref<unknown>(null)
  const groups = computed(() => groupSnapshots(snapshots.value, order.value))
  const api = useCommunityActivityApi()
  let pending: Promise<void> | null = null
  function current(game: string) {
    const items = groups.value.find(group => group.game === game)?.snapshots ?? []
    return items.find(item => snapshotKey(item) === selected.value[game]) ?? items[0]
  }
  function select(game: string, key: string) {
    if (snapshots.value.some(item => item.game === game && snapshotKey(item) === key))
      selected.value[game] = key
  }
  function load(refresh = false) {
    if (pending) return pending
    loading.value = true
    failure.value = null
    pending = api
      .queryActivity(null, refresh)
      .then(data => {
        snapshots.value = data
        // 被删除的角色不能重新出现；保留仍存在的选择，失效时回到该游戏首个可用账号。
        for (const group of groups.value)
          selected.value[group.game] = snapshotKey(current(group.game)!)
        for (const game of Object.keys(selected.value))
          if (!groups.value.some(group => group.game === game)) delete selected.value[game]
      })
      .catch(cause => {
        failure.value = cause
      })
      .finally(() => {
        loaded.value = true
        loading.value = false
        pending = null
      })
    return pending
  }
  return { snapshots, selected, order, groups, loading, loaded, failure, current, select, load }
})
