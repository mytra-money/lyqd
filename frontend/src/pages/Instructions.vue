<template>
  <div>
    <PageHeader
      title="Investment instructions"
      subtitle="Draft → Approved → Ready. External exchange submit is handled on Mytra’s transaction site."
    >
    </PageHeader>

    <div
      class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      Approve and mark Ready here. Final submit to the exchange runs through Mytra’s mutual fund
      workflow — not from this app directly in the soft launch.
    </div>

    <div class="rounded-md border border-gray-200 bg-white overflow-x-auto">
      <EmptyState
        v-if="!(list.data || []).length"
        variant="portfolio"
        title="No instructions yet"
        description="Confirm a proposal amount, then create an instruction from Proposal."
      >
        <template #actions>
          <Button variant="solid" size="sm" @click="$router.push('/proposal')">
            Go to Proposal
          </Button>
        </template>
      </EmptyState>

      <table v-else class="min-w-full px-4 text-sm">
        <thead class="text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2">Instruction</th>
            <th class="px-4 py-2">Scheme</th>
            <th class="px-4 py-2">Status</th>
            <th class="px-4 py-2 text-right">Amount</th>
            <th class="px-4 py-2">Mytra</th>
            <th class="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list.data || []" :key="row.name" class="border-t border-black/5">
            <td class="px-4 py-3 font-mono text-xs">{{ row.name }}</td>
            <td class="px-4 py-3">{{ row.scheme_label || row.scheme }}</td>
            <td class="px-4 py-3"><Badge theme="blue">{{ row.status }}</Badge></td>
            <td class="px-4 py-3 text-right tabular-nums">{{ formatINR(row.amount) }}</td>
            <td class="px-4 py-3 text-xs text-gray-500">
              <div>{{ row.external_submit_status || '—' }}</div>
              <div v-if="row.mytra_transaction_ref" class="font-mono">
                {{ row.mytra_transaction_ref }}
              </div>
            </td>
            <td class="px-4 py-3 text-right space-x-1">
              <Button size="sm" variant="outline" @click="runMethod(row.name, 'mark_approved')">
                Approve
              </Button>
              <Button size="sm" variant="outline" @click="runMethod(row.name, 'mark_ready')">
                Ready
              </Button>
              <Button size="sm" variant="ghost" @click="runMethod(row.name, 'submit_to_mytra')">
                Submit…
              </Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { formatINR } from '@/utils/format'

const company = useCompanyStore()
const list = createListResource({
  doctype: 'LYQD Investment Instruction',
  fields: [
    'name',
    'scheme',
    'scheme_label',
    'status',
    'amount',
    'external_submit_status',
    'mytra_transaction_ref',
    'company',
  ],
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

async function runMethod(name, method) {
  const action = method === 'mark_approved' ? 'approve' : method === 'mark_ready' ? 'ready' : 'submit'
  try {
    const result = await call('lyqd.api.spa.instruction_action', { name, action })
    if (action === 'submit') {
      toast.error(result?.message || 'External submit is not available from this app yet')
    } else {
      toast.success('Updated')
    }
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Action failed')
  }
}
</script>
