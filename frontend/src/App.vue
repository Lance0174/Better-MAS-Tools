<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { connectSession, LoginRequiredError } from '@/services/session'
import { errorMessage } from '@/composables/useCommunityApi'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/composables/useTheme'
import {
  CalendarOutlined,
  DashboardOutlined,
  GiftOutlined,
  LinkOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'

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
const connect = async () => {
  loading.value = true
  failed.value = false
  try {
    await connectSession(password.value)
    await settings.load()
    ready.value = true
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
onMounted(connect)
</script>

<template>
  <a-config-provider :theme="themeConfig" :locale="zhCN">
    <a-layout class="app-layout">
      <a-layout class="app-body">
        <nav
          class="navigation"
          :class="{ 'reduced-motion': settings.data?.LowPerformanceMode }"
          :aria-label="t('standalone.navigation')"
        >
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
            <a-menu-item key="/mas"
              ><template #icon><LinkOutlined /></template>{{ t('standalone.mas') }}</a-menu-item
            >
          </a-menu>
          <a-menu
            mode="inline"
            :selected-keys="[route.path]"
            class="navigation-footer"
            @click="navigate"
          >
            <a-menu-item key="/settings"
              ><template #icon><SettingOutlined /></template
              >{{ t('standalone.settings') }}</a-menu-item
            >
          </a-menu>
        </nav>
        <a-layout-content class="app-content">
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
              <a-alert type="error" :message="t('standalone.connectionFailed')" />
              <a-button :loading="loading" @click="connect">{{ t('standalone.retry') }}</a-button>
            </a-space>
            <a-spin v-else :tip="t('standalone.connecting')" />
          </div>
          <router-view v-else />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>

<style scoped>
.app-layout {
  height: 100%;
  background: var(--ant-color-bg-container);
}
.remote-login {
  width: min(360px, 100%);
  text-align: left;
}
.app-body {
  min-height: 0;
  flex-direction: row;
  background: var(--ant-color-bg-container);
}
.navigation {
  display: flex;
  flex-direction: column;
  flex: 0 0 188px;
  min-height: 0;
  background: var(--ant-color-bg-container);
  border-right: 1px solid var(--ant-color-primary-border);
  padding: 20px 8px 12px;
}
.navigation :deep(.ant-menu) {
  border: 0;
}
.navigation-main {
  overflow-y: auto;
}
.navigation .navigation-footer {
  flex-shrink: 0;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--ant-color-border-secondary);
}
.navigation :deep(.ant-menu-item) {
  transition: background-color 200ms ease;
}
.navigation :deep(.ant-menu-item-selected) {
  font-weight: 600;
}
.navigation.reduced-motion :deep(.ant-menu-item) {
  transition: none;
}
.app-content {
  padding: 28px 32px;
  overflow-y: auto;
  min-width: 0;
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
