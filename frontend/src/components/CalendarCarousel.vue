<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { WikiCalendarGameOut } from '@/api'
import GameArtwork from '@/components/GameArtwork.vue'

const props = withDefaults(
  defineProps<{ groups: WikiCalendarGameOut[]; game: string; autoplay?: boolean }>(),
  { autoplay: true }
)
const emit = defineEmits<{ 'update:game': [game: string] }>()
const { t, locale } = useI18n()
const paused = ref(false)
const hovered = ref(false)
const focused = ref(false)
const index = computed(() =>
  Math.max(
    0,
    props.groups.findIndex(group => group.game === props.game)
  )
)
const current = computed(() => props.groups[index.value])
const event = computed(
  () =>
    current.value?.activities?.find(item => ['进行中', '即将开始'].includes(item.status || '')) ??
    current.value?.activities?.[0]
)
const time = computed(() => {
  const value = event.value?.status === '即将开始' ? event.value.startsAt : event.value?.endsAt
  const date = new Date(value || '')
  if (Number.isNaN(date.getTime())) return ''
  const formatted = date.toLocaleString(locale.value, {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  return t(
    event.value?.status === '即将开始' ? 'standalone.calendarFrom' : 'standalone.calendarUntil',
    { time: formatted }
  )
})
function select(offset: number) {
  if (props.groups.length < 2) return
  emit(
    'update:game',
    props.groups[(index.value + offset + props.groups.length) % props.groups.length].game
  )
}
function focusOut(event: FocusEvent) {
  focused.value =
    event.relatedTarget instanceof Node &&
    Boolean(
      event.currentTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)
    )
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (!props.autoplay || paused.value || hovered.value || focused.value || document.hidden) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (document.activeElement?.closest('[role="dialog"], .note-account')) return
    select(1)
  }, 6500)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <section
    v-if="current"
    class="activity-carousel"
    :aria-label="t('standalone.calendarCarousel')"
    @pointerenter="hovered = true"
    @pointerleave="hovered = false"
    @focusin="focused = true"
    @focusout="focusOut"
  >
    <div class="calendar-banner" :data-banner-game="current.game">
      <GameArtwork
        class="calendar-background"
        :game="current.game"
        :cover="current.cover"
        :banner="event?.banner"
        prefer-cover
      />
      <div class="banner-scrim" />
      <div class="banner-caption">
        <div class="banner-top">
          <span class="banner-kicker"
            >{{ current.name || current.game }} · {{ t('standalone.calendar') }}</span
          >
          <button
            class="carousel-pause"
            type="button"
            :disabled="!autoplay || groups.length < 2"
            :aria-pressed="paused"
            @click="paused = !paused"
          >
            {{ t(paused ? 'standalone.carouselResume' : 'standalone.carouselPause') }}
          </button>
        </div>
        <h2>{{ event?.title || current.versionName || current.version || current.name }}</h2>
        <p>{{ event?.subtitle || current.message || t('standalone.calendarEmpty') }}</p>
        <p v-if="time">{{ time }} · {{ t('standalone.beijingTime') }}</p>
        <div class="banner-bottom">
          <div class="banner-labels">
            <span v-if="event?.status">{{ event.status }}</span
            ><span v-if="current.source === 'cache' || current.source === 'stale-cache'">{{
              t(
                current.source === 'cache'
                  ? 'standalone.calendarSourceCache'
                  : 'standalone.calendarSourceStale'
              )
            }}</span>
          </div>
          <div class="carousel-dots">
            <button
              v-for="group in groups"
              :key="group.game"
              type="button"
              :aria-label="group.name || group.game"
              :aria-current="group.game === current.game ? 'true' : undefined"
              @click="emit('update:game', group.game)"
            />
          </div>
          <button
            type="button"
            class="carousel-next"
            :disabled="groups.length < 2"
            :aria-label="t('standalone.carouselNext')"
            @click="select(1)"
          >
            →
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.activity-carousel {
  min-width: 0;
}
.calendar-banner {
  height: 280px;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: 24px;
  background: #263744;
  color: #fff;
}
.calendar-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 38%;
  z-index: 0;
}
.banner-scrim {
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(105deg, #101922ad, #10192210), linear-gradient(0deg, #0b1723e8, transparent 85%);
}
.banner-caption {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 24px 28px;
  height: 100%;
}
.banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}
.banner-kicker {
  font-size: 12px;
  padding: 5px 8px;
  border-radius: 9px;
  background: #ffffff1f;
  border: 1px solid #ffffff32;
}
.carousel-pause {
  font: inherit;
  font-size: 11px;
  color: #fff;
  border: 0;
  background: transparent;
  min-height: 32px;
  cursor: pointer;
}
.banner-caption h2 {
  margin: auto 0 8px;
  color: #fff;
  font-size: 28px;
  font-weight: 650;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.banner-caption p {
  margin: 3px 0;
  font-size: 12px;
  color: #ffffffde;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.banner-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  margin-top: 12px;
}
.banner-labels {
  display: flex;
  gap: 10px;
  font-size: 11px;
}
.carousel-dots {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.carousel-dots button {
  position: relative;
  width: 18px;
  height: 28px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.carousel-dots button::after {
  content: '';
  position: absolute;
  left: 6px;
  top: 12px;
  width: 5px;
  height: 5px;
  border-radius: 8px;
  background: #ffffff70;
}
.carousel-dots button[aria-current]::after {
  width: 15px;
  left: 1px;
  background: #fff;
}
.carousel-next {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  color: #fff;
  background: #ffffff26;
  cursor: pointer;
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
@media (max-width: 700px) {
  .calendar-banner {
    height: 192px;
  }
  .banner-caption {
    padding: 14px 18px;
  }
  .banner-caption h2 {
    font-size: 23px;
    margin-bottom: 4px;
  }
  .banner-caption p {
    font-size: 11px;
  }
  .banner-bottom {
    margin-top: 4px;
  }
  .banner-kicker {
    font-size: 10px;
  }
}
@media (max-width: 350px) {
  .calendar-banner {
    height: 184px;
  }
  .banner-caption h2 {
    font-size: 21px;
  }
  .carousel-dots {
    gap: 0;
  }
}
</style>
