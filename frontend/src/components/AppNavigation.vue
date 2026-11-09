<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { isAndroidLocal } from '@/services/android'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const moreOpen = ref(false)
const items = computed(() => [
  { path: '/home', key: 'home' },
  { path: '/sign', key: 'sign' },
  ...(settings.data?.ActivityEnabled !== false ? [{ path: '/activity', key: 'activity' }] : []),
  { path: '/gacha', key: 'gacha' },
  { path: '/wiki', key: 'wiki' },
  { path: '/calendar', key: 'calendar' },
  ...(isAndroidLocal ? [] : [{ path: '/mas', key: 'mas' }]),
  ...(settings.data?.CloudMode ? [{ path: '/remote', key: 'remote' }] : []),
  { path: '/logs', key: 'logs' },
  { path: '/settings', key: 'settings' },
])
const primary = computed(() => items.value.filter(item => !['logs', 'settings'].includes(item.key)))
const secondary = computed(() =>
  items.value.filter(item => ['logs', 'settings'].includes(item.key))
)
const mobile = computed(() =>
  items.value.filter(item => ['home', 'activity', 'gacha', 'calendar'].includes(item.key))
)
const number = (index: number) => String(index + 1).padStart(2, '0')
const go = (path: string) => {
  moreOpen.value = false
  void router.push(path)
}
</script>

<template>
  <nav v-if="!isAndroidLocal" class="desktop-navigation" :aria-label="t('standalone.navigation')">
    <div class="navigation-links">
      <router-link
        v-for="(item, index) in primary"
        :key="item.path"
        :to="item.path"
        :aria-current="route.path === item.path ? 'page' : undefined"
      >
        <span class="nav-number mono">{{ number(index) }}</span
        >{{ t(`standalone.${item.key}`) }}
      </router-link>
    </div>
    <div class="navigation-bottom">
      <div class="navigation-links">
        <router-link
          v-for="(item, index) in secondary"
          :key="item.path"
          :to="item.path"
          :aria-current="route.path === item.path ? 'page' : undefined"
        >
          <span class="nav-number mono">{{ number(primary.length + index) }}</span
          >{{ t(`standalone.${item.key}`) }}
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
      <span class="nav-number mono">{{
        number(items.findIndex(entry => entry.path === item.path))
      }}</span>
      <span>{{ t(`standalone.${item.key}`) }}</span>
    </button>
    <button type="button" :aria-label="t('standalone.allFeatures')" @click="moreOpen = true">
      <span class="nav-number mono">•••</span><span>{{ t('standalone.more') }}</span>
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
        {{ t(`standalone.${item.key}`) }}
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
  padding: 27px 12px 16px;
  background: var(--ant-color-bg-container);
  border-right: 1px solid var(--ant-color-border);
}
.navigation-links {
  display: grid;
  gap: 4px;
  overflow-y: auto;
}
.navigation-links a {
  position: relative;
  display: flex;
  align-items: center;
  gap: 13px;
  min-height: 46px;
  padding: 10px 12px;
  border: 1px solid transparent;
  color: var(--ant-color-text-secondary);
  font-size: 13px;
  text-decoration: none;
}
.navigation-links a:hover,
.navigation-links a[aria-current] {
  background: var(--ant-color-bg-elevated);
  color: var(--ant-color-text);
}
.navigation-links a[aria-current] {
  border-color: var(--ant-color-border);
}
.navigation-links a[aria-current]::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 9px;
  bottom: 9px;
  width: 3px;
  background: var(--ant-color-primary);
}
.nav-number {
  font-size: 10px;
  color: var(--ant-color-text-tertiary);
}
.navigation-links a[aria-current] .nav-number {
  color: var(--ant-color-text);
}
.navigation-bottom {
  margin-top: auto;
  padding-top: 24px;
}
.navigation-status {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--ant-color-border);
  margin: 24px 8px 0;
  padding-top: 16px;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.navigation-status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ant-color-success);
}
.mobile-navigation {
  display: none;
  position: fixed;
  inset: auto 0 0;
  z-index: 10;
  gap: 3px;
  padding: 6px 8px max(6px, env(safe-area-inset-bottom));
  border-top: 1px solid var(--ant-color-border);
  background: var(--ant-color-bg-container);
}
.mobile-navigation button {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 0;
  min-height: 48px;
  padding: 5px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ant-color-text-secondary);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.mobile-navigation button[aria-current] {
  border-color: var(--ant-color-border);
  border-top-color: var(--ant-color-primary);
  background: var(--ant-color-bg-elevated);
  color: var(--ant-color-text);
}
.mobile-navigation--android {
  display: flex;
}
.all-features {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.all-features .ant-btn {
  min-height: 40px;
}
:global(.navigation-drawer .ant-drawer-body) {
  max-height: 65dvh;
  overflow-y: auto;
}
@media (max-width: 1180px) {
  .desktop-navigation {
    flex-basis: 178px;
  }
  .navigation-links a {
    font-size: 12px;
    padding: 10px 8px;
    gap: 9px;
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
