<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LeftOutlined, RightOutlined } from '@ant-design/icons-vue'
import type { WikiCalendarRowOut } from '@/api'
import { beijingDay, occursOnDay } from './calendarDays'

const props = defineProps<{ events: WikiCalendarRowOut[]; value: string }>()
const emit = defineEmits<{ 'update:value': [value: string] }>()
const { t, locale } = useI18n()
const today = beijingDay()
const month = ref(today.slice(0, 7))
const first = computed(() => new Date(`${month.value}-01T00:00:00Z`))
const title = computed(() =>
  first.value.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', timeZone: 'UTC' })
)
const cells = computed(() => {
  const start = (first.value.getUTCDay() + 6) % 7
  const count = new Date(
    Date.UTC(first.value.getUTCFullYear(), first.value.getUTCMonth() + 1, 0)
  ).getUTCDate()
  return Array.from({ length: Math.ceil((start + count) / 7) * 7 }, (_, index) => {
    const number = index - start + 1
    const day = `${month.value}-${String(number).padStart(2, '0')}`
    return number > 0 && number <= count
      ? { number, day, hasEvent: props.events.some(event => occursOnDay(event, day)) }
      : null
  })
})
const move = (offset: number) => {
  const date = new Date(
    Date.UTC(first.value.getUTCFullYear(), first.value.getUTCMonth() + offset, 1)
  )
  month.value = date.toISOString().slice(0, 7)
  emit('update:value', '')
}
const selectToday = () => {
  month.value = today.slice(0, 7)
  emit('update:value', today)
}
</script>

<template>
  <section class="month-calendar">
    <header>
      <strong>{{ title }}</strong>
      <div>
        <a-button type="text" :aria-label="t('standalone.ui.monthPrevious')" @click="move(-1)"
          ><LeftOutlined /></a-button
        ><a-button type="text" :aria-label="t('standalone.ui.monthNext')" @click="move(1)"
          ><RightOutlined
        /></a-button>
      </div>
    </header>
    <div class="weekdays">
      <span v-for="day in t('standalone.ui.weekdays').split(' ')" :key="day">{{ day }}</span>
    </div>
    <div class="month-days">
      <template v-for="(cell, index) in cells" :key="index"
        ><button
          v-if="cell"
          type="button"
          :class="{ 'has-event': cell.hasEvent, today: cell.day === today }"
          :aria-label="cell.day"
          :aria-pressed="value === cell.day"
          @click="emit('update:value', value === cell.day ? '' : cell.day)"
        >
          {{ cell.number }}</button
        ><span v-else
      /></template>
    </div>
    <footer>
      <span>{{
        value ? t('standalone.ui.selectedDay', { date: value }) : t('standalone.calendarAll')
      }}</span
      ><a-button type="link" size="small" @click="selectToday">{{
        t('standalone.ui.today')
      }}</a-button
      ><a-button v-if="value" type="link" size="small" @click="emit('update:value', '')">{{
        t('standalone.calendarAll')
      }}</a-button>
    </footer>
  </section>
</template>

<style scoped>
.month-calendar {
  background: var(--ant-color-bg-container);
  padding: 20px;
  border-radius: 24px;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
header strong {
  font-size: 18px;
  font-weight: 650;
}
.weekdays,
.month-days {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  text-align: center;
  gap: 4px;
}
.weekdays {
  color: var(--ant-color-text-secondary);
  font-size: 11px;
  padding: 8px 0;
}
.month-days button {
  position: relative;
  min-height: 36px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: var(--ant-color-text);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.month-days button.today {
  color: var(--ant-color-link);
  font-weight: 650;
}
.month-days button.has-event::after {
  content: '';
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--ant-color-link);
  position: absolute;
  bottom: 3px;
  left: calc(50% - 1.5px);
}
.month-days button[aria-pressed='true'] {
  background: var(--ant-color-primary);
  color: #fff;
}
.month-days button[aria-pressed='true']::after {
  background: #fff;
}
footer {
  display: flex;
  align-items: center;
  margin-top: 10px;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
footer > span {
  flex: 1;
}
</style>
