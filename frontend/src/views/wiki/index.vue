<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined, SearchOutlined, SyncOutlined } from '@ant-design/icons-vue'
import type {
  WikiCountsOut,
  WikiEntryDataOut,
  WikiSearchItemOut,
  WikiStatusDataOut,
} from '@/api'
import { errorMessage } from '@/composables/useCommunityApi'
import { useWikiApi } from '@/composables/useWikiApi'
import { createDebouncer, createSequenceGuard } from '@/utils/asyncGuard'

const { t } = useI18n()
const wikiApi = useWikiApi()
const keyword = ref('')
const searching = ref(false)
const searchError = ref('')
const results = ref<WikiSearchItemOut[]>([])
const entry = ref<WikiEntryDataOut | null>(null)
const entryLoading = ref(false)
const entryError = ref('')
const syncing = ref(false)

type WikiStatus = {
  ready: boolean
  version: string
  updatedAt: string
  counts: WikiCountsOut
  problems: string[]
  message: string
}
const status = ref<WikiStatus>({
  ready: false,
  version: '',
  updatedAt: '',
  counts: {},
  problems: [],
  message: '',
})
// 状态接口的 data 是可选的；缺字段时补默认值，避免模板读 status.problems.length 抛 TypeError。
const applyStatus = (data?: WikiStatusDataOut) => {
  status.value = {
    ready: data?.ready === true,
    version: data?.version ?? '',
    updatedAt: data?.updatedAt ?? '',
    counts: data?.counts ?? {},
    problems: data?.problems ?? [],
    message: data?.message ?? '',
  }
}
// 搜索与资料卡都会先发后到：各自用一个序号守卫，只认最后一次请求；
// 防抖器可整体取消，页面卸载后不再补发检索。
const searchGuard = createSequenceGuard()
const entryGuard = createSequenceGuard()
const searchDebounce = createDebouncer(300)

// 资料库按“同步 → 检索 → 资料卡”三步使用；搜索为空时只显示状态与入口提示。
const kindLabel = computed<Record<string, string>>(() => ({
  character: t('standalone.wikiKindCharacter'),
  weapon: t('standalone.wikiKindWeapon'),
  equipSuit: t('standalone.wikiKindEquipSuit'),
  dungeon: t('standalone.wikiKindDungeon'),
  enemy: t('standalone.wikiKindEnemy'),
}))

const loadStatus = async () => {
  try {
    const response = await wikiApi.status()
    applyStatus(response.data)
  } catch (cause) {
    status.value.message = errorMessage(cause, t('standalone.wikiStatusFailed'))
  }
}

const sync = async (force = false) => {
  if (syncing.value) return
  syncing.value = true
  try {
    const response = await wikiApi.sync(force)
    applyStatus(response.data)
    // 同步失败时后端会把原因放在 message 里，按结果提示而不是一律成功。
    if (status.value.ready) message.success(t('standalone.wikiSyncDone'))
    else message.warning(status.value.message || t('standalone.wikiSyncFailed'))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.wikiSyncFailed')))
  } finally {
    syncing.value = false
  }
}

const search = async () => {
  const query = keyword.value.trim()
  if (!query) {
    results.value = []
    return
  }
  const token = searchGuard.next()
  searching.value = true
  searchError.value = ''
  try {
    const response = await wikiApi.search(query, 20)
    if (!searchGuard.isLatest(token)) return
    results.value = response.data as WikiSearchItemOut[]
  } catch (cause) {
    if (!searchGuard.isLatest(token)) return
    results.value = []
    searchError.value = errorMessage(cause, t('standalone.wikiSearchFailed'))
  } finally {
    if (searchGuard.isLatest(token)) searching.value = false
  }
}

const openEntry = async (item: WikiSearchItemOut) => {
  const token = entryGuard.next()
  entryLoading.value = true
  entryError.value = ''
  try {
    const response = await wikiApi.entry(item.kind, item.id)
    if (!entryGuard.isLatest(token)) return
    entry.value = response.data ?? null
  } catch (cause) {
    if (!entryGuard.isLatest(token)) return
    entry.value = null
    entryError.value = errorMessage(cause, t('standalone.wikiEntryFailed'))
  } finally {
    if (entryGuard.isLatest(token)) entryLoading.value = false
  }
}

watch(keyword, () => searchDebounce.schedule(() => void search()))
onMounted(async () => {
  await loadStatus()
  if (status.value.ready) await search()
})
onUnmounted(() => {
  // 卸载后守卫失效且待触发的防抖被取消：不再发请求，也不再写已销毁的状态。
  searchGuard.dispose()
  entryGuard.dispose()
  searchDebounce.cancel()
})
</script>

<template>
  <section class="wiki-page">
    <header class="page-toolbar">
      <h1 class="page-title">{{ t('standalone.wiki') }}</h1>
      <a-space>
        <a-tag v-if="status.ready" color="green">{{ status.version || t('standalone.wikiReady') }}</a-tag>
        <a-tag v-else color="orange">{{ t('standalone.wikiNotReady') }}</a-tag>
        <a-button :loading="syncing" @click="sync(false)">
          <template #icon><SyncOutlined /></template>{{ t('standalone.wikiSync') }}
        </a-button>
        <a-button :disabled="syncing" @click="sync(true)">
          <template #icon><ReloadOutlined /></template>{{ t('standalone.wikiRebuild') }}
        </a-button>
      </a-space>
    </header>

    <a-alert
      v-if="!status.ready"
      type="info"
      show-icon
      class="glass-surface wiki-hint"
      :message="status.message || t('standalone.wikiNotReadyHint')"
    />
    <a-alert
      v-else-if="status.problems.length"
      type="warning"
      show-icon
      class="glass-surface wiki-hint"
      :message="t('standalone.wikiProblems', { count: status.problems.length })"
      :description="status.problems.slice(0, 5).join('；')"
    />

    <div class="wiki-body">
      <div class="wiki-search">
        <a-input-search
          v-model:value="keyword"
          :placeholder="t('standalone.wikiSearchPlaceholder')"
          :loading="searching"
          allow-clear
          size="large"
          @search="search"
        />
        <a-alert v-if="searchError" type="error" show-icon :message="searchError" class="wiki-hint" />
        <a-empty v-if="!searching && keyword && !results.length && !searchError" :description="t('standalone.wikiNoResult')" />
        <ul v-else class="wiki-result-list">
          <li v-for="item in results" :key="`${item.kind}-${item.id}`">
            <button type="button" class="wiki-result glass-surface" @click="openEntry(item)">
              <img v-if="item.icon" :src="item.icon" alt="" loading="lazy" referrerpolicy="no-referrer" />
              <span class="wiki-result-text">
                <strong>{{ item.name }}</strong>
                <small>{{ kindLabel[item.kind] }}{{ item.subtitle ? ` · ${item.subtitle}` : '' }}</small>
              </span>
            </button>
          </li>
        </ul>
      </div>

      <article class="wiki-entry glass-surface">
        <a-spin :spinning="entryLoading">
          <a-alert v-if="entryError" type="error" show-icon :message="entryError" class="wiki-hint" />
          <a-empty v-else-if="!entry" :description="t('standalone.wikiEntryHint')">
            <template #image><SearchOutlined class="wiki-entry-icon" /></template>
          </a-empty>
          <template v-else>
            <header class="wiki-entry-header">
              <img v-if="entry.icon" :src="entry.icon" alt="" referrerpolicy="no-referrer" />
              <div>
                <h2>{{ entry.name }}</h2>
                <p v-if="entry.subtitle">{{ entry.subtitle }}</p>
                <a-space v-if="entry.tags?.length" wrap>
                  <a-tag v-for="tag in entry.tags" :key="tag">{{ tag }}</a-tag>
                </a-space>
              </div>
            </header>
            <section v-for="section in entry.sections" :key="section.title" class="wiki-section">
              <h3 class="section-title">{{ section.title }}</h3>
              <dl v-if="section.fields?.length" class="wiki-fields">
                <template v-for="field in section.fields" :key="field.label">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value || '—' }}</dd>
                </template>
              </dl>
              <div v-if="section.table?.columns?.length" class="wiki-table-scroll">
                <table class="wiki-table">
                  <thead>
                    <tr>
                      <th v-for="column in section.table.columns" :key="column">{{ column }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, index) in section.table.rows" :key="index">
                      <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell || '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </template>
        </a-spin>
      </article>
    </div>
  </section>
</template>

<style scoped>
.wiki-page {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.wiki-hint {
  margin-bottom: 16px;
}
.wiki-body {
  display: grid;
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: 20px;
  align-items: start;
  min-height: 0;
}
.wiki-result-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 60vh;
  overflow-y: auto;
}
.wiki-result {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  color: var(--ant-color-text);
  font: inherit;
}
.wiki-result:hover {
  border-color: var(--ant-color-primary);
}
.wiki-result img {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 8px;
  flex: 0 0 auto;
}
.wiki-result-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.wiki-result-text small {
  color: var(--ant-color-text-secondary);
}
.wiki-entry {
  padding: 16px 18px;
  min-height: 320px;
  border-radius: 14px;
}
.wiki-entry-icon {
  font-size: 36px;
  color: var(--ant-color-text-tertiary);
}
.wiki-entry-header {
  display: flex;
  gap: 14px;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-glass-border-body);
}
.wiki-entry-header img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 12px;
}
.wiki-entry-header h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: 0.03em;
}
.wiki-entry-header p {
  margin: 2px 0 6px;
  color: var(--ant-color-text-secondary);
}
.wiki-fields {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 16px;
  margin: 0;
}
.wiki-fields dt {
  color: var(--ant-color-text-secondary);
}
.wiki-fields dd {
  margin: 0;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-variant-numeric: tabular-nums;
}
.wiki-table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
}
/* 资料卡表格列多且是等宽字体，窄屏会撑破玻璃卡片，交给容器横向滚动。 */
.wiki-table-scroll {
  max-width: 100%;
  overflow-x: auto;
}
.wiki-table-scroll .wiki-table {
  min-width: 520px;
}
.wiki-table th,
.wiki-table td {
  border: 1px solid var(--app-glass-border-body);
  padding: 4px 8px;
  text-align: left;
}
.wiki-table th {
  color: var(--ant-color-text-secondary);
  font-weight: 600;
}
@media (max-width: 900px) {
  .wiki-body {
    grid-template-columns: 1fr;
  }
}
</style>
