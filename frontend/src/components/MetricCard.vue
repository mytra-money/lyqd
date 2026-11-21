<template>
  <component
    :is="to ? 'router-link' : 'div'"
    :to="to || undefined"
    class="block rounded-md border border-gray-200 bg-white p-3"
    :class="
      to
        ? 'transition-colors hover:border-gray-300 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400'
        : ''
    "
  >
    <div class="flex items-start justify-between gap-2">
      <div class="flex min-w-0 items-center gap-1">
        <div class="min-w-0 text-xs font-medium text-gray-500">{{ label }}</div>
        <InfoHover v-if="info" side="bottom" align="start">
          <div class="w-56 max-w-[85vw] p-3 text-left text-xs leading-relaxed text-gray-600">
            {{ info }}
          </div>
        </InfoHover>
      </div>
      <FeatherIcon
        v-if="to"
        name="chevron-right"
        class="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400"
      />
    </div>
    <div class="mt-1 text-xl font-semibold tabular-nums text-gray-900" :class="valueClass">
      {{ display }}
    </div>
    <div v-if="hint" class="mt-1 text-xs text-gray-500">{{ hint }}</div>
  </component>
</template>

<script setup>
import { computed } from 'vue'
import InfoHover from '@/components/InfoHover.vue'
import { formatINRCompact } from '@/utils/format'

const props = defineProps({
  label: String,
  value: [Number, String],
  /** Short status under the value (keep brief). */
  hint: String,
  /** Longer explanation behind the info icon. */
  info: String,
  tone: { type: String, default: 'default' },
  /** When set, card navigates (e.g. `/cash`, `/holdings`). */
  to: { type: String, default: null },
})

const display = computed(() => formatINRCompact(props.value))

const valueClass = computed(() => {
  if (props.tone === 'danger') return 'text-red-600'
  if (props.tone === 'success') return 'text-green-700'
  return ''
})
</script>
