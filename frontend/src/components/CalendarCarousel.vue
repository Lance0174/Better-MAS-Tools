<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { WikiCalendarGameOut } from '@/api'
import { gameBackground } from '@/utils/communityDashboard'

const props = withDefaults(
  defineProps<{ groups: WikiCalendarGameOut[]; game: string; autoplay?: boolean }>(),
  { autoplay: true }
)
const emit = defineEmits<{ 'update:game': [game: string] }>()
const { t, locale } = useI18n()
const paused = ref(false)
const hovered = ref(false)
const focused = ref(false)
const imageIndex = ref(0)
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
const images = computed(() => [
  ...new Set(
    [current.value?.cover, event.value?.banner, gameBackground(current.value?.game || '')].filter(
      (item): item is string => Boolean(item)
    )
  ),
])
const artwork = computed(() => images.value[imageIndex.value])
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
watch(
  () => current.value?.game,
  () => {
    imageIndex.value = 0
  }
)
watch(images, () => {
  imageIndex.value = 0
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
    <div class="carousel-toolbar">
      <div class="carousel-games">
        <button
          v-for="group in groups"
          :key="group.game"
          type="button"
          :aria-current="group.game === current.game ? 'true' : undefined"
          @click="emit('update:game', group.game)"
        >
          {{ group.name || group.game }}
        </button>
      </div>
      <a-button
        size="small"
        :disabled="!autoplay || groups.length < 2"
        :aria-pressed="paused"
        @click="paused = !paused"
        >{{
          t(
            !autoplay || groups.length < 2
              ? 'standalone.carouselSingle'
              : paused
                ? 'standalone.carouselResume'
                : 'standalone.carouselPause'
          )
        }}</a-button
      >
    </div>
    <div class="calendar-banner" :data-banner-game="current.game">
      <img
        v-if="artwork"
        :key="artwork"
        class="calendar-background"
        :src="artwork"
        alt=""
        referrerpolicy="no-referrer"
        decoding="async"
        @error="imageIndex++"
      />
      <div class="banner-scrim" />
      <div class="banner-caption">
        <p class="banner-kicker">{{ current.name }} / {{ t('standalone.calendar') }}</p>
        <h2>{{ event?.title || current.versionName || current.version || current.name }}</h2>
        <p>{{ event?.subtitle || current.message || t('standalone.calendarEmpty') }}</p>
        <p v-if="time">{{ time }} · {{ t('standalone.beijingTime') }}</p>
        <span v-if="event?.status" class="banner-status">{{ event.status }}</span>
        <span
          v-if="current.source === 'cache' || current.source === 'stale-cache'"
          class="banner-source"
          >{{
            t(
              current.source === 'cache'
                ? 'standalone.calendarSourceCache'
                : 'standalone.calendarSourceStale'
            )
          }}</span
        >
      </div>
      <div class="carousel-controls">
        <button
          type="button"
          :disabled="groups.length < 2"
          :aria-label="t('standalone.carouselPrevious')"
          @click="select(-1)"
        >
          ←</button
        ><span class="mono"
          >{{ String(index + 1).padStart(2, '0') }} /
          {{ String(groups.length).padStart(2, '0') }}</span
        ><button
          type="button"
          :disabled="groups.length < 2"
          :aria-label="t('standalone.carouselNext')"
          @click="select(1)"
        >
          →
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.activity-carousel {
  margin-bottom: 24px;
  min-width: 0;
}
.carousel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.carousel-games {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
  overflow: auto;
  scrollbar-width: thin;
}
.carousel-games button {
  padding: 8px 0;
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--ant-color-text-secondary);
  font: inherit;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.carousel-games button[aria-current] {
  color: var(--ant-color-text);
  border-bottom-color: var(--ant-color-primary);
}
.calendar-banner {
  height: 244px;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border: 1px solid var(--ant-color-border);
  border-radius: 3px;
  background: #182026;
  color: #f8fafc;
}
.calendar-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 42%;
  z-index: 0;
}
.banner-scrim {
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(90deg, #0a1118eb, #0a1118b8 32%, #0a11181a 78%),
    linear-gradient(0deg, #0a111894, transparent 65%);
}
.banner-caption {
  position: absolute;
  z-index: 2;
  left: 32px;
  bottom: 28px;
  max-width: calc(100% - 220px);
}
.banner-kicker {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #d2dbe1;
}
.banner-caption h2 {
  margin: 8px 0;
  font-size: 28px;
  line-height: 1.3;
  font-weight: 650;
  color: #f8fafc;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.banner-caption p {
  margin: 4px 0;
  font-size: 12px;
  color: #e1e6ea;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.banner-status,
.banner-source {
  display: inline-block;
  font-size: 11px;
  margin-top: 16px;
  margin-right: 16px;
}
.banner-status {
  color: #b6eed1;
}
.carousel-controls {
  position: absolute;
  z-index: 2;
  bottom: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11px;
}
.carousel-controls button {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid #f4f7fa70;
  color: #f8fafc;
  background: #10182070;
  border-radius: 3px;
  font-size: 17px;
  cursor: pointer;
}
.carousel-controls button:disabled {
  opacity: 0.4;
  cursor: default;
}
button:focus-visible {
  outline: 2px solid var(--ant-color-primary);
  outline-offset: 3px;
}
@media (max-width: 700px) {
  .carousel-toolbar {
    gap: 12px;
    align-items: flex-end;
  }
  .carousel-games {
    gap: 15px;
    flex: 1;
  }
  .carousel-games button {
    font-size: 11px;
  }
  .carousel-toolbar > .ant-btn {
    font-size: 10px;
  }
  .calendar-banner {
    height: 244px;
  }
  .calendar-background {
    object-position: 58% center;
  }
  .banner-scrim {
    background:
      linear-gradient(90deg, #0a1118e0, #0a111866), linear-gradient(0deg, #0a1118b3, transparent);
  }
  .banner-caption {
    left: 20px;
    bottom: 58px;
    max-width: calc(100% - 40px);
  }
  .banner-caption h2 {
    font-size: 21px;
  }
  .banner-caption p {
    font-size: 10px;
  }
  .banner-status,
  .banner-source {
    margin-top: 8px;
    font-size: 10px;
  }
  .carousel-controls {
    bottom: 16px;
    right: 16px;
    gap: 8px;
    font-size: 9px;
  }
  .carousel-controls button {
    width: 28px;
    height: 28px;
  }
}
</style>
