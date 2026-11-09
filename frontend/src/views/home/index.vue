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
import { GAME_NAMES, homeSignRows } from '@/utils/communityDashboard'

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
const gameName = computed(
  () =>
    GAME_NAMES[activeGame.value] ||
    game.value?.name ||
    activity.groups[0]?.game ||
    Object.values(status.value?.results ?? {}).flatMap(accounts =>
      accounts.flatMap(account => account.games ?? [])
    )[0]?.game ||
    ''
)
const rows = computed(() =>
  homeSignRows(status.value?.results ?? {}, gameName.value, status.value?.today ?? '')
)
const completed = computed(() => rows.value.filter(row => row.state === 'success').length)
const events = computed(() =>
  filterAndSortActivities(game.value?.activities ?? [], {
    statusFilter: 'active',
    sortBy: 'endsAt',
    hidePermanent: false,
  }).slice(0, 3)
)
const note = computed(() => activity.current(gameName.value))
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
    <div class="home-section-heading">
      <h2>{{ t('standalone.calendar') }}</h2>
      <router-link to="/calendar">{{ t('standalone.viewCalendar') }} ↗</router-link>
    </div>
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
    <a-empty v-else :description="t('standalone.calendarEmpty')" class="page-state" />

    <div
      class="home-community"
      :class="{ 'home-community--sign-only': settings.data?.ActivityEnabled === false }"
    >
      <section class="home-sign">
        <header>
          <h2>{{ t('standalone.homeSignResults') }}</h2>
          <span>{{ t('standalone.signCompleted', { count: completed, total: rows.length }) }}</span>
        </header>
        <a-alert
          v-if="statusFailure"
          type="error"
          show-icon
          :message="errorMessage(statusFailure, t('standalone.loadFailed'))"
        />
        <div v-if="statusLoading && !status" class="page-state"><a-spin /></div>
        <div v-else-if="rows.length" class="home-sign-rows">
          <article v-for="row in rows" :key="row.key" class="home-sign-row">
            <div>
              <strong>{{ row.name }}</strong
              ><span>{{ row.platform }}</span>
            </div>
            <a-tag
              :color="
                row.state === 'success' ? 'success' : row.state === 'error' ? 'error' : 'default'
              "
              >{{ row.status || t('standalone.todayPending') }}</a-tag
            >
            <p :class="{ 'sign-error': row.state === 'error' }">
              {{ row.reason || row.reward || t('standalone.todayPending') }}
            </p>
          </article>
        </div>
        <a-empty v-else :description="t('standalone.noResult')" class="home-sign-empty" />
        <footer>
          <router-link to="/sign">{{ t('standalone.openSign') }}</router-link
          ><span v-if="settings.data?.ScheduledRun">{{
            t('standalone.dailyPlan', { time: settings.data.ScheduledTime || '' })
          }}</span>
        </footer>
      </section>
      <section v-if="settings.data?.ActivityEnabled !== false" class="home-note">
        <a-alert
          v-if="activity.failure"
          type="error"
          show-icon
          :message="errorMessage(activity.failure, t('gamesign.activity.queryFailed'))"
          ><template #action
            ><a-button size="small" :loading="activity.loading" @click="activity.load(true)">{{
              t('standalone.retry')
            }}</a-button></template
          ></a-alert
        >
        <div v-if="activity.loading && !activity.loaded" class="page-state"><a-spin /></div>
        <DailyNote v-else-if="note" :game="gameName" compact />
        <div v-else class="home-note-empty">
          <a-empty :description="t('standalone.homeNoteEmpty')" /><router-link to="/sign">{{
            t('standalone.accountList')
          }}</router-link>
        </div>
      </section>
    </div>
    <div class="home-section-heading">
      <h2>{{ game?.name }} · {{ t('standalone.activityReminders') }}</h2>
      <span>{{ t('standalone.beijingTime') }}</span>
    </div>
    <div v-if="events.length" class="home-agenda">
      <article v-for="(event, index) in events" :key="`${event.title}-${event.startsAt}-${index}`">
        <p>
          {{
            event.subtitle ||
            t(event.kind === 'gacha' ? 'standalone.calendarGacha' : 'standalone.calendarActivity')
          }}
        </p>
        <h3>{{ event.title }}</h3>
        <div>
          <span class="mono">{{
            time(event.status === '即将开始' ? event.startsAt : event.endsAt)
          }}</span
          ><a-tag :color="event.status === '即将开始' ? 'blue' : 'gold'">{{ event.status }}</a-tag>
        </div>
      </article>
    </div>
    <a-empty v-else :description="t('standalone.homeAgendaEmpty')" />
  </section>
</template>

<style scoped>
.home-overview {
  max-width: 1440px;
  margin: 0 auto;
}
.home-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ant-color-border);
}
.home-section-heading h2 {
  margin: 0;
  font-size: 19px;
  font-weight: 650;
}
.home-section-heading > a,
.home-section-heading > span {
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.home-community {
  display: grid;
  grid-template-columns: minmax(250px, 0.9fr) minmax(0, 1.7fr);
  gap: 20px;
  margin-bottom: 28px;
}
.home-community--sign-only {
  grid-template-columns: minmax(0, 1fr);
}
.home-sign {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--ant-color-bg-container);
  border: 1px solid var(--ant-color-border);
  border-radius: 3px;
}
.home-sign > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 15px 20px;
  border-bottom: 1px solid var(--ant-color-border);
}
.home-sign h2 {
  font-size: 14px;
  margin: 0;
}
.home-sign > header > span {
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.home-sign-rows {
  padding: 0 20px;
  flex: 1;
  max-height: 360px;
  overflow: auto;
}
.home-sign-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 5px 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--ant-color-border-secondary);
}
.home-sign-row:last-child {
  border: 0;
}
.home-sign-row > div {
  display: flex;
  gap: 9px;
  align-items: baseline;
  flex-wrap: wrap;
}
.home-sign-row strong {
  font-size: 13px;
  font-weight: 600;
}
.home-sign-row > div > span {
  font-size: 10px;
  color: var(--ant-color-text-secondary);
}
.home-sign-row p {
  grid-column: 1/-1;
  margin: 0;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
  overflow-wrap: anywhere;
}
.home-sign-row p.sign-error {
  color: var(--app-danger-ink);
}
.home-sign-row .ant-tag {
  margin: 0;
  font-size: 10px;
}
.home-sign-empty {
  padding: 20px 0;
  flex: 1;
}
.home-sign footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
  padding: 13px 20px;
  border-top: 1px solid var(--ant-color-border);
  font-size: 11px;
}
.home-sign footer span {
  font-size: 10px;
  color: var(--ant-color-text-secondary);
}
.home-note {
  min-width: 0;
}
.home-note-empty {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 24px;
  border: 1px solid var(--ant-color-border);
  background: var(--ant-color-bg-container);
  height: 100%;
  min-height: 264px;
}
.home-agenda {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.home-agenda article {
  background: var(--ant-color-bg-container);
  border: 1px solid var(--ant-color-border);
  padding: 16px;
  min-width: 0;
}
.home-agenda p {
  margin: 0;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.home-agenda h3 {
  font-size: 13px;
  margin: 6px 0 17px;
  overflow-wrap: anywhere;
}
.home-agenda article > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
}
.home-agenda .ant-tag {
  margin: 0;
}
@media (max-width: 1180px) {
  .home-community {
    grid-template-columns: minmax(240px, 0.95fr) minmax(0, 1.3fr);
    gap: 16px;
  }
}
@media (max-width: 900px) {
  .home-community {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 700px) {
  .home-agenda {
    grid-template-columns: minmax(0, 1fr);
  }
  .home-section-heading h2 {
    font-size: 17px;
  }
}
</style>
