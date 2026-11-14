import { computed, nextTick, onScopeDispose, ref, watch, type Ref } from 'vue'
import type { AccountOut, AccountRoleOut, GachaRecord } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'

/** 明日方舟已登录账号 → 对应角色 → 官方授权；凭据只由后端读取。 */
export function useOfficialGacha(
  game: Ref<GachaRecord['game']>,
  accounts: Ref<AccountOut[]>,
  fallback: () => string
) {
  const api = useCommunityApi()
  const accountId = ref('')
  const playerUid = ref('')
  const roles = ref<AccountRoleOut[]>([])
  const loading = ref(false)
  const issue = ref('')
  let generation = 0
  let preparation = 0
  let pending: { key: string; request: Promise<void> } | null = null
  const options = computed(() =>
    accounts.value
      .filter(item => game.value === 'arknights' && item.data.SklandToken)
      .map(item => ({ value: item.uid, label: item.data.Name }))
  )
  const roleOptions = computed(() =>
    roles.value.map(role => ({
      value: role.roleUid,
      label: [role.roleName, role.roleUid, role.server].filter(Boolean).join(' · '),
    }))
  )
  const loadRoles = async () => {
    const key = `${game.value}:${accountId.value}`
    if (pending?.key === key) return pending.request
    pending = null
    const version = ++generation
    roles.value = []
    playerUid.value = ''
    issue.value = ''
    loading.value = false
    if (!accountId.value || game.value !== 'arknights') return
    loading.value = true
    const request = (async () => {
      try {
        const response = await api.listAccountRoles(accountId.value, '森空岛')
        if (version !== generation) return
        roles.value = (response.data ?? []).filter(role => role.game === '明日方舟')
        issue.value = (response.warnings ?? []).join('；')
        if (roles.value.length === 1) playerUid.value = roles.value[0]!.roleUid
      } catch (cause) {
        if (version === generation) issue.value = errorMessage(cause, fallback())
      } finally {
        if (version === generation) loading.value = false
        if (version === generation) pending = null
      }
    })()
    pending = { key, request }
    return request
  }
  watch(
    [game, accountId],
    () => {
      void loadRoles()
    },
    { flush: 'sync' }
  )
  watch(
    options,
    choices => {
      if (!choices.some(item => item.value === accountId.value))
        accountId.value = choices[0]?.value ?? ''
    },
    { immediate: true, flush: 'sync' }
  )
  const prepare = async () => {
    if (game.value !== 'arknights') return
    const version = ++preparation
    const requestedGame = game.value
    const response = await api.listAccounts()
    if (version !== preparation || game.value !== requestedGame) return
    accounts.value = response.data
    // 同一账号重复打开时重新确认角色；保留仍属于它的选择。
    const selected = playerUid.value
    const selectedAccount = accountId.value
    await nextTick()
    await loadRoles()
    if (
      version !== preparation ||
      game.value !== requestedGame ||
      accountId.value !== selectedAccount
    )
      return
    if (roles.value.some(role => role.roleUid === selected)) playerUid.value = selected
  }
  onScopeDispose(() => {
    generation++
    preparation++
  })
  return {
    accountId,
    playerUid,
    roles,
    options,
    roleOptions,
    loading,
    issue,
    prepare,
  }
}
