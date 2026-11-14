<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CalendarOutlined,
  CheckCircleOutlined,
  CloudOutlined,
  DesktopOutlined,
  DownloadOutlined,
  FileTextOutlined,
  RightOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import type { AccountOut } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { useSettingsStore } from '@/stores/settings'
import { isAndroidLocal } from '@/services/android'

const { t } = useI18n()
const api = useCommunityApi()
const settings = useSettingsStore()
const accounts = ref<AccountOut[]>([])
const loading = ref(true)
const error = ref('')
const load = async () => {
  loading.value = true
  try {
    accounts.value = (await api.listAccounts()).data
    error.value = ''
  } catch (cause) {
    error.value = errorMessage(cause, t('standalone.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
const groups = computed(() => [
  {
    title: 'standalone.ui.accountsAndTools',
    rows: [
      {
        to: '/accounts',
        title: 'standalone.accountList',
        sub: 'standalone.ui.accountsSubtitle',
        icon: UserOutlined,
      },
      {
        to: '/sign',
        title: 'standalone.homeSignResults',
        sub: 'standalone.ui.signSubtitle',
        icon: CheckCircleOutlined,
      },
      {
        to: '/wiki',
        title: 'standalone.wiki',
        sub: 'standalone.ui.wikiSubtitle',
        icon: CalendarOutlined,
      },
      ...(!import.meta.env.BMAT_ANDROID && !isAndroidLocal
        ? [
            {
              to: '/mas',
              title: 'standalone.mas',
              sub: 'standalone.ui.masSubtitle',
              icon: DesktopOutlined,
            },
          ]
        : []),
      ...(!import.meta.env.BMAT_ANDROID && !isAndroidLocal && settings.data?.CloudMode
        ? [
            {
              to: '/remote',
              title: 'standalone.remote',
              sub: 'standalone.cloudModeHint',
              icon: CloudOutlined,
            },
          ]
        : []),
    ],
  },
  {
    title: 'standalone.ui.appSettings',
    rows: [
      {
        to: '/settings',
        title: 'standalone.ui.appearanceAndPreferences',
        sub: 'standalone.ui.settingsSubtitle',
        icon: SettingOutlined,
      },
      {
        to: '/settings?section=updates',
        title: 'standalone.softwareUpdate',
        sub: 'standalone.ui.updateSubtitle',
        icon: DownloadOutlined,
      },
      {
        to: '/logs',
        title: 'standalone.logs',
        sub: 'standalone.ui.logsSubtitle',
        icon: FileTextOutlined,
      },
    ],
  },
])
</script>

<template>
  <section class="more-page">
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert">
      <template #action
        ><a-button size="small" @click="load">{{ t('standalone.retry') }}</a-button></template
      >
    </a-alert>
    <router-link to="/accounts" class="more-profile">
      <span class="profile-avatar"><UserOutlined /></span>
      <div>
        <h2>{{ accounts[0]?.data.Name || t('standalone.accountList') }}</h2>
        <p>
          {{
            loading
              ? t('standalone.ui.loading')
              : t('standalone.ui.accountCount', { count: accounts.length })
          }}
        </p>
      </div>
      <RightOutlined />
    </router-link>
    <section v-for="group in groups" :key="group.title" class="more-group">
      <h2>{{ t(group.title) }}</h2>
      <div class="preference-group">
        <router-link v-for="row in group.rows" :key="row.to" :to="row.to" class="preference-row">
          <span class="preference-icon"><component :is="row.icon" /></span>
          <div>
            <strong>{{ t(row.title) }}</strong>
            <p>{{ t(row.sub) }}</p>
          </div>
          <RightOutlined />
        </router-link>
      </div>
    </section>
  </section>
</template>

<style scoped>
.more-page {
  max-width: 880px;
  margin: auto;
}
.more-profile {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 10px 4px 26px;
  color: var(--ant-color-text);
}
.profile-avatar {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  border-radius: 22px;
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
  font-size: 26px;
}
.more-profile > div {
  flex: 1;
  min-width: 0;
}
.more-profile h2 {
  margin: 0 0 6px;
  font-size: 20px;
  overflow-wrap: anywhere;
}
.more-profile p {
  margin: 0;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.more-group {
  margin-bottom: 24px;
}
.more-group > h2 {
  font-size: 13px;
  color: var(--ant-color-text-secondary);
  font-weight: 500;
  margin: 0 0 12px 6px;
}
</style>
