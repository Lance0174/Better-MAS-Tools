<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckOutlined, ClockCircleOutlined, ExclamationOutlined } from '@ant-design/icons-vue'
import type { SignAccountOut } from '@/api'
import {
  getAccountSignSteps,
  getSignSummaryState,
  signRoleIdentity,
  summarizeSignResults,
} from '../signSummary'

const props = defineProps<{ results: Record<string, SignAccountOut[]>; today: string }>()
const { t, locale } = useI18n()
const counts = computed(() =>
  summarizeSignResults(Object.values(props.results).flat(), props.today)
)
const summaryLabels = {
  success: 'standalone.signAllSuccess',
  partial: 'standalone.signPartialFailure',
  failed: 'standalone.signFailedStatus',
  pending: 'standalone.signPendingStatus',
} as const
const groups = computed(() =>
  Object.entries(props.results)
    .filter(([, accounts]) => accounts.length)
    .map(([platform, accounts]) => ({
      platform,
      accounts: accounts.map(account => ({
        ...account,
        state: getSignSummaryState(summarizeSignResults([account], props.today)),
        steps: getAccountSignSteps(account).map(step => ({
          ...step,
          role: signRoleIdentity(step.account),
          state:
            !props.today || step.signedAt?.slice(0, 10) !== props.today
              ? 'pending'
              : step.status === '成功' || step.status === '已签到'
                ? 'success'
                : 'failed',
        })),
      })),
    }))
)
const time = (value?: string) => {
  const date = new Date(value || '')
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleString(locale.value, {
        timeZone: 'Asia/Shanghai',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
}
</script>

<template>
  <section class="sign-results">
    <div class="sign-overview" :aria-label="t('standalone.ui.signOverview')">
      <div
        v-for="state in ['success', 'failed', 'pending'] as const"
        :key="state"
        :data-state="state"
      >
        <span>{{ t(`standalone.ui.signCounts.${state}`) }}</span
        ><strong class="mono">{{ counts[state] }}</strong>
      </div>
    </div>
    <a-empty v-if="!groups.length" :description="t('standalone.noResult')" />
    <section v-for="group in groups" :key="group.platform" class="sign-platform">
      <header class="platform-heading">
        <h2>{{ group.platform }}</h2>
        <span>{{ t('standalone.ui.accountCount', { count: group.accounts.length }) }}</span>
      </header>
      <div class="sign-account-grid">
        <article
          v-for="(account, index) in group.accounts"
          :key="account.account_uid || index"
          class="result-account"
        >
          <header class="result-account-header">
            <strong>{{ account.account_alias || t('gamesign.unknownUser') }}</strong>
            <span class="result-status" :data-state="account.state">{{
              t(summaryLabels[account.state])
            }}</span>
          </header>
          <p v-if="!account.steps.length" class="result-detail">
            {{ t('standalone.todayPending') }}
          </p>
          <ul v-else class="result-steps">
            <li
              v-for="(step, stepIndex) in account.steps"
              :key="stepIndex"
              class="result-step"
              :data-kind="step.kind"
              :data-state="step.state"
            >
              <span class="result-symbol" aria-hidden="true"
                ><CheckOutlined v-if="step.state === 'success'" /><ExclamationOutlined
                  v-else-if="step.state === 'failed'" /><ClockCircleOutlined v-else
              /></span>
              <div class="result-content">
                <div class="result-line">
                  <strong>{{
                    step.kind === 'community'
                      ? t('standalone.kuroCoinSign')
                      : step.kind === 'game'
                        ? t('standalone.gameSignTask', { game: step.game })
                        : step.game
                  }}</strong>
                  <span class="step-status">{{
                    step.state === 'pending'
                      ? t('standalone.signPendingStatus')
                      : step.status || t('standalone.signFailedStatus')
                  }}</span>
                </div>
                <p
                  v-if="step.role.name && step.role.name !== account.account_alias"
                  class="result-role"
                >
                  {{ step.role.name }}
                </p>
                <p v-if="step.role.uid" class="result-role mono">UID {{ step.role.uid }}</p>
                <p v-if="step.reward" class="result-reward">{{ step.reward }}</p>
                <p v-if="step.reason" class="result-reason">{{ step.reason }}</p>
                <time v-if="time(step.signedAt)" class="result-time">{{
                  t('standalone.ui.lastSignRun', { time: time(step.signedAt) })
                }}</time>
              </div>
            </li>
          </ul>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.sign-results {
  margin-top: 22px;
}
.sign-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.sign-overview > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 18px 22px;
  border-radius: 20px;
  background: var(--ant-color-bg-container);
}
.sign-overview span {
  font-size: 12px;
  color: var(--ant-color-text-secondary);
}
.sign-overview strong {
  font-size: 27px;
  line-height: 1;
}
.sign-overview [data-state='success'] strong {
  color: var(--ant-color-success);
}
.sign-overview [data-state='failed'] strong {
  color: var(--ant-color-error);
}
.sign-platform + .sign-platform {
  margin-top: 26px;
}
.platform-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.platform-heading h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.platform-heading > span {
  color: var(--ant-color-text-tertiary);
  font-size: 11px;
}
.sign-account-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
  gap: 16px;
  align-items: start;
}
.result-account {
  min-width: 0;
  padding: 20px;
  border-radius: 24px;
  background: var(--ant-color-bg-container);
}
.result-account-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 16px;
}
.result-account-header > strong {
  font-size: 15px;
  overflow-wrap: anywhere;
}
.result-status {
  flex-shrink: 0;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
  background: var(--ant-color-fill-secondary);
}
.result-status[data-state='success'] {
  color: var(--ant-color-success-text);
  background: var(--ant-color-success-bg);
}
.result-status[data-state='failed'],
.result-status[data-state='partial'] {
  color: var(--ant-color-warning-text);
  background: var(--ant-color-warning-bg);
}
.result-steps {
  padding: 0;
  margin: 0;
  list-style: none;
}
.result-step {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  border-top: 1px solid var(--ant-color-border-secondary);
}
.result-step:last-child {
  padding-bottom: 0;
}
.result-symbol {
  flex: 0 0 25px;
  display: grid;
  place-content: center;
  align-self: flex-start;
  width: 25px;
  height: 25px;
  border-radius: 50%;
  background: var(--ant-color-fill-secondary);
  color: var(--ant-color-text-secondary);
}
[data-state='success'] > .result-symbol {
  color: var(--ant-color-success-text);
  background: var(--ant-color-success-bg);
}
[data-state='failed'] > .result-symbol {
  color: var(--ant-color-error);
}
.result-content {
  min-width: 0;
  flex: 1;
  overflow-wrap: anywhere;
}
.result-line {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}
.result-line strong {
  font-size: 14px;
  font-weight: 600;
}
.step-status {
  color: var(--ant-color-text-secondary);
  font-size: 11px;
  flex-shrink: 0;
}
.result-role,
.result-detail {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  margin: 5px 0 0;
}
.result-reward {
  margin: 10px 0 0;
  font-size: 12px;
}
.result-reason {
  color: var(--ant-color-error);
  margin: 7px 0 0;
  font-size: 12px;
}
.result-time {
  display: block;
  color: var(--ant-color-text-tertiary);
  margin-top: 8px;
  font-size: 10px;
}
@media (max-width: 700px) {
  .sign-overview {
    gap: 8px;
    margin-bottom: 24px;
  }
  .sign-overview > div {
    flex-direction: column;
    align-items: flex-start;
    padding: 17px 16px;
  }
  .sign-account-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .result-account {
    padding: 18px;
  }
}
</style>
