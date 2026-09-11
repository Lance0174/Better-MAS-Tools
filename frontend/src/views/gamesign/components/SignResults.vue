<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { SignAccountOut } from '@/api'
import { summarizeSignResults } from '../signSummary'
import { usePerformanceStore } from '@/stores/performance'

const props = defineProps<{ results: Record<string, SignAccountOut[]>; today: string }>()
const { t } = useI18n()
const performance = usePerformanceStore()
// 原始中文状态来自社区结果契约，不能翻译后参与判定。
const isSuccess = (status: string | undefined) => status === '成功' || status === '已签到'
const summary = (accounts: SignAccountOut[]) => {
  const counts = summarizeSignResults(accounts, props.today)
  if (!counts.success && !counts.failed) return t('standalone.todayPending')
  if (!counts.failed && !counts.pending) return t('standalone.todayAllSuccess')
  return t('standalone.todaySummary', counts)
}
</script>

<template>
  <section class="sign-results" :class="{ 'reduced-motion': performance.isLowPower }">
    <h2 class="section-title">{{ t('standalone.signResults') }}</h2>
    <a-empty
      v-if="!Object.keys(results).length"
      :description="t('standalone.noResult')"
      :image="undefined"
    />
    <a-collapse v-else :default-active-key="Object.keys(results)">
      <a-collapse-panel v-for="(accounts, platform) in results" :key="platform" :header="platform">
        <template #extra
          ><span class="platform-summary">{{ summary(accounts) }}</span></template
        >
        <div v-for="account in accounts" :key="account.account_uid" class="result-account">
          <strong>{{ account.account_alias }}</strong>
          <p v-if="!account.games?.length" class="result-detail">
            {{ t('standalone.todayPending') }}
          </p>
          <div v-for="(game, index) in account.games" :key="index" class="result-line">
            <a-tag :color="isSuccess(game.status) ? 'success' : 'error'">{{ game.status }}</a-tag>
            <span class="result-game">{{ game.game }}</span
            ><span>{{ game.account }}</span>
            <span class="result-detail">{{ game.reward || game.reason }}</span>
          </div>
        </div>
      </a-collapse-panel>
    </a-collapse>
  </section>
</template>

<style scoped>
.sign-results {
  margin-top: 24px;
}
.sign-results :deep(.ant-collapse) {
  border: 0;
  background: transparent;
}
.sign-results :deep(.ant-collapse > .ant-collapse-item) {
  background: var(--ant-color-bg-container);
  border: 1px solid var(--ant-color-primary-border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
}
.sign-results :deep(.ant-collapse-header) {
  font-weight: 600;
  transition: background-color 200ms ease;
}
.sign-results :deep(.ant-collapse-header:hover),
.sign-results :deep(.ant-collapse-header:focus-visible),
.sign-results :deep(.ant-collapse-item-active > .ant-collapse-header) {
  background: var(--ant-color-primary-bg);
}
.sign-results.reduced-motion :deep(.ant-collapse-header) {
  transition: none;
}
.platform-summary {
  color: var(--ant-color-primary);
  font-size: 12px;
  font-weight: 400;
}
.result-account + .result-account {
  margin-top: 16px;
}
.result-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 12px;
  overflow-wrap: anywhere;
}
.result-game {
  font-weight: 500;
}
.result-detail {
  color: var(--ant-color-text-secondary);
}
</style>
