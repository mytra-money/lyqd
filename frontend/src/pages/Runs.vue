<template>
  <div>
    <PageHeader title="Surplus runs" subtitle="Saved surplus calculations for demos and audit.">
      <Button variant="solid" @click="$router.push('/surplus')">Compute surplus</Button>
    </PageHeader>

    <div class="rounded-md border border-gray-200 bg-white p-4 overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead class="text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="py-2">Run</th>
            <th class="py-2">As of</th>
            <th class="py-2">Horizon</th>
            <th class="py-2 text-right">Surplus</th>
            <th class="py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list.data || []" :key="row.name" class="border-t border-black/5">
            <td class="py-3 font-mono text-xs">{{ row.name }}</td>
            <td class="py-3">{{ formatDate(row.as_of) }}</td>
            <td class="py-3">{{ row.horizon_days }}d</td>
            <td class="py-3 text-right tabular-nums" :class="row.is_shortfall ? 'text-red-700' : ''">
              {{ formatINR(row.investable_surplus) }}
            </td>
            <td class="py-3 text-right">
              <Button size="sm" variant="ghost" @click="$router.push(`/runs/${row.name}`)">
                Open
              </Button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!(list.data || []).length" class="py-8 text-center text-sm text-gray-500">
        No saved runs yet.
      </div>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { createListResource } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { formatDate, formatINR } from '@/utils/format'

const company = useCompanyStore()
const list = createListResource({
  doctype: 'LYQD Surplus Run',
  fields: ['name', 'as_of', 'horizon_days', 'investable_surplus', 'is_shortfall', 'company'],
  orderBy: 'modified desc',
  auto: false,
})

watch(
  () => company.current,
  (c) => {
    if (!c) return
    list.update({ filters: { company: c } })
    list.reload()
  },
  { immediate: true },
)
</script>
