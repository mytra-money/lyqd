<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Checkbox, FormControl, call } from 'frappe-ui'
import { toast } from '@/utils/toast'
import Dialog from '@/components/Dialog.vue'

const props = defineProps({
  company: { type: String, default: '' },
  cashEffect: { type: String, default: 'Outflow' },
  seedName: { type: String, default: '' },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['created'])

const saving = ref(false)
const form = reactive({
  category_name: '',
  allow_outflow: true,
  allow_inflow: false,
})

const title = computed(() =>
  form.category_name ? `New category · ${form.category_name}` : 'New payment category',
)

watch(open, (v) => {
  if (!v) return
  form.category_name = (props.seedName || '').trim()
  const effect = props.cashEffect || 'Outflow'
  if (effect === 'Outflow') {
    form.allow_outflow = true
    form.allow_inflow = false
  } else if (effect === 'Inflow' || effect === 'Setoff') {
    form.allow_outflow = false
    form.allow_inflow = true
  } else {
    form.allow_outflow = true
    form.allow_inflow = true
  }
})

async function save() {
  const name = (form.category_name || '').trim()
  if (!name) {
    toast.error('Category name is required')
    return
  }
  if (!form.allow_outflow && !form.allow_inflow) {
    toast.error('Enable Outflow and/or Inflow')
    return
  }
  if (!props.company) {
    toast.error('Select a company first')
    return
  }
  saving.value = true
  try {
    const row = await call('lyqd.api.spa.save_payment_category', {
      company: props.company,
      category_name: name,
      allow_outflow: form.allow_outflow ? 1 : 0,
      allow_inflow: form.allow_inflow ? 1 : 0,
    })
    toast.success('Category created')
    open.value = false
    emit('created', row)
  } catch (e) {
    toast.error(e?.messages?.[0] || e?.message || 'Could not create category')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model="open" :options="{ title, size: 'sm' }">
    <template #body-content>
      <div class="space-y-3">
        <FormControl
          v-model="form.category_name"
          label="Category name"
          placeholder="e.g. Rent"
          required
        />
        <Checkbox v-model="form.allow_outflow" label="Allow for outgoing (pay)" />
        <Checkbox v-model="form.allow_inflow" label="Allow for incoming (receive)" />
        <p class="text-xs text-gray-500">
          Tick both for categories like Rent or Other that work either way.
        </p>
      </div>
    </template>
    <template #actions>
      <Button variant="solid" :loading="saving" @click="save">Create</Button>
      <Button variant="outline" @click="open = false">Cancel</Button>
    </template>
  </Dialog>
</template>
