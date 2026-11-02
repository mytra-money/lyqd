<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <div class="flex items-center overflow-hidden rounded-md border border-gray-200 bg-white">
      <input
        :value="modelValue"
        type="number"
        min="1"
        max="365"
        step="1"
        class="w-14 border-0 bg-transparent px-2 py-1.5 text-sm tabular-nums text-gray-900 focus:outline-none focus:ring-0"
        aria-label="Forecast horizon in days"
        @input="onInput"
        @blur="normalize"
      />
      <span class="border-l border-gray-200 px-2 py-1.5 text-xs text-gray-500">days</span>
    </div>
    <div class="flex flex-wrap gap-1">
      <button
        v-for="d in presets"
        :key="d"
        type="button"
        class="rounded px-1.5 py-1 text-xs font-medium transition-colors"
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
