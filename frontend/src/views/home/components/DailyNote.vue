<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HolderOutlined } from '@ant-design/icons-vue'
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
const { t, locale } = useI18n()
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
const details = computed(() => {
  if (!presentation.value) return []
  if (props.compact) return presentation.value.groups.flatMap(group => group.metrics).slice(0, 2)
  return presentation.value.groups.flatMap(group => group.metrics)
})
const percent = (metric: NoteMetric) =>
  Math.min(100, Math.max(0, (metric.current / metric.target) * 100))
const updated = computed(() => {
  const date = new Date(snapshot.value?.updatedAt || '')
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString(locale.value, {
        timeZone: 'Asia/Shanghai',
        hour: '2-digit',
        minute: '2-digit',
      })
})
const statusColor = computed(
  () =>
    ({
      success: 'success',
      empty: 'default',
      limited: 'warning',
      unavailable: 'warning',
      failed: 'error',
    })[snapshot.value?.status ?? 'empty']
)
const selectAccount = (value: unknown) => activity.select(props.game, String(value))
</script>

<template>
  <article v-if="snapshot" class="daily-note" :data-game="game">
    <img
      v-if="background && !imageFailed"
      class="note-background"
      :src="background"
      alt=""
      referrerpolicy="no-referrer"
      decoding="async"
      @error="imageFailed = true"
    />
    <div class="note-scrim" />
    <div class="note-content">
      <header class="note-heading">
        <span v-if="draggable" class="activity-drag-handle" :title="t('gamesign.activity.drag')"
          ><HolderOutlined
        /></span>
        <div>
          <h3>{{ label }} · {{ t('standalone.activity') }}</h3>
        </div>
        <a-tag :color="statusColor">{{ t(`gamesign.activity.status.${snapshot.status}`) }}</a-tag>
      </header>
      <a-select
        v-if="options.length > 1"
        class="note-account"
        :value="snapshotKey(snapshot)"
        :options="options"
        show-search
        option-filter-prop="label"
        :aria-label="t('standalone.chooseGameAccount', { game: label })"
        @change="selectAccount"
      />
      <span v-else class="note-identity">{{ options[0]?.label }}</span>
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
            :stroke-width="3"
            stroke-color="var(--ant-color-primary)"
            trail-color="#ffffff33"
          />
          <span v-if="metric.status" class="note-metric-status">{{ metric.status }}</span>
        </div>
      </div>
      <div class="note-details">
        <div v-for="metric in details" :key="`${metric.period}-${metric.name}`">
          <span>{{ metric.name }}</span>
          <strong v-if="metric.target > 0" class="mono"
            >{{ metric.current }} / {{ metric.target }}</strong
          >
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
      <footer>
        <span>{{ snapshot.platform }}</span
        ><span v-if="updated">{{ t('gamesign.activity.queriedAt', { time: updated }) }}</span>
        <router-link v-if="compact" to="/activity">{{ t('standalone.viewAllNotes') }}</router-link>
      </footer>
    </div>
  </article>
</template>

<style scoped>
.daily-note {
  position: relative;
  isolation: isolate;
  min-width: 0;
  min-height: 264px;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--ant-color-border);
  border-radius: 24px;
  background: #182026;
  color: #f8fafc;
}
.note-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 60% 35%;
  z-index: 0;
}
.note-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, #091119e0, #09111980), linear-gradient(0deg, #091119eb, transparent);
  z-index: 1;
}
.note-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 22px 24px;
}
.note-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 17px;
}
.note-heading > div {
  flex: 1;
  min-width: 0;
}
.note-heading h3 {
  margin: 0;
  font-size: 16px;
  color: inherit;
}
.note-eyebrow {
  margin: 0 0 5px;
  font-size: 12px;
  color: #cad4dc;
  letter-spacing: 0.12em;
}
.note-heading .ant-tag {
  margin: 0;
  background: #0b151dcc;
  color: #e6f7ef;
  border-color: #d4e4dc70;
  font-size: 12px;
}
.activity-drag-handle {
  cursor: grab;
  color: #d6e0e7;
}
.activity-drag-handle:active {
  cursor: grabbing;
}
.note-account {
  width: 100%;
  max-width: 390px;
  font-size: 12px;
}
.note-account :deep(.ant-select-selector) {
  background: #0b151da6;
  border-color: #dde7ed55;
  color: #f8fafc;
}
.note-account :deep(.ant-select-arrow) {
  color: #f8fafc;
}
.note-identity {
  font-size: 12px;
  padding: 6px 0;
  overflow-wrap: anywhere;
  color: #f8fafc;
}
.note-featured {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 16px;
  margin-top: 13px;
}
.note-resource > div {
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.note-resource > div > span {
  font-size: 12px;
  color: #d6e0e7;
}
.note-resource strong {
  font-size: 30px;
  font-weight: 500;
  line-height: 1.4;
}
.note-resource strong small {
  font-size: 13px;
  color: #d6e0e7;
  font-weight: 400;
}
.note-details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 24px;
  margin: 14px 0 18px;
  font-size: 12px;
}
.note-details > div {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 10px;
  color: #d6e0e7;
}
.note-details strong {
  font-weight: 400;
  color: #f8fafc;
}
.note-metric-status {
  font-size: 12px;
  color: #d6e0e7;
}
.note-details .note-metric-status {
  flex-basis: 100%;
}
.note-reason {
  margin: 12px 0;
}
footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  font-size: 12px;
  color: #d6e0e7;
}
footer a {
  color: #fff;
  text-decoration: underline;
}
@media (max-width: 700px) {
  .note-content {
    padding: 20px;
  }
  .note-heading h3 {
    font-size: 15px;
  }
  .note-details {
    gap: 10px 16px;
  }
}
</style>
