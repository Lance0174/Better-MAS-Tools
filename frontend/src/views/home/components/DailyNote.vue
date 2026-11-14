<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ChoiceSelect from '@/components/ChoiceSelect.vue'
import CommunityActivityCard from '@/views/gamesign/components/CommunityActivityCard.vue'
import { useActivityStore } from '@/stores/activity'
import {
  gameLabelKey,
  presentActivity,
  type NoteMetric,
} from '@/views/gamesign/communityActivityPresentation'
import { gameBackground, snapshotKey } from '@/utils/communityDashboard'

const props = withDefaults(
  defineProps<{ game: string; compact?: boolean; draggable?: boolean }>(),
  { compact: false, draggable: false }
)
const { t } = useI18n()
const activity = useActivityStore()
const snapshot = computed(() => activity.current(props.game))
const accounts = computed(
  () => activity.groups.find(group => group.game === props.game)?.snapshots ?? []
)
const label = computed(() => {
  const key = gameLabelKey(props.game)
  return key ? t(key) : props.game
})
const background = computed(() => gameBackground(props.game))
const imageFailed = ref(false)
watch(background, () => {
  imageFailed.value = false
})
const options = computed(() =>
  accounts.value.map(item => ({
    value: snapshotKey(item),
    label: [
      item.roleName || item.account,
      item.server || item.platform,
      item.roleUid ? t('gamesign.activity.roleUid', { uid: item.roleUid }) : item.account,
    ]
      .filter(Boolean)
      .join(' · '),
  }))
)
const presentation = computed(() => (snapshot.value ? presentActivity(snapshot.value) : null))
const featured = computed(() =>
  props.compact ? presentation.value?.featured.slice(0, 1) : presentation.value?.featured
)
const percent = (metric: NoteMetric) =>
  Math.min(100, Math.max(0, (metric.current / metric.target) * 100))
const selectAccount = (value: unknown) => activity.select(props.game, String(value))
</script>

<template>
  <article v-if="snapshot" class="daily-note" :class="{ compact }" :data-game="game">
    <CommunityActivityCard v-if="!compact" :snapshot="snapshot" :draggable="draggable">
      <template #identity>
        <ChoiceSelect
          class="note-account"
          :value="snapshotKey(snapshot)"
          :options="options"
          show-search
          option-filter-prop="label"
          :aria-label="t('standalone.chooseGameAccount', { game: label })"
          @change="selectAccount"
        />
      </template>
    </CommunityActivityCard>
    <template v-else>
      <header class="note-banner">
        <img
          v-if="background && !imageFailed"
          class="note-background"
          :src="background"
          alt=""
          decoding="async"
          @error="imageFailed = true"
        />
        <div class="note-scrim" />
        <div class="note-heading">
          <h3>{{ label }}</h3>
        </div>
      </header>
      <div class="note-paper">
        <ChoiceSelect
          class="note-account"
          :value="snapshotKey(snapshot)"
          :options="options"
          show-search
          option-filter-prop="label"
          :aria-label="t('standalone.chooseGameAccount', { game: label })"
          @change="selectAccount"
        />
        <div class="note-featured">
          <div v-for="metric in featured" :key="metric.name" class="note-resource">
            <div>
              <span>{{ metric.name }}</span
              ><strong v-if="metric.target > 0" class="mono" :data-resource="metric.name"
                >{{ metric.current }}<small> / {{ metric.target }}</small></strong
              >
            </div>
            <a-progress
              v-if="metric.target > 0"
              :percent="percent(metric)"
              :show-info="false"
              :stroke-width="compact ? 4 : 5"
              stroke-color="var(--ant-color-primary)"
              trail-color="var(--ant-color-fill-secondary)"
            />
            <span v-if="metric.status" class="note-metric-status">{{ metric.status }}</span>
          </div>
        </div>
        <a-alert
          v-if="snapshot.reason"
          :type="snapshot.status === 'failed' ? 'error' : 'warning'"
          :message="snapshot.reason"
          show-icon
          class="note-reason"
        />
        <span v-else-if="compact && !featured?.length" class="note-metric-status">{{
          t(`gamesign.activity.status.${snapshot.status}`)
        }}</span>
      </div>
    </template>
  </article>
</template>

<style scoped>
.daily-note {
  min-width: 0;
  overflow: hidden;
  border-radius: 24px;
  background: var(--ant-color-bg-container);
}
.daily-note :deep(.activity-card) {
  clip-path: none;
  border: 0;
  border-radius: 24px;
}
.daily-note :deep(.ant-card-body) {
  padding: 20px;
}
.daily-note :deep(.activity-identity) {
  margin: 12px 0;
}
.daily-note :deep(.activity-content) {
  gap: 16px;
}
.daily-note :deep(.activity-card-footer) {
  padding-top: 14px;
}
.daily-note:not(.compact) .note-account {
  margin-bottom: 0;
}
.note-banner {
  position: relative;
  isolation: isolate;
  height: 128px;
  padding: 23px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: #263744;
  color: #fff;
}
.note-background,
.note-scrim {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  object-fit: cover;
  object-position: center 37%;
}
.note-scrim {
  background: linear-gradient(0deg, #102131c9, #10213113);
}
.note-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}
.note-heading h3 {
  flex: 1;
  margin: 0;
  color: #fff;
  font-size: 21px;
  font-weight: 650;
}
.note-paper {
  padding: 22px;
}
.note-account {
  width: 100%;
  margin-bottom: 20px;
}
.note-featured {
  display: grid;
  gap: 18px;
}
.note-resource > div:first-child {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
}
.note-resource strong {
  font-size: 34px;
  font-weight: 650;
  color: var(--ant-color-text);
  white-space: nowrap;
  letter-spacing: -0.5px;
}
.note-resource strong small {
  font-size: 14px;
  font-weight: 400;
  color: var(--ant-color-text-secondary);
  letter-spacing: 0;
}
.note-metric-status {
  display: block;
  color: var(--ant-color-text-secondary);
  font-size: 11px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.note-reason {
  margin-top: 14px;
}
.compact .note-banner {
  height: 64px;
  padding: 12px 14px;
}
.compact .note-heading h3 {
  font-size: 13px;
}
.compact .note-paper {
  padding: 13px;
}
.compact .note-resource > div:first-child {
  display: block;
}
.compact .note-resource > div:first-child > span {
  display: block;
  font-size: 11px;
  margin-bottom: 3px;
}
.compact .note-resource strong {
  font-size: 26px;
}
.compact .note-resource strong small {
  font-size: 12px;
}
.compact .note-account {
  padding: 7px 0;
  margin-top: -7px;
  margin-bottom: 1px;
}
.compact :deep(.choice-select) {
  position: relative;
  font-size: 10px;
  min-height: 30px;
  padding: 4px 8px;
  gap: 5px;
  border-radius: 10px;
}
/* 缩小可见控件，周围留白仍提供 44px 的触控范围。 */
.compact :deep(.choice-select::before) {
  content: '';
  position: absolute;
  inset: -7px 0;
}
.compact :deep(.choice-select > .anticon) {
  font-size: 9px;
}
.compact .note-reason {
  font-size: 11px;
  padding: 8px;
}
@media (max-width: 350px) {
  .note-paper {
    padding: 17px;
  }
  .compact .note-paper {
    padding: 11px;
  }
  .compact .note-resource strong {
    font-size: 23px;
  }
}
</style>
