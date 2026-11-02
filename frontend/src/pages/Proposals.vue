<template>
  <div>
    <PageHeader
      title="Draft proposals"
      subtitle="Freeze surplus numbers locally. No Mytra / BSE submit in this PoC."
    >
      <Button variant="solid" :loading="creating" @click="createFromSurplus">
        Create from 7d surplus
      </Button>
    </PageHeader>

    <div class="rounded-md border border-gray-200 bg-white p-4 overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead class="text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="py-2">Proposal</th>
            <th class="py-2">Status</th>
            <th class="py-2">Scheme</th>
            <th class="py-2 text-right">Amount</th>
            <th class="py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list.data || []" :key="row.name" class="border-t border-black/5">
            <td class="py-3 font-mono text-xs">{{ row.name }}</td>
            <td class="py-3"><Badge :theme="row.status === 'Frozen' ? 'green' : 'blue'">{{ row.status }}</Badge></td>
            <td class="py-3">{{ row.display_scheme_label || '—' }}</td>
            <td class="py-3 text-right tabular-nums">{{ formatINR(row.proposed_amount) }}</td>
            <td class="py-3 text-right space-x-1">
              <Button
                v-if="row.status !== 'Frozen'"
                size="sm"
                variant="outline"
                @click="freeze(row.name)"
              >
                Freeze
              </Button>
              <Button size="sm" variant="ghost" @click="toInstruction(row.name)">Instruction</Button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!(list.data || []).length" class="py-8 text-center text-sm text-gray-500">
        No proposals yet. Create one from current surplus.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { formatINR } from '@/utils/format'

const company = useCompanyStore()
const router = useRouter()
const creating = ref(false)

const list = createListResource({
  doctype: 'LYQD Draft Proposal',
  fields: [
    'name',
    'status',
    'proposed_amount',
    'display_scheme_label',
    'display_scheme_isin',
    'company',
    'as_of',
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

async function createFromSurplus() {
  creating.value = true
  try {
    await call('lyqd.api.spa.create_proposal_from_surplus', {
      company: company.current,
      horizon_days: 7,
      freeze: 1,
    })
    toast.success('Proposal created and frozen')
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create proposal')
  } finally {
    creating.value = false
  }
}

async function freeze(name) {
  try {
    await call('lyqd.api.spa.freeze_proposal', { name })
    toast.success('Frozen')
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Freeze failed')
  }
}

async function toInstruction(proposal) {
  if (!company.investmentAccountActivated) {
    toast.error('Activate the investment account in Settings first')
    router.push({ path: '/settings', query: { tab: 'investment' } })
    return
  }
  try {
    const doc = await call('lyqd.api.spa.create_instruction_from_proposal', { proposal })
    toast.success(`Instruction ${doc.name}`)
    router.push('/instructions')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create instruction')
  }
}
</script>
