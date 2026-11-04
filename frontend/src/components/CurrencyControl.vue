<template>
  <FormControl
    :model-value="display"
    type="number"
    :label="label"
    :disabled="disabled"
    :required="required"
    :description="description"
    :size="size"
    step="0.01"
    min="0"
    inputmode="decimal"
    @update:model-value="onInput"
    @blur="onBlur"
  >
    <template #prefix>
      <span class="pl-2 text-sm font-medium text-gray-500">{{ currencySymbol }}</span>
    </template>
  </FormControl>
</template>

<script setup>
import { computed } from 'vue'
import { FormControl } from 'frappe-ui'

const props = defineProps({
  modelValue: { type: [Number, String, null], default: null },
  label: { type: String, default: 'Amount' },
  currency: { type: String, default: 'INR' },
  precision: { type: Number, default: 2 },
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  description: { type: String, default: '' },
  size: { type: String, default: 'sm' },
  allowNegative: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const currencySymbol = computed(() => {
  try {
    const parts = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: props.currency,
    }).formatToParts(0)
    return parts.find((p) => p.type === 'currency')?.value || '₹'
  } catch {
    return '₹'
  }
})

const display = computed(() => {
  if (props.modelValue === null || props.modelValue === undefined || props.modelValue === '') {
    return ''
  }
  const n = Number(props.modelValue)
  if (Number.isNaN(n)) return ''
  return n
})

function roundToPrecision(value) {
  const p = Math.max(0, Number(props.precision) || 2)
  const factor = 10 ** p
  let n = Math.round((Number(value) + Number.EPSILON) * factor) / factor
  if (!props.allowNegative && n < 0) n = 0
  return n
}

function onInput(raw) {
  if (raw === '' || raw === null || raw === undefined) {
    emit('update:modelValue', null)
    return
  }
  const n = Number(raw)
  if (Number.isNaN(n)) return
  emit('update:modelValue', n)
}

function onBlur() {
  if (props.modelValue === null || props.modelValue === undefined || props.modelValue === '') {
    return
  }
  emit('update:modelValue', roundToPrecision(props.modelValue))
}
</script>
