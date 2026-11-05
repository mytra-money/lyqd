<template>
  <div class="flex items-center gap-1">
    <div
      class="flex items-center overflow-hidden rounded-md border border-gray-200 bg-white"
      title="Forecast horizon in days"
    >
      <input
        :value="modelValue"
        type="number"
        min="1"
        max="365"
        step="1"
        inputmode="numeric"
        class="horizon-days w-11 border-0 bg-transparent px-1.5 py-1.5 text-center text-sm tabular-nums text-gray-900 focus:outline-none focus:ring-0 sm:w-12 sm:px-2"
        aria-label="Forecast horizon in days"
        @input="onInput"
        @blur="normalize"
      />
      <span class="border-l border-gray-200 px-1.5 py-1.5 text-[10px] text-gray-500 sm:px-2 sm:text-xs">
        days
      </span>
    </div>
    <!-- Quick picks: desktop / tablet only — PWA keeps a compact input -->
    <div v-if="!isMobileView" class="flex items-center gap-0.5">
      <button
        v-for="d in presets"
        :key="d"
        type="button"
        class="rounded px-1.5 py-1 text-xs font-medium tabular-nums transition-colors"
        :class="
          Number(modelValue) === d
            ? 'bg-gray-900 text-white'
            : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
        "
        :title="`${d}-day horizon`"
        @click="emit('update:modelValue', d)"
      >
        {{ d }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { isMobileView } from '@/composables/useMobile'

const props = defineProps({
  modelValue: { type: Number, default: 7 },
  presets: {
    type: Array,
    default: () => [7, 14, 30, 60],
  },
})

const emit = defineEmits(['update:modelValue'])

function clamp(n) {
  const v = Math.round(Number(n))
  if (!Number.isFinite(v) || v < 1) return 1
  if (v > 365) return 365
  return v
}

function onInput(e) {
  const raw = e.target.value
  if (raw === '' || raw === null) return
  emit('update:modelValue', clamp(raw))
}

function normalize() {
  emit('update:modelValue', clamp(props.modelValue || 7))
}
</script>

<style scoped>
/* Hide browser up/down steppers — they clip the day value on narrow PWA headers. */
.horizon-days {
  -moz-appearance: textfield;
  appearance: textfield;
}
.horizon-days::-webkit-outer-spin-button,
.horizon-days::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
</style>
