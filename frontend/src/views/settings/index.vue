<script setup lang="ts">
import { confirmDialog } from '@/utils/confirmDialog'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ChoiceSelect from '@/components/ChoiceSelect.vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import type { SettingsData } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { errorMessage } from '@/composables/useCommunityApi'
import { isAndroidLocal } from '@/services/android'
import { isDesktop } from '@/services/desktop'
import { applyLightModeChange } from './settingsLightMode'
import { createSettingsAutoSave } from './settingsAutoSave'
import SoftwareUpdate from './SoftwareUpdate.vue'

const { t } = useI18n()
const settings = useSettingsStore()
const route = useRoute()
const section = ref('appearance')
watch(
  () => route.query.section,
  value => {
    section.value = value === 'updates' ? 'updates' : 'appearance'
  },
  { immediate: true }
)
const androidBuild = import.meta.env.BMAT_ANDROID
const draft = ref<SettingsData>({
  ...settings.data,
})
// 壳层也提供主题切换，避免设置草稿在下一次自动保存时写回旧主题。
watch(
  () => settings.data?.Theme,
  value => {
    if (value) draft.value.Theme = value
  },
  { flush: 'sync' }
)
const themePreference = computed({
  get: () => settings.data?.Theme ?? 'system',
  set: (value: SettingsData['Theme']) => {
    void settings
      .patch({ Theme: value })
      .catch(cause => message.error(errorMessage(cause, t('standalone.saveFailed'))))
  },
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
  (['light', 'dark', 'system'] as const).map(value => ({ value, label: t(`standalone.${value}`) }))
)
const reopenOnboarding = () => {
  window.dispatchEvent(new CustomEvent('bmat-open-onboarding'))
}
const autoSave = createSettingsAutoSave({
  getSnapshot: () => ({ ...draft.value, Theme: settings.data?.Theme }),
  save: next => settings.save(next),
  onFailure: cause => message.error(errorMessage(cause, t('standalone.saveFailed'))),
})
const changed = () => autoSave.changed()
const clearYunmaKey = () => {
  draft.value.YunmaToken = ''
  changed()
}
const lightModeConfirmPending = ref(false)
// 轻量模式开启前确认：开启后窗口会被销毁、任务栏不再显示，只能从托盘或再次启动程序唤回。
const lightModeChanged = (enabled: boolean) => {
  if (lightModeConfirmPending.value) return
  lightModeConfirmPending.value = true
  void applyLightModeChange(enabled, {
    setEnabled: value => {
      draft.value.LightMode = value
    },
    confirm: () =>
      new Promise<boolean>(resolve => {
        confirmDialog({
          title: t('standalone.lightModeConfirmTitle'),
          content: t('standalone.lightModeConfirmContent'),
          okText: t('standalone.lightModeConfirmOk'),
          cancelText: t('standalone.lightModeConfirmCancel'),
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        })
      }),
    onChange: changed,
  }).finally(() => {
    lightModeConfirmPending.value = false
  })
}
const textChanged = () => autoSave.textChanged()
const textBlurred = () => autoSave.textBlurred()
onBeforeUnmount(autoSave.dispose)
</script>

<template>
  <section class="settings-page">
    <a-form layout="vertical" :model="draft">
      <a-tabs v-model:active-key="section">
        <a-tab-pane key="appearance" :tab="t('standalone.ui.appearance')">
          <a-form-item name="Theme" :label="t('standalone.theme')"
            ><ChoiceSelect v-model:value="themePreference" :options="themes" class="short-field"
          /></a-form-item>
          <a-form-item
            name="GlassEffect"
            :label="t('standalone.glassEffect')"
            :extra="t('standalone.glassEffectHint')"
            ><a-switch v-model:checked="draft.GlassEffect" @change="changed"
          /></a-form-item>
          <a-form-item
            name="onboarding"
            :label="t('standalone.onboardingReopen')"
            :extra="t('standalone.onboardingReopenHint')"
          >
            <a-button @click="reopenOnboarding">{{ t('standalone.onboardingReopen') }}</a-button>
          </a-form-item>
        </a-tab-pane>
        <a-tab-pane key="updates" :tab="t('standalone.softwareUpdate')"
          ><SoftwareUpdate
        /></a-tab-pane>
        <a-tab-pane key="captcha" :tab="t('standalone.humanVerification')">
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.captchaScope')"
            class="settings-hint"
          />
          <a-form-item name="CaptchaMode" :label="t('standalone.captchaMode')">
            <ChoiceSelect
              v-model:value="draft.CaptchaMode"
              :options="captchaModes"
              @change="changed"
            />
          </a-form-item>
          <a-form-item
            name="YunmaToken"
            :label="t('standalone.yunmaToken')"
            :extra="t('standalone.yunmaKeyHint')"
          >
            <a-input-password
              v-model:value="yunmaToken"
              autocomplete="new-password"
              @update:value="textChanged"
              @blur="textBlurred"
            />
          </a-form-item>
          <a-button danger @click="clearYunmaKey">{{ t('standalone.clearYunmaKey') }}</a-button>
        </a-tab-pane>
        <a-tab-pane key="preferences" :tab="t('standalone.ui.preferences')">
          <a-form-item
            v-if="!isAndroidLocal && !androidBuild"
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
          <a-form-item
            v-if="isDesktop"
            name="LightMode"
            :label="t('standalone.lightMode')"
            :extra="t('standalone.lightModeHint')"
            ><a-switch
              v-model:checked="draft.LightMode"
              :disabled="lightModeConfirmPending"
              @change="lightModeChanged"
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
            ><a-switch
              v-model:checked="draft.RunOnStartup"
              :disabled="!draft.Enabled"
              @change="changed"
          /></a-form-item>
          <a-form-item
            v-if="!isAndroidLocal"
            name="ScheduledRun"
            :label="t('standalone.scheduledRun')"
            ><a-switch
              v-model:checked="draft.ScheduledRun"
              :disabled="!draft.Enabled"
              @change="changed"
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
        <a-tab-pane
          v-if="!isAndroidLocal && !androidBuild"
          key="cloud"
          :tab="t('standalone.cloudMode')"
        >
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.cloudModeHint')"
            class="settings-hint"
          />
          <a-form-item name="CloudMode" :label="t('standalone.cloudModeEnabled')">
            <a-switch v-model:checked="draft.CloudMode" @change="changed" />
          </a-form-item>
          <a-form-item
            name="CloudBaseUrl"
            :label="t('standalone.cloudBaseUrl')"
            :extra="t('standalone.cloudBaseUrlHint')"
          >
            <a-input
              v-model:value="draft.CloudBaseUrl"
              :disabled="!draft.CloudMode"
              placeholder="https://community.example.com"
              autocomplete="off"
              @update:value="textChanged"
              @blur="textBlurred"
            />
          </a-form-item>
          <a-form-item
            name="CloudPassword"
            :label="t('standalone.cloudPassword')"
            :extra="t('standalone.cloudPasswordHint')"
          >
            <a-input-password
              v-model:value="draft.CloudPassword"
              :disabled="!draft.CloudMode"
              autocomplete="new-password"
              @update:value="textChanged"
              @blur="textBlurred"
            />
          </a-form-item>
          <a-form-item
            name="RelayEnabled"
            :label="t('standalone.relay.settingsTitle')"
            :extra="t('standalone.relay.settingsHint')"
          >
            <a-switch
              v-model:checked="draft.RelayEnabled"
              :disabled="!draft.CloudMode"
              @change="changed"
            />
          </a-form-item>
        </a-tab-pane>
      </a-tabs>
    </a-form>
  </section>
</template>

<style scoped>
.settings-page {
  max-width: 1000px;
  margin: auto;
}
.settings-page :deep(.ant-tabs-tabpane) {
  background: var(--ant-color-bg-container);
  border-radius: 24px;
  padding: 24px;
}
.settings-page :deep(.ant-form-item) {
  margin-bottom: 24px;
}
.short-field {
  width: 200px;
}
.settings-hint {
  margin-bottom: 20px;
}
@media (max-width: 700px) {
  .settings-page :deep(.ant-tabs-tabpane) {
    padding: 20px;
  }
  .short-field {
    width: 100%;
  }
}
</style>
