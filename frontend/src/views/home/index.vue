<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { StatusOut } from '@/api'
import { useActivityStore } from '@/stores/activity'
import { useCalendarStore } from '@/stores/calendar'
import { useSettingsStore } from '@/stores/settings'
import { errorMessage, useCommunityApi } from '@/composables/useCommunityApi'
import CalendarCarousel from '@/components/CalendarCarousel.vue'
import { filterAndSortActivities } from '@/views/calendar/calendarFilter'
import DailyNote from './components/DailyNote.vue'
import { CheckCircleOutlined, RightOutlined } from '@ant-design/icons-vue'
import { summarizeSignResults } from '@/views/gamesign/signSummary'

const { t, locale } = useI18n()
const activity = useActivityStore()
const calendar = useCalendarStore()
const settings = useSettingsStore()
const api = useCommunityApi()
const activeGame = ref('')
const status = ref<StatusOut | null>(null)
const statusFailure = ref<unknown>(null)
const statusLoading = ref(false)
const game = computed(() => calendar.games.find(group => group.game === activeGame.value))
const counts = computed(() =>
  summarizeSignResults(Object.values(status.value?.results ?? {}).flat(), status.value?.today ?? '')
)
const noteGames = computed(() => activity.groups.slice(0, 2))
const signSummary = computed(() => {
  if (!status.value) return t('standalone.ui.signEmpty')
  if (!Object.values(status.value.results ?? {}).flat().length) return t('standalone.noResult')
  return t(
    counts.value.failed ? 'standalone.todayPartialFailure' : 'standalone.todaySummary',
    counts.value
  )
})
const events = computed(() =>
  filterAndSortActivities(game.value?.activities ?? [], {
    statusFilter: 'active',
    sortBy: 'endsAt',
    hidePermanent: false,
  }).slice(0, 3)
)
watch(
  () => calendar.games,
  groups => {
    if (!groups.some(group => group.game === activeGame.value))
      activeGame.value = groups[0]?.game ?? ''
  },
  { immediate: true }
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
let alive = true
let timer: ReturnType<typeof setTimeout> | undefined
async function loadStatus() {
  if (statusLoading.value) return
  statusLoading.value = true
  try {
    const response = await api.status()
    if (alive) {
      status.value = response
      statusFailure.value = null
    }
  } catch (cause) {
    if (alive) statusFailure.value = cause
  } finally {
    if (alive) statusLoading.value = false
  }
}
async function poll() {
  if (!alive) return
  if (!document.hidden) await loadStatus()
  if (alive) timer = setTimeout(poll, 10000)
}
onMounted(() => {
  void calendar.load()
  if (settings.data?.ActivityEnabled !== false) void activity.load()
  void poll()
})
onUnmounted(() => {
  alive = false
  clearTimeout(timer)
})
</script>

<template>
  <section class="home-overview">
    <a-alert
      v-if="calendar.failure"
      type="error"
      show-icon
      :message="errorMessage(calendar.failure, t('standalone.calendarFailed'))"
      class="page-alert"
      ><template #action
        ><a-button size="small" :loading="calendar.loading" @click="calendar.load()">{{
          t('standalone.retry')
        }}</a-button></template
      ></a-alert
    >
    <a-alert
      v-if="calendar.notice"
      type="info"
      show-icon
      :message="calendar.notice"
      class="page-alert"
    />
    <div v-if="calendar.loading && !calendar.games.length" class="page-state"><a-spin /></div>
    <CalendarCarousel
      v-else-if="calendar.games.length"
      v-model:game="activeGame"
      :groups="calendar.games"
    />
    <a-empty v-else :description="t('standalone.calendarEmpty')" class="home-calendar-empty" />
    <a-alert
      v-if="statusFailure"
      type="error"
      show-icon
      :message="errorMessage(statusFailure, t('standalone.loadFailed'))"
      class="page-alert"
      ><template #action
        ><a-button size="small" @click="loadStatus">{{ t('standalone.retry') }}</a-button></template
      ></a-alert
    >
    <router-link to="/sign" class="home-sign-summary">
      <span class="sign-icon" :class="{ 'sign-icon--warning': counts.failed }"
        ><CheckCircleOutlined
      /></span>
      <div>
        <h2>{{ t('standalone.ui.todayResults') }}</h2>
        <p>{{ statusLoading && !status ? t('standalone.ui.signLoading') : signSummary }}</p>
        <small v-if="settings.data?.ScheduledRun">{{
          t('standalone.dailyPlan', { time: settings.data.ScheduledTime || '' })
        }}</small>
      </div>
      <RightOutlined />
    </router-link>
    <div class="home-details" :class="{ 'sign-only': settings.data?.ActivityEnabled === false }">
      <section v-if="settings.data?.ActivityEnabled !== false" class="home-notes-section">
        <div class="home-section-heading">
          <h2>{{ t('standalone.ui.noteTitle') }}</h2>
          <router-link to="/activity">{{ t('standalone.ui.noteMore') }} ›</router-link>
        </div>
        <a-alert
          v-if="activity.failure"
          type="error"
          show-icon
          :message="errorMessage(activity.failure, t('gamesign.activity.queryFailed'))"
          class="page-alert"
          ><template #action
            ><a-button size="small" :loading="activity.loading" @click="activity.load(true)">{{
              t('standalone.retry')
            }}</a-button></template
          ></a-alert
        >
        <div v-if="activity.loading && !activity.loaded" class="page-state"><a-spin /></div>
        <div v-else-if="noteGames.length" class="home-notes">
          <DailyNote v-for="group in noteGames" :key="group.game" :game="group.game" compact />
        </div>
        <div v-else class="home-note-empty">
          <a-empty :description="t('standalone.ui.notesEmpty')" /><router-link to="/accounts">{{
            t('standalone.accountList')
          }}</router-link>
        </div>
      </section>
      <section class="home-reminders">
        <div class="home-section-heading">
          <h2>{{ t('standalone.activityReminders') }}</h2>
          <router-link to="/calendar">{{ t('standalone.viewCalendar') }} ›</router-link>
        </div>
        <div v-if="events.length" class="home-agenda">
          <article
            v-for="(event, index) in events"
            :key="`${event.title}-${event.startsAt}-${index}`"
          >
            <div>
              <p>
                {{ game?.name }} ·
                {{
                  event.subtitle ||
                  t(
                    event.kind === 'gacha'
                      ? 'standalone.calendarGacha'
                      : 'standalone.calendarActivity'
                  )
                }}
              </p>
              <h3>{{ event.title }}</h3>
              <span class="mono"
                >{{ time(event.status === '即将开始' ? event.startsAt : event.endsAt) }} ·
                {{ t('standalone.beijingTime') }}</span
              >
            </div>
            <a-tag :color="event.status === '即将开始' ? 'blue' : 'gold'">{{ event.status }}</a-tag>
          </article>
        </div>
        <a-empty v-else :description="t('standalone.homeAgendaEmpty')" />
      </section>
    </div>
  </section>
</template>

<style scoped>
.home-overview {
  max-width: 1400px;
  margin: auto;
}
.home-sign-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 22px;
  margin-top: 16px;
  border-radius: 23px;
  background: var(--ant-color-bg-container);
  color: var(--ant-color-text);
}
.sign-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 15px;
  background: var(--ant-color-success-bg);
  color: var(--ant-color-success-text);
  font-size: 23px;
  flex-shrink: 0;
}
.sign-icon--warning {
  color: var(--ant-color-warning-text);
  background: var(--ant-color-warning-bg);
}
.home-sign-summary > div {
  flex: 1;
  min-width: 0;
}
.home-sign-summary h2 {
  margin: 0 0 5px;
  font-size: 15px;
  font-weight: 650;
}
.home-sign-summary p,
.home-sign-summary small {
  margin: 0;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
  line-height: 1.6;
}
.home-sign-summary > .anticon {
  color: var(--ant-color-text-tertiary);
  font-size: 13px;
}
.home-details {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 26px;
  margin-top: 24px;
}
.home-details.sign-only {
  grid-template-columns: 1fr;
}
.home-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 13px;
}
.home-section-heading h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 650;
}
.home-section-heading a {
  font-size: 12px;
  min-height: 32px;
  display: flex;
  align-items: center;
}
.home-notes-section,
.home-reminders {
  min-width: 0;
}
.home-notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px;
  align-items: stretch;
}
.home-note-empty,
.home-agenda,
.home-calendar-empty {
  background: var(--ant-color-bg-container);
  padding: 16px 20px;
  border-radius: 24px;
}
.home-calendar-empty {
  margin: 0;
}
.home-note-empty {
  text-align: center;
  padding: 22px;
}
.home-agenda article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--ant-color-border-secondary);
}
.home-agenda article:last-child {
  border: 0;
}
.home-agenda article > div {
  min-width: 0;
}
.home-agenda p,
.home-agenda .mono {
  margin: 0;
  color: var(--ant-color-text-secondary);
  font-size: 11px;
}
.home-agenda h3 {
  font-size: 13px;
  font-weight: 600;
  margin: 6px 0 8px;
  overflow-wrap: anywhere;
}
.home-agenda .ant-tag {
  margin: 0;
  flex-shrink: 0;
  font-size: 11px;
}
@media (max-width: 1000px) {
  .home-details {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .home-sign-summary {
    padding: 15px 16px;
    margin-top: 14px;
    gap: 12px;
  }
  .home-sign-summary h2 {
    font-size: 14px;
  }
  .home-sign-summary p {
    font-size: 11px;
  }
  .home-details {
    gap: 24px;
    margin-top: 20px;
  }
}
</style>
