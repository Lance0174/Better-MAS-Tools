<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import type { AccountData, AccountOut } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { getLogger } from '@/utils/logger'
import QrLoginModal from '../QrLoginModal.vue'
import KuroSmsLoginModal from '../KuroSmsLoginModal.vue'
import { useQrLogin, type QrLoginProvider } from '../useQrLogin'

const props = defineProps<{ open: boolean; account: AccountOut | null }>()
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
const tabs = [
  { key: 'MiyousheToken', label: 'miyoushe' },
  { key: 'SklandToken', label: 'skland' },
  { key: 'TaygedoToken', label: 'taygedo' },
  { key: 'KuroToken', label: 'kuro' },
] as const
const dirty = computed(() => JSON.stringify(draft.value) !== baseline.value)

watch(
  () => [props.open, props.account?.uid],
  () => {
    if (props.open && props.account) {
      draft.value = { ...props.account.data }
      baseline.value = JSON.stringify(draft.value)
    }
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
    credentials.password = ''
    emit('close')
  }
  if (dirty.value || credentials.password) {
    Modal.confirm({
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
  <a-drawer
    :open="open"
    :title="t('standalone.editAccount')"
    :width="620"
    :closable="!saving && !loggingIn"
    :mask-closable="!saving && !loggingIn"
    @close="close"
  >
    <a-form layout="vertical" :model="draft" :disabled="saving || loggingIn">
      <a-form-item name="Name" :label="t('standalone.accountName')" required
        ><a-input v-model:value="draft.Name" :maxlength="80"
      /></a-form-item>
      <a-form-item name="Enabled" :label="t('standalone.accountEnabled')"
        ><a-switch v-model:checked="draft.Enabled"
      /></a-form-item>
      <a-alert
        type="info"
        show-icon
        :message="t('standalone.credentialHint')"
        class="credential-hint"
      />
      <a-tabs>
        <a-tab-pane v-for="tab in tabs" :key="tab.key" :tab="t(`standalone.${tab.label}`)">
          <a-button
            v-if="tab.key === 'KuroToken'"
            class="credential-hint"
            @click="kuroOpen = true"
            >{{ t('standalone.kuroSmsLogin') }}</a-button
          >
          <a-form-item
            :name="tab.key"
            :label="t('standalone.token')"
            :extra="t('standalone.tokenHint')"
            ><a-textarea
              v-model:value="draft[tab.key]"
              :rows="4"
              autocomplete="off"
              spellcheck="false"
          /></a-form-item>
          <a-button
            v-if="tab.key === 'MiyousheToken' || tab.key === 'SklandToken'"
            @click="startQr(tab.key === 'SklandToken' ? 'skland' : 'miyoushe')"
            >{{ t('standalone.qrLogin') }}</a-button
          >
          <a-form-item
            v-if="tab.key === 'MiyousheToken'"
            name="CloudGenshinToken"
            :label="t('standalone.cloudToken')"
            :extra="t('standalone.cloudHint')"
            class="cloud-token"
            ><a-input-password v-model:value="draft.CloudGenshinToken" autocomplete="off"
          /></a-form-item>
          <template v-if="tab.key === 'TaygedoToken'">
            <a-divider orientation="left">{{ t('standalone.passwordLogin') }}</a-divider>
            <a-form-item :label="t('standalone.loginAccount')"
              ><a-input v-model:value="credentials.phone" autocomplete="off"
            /></a-form-item>
            <a-form-item :label="t('standalone.password')" :extra="t('standalone.loginHint')"
              ><a-input-password v-model:value="credentials.password" autocomplete="new-password"
            /></a-form-item>
            <a-button :loading="loggingIn" @click="passwordLogin">{{
              t('standalone.login')
            }}</a-button>
          </template>
        </a-tab-pane>
      </a-tabs>
    </a-form>
    <template #footer
      ><a-space
        ><a-button :disabled="saving || loggingIn" @click="close">{{
          t('standalone.cancel')
        }}</a-button
        ><a-button type="primary" :loading="saving" :disabled="loggingIn" @click="save">{{
          t('standalone.save')
        }}</a-button></a-space
      ></template
    >
  </a-drawer>
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
.credential-hint {
  margin-bottom: 16px;
}
.cloud-token {
  margin-top: 24px;
}
</style>
