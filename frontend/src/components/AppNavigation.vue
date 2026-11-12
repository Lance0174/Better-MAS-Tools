<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  AppstoreOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  GiftOutlined,
  HomeOutlined,
  ReadOutlined,
  SettingOutlined,
  DesktopOutlined,
  CloudOutlined,
} from '@ant-design/icons-vue'
import { useSettingsStore } from '@/stores/settings'
import { isAndroidLocal } from '@/services/android'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const moreOpen = ref(false)
const items = computed(() => [
  { path: '/home', key: 'home', icon: HomeOutlined },
  { path: '/sign', key: 'sign', icon: CheckCircleOutlined },
  ...(settings.data?.ActivityEnabled !== false
    ? [{ path: '/activity', key: 'activity', icon: ClockCircleOutlined }]
    : []),
  { path: '/gacha', key: 'gacha', icon: GiftOutlined },
  { path: '/wiki', key: 'wiki', icon: ReadOutlined },
  { path: '/calendar', key: 'calendar', icon: CalendarOutlined },
  ...(import.meta.env.BMAT_ANDROID || isAndroidLocal
    ? []
    : [{ path: '/mas', key: 'mas', icon: DesktopOutlined }]),
  ...(!isAndroidLocal && !import.meta.env.BMAT_ANDROID && settings.data?.CloudMode
    ? [{ path: '/remote', key: 'remote', icon: CloudOutlined }]
    : []),
  { path: '/logs', key: 'logs', icon: FileTextOutlined },
  { path: '/settings', key: 'settings', icon: SettingOutlined },
])
const primary = computed(() => items.value.filter(item => !['logs', 'settings'].includes(item.key)))
const secondary = computed(() =>
  items.value.filter(item => ['logs', 'settings'].includes(item.key))
)
const mobile = computed(() =>
  items.value.filter(item => ['home', 'activity', 'gacha', 'calendar'].includes(item.key))
)
const isMorePage = computed(() => !mobile.value.some(item => route.path === item.path))
const go = (path: string) => {
  moreOpen.value = false
  void router.push(path)
}
</script>

<template>
  <nav v-if="!isAndroidLocal" class="desktop-navigation" :aria-label="t('standalone.navigation')">
    <div class="navigation-links">
      <router-link
        v-for="item in primary"
        :key="item.path"
        :to="item.path"
        :aria-current="route.path === item.path ? 'page' : undefined"
      >
        <component :is="item.icon" aria-hidden="true" />
        <span>{{ t(`standalone.${item.key}`) }}</span>
      </router-link>
    </div>
    <div class="navigation-bottom">
      <div class="navigation-links">
        <router-link
          v-for="item in secondary"
          :key="item.path"
          :to="item.path"
          :aria-current="route.path === item.path ? 'page' : undefined"
        >
          <component :is="item.icon" aria-hidden="true" />
          <span>{{ t(`standalone.${item.key}`) }}</span>
        </router-link>
      </div>
      <p class="navigation-status"><i />{{ t('standalone.serviceReady') }}</p>
    </div>
  </nav>
  <nav
    class="mobile-navigation"
    :class="{ 'mobile-navigation--android': isAndroidLocal }"
    :aria-label="t('standalone.navigation')"
  >
    <button
      v-for="item in mobile"
      :key="item.path"
      type="button"
      :aria-current="route.path === item.path ? 'page' : undefined"
      @click="go(item.path)"
    >
      <component :is="item.icon" aria-hidden="true" />
      <span>{{ t(`standalone.${item.key}`) }}</span>
    </button>
    <button
      type="button"
      :aria-label="t('standalone.allFeatures')"
      :aria-expanded="moreOpen"
      :aria-current="isMorePage ? 'page' : undefined"
      @click="moreOpen = true"
    >
      <AppstoreOutlined aria-hidden="true" /><span>{{ t('standalone.more') }}</span>
    </button>
  </nav>
  <a-drawer
    :open="moreOpen"
    placement="bottom"
    :title="t('standalone.allFeatures')"
    height="auto"
    root-class-name="navigation-drawer"
    @close="moreOpen = false"
  >
    <div class="all-features">
      <a-button
        v-for="item in items"
        :key="item.path"
        :type="route.path === item.path ? 'primary' : 'default'"
        @click="go(item.path)"
      >
        <component :is="item.icon" aria-hidden="true" />{{ t(`standalone.${item.key}`) }}
      </a-button>
    </div>
  </a-drawer>
</template>

<style scoped>
.desktop-navigation {
  display: flex;
  flex-direction: column;
  flex: 0 0 208px;
  min-height: 0;
  padding: 40px 14px 20px;
  background: var(--ant-color-bg-layout);
  border-right: 1px solid var(--ant-color-border-secondary);
}
.navigation-links {
  display: grid;
  gap: 6px;
  overflow-y: auto;
}
.navigation-links a {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 50px;
  padding: 13px 18px;
  border-radius: 16px;
  color: var(--ant-color-text-secondary);
  font-size: 14px;
  font-weight: 550;
  text-decoration: none;
}
.navigation-links .anticon {
  font-size: 21px;
}
.navigation-links a:hover {
  background: var(--ant-color-bg-elevated);
}
.navigation-links a[aria-current] {
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
}
.navigation-bottom {
  margin-top: auto;
  padding-top: 24px;
}
.navigation-status {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--ant-color-border-secondary);
  margin: 20px 12px 0;
  padding-top: 20px;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
}
.navigation-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ant-color-success);
}
.mobile-navigation {
  display: none;
  position: fixed;
  inset: auto 16px calc(12px + env(safe-area-inset-bottom));
  z-index: 10;
  gap: 4px;
  padding: 8px;
  border: 1px solid var(--ant-color-border-secondary);
  border-radius: 24px;
  background: var(--ant-color-bg-container);
  box-shadow: 0 8px 32px #00000012;
}
.mobile-navigation button {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 0;
  min-height: 48px;
  padding: 6px 2px;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: var(--ant-color-text-secondary);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
}
.mobile-navigation .anticon {
  font-size: 21px;
}
.mobile-navigation button[aria-current] {
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
}
.mobile-navigation--android {
  display: flex;
}
.all-features {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.all-features .ant-btn {
  min-height: 48px;
}
:global(.navigation-drawer .ant-drawer-body) {
  max-height: 65dvh;
  overflow-y: auto;
}
@media (max-width: 1180px) {
  .desktop-navigation {
    flex-basis: 184px;
  }
  .navigation-links a {
    padding: 12px;
    gap: 10px;
  }
}
@media (max-width: 700px) {
  .desktop-navigation {
    display: none;
  }
  .mobile-navigation {
    display: flex;
  }
}
</style>
