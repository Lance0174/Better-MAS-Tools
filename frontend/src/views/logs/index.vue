<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Table as ATable, message } from 'ant-design-vue'
import type { CancelablePromise, LogEntryInfo, LogsOut } from '@/api'
import { assertSuccess, errorMessage } from '@/composables/useCommunityApi'
import { useDiagnosticsApi } from '@/composables/useDiagnosticsApi'

const { t } = useI18n()
const api = useDiagnosticsApi()
const entries = ref<LogEntryInfo[]>([])
const level = ref('all')
const search = ref('')
const paused = ref(false)
const loading = ref(false)
const exporting = ref(false)
const failure = ref('')
const capacity = ref(2000)
const fileAvailable = ref(false)
let disposed = false
let pending: CancelablePromise<LogsOut> | undefined
let timer: ReturnType<typeof setInterval> | undefined
const levels = computed(() => [
  { value: 'all', label: t('standalone.logAllLevels') },
  ...['DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'].map(value => ({
    value,
    label: value,
  })),
])
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return entries.value
    .filter(
      entry =>
        (level.value === 'all' || entry.level === level.value) &&
        (!query ||
          `${entry.requestId} ${entry.module} ${entry.message}`.toLowerCase().includes(query))
    )
    .reverse()
})
const columns = computed(() => [
  { title: t('standalone.logTime'), key: 'time', dataIndex: 'time', width: 180 },
  { title: t('standalone.logLevel'), key: 'level', dataIndex: 'level', width: 100 },
  { title: t('standalone.logModule'), key: 'module', dataIndex: 'module', width: 145 },
  { title: t('standalone.logRequestId'), key: 'requestId', dataIndex: 'requestId', width: 145 },
  { title: t('standalone.logMessage'), key: 'message', dataIndex: 'message' },
])
async function refresh() {
  if (loading.value || disposed) return
  loading.value = true
  try {
    pending = api.list()
    const result = assertSuccess(await pending)
    if (disposed) return
    entries.value = result.data ?? []
    capacity.value = result.capacity ?? 2000
    fileAvailable.value = result.fileAvailable ?? false
    failure.value = ''
  } catch (error) {
    if (!disposed) failure.value = errorMessage(error, t('standalone.logLoadFailed'))
  } finally {
    loading.value = false
    pending = undefined
  }
}
async function download() {
  exporting.value = true
  try {
    const result = assertSuccess(await api.export())
    const url = URL.createObjectURL(
      new Blob([result.content], { type: 'text/plain;charset=utf-8' })
    )
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    message.error(errorMessage(error, t('standalone.logExportFailed')))
  } finally {
    exporting.value = false
  }
}
onMounted(() => {
  void refresh()
  timer = setInterval(() => {
    if (!paused.value && !document.hidden) void refresh()
  }, 3000)
})
onBeforeUnmount(() => {
  disposed = true
  clearInterval(timer)
  pending?.cancel()
})
</script>

<template>
  <section class="logs-page">
    <a-space wrap class="log-toolbar">
      <a-input
        v-model:value="search"
        :placeholder="t('standalone.logSearch')"
        allow-clear
        class="log-search"
      />
      <a-select v-model:value="level" :options="levels" class="log-level-select" />
      <a-button @click="paused = !paused">{{
        t(paused ? 'standalone.logResume' : 'standalone.logPause')
      }}</a-button>
      <a-button :loading="loading" @click="refresh">{{ t('standalone.refresh') }}</a-button>
      <a-button :loading="exporting" @click="download">{{ t('standalone.logExport') }}</a-button>
    </a-space>
    <a-alert v-if="failure" type="error" show-icon :message="failure" />
    <a-alert
      type="info"
      show-icon
      :message="
        t(fileAvailable ? 'standalone.logFileHint' : 'standalone.logCloudHint', { capacity })
      "
    />
    <a-table
      :columns="columns"
      :data-source="filtered"
      row-key="id"
      size="small"
      :pagination="{ pageSize: 50, showSizeChanger: false }"
      :scroll="{ x: 960 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'time'">{{
          new Date(record.time).toLocaleString()
        }}</template>
        <a-tag
          v-else-if="column.key === 'level'"
          :color="
            ['ERROR', 'CRITICAL'].includes(record.level)
              ? 'error'
              : record.level === 'WARNING'
                ? 'warning'
                : 'processing'
          "
          >{{ record.level }}</a-tag
        >
        <pre v-else-if="column.key === 'message'" class="log-message">{{ record.message }}</pre>
      </template>
    </a-table>
  </section>
</template>

<style scoped>
.logs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.log-search {
  width: 280px;
}
.log-level-select {
  width: 130px;
}
.log-message {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
  max-height: 240px;
  overflow-y: auto;
}
</style>
