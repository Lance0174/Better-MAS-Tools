<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import type { SettingsData } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { errorMessage } from '@/composables/useCommunityApi'
import { isAndroidLocal } from '@/services/android'
import { isDesktop } from '@/services/desktop'
import { createSettingsAutoSave } from './settingsAutoSave'

const { t } = useI18n()
const settings = useSettingsStore()
const draft = ref<SettingsData>({
  ...settings.data,
})
const yunmaToken = computed({
  get: () => draft.value.YunmaToken ?? '',
  set: (value: string) => {
    draft.value.YunmaToken = value
  },
})
const captchaModes = computed(() => [
  { value: 'local', label: t('standalone.captchaLocal') },
  { value: 'local_yunma', label: t('standalone.captchaYunma') },
  { value: 'manual', label: t('standalone.captchaManual') },
])
const themes = computed(() =>
  ['light', 'dark', 'system'].map(value => ({ value, label: t(`standalone.${value}`) }))
)
const reopenOnboarding = () => {
  window.dispatchEvent(new CustomEvent('bmat-open-onboarding'))
}
const autoSave = createSettingsAutoSave({
  getSnapshot: () => draft.value,
  save: next => settings.save(next),
  onFailure: cause => message.error(errorMessage(cause, t('standalone.saveFailed'))),
})
const changed = () => autoSave.changed()
const textChanged = () => autoSave.textChanged()
const textBlurred = () => autoSave.textBlurred()
onBeforeUnmount(autoSave.dispose)
</script>

<template>
  <section class="settings-page">
    <header class="page-toolbar"><h1 class="page-title">{{ t('standalone.settings') }}</h1></header>
    <a-form layout="vertical" :model="draft">
      <a-tabs>
        <a-tab-pane key="captcha" :tab="t('standalone.humanVerification')">
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.captchaScope')"
            class="settings-hint"
          />
          <a-form-item name="CaptchaMode" :label="t('standalone.captchaMode')">
            <a-select v-model:value="draft.CaptchaMode" :options="captchaModes" @change="changed" />
          </a-form-item>
          <a-form-item
            name="YunmaToken"
            :label="t('standalone.yunmaToken')"
            :extra="t('standalone.yunmaKeyHint')"
          >
            <a-input-password v-model:value="yunmaToken" autocomplete="new-password" @update:value="textChanged" @blur="textBlurred" />
          </a-form-item>
          <a-button danger @click="draft.YunmaToken = ''; changed()">{{
            t('standalone.clearYunmaKey')
          }}</a-button>
        </a-tab-pane>
        <a-tab-pane key="preferences" :tab="t('standalone.preferences')">
          <a-form-item
            v-if="!isAndroidLocal"
            name="MasBaseUrl"
            :label="t('standalone.masAddress')"
            :extra="t('standalone.masHint')"
          >
            <a-input
              v-model:value="draft.MasBaseUrl"
              :disabled="!settings.localConnections"
              autocomplete="off"
              @update:value="textChanged"
              @blur="textBlurred"
            />
          </a-form-item>
          <a-form-item name="Theme" :label="t('standalone.theme')"
            ><a-select v-model:value="draft.Theme" :options="themes" class="short-field" @change="changed"
          /></a-form-item>
          <a-form-item name="onboarding" :label="t('standalone.onboardingReopen')" :extra="t('standalone.onboardingReopenHint')">
            <a-button @click="reopenOnboarding">{{ t('standalone.onboardingReopen') }}</a-button>
          </a-form-item>
          <a-form-item
            v-if="isDesktop"
            name="LightMode"
            :label="t('standalone.lightMode')"
            :extra="t('standalone.lightModeHint')"
            ><a-switch v-model:checked="draft.LightMode" @change="changed"
          /></a-form-item>
          <a-form-item name="ActivityEnabled" :label="t('standalone.activityEnabled')"
            ><a-switch v-model:checked="draft.ActivityEnabled" @change="changed"
          /></a-form-item>
          <a-form-item
            name="Proxy"
            v-if="!isAndroidLocal"
            :label="t('standalone.proxy')"
            :extra="t('standalone.proxyHint')"
            ><a-input
              v-model:value="draft.Proxy"
              :disabled="!settings.localConnections"
              autocomplete="off"
              @update:value="textChanged"
              @blur="textBlurred"
          /></a-form-item>
        </a-tab-pane>
        <a-tab-pane key="automation" :tab="t('standalone.automation')">
          <a-form-item
            name="MiyousheBbsEnabled"
            :label="t('standalone.miyousheBbs')"
            :extra="t('standalone.miyousheBbsHint')"
          >
            <a-switch v-model:checked="draft.MiyousheBbsEnabled" @change="changed" />
          </a-form-item>
          <a-alert
            type="info"
            show-icon
            :message="
              t(isAndroidLocal ? 'standalone.androidAutomationHint' : 'standalone.automationHint')
            "
            class="settings-hint"
          />
          <a-form-item name="Enabled" :label="t('standalone.autoEnabled')"
            ><a-switch v-model:checked="draft.Enabled" @change="changed"
          /></a-form-item>
          <a-form-item
            name="RunOnStartup"
            :label="t(isAndroidLocal ? 'standalone.androidRunOnOpen' : 'standalone.runOnStartup')"
            ><a-switch v-model:checked="draft.RunOnStartup" :disabled="!draft.Enabled" @change="changed"
          /></a-form-item>
          <a-form-item
            v-if="!isAndroidLocal"
            name="ScheduledRun"
            :label="t('standalone.scheduledRun')"
            ><a-switch v-model:checked="draft.ScheduledRun" :disabled="!draft.Enabled" @change="changed"
          /></a-form-item>
          <a-form-item
            v-if="!isAndroidLocal"
            name="ScheduledTime"
            :label="t('standalone.scheduledTime')"
            ><a-input
              v-model:value="draft.ScheduledTime"
              type="time"
              :disabled="!draft.Enabled || !draft.ScheduledRun"
              class="short-field"
              @update:value="textChanged"
              @blur="textBlurred"
          /></a-form-item>
        </a-tab-pane>
        <a-tab-pane key="cloud" :tab="t('standalone.cloudMode')">
          <a-alert type="info" show-icon :message="t('standalone.cloudModeHint')" class="settings-hint" />
          <a-form-item name="CloudMode" :label="t('standalone.cloudModeEnabled')">
            <a-switch v-model:checked="draft.CloudMode" @change="changed" />
          </a-form-item>
          <a-form-item
            name="CloudBaseUrl"
            :label="t('standalone.cloudBaseUrl')"
            :extra="t('standalone.cloudBaseUrlHint')"
          >
            <a-input v-model:value="draft.CloudBaseUrl" :disabled="!draft.CloudMode" placeholder="https://community.example.workers.dev" autocomplete="off" @update:value="textChanged" @blur="textBlurred" />
          </a-form-item>
          <a-form-item
            name="CloudPassword"
            :label="t('standalone.cloudPassword')"
            :extra="t('standalone.cloudPasswordHint')"
          >
            <a-input-password v-model:value="draft.CloudPassword" :disabled="!draft.CloudMode" autocomplete="new-password" @update:value="textChanged" @blur="textBlurred" />
          </a-form-item>
          <a-form-item name="RelayEnabled" :label="t('standalone.relay.settingsTitle')" :extra="t('standalone.relay.settingsHint')">
            <a-switch v-model:checked="draft.RelayEnabled" :disabled="!draft.CloudMode" @change="changed" />
          </a-form-item>
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
