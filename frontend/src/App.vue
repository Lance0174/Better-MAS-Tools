<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
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
import AppPageHeader from '@/components/AppPageHeader.vue'
import { useMobileUi } from '@/composables/useMobileUi'
import { consumeBackAction } from '@/composables/useBackAction'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const mobile = useMobileUi()
const content = ref<{ $el: HTMLElement }>()
const scrollPositions = new Map<string, number>()
const detailEntry = ref(false)
watch(
  () => route.fullPath,
  async (next, previous) => {
    if (content.value) scrollPositions.set(previous, content.value.$el.scrollTop)
    detailEntry.value = mobile.value && !route.meta.primary
    await nextTick()
    if (content.value) content.value.$el.scrollTop = scrollPositions.get(next) ?? 0
  }
)
const back = () => {
  if (consumeBackAction()) return
  if (router.options.history.state.back) router.back()
  else void router.replace(String(route.meta.parent || '/more'))
}
const nativeBack = (event: Event) => {
  if (consumeBackAction()) event.preventDefault()
  else if (!route.meta.primary) {
    event.preventDefault()
    back()
  } else if (route.path !== '/home') {
    event.preventDefault()
    void router.replace('/home')
  }
}
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
    await settings.patch({ Theme: isDark.value ? 'light' : 'dark' })
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
  window.addEventListener('bmat-android-back', nativeBack)
  window.addEventListener('bmat-engine-reset', resetEngine)
  window.addEventListener('bmat-engine-stage', updateStartupStage)
  void connect()
})
onBeforeUnmount(() => {
  window.removeEventListener('bmat-android-back', nativeBack)
  window.removeEventListener('bmat-engine-reset', resetEngine)
  window.removeEventListener('bmat-engine-stage', updateStartupStage)
  window.removeEventListener('bmat-open-onboarding', openOnboarding)
})
</script>

<template>
  <a-config-provider :theme="themeConfig" :locale="zhCN">
    <a-layout
      class="app-layout"
      :class="{
        'android-local': isAndroidLocal,
        'mobile-layout': mobile,
        'primary-page': route.meta.primary,
      }"
    >
      <AppNavigation v-if="ready" />
      <a-layout-content ref="content" class="app-content">
        <AppPageHeader
          v-if="ready"
          :title="pageTitle"
          :dark="isDark"
          :saving="themeSaving"
          @theme="toggleTheme"
          @back="back"
        />
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
          <router-view v-else v-slot="{ Component }"
            ><div :key="route.path" :class="{ 'detail-entry': detailEntry }">
              <component :is="Component" /></div
          ></router-view>
        </main>
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
.page-frame {
  padding: 0 36px 32px;
  max-width: 1560px;
  margin: 0 auto;
  min-height: calc(100% - 152px);
}
.remote-login {
  width: min(360px, 100%);
  text-align: left;
}
.mobile-layout .page-frame {
  padding: 0 18px 32px;
  max-width: 640px;
}
.mobile-layout.primary-page .page-frame {
  padding-bottom: calc(100px + var(--app-safe-area-bottom));
}
.detail-entry {
  animation: detail-entry 150ms ease-out;
}
@keyframes detail-entry {
  from {
    opacity: 0.5;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@media (max-width: 1180px) {
  .page-frame {
    padding: 0 24px 32px;
  }
}
@media (max-width: 350px) {
  .mobile-layout .page-frame {
    padding-inline: 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .detail-entry {
    animation: none;
  }
}
</style>
