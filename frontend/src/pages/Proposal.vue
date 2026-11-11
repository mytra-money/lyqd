<template>
  <div>
    <PageHeader
      title="Proposal"
      subtitle="Live free cash × horizon. Snapshot is saved only when you create an instruction."
    >
      <Button variant="outline" @click="$router.push('/surplus')">Free cash</Button>
      <Button
        v-if="openInstruction"
        variant="solid"
        @click="$router.push('/instructions')"
      >
        Continue instruction
      </Button>
      <Button
        v-else
        variant="solid"
        :loading="creating"
        :disabled="!canCreateInstruction"
        @click="primaryCreate"
      >
        {{ primaryCtaLabel }}
      </Button>
    </PageHeader>

    <div
      v-if="!company.investmentAccountActivated"
      class="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      <span class="font-medium">Investment account not activated.</span>
      You can review free cash; creating an instruction needs Mytra activation.
      <button
        type="button"
        class="ml-1 font-medium underline"
        @click="openActivationWhatsApp"
      >
        Request activation
      </button>
    </div>

    <!-- Open instruction (frozen snapshot) -->
    <section
      v-if="openInstruction"
      class="mb-5 rounded-md border border-gray-200 bg-white"
    >
      <div class="flex flex-col gap-4 px-5 py-5 lg:flex-row lg:items-end lg:justify-between">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <Badge :theme="openIsRedeem ? 'red' : 'green'">
              {{ openIsRedeem ? 'Redeem' : 'Invest' }}
            </Badge>
            <Badge theme="blue" variant="subtle">{{ openInstruction.status }}</Badge>
            <span class="font-mono text-xs text-gray-500">{{ openInstruction.name }}</span>
          </div>
          <div class="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-gray-900">
            {{ formatINR(openInstruction.amount) }}
          </div>
          <p class="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-gray-600">
            <span>
              Snapshot as of {{ formatDate(openInstruction.as_of) }}
              <span v-if="openInstruction.horizon_days">
                · {{ openInstruction.horizon_days }}d
              </span>
              <template v-if="openInstruction.scheme_label">
                · {{ openInstruction.scheme_label }}
              </template>
            </span>
            <a
              v-if="openSchemeUrl"
              :href="openSchemeUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
              title="Scheme info"
              aria-label="Scheme info"
            >
              <FeatherIcon name="info" class="h-3.5 w-3.5" />
            </a>
          </p>
          <p class="mt-2 text-xs text-gray-500">
            This amount was frozen when the instruction was created. Live free cash below may differ.
          </p>
        </div>
        <div class="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
          <Button variant="solid" @click="$router.push('/instructions')">
            Continue instruction
          </Button>
          <Button
            v-if="openInstruction.status === 'Draft'"
            variant="outline"
            :loading="cancelling"
            @click="cancelOpenInstruction"
          >
            Cancel instruction
          </Button>
        </div>
      </div>

      <div
        v-if="instructionDrift"
        class="border-t border-amber-100 bg-amber-50 px-5 py-3 text-sm text-amber-950"
      >
        <p class="font-medium">{{ instructionDrift.title }}</p>
        <p class="mt-1 text-p-base text-amber-900">{{ instructionDrift.body }}</p>
      </div>

      <div v-if="snapshotRun" class="border-t border-gray-100 px-5 py-4">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 text-left"
          @click="showCalc = !showCalc"
        >
          <div>
            <div class="text-sm font-medium text-gray-900">
              How {{ formatINR(openInstruction.amount) }} was calculated
            </div>
            <div class="mt-0.5 text-xs text-gray-500">
              Frozen surplus run
              <span v-if="openInstruction.surplus_run" class="font-mono text-gray-400">
                · {{ openInstruction.surplus_run }}
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
        </div>
      </div>
    </section>

    <!-- Live treasury view: amount → metrics → options → waterfall -->
    <section class="rounded-md border border-gray-200 bg-white">
      <header
        v-if="openInstruction"
        class="border-b border-gray-100 px-5 py-3"
      >
        <h2 class="text-sm font-semibold text-gray-900">Live free cash (this horizon)</h2>
        <p class="mt-0.5 text-xs text-gray-500">
          Finish or cancel the open instruction before creating another.
        </p>
      </header>

      <div class="px-5 py-5">
        <div v-if="canInvest" class="min-w-0">
          <div class="text-xs text-gray-500">Suggested amount · {{ horizon }}d</div>
          <div class="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-gray-900">
            {{ formatINR(liveFreeCash) }}
          </div>
          <p class="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-gray-600">
            <span>Bank → {{ defaultSchemeLabel }}</span>
            <a
              v-if="defaultSchemeUrl"
              :href="defaultSchemeUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
              title="Scheme info"
              aria-label="Scheme info"
            >
              <FeatherIcon name="info" class="h-3.5 w-3.5" />
            </a>
          </p>
        </div>

        <div
          v-if="liveSurplus"
          class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
          :class="canInvest ? 'mt-5' : ''"
        >
          <MetricCard
            label="Cash position"
            :value="liveSurplus.bank_cash"
            hint="T-1 statements"
          />
          <MetricCard
            :label="`Commitments (${liveSurplus.horizon_days || horizon}d)`"
            :value="liveSurplus.upcoming_total"
            hint="Planned + overdue"
          />
          <MetricCard
            label="Policy reserves"
            :value="
              (liveSurplus.min_liquidity_buffer || 0) + (liveSurplus.restricted_cash || 0)
            "
            hint="Buffer + restricted"
          />
          <MetricCard
            :label="liveSurplus.is_shortfall ? 'Liquidity shortfall' : 'Free cash'"
            :value="Math.abs(liveSurplus.investable_surplus || 0)"
            :tone="liveSurplus.is_shortfall ? 'danger' : 'success'"
            :hint="liveSurplus.is_shortfall ? 'Need cash / redeem' : 'Available to invest'"
          />
        </div>

        <div v-if="canInvest" class="mt-5">
          <TreasuryActionChooser
            :amount="liveFreeCash"
            :horizon-days="horizon"
            :scheme-url="defaultSchemeUrl"
            :creating="creating"
            :create-disabled="!!openInstruction || !company.investmentAccountActivated"
            :create-label="
              openInstruction
                ? 'Instruction already open'
                : company.investmentAccountActivated
                  ? 'Create liquid fund instruction'
                  : 'Activate account to instruct'
            "
            :idle-pct="yieldRates.idle"
            :fd-pct="yieldRates.fd"
            :liquid-pct="yieldRates.liquid"
            @leave-in-bank="leaveInBank"
            @create-instruction="createFromLive('Invest')"
          />
        </div>

        <EmptyState
          v-else-if="liveShortfall && canRedeem"
          class="mt-5"
          variant="invest"
          title="Liquidity shortfall this horizon"
          :description="`Suggest redeem ${formatINR(redemptionNeed)} from holdings (${formatINR(liquidTotal)} available) to cover commitments and reserves.`"
        >
          <template #actions>
            <Button
              variant="solid"
              size="sm"
              :loading="creating"
              :disabled="!!openInstruction || !company.investmentAccountActivated"
              @click="createFromLive('Redeem')"
            >
              Create redeem instruction
            </Button>
          </template>
        </EmptyState>

        <EmptyState
          v-else-if="liveShortfall"
          class="mt-5"
          variant="invest"
          title="Nothing to invest this horizon"
          description="Free cash is negative and there are no liquid holdings to redeem. Review Free cash or top up the bank."
        >
          <template #actions>
            <Button variant="outline" size="sm" @click="$router.push('/surplus')">
              Review free cash
            </Button>
            <Button variant="ghost" size="sm" @click="$router.push('/holdings')">
              Open holdings
            </Button>
          </template>
        </EmptyState>

        <EmptyState
          v-else
          class="mt-5"
          variant="invest"
          title="Nothing to invest this horizon"
          description="Free cash is zero after commitments and buffers — add bank balances or adjust the plan before creating an instruction."
        >
          <template #actions>
            <Button variant="solid" size="sm" @click="$router.push('/cash')">
              Add bank balance
            </Button>
            <Button variant="outline" size="sm" @click="$router.push('/surplus')">
              Review free cash
            </Button>
          </template>
        </EmptyState>
      </div>

      <div
        v-if="liveSurplus && liveExplanationLines.length"
        class="border-t border-gray-100 px-5 py-4"
      >
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 text-left"
          @click="showLiveExtract = !showLiveExtract"
        >
          <div>
            <div class="text-sm font-medium text-gray-900">Explainable waterfall</div>
            <div class="mt-0.5 text-xs text-gray-500">
              As of {{ formatDate(liveSurplus.as_of) }}
              <span v-if="liveSurplus.horizon_end">
                · horizon ends {{ formatDate(liveSurplus.horizon_end) }}
              </span>
            </div>
          </div>
          <FeatherIcon
            :name="showLiveExtract ? 'chevron-up' : 'chevron-down'"
            class="h-4 w-4 shrink-0 text-gray-400"
          />
        </button>
        <div v-if="showLiveExtract" class="mt-3">
          <ExplanationTable :lines="liveExplanationLines" />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call, createResource } from 'frappe-ui'
import { toast } from '@/utils/toast'
import { useRouter } from 'vue-router'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import ExplanationTable from '@/components/ExplanationTable.vue'
import TreasuryActionChooser from '@/components/TreasuryActionChooser.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'
import { surplusRunExplanationLines } from '@/utils/explanationNest'
import { LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL } from '@/utils/investmentAccount'
import { resolveIllustrativeRates, schemeInfoUrl } from '@/utils/scheme'

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const router = useRouter()
const { horizon } = useHorizon()
const creating = ref(false)
const cancelling = ref(false)
const showCalc = ref(true)
const showLiveExtract = ref(true)
const openInstruction = ref(null)

const runResource = createResource({
  url: 'frappe.client.get',
  makeParams() {
    return {
      doctype: 'LYQD Surplus Run',
      name: openInstruction.value?.surplus_run,
    }
  },
  auto: false,
})

async function reloadContext() {
  if (!company.current) return
  await Promise.all([
    cache.ensureSurplus({ company: company.current, horizonDays: horizon.value }),
    cache.ensureMis({ company: company.current, horizonDays: horizon.value }),
    cache.ensurePlan({ company: company.current }),
    loadOpenInstruction(),
  ])
}

async function loadOpenInstruction() {
  if (!company.current) {
    openInstruction.value = null
    return
  }
  try {
    openInstruction.value = await call('lyqd.api.spa.get_open_instruction', {
      company: company.current,
    })
  } catch (e) {
    openInstruction.value = null
  }
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

watch(
  () => openInstruction.value?.surplus_run,
  (name) => {
    showCalc.value = true
    if (name) runResource.reload()
  },
  { immediate: true },
)

onMounted(() => reloadContext())

const liveSurplus = computed(() => cache.getSurplus(company.current, horizon.value))
const liveMis = computed(() => cache.getMis(company.current, horizon.value))
const liveShortfall = computed(() => !!liveSurplus.value?.is_shortfall)
const liveFreeCash = computed(() =>
  Math.max(
    0,
    Number(liveSurplus.value?.investable_surplus || liveMis.value?.investable_surplus || 0),
  ),
)
const liquidTotal = computed(() => Number(liveMis.value?.liquid_fund_total || 0))
const redemptionNeed = computed(() => Number(liveMis.value?.redemption_need || 0))
const canRedeem = computed(() => liquidTotal.value > 0.01 && redemptionNeed.value > 0.01)
const canInvest = computed(() => !liveShortfall.value && liveFreeCash.value > 0.01)
const canCreateInstruction = computed(() => {
  if (openInstruction.value) return false
  if (!company.investmentAccountActivated) return false
  if (liveShortfall.value) return canRedeem.value
  return canInvest.value
})

const openIsRedeem = computed(() => (openInstruction.value?.side || '') === 'Redeem')
const snapshotRun = computed(() => !!openInstruction.value?.surplus_run)

const defaultSchemeLabel = computed(
  () => company.settings?.display_scheme_label || 'ICICI Prudential Liquid Fund',
)

const defaultSchemeUrl = computed(() =>
  schemeInfoUrl(
    company.settings?.display_scheme_isin || 'INF109K01VQ1',
    defaultSchemeLabel.value,
  ),
)
const openSchemeUrl = computed(() =>
  schemeInfoUrl(openInstruction.value?.scheme_isin, openInstruction.value?.scheme_label),
)

const yieldRates = computed(() => resolveIllustrativeRates(company.settings))

const primaryCtaLabel = computed(() => {
  if (liveShortfall.value && canRedeem.value) return 'Create redeem instruction'
  if (liveShortfall.value) return 'Review free cash'
  if (!canInvest.value) return 'No free cash'
  return 'Create liquid fund instruction'
})

const instructionDrift = computed(() => {
  if (!openInstruction.value || !liveMis.value) return null
  const m = liveMis.value
  const free = Math.max(0, Number(m.investable_surplus || 0))
  if (openIsRedeem.value && m.redeem_no_longer_needed) {
    return {
      title: 'Redeem may no longer be needed',
      body: `This horizon now shows free cash ${formatINR(free)}. Review or cancel the open instruction before acting.`,
    }
  }
  if (openIsRedeem.value && Number(m.redeem_over_need || 0) > 0) {
    return {
      title: 'Instruction amount is higher than today’s need',
      body: `Today’s shortfall need is ${formatINR(m.redemption_need)} — the open redeem is ${formatINR(m.redeem_over_need)} higher.`,
    }
  }
  if (openIsRedeem.value && Number(m.redeem_under_need || 0) > 0) {
    return {
      title: 'Instruction amount is below today’s need',
      body: `Today’s shortfall need is ${formatINR(m.redemption_need)} — the open redeem is ${formatINR(m.redeem_under_need)} short.`,
    }
  }
  if (!openIsRedeem.value && m.invest_flipped_to_shortfall) {
    return {
      title: 'Horizon flipped to a shortfall',
      body: `Do not deploy ${formatINR(openInstruction.value.amount)}. This horizon needs more cash — cancel the invest instruction and create a redeem instead.`,
    }
  }
  if (!openIsRedeem.value && Number(m.over_allocated || 0) > 0) {
    return {
      title: 'Free cash is below this instruction',
      body: `Cash moved since the snapshot. Free cash is ${formatINR(m.over_allocated)} lower than the instruction amount.`,
    }
  }
  return null
})

const runDoc = computed(() => runResource.data)
const runLoading = computed(() => runResource.loading)

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

const liveExplanationLines = computed(() => {
  const r = liveSurplus.value
  if (!r) return []
  // Live surplus payload already nests explanation lines for the SPA
  if (Array.isArray(r.explanation) && r.explanation.length) return r.explanation
  return surplusRunExplanationLines(r, planParentByName.value)
})

function openActivationWhatsApp() {
  window.open(LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL, '_blank', 'noopener,noreferrer')
}

function leaveInBank() {
  toast.success('Leaving free cash in the bank — no instruction created')
  router.push('/surplus')
}

async function primaryCreate() {
  if (openInstruction.value) {
    router.push('/instructions')
    return
  }
  if (liveShortfall.value && canRedeem.value) return createFromLive('Redeem')
  if (liveShortfall.value) {
    router.push('/surplus')
    return
  }
  if (!canInvest.value) {
    toast.error('No free cash to invest for this horizon')
    return
  }
  return createFromLive('Invest')
}

async function createFromLive(requestType) {
  if (!company.investmentAccountActivated) {
    toast.error('Activate the investment account in Settings first')
    router.push({ path: '/settings', query: { tab: 'investment' } })
    return
  }
  if (openInstruction.value) {
    toast.error('An instruction is already open')
    return
  }
  creating.value = true
  try {
    const res = await call('lyqd.api.spa.create_instruction_from_live', {
      company: company.current,
      horizon_days: horizon.value,
      request_type: requestType,
    })
    toast.success(`Instruction ${res.instruction?.name || ''} ready`)
    await cache.ensureMis({
      company: company.current,
      horizonDays: horizon.value,
      force: true,
    })
    await reloadContext()
    router.push('/instructions')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create instruction')
  } finally {
    creating.value = false
  }
}

async function cancelOpenInstruction() {
  if (!openInstruction.value || openInstruction.value.status !== 'Draft') return
  cancelling.value = true
  try {
    await call('frappe.client.set_value', {
      doctype: 'LYQD Investment Instruction',
      name: openInstruction.value.name,
      fieldname: 'status',
      value: 'Cancelled',
    })
    if (openInstruction.value.proposal) {
      await call('frappe.client.set_value', {
        doctype: 'LYQD Draft Proposal',
        name: openInstruction.value.proposal,
        fieldname: {
          status: 'Cancelled',
          notes: 'Cancelled with instruction',
        },
      })
    }
    toast.success('Instruction cancelled')
    await reloadContext()
    await cache.ensureMis({
      company: company.current,
      horizonDays: horizon.value,
      force: true,
    })
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Cancel failed')
  } finally {
    cancelling.value = false
  }
}
</script>
