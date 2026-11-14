<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  HolderOutlined,
  PlusOutlined,
  ReloadOutlined,
  UserOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons-vue'
import { useRoute } from 'vue-router'
import { useMobileUi } from '@/composables/useMobileUi'
import { confirmDialog } from '@/utils/confirmDialog'
import draggable from 'vuedraggable'
import type { AccountOut, StatusOut } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { usePerformanceStore } from '@/stores/performance'
import AccountEditor from './components/AccountEditor.vue'
import SignResults from './components/SignResults.vue'
import MiyousheVerificationPanel from './MiyousheVerificationPanel.vue'

const { t } = useI18n()
const api = useCommunityApi()
const route = useRoute()
const mobile = useMobileUi()
const accountMode = computed(() => route.name === 'Accounts')
const performance = usePerformanceStore()
const accounts = ref<AccountOut[]>([])
const status = ref<StatusOut | null>(null)
const loading = ref(false)
const adding = ref(false)
const signing = ref(false)
const ordering = ref(false)
const error = ref('')
const selected = ref<AccountOut | null>(null)
const editorOpen = ref(false)
const selectedNew = ref(false)
const busy = computed(
  () => signing.value || status.value?.running === true || status.value?.activityRunning === true
)
let timer: ReturnType<typeof setTimeout> | undefined
let alive = true
const fields = [
  { field: 'SklandToken', name: 'skland' },
  { field: 'MiyousheToken', name: 'miyoushe' },
  { field: 'TaygedoToken', name: 'taygedo' },
  { field: 'KuroToken', name: 'kuro' },
] as const

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [accountResponse, statusResponse] = await Promise.all([api.listAccounts(), api.status()])
    if (!alive) return
    accounts.value = accountResponse.data
    status.value = statusResponse
  } catch (cause) {
    error.value = errorMessage(cause, t('standalone.loadFailed'))
  } finally {
    loading.value = false
  }
}
const poll = async () => {
  if (!alive) return
  if (!document.hidden && !loading.value) {
    try {
      status.value = await api.status()
    } catch (cause) {
      error.value = errorMessage(cause, t('standalone.loadFailed'))
    }
  }
  if (alive) timer = setTimeout(poll, performance.isLowPower ? 30000 : 10000)
}
onMounted(async () => {
  await load()
  if (alive) timer = setTimeout(poll, 10000)
})
onUnmounted(() => {
  alive = false
  clearTimeout(timer)
})
const edit = (account: AccountOut, newlyCreated = false) => {
  selected.value = account
  selectedNew.value = newlyCreated
  editorOpen.value = true
}
const add = async () => {
  adding.value = true
  try {
    const response = await api.createAccount()
    await load()
    edit(response.data, true)
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.saveFailed')))
  } finally {
    adding.value = false
  }
}
const remove = (account: AccountOut) =>
  confirmDialog({
    title: t('standalone.deleteTitle'),
    content: t('standalone.deleteHint'),
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api.deleteAccount(account.uid)
        await load()
      } catch (cause) {
        message.error(errorMessage(cause, t('standalone.saveFailed')))
        throw cause
      }
    },
  })
const reorder = async () => {
  ordering.value = true
  try {
    await api.reorderAccounts(accounts.value.map(account => account.uid))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.saveFailed')))
    await load()
  } finally {
    ordering.value = false
  }
}
const move = async (index: number, offset: number) => {
  const next = index + offset
  if (next < 0 || next >= accounts.value.length) return
  const [item] = accounts.value.splice(index, 1)
  accounts.value.splice(next, 0, item!)
  await reorder()
}
const sign = async () => {
  signing.value = true
  try {
    await api.sign()
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.signFailed')))
  } finally {
    signing.value = false
    await load()
  }
}
</script>

<template>
  <section class="community-sign-page" :class="{ 'accounts-page': accountMode }">
    <header class="page-toolbar">
      <p>{{ t(accountMode ? 'standalone.ui.accountSubtitle' : 'standalone.ui.signSubtitle') }}</p>
      <a-space wrap
        ><a-button :loading="loading" @click="load"
          ><ReloadOutlined />{{ t('standalone.refresh') }}</a-button
        >
        <a-button
          v-if="accountMode"
          class="add-account"
          type="primary"
          :loading="adding"
          :disabled="busy"
          @click="add"
          ><PlusOutlined />{{ t('standalone.addAccount') }}</a-button
        >
        <template v-else
          ><router-link to="/accounts"
            ><a-button>{{ t('standalone.accountList') }}</a-button></router-link
          ><a-button type="primary" :loading="busy" :disabled="!accounts.length" @click="sign">{{
            t('standalone.signNow')
          }}</a-button></template
        >
      </a-space>
    </header>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
    <template v-if="accountMode">
      <a-spin :spinning="loading">
        <a-empty
          v-if="!accounts.length && !loading"
          class="page-state"
          :description="t('standalone.noAccounts')"
        />
        <draggable
          v-else
          v-model="accounts"
          item-key="uid"
          handle=".account-handle"
          :disabled="busy || ordering || mobile"
          :animation="performance.isLowPower ? 0 : 150"
          class="account-list"
          @end="reorder"
        >
          <template #item="{ element: account, index }"
            ><article
              class="account-row"
              :class="{ selected: editorOpen && selected?.uid === account.uid }"
            >
              <div class="account-heading">
                <span class="account-avatar">{{ account.data.Name?.slice(0, 1) || '?' }}</span>
                <div class="account-info">
                  <h2>{{ account.data.Name }}</h2>
                  <p>
                    {{
                      t(account.data.Enabled ? 'standalone.accountEnabled' : 'standalone.disabled')
                    }}
                  </p>
                </div>
                <HolderOutlined
                  v-if="!mobile"
                  class="account-handle"
                  :title="t('gamesign.activity.drag')"
                /><UserOutlined v-else />
              </div>
              <div class="platforms">
                <span
                  v-for="item in fields"
                  :key="item.field"
                  :class="{ configured: account.data[item.field] }"
                  >{{ t(`standalone.${item.name}`)
                  }}<small>{{
                    t(account.data[item.field] ? 'standalone.ui.bound' : 'standalone.ui.unbound')
                  }}</small></span
                >
              </div>
              <footer>
                <div class="account-order">
                  <template v-if="mobile"
                    ><a-button
                      type="text"
                      :disabled="busy || ordering || index === 0"
                      :aria-label="t('standalone.ui.moveUp')"
                      @click="move(index, -1)"
                      ><ArrowUpOutlined /></a-button
                    ><a-button
                      type="text"
                      :disabled="busy || ordering || index === accounts.length - 1"
                      :aria-label="t('standalone.ui.moveDown')"
                      @click="move(index, 1)"
                      ><ArrowDownOutlined /></a-button
                  ></template>
                </div>
                <a-space
                  ><a-button type="text" danger :disabled="busy" @click="remove(account)">{{
                    t('standalone.delete')
                  }}</a-button
                  ><a-button :disabled="busy" @click="edit(account)">{{
                    t('standalone.edit')
                  }}</a-button></a-space
                >
              </footer>
            </article></template
          >
        </draggable>
      </a-spin>
    </template>
    <template v-else
      ><MiyousheVerificationPanel :busy="busy" @completed="load" /><SignResults
        :results="status?.results ?? {}"
        :today="status?.today ?? ''"
    /></template>
    <AccountEditor
      :open="editorOpen"
      :account="selected"
      :suggest-name="selectedNew"
      @close="editorOpen = false"
      @saved="load"
    />
  </section>
</template>

<style scoped>
.page-toolbar p {
  margin: 0;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.account-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}
.account-row {
  padding: 22px;
  border: 1px solid transparent;
  border-radius: 24px;
  background: var(--ant-color-bg-container);
  min-width: 0;
}
.account-row.selected {
  border-color: var(--ant-color-primary);
}
.account-heading {
  display: flex;
  align-items: center;
  gap: 13px;
}
.account-avatar {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  border-radius: 18px;
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
  font-size: 20px;
  flex-shrink: 0;
}
.account-info {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.account-info h2 {
  margin: 0 0 5px;
  font-size: 17px;
  font-weight: 650;
}
.account-info p {
  margin: 0;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.account-heading > .anticon {
  color: var(--ant-color-text-tertiary);
}
.account-handle {
  cursor: grab;
}
.platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 20px 0 16px;
}
.platforms > span {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background: var(--ant-color-fill-quaternary);
  border-radius: 10px;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.platforms small {
  font-size: 10px;
  opacity: 0.7;
}
.platforms .configured {
  color: var(--ant-color-link);
  background: var(--ant-color-primary-bg);
}
.account-row footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 13px;
  border-top: 1px solid var(--ant-color-border-secondary);
}
.account-order {
  display: flex;
}
@media (max-width: 700px) {
  .account-list {
    grid-template-columns: 1fr;
    gap: 13px;
  }
  .account-row {
    padding: 19px;
  }
  .page-toolbar {
    align-items: stretch;
  }
  .page-toolbar > .ant-space {
    width: 100%;
  }
  .page-toolbar :deep(.ant-space-item:last-child) {
    margin-left: auto;
  }
}
</style>
