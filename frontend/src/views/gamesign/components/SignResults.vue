<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SignAccountOut } from '@/api'
import { getAccountSignSteps, getSignSummaryState, summarizeSignResults } from '../signSummary'
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
  if (counts.failed && counts.success) return t('standalone.todayPartialFailure', counts)
  return t('standalone.todaySummary', counts)
}
const summaryStyles = {
  success: { color: 'success', label: 'standalone.signAllSuccess' },
  partial: { color: 'warning', label: 'standalone.signPartialFailure' },
  failed: { color: 'error', label: 'standalone.signFailedStatus' },
  pending: { color: 'default', label: 'standalone.signPendingStatus' },
} as const
const groups = computed(() =>
  Object.entries(props.results).map(([platform, accounts]) => ({
    platform,
    summary: summary(accounts),
    accounts: accounts.map(account => ({
      ...account,
      steps: getAccountSignSteps(account),
      summary: summaryStyles[getSignSummaryState(summarizeSignResults([account], props.today))],
    })),
  }))
)
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
      <a-collapse-panel v-for="group in groups" :key="group.platform" :header="group.platform">
        <template #extra
          ><span class="platform-summary">{{ group.summary }}</span></template
        >
        <div v-for="account in group.accounts" :key="account.account_uid" class="result-account">
          <div class="result-account-header">
            <strong>{{ account.account_alias }}</strong>
            <a-tag :color="account.summary.color">{{ t(account.summary.label) }}</a-tag>
          </div>
          <p v-if="!account.steps.length" class="result-detail">
            {{ t('standalone.todayPending') }}
          </p>
          <div
            v-for="(step, index) in account.steps"
            :key="index"
            class="result-step"
            :data-kind="step.kind"
          >
            <div class="result-line">
              <a-tag :color="isSuccess(step.status) ? 'success' : 'error'">{{ step.status }}</a-tag>
              <span class="result-game">{{
                step.kind === 'community'
                  ? t('standalone.kuroCoinSign')
                  : step.kind === 'game'
                    ? t('standalone.gameSignTask', { game: step.game })
                    : step.game
              }}</span>
              <span v-if="step.account" class="result-role">{{ step.account }}</span>
            </div>
            <p v-if="step.reward" class="result-detail">{{ step.reward }}</p>
            <p v-if="step.reason" class="result-reason">{{ step.reason }}</p>
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
.result-account-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.result-step {
  overflow-wrap: anywhere;
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
.result-role,
.result-detail {
  color: var(--ant-color-text-secondary);
}
.result-detail,
.result-reason {
  margin: 4px 0 0;
}
.result-reason {
  color: var(--ant-color-error);
}
</style>
