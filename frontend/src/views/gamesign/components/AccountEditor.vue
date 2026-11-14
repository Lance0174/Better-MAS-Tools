<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import type { AccountData, AccountOut } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { getLogger } from '@/utils/logger'
import AdaptivePanel from '@/components/AdaptivePanel.vue'
import ChoiceSelect from '@/components/ChoiceSelect.vue'
import { confirmDialog } from '@/utils/confirmDialog'
import QrLoginModal from '../QrLoginModal.vue'
import KuroSmsLoginModal from '../KuroSmsLoginModal.vue'
import { useQrLogin, type QrLoginProvider } from '../useQrLogin'

const props = defineProps<{ open: boolean; account: AccountOut | null; suggestName?: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()
const api = useCommunityApi()
const draft = ref<AccountData>({})
const baseline = ref('')
const saving = ref(false)
const loggingIn = ref(false)
const credentials = reactive({ phone: '', password: '' })
const provider = ref<QrLoginProvider>('miyoushe')
const kuroOpen = ref(false)
const passwordOpen = ref(false)
const advancedOpen = ref<string[]>([])
const nameOptions = ref<{ value: string; label: string }[]>([])
const namesLoading = ref(false)
let nameGeneration = 0
const tabs = [
  { key: 'MiyousheToken', label: 'miyoushe' },
  { key: 'SklandToken', label: 'skland' },
  { key: 'TaygedoToken', label: 'taygedo' },
  { key: 'KuroToken', label: 'kuro' },
] as const
const dirty = computed(() => JSON.stringify(draft.value) !== baseline.value)
const loadNames = async () => {
  const uid = props.account?.uid
  const version = ++nameGeneration
  if (!uid || !props.open) return
  namesLoading.value = true
  const platforms = [
    ['SklandToken', '森空岛'],
    ['MiyousheToken', '米游社'],
    ['KuroToken', '库街区'],
    ['TaygedoToken', '塔吉多'],
  ] as const
  const responses = await Promise.allSettled(
    platforms
      .filter(([field]) => draft.value[field])
      .map(([, platform]) => api.listAccountRoles(uid, platform))
  )
  if (version !== nameGeneration || !props.open || props.account?.uid !== uid) return
  const choices = responses.flatMap(result =>
    result.status === 'fulfilled'
      ? (result.value.data ?? []).flatMap(role =>
          [...new Set([role.roleName ?? '', role.roleUid].filter(Boolean))].map(value => ({
            value: value.slice(0, 80),
            label: [role.game, value, value === role.roleName ? role.roleUid : role.server]
              .filter(Boolean)
              .join(' · '),
          }))
        )
      : []
  )
  nameOptions.value = [...new Map(choices.map(item => [item.value, item])).values()]
  if (
    props.suggestName &&
    /^(新账号|账号 \d+)$/.test(draft.value.Name ?? '') &&
    nameOptions.value.length
  )
    draft.value.Name = nameOptions.value[0]!.value
  namesLoading.value = false
  if (!choices.length && responses.some(result => result.status === 'rejected'))
    message.warning(t('standalone.accountNamesFailed'))
}
onBeforeUnmount(() => {
  nameGeneration++
})

watch(
  () => [props.open, props.account?.uid],
  () => {
    if (props.open && props.account) {
      draft.value = { ...props.account.data }
      baseline.value = JSON.stringify(draft.value)
      void loadNames()
    } else {
      nameGeneration++
      namesLoading.value = false
    }
    passwordOpen.value = false
    advancedOpen.value = []
    nameOptions.value = []
    // 切换账号或关窗时复位短信登录弹窗，否则给另一个账号重开编辑会沿用它上次的打开状态。
    kuroOpen.value = false
    credentials.phone = ''
    credentials.password = ''
  },
  { immediate: true }
)

const syncCredential = async (
  field: 'MiyousheToken' | 'SklandToken' | 'TaygedoToken' | 'KuroToken',
  isCurrent: () => boolean = () => true
) => {
  const response = await api.listAccounts()
  if (!isCurrent()) return
  const fresh = response.data.find(item => item.uid === props.account?.uid)
  if (fresh) {
    draft.value[field] = fresh.data[field]
    const saved: AccountData = JSON.parse(baseline.value)
    saved[field] = fresh.data[field]
    baseline.value = JSON.stringify(saved)
    emit('saved')
    void loadNames()
  }
}
const qr = useQrLogin({
  getAccountId: () => props.account?.uid,
  onSaved: (_uid, _credential, isCurrent) =>
    syncCredential(provider.value === 'skland' ? 'SklandToken' : 'MiyousheToken', isCurrent),
  provider: () => provider.value,
  logger: getLogger('扫码登录'),
})
const startQr = (next: QrLoginProvider) => {
  provider.value = next
  void qr.start()
}
const close = () => {
  if (saving.value || loggingIn.value) return
  const finish = () => {
    qr.cancel()
    // 与扫码弹窗同样在这里收尾：关抽屉即复位短信登录弹窗，下次打开不会被残留状态顶出来。
    kuroOpen.value = false
    credentials.password = ''
    emit('close')
  }
  if (dirty.value || credentials.password) {
    confirmDialog({
      title: t('standalone.discardTitle'),
      content: t('standalone.discardHint'),
      onOk: finish,
    })
  } else finish()
}
const save = async () => {
  if (!props.account) return
  if (!draft.value.Name?.trim()) {
    message.error(t('standalone.requiredName'))
    return
  }
  saving.value = true
  try {
    await api.updateAccount({
      accountId: props.account.uid,
      data: { ...draft.value, Name: draft.value.Name.trim() },
    })
    baseline.value = JSON.stringify(draft.value)
    // 保存成功后直接 emit('close')，不经过 close()，这里同步复位短信登录弹窗。
    kuroOpen.value = false
    message.success(t('standalone.saved'))
    emit('saved')
    emit('close')
  } catch (error) {
    message.error(errorMessage(error, t('standalone.saveFailed')))
  } finally {
    saving.value = false
  }
}
const passwordLogin = async () => {
  if (!props.account) return
  if (!credentials.phone || !credentials.password) {
    message.error(t('standalone.loginRequired'))
    return
  }
  loggingIn.value = true
  try {
    await api.loginTaygedo(props.account.uid, credentials.phone, credentials.password)
    await syncCredential('TaygedoToken')
    message.success(t('standalone.loginSuccess'))
  } catch (error) {
    message.error(errorMessage(error, t('standalone.saveFailed')))
  } finally {
    credentials.password = ''
    loggingIn.value = false
  }
}
</script>

<template>
  <AdaptivePanel
    :open="open"
    :title="t('standalone.editAccount')"
    :width="620"
    full-mobile
    :busy="saving || loggingIn"
    @close="close"
  >
    <a-form
      :key="`${account?.uid}-${open}`"
      layout="vertical"
      :model="draft"
      :disabled="saving || loggingIn"
      class="account-editor"
    >
      <section class="editor-card">
        <a-form-item name="Name" :label="t('standalone.accountName')" required
          ><a-input v-model:value="draft.Name" :maxlength="80"
        /></a-form-item>
        <a-form-item v-if="nameOptions.length" :label="t('standalone.accountNameFromGame')"
          ><ChoiceSelect
            v-model:value="draft.Name"
            :options="nameOptions"
            :disabled="saving || loggingIn"
            :loading="namesLoading"
            :placeholder="t('standalone.accountChooseName')"
        /></a-form-item>
        <a-button v-else type="link" :loading="namesLoading" @click="loadNames">{{
          t('standalone.accountGetNames')
        }}</a-button>
        <div class="enabled-row">
          <span>{{ t('standalone.accountEnabled') }}</span
          ><a-switch v-model:checked="draft.Enabled" />
        </div>
      </section>
      <h2 class="editor-section-title">{{ t('standalone.ui.accountBindings') }}</h2>
      <p class="editor-subtitle">{{ t('standalone.ui.bindingHint') }}</p>
      <section class="editor-card community-bindings">
        <div v-for="tab in tabs" :key="tab.key" class="binding-row">
          <span class="binding-avatar">{{ t(`standalone.${tab.label}`).slice(0, 1) }}</span>
          <div>
            <strong>{{ t(`standalone.${tab.label}`) }}</strong>
            <p>{{ t(draft[tab.key] ? 'standalone.ui.bound' : 'standalone.ui.unbound') }}</p>
          </div>
          <a-button
            v-if="tab.key === 'MiyousheToken' || tab.key === 'SklandToken'"
            @click="startQr(tab.key === 'SklandToken' ? 'skland' : 'miyoushe')"
            >{{ t(draft[tab.key] ? 'standalone.ui.signAgain' : 'standalone.qrLogin') }}</a-button
          >
          <a-button v-else-if="tab.key === 'KuroToken'" @click="kuroOpen = true">{{
            t(draft[tab.key] ? 'standalone.ui.signAgain' : 'standalone.kuroSmsLogin')
          }}</a-button>
          <a-button v-else @click="passwordOpen = !passwordOpen">{{
            t(draft[tab.key] ? 'standalone.ui.signAgain' : 'standalone.ui.signIn')
          }}</a-button>
        </div>
        <div v-if="passwordOpen" class="password-form">
          <a-form-item :label="t('standalone.loginAccount')"
            ><a-input v-model:value="credentials.phone" autocomplete="off" /></a-form-item
          ><a-form-item :label="t('standalone.password')" :extra="t('standalone.loginHint')"
            ><a-input-password
              v-model:value="credentials.password"
              autocomplete="new-password" /></a-form-item
          ><a-button type="primary" :loading="loggingIn" @click="passwordLogin">{{
            t('standalone.login')
          }}</a-button>
        </div>
      </section>
      <a-collapse v-model:active-key="advancedOpen" ghost class="advanced-credentials"
        ><a-collapse-panel key="credentials" :header="t('standalone.ui.manualCredentials')">
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.credentialHint')"
            class="credential-hint"
          />
          <a-form-item
            v-for="tab in tabs"
            :key="tab.key"
            :name="tab.key"
            :label="t(`standalone.${tab.label}`)"
            :extra="t('standalone.tokenHint')"
            ><a-input-password v-model:value="draft[tab.key]" autocomplete="off" spellcheck="false"
          /></a-form-item>
          <a-form-item
            name="CloudGenshinToken"
            :label="t('standalone.cloudToken')"
            :extra="t('standalone.cloudHint')"
            ><a-input-password v-model:value="draft.CloudGenshinToken" autocomplete="off"
          /></a-form-item> </a-collapse-panel
      ></a-collapse>
    </a-form>
    <template #footer
      ><a-button :disabled="saving || loggingIn" @click="close">{{
        t('standalone.cancel')
      }}</a-button
      ><a-button type="primary" :loading="saving" :disabled="loggingIn" @click="save">{{
        t('standalone.save')
      }}</a-button></template
    >
  </AdaptivePanel>
  <QrLoginModal
    :open="qr.visible.value"
    :status="qr.status.value"
    :status-text="qr.statusText.value"
    :qr-code-data-url="qr.qrCodeDataUrl.value"
    :loading="qr.loading.value"
    :provider="provider"
    @cancel="qr.cancel"
    @retry="qr.start"
  />
  <KuroSmsLoginModal
    :open="kuroOpen && open"
    :account-id="account?.uid"
    @close="kuroOpen = false"
    @saved="syncCredential('KuroToken')"
  />
</template>

<style scoped>
.editor-card {
  background: var(--ant-color-bg-container);
  border-radius: 22px;
  padding: 20px;
}
.enabled-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  margin-top: 16px;
  font-size: 13px;
}
.editor-section-title {
  margin: 26px 4px 7px;
  font-size: 16px;
  font-weight: 650;
}
.editor-subtitle {
  margin: 0 4px 14px;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.community-bindings {
  padding-block: 4px;
}
.binding-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 17px 0;
  border-bottom: 1px solid var(--ant-color-border-secondary);
}
.binding-row:last-of-type {
  border: 0;
}
.binding-avatar {
  display: grid;
  place-items: center;
  width: 37px;
  height: 37px;
  border-radius: 12px;
  color: var(--ant-color-link);
  background: var(--ant-color-primary-bg);
  flex-shrink: 0;
}
.binding-row > div {
  flex: 1;
  min-width: 0;
}
.binding-row strong {
  font-size: 13px;
  font-weight: 600;
}
.binding-row p {
  font-size: 11px;
  color: var(--ant-color-text-secondary);
  margin: 5px 0 0;
}
.binding-row .ant-btn {
  font-size: 12px;
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
  border: 0;
}
.password-form {
  padding: 20px 0;
}
.advanced-credentials {
  margin-top: 20px;
}
.credential-hint {
  margin-bottom: 16px;
}
</style>
