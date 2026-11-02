<template>
  <div>
    <PageHeader
      title="Free cash"
      subtitle="Cash position minus near-term commitments, liquidity buffer, and restricted cash (liquidity view)."
    >
      <div class="flex flex-wrap items-center gap-2">
        <HorizonPicker v-model="horizon" />
        <Button variant="outline" :loading="loading" @click="refresh">
          Refresh
        </Button>
        <Button
          v-if="r && !r.is_shortfall"
          variant="solid"
          :loading="investing"
          @click="investNow"
        >
          Invest this free cash
        </Button>
      </div>
    </PageHeader>

    <div v-if="loading && !r" class="text-sm text-gray-500">Computing…</div>
    <template v-else-if="r">
      <div class="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Cash position" :value="r.bank_cash" hint="Bank statement balances" />
        <MetricCard
          :label="`Commitments (${r.horizon_days}d)`"
          :value="r.upcoming_total"
          hint="Planned + overdue"
        />
        <MetricCard
          label="Policy reserves"
          :value="(r.min_liquidity_buffer || 0) + (r.restricted_cash || 0)"
          hint="Buffer + restricted"
        />
        <MetricCard
          :label="r.is_shortfall ? 'Liquidity shortfall' : 'Free cash'"
          :value="Math.abs(r.investable_surplus || 0)"
          :tone="r.is_shortfall ? 'danger' : 'success'"
          :hint="r.is_shortfall ? 'Need cash / redeem' : 'Available to invest'"
        />
      </div>

      <div
        v-if="r.is_shortfall"
        class="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
      >
        Free cash is negative for this horizon. Review Commitments and Cash position redemption
        guidance before investing.
      </div>

      <div class="rounded-md border border-gray-200 bg-white p-4">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-500">
          <span>
            As of {{ formatDate(r.as_of) }} · horizon ends {{ formatDate(r.horizon_end) }}
          </span>
          <Badge theme="blue">Explainable waterfall</Badge>
        </div>
        <ExplanationTable :lines="r.explanation || []" />
      </div>

      <div class="mt-6 rounded-md border border-gray-200 bg-white p-4">
        <button
          type="button"
          class="flex w-full items-center justify-between text-left"
          @click="showHistory = !showHistory"
        >
          <div>
            <h2 class="text-sm font-semibold text-gray-900">Calculation history</h2>
            <p class="mt-0.5 text-p-base text-gray-600">
              Optional audit snapshots of free-cash calculations — not required for investing.
            </p>
          </div>
          <FeatherIcon
            name="chevron-right"
            class="h-4 w-4 text-gray-500 transition-transform"
            :class="{ 'rotate-90': showHistory }"
          />
        </button>

        <div v-if="showHistory" class="mt-4">
          <div class="mb-3 flex justify-end">
            <Button size="sm" variant="outline" :loading="saving" @click="saveSnapshot">
              Save snapshot now
            </Button>
          </div>
          <table class="min-w-full text-sm">
            <thead class="text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="py-2">Snapshot</th>
                <th class="py-2">As of</th>
                <th class="py-2">Horizon</th>
                <th class="py-2 text-right">Free cash</th>
                <th class="py-2"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in history.data || []" :key="row.name" class="border-t border-gray-100">
                <td class="py-2 font-mono text-xs">{{ row.name }}</td>
                <td class="py-2">{{ formatDate(row.as_of) }}</td>
                <td class="py-2">{{ row.horizon_days }}d</td>
                <td
                  class="py-2 text-right tabular-nums"
                  :class="row.is_shortfall ? 'text-red-600' : ''"
                >
                  {{ formatINR(row.investable_surplus) }}
                </td>
                <td class="py-2 text-right">
                  <Button size="sm" variant="ghost" @click="$router.push(`/runs/${row.name}`)">
                    Open
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!(history.data || []).length" class="py-4 text-center text-sm text-gray-500">
            No snapshots yet.
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onActivated, ref, watch } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import ExplanationTable from '@/components/ExplanationTable.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'

defineOptions({ name: 'Surplus' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const router = useRouter()
const { horizon } = useHorizon()
const saving = ref(false)
const investing = ref(false)
const showHistory = ref(false)

const history = createListResource({
  doctype: 'LYQD Surplus Run',
  fields: ['name', 'as_of', 'horizon_days', 'investable_surplus', 'is_shortfall', 'company'],
  orderBy: 'modified desc',
  pageLength: 10,
  auto: false,
})

const r = computed(() => cache.getSurplus(company.current, horizon.value))
const loading = computed(() => cache.surplusLoading && !r.value)

async function loadSurplus(force = false) {
  if (!company.current) return
  await cache.ensureSurplus({
    company: company.current,
    horizonDays: horizon.value,
    force,
  })
}

function refresh() {
  return loadSurplus(true)
}

watch(
  [() => company.current, horizon],
  () => {
    if (!company.current) return
    loadSurplus(false)
    history.update({ filters: { company: company.current } })
    history.reload()
  },
  { immediate: true },
)

onActivated(() => {
  loadSurplus(false)
})

async function investNow() {
  investing.value = true
  try {
    const doc = await call('lyqd.api.spa.create_proposal_from_surplus', {
      company: company.current,
      horizon_days: horizon.value,
      freeze: 1,
    })
    const n = (doc.superseded || []).length
    toast.success(
      n
        ? `Investment request created · superseded ${n} prior open request(s)`
        : 'Investment request created',
    )
    router.push('/invest')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create investment request')
  } finally {
    investing.value = false
  }
}

async function saveSnapshot() {
  saving.value = true
  try {
    const name = await call('lyqd.api.dashboard.save_surplus_run', {
      company: company.current,
      horizon_days: horizon.value,
    })
    toast.success(`Snapshot ${name} saved`)
    history.reload()
    router.push(`/runs/${name}`)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not save snapshot')
  } finally {
    saving.value = false
  }
}
</script>
