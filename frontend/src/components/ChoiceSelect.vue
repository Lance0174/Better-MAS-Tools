<script setup lang="ts" generic="T extends string">
import { computed, ref, useAttrs, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckOutlined, DownOutlined } from '@ant-design/icons-vue'
import { useMobileUi } from '@/composables/useMobileUi'
import AdaptivePanel from './AdaptivePanel.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps<{
  value?: T
  options: readonly { value: T; label?: string }[]
  placeholder?: string
  disabled?: boolean
  loading?: boolean
}>()
const emit = defineEmits<{ 'update:value': [value: T]; change: [value: T] }>()
const attrs = useAttrs()
// 单一根节点承接页面的宽度与间距；ARIA 和输入事件继续落在实际控件上。
const controlAttrs = () => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
}
const { t } = useI18n()
const mobile = useMobileUi()
const open = ref(false)
const search = ref('')
watch(mobile, value => {
  if (!value) open.value = false
})
const normalized = computed(() =>
  props.options.map(item => ({ ...item, label: item.label || item.value }))
)
const selected = computed(() => normalized.value.find(item => item.value === props.value))
const choices = computed(() =>
  normalized.value.filter(item =>
    item.label.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())
  )
)
const title = computed(() =>
  String(attrs['aria-label'] || props.placeholder || t('standalone.ui.choose'))
)
const choose = (value: unknown) => {
  const option = props.options.find(item => item.value === value)
  if (!option || props.disabled || props.loading) return
  emit('update:value', option.value)
  emit('change', option.value)
  open.value = false
}
const show = () => {
  if (props.disabled || props.loading) return
  search.value = ''
  open.value = true
}
</script>

<template>
  <div class="choice-field" :class="$attrs.class" :style="$attrs.style">
    <a-select
      v-if="!mobile"
      v-bind="controlAttrs()"
      :value="value"
      :options="normalized"
      :placeholder="placeholder"
      :disabled="disabled"
      :loading="loading"
      @change="choose"
    />
    <button
      v-else
      v-bind="controlAttrs()"
      class="choice-select"
      type="button"
      :disabled="disabled || loading"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="show"
    >
      <span>{{
        loading ? t('standalone.ui.loading') : selected?.label || placeholder || title
      }}</span
      ><DownOutlined />
    </button>
    <AdaptivePanel :open="open && mobile" :title="title" :width="440" @close="open = false">
      <a-input
        v-if="options.length > 6"
        v-model:value="search"
        :placeholder="t('standalone.ui.searchChoices')"
        class="choice-search"
      />
      <div class="choice-options">
        <button
          v-for="option in choices"
          :key="option.value"
          type="button"
          class="choice-option"
          :aria-pressed="option.value === value"
          @click="choose(option.value)"
        >
          <span>{{ option.label }}</span
          ><CheckOutlined v-if="option.value === value" />
        </button>
        <a-empty v-if="!choices.length" :description="t('standalone.ui.noMatches')" />
      </div>
    </AdaptivePanel>
  </div>
</template>

<style scoped>
.choice-field {
  min-width: 0;
  width: 100%;
}
.choice-field > .ant-select {
  width: 100%;
}
.choice-select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 10px 13px;
  border: 1px solid var(--ant-color-border);
  border-radius: 14px;
  background: var(--ant-color-bg-elevated);
  color: var(--ant-color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.choice-select > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.choice-select > .anticon {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--ant-color-text-secondary);
}
.choice-select:disabled {
  opacity: 0.55;
  cursor: default;
}
.choice-options {
  display: grid;
  gap: 6px;
}
.choice-search {
  margin-bottom: 14px;
}
.choice-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 17px 12px;
  width: 100%;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: var(--ant-color-text);
  font: inherit;
  text-align: left;
}
.choice-option > span {
  overflow-wrap: anywhere;
}
.choice-option[aria-pressed='true'] {
  color: var(--ant-color-link);
  background: var(--ant-color-primary-bg);
}
.choice-option .anticon {
  flex-shrink: 0;
}
</style>
