<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { ArrowLeftOutlined, BulbOutlined, BulbFilled, UserOutlined } from '@ant-design/icons-vue'

defineProps<{ title: string; dark: boolean; saving: boolean }>()
const emit = defineEmits<{ theme: []; back: [] }>()
const { t, locale } = useI18n()
const route = useRoute()
const subtitle = computed(() =>
  route.name === 'Home'
    ? new Date().toLocaleDateString(locale.value, {
        month: 'long',
        day: 'numeric',
        weekday: 'long',
        timeZone: 'Asia/Shanghai',
      })
    : route.meta.subtitle
      ? t(String(route.meta.subtitle))
      : ''
)
</script>

<template>
  <header class="app-page-header" :class="{ 'detail-header': !route.meta.primary }">
    <div class="page-heading">
      <a-button
        v-if="!route.meta.primary"
        class="page-back"
        shape="circle"
        :aria-label="t('standalone.ui.back')"
        @click="emit('back')"
        ><ArrowLeftOutlined
      /></a-button>
      <div>
        <h1>{{ title }}</h1>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
    </div>
    <div class="header-actions">
      <a-button
        shape="circle"
        class="theme-toggle"
        :loading="saving"
        :aria-label="t(dark ? 'standalone.switchToLight' : 'standalone.switchToDark')"
        :title="t(dark ? 'standalone.switchToLight' : 'standalone.switchToDark')"
        @click="emit('theme')"
      >
        <BulbFilled v-if="dark" /><BulbOutlined v-else />
      </a-button>
      <router-link to="/accounts" class="header-account" :aria-label="t('standalone.accountList')"
        ><UserOutlined
      /></router-link>
    </div>
  </header>
</template>

<style scoped>
.app-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  max-width: 1520px;
  margin: auto;
  padding: 34px 36px 26px;
}
.page-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 650;
  line-height: 1.3;
  letter-spacing: -0.03em;
}
p {
  margin: 7px 0 0;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.theme-toggle,
.header-account {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border: 0;
  background: var(--ant-color-bg-container);
  border-radius: 50%;
}
.header-account {
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
  font-size: 18px;
}
.page-back {
  border: 0;
  background: transparent;
}
@media (max-width: 700px) {
  .app-page-header {
    padding: calc(24px + var(--app-safe-area-top)) 20px 22px;
  }
  h1 {
    font-size: 28px;
  }
  .detail-header {
    padding-top: calc(16px + var(--app-safe-area-top));
    padding-bottom: 20px;
  }
  .detail-header h1 {
    font-size: 23px;
  }
  .detail-header .header-actions {
    display: none;
  }
}
</style>
