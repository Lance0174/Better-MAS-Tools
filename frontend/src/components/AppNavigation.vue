<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
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
  MoreOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { useSettingsStore } from '@/stores/settings'
import { useMobileUi } from '@/composables/useMobileUi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const mobile = useMobileUi()
const primary = computed(() => [
  { path: '/home', key: 'home', icon: HomeOutlined },
  ...(settings.data?.ActivityEnabled !== false
    ? [{ path: '/activity', key: 'activity', icon: ClockCircleOutlined }]
    : []),
  { path: '/gacha', key: 'gacha', icon: GiftOutlined },
  { path: '/calendar', key: 'calendar', icon: CalendarOutlined },
])
const desktop = computed(() => [
  ...primary.value,
  { path: '/accounts', key: 'accountList', icon: UserOutlined },
  { path: '/sign', key: 'sign', icon: CheckCircleOutlined },
  { path: '/wiki', key: 'wiki', icon: ReadOutlined },
  ...(!import.meta.env.BMAT_ANDROID ? [{ path: '/mas', key: 'mas', icon: DesktopOutlined }] : []),
  ...(!import.meta.env.BMAT_ANDROID && settings.data?.CloudMode
    ? [{ path: '/remote', key: 'remote', icon: CloudOutlined }]
    : []),
])
const secondary = [
  { path: '/logs', key: 'logs', icon: FileTextOutlined },
  { path: '/settings', key: 'settings', icon: SettingOutlined },
]
const go = (path: string) => {
  if (path !== route.path) void router.replace(path)
}
</script>

<template>
  <nav v-if="!mobile" class="desktop-navigation" :aria-label="t('standalone.navigation')">
    <div class="navigation-links">
      <router-link
        v-for="item in desktop"
        :key="item.path"
        :to="item.path"
        :aria-current="route.path === item.path ? 'page' : undefined"
        ><component :is="item.icon" /><span>{{ t(`standalone.${item.key}`) }}</span></router-link
      >
    </div>
    <div class="navigation-bottom">
      <div class="navigation-links">
        <router-link
          v-for="item in secondary"
          :key="item.path"
          :to="item.path"
          :aria-current="route.path === item.path ? 'page' : undefined"
          ><component :is="item.icon" /><span>{{ t(`standalone.${item.key}`) }}</span></router-link
        >
      </div>
    </div>
  </nav>
  <nav
    v-else-if="route.meta.primary"
    class="mobile-navigation"
    :aria-label="t('standalone.navigation')"
  >
    <button
      v-for="item in primary"
      :key="item.path"
      type="button"
      :aria-current="route.path === item.path ? 'page' : undefined"
      @click="go(item.path)"
    >
      <component :is="item.icon" /><span>{{ t(`standalone.ui.nav.${item.key}`) }}</span>
    </button>
    <button
      type="button"
      :aria-current="route.path === '/more' ? 'page' : undefined"
      @click="go('/more')"
    >
      <MoreOutlined /><span>{{ t('standalone.more') }}</span>
    </button>
  </nav>
</template>

<style scoped>
.desktop-navigation {
  display: flex;
  flex-direction: column;
  flex: 0 0 208px;
  min-height: 0;
  padding: 34px 14px 20px;
  border-right: 1px solid var(--ant-color-border-secondary);
}
.navigation-links {
  display: grid;
  gap: 5px;
  overflow-y: auto;
}
.navigation-links a {
  display: flex;
  align-items: center;
  gap: 13px;
  min-height: 48px;
  padding: 12px 16px;
  border-radius: 16px;
  color: var(--ant-color-text-secondary);
  font-size: 14px;
  font-weight: 550;
}
.navigation-links .anticon {
  font-size: 20px;
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
.mobile-navigation {
  display: flex;
  position: fixed;
  inset: auto 12px calc(10px + var(--app-safe-area-bottom));
  z-index: 10;
  gap: 4px;
  padding: 7px;
  border: 1px solid var(--ant-color-border-secondary);
  border-radius: 25px;
  background: var(--ant-color-bg-container);
  box-shadow: 0 8px 32px #0000000c;
}
.mobile-navigation button {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 0;
  min-height: 52px;
  padding: 6px 2px;
  border: 0;
  border-radius: 18px;
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
@media (max-width: 1180px) {
  .desktop-navigation {
    flex-basis: 184px;
    padding-inline: 10px;
  }
  .navigation-links a {
    padding: 12px;
    gap: 10px;
  }
}
</style>
