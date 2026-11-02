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
          label="Free cash"
          :value="run.investable_surplus"
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
import { formatDate } from '@/utils/format'

const props = defineProps({ name: String })
const route = useRoute()

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

const subtitle = computed(() => {
  const d = run.value
  if (!d) return ''
  return `${formatDate(d.as_of)} · ${d.horizon_days}d horizon · ${d.company}`
})

const lines = computed(() => {
  const d = run.value
  if (!d) return []
  if (Array.isArray(d.lines) && d.lines.length) {
    return d.lines.map((l) => ({
      kind: l.kind,
      label: l.label,
      amount: l.amount,
      sign: l.sign,
      category: l.category,
      due_date: l.due_date,
      ref_name: l.ref_name,
    }))
  }
  try {
    const raw = d.explanation_json
    if (!raw) return []
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return parsed.explanation || []
  } catch {
    return []
  }
})
</script>
