<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import {
  Table as ATable,
  InputNumber as AInputNumber,
  Pagination as APagination,
  message,
} from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { AccountOut, GachaRecord, GachaRecordsOut, GachaUpdateOut } from '@/api'
import { useGachaApi } from '@/composables/useGachaApi'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { isAndroidLocal } from '@/services/android'
import { saveTextFile } from '@/utils/download'

const { t } = useI18n()
const api = useGachaApi()
const accountsApi = useCommunityApi()
const game = ref<GachaRecord['game']>('genshin')
const player = ref('')
const pool = ref('')
const page = ref(1)
const data = ref<GachaRecordsOut>({ data: [], total: 0, players: [], pools: [] })
const accounts = ref<AccountOut[]>([])
const importing = ref(false)
const loading = ref(false)
const error = ref('')
const warnings = ref<string[]>([])
const fetchOpen = ref(false)
const source = ref('')
const accountId = ref('')
const playerUid = ref('')
const timezone = ref(8)
const maxPages = ref(100)
const fileInput = ref<HTMLInputElement | null>(null)
let generation = 0
const games = computed(() =>
  ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights', 'endfield'].map(value => ({
    value,
    label: t(`standalone.gachaGames.${value}`),
  }))
)
const players = computed(() => [
  { value: '', label: t('standalone.allPlayers') },
  ...(data.value.players ?? []).map(value => ({ value, label: value })),
])
const pools = computed(() => [
  { value: '', label: t('standalone.allPools') },
  ...Array.from(
    new Map(
      (data.value.pools ?? []).map(item => [
        item.poolType,
        { value: item.poolType, label: item.poolName },
      ])
    ).values()
  ),
])
const sklandAccounts = computed(() =>
  accounts.value
    .filter(item => item.data.SklandToken)
    .map(item => ({ value: item.uid, label: item.data.Name }))
)
const supportsUigf = computed(() => ['genshin', 'starrail', 'zzz'].includes(game.value))
const columns = computed(() => [
  { title: t('standalone.gachaTime'), dataIndex: 'time', width: 190 },
  { title: t('standalone.gachaItem'), dataIndex: 'name' },
  { title: t('standalone.gachaRarity'), dataIndex: 'rarity', width: 90 },
  { title: t('standalone.gachaPool'), key: 'pool', width: 200 },
  { title: 'UID', dataIndex: 'playerUid', width: 150 },
])
const keyOf = (item: GachaRecord) => [item.game, item.playerUid, item.poolType, item.id].join(':')
const load = async () => {
  const current = ++generation
  loading.value = true
  try {
    const response = await api.list(game.value, player.value, pool.value, page.value)
    if (current === generation) {
      data.value = response
      error.value = ''
    }
  } catch (cause) {
    if (current === generation) error.value = errorMessage(cause, t('standalone.loadFailed'))
  } finally {
    if (current === generation) loading.value = false
  }
}
const refresh = () => {
  page.value = 1
  void load()
}
watch(game, () => {
  player.value = ''
  pool.value = ''
  warnings.value = []
  refresh()
})
watch(fetchOpen, open => {
  if (!open) source.value = ''
})
onBeforeUnmount(() => {
  generation++
  source.value = ''
})
onMounted(async () => {
  await load()
  try {
    accounts.value = (await accountsApi.listAccounts()).data
  } catch (cause) {
    error.value = errorMessage(cause, t('standalone.loadFailed'))
  }
})
const finish = async (response: GachaUpdateOut) => {
  warnings.value = response.warnings ?? []
  const text = t('standalone.gachaAdded', {
    added: response.added ?? 0,
    fetched: response.fetched ?? 0,
  })
  if (warnings.value.length) message.warning(text)
  else message.success(text)
  await load()
}
const fetchRecords = async () => {
  importing.value = true
  try {
    const response = await api.fetch({
      game: game.value,
      source: source.value,
      accountId: accountId.value,
      playerUid: playerUid.value,
      timezone: timezone.value,
      maxPages: maxPages.value,
    })
    fetchOpen.value = false
    await finish(response)
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaFetchFailed')))
  } finally {
    importing.value = false
    source.value = ''
  }
}
const importFile = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    if (file.size > 20_000_000) throw new Error(t('standalone.gachaFileTooLarge'))
    await finish(await api.import(game.value, await file.text()))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaImportFailed')))
  } finally {
    importing.value = false
    input.value = ''
  }
}
const exportFile = async (format: 'bmasc' | 'uigf') => {
  importing.value = true
  try {
    const response = await api.export(game.value, player.value, format)
    await saveTextFile(response.filename, response.content)
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaExportFailed')))
  } finally {
    importing.value = false
  }
}
const changePage = (value: { current?: number }) => {
  page.value = value.current ?? 1
  void load()
}
</script>

<template>
  <section class="gacha-page">
    <header class="page-toolbar">
      <h1 class="page-title">{{ t('standalone.gacha') }}</h1>
      <a-space wrap>
        <a-button :disabled="importing" @click="fileInput?.click()">{{
          t('standalone.gachaImport')
        }}</a-button>
        <a-button :disabled="importing || !data.total" @click="exportFile('bmasc')">{{
          t('standalone.gachaExport')
        }}</a-button>
        <a-button
          v-if="supportsUigf"
          :disabled="importing || !data.total"
          @click="exportFile('uigf')"
          >{{ t('standalone.gachaUigf') }}</a-button
        >
        <a-button type="primary" :loading="importing" @click="fetchOpen = true">{{
          t('standalone.gachaFetch')
        }}</a-button>
      </a-space>
    </header>
    <input
      ref="fileInput"
      type="file"
      accept=".json,application/json"
      hidden
      @change="importFile"
    />
    <div class="gacha-filters">
      <a-select
        v-model:value="game"
        :options="games"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.gachaGame')"
      />
      <a-select
        v-model:value="player"
        :options="players"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.allPlayers')"
        @change="refresh"
      />
      <a-select
        v-model:value="pool"
        :options="pools"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.allPools')"
        @change="refresh"
      />
    </div>
    <a-alert type="info" show-icon :message="t('standalone.gachaHistoryHint')" class="page-alert" />
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
    <a-alert
      v-for="warning in warnings"
      :key="warning"
      type="warning"
      show-icon
      :message="warning"
      class="page-alert"
    />
    <div class="gacha-summary">
      <article v-for="summary in data.pools" :key="summary.poolName" class="gacha-pool">
        <strong>{{ summary.poolName }}</strong>
        <span>{{
          t('standalone.gachaPoolSummary', {
            total: summary.total,
            top: summary.topRarity,
            count: summary.topCount,
            since: summary.sinceTop,
          })
        }}</span>
      </article>
    </div>
    <a-spin v-if="isAndroidLocal" :spinning="loading || importing">
      <div class="mobile-records">
        <a-empty v-if="!data.total" />
        <article v-for="record in data.data" :key="keyOf(record)" class="mobile-record">
          <div>
            <strong>{{ record.name }}</strong
            ><a-tag color="blue">{{ record.rarity }} ★</a-tag>
          </div>
          <span>{{ record.poolName || record.poolType }} · {{ record.time }}</span>
          <small>UID {{ record.playerUid }}</small>
        </article>
      </div>
      <a-pagination
        v-if="data.total"
        :current="page"
        :page-size="50"
        :total="data.total"
        simple
        @change="value => changePage({ current: value })"
      />
    </a-spin>
    <a-table
      v-else
      :columns="columns"
      :data-source="data.data"
      :row-key="keyOf"
      :loading="loading || importing"
      :pagination="{ current: page, pageSize: 50, total: data.total, showSizeChanger: false }"
      :scroll="{ x: 800 }"
      @change="changePage"
    >
      <template #bodyCell="{ column, record }"
        ><template v-if="column.key === 'pool'">{{
          record.poolName || record.poolType
        }}</template></template
      >
    </a-table>
    <a-modal
      :open="fetchOpen"
      :title="t('standalone.gachaFetch')"
      :confirm-loading="importing"
      :closable="!importing"
      :mask-closable="!importing"
      @cancel="fetchOpen = false"
      @ok="fetchRecords"
    >
      <a-form
        layout="vertical"
        :model="{ source, playerUid, accountId, timezone, maxPages }"
        :disabled="importing"
      >
        <a-alert
          type="info"
          show-icon
          :message="t(`standalone.gachaHints.${game}`)"
          class="page-alert"
        />
        <a-form-item
          v-if="game === 'arknights' || game === 'endfield'"
          name="accountId"
          :label="t('standalone.skland')"
          :required="!source"
          ><a-select v-model:value="accountId" :options="sklandAccounts" allow-clear
        /></a-form-item>
        <a-form-item
          v-if="game !== 'arknights'"
          name="source"
          :label="t('standalone.gachaSource')"
          :required="game !== 'endfield' || !accountId"
          ><a-textarea v-model:value="source" :rows="3" autocomplete="off"
        /></a-form-item>
        <a-form-item
          v-if="game === 'arknights' || game === 'endfield'"
          name="playerUid"
          label="UID"
          required
          ><a-input v-model:value="playerUid" autocomplete="off"
        /></a-form-item>
        <a-form-item v-if="supportsUigf" name="timezone" :label="t('standalone.gachaTimezone')"
          ><a-input-number v-model:value="timezone" :min="-12" :max="14"
        /></a-form-item>
        <a-form-item
          v-if="game !== 'wuthering'"
          name="maxPages"
          :label="t('standalone.gachaMaxPages')"
          ><a-input-number v-model:value="maxPages" :min="1" :max="500"
        /></a-form-item>
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.gacha-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.gacha-select {
  width: 220px;
}
.gacha-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.gacha-pool {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--ant-color-primary-bg);
  border: 1px solid var(--ant-color-primary-border);
  border-radius: 8px;
}
.gacha-pool span {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.mobile-records {
  min-height: 120px;
  margin-bottom: 16px;
}
.mobile-record {
  padding: 12px 0;
  border-bottom: 1px solid var(--ant-color-border-secondary);
  overflow-wrap: anywhere;
}
.mobile-record > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.mobile-record > span,
.mobile-record small {
  display: block;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
@media (max-width: 600px) {
  .gacha-select {
    flex: 1 1 100%;
    min-width: 0;
    width: 100%;
  }
  .gacha-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
