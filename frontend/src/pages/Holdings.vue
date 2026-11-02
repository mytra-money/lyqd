<template>
  <div>
    <PageHeader
      title="Portfolio"
      subtitle="Liquid fund holdings for the company. Units update after confirmed allotment."
    >
      <Button variant="solid" @click="openNew">Add holding</Button>
    </PageHeader>

    <div class="rounded-md border border-gray-200 bg-white p-4 overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead class="text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="py-2">Scheme</th>
            <th class="py-2">As on</th>
            <th class="py-2">Source</th>
            <th class="py-2 text-right">Units</th>
            <th class="py-2 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list.data || []" :key="row.name" class="border-t border-black/5">
            <td class="py-3">{{ row.scheme }}</td>
            <td class="py-3">{{ formatDate(row.as_on) }}</td>
            <td class="py-3"><Badge theme="gray">{{ row.source }}</Badge></td>
            <td class="py-3 text-right tabular-nums">{{ row.units }}</td>
            <td class="py-3 text-right tabular-nums">{{ formatINR(row.amount) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!(list.data || []).length" class="py-8 text-center text-sm text-gray-500">
        No holdings recorded.
      </div>
    </div>

    <Dialog v-model="show" :options="{ title: 'Add holding' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl v-model="form.scheme" type="select" label="Scheme" :options="schemeOptions" />
          <FormControl v-model="form.as_on" type="date" label="As on" />
          <FormControl
            v-model="form.source"
            type="select"
            label="Source"
            :options="['Manual', 'Simulated']"
          />
          <FormControl v-model="form.units" type="number" label="Units" />
          <FormControl v-model="form.amount" type="number" label="Amount" />
          <FormControl v-model="form.notes" type="textarea" label="Notes" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
        <Button variant="outline" @click="show = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { formatDate, formatINR } from '@/utils/format'

const company = useCompanyStore()
const show = ref(false)
const saving = ref(false)
const form = reactive({
  scheme: '',
  as_on: '',
  source: 'Manual',
  units: 0,
  amount: 0,
  notes: '',
})

const list = createListResource({
  doctype: 'LYQD Holding',
  fields: ['name', 'scheme', 'as_on', 'source', 'units', 'amount', 'company'],
  orderBy: 'as_on desc',
  auto: false,
})

const schemes = createListResource({
  doctype: 'LYQD Scheme',
  fields: ['name', 'scheme_name'],
  filters: { is_active: 1 },
  auto: true,
})

const schemeOptions = computed(() => (schemes.data || []).map((s) => s.name))

watch(
  () => company.current,
  (c) => {
    if (!c) return
    list.update({ filters: { company: c } })
    list.reload()
  },
  { immediate: true },
)

function openNew() {
  form.scheme = schemeOptions.value[0] || ''
  form.as_on = new Date().toISOString().slice(0, 10)
  form.source = 'Simulated'
  form.units = 0
  form.amount = 0
  form.notes = ''
  show.value = true
}

async function save() {
  saving.value = true
  try {
    await call('frappe.client.insert', {
      doc: {
        doctype: 'LYQD Holding',
        company: company.current,
        ...form,
      },
    })
    toast.success('Holding saved')
    show.value = false
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>
