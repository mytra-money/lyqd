<script setup>
/**
 * DocType-style picker for LYQD Payment Category (CRM Link pattern).
 * Uses frappe-ui Combobox + Create New footer; values are category labels
 * (server resolves to Link names on save).
 */
import { computed, ref, watch } from 'vue'
import { Button, Combobox } from 'frappe-ui'
import {
  DEFAULT_CATEGORY_LABELS,
  fetchPaymentCategoryOptions,
} from '@/utils/paymentCategories'
import CreatePaymentCategoryDialog from '@/components/CreatePaymentCategoryDialog.vue'

const props = defineProps({
  company: { type: String, default: '' },
  /** Outflow | Inflow | Setoff — filters allow_* flags */
  cashEffect: { type: String, default: 'Outflow' },
  label: { type: String, default: 'Category' },
  placeholder: { type: String, default: 'Select category' },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'sm' },
})

const model = defineModel({ type: String, default: '' })
const emit = defineEmits(['change', 'created'])

const options = ref(
  DEFAULT_CATEGORY_LABELS.map((c) => ({ label: c, value: c })),
)
const loading = ref(false)
const showCreate = ref(false)
const createSeed = ref('')

const comboboxOptions = computed(() => {
  const list = [...options.value]
  if (model.value && !list.some((o) => o.value === model.value)) {
    list.unshift({ label: model.value, value: model.value })
  }
  return list
})

async function reload() {
  if (!props.company) return
  loading.value = true
  try {
    const opts = await fetchPaymentCategoryOptions(props.company, props.cashEffect)
    if (opts.length) options.value = opts
  } catch {
    /* keep fallbacks */
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.company, props.cashEffect],
  () => reload(),
  { immediate: true },
)

function onModelUpdate(val) {
  const next = val == null ? '' : String(val)
  model.value = next
  emit('change', next)
}

function openCreate(query) {
  createSeed.value = (query || model.value || '').trim()
  showCreate.value = true
}

function onCreated(row) {
  const name = row?.category_name
  if (!name) return
  if (!options.value.some((o) => o.value === name)) {
    options.value = [{ label: name, value: name }, ...options.value]
  }
  model.value = name
  emit('change', name)
  emit('created', row)
  reload()
}

defineExpose({ reload })
</script>

<template>
  <div class="space-y-1.5">
    <Combobox
      :model-value="model || null"
      :options="comboboxOptions"
      :label="label"
      :placeholder="placeholder"
      :disabled="disabled"
      :size="size"
      :loading="loading"
      variant="subtle"
      empty-text="No categories"
      @update:model-value="onModelUpdate"
    >
      <template #footer="{ query, close }">
        <div class="flex flex-col gap-0.5 border-t border-outline-gray-1 p-1">
          <Button
            variant="ghost"
            class="w-full !justify-start"
            label="Create new"
            icon-left="lucide-plus"
            @click="
              () => {
                close?.()
                openCreate(query)
              }
            "
          />
          <Button
            v-if="model"
            variant="ghost"
            class="w-full !justify-start"
            label="Clear"
            icon-left="lucide-x"
            @click="
              () => {
                onModelUpdate('')
                close?.()
              }
            "
          />
        </div>
      </template>
    </Combobox>

    <CreatePaymentCategoryDialog
      v-model="showCreate"
      :company="company"
      :cash-effect="cashEffect"
      :seed-name="createSeed"
      @created="onCreated"
    />
  </div>
</template>
