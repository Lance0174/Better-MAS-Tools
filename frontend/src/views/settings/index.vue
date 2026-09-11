<script setup lang="ts">
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import type { SettingsData } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { errorMessage } from '@/composables/useCommunityApi'

const { t } = useI18n()
const settings = useSettingsStore()
const draft = ref<SettingsData>({
  ...settings.data,
})
const original = ref(JSON.stringify(draft.value))
const dirty = computed(() => JSON.stringify(draft.value) !== original.value)
const saving = ref(false)
const yunmaToken = computed({
  get: () => draft.value.YunmaToken ?? '',
  set: (value: string) => { draft.value.YunmaToken = value },
})
const captchaModes = computed(() => [
  { value: 'local', label: t('standalone.captchaLocal') },
  { value: 'local_yunma', label: t('standalone.captchaYunma') },
  { value: 'manual', label: t('standalone.captchaManual') },
])
const themes = computed(() =>
  ['light', 'dark', 'system'].map(value => ({ value, label: t(`standalone.${value}`) }))
)
const save = async () => {
  saving.value = true
  try {
    const next: SettingsData = JSON.parse(JSON.stringify(draft.value))
    await settings.save(next)
    draft.value = { ...settings.data }
    original.value = JSON.stringify(draft.value)
    message.success(t('standalone.saved'))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.saveFailed')))
  } finally {
    saving.value = false
  }
}
onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return new Promise<boolean>(resolve =>
    Modal.confirm({
      title: t('standalone.discardTitle'),
      content: t('standalone.discardHint'),
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  )
})
</script>

<template>
  <section class="settings-page">
    <header class="page-toolbar">
      <h1 class="page-title">{{ t('standalone.settings') }}</h1>
      <a-button type="primary" :loading="saving" :disabled="!dirty" @click="save">{{
        t('standalone.save')
      }}</a-button>
    </header>
    <a-form layout="vertical" :model="draft" :disabled="saving">
      <a-tabs>
        <a-tab-pane key="captcha" :tab="t('standalone.humanVerification')">
          <a-alert type="info" show-icon :message="t('standalone.captchaScope')" class="settings-hint" />
          <a-form-item name="CaptchaMode" :label="t('standalone.captchaMode')">
            <a-select v-model:value="draft.CaptchaMode" :options="captchaModes" />
          </a-form-item>
          <a-form-item name="YunmaToken" :label="t('standalone.yunmaToken')" :extra="t('standalone.yunmaKeyHint')">
            <a-input-password v-model:value="yunmaToken" autocomplete="new-password" />
          </a-form-item>
          <a-button danger @click="draft.YunmaToken = ''">{{ t('standalone.clearYunmaKey') }}</a-button>
        </a-tab-pane>
        <a-tab-pane key="preferences" :tab="t('standalone.preferences')">
          <a-form-item name="MasBaseUrl" :label="t('standalone.masAddress')" :extra="t('standalone.masHint')">
            <a-input v-model:value="draft.MasBaseUrl" :disabled="!settings.localConnections" autocomplete="off" />
          </a-form-item>
          <a-form-item name="Theme" :label="t('standalone.theme')"
            ><a-select v-model:value="draft.Theme" :options="themes" class="short-field"
          /></a-form-item>
          <a-form-item
            name="LowPerformanceMode"
            :label="t('standalone.lowPower')"
            :extra="t('standalone.lowPowerHint')"
            ><a-switch v-model:checked="draft.LowPerformanceMode"
          /></a-form-item>
          <a-form-item name="ActivityEnabled" :label="t('standalone.activityEnabled')"
            ><a-switch v-model:checked="draft.ActivityEnabled"
          /></a-form-item>
          <a-form-item
            name="Proxy"
            :label="t('standalone.proxy')"
            :extra="t('standalone.proxyHint')"
            ><a-input v-model:value="draft.Proxy" :disabled="!settings.localConnections" autocomplete="off"
          /></a-form-item>
        </a-tab-pane>
        <a-tab-pane key="automation" :tab="t('standalone.automation')">
          <a-form-item name="MiyousheBbsEnabled" :label="t('standalone.miyousheBbs')" :extra="t('standalone.miyousheBbsHint')">
            <a-switch v-model:checked="draft.MiyousheBbsEnabled" />
          </a-form-item>
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.automationHint')"
            class="settings-hint"
          />
          <a-form-item name="Enabled" :label="t('standalone.autoEnabled')"
            ><a-switch v-model:checked="draft.Enabled"
          /></a-form-item>
          <a-form-item name="RunOnStartup" :label="t('standalone.runOnStartup')"
            ><a-switch v-model:checked="draft.RunOnStartup" :disabled="!draft.Enabled"
          /></a-form-item>
          <a-form-item name="ScheduledRun" :label="t('standalone.scheduledRun')"
            ><a-switch v-model:checked="draft.ScheduledRun" :disabled="!draft.Enabled"
          /></a-form-item>
          <a-form-item name="ScheduledTime" :label="t('standalone.scheduledTime')"
            ><a-input
              v-model:value="draft.ScheduledTime"
              type="time"
              :disabled="!draft.Enabled || !draft.ScheduledRun"
              class="short-field"
          /></a-form-item>
        </a-tab-pane>
      </a-tabs>
    </a-form>
  </section>
</template>

<style scoped>
.settings-page {
  max-width: 900px;
}
.short-field {
  width: 200px;
}
.settings-hint {
  margin-bottom: 20px;
}
</style>
