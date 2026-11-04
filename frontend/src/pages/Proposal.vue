<template>
  <div>
    <PageHeader
      title="Proposal"
      subtitle="Draft an invest or redeem proposal from free cash. One open proposal at a time."
    >
      <HorizonPicker v-model="horizon" />
      <Button variant="outline" @click="$router.push('/surplus')">Free cash</Button>
      <Button variant="solid" :loading="creating" @click="primaryAction">
        {{ primaryCtaLabel }}
      </Button>
    </PageHeader>

    <div
      v-if="!company.investmentAccountActivated"
      class="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      <span class="font-medium">Investment account not activated.</span>
      You can draft a request; creating an instruction needs Mytra activation.
      <button
        type="button"
        class="ml-1 font-medium underline"
        @click="openActivationWhatsApp"
      >
        Request activation
      </button>
    </div>

    <section class="mb-5 rounded-md border border-gray-200 bg-white">
      <!-- Empty: shortfall with holdings → start redeem -->
      <div v-if="!active && liveShortfall && canRedeem" class="px-5 py-10 text-center">
        <Badge theme="red">Redeem</Badge>
        <p class="mt-3 text-sm font-semibold text-gray-900">Liquidity shortfall this horizon</p>
        <p class="mx-auto mt-2 max-w-md text-sm text-gray-600">
          Suggest redeem
          <span class="font-medium tabular-nums text-gray-900">{{ formatINR(redemptionNeed) }}</span>
          from holdings
          <span class="tabular-nums">({{ formatINR(liquidTotal) }} available)</span>
          to cover commitments and reserves.
        </p>
        <Button class="mt-4" variant="solid" :loading="creating" @click="createFromShortfall">
          Start redeem
        </Button>
      </div>

      <!-- Empty: shortfall, no holdings -->
      <div v-else-if="!active && liveShortfall" class="px-5 py-10 text-center">
        <Badge theme="red">Redeem</Badge>
        <p class="mt-3 text-sm font-semibold text-gray-900">Nothing to invest this horizon</p>
        <p class="mx-auto mt-2 max-w-md text-sm text-gray-600">
          Free cash is negative and there are no liquid holdings to redeem. Review Free cash or top
          up the bank.
        </p>
        <div class="mt-4 flex flex-wrap justify-center gap-2">
          <Button variant="outline" @click="$router.push('/surplus')">Review free cash</Button>
          <Button variant="ghost" @click="$router.push('/holdings')">Open holdings</Button>
        </div>
      </div>

      <!-- Empty: ready to invest -->
      <div v-else-if="!active" class="px-5 py-10 text-center">
        <Badge theme="green">Invest</Badge>
        <p class="mt-3 text-sm font-semibold text-gray-900">No open proposal</p>
        <p class="mx-auto mt-2 max-w-md text-sm text-gray-600">
          Start from today’s free cash to lock an amount and scheme, then create a Mytra instruction.
        </p>
        <Button class="mt-4" variant="solid" :loading="creating" @click="createFromSurplus">
          Start from free cash
        </Button>
      </div>

      <!-- Active request -->
      <div v-else>
        <div class="flex flex-col gap-5 border-b border-gray-100 px-5 py-5 lg:flex-row lg:items-end lg:justify-between">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <Badge :theme="isRedeem ? 'red' : 'green'">
                {{ isRedeem ? 'Redeem' : 'Invest' }}
              </Badge>
              <Badge :theme="statusTheme(active.status)" variant="subtle">
                {{ statusLabel(active.status) }}
              </Badge>
              <span class="text-xs text-gray-500">
                As of {{ formatDate(active.as_of) }}
                <span v-if="active.horizon_days"> · {{ active.horizon_days }}d</span>
              </span>
            </div>
            <div class="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-gray-900">
              {{ formatINR(active.proposed_amount) }}
            </div>
            <p class="mt-1 max-w-xl text-sm text-gray-600">
              <template v-if="isRedeem">
                {{ active.display_scheme_label || 'Liquid fund'
                }}{{ active.display_scheme_isin ? ` (${active.display_scheme_isin})` : '' }}
                → Bank
              </template>
              <template v-else>
                Bank →
                {{ active.display_scheme_label || 'liquid fund'
                }}{{ active.display_scheme_isin ? ` (${active.display_scheme_isin})` : '' }}
              </template>
            </p>
          </div>

          <div class="flex shrink-0 flex-col items-stretch gap-2 sm:flex-row sm:items-center">
            <Button
              v-if="active.status === 'Frozen' && !activeInstruction"
              variant="solid"
              :disabled="!company.investmentAccountActivated"
              :loading="instructing"
              @click="toInstruction(active.name)"
            >
              Create instruction
            </Button>
            <Button
              v-else-if="active.status === 'Draft'"
              variant="solid"
              @click="freeze(active.name)"
            >
              Confirm amount
            </Button>
            <Button
              v-else-if="activeInstruction"
              variant="solid"
              @click="$router.push('/instructions')"
            >
              Continue instruction
            </Button>
            <Button variant="ghost" :loading="cancelling" @click="cancelActive">Cancel</Button>
          </div>
        </div>

        <!-- Horizon drift vs open proposal (same signals as Cash position) -->
        <div
          v-if="horizonDrift"
          class="border-b border-amber-100 bg-amber-50 px-5 py-3 text-sm text-amber-950"
        >
          <p class="font-medium">{{ horizonDrift.title }}</p>
          <p class="mt-1 text-p-base text-amber-900">{{ horizonDrift.body }}</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <Button
              v-if="horizonDrift.action === 'replace_invest'"
              size="sm"
              variant="solid"
              :loading="creating"
              @click="createFromSurplus"
            >
              Replace with invest
            </Button>
            <Button
              v-else-if="horizonDrift.action === 'replace_redeem'"
              size="sm"
              variant="solid"
              :loading="creating"
              @click="createFromShortfall"
            >
              Replace with redeem
            </Button>
            <Button
              v-else-if="horizonDrift.action === 'refresh'"
              size="sm"
              variant="solid"
              :loading="creating"
              @click="primaryAction"
            >
              Refresh proposal
            </Button>
            <Button size="sm" variant="outline" :loading="cancelling" @click="cancelActive">
              Cancel proposal
            </Button>
          </div>
        </div>

        <!-- Invest: yield card / Redeem: liquidity note -->
        <div v-if="!isRedeem" class="border-b border-gray-100 px-5 py-4">
          <div
            class="flex flex-col gap-4 rounded-md border border-emerald-200 bg-emerald-50/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="min-w-0">
              <div class="text-xs font-medium uppercase tracking-wide text-emerald-800">
                Earn more than a current account
              </div>
              <div class="mt-1 text-2xl font-semibold tabular-nums text-emerald-950">
                ~{{ formatINR(annualBenefit) }}
                <span class="text-base font-medium text-emerald-800">/ year</span>
              </div>
              <p class="mt-1 text-sm text-emerald-900/80">
                On {{ formatINR(active.proposed_amount) }} parked in
                {{ active.display_scheme_label || 'a liquid fund' }}
                <a
                  v-if="schemeUrl"
                  :href="schemeUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ml-1 font-medium text-emerald-900 underline"
                >
                  Scheme info
                </a>
              </p>
            </div>
            <div class="grid shrink-0 grid-cols-2 gap-3 text-sm sm:min-w-[220px]">
              <div class="rounded bg-white/70 px-3 py-2">
                <div class="text-xs text-gray-500">Current account</div>
                <div class="mt-0.5 font-semibold tabular-nums text-gray-700">~0%</div>
              </div>
              <div class="rounded bg-white/70 px-3 py-2">
                <div class="text-xs text-gray-500">Liquid fund</div>
                <div class="mt-0.5 font-semibold tabular-nums text-emerald-800">
                  ~{{ ILLUSTRATIVE_LIQUID_YIELD_PCT }}%
                </div>
              </div>
            </div>
          </div>
          <p class="mt-3 text-xs leading-relaxed text-gray-500">{{ MF_DISCLAIMER }}</p>
        </div>
        <div v-else class="border-b border-gray-100 px-5 py-4">
          <div class="rounded-md border border-red-200 bg-red-50/70 px-4 py-4">
            <div class="text-xs font-medium uppercase tracking-wide text-red-800">
              Bring cash back for commitments
            </div>
            <p class="mt-1 text-sm text-red-950">
              Redeem up to
              <span class="font-semibold tabular-nums">{{ formatINR(active.proposed_amount) }}</span>
              from
              {{ active.display_scheme_label || 'liquid holdings' }}
              <a
                v-if="schemeUrl"
                :href="schemeUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="font-medium underline"
              >
                (scheme info)
              </a>
              to cover the liquidity gap (capped by portfolio).
            </p>
          </div>
          <p class="mt-3 text-xs leading-relaxed text-gray-500">{{ MF_DISCLAIMER }}</p>
        </div>

        <div
          v-if="activeInstruction"
          class="border-b border-gray-100 bg-gray-50 px-5 py-2.5 text-xs text-gray-600"
        >
          Instruction
          <span class="font-mono text-gray-800">{{ activeInstruction.name }}</span>
          · {{ activeInstruction.status }}
        </div>

        <div class="px-5 py-4">
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 text-left"
            @click="showCalc = !showCalc"
          >
            <div>
              <div class="text-sm font-medium text-gray-900">
                How {{ formatINR(active.proposed_amount) }} was calculated
              </div>
              <div class="mt-0.5 text-xs text-gray-500">
                Free cash after commitments and policy reserves
                <span v-if="active.surplus_run" class="font-mono text-gray-400">
                  · {{ active.surplus_run }}
                </span>
              </div>
            </div>
            <FeatherIcon
              :name="showCalc ? 'chevron-up' : 'chevron-down'"
              class="h-4 w-4 shrink-0 text-gray-400"
            />
          </button>

          <div v-if="showCalc" class="mt-4">
            <div v-if="runLoading" class="py-4 text-sm text-gray-500">Loading…</div>
            <div
              v-else-if="runError"
              class="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-800"
            >
              Could not load the surplus calculation.
            </div>
            <template v-else-if="runDoc">
              <div class="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="Cash position" :value="runDoc.bank_cash" />
                <MetricCard label="Commitments" :value="runDoc.upcoming_total" />
                <MetricCard
                  label="Policy reserves"
                  :value="(runDoc.min_liquidity_buffer || 0) + (runDoc.restricted_cash || 0)"
                />
                <MetricCard
                  :label="runDoc.is_shortfall ? 'Liquidity shortfall' : 'Free cash'"
                  :value="Math.abs(runDoc.investable_surplus || 0)"
                  :tone="runDoc.is_shortfall ? 'danger' : 'success'"
                />
              </div>
              <ExplanationTable :lines="runLines" />
            </template>
            <div v-else class="py-3 text-sm text-gray-500">No surplus run on this proposal.</div>
          </div>
        </div>
      </div>
    </section>

    <section class="rounded-md border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-5 py-3">
        <h2 class="text-sm font-semibold text-gray-900">Earlier proposals</h2>
        <p class="mt-0.5 text-xs text-gray-500">Cancelled or replaced — audit only.</p>
      </header>
      <div v-if="!history.length" class="px-5 py-8 text-center text-sm text-gray-500">
        None yet.
      </div>
      <ul v-else class="divide-y divide-gray-100">
        <li
          v-for="row in history"
          :key="row.name"
          class="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
        >
          <div class="min-w-0">
            <div class="font-mono text-xs text-gray-500">{{ row.name }}</div>
            <div class="mt-0.5 text-xs text-gray-500">
              {{ formatDate(row.as_of) }}
              <span v-if="row.notes"> · {{ row.notes }}</span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Badge
              :theme="(row.request_type || 'Invest') === 'Redeem' ? 'red' : 'green'"
              variant="subtle"
            >
              {{ row.request_type || 'Invest' }}
            </Badge>
            <span class="text-xs text-gray-500">{{ statusLabel(row.status) }}</span>
            <span class="tabular-nums text-sm font-medium text-gray-700">
              {{ formatINR(row.proposed_amount) }}
            </span>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call, createListResource, createResource, toast } from 'frappe-ui'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import MetricCard from '@/components/MetricCard.vue'
import ExplanationTable from '@/components/ExplanationTable.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'
import { surplusRunExplanationLines } from '@/utils/explanationNest'
import { LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL } from '@/utils/investmentAccount'
import {
  ILLUSTRATIVE_LIQUID_YIELD_PCT,
  MF_DISCLAIMER,
  schemeInfoUrl,
} from '@/utils/scheme'

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const route = useRoute()
const router = useRouter()
const { horizon } = useHorizon()
const creating = ref(false)
const cancelling = ref(false)
const instructing = ref(false)
const showCalc = ref(true)

const list = createListResource({
  doctype: 'LYQD Draft Proposal',
  fields: [
    'name',
    'status',
    'request_type',
    'proposed_amount',
    'display_scheme_label',
    'display_scheme_isin',
    'company',
    'as_of',
    'horizon_days',
    'notes',
    'surplus_run',
  ],
  orderBy: 'modified desc',
  auto: false,
})

const instructions = createListResource({
  doctype: 'LYQD Investment Instruction',
  fields: ['name', 'status', 'proposal', 'amount', 'company', 'side'],
  orderBy: 'modified desc',
  pageLength: 50,
  auto: false,
})

const runResource = createResource({
  url: 'frappe.client.get',
  makeParams() {
    return {
      doctype: 'LYQD Surplus Run',
      name: active.value?.surplus_run,
    }
  },
  auto: false,
})

async function reloadContext() {
  if (!company.current) return
  list.update({ filters: { company: company.current } })
  instructions.update({ filters: { company: company.current } })
  await Promise.all([
    list.reload(),
    instructions.reload(),
    cache.ensureSurplus({ company: company.current, horizonDays: horizon.value }),
    cache.ensureMis({ company: company.current, horizonDays: horizon.value }),
    cache.ensurePlan({ company: company.current }),
  ])
}

watch(
  () => company.current,
  () => reloadContext(),
  { immediate: true },
)

watch(horizon, () => {
  if (!company.current) return
  cache.ensureSurplus({ company: company.current, horizonDays: horizon.value })
  cache.ensureMis({ company: company.current, horizonDays: horizon.value })
})

onMounted(async () => {
  if (route.query.start === 'redeem') {
    await reloadContext()
    // Supersede an open Invest (or create when empty) — API cancels prior open proposals.
    const openType = active.value?.request_type || (active.value ? 'Invest' : null)
    if (
      liveShortfall.value &&
      canRedeem.value &&
      (!active.value || openType === 'Invest')
    ) {
      await createFromShortfall()
    }
    router.replace({ path: '/proposal', query: {} })
  }
})

const active = computed(() =>
  (list.data || []).find((r) => r.status === 'Draft' || r.status === 'Frozen'),
)

const isRedeem = computed(() => (active.value?.request_type || 'Invest') === 'Redeem')

watch(
  () => active.value?.surplus_run,
  (name) => {
    showCalc.value = true
    if (name) runResource.reload()
  },
  { immediate: true },
)

function statusTheme(s) {
  if (s === 'Frozen') return 'green'
  if (s === 'Cancelled') return 'gray'
  return 'blue'
}

const history = computed(() =>
  (list.data || []).filter((r) => r.status === 'Cancelled'),
)

const activeInstruction = computed(() => {
  if (!active.value) return null
  return (instructions.data || []).find(
    (i) =>
      i.proposal === active.value.name && ['Draft', 'Approved', 'Ready'].includes(i.status),
  )
})

const liveSurplus = computed(() => cache.getSurplus(company.current, horizon.value))
const liveMis = computed(() => cache.getMis(company.current, horizon.value))
const liveShortfall = computed(() => !!liveSurplus.value?.is_shortfall)
const liquidTotal = computed(() => Number(liveMis.value?.liquid_fund_total || 0))
const redemptionNeed = computed(() => Number(liveMis.value?.redemption_need || 0))
const canRedeem = computed(() => liquidTotal.value > 0.01 && redemptionNeed.value > 0.01)

const schemeUrl = computed(() =>
  schemeInfoUrl(active.value?.display_scheme_isin, active.value?.display_scheme_label),
)

/** Align open proposal with the picker horizon (same MIS flags as Cash position). */
const horizonDrift = computed(() => {
  if (!active.value || !liveMis.value) return null
  const m = liveMis.value
  const free = Math.max(0, Number(m.investable_surplus || 0))
  if (isRedeem.value && m.redeem_no_longer_needed) {
    return {
      title: 'Redeem may no longer be needed',
      body: `This horizon now shows free cash ${formatINR(free)} — review or cancel this redeem before acting, or replace it with an invest proposal.`,
      action: 'replace_invest',
    }
  }
  if (isRedeem.value && Number(m.redeem_over_need || 0) > 0) {
    return {
      title: 'Redeem amount is higher than today’s need',
      body: `Today’s shortfall need is ${formatINR(m.redemption_need)} — this proposal is ${formatINR(m.redeem_over_need)} higher. Refresh the amount before creating an instruction.`,
      action: 'refresh',
    }
  }
  if (!isRedeem.value && m.invest_flipped_to_shortfall) {
    return {
      title: 'Horizon flipped to a shortfall',
      body: `Do not invest ${formatINR(active.value.proposed_amount)}. This horizon needs ${formatINR(m.redemption_need || Math.abs(m.investable_surplus || 0))} more cash — cancel this invest and create a redeem instead.`,
      action: 'replace_redeem',
    }
  }
  if (!isRedeem.value && Number(m.over_allocated || 0) > 0) {
    return {
      title: 'Free cash is below this proposal',
      body: `Cash moved since the proposal. Free cash is ${formatINR(m.over_allocated)} lower — do not deploy the full amount; refresh before creating an instruction.`,
      action: 'refresh',
    }
  }
  return null
})

const primaryCtaLabel = computed(() => {
  if (active.value) {
    return isRedeem.value ? 'Refresh redeem' : 'Refresh amount'
  }
  if (liveShortfall.value && canRedeem.value) return 'Start redeem'
  if (liveShortfall.value) return 'Review free cash'
  return 'Start from free cash'
})

const runDoc = computed(() => runResource.data)
const runLoading = computed(() => runResource.loading)
const runError = computed(() => runResource.error)

const planParentByName = computed(() => {
  const map = {}
  for (const row of cache.getPlan(company.current) || []) {
    if (row?.name && row.parent_payment) map[row.name] = row.parent_payment
  }
  return map
})

const runLines = computed(() =>
  surplusRunExplanationLines(runDoc.value, planParentByName.value),
)

const annualBenefit = computed(() => {
  const amt = Number(active.value?.proposed_amount || 0)
  return Math.round(amt * (ILLUSTRATIVE_LIQUID_YIELD_PCT / 100))
})

function statusLabel(s) {
  if (s === 'Frozen') return 'Ready'
  if (s === 'Draft') return 'Draft'
  if (s === 'Cancelled') return 'Cancelled'
  return s
}

function openActivationWhatsApp() {
  window.open(LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL, '_blank', 'noopener,noreferrer')
}

async function primaryAction() {
  if (active.value) {
    if (isRedeem.value) return createFromShortfall()
    return createFromSurplus()
  }
  if (liveShortfall.value && canRedeem.value) return createFromShortfall()
  if (liveShortfall.value) {
    router.push('/surplus')
    return
  }
  return createFromSurplus()
}

async function createFromSurplus() {
  creating.value = true
  try {
    const doc = await call('lyqd.api.spa.create_proposal_from_surplus', {
      company: company.current,
      horizon_days: horizon.value,
      freeze: 1,
    })
    if (doc.unchanged) {
      toast.success('Already matches today’s free cash')
    } else {
      const n = (doc.superseded || []).length
      toast.success(n ? `Updated · replaced ${n} prior proposal(s)` : 'Invest proposal ready')
    }
    list.reload()
    instructions.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create request')
  } finally {
    creating.value = false
  }
}

async function createFromShortfall() {
  creating.value = true
  try {
    const doc = await call('lyqd.api.spa.create_proposal_from_shortfall', {
      company: company.current,
      horizon_days: horizon.value,
      freeze: 1,
    })
    if (doc.unchanged) {
      toast.success('Already matches today’s shortfall')
    } else {
      const n = (doc.superseded || []).length
      toast.success(n ? `Redeem updated · replaced ${n} prior request(s)` : 'Redeem request ready')
    }
    list.reload()
    instructions.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create redeem request')
  } finally {
    creating.value = false
  }
}

async function freeze(name) {
  try {
    await call('lyqd.api.spa.freeze_proposal', { name })
    toast.success('Amount confirmed')
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Confirm failed')
  }
}

async function cancelActive() {
  if (!active.value) return
  cancelling.value = true
  try {
    if (activeInstruction.value?.status === 'Draft') {
      await call('frappe.client.set_value', {
        doctype: 'LYQD Investment Instruction',
        name: activeInstruction.value.name,
        fieldname: 'status',
        value: 'Cancelled',
      })
    } else if (activeInstruction.value) {
      toast.error('Cancel or finish the Approved/Ready instruction first')
      return
    }
    await call('frappe.client.set_value', {
      doctype: 'LYQD Draft Proposal',
      name: active.value.name,
      fieldname: {
        status: 'Cancelled',
        notes: 'Cancelled by user',
      },
    })
    toast.success('Request cancelled')
    list.reload()
    instructions.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Cancel failed')
  } finally {
    cancelling.value = false
  }
}

async function toInstruction(proposal) {
  if (!company.investmentAccountActivated) {
    toast.error('Activate the investment account in Settings first')
    router.push({ path: '/settings', query: { tab: 'investment' } })
    return
  }
  instructing.value = true
  try {
    const doc = await call('lyqd.api.spa.create_instruction_from_proposal', { proposal })
    toast.success(`Instruction ${doc.name}`)
    router.push('/instructions')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create instruction')
    list.reload()
  } finally {
    instructing.value = false
  }
}
</script>
