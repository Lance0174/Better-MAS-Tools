<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { connectSession, LoginRequiredError } from '@/services/session'
import { errorMessage } from '@/composables/useCommunityApi'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/composables/useTheme'
import { useOnboarding } from '@/composables/useOnboarding'
import { isAndroidLocal, markAndroidReady, retryAndroidEngine } from '@/services/android'
import { setDesktopLightMode } from '@/services/desktop'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import AppNavigation from '@/components/AppNavigation.vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { BulbOutlined } from '@ant-design/icons-vue'

const { t } = useI18n()
const route = useRoute()
const settings = useSettingsStore()
const { themeConfig, isDark } = useTheme()
const themeSaving = ref(false)
const ready = ref(false)
const failed = ref(false)
const loading = ref(false)
const loginRequired = ref(false)
const password = ref('')
const loginError = ref('')
const startupStage = ref('')
const {
  open: onboardingOpen,
  show: openOnboarding,
  hide: closeOnboarding,
  complete: completeOnboarding,
  skip: skipOnboarding,
  maybeShow: maybeOpenOnboarding,
} = useOnboarding({
  isDone: () => settings.data?.OnboardingDismissed === true,
  saveDone: async () => {
    if (settings.data) await settings.save({ ...settings.data, OnboardingDismissed: true })
  },
  onFailure: cause => message.error(errorMessage(cause, t('standalone.onboardingSaveFailed'))),
})
// 设置页“重新查看引导”通过此事件重开首启向导，不影响“已跳过”标记。
window.addEventListener('bmat-open-onboarding', openOnboarding)
const pageTitle = computed(() => t(String(route.meta.title || 'standalone.home')))
const toggleTheme = async () => {
  if (!settings.data || themeSaving.value) return
  themeSaving.value = true
  try {
    await settings.save({ ...settings.data, Theme: isDark.value ? 'light' : 'dark' })
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.saveFailed')))
  } finally {
    themeSaving.value = false
  }
}
// 轻量模式开关同步给桌面壳（托盘驻留/窗口销毁）；非桌面端为空实现。
watch(
  () => settings.data?.LightMode,
  enabled => {
    if (enabled !== undefined) setDesktopLightMode(enabled)
  }
)
const connect = async () => {
  if (loading.value) return
  if (isAndroidLocal) retryAndroidEngine()
  loading.value = true
  failed.value = false
  try {
    await connectSession(password.value)
    await settings.load()
    ready.value = true
    markAndroidReady()
    maybeOpenOnboarding()
  } catch (cause) {
    if (cause instanceof LoginRequiredError) loginRequired.value = true
    else {
      failed.value = true
      loginError.value = errorMessage(cause, t('standalone.connectionFailed'))
    }
  } finally {
    password.value = ''
    loading.value = false
  }
}
const resetEngine = (event: Event) => {
  ready.value = false
  failed.value = true
  loginError.value = (event as CustomEvent<string>).detail || t('standalone.connectionFailed')
}
const updateStartupStage = (event: Event) => {
  startupStage.value = (event as CustomEvent<string>).detail
}
onMounted(() => {
  window.addEventListener('bmat-engine-reset', resetEngine)
  window.addEventListener('bmat-engine-stage', updateStartupStage)
  void connect()
})
onBeforeUnmount(() => {
  window.removeEventListener('bmat-engine-reset', resetEngine)
  window.removeEventListener('bmat-engine-stage', updateStartupStage)
  window.removeEventListener('bmat-open-onboarding', openOnboarding)
})
</script>

<template>
  <a-config-provider :theme="themeConfig" :locale="zhCN">
    <a-layout class="app-layout" :class="{ 'android-local': isAndroidLocal }">
      <AppNavigation v-if="ready" />
      <a-layout-content class="app-content">
        <header v-if="ready" class="app-page-header">
          <div>
            <h1>{{ pageTitle }}</h1>
          </div>
          <a-button
            shape="circle"
            class="theme-toggle"
            :loading="themeSaving"
            :aria-label="t(isDark ? 'standalone.switchToLight' : 'standalone.switchToDark')"
            :title="t(isDark ? 'standalone.switchToLight' : 'standalone.switchToDark')"
            @click="toggleTheme"
            ><BulbOutlined
          /></a-button>
        </header>
        <main class="page-frame">
          <div v-if="!ready" class="page-state">
            <a-form
              v-if="loginRequired"
              layout="vertical"
              :model="{ password }"
              class="remote-login"
              @finish="connect"
            >
              <a-alert
                v-if="failed"
                type="error"
                show-icon
                :message="loginError"
                class="page-alert"
              />
              <a-form-item name="password" :label="t('standalone.remotePassword')" required>
                <a-input-password
                  v-model:value="password"
                  autocomplete="current-password"
                  :disabled="loading"
                />
              </a-form-item>
              <a-button html-type="submit" type="primary" :loading="loading">{{
                t('standalone.remoteLogin')
              }}</a-button>
            </a-form>
            <a-space v-else-if="failed" direction="vertical" align="center">
              <a-alert type="error" :message="loginError || t('standalone.connectionFailed')" />
              <a-button :loading="loading" @click="connect">{{ t('standalone.retry') }}</a-button>
              <small v-if="isAndroidLocal">{{ t('standalone.androidStartupHint') }}</small>
            </a-space>
            <a-space v-else direction="vertical" align="center">
              <a-spin />
              <span>{{ startupStage || t('standalone.connecting') }}</span>
              <small v-if="isAndroidLocal">{{ t('standalone.androidStartupHint') }}</small>
            </a-space>
          </div>
          <router-view v-else />
        </main>
        <footer v-if="ready" class="app-status">{{ t('standalone.serviceReady') }}</footer>
      </a-layout-content>
    </a-layout>
    <OnboardingWizard
      :open="onboardingOpen && ready"
      @close="closeOnboarding"
      @done="completeOnboarding"
      @skip="skipOnboarding"
    />
  </a-config-provider>
</template>

<style scoped>
.app-layout {
  height: 100%;
  display: flex;
  flex-direction: row;
  background: var(--ant-color-bg-layout);
}
.app-content {
  min-width: 0;
  overflow: auto;
  background: transparent;
}
.app-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 40px 40px 28px;
  background: var(--ant-color-bg-layout);
}
.app-page-header h1 {
  margin: 0;
  font-size: 32px;
  line-height: 1.25;
  font-weight: 650;
  letter-spacing: -0.03em;
}
.theme-toggle {
  background: var(--ant-color-bg-container);
  border-color: transparent;
  flex-shrink: 0;
}
.page-frame {
  padding: 0 40px 32px;
  max-width: 1560px;
  margin: 0 auto;
  min-height: calc(100% - 152px);
}
.app-status {
  padding: 16px 32px;
  text-align: center;
  color: var(--ant-color-text-secondary);
  font-size: 11px;
}
.remote-login {
  width: min(360px, 100%);
  text-align: left;
}
.android-local .page-frame {
  padding-bottom: calc(104px + env(safe-area-inset-bottom));
}
@media (max-width: 1180px) {
  .app-page-header {
    padding: 24px;
  }
  .page-frame {
    padding: 0 24px 32px;
  }
}
@media (max-width: 700px) {
  .app-page-header {
    padding: 28px 20px 24px;
  }
  .app-page-header h1 {
    font-size: 28px;
  }
  .page-frame {
    padding: 0 16px calc(104px + env(safe-area-inset-bottom));
  }
  .app-status {
    padding-bottom: 80px;
  }
}
</style>
