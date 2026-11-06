<template>
  <div>
    <PageHeader
      title="Free cash"
      subtitle="Cash position minus near-term commitments, liquidity buffer, and restricted cash (liquidity view)."
    >
      <div class="flex flex-wrap items-center gap-2">
        <Button variant="outline" :loading="loading" @click="refresh">
          Refresh
        </Button>
        <Button
          v-if="hasOpenRequest"
          variant="solid"
          @click="$router.push('/proposal')"
        >
          Open proposal
        </Button>
        <Button
          v-else-if="r && !r.is_shortfall && Number(r.investable_surplus || 0) > 0.01"
          variant="solid"
          :loading="investing"
          @click="investNow"
        >
          Invest this free cash
        </Button>
        <Button
          v-else-if="r && r.is_shortfall"
          variant="solid"
          @click="$router.push({ path: '/proposal', query: { start: 'redeem' } })"
        >
          Start redeem
        </Button>
      </div>
    </PageHeader>

    <div v-if="loading && !r" class="text-sm text-gray-500">Computing…</div>
    <template v-else-if="r">
      <div class="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Cash position"
          :value="r.bank_cash"
          hint="T-1 statements"
          info="Morning free cash uses yesterday's bank statement balances."
        />
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
        Free cash is negative for this horizon.
        <template v-if="hasOpenRequest">
          <button
            type="button"
            class="ml-1 font-medium underline"
            @click="$router.push('/proposal')"
          >
            Open the existing proposal
          </button>
          instead of starting another redeem.
        </template>
        <template v-else>
          <button
            type="button"
            class="ml-1 font-medium underline"
            @click="$router.push({ path: '/proposal', query: { start: 'redeem' } })"
          >
            Start redeem on Proposal
          </button>
          if you have liquid holdings, or review commitments.
        </template>
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
    </template>
  </div>
</template>

<script setup>
import { computed, onActivated, ref, watch } from 'vue'
import { call, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import ExplanationTable from '@/components/ExplanationTable.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate } from '@/utils/format'

defineOptions({ name: 'Surplus' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const router = useRouter()
const { horizon } = useHorizon()
const investing = ref(false)

const r = computed(() => cache.getSurplus(company.current, horizon.value))
const mis = computed(() => cache.getMis(company.current, horizon.value))
const hasOpenRequest = computed(() => !!mis.value?.has_open_request || !!mis.value?.planned_ref)
const loading = computed(() => cache.surplusLoading && !r.value)

async function loadSurplus(force = false) {
  if (!company.current) return
  await Promise.all([
    cache.ensureSurplus({
      company: company.current,
      horizonDays: horizon.value,
      force,
    }),
    cache.ensureMis({
      company: company.current,
      horizonDays: horizon.value,
      force,
    }),
  ])
}

function refresh() {
  return loadSurplus(true)
}

watch(
  [() => company.current, horizon],
  () => {
    if (!company.current) return
    loadSurplus(false)
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
    if (doc.unchanged) {
      toast.success('Open proposal already matches today’s free cash')
    } else {
      const n = (doc.superseded || []).length
      toast.success(
        n
          ? `Proposal updated · superseded ${n} prior open proposal(s)`
          : 'Proposal created',
      )
    }
    router.push('/proposal')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create proposal')
  } finally {
    investing.value = false
  }
}
</script>
