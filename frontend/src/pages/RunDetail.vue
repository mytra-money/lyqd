<template>
  <div>
    <PageHeader :title="run?.name || routeName || 'Free cash snapshot'" :subtitle="subtitle">
      <Button variant="outline" @click="$router.push('/surplus')">Back to free cash</Button>
    </PageHeader>

    <div v-if="doc.loading" class="text-sm text-gray-500">Loading…</div>
    <div v-else-if="doc.error" class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      {{ doc.error?.messages?.[0] || doc.error?.message || 'Could not load surplus run.' }}
    </div>
    <template v-else-if="run">
      <div class="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Cash position" :value="run.bank_cash" />
        <MetricCard label="Commitments" :value="run.upcoming_total" />
        <MetricCard label="Buffer" :value="run.min_liquidity_buffer" />
        <MetricCard
          :label="run.is_shortfall ? 'Liquidity shortfall' : 'Free cash'"
          :value="Math.abs(run.investable_surplus || 0)"
          :tone="run.is_shortfall ? 'danger' : 'success'"
        />
      </div>
      <div class="rounded-md border border-gray-200 bg-white p-4">
        <ExplanationTable :lines="lines" />
      </div>
    </template>
    <div v-else class="text-sm text-gray-500">No run found for {{ routeName }}.</div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { createResource } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import ExplanationTable from '@/components/ExplanationTable.vue'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatDate } from '@/utils/format'
import { surplusRunExplanationLines } from '@/utils/explanationNest'

const props = defineProps({ name: String })
const route = useRoute()
const cache = useTreasuryCacheStore()

const routeName = computed(() => props.name || route.params.name)

const doc = createResource({
  url: 'frappe.client.get',
  makeParams() {
    return {
      doctype: 'LYQD Surplus Run',
      name: routeName.value,
    }
  },
  auto: false,
})

watch(
  routeName,
  (n) => {
    if (n) doc.reload()
  },
  { immediate: true },
)

const run = computed(() => doc.data)

watch(
  () => run.value?.company,
  (c) => {
    if (c) cache.ensurePlan({ company: c })
  },
  { immediate: true },
)

const subtitle = computed(() => {
  const d = run.value
  if (!d) return ''
  return `${formatDate(d.as_of)} · ${d.horizon_days}d horizon · ${d.company}`
})

const planParentByName = computed(() => {
  const map = {}
  const company = run.value?.company
  if (!company) return map
  for (const row of cache.getPlan(company) || []) {
    if (row?.name && row.parent_payment) map[row.name] = row.parent_payment
  }
  return map
})

const lines = computed(() =>
  surplusRunExplanationLines(run.value, planParentByName.value),
)
</script>
