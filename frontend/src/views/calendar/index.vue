<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { ReloadOutlined } from '@ant-design/icons-vue'
import type { WikiCalendarGameOut } from '@/api'
import { errorMessage } from '@/composables/useCommunityApi'
import { useCalendarStore } from '@/stores/calendar'
import CalendarCarousel from '@/components/CalendarCarousel.vue'
import { filterAndSortActivities } from './calendarFilter'

const { t, locale } = useI18n()
const calendar = useCalendarStore()
const { games, loading } = storeToRefs(calendar)
const message = computed(() =>
  calendar.failure
    ? errorMessage(calendar.failure, t('standalone.calendarFailed'))
    : calendar.notice
)
const bannerGame = ref('')
const activeGame = ref<string>('all')
const statusFilter = ref<string>('all')
const sortBy = ref<'endsAt' | 'startsAt' | 'title'>('endsAt')
const hidePermanent = ref(false)

const STATUS_OPTIONS = ['all', 'active', 'running', 'upcoming', 'permanent', 'ended'] as const

type CalendarActivity = NonNullable<WikiCalendarGameOut['activities']>[number]

const selectedGames = computed(() =>
  activeGame.value === 'all'
    ? games.value
    : games.value.filter(item => item.game === activeGame.value)
)

// 后端按游戏分组返回，并且每个游戏各自带 message 与来源；
// 某个游戏取不到数据只影响它自己，不会让整页失败。
// rawCount 保留筛选前的条数，用于区分「这个游戏没有数据」和「筛选后没有匹配」。
const visibleGames = computed(() =>
  selectedGames.value
    .map(group => {
      const raw = group.activities ?? []
      return {
        ...group,
        rawCount: raw.length,
        activities: filterAndSortActivities(raw, {
          statusFilter: statusFilter.value,
          sortBy: sortBy.value,
          hidePermanent: hidePermanent.value,
        }),
      }
    })
    // 有可见条目就展示；整组没有数据但后端给了说明时也保留，用来解释这个游戏为什么是空的。
    .filter(
      group => group.activities.length > 0 || (group.rawCount === 0 && Boolean(group.message))
    )
)

// 有数据但被筛掉时要说「无匹配」，不能和「后端没有数据」共用一个空态。
const hasAnyActivity = computed(() =>
  selectedGames.value.some(group => (group.activities ?? []).length > 0)
)

const gameTabs = computed(() => games.value.filter(item => item.name))

const visibleCount = computed(() =>
  visibleGames.value.reduce((total, group) => total + group.activities.length, 0)
)

/** 同一游戏下同名活动可能重复（例如版本更新公告），标题无法唯一标识，需带上起止时间与序号兜底。 */
const rowKey = (group: WikiCalendarGameOut, item: CalendarActivity, index: number) =>
  [group.game, item.kind, item.title, item.startsAt ?? '', item.endsAt ?? '', index].join('|')

const statusLabel = (value: string) =>
  ({
    all: t('standalone.calendarStatusAll'),
    active: t('standalone.calendarStatusActive'),
    running: t('standalone.calendarStatusRunning'),
    upcoming: t('standalone.calendarStatusUpcoming'),
    permanent: t('standalone.calendarStatusPermanent'),
    ended: t('standalone.calendarStatusEnded'),
  })[value] ?? value

const statusColor = (status: string) => {
  if (status.includes('进行')) return 'green'
  if (status.includes('即将')) return 'blue'
  if (status.includes('常驻')) return 'purple'
  return 'default'
}

// 来源提示：缓存与兜底数据要能看出来，避免把过期数据当成实时结果。
const sourceTag = (source: string) => {
  if (source === 'stale-cache')
    return { color: 'orange', label: t('standalone.calendarSourceStale') }
  if (source === 'cache') return { color: 'default', label: t('standalone.calendarSourceCache') }
  if (source === 'local') return { color: 'cyan', label: t('standalone.calendarSourceLocal') }
  return null
}

const formatTime = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(locale.value, {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const load = async () => {
  await calendar.load()
  if (activeGame.value !== 'all' && !games.value.some(item => item.game === activeGame.value))
    activeGame.value = 'all'
}
const visibleEvents = computed(() => visibleGames.value.flatMap(group => group.activities))
const stateCounts = computed(() =>
  ['进行中', '即将开始', '常驻'].map(name => ({
    name,
    count: visibleEvents.value.filter(item => item.status === name).length,
  }))
)
const endingSoon = computed(() =>
  visibleEvents.value
    .filter(item => item.status === '进行中' && item.endsAt)
    .sort((a, b) => a.endsAt!.localeCompare(b.endsAt!))
    .slice(0, 3)
)

onMounted(load)
</script>

<template>
  <section class="calendar-page">
    <CalendarCarousel
      v-if="selectedGames.length"
      v-model:game="bannerGame"
      :groups="selectedGames"
      :autoplay="activeGame === 'all'"
    />
    <header class="page-toolbar">
      <a-space wrap>
        <a-radio-group v-model:value="activeGame" size="small" button-style="solid">
          <a-radio-button value="all">{{ t('standalone.calendarAll') }}</a-radio-button>
          <a-radio-button v-for="item in gameTabs" :key="item.game" :value="item.game">
            {{ item.name }}
          </a-radio-button>
        </a-radio-group>
        <a-button :loading="loading" @click="load">
          <template #icon><ReloadOutlined /></template>{{ t('standalone.calendarRefresh') }}
        </a-button>
      </a-space>
    </header>

    <div class="calendar-filters glass-surface">
      <a-select v-model:value="statusFilter" size="small" class="calendar-filter-field">
        <a-select-option v-for="value in STATUS_OPTIONS" :key="value" :value="value">
          {{ statusLabel(value) }}
        </a-select-option>
      </a-select>
      <a-select v-model:value="sortBy" size="small" class="calendar-filter-field">
        <a-select-option value="endsAt">{{ t('standalone.calendarSortEndsAt') }}</a-select-option>
        <a-select-option value="startsAt">{{
          t('standalone.calendarSortStartsAt')
        }}</a-select-option>
        <a-select-option value="title">{{ t('standalone.calendarSortTitle') }}</a-select-option>
      </a-select>
      <a-checkbox v-model:checked="hidePermanent">
        {{ t('standalone.calendarHidePermanent') }}
      </a-checkbox>
      <span class="calendar-count">
        {{ t('standalone.calendarCount', { count: visibleCount }) }}
      </span>
    </div>

    <a-alert
      v-if="message"
      type="info"
      show-icon
      class="glass-surface calendar-hint"
      :message="message"
    />

    <div class="calendar-layout">
      <div>
        <a-spin :spinning="loading">
          <a-empty
            v-if="!visibleGames.length && !loading"
            :description="
              t(hasAnyActivity ? 'standalone.calendarEmptyFiltered' : 'standalone.calendarEmpty')
            "
          />
          <section v-for="group in visibleGames" :key="group.game" class="calendar-group">
            <header class="calendar-group-header">
              <h2 class="section-title">{{ group.name || group.game }}</h2>
              <a-space>
                <a-tag v-if="group.versionName" color="cyan">{{ group.versionName }}</a-tag>
                <a-tag v-else-if="group.version" color="cyan">{{ group.version }}</a-tag>
                <a-tag
                  v-if="sourceTag(group.source ?? '')"
                  :color="sourceTag(group.source ?? '')?.color"
                >
                  {{ sourceTag(group.source ?? '')?.label }}
                </a-tag>
              </a-space>
            </header>
            <a-alert
              v-if="group.message && !(group.activities ?? []).length"
              type="warning"
              show-icon
              class="calendar-hint"
              :message="group.message"
            />
            <ul v-else class="calendar-list">
              <li v-for="(item, index) in group.activities ?? []" :key="rowKey(group, item, index)">
                <article class="calendar-card glass-surface">
                  <img v-if="item.banner" :src="item.banner" alt="" loading="lazy" />
                  <div v-else class="calendar-card-placeholder" aria-hidden="true">
                    {{ (item.title || '?').slice(0, 1) }}
                  </div>
                  <div class="calendar-card-body">
                    <header>
                      <strong>{{ item.title }}</strong>
                      <a-tag v-if="item.status" :color="statusColor(item.status)">{{
                        item.status
                      }}</a-tag>
                    </header>
                    <p v-if="item.subtitle">{{ item.subtitle }}</p>
                    <footer>
                      <span v-if="item.endsAt">{{
                        t('standalone.calendarUntil', { time: formatTime(item.endsAt) })
                      }}</span>
                      <span v-else-if="item.startsAt">{{
                        t('standalone.calendarFrom', { time: formatTime(item.startsAt) })
                      }}</span>
                    </footer>
                  </div>
                </article>
              </li>
            </ul>
          </section>
        </a-spin>
      </div>
      <aside class="calendar-summary">
        <section>
          <h2>{{ t('standalone.calendarOverview') }}</h2>
          <div v-for="state in stateCounts" :key="state.name" class="summary-row">
            <span>{{ state.name }}</span
            ><strong class="mono">{{ state.count }}</strong>
          </div>
        </section>
        <section>
          <h2>{{ t('standalone.calendarEndingSoon') }}</h2>
          <article v-for="(item, index) in endingSoon" :key="index">
            <strong>{{ item.title }}</strong>
            <p class="mono">{{ formatTime(item.endsAt || '') }}</p>
          </article>
          <p v-if="!endingSoon.length">{{ t('standalone.calendarNoEnding') }}</p>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.calendar-page {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.calendar-hint {
  margin-bottom: 12px;
}
/* 筛选条与卡片同材质，避免在玻璃界面里插一块实色面板。 */
.calendar-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding: 8px 12px;
  border-radius: 3px;
}
.calendar-filter-field {
  min-width: 132px;
}
.calendar-count {
  margin-left: auto;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--ant-color-text-tertiary);
}
.calendar-group {
  margin-bottom: 12px;
}
.calendar-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.calendar-group-header .section-title {
  margin-bottom: 8px;
}
.calendar-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.calendar-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 12px;
  height: 100%;
  padding: 10px;
  border-radius: 3px;
}
.calendar-card img,
.calendar-card-placeholder {
  width: 100%;
  height: 88px;
  flex: 0 0 auto;
  border-radius: 3px;
  object-fit: cover;
}
.calendar-card-placeholder {
  display: grid;
  place-items: center;
  background: var(--app-panel);
  color: var(--ant-color-text-tertiary);
  font-size: 24px;
  font-weight: 700;
}
.calendar-card-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 4px;
}
.calendar-card-body header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.calendar-card-body strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.calendar-card-body p {
  margin: 0;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.calendar-card-body footer {
  margin-top: auto;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--ant-color-text-tertiary);
}
.calendar-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 24px;
}
.calendar-summary section {
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--ant-color-border);
  background: var(--ant-color-bg-container);
}
.calendar-summary h2 {
  font-size: 13px;
  margin: 0 0 16px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  margin: 12px 0;
  font-size: 12px;
}
.calendar-summary article {
  padding: 12px 0;
  border-top: 1px solid var(--ant-color-border-secondary);
  font-size: 12px;
}
.calendar-summary p {
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
@media (max-width: 1180px) {
  .calendar-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .calendar-layout {
    grid-template-columns: minmax(0, 1fr) 220px;
    gap: 16px;
  }
}
@media (max-width: 900px) {
  .calendar-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .calendar-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
}
@media (max-width: 700px) {
  .calendar-summary {
    display: block;
  }
  .calendar-filters {
    padding: 12px 0;
  }
  .calendar-filter-field {
    min-width: 120px;
  }
}
</style>
