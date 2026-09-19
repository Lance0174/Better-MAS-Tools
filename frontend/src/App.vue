<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { connectSession, LoginRequiredError } from '@/services/session'
import { errorMessage } from '@/composables/useCommunityApi'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/composables/useTheme'
import { isAndroidLocal, markAndroidReady, retryAndroidEngine } from '@/services/android'
import { setDesktopLightMode } from '@/services/desktop'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import {
  CalendarOutlined,
  ControlOutlined,
  DashboardOutlined,
  GiftOutlined,
  LinkOutlined,
  FileTextOutlined,
  MenuOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'

const ONBOARDING_KEY = 'bmat-onboarding-done'
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const navigate = (item: { key: string | number }) => router.push(String(item.key))
const settings = useSettingsStore()
const { themeConfig } = useTheme()
const ready = ref(false)
const failed = ref(false)
const loading = ref(false)
const loginRequired = ref(false)
const password = ref('')
const loginError = ref('')
const startupStage = ref('')
const onboardingOpen = ref(false)
const openOnboarding = () => {
  onboardingOpen.value = true
}
// 设置页“重新查看引导”通过此事件重开首启向导。
window.addEventListener('bmat-open-onboarding', openOnboarding)
const markOnboardingDone = () => {
  try {
    localStorage.setItem(ONBOARDING_KEY, '1')
  } catch {
    /* 存储不可用时每次启动都显示，不影响使用 */
  }
}
const maybeOpenOnboarding = () => {
  let done = false
  try {
    done = localStorage.getItem(ONBOARDING_KEY) === '1'
  } catch {
    done = false
  }
  if (!done) openOnboarding()
}
// 底部导航：游戏社区为主入口 + 系统工具；功能页在左侧可收起侧边栏。
const mobileItems = computed(() => [
  { path: '/sign', label: t('standalone.sign'), icon: CalendarOutlined },
  ...(settings.data?.CloudMode
    ? [{ path: '/remote', label: t('standalone.remote'), icon: ControlOutlined }]
    : []),
  { path: '/logs', label: t('standalone.logs'), icon: FileTextOutlined },
  { path: '/settings', label: t('standalone.settings'), icon: SettingOutlined },
])
// 左侧可收起侧边栏：社区功能页菜单。
const sideOpen = ref(false)
const sideItems = computed(() => [
  { path: '/sign', label: t('standalone.sign'), icon: CalendarOutlined },
  ...(settings.data?.ActivityEnabled !== false
    ? [{ path: '/activity', label: t('standalone.activity'), icon: DashboardOutlined }]
    : []),
  { path: '/gacha', label: t('standalone.gacha'), icon: GiftOutlined },
  ...(settings.data?.CloudMode
    ? [{ path: '/remote', label: t('standalone.remote'), icon: ControlOutlined }]
    : []),
])
const goSide = (item: { key: string | number }) => {
  router.push(String(item.key))
  sideOpen.value = false
}
const pageTitle = computed(() => {
  const meta = route.meta.title as string | undefined
  return meta ? t(meta) : t('standalone.sign')
})
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
      <a-layout class="app-body">
        <nav
          v-if="!isAndroidLocal"
          class="navigation"
          :aria-label="t('standalone.navigation')"
        >
          <div class="brand-block">
            <span class="brand-hex" aria-hidden="true"><i /></span>
            <span class="brand-name">{{ t('standalone.title') }}</span>
            <span class="brand-coord">N31.23° E121.47°</span>
          </div>
          <div class="nav-tick" aria-hidden="true" />
          <a-menu
            mode="inline"
            :selected-keys="[route.path]"
            class="navigation-main"
            @click="navigate"
          >
            <a-menu-item key="/sign"
              ><template #icon><CalendarOutlined /></template
              >{{ t('standalone.sign') }}</a-menu-item
            >
            <a-menu-item v-if="settings.data?.ActivityEnabled !== false" key="/activity"
              ><template #icon><DashboardOutlined /></template
              >{{ t('standalone.activity') }}</a-menu-item
            >
            <a-menu-item key="/gacha"
              ><template #icon><GiftOutlined /></template>{{ t('standalone.gacha') }}</a-menu-item
            >
            <a-menu-item v-if="!isAndroidLocal" key="/mas"
              ><template #icon><LinkOutlined /></template>{{ t('standalone.mas') }}</a-menu-item
            >
            <a-menu-item v-if="settings.data?.CloudMode" key="/remote"
              ><template #icon><ControlOutlined /></template>{{
                t('standalone.remote')
              }}</a-menu-item
            >
          </a-menu>
          <a-menu
            mode="inline"
            :selected-keys="[route.path]"
            class="navigation-footer"
            @click="navigate"
          >
            <a-menu-item key="/logs"
              ><template #icon><FileTextOutlined /></template
              >{{ t('standalone.logs') }}</a-menu-item
            >
            <a-menu-item key="/settings"
              ><template #icon><SettingOutlined /></template
              >{{ t('standalone.settings') }}</a-menu-item
            >
          </a-menu>
        </nav>
        <a-layout-content class="app-content">
          <div v-if="isAndroidLocal && ready" class="android-topbar">
            <button
              class="android-hamburger"
              type="button"
              :aria-label="t('standalone.navigation')"
              @click="sideOpen = true"
            >
              <MenuOutlined />
            </button>
            <span class="android-page-title">{{ pageTitle }}</span>
          </div>
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
        </a-layout-content>
      </a-layout>
      <nav
        v-if="isAndroidLocal && ready"
        class="mobile-navigation"
        :aria-label="t('standalone.navigation')"
      >
        <button
          v-for="item in mobileItems"
          :key="item.path"
          type="button"
          :aria-current="route.path === item.path ? 'page' : undefined"
          :class="{ selected: route.path === item.path }"
          @click="router.push(item.path)"
        >
          <component :is="item.icon" /><span>{{ item.label }}</span>
        </button>
      </nav>
    </a-layout>
    <a-drawer
      v-if="isAndroidLocal"
      :open="sideOpen"
      placement="left"
      :title="t('standalone.title')"
      :width="240"
      class="android-side-drawer"
      @close="sideOpen = false"
    >
      <a-menu
        mode="inline"
        :selected-keys="[route.path]"
        class="android-side-menu"
        @click="goSide"
      >
        <a-menu-item v-for="item in sideItems" :key="item.path">
          <template #icon><component :is="item.icon" /></template>{{ item.label }}
        </a-menu-item>
      </a-menu>
    </a-drawer>
    <OnboardingWizard
      :open="onboardingOpen && ready"
      @close="onboardingOpen = false"
      @done="markOnboardingDone"
    />
  </a-config-provider>
</template>

<style scoped>
.app-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--ant-color-bg-container);
}
.remote-login {
  width: min(360px, 100%);
  text-align: left;
}
.app-body {
  min-height: 0;
  flex: 1;
  flex-direction: row;
  background: var(--ant-color-bg-container);
}
.navigation {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 0 0 196px;
  min-height: 0;
  background: var(--ant-color-bg-container);
  border-right: 1px solid var(--ant-color-primary-border);
  padding: 0 8px 12px;
}
/* 侧栏底部 HUD 角标：斜切三角 + 坐标刻度 */
.navigation::after {
  content: '';
  position: absolute;
  right: -1px;
  bottom: 0;
  width: 14px;
  height: 14px;
  background: var(--app-corner);
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
  opacity: 0.6;
}
.brand-block {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 12px 14px;
  border-bottom: 1px solid var(--app-panel-border);
  /* 右上角斜切，营造工业面板切割感 */
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 0 100%);
  background: linear-gradient(180deg, var(--app-panel), transparent);
}
.brand-hex {
  flex: 0 0 auto;
  width: 30px;
  height: 34px;
  position: relative;
  background: var(--ant-color-primary);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
  display: grid;
  place-items: center;
}
.brand-hex i {
  width: 12px;
  height: 12px;
  background: var(--ant-color-bg-container);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}
.brand-name {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--ant-color-text);
}
.brand-coord {
  position: absolute;
  right: 14px;
  top: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.08em;
  color: var(--app-corner);
  opacity: 0.8;
}
/* 导航刻度条 */
.nav-tick {
  height: 4px;
  margin: 0 12px;
  background: repeating-linear-gradient(
    90deg,
    var(--app-tick) 0 1px,
    transparent 1px 8px
  );
  opacity: 0.7;
}
.navigation :deep(.ant-menu) {
  border: 0;
  background: transparent;
}
.navigation-main {
  overflow-y: auto;
  padding-top: 6px;
}
.navigation .navigation-footer {
  flex-shrink: 0;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--ant-color-border-secondary);
}
.navigation :deep(.ant-menu-item) {
  margin: 2px 0;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  letter-spacing: 0.02em;
  transition: background-color 200ms ease;
}
/* 菜单选中：左侧六边形角标 + 斜切底 */
.navigation :deep(.ant-menu-item-selected) {
  font-weight: 700;
  color: var(--ant-color-primary);
  background: var(--app-panel);
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%);
}
.navigation :deep(.ant-menu-item-selected)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 8px;
  height: 9px;
  background: var(--ant-color-primary);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}
.app-content {
  position: relative;
  padding: 28px 32px;
  overflow-y: auto;
  min-width: 0;
}
/* 内容区左上 HUD 角标 */
.app-content::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 12px;
  width: 16px;
  height: 16px;
  border-top: 2px solid var(--app-corner);
  border-left: 2px solid var(--app-corner);
  opacity: 0.6;
  pointer-events: none;
}
.mobile-navigation {
  display: none;
}
/* 安卓布局：顶部汉堡栏 + 内容 + 底部导航；功能页在左侧可收起 Drawer 侧边栏 */
.android-local .app-body {
  flex-direction: column;
}
.android-local .app-content {
  padding: 12px 16px;
  min-width: 0;
}
/* 安卓顶栏：汉堡按钮 + 当前页标题 */
.android-topbar {
  display: none;
}
.android-local .android-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0 12px;
}
.android-hamburger {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ant-color-primary-border);
  border-radius: 6px;
  background: var(--app-panel);
  color: var(--ant-color-primary);
  font-size: 18px;
  cursor: pointer;
}
.android-page-title {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.03em;
}
/* 左侧可收起侧边栏菜单 */
.android-local :deep(.android-side-drawer .ant-drawer-body) {
  padding: 12px 8px;
}
.android-local :deep(.android-side-menu) {
  border: 0;
  background: transparent;
}
.android-local :deep(.android-side-menu .ant-menu-item) {
  margin: 4px 0;
  border-radius: 6px;
  font-size: 14px;
}
.android-local :deep(.android-side-menu .ant-menu-item-selected) {
  background: var(--app-panel);
  color: var(--ant-color-primary);
  font-weight: 600;
}
.android-local .mobile-navigation {
  display: flex;
  flex-shrink: 0;
  padding: 6px 4px;
  border-top: 1px solid var(--ant-color-primary-border);
  background: var(--ant-color-bg-container);
}
.mobile-navigation button {
  flex: 1;
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  min-height: 48px;
  padding: 8px 2px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: background-color 200ms ease;
}
.mobile-navigation button > :first-child {
  font-size: 20px;
}
.mobile-navigation button.selected,
.mobile-navigation button:hover {
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-primary);
}
@media (max-width: 700px) {
  .navigation {
    flex-basis: 144px;
    padding-inline: 0;
  }
  .app-content {
    padding: 16px;
  }
}
</style>
