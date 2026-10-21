<script setup lang="ts">
import { computed, ref, watch, type Component, type CSSProperties } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  AimOutlined,
  ApiOutlined,
  AppstoreOutlined,
  CloudOutlined,
  CompassOutlined,
  ExperimentOutlined,
  HolderOutlined,
  RocketOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import arknightsNoteImage from '@/assets/community-notes/arknights.webp'
import endfieldNoteImage from '@/assets/community-notes/endfield.webp'
import genshinNoteImage from '@/assets/community-notes/genshin.webp'
import starRailNoteImage from '@/assets/community-notes/star-rail.webp'
import zenlessNoteImage from '@/assets/community-notes/zenless.webp'
import type { ActivitySnapshot } from '../useCommunityActivityApi'
import { gameLabelKey, platformLabelKey, presentActivity } from '../communityActivityPresentation'
import CommunityActivityMetric from './CommunityActivityMetric.vue'

interface GameVisual {
  accent: string
  backgroundImage: string
  icon: Component
  image: string
  uiClass: string
}

const props = defineProps<{ snapshot: ActivitySnapshot }>()
const { t, locale } = useI18n()
const backgroundAttempt = ref(0)

// 背景由文档站分发；哈希前缀与 public/community-notes/manifest.json 对应，绕过发布前缓存。
const NOTE_BACKGROUND_BASE = 'https://doc.auto-mas.top/community-notes'

// 这些中文值是后端稳定游戏枚举，只用于映射，不参与界面翻译；名称文案在 presentation 里映射 i18n 键。
const GAME_VISUALS: Record<string, GameVisual> = {
  明日方舟: {
    accent: 'var(--ant-color-primary)',
    backgroundImage: `${NOTE_BACKGROUND_BASE}/arknights-background.webp?v=6a23195b201d`,
    icon: AimOutlined,
    image: arknightsNoteImage,
    uiClass: 'activity-card--arknights',
  },
  终末地: {
    accent: 'var(--ant-color-success)',
    backgroundImage: `${NOTE_BACKGROUND_BASE}/endfield-background.webp?v=9d3a6fee469e`,
    icon: ApiOutlined,
    image: endfieldNoteImage,
    uiClass: 'activity-card--endfield',
  },
  原神: {
    accent: '#8fe3b0',
    backgroundImage: `${NOTE_BACKGROUND_BASE}/genshin-background.webp?v=f06788a6cb81`,
    icon: CompassOutlined,
    image: genshinNoteImage,
    uiClass: 'activity-card--genshin',
  },
  星穹铁道: {
    accent: '#62c4e7',
    backgroundImage: `${NOTE_BACKGROUND_BASE}/star-rail-background.webp?v=1048d29ea88f`,
    icon: RocketOutlined,
    image: starRailNoteImage,
    uiClass: 'activity-card--star-rail',
  },
  绝区零: {
    accent: '#ffd24a',
    backgroundImage: `${NOTE_BACKGROUND_BASE}/zenless-background.webp?v=e4f8798de02c`,
    icon: ThunderboltOutlined,
    image: zenlessNoteImage,
    uiClass: 'activity-card--zenless',
  },
  鸣潮: {
    accent: '#7fd6ea',
    // 鸣潮背景尚未在文档站发布；留空以复用玻璃卡片的底色与本地图标，
    // 不用其它游戏的素材冒充鸣潮。
    backgroundImage: '',
    icon: CloudOutlined,
    image: '',
    uiClass: 'activity-card--waves',
  },
  异环: {
    accent: '#c9a2ff',
    // 异环同样没有已发布的背景素材：背景与图片留空，卡片退回玻璃底色 + 图标标识，
    // 复用鸣潮那套「无背景素材」的降级样式（不编造图片地址）。
    backgroundImage: '',
    icon: ExperimentOutlined,
    image: '',
    uiClass: 'activity-card--waves',
  },
}

const visual = computed(() => GAME_VISUALS[props.snapshot.game])
const presentation = computed(() => presentActivity(props.snapshot))
const cardStyle = computed(
  () =>
    ({ '--activity-accent': visual.value?.accent ?? 'var(--ant-color-primary)' }) as CSSProperties
)
const backgroundUrl = computed(
  () => `${visual.value?.backgroundImage ?? ''}${backgroundAttempt.value ? '&retry=1' : ''}`
)
const statusMeta = computed(() => {
  const colors = {
    success: 'success',
    empty: 'default',
    limited: 'warning',
    unavailable: 'orange',
    failed: 'error',
  }
  return {
    label: t(`gamesign.activity.status.${props.snapshot.status}`),
    color: colors[props.snapshot.status],
  }
})
const alertType = computed(() => {
  if (props.snapshot.status === 'failed') return 'error'
  if (['limited', 'unavailable'].includes(props.snapshot.status)) return 'warning'
  return 'info'
})
const platform = computed(() => {
  const key = platformLabelKey(props.snapshot.platform)
  return key ? t(key) : props.snapshot.platform
})
const gameLabel = computed(() => {
  const key = gameLabelKey(props.snapshot.game)
  return key ? t(key) : props.snapshot.game
})
const updatedAt = computed(() => {
  const date = new Date(props.snapshot.updatedAt)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
})

// 每次手动刷新可重试背景；单轮失败最多重试一次，离线时保留底色与本地图标。
watch(
  () => [props.snapshot.game, props.snapshot.updatedAt],
  () => {
    backgroundAttempt.value = 0
  }
)
</script>

<template>
  <a-card
    :bordered="false"
    :class="['activity-card', visual?.uiClass]"
    :style="cardStyle"
  >
    <img
      v-if="visual?.backgroundImage && backgroundAttempt < 2"
      class="activity-background"
      :src="backgroundUrl"
      alt=""
      aria-hidden="true"
      referrerpolicy="no-referrer"
      loading="lazy"
      decoding="async"
      fetchpriority="low"
      @error="backgroundAttempt++"
    />
    <header class="activity-card-header">
      <span
        class="activity-drag-handle"
        :title="t('gamesign.activity.drag')"
        :aria-label="t('gamesign.activity.drag')"
        ><HolderOutlined
      /></span>
      <span class="activity-game-mark">
        <img v-if="visual?.image" class="activity-game-image" :src="visual.image" alt="" />
        <component v-else :is="visual?.icon ?? AppstoreOutlined" aria-hidden="true" />
      </span>
      <div class="activity-card-title">
        <strong>{{ gameLabel }}</strong>
        <span>{{ platform }}</span>
      </div>
      <a-tag :color="statusMeta.color">{{ statusMeta.label }}</a-tag>
    </header>
    <div class="activity-identity">
      <strong>{{ snapshot.account }}</strong>
      <span v-if="snapshot.roleName && snapshot.roleName !== snapshot.account">{{
        snapshot.roleName
      }}</span>
      <span v-if="snapshot.server">{{ snapshot.server }}</span>
    </div>

    <div
      v-if="presentation.featured.length || presentation.groups.length"
      class="activity-content"
      :class="{
        'activity-content--overview': presentation.overview,
        'activity-content--details-only': !presentation.featured.length,
      }"
    >
      <div v-if="presentation.featured.length" class="activity-featured">
        <CommunityActivityMetric
          v-for="metric in presentation.featured"
          :key="metric.name"
          :metric="metric"
          
          featured
        />
      </div>
      <div class="activity-details">
        <section
          v-for="group in presentation.groups"
          :key="group.labelKey"
          class="activity-section"
        >
          <h3 v-if="group.labelKey">{{ t(group.labelKey) }}</h3>
          <CommunityActivityMetric
            v-for="metric in group.metrics"
            :key="`${metric.period}-${metric.name}`"
            :metric="metric"
          />
        </section>
      </div>
    </div>

    <a-alert
      v-if="snapshot.reason"
      :type="alertType"
      :message="snapshot.reason"
      show-icon
      class="activity-reason"
    />
    <footer class="activity-card-footer">
      <span v-if="snapshot.roleUid">{{
        t('gamesign.activity.roleUid', { uid: snapshot.roleUid })
      }}</span>
      <span v-else>{{ t('gamesign.activity.noRole') }}</span>
      <span v-if="updatedAt">{{ updatedAt }}</span>
    </footer>
  </a-card>
</template>

<style scoped src="./community-activity-card.css"></style>
