<script setup lang="ts">
defineProps<{
  value: string
  options: readonly { value: string; label: string }[]
  label: string
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:value': [value: string] }>()
</script>

<template>
  <div class="game-tabs" role="tablist" :aria-label="label">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="tab"
      :disabled="disabled"
      :aria-selected="option.value === value"
      @click="emit('update:value', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.game-tabs {
  display: flex;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
  margin-bottom: 20px;
}
.game-tabs::-webkit-scrollbar {
  display: none;
}
.game-tabs button {
  flex-shrink: 0;
  padding: 11px 17px;
  min-height: 42px;
  border: 0;
  border-radius: 14px;
  background: var(--ant-color-bg-container);
  color: var(--ant-color-text-secondary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.game-tabs button[aria-selected='true'] {
  background: var(--ant-color-primary-bg);
  color: var(--ant-color-link);
  font-weight: 600;
}
.game-tabs button:disabled {
  opacity: 0.5;
}
</style>
