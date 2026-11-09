<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import {
  BookOutlined,
  CalendarOutlined,
  ControlOutlined,
  DashboardOutlined,
  GiftOutlined,
  LinkOutlined,
  FileTextOutlined,
  MenuOutlined,
  ScheduleOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const { themeConfig } = useTheme()
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
// 左侧书脊导航（方案 A）：编号由 CSS 计数器生成，顺序即阅读顺序。
const navItems = computed(() => [
  { path: '/sign', label: t('standalone.sign') },
  ...(settings.data?.ActivityEnabled !== false
    ? [{ path: '/activity', label: t('standalone.activity') }]
    : []),
  { path: '/gacha', label: t('standalone.gacha') },
  { path: '/wiki', label: t('standalone.wiki') },
  { path: '/calendar', label: t('standalone.calendar') },
  ...(isAndroidLocal ? [] : [{ path: '/mas', label: t('standalone.mas') }]),
  ...(settings.data?.CloudMode ? [{ path: '/remote', label: t('standalone.remote') }] : []),
])
const footItems = computed(() => [
  { path: '/logs', label: t('standalone.logs') },
  { path: '/settings', label: t('standalone.settings') },
])
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
  { path: '/wiki', label: t('standalone.wiki'), icon: BookOutlined },
  { path: '/calendar', label: t('standalone.calendar'), icon: ScheduleOutlined },
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
    <!-- 景深层：四团色雾、焦散细纹与暗角，为所有玻璃面板提供可采样的背景景深。 -->
    <div class="glass-depth" aria-hidden="true"><i /><i /><i /><i /></div>
    <a-layout class="app-layout" :class="{ 'android-local': isAndroidLocal }">
      <a-layout class="app-body">
        <nav
          v-if="!isAndroidLocal"
          class="navigation spine"
          :aria-label="t('standalone.navigation')"
        >
          <div class="brand-block">
            <span class="brand-mark" aria-hidden="true" />
            <span class="brand-stack">
              <span class="brand-name">{{ t('standalone.title') }}</span>
              <span class="brand-sub">BETTER MAS TOOLS</span>
            </span>
          </div>
          <p class="spine-kicker">SECTIONS / 功能</p>
          <ul class="spine-list">
            <li v-for="item in navItems" :key="item.path">
              <router-link
                :to="item.path"
                class="spine-item"
                :class="{ on: route.path === item.path }"
                :aria-current="route.path === item.path ? 'page' : undefined"
                >{{ item.label }}</router-link
              >
            </li>
          </ul>
          <ul class="spine-list spine-list--foot">
            <li v-for="item in footItems" :key="item.path">
              <router-link
                :to="item.path"
                class="spine-item"
                :class="{ on: route.path === item.path }"
                :aria-current="route.path === item.path ? 'page' : undefined"
                >{{ item.label }}</router-link
              >
            </li>
          </ul>
          <div class="spine-meta">
            <span class="mono">{{ ready ? 'SIGNAL OK' : 'CONNECTING' }}</span>
            <span class="mono">{{ route.path }}</span>
          </div>
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
  flex-direction: column;
  /* 衬底交给景深层与 body，外壳本身透明，玻璃面板才能采到背景。 */
  background: transparent;
}
.remote-login {
  width: min(360px, 100%);
  text-align: left;
}
.app-body {
  min-height: 0;
  flex: 1;
  flex-direction: row;
  background: transparent;
}
/* 书脊：深色竖排导航（方案 A）——编号由计数器给出，选中项左侧 3px 强调条。 */
.navigation {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 0 0 212px;
  min-height: 0;
  counter-reset: nav;
  background: #1b1c1e;
  color: #f4f4f0;
  border: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.12);
  padding: 0;
  border-radius: 0;
  overflow: hidden;
}
html.dark .navigation {
  background: #2b2c2f;
}
.brand-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 14px 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  flex: 0 0 auto;
}
.brand-mark {
  width: 10px;
  height: 26px;
  flex: 0 0 auto;
  background: var(--app-accent, #ffe100);
}
.brand-stack {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.brand-name {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.07em;
  white-space: nowrap;
  color: inherit;
}
.brand-sub {
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 9px;
  letter-spacing: 0.26em;
  color: rgba(255, 255, 255, 0.6);
}
.spine-kicker {
  margin: 0;
  padding: 9px 14px 8px;
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 9px;
  letter-spacing: 0.2em;
  color: rgba(255, 255, 255, 0.6);
  flex: 0 0 auto;
}
.spine-list {
  list-style: none;
  margin: 0;
  padding: 0 0 8px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  flex: 1 1 auto;
}
.spine-list--foot {
  flex: 0 0 auto;
  margin-top: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 8px;
}
.spine-item {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 36px;
  padding: 0 12px 0 11px;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.66);
  text-decoration: none;
  white-space: nowrap;
  border-left: 3px solid transparent;
  transition: background-color 160ms ease, color 160ms ease;
}
.spine-item::before {
  counter-increment: nav;
  content: counter(nav, decimal-leading-zero);
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 9.5px;
  letter-spacing: 0.06em;
  width: 15px;
  flex: 0 0 auto;
  opacity: 0.85;
}
.spine-item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.04);
}
.spine-item.on {
  color: #fff;
  background: rgba(255, 255, 255, 0.065);
  border-left-color: var(--app-accent, #ffe100);
}
.spine-item.on::before {
  color: var(--app-accent, #ffe100);
  opacity: 1;
}
.spine-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px 13px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 10.5px;
  color: rgba(255, 255, 255, 0.58);
  flex: 0 0 auto;
}
.spine-meta .mono {
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  letter-spacing: 0.04em;
}
.app-content {
  position: relative;
  padding: 20px 24px;
  overflow-y: auto;
  min-width: 0;
  /* 内容画布透明，景深直接可见；具体面板各自使用玻璃或实色材质。 */
  background: transparent;
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
  border-top: 1px solid var(--app-glass-border-body);
  background:
    linear-gradient(112deg, var(--app-glass-highlight) 0%, transparent 46%),
    var(--app-glass-tint-strong);
  -webkit-backdrop-filter: blur(var(--app-glass-blur)) saturate(var(--app-glass-saturate));
  backdrop-filter: blur(var(--app-glass-blur)) saturate(var(--app-glass-saturate));
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
/* 窄屏把书脊折叠成顶部横向导航条：144px 宽的书脊会吃掉近四成内容宽度。 */
@media (max-width: 700px) {
  .app-body {
    flex-direction: column;
  }
  .navigation {
    flex: 0 0 auto;
    width: 100%;
    flex-direction: row;
    align-items: center;
    padding: 0 8px;
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .navigation::-webkit-scrollbar {
    display: none;
  }
  .brand-block {
    padding: 8px 10px 8px 4px;
    border-bottom: 0;
  }
  .brand-mark {
    height: 18px;
  }
  .brand-sub,
  .spine-kicker,
  .spine-meta {
    display: none;
  }
  .spine-list {
    flex-direction: row;
    padding: 0;
    overflow: visible;
  }
  .spine-list--foot {
    margin-top: 0;
    border-top: 0;
    padding-top: 0;
  }
  .spine-item {
    height: 42px;
    padding: 0 10px;
    border-left: 0;
    border-bottom: 3px solid transparent;
  }
  .spine-item.on {
    border-bottom-color: var(--app-accent, #ffe100);
  }
  .spine-item::before {
    display: none;
  }
  .app-content {
    padding: 16px;
  }
}
</style>
