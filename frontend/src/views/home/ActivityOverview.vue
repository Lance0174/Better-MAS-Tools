<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import { useActivityStore } from '@/stores/activity'
import { usePerformanceStore } from '@/stores/performance'
import { errorMessage } from '@/composables/useCommunityApi'
import DailyNote from './components/DailyNote.vue'

const { t } = useI18n()
const activity = useActivityStore()
const performance = usePerformanceStore()
onMounted(() => {
  void activity.load()
})
const reorder = (groups: typeof activity.groups) => {
  activity.order = groups.map(group => group.game)
}
</script>

<template>
  <section class="activity-overview">
    <header class="page-toolbar">
      <p>{{ t('standalone.noteAccountHint') }}</p>
      <a-button type="primary" :loading="activity.loading" @click="activity.load(true)">{{
        t('gamesign.activity.refresh')
      }}</a-button>
    </header>
    <a-alert
      v-if="activity.failure"
      type="error"
      show-icon
      :message="errorMessage(activity.failure, t('gamesign.activity.queryFailed'))"
      class="page-alert"
    />
    <div v-if="activity.loading && !activity.loaded" class="page-state"><a-spin /></div>
    <a-empty
      v-else-if="!activity.groups.length"
      class="page-state"
      :description="t('gamesign.activity.empty')"
    />
    <a-spin v-else :spinning="activity.loading">
      <draggable
        :model-value="activity.groups"
        item-key="game"
        handle=".activity-drag-handle"
        :animation="performance.isLowPower ? 0 : 180"
        class="note-grid"
        ghost-class="note-ghost"
        @update:model-value="reorder"
      >
        <template #item="{ element }"><DailyNote :game="element.game" draggable /></template>
      </draggable>
    </a-spin>
  </section>
</template>

<style scoped>
.page-toolbar p {
  margin: 0;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
}
.note-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
}
.note-ghost {
  opacity: 0.45;
}
@media (max-width: 900px) {
  .note-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
