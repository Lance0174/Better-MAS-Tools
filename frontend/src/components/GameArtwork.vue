<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { artworkSources } from '@/utils/communityDashboard'

const props = defineProps<{
  game: string
  banner?: string
  cover?: string
  preferCover?: boolean
}>()
const failed = ref<string[]>([])
const candidates = computed(() =>
  artworkSources(props.game, props.banner, props.cover, props.preferCover)
)
const source = computed(() => candidates.value.find(image => !failed.value.includes(image)))
watch(candidates, () => {
  failed.value = []
})
const reject = (event: Event) => {
  const image = event.target as HTMLImageElement
  if (source.value && image.getAttribute('src') === source.value) failed.value.push(source.value)
}
const loaded = (event: Event) => {
  const image = event.target as HTMLImageElement
  // 方形图标和缩略图不能被放大成背景；继续尝试大版本或原便笺图。
  if (image.naturalWidth < 300 || image.naturalWidth / image.naturalHeight < 1.2) reject(event)
}
</script>

<template>
  <div class="game-artwork" aria-hidden="true">
    <img
      v-if="source"
      :key="source"
      :src="source"
      alt=""
      referrerpolicy="no-referrer"
      decoding="async"
      @load="loaded"
      @error="reject"
    />
  </div>
</template>

<style scoped>
.game-artwork {
  overflow: hidden;
  background: var(--ant-color-bg-elevated);
}
.game-artwork img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
