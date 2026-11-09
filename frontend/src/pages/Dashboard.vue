<template>
  <div>
    <PageHeader title="Cash position">
      <template #subtitle>
        <span class="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
          <span class="whitespace-nowrap">As of {{ formatDate(d?.as_of) }}</span>
          <span class="text-gray-300" aria-hidden="true">·</span>
          <span class="min-w-0 break-words">{{ company.current || '—' }}</span>
        </span>
      </template>
      <Button variant="outline" :loading="loading" @click="refresh">Refresh</Button>
    </PageHeader>

    <div v-if="loading && !d" class="text-sm text-gray-500">Loading morning view…</div>
    <template v-else-if="d">
      <!-- Hero metrics — drill into detail pages -->
      <div class="mb-5 grid grid-cols-[repeat(auto-fit,minmax(11.5rem,1fr))] gap-3">
        <MetricCard
          label="Bank cash"
          :value="d.bank_cash"
          :hint="bankCashHint"
          :info="bankCashInfo"
          to="/cash"
        />
        <MetricCard
          :label="`Incoming (${d.horizon_days}d)`"
          :value="d.incoming_expected != null ? d.incoming_expected : d.incoming_total || 0"
          hint="Expected"
          :info="incomingInfo"
          to="/upcoming"
        />
        <MetricCard
          :label="`Commitments (${d.horizon_days}d)`"
          :value="d.commitments_total != null ? d.commitments_total : Math.max(0, d.upcoming_total || 0)"
          hint="Outflows"
          info="Outflows reserved this horizon. Open Commitments to review."
          to="/upcoming"
        />
        <MetricCard
          label="Free cash"
          :value="Math.abs(d.investable_surplus || 0)"
          :tone="d.is_shortfall ? 'danger' : 'success'"
          :hint="d.is_shortfall ? 'Shortfall' : 'Surplus'"
          info="Bank − commitments − policy. Does not include expected incoming."
          to="/surplus"
        />
        <MetricCard
          v-if="showExpectedLiquidity"
          :label="expectedLiquidityLabel"
          :value="Math.abs(d.expected_free_cash || 0)"
          :tone="d.expected_is_shortfall ? 'danger' : 'success'"
          :hint="expectedLiquidityHint"
          :info="expectedLiquidityInfo"
          to="/upcoming"
        />
      </div>

      <div
        v-if="staleBanks.length"
        class="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      >
        <span class="font-medium">{{ staleBanks.length }} bank balance(s)</span>
        not updated for {{ formatDate(bankAsOf) }}.
        <Button class="ml-2" size="sm" variant="outline" @click="$router.push('/cash')">
          Update on Bank balances
        </Button>
      </div>

      <!-- Plan drift — Invest or Redeem open request vs this horizon -->
      <div
        v-if="d.planned_investment > 0"
        class="mb-4 rounded-md border border-gray-200 bg-white px-4 py-3 text-sm"
      >
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <div class="font-medium text-gray-900">
            {{
              (d.planned_request_type || 'Invest') === 'Redeem'
                ? 'Redeem proposal vs this horizon'
                : d.invest_flipped_to_shortfall
                  ? 'Invest proposal vs shortfall today'
                  : 'Invest proposal vs free cash today'
            }}
          </div>
          <div class="tabular-nums text-gray-700">
            Proposal {{ formatINR(d.planned_investment) }}
            <span v-if="d.planned_ref" class="text-xs text-gray-500">· {{ d.planned_ref }}</span>
            <template v-if="(d.planned_request_type || 'Invest') === 'Redeem'">
              → need {{ formatINR(d.is_shortfall ? d.redemption_need : 0) }}
            </template>
            <template v-else-if="d.invest_flipped_to_shortfall">
              → shortfall {{ formatINR(Math.abs(d.investable_surplus || d.cash_gap || 0)) }}
            </template>
            <template v-else>
              → free cash {{ formatINR(Math.max(0, d.investable_surplus || 0)) }}
            </template>
          </div>
        </div>
        <!-- Invest open, but this horizon is a shortfall → replace with redeem -->
        <p v-if="d.invest_flipped_to_shortfall" class="mt-1 text-p-base text-amber-800">
          Do not invest
          {{ formatINR(d.planned_investment) }}. This horizon needs
          {{ formatINR(d.redemption_need || Math.abs(d.investable_surplus || 0)) }} more cash —
          cancel the invest proposal and create a redeem proposal instead.
        </p>
        <!-- Redeem: horizon flipped to free cash -->
        <p v-else-if="d.redeem_no_longer_needed" class="mt-1 text-p-base text-amber-800">
          This horizon now shows free cash
          {{ formatINR(Math.max(0, d.investable_surplus || 0)) }} — the open redeem may no longer be
          needed. Review or cancel it on Proposal before acting.
        </p>
        <!-- Redeem: still short but request larger than today’s need -->
        <p v-else-if="d.redeem_over_need > 0" class="mt-1 text-p-base text-amber-800">
          Today’s shortfall need is
          {{ formatINR(d.redemption_need) }} — the open redeem is
          {{ formatINR(d.redeem_over_need) }} higher. Confirm the amount on Proposal before creating
          an instruction.
        </p>
        <!-- Redeem: still short but request smaller than today’s need -->
        <p v-else-if="d.redeem_under_need > 0" class="mt-1 text-p-base text-amber-800">
          Today’s shortfall need is
          {{ formatINR(d.redemption_need) }} — the open redeem is
          {{ formatINR(d.redeem_under_need) }} short. Refresh the amount on Proposal before creating
          an instruction.
        </p>
        <!-- Invest: free cash still positive but below the open request -->
        <p v-else-if="d.over_allocated > 0" class="mt-1 text-p-base text-amber-800">
          Cash moved since the proposal. Free cash is
          {{ formatINR(d.over_allocated) }} lower — do not deploy the full amount; refresh the
          proposal on Proposal before creating an instruction.
        </p>
        <p v-else class="mt-1 text-p-base text-gray-600">
          <template v-if="(d.planned_request_type || 'Invest') === 'Redeem'">
            Open redeem still covers today’s shortfall need for this horizon.
          </template>
          <template v-else>
            Proposal still fits today’s free cash after the daily balance update.
          </template>
        </p>
        <div class="mt-2 flex flex-wrap gap-2">
          <Button
            v-if="d.invest_flipped_to_shortfall && d.liquid_fund_total"
            size="sm"
            variant="solid"
            @click="$router.push({ path: '/proposal', query: { start: 'redeem' } })"
          >
            Replace with redeem
          </Button>
          <Button size="sm" variant="outline" @click="$router.push('/proposal')">
            Open proposal
          </Button>
        </div>
      </div>

      <div
        v-if="d.cash_gap > 0 && !d.incoming_covers_shortfall"
        class="mb-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
      >
        <div class="font-medium">Liquidity shortfall — redeem from portfolio</div>
        <p class="mt-1 text-p-base">
          Actual free cash is short
          {{ formatINR(d.cash_gap) }} (bank − commitments − policy).
          <span v-if="d.liquid_fund_total">
            Suggest redeem {{ formatINR(d.redemption_need) }} from liquid funds (available
            {{ formatINR(d.liquid_fund_total) }}).
          </span>
          <span v-else>No portfolio holdings on file to redeem.</span>
        </p>
        <div class="mt-2 flex flex-wrap gap-2">
          <Button
            v-if="!d.has_open_request && d.liquid_fund_total"
            size="sm"
            variant="solid"
            @click="$router.push({ path: '/proposal', query: { start: 'redeem' } })"
          >
            Start redeem
          </Button>
          <Button size="sm" variant="outline" @click="$router.push('/holdings')">
            Open portfolio
          </Button>
        </div>
      </div>

      <!-- Plan work surface: commitments + incoming in horizon -->
      <section id="commitments" class="rounded-md border border-gray-200 bg-white">
        <header class="border-b border-gray-100 px-4 py-3">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h2 class="text-base font-semibold text-gray-900">
                Plan
                <span class="font-normal text-gray-500">({{ d.horizon_days }}d)</span>
              </h2>
              <p class="mt-0.5 text-xs text-gray-500">
                Outflows reserve free cash; incoming is expected separately (not in free cash).
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <Button
                v-if="planRows.length && !hasBanks"
                size="sm"
                variant="solid"
                @click="$router.push({ path: '/cash', query: { add: '1' } })"
              >
                Add bank account
              </Button>
              <Button
                v-if="planRows.length"
                size="sm"
                variant="solid"
                @click="openNew"
              >
                Add payment
              </Button>
            </div>
          </div>

          <div class="mt-2.5 flex gap-2">
            <FormControl
              v-model="statusFilter"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="planStatusOptions"
            />
            <FormControl
              v-model="effectFilter"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="planEffectOptions"
            />
            <FormControl
              v-model="categoryFilter"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="planCategoryOptions"
            />
          </div>
        </header>

        <EmptyState
          v-if="!nestedCommitments.length && planFiltersActive"
          variant="filter"
          title="No commitments in this filter"
          description="Try another status, direction, or category."
        >
          <template #actions>
            <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
          </template>
        </EmptyState>
        <EmptyState
          v-else-if="!nestedCommitments.length && !hasBanks"
          variant="bank"
          title="Add a bank account first"
          description="Statement balances unlock free cash. Then add planned payments for the horizon."
        >
          <template #actions>
            <Button
              size="sm"
              variant="solid"
              @click="$router.push({ path: '/cash', query: { add: '1' } })"
            >
              Add bank account
            </Button>
            <Button size="sm" variant="outline" @click="openNew">Add payment</Button>
          </template>
        </EmptyState>
        <EmptyState
          v-else-if="!nestedCommitments.length"
          variant="plan"
          title="No payments planned yet"
          description="Add a planned payment to reserve free cash for the next few days."
        >
          <template #actions>
            <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
          </template>
        </EmptyState>

        <ul
          v-else
          class="max-h-[70vh] divide-y divide-gray-100 overflow-y-auto"
        >
          <CommitmentRow
            v-for="u in nestedCommitments"
            :key="u.name"
            hoverable
            :row="u"
            :as-of="asOfDate"
            :expanded="isGroupExpanded(u.name)"
            :marking="marking === u.name"
            :can-mark-paid="groupCanMarkPaid(u)"
            @toggle-group="toggleGroup(u.name)"
            @edit="(payload) => openEdit(payload?._schedule ? payload : u)"
            @mark-paid="(payload) => markPaid(payload?._schedule ? payload : u)"
          />
        </ul>
      </section>
    </template>

    <PlanCalendarDialog
      :model-value="showPlanCalendar"
      @update:model-value="onPlanCalendarOpenChange"
      @edit="openEdit"
      @changed="loadMis(true)"
    />

    <Dialog
      v-model="showNew"
      :options="{
        title: form.edit_mode === 'split_line'
          ? 'Edit split installment'
          : form.edit_mode === 'split_schedule'
            ? 'Edit split payment'
            : form.name
              ? 'Edit payment'
              : 'New upcoming payment',
      }"
    >
      <template #body-content>
        <div class="space-y-3">
          <template v-if="form.edit_mode === 'split_line'">
            <p class="text-sm text-gray-600">{{ form.title }}</p>
            <div class="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
              <div class="flex justify-between gap-3">
                <span class="text-gray-500">Due</span>
                <span class="font-medium tabular-nums">{{ form.due_date || '—' }}</span>
              </div>
              <div class="mt-1 flex justify-between gap-3">
                <span class="text-gray-500">Amount</span>
                <span class="font-medium tabular-nums">{{ formatINR(form.amount) }}</span>
              </div>
            </div>
            <FormControl
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              v-model="form.probability"
              type="number"
              label="Probability (%)"
              :min="0"
              :max="100"
            />
            <p class="text-xs text-gray-500">
              Amount and due date come from the split schedule. Open Plan to re-split.
            </p>
          </template>
          <template v-else-if="form.edit_mode === 'split_schedule'">
            <FormControl v-model="form.title" label="Title" />
            <div class="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
              <div class="flex justify-between gap-3">
                <span class="text-gray-500">Total (planned)</span>
                <span class="font-medium tabular-nums">{{ formatINR(form.amount) }}</span>
              </div>
            </div>
            <ul class="divide-y divide-gray-100 overflow-hidden rounded-md border border-gray-200">
              <li
                v-for="(line, idx) in form.splits"
                :key="line.name || idx"
                class="space-y-2 bg-white px-3 py-2.5"
              >
                <div class="text-sm font-medium text-gray-900">
                  Due {{ line.due_date || '—' }} ·
                  <span class="tabular-nums">{{ formatINR(line.amount) }}</span>
                  <span
                    v-if="line.status === 'Paid'"
                    class="ml-1 text-[10px] font-medium text-gray-500"
                    >Paid</span
                  >
                </div>
                <FormControl
                  v-if="
                    (form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff') &&
                    line.status !== 'Paid'
                  "
                  v-model="line.probability"
                  type="number"
                  label="Probability (%)"
                  :min="0"
                  :max="100"
                />
              </li>
            </ul>
            <p class="text-xs text-gray-500">
              Amounts are set by the split schedule. Open Plan → Re-split to remap.
            </p>
            <FormControl v-model="form.notes" type="textarea" label="Notes" />
          </template>
          <template v-else>
            <FormControl
              v-model="form.category"
              type="select"
              label="Category"
              :options="categoryOptions"
              @update:model-value="onCategoryChange"
            />
            <FormControl v-model="form.title" label="Title" />
            <FormControl
              v-model="form.cash_effect"
              type="select"
              label="Cash effect"
              :options="cashEffectOptions"
              :disabled="!!form.parent_payment || !!form.is_recurring"
              @update:model-value="onCashEffectChange"
            />
            <FormControl
              v-model="form.due_date"
              type="date"
              :label="form.is_recurring ? 'Next due' : 'Due date'"
              :disabled="!!form.parent_payment"
            />
            <p
              v-if="form.parent_payment"
              class="rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-950"
            >
              Due date follows the parent plan row.
            </p>
            <CurrencyControl
              v-model="form.amount"
              :label="
                form.is_recurring
                  ? `Amount each ${frequencyUnit(form.frequency)}`
                  : 'Amount'
              "
            />
            <FormControl
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              v-model="form.probability"
              type="number"
              label="Probability (%)"
              :min="0"
              :max="100"
            />
            <Checkbox
              v-if="
                !form.source_doctype &&
                !form.parent_payment &&
                (form.cash_effect === 'Outflow' || form.is_recurring)
              "
              v-model="form.is_recurring"
              label="Repeats (outgoing)"
              @update:model-value="onRecurringToggle"
            />
            <FormControl
              v-if="form.is_recurring"
              v-model="form.frequency"
              type="select"
              label="Frequency"
              :options="frequencyOptions"
            />
            <FormControl
              v-if="form.is_recurring"
              v-model="form.recurrence_end"
              type="date"
              label="Repeat until (optional)"
            />
            <FormControl
              v-if="form.name && !form.is_recurring"
              v-model="form.status"
              type="select"
              label="Status"
              :options="statusOptions"
            />
            <FormControl v-model="form.notes" type="textarea" label="Notes" />
          </template>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="savePayment">
          {{ form.name ? 'Save' : 'Save as Planned' }}
        </Button>
        <Button variant="outline" @click="showNew = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import { toast } from '@/utils/toast'
import CommitmentRow from '@/components/CommitmentRow.vue'
import CurrencyControl from '@/components/CurrencyControl.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import PlanCalendarDialog from '@/components/PlanCalendarDialog.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { usePlanCalendar } from '@/composables/usePlanCalendar'
import { formatDate, formatINR } from '@/utils/format'
import { frequencyUnit, isOverdue as isOverdueDue } from '@/utils/commitment'
import { groupMembers, nestPlanRows, planSignedNet } from '@/utils/planNest'

defineOptions({ name: 'Dashboard' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const { horizon } = useHorizon()
const { showPlanCalendar, onPlanCalendarOpenChange, syncCalendarFromRoute } =
  usePlanCalendar('/')
const statusFilter = ref('all')
const effectFilter = ref('all')
const categoryFilter = ref('all')
/** Group parents expanded by name; default collapsed. */
const expandedGroups = ref({})
const showNew = ref(false)
const saving = ref(false)
const marking = ref(null)
const categoryOptions = [
  'Salary',
  'Import-LC',
  'Vendor',
  'Customer',
  'Tax',
  'Loan',
  'FD Maturity',
  'Loan Proceeds',
  'Other',
].map((c) => ({ label: c, value: c }))
const cashEffectOptions = [
  { label: 'Outflow (pay)', value: 'Outflow' },
  { label: 'Inflow (receive)', value: 'Inflow' },
]
const frequencyOptions = ['Weekly', 'Monthly', 'Quarterly'].map((f) => ({
  label: f,
  value: f,
}))
const statusOptions = ['Planned', 'Paid', 'Cancelled'].map((s) => ({ label: s, value: s }))

const categoryValues = categoryOptions.map((c) => c.value)

const emptyForm = () => ({
  name: null,
  title: 'Other',
  category: 'Other',
  cash_effect: 'Outflow',
  probability: 100,
  due_date: '',
  amount: 0,
  status: 'Planned',
  notes: '',
  parent_payment: '',
  source_doctype: '',
  is_recurring: false,
  frequency: 'Monthly',
  recurrence_end: '',
  edit_mode: 'payment',
  has_splits: false,
  split_name: '',
  splits: [],
})
const form = reactive(emptyForm())

const d = computed(() => cache.getMis(company.current, horizon.value))
const loading = computed(() => cache.misLoading && !d.value)
const hasBanks = computed(() => (d.value?.banks || []).length > 0)
const incomingInfo = computed(() => {
  const face = Number(d.value?.incoming_total || 0)
  const expected = Number(d.value?.incoming_expected ?? face)
  if (face > 0.01 && Math.abs(face - expected) > 0.01) {
    return `Expected receipts (probability-weighted). Face ${formatINR(face)}. Not in free cash.`
  }
  return 'Expected receipts this horizon. Not included in free cash.'
})

/** Show expected liquidity when there is incoming, or actual is short. */
const showExpectedLiquidity = computed(() => {
  const data = d.value
  if (!data) return false
  if (data.is_shortfall) return true
  return Number(data.incoming_expected || 0) > 0.01
})

const expectedLiquidityLabel = computed(() => {
  const days = d.value?.horizon_days
  return days != null ? `Expected (${days}d)` : 'Expected'
})

const expectedLiquidityHint = computed(() => {
  const data = d.value
  if (!data) return 'With incoming'
  if (data.incoming_covers_shortfall) return 'Covers shortfall'
  if (data.expected_is_shortfall) return 'Still short'
  return 'With incoming'
})

const expectedLiquidityInfo = computed(() => {
  const data = d.value
  if (!data) return ''
  if (data.incoming_covers_shortfall) {
    return 'Bank − commitments + expected incoming − policy. Receipts this horizon cover the gap if they land.'
  }
  if (data.expected_is_shortfall) {
    return 'Bank − commitments + expected incoming − policy. Still short after expected incoming.'
  }
  return 'Bank − commitments + expected incoming − policy.'
})

function onCategoryChange(value) {
  const next = value || form.category
  if (!form.title || categoryValues.includes(form.title)) {
    form.title = next
  }
}

function onRecurringToggle() {
  if (form.is_recurring) {
    form.cash_effect = 'Outflow'
    if (!form.frequency) form.frequency = 'Monthly'
  }
}

function onCashEffectChange(value) {
  if (value !== 'Outflow' && form.is_recurring) {
    form.is_recurring = false
  }
}

async function loadMis(force = false) {
  if (!company.current) return
  try {
    await call('lyqd.api.spa.relink_commitment_parents', { company: company.current })
  } catch {
    /* ignore */
  }
  await Promise.all([
    cache.ensureMis({
      company: company.current,
      horizonDays: horizon.value,
      force,
    }),
    // Warm full plan for the calendar dialog
    cache.ensurePlan({ company: company.current, force }),
  ])
}

function refresh() {
  return loadMis(true)
}

watch(
  [() => company.current, horizon],
  () => {
    loadMis(false)
  },
  { immediate: true },
)

onActivated(() => {
  loadMis(false)
  syncCalendarFromRoute()
})

const asOfDate = computed(() => d.value?.as_of || new Date().toISOString().slice(0, 10))
/** Morning bank cash uses T-1 statement date (falls back to planning as_of). */
const bankAsOf = computed(() => d.value?.bank_as_of || d.value?.as_of || asOfDate.value)

const bankCashHint = computed(() =>
  bankAsOf.value ? `As of ${formatDate(bankAsOf.value)}` : 'T-1 statements',
)
const bankCashInfo = computed(
  () =>
    `Morning planning uses T-1 statement balances (as of ${formatDate(bankAsOf.value)}). Update on Bank balances.`,
)

const staleBanks = computed(() => {
  const asOf = bankAsOf.value
  return (d.value?.banks || []).filter((ba) => !ba.balance_date || ba.balance_date !== asOf)
})

const planRows = computed(() => {
  const out = d.value?.upcoming || []
  const incoming = d.value?.incoming || []
  return [...out, ...incoming]
})

function isOverdue(u) {
  return isOverdueDue(u.due_date, asOfDate.value)
}

function isDueSoon(u) {
  const due = u?.due_date
  if (!due) return false
  const a = new Date(asOfDate.value)
  const b = new Date(due)
  const days = Math.round((b - a) / 86400000)
  return days >= 0 && days <= 3
}

const planStatusOptions = computed(() => {
  const rows = planRows.value
  return [
    { label: `All (${rows.length})`, value: 'all' },
    { label: `Overdue (${rows.filter(isOverdue).length})`, value: 'overdue' },
    { label: `Due in 3 days (${rows.filter(isDueSoon).length})`, value: 'soon' },
  ]
})

const planCategories = computed(() => {
  const set = new Set(planRows.value.map((r) => r.category).filter(Boolean))
  return [...set].sort()
})

const planCategoryOptions = computed(() => [
  { label: 'Category', value: 'all' },
  ...planCategories.value.map((c) => ({ label: c, value: c })),
])

const planEffectOptions = computed(() => {
  const nested = nestPlanRows(planRows.value)
  const outgoing = nested.filter((r) => planSignedNet(r) > 0.01).length
  const incoming = nested.filter((r) => planSignedNet(r) < -0.01).length
  return [
    { label: 'Direction', value: 'all' },
    { label: `Outgoing (${outgoing})`, value: 'outflow' },
    { label: `Incoming (${incoming})`, value: 'inflow' },
  ]
})

const planFiltersActive = computed(
  () =>
    statusFilter.value !== 'all' ||
    effectFilter.value !== 'all' ||
    categoryFilter.value !== 'all',
)

function filterNestedPlan(nestedRoots) {
  let nested = nestedRoots || []
  if (statusFilter.value === 'overdue') nested = nested.filter(isOverdue)
  else if (statusFilter.value === 'soon') nested = nested.filter(isDueSoon)
  if (categoryFilter.value !== 'all') {
    nested = nested.filter((r) => r.category === categoryFilter.value)
  }
  if (effectFilter.value === 'outflow') {
    nested = nested.filter((r) => planSignedNet(r) > 0.01)
  } else if (effectFilter.value === 'inflow') {
    nested = nested.filter((r) => planSignedNet(r) < -0.01)
  }
  return nested
    .slice()
    .sort((a, b) => String(a.due_date || '').localeCompare(String(b.due_date || '')))
}

const nestedCommitments = computed(() =>
  filterNestedPlan(nestPlanRows(planRows.value)),
)

function isGroupExpanded(name) {
  return !!expandedGroups.value[name]
}

function toggleGroup(name) {
  expandedGroups.value = {
    ...expandedGroups.value,
    [name]: !expandedGroups.value[name],
  }
}

function groupCanMarkPaid(row) {
  return groupMembers(row).some((m) => m.status === 'Planned')
}

function openNew() {
  Object.assign(form, emptyForm(), { due_date: asOfDate.value })
  showNew.value = true
}

function openEdit(u) {
  if (u?._schedule && u.split_name && u.parent_payment) {
    Object.assign(form, emptyForm(), {
      name: u.parent_payment,
      title: u.title || '',
      category: u.category || 'Other',
      cash_effect: u.cash_effect === 'Setoff' ? 'Inflow' : u.cash_effect || 'Outflow',
      probability: u.probability != null ? Number(u.probability) : 100,
      due_date: u.due_date,
      amount: Number(u.amount) || 0,
      status: u.status || 'Planned',
      source_doctype: u.source_doctype || '',
      edit_mode: 'split_line',
      has_splits: true,
      split_name: u.split_name,
      splits: [
        {
          name: u.split_name,
          amount: Number(u.amount) || 0,
          due_date: u.due_date,
          status: u.status || 'Planned',
          probability: u.probability != null ? Number(u.probability) : 100,
        },
      ],
    })
    showNew.value = true
    return
  }
  const splits = (u._children || [])
    .filter((c) => c._schedule)
    .map((c) => ({
      name: c.split_name || c.name,
      amount: Number(c.amount) || 0,
      due_date: c.due_date,
      status: c.status || 'Planned',
      probability: c.probability != null ? Number(c.probability) : 100,
    }))
  const hasSplits = Boolean(u._has_splits && splits.length)
  Object.assign(form, emptyForm(), {
    name: u.name,
    title: u.title,
    category: u.category || 'Other',
    cash_effect: u.cash_effect === 'Setoff' ? 'Inflow' : u.cash_effect || 'Outflow',
    probability: u.probability != null ? Number(u.probability) : 100,
    parent_payment: u.parent_payment || '',
    source_doctype: u.source_doctype || '',
    due_date: u.due_date,
    amount: hasSplits
      ? splits
          .filter((s) => s.status === 'Planned')
          .reduce((sum, s) => sum + (Number(s.amount) || 0), 0)
      : u.period_amount != null
        ? u.period_amount
        : u.amount,
    status: u.status || 'Planned',
    notes: u.notes || '',
    is_recurring: !!u.is_recurring,
    frequency: u.frequency || 'Monthly',
    recurrence_end: u.recurrence_end || '',
    edit_mode: hasSplits ? 'split_schedule' : 'payment',
    has_splits: hasSplits,
    splits,
  })
  showNew.value = true
}

async function markPaid(u) {
  marking.value = u.name
  try {
    // GL schedule line from Cash position (expanded) or nested child
    if (u._schedule && u.split_name && u.parent_payment) {
      await call('lyqd.api.spa.mark_upcoming_split_paid', {
        parent: u.parent_payment,
        split_row_name: u.split_name,
      })
      toast.success('Marked schedule line paid')
      cache.invalidatePlanOnly(company.current)
      await loadMis(true)
      return
    }
    const scheduleKids = (u._children || []).filter(
      (m) => m._schedule && m.status === 'Planned' && m.split_name,
    )
    if (scheduleKids.length) {
      for (const m of scheduleKids) {
        await call('lyqd.api.spa.mark_upcoming_split_paid', {
          parent: u.name,
          split_row_name: m.split_name,
        })
      }
      toast.success(
        scheduleKids.length > 1
          ? `Marked ${scheduleKids.length} schedule lines paid`
          : 'Marked schedule line paid',
      )
      cache.invalidatePlanOnly(company.current)
      await loadMis(true)
      return
    }
    const targets = groupMembers(u).filter((m) => m.status === 'Planned' && !m._schedule)
    let advanced = 0
    for (const m of targets) {
      await call('lyqd.api.spa.save_upcoming_payment', {
        doc: {
          name: m.name,
          company: company.current,
          title: m.title,
          category: m.category,
          due_date: m.due_date,
          amount: m.period_amount != null ? m.period_amount : m.amount,
          period_amount: m.period_amount != null ? m.period_amount : m.amount,
          cash_effect: m.cash_effect,
          is_recurring: m.is_recurring ? 1 : 0,
          frequency: m.frequency,
          recurrence_end: m.recurrence_end,
          status: 'Paid',
          notes: m.notes,
        },
      })
      if (m.is_recurring) advanced += 1
    }
    toast.success(
      advanced && targets.length === 1
        ? `Recorded ${(u.frequency || 'Monthly').toLowerCase()} · next due advanced`
        : targets.length > 1
          ? `Marked ${targets.length} paid`
          : `Marked ${u.title} as paid`,
    )
    cache.invalidatePlanOnly(company.current)
    await loadMis(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not mark paid')
  } finally {
    marking.value = null
  }
}

async function savePayment() {
  saving.value = true
  try {
    const isSplitEdit =
      form.edit_mode === 'split_line' || form.edit_mode === 'split_schedule'
    const splitsPayload =
      form.edit_mode === 'split_line'
        ? [
            {
              name: form.split_name,
              probability: Number(form.probability ?? 100),
              status: form.status || 'Planned',
            },
          ]
        : form.edit_mode === 'split_schedule'
          ? (form.splits || []).map((s) => ({
              name: s.name,
              probability: Number(s.probability ?? 100),
              status: s.status || 'Planned',
            }))
          : undefined
    await call('lyqd.api.spa.save_upcoming_payment', {
      doc: {
        name: form.name,
        company: company.current,
        title: form.title,
        category: form.category,
        cash_effect: form.is_recurring ? 'Outflow' : form.cash_effect || 'Outflow',
        probability:
          !isSplitEdit &&
          !form.is_recurring &&
          (form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff')
            ? Number(form.probability ?? 100)
            : undefined,
        due_date: form.due_date,
        amount: form.amount,
        period_amount: form.amount,
        is_recurring: form.is_recurring ? 1 : 0,
        frequency: form.is_recurring ? form.frequency || 'Monthly' : null,
        recurrence_end: form.is_recurring ? form.recurrence_end || null : null,
        status: isSplitEdit
          ? undefined
          : form.name && !form.is_recurring
            ? form.status
            : 'Planned',
        notes: form.notes,
        splits: splitsPayload,
      },
    })
    showNew.value = false
    try {
      toast.success(form.name ? 'Payment updated' : 'Payment added to plan')
    } catch (_) {
      /* toast host is best-effort */
    }
    // Cancelled books rows reappear in From-books on Commitments.
    if (!isSplitEdit && form.status === 'Cancelled') {
      cache.invalidatePlanRelated(company.current)
    } else {
      cache.invalidatePlanOnly(company.current)
    }
    await loadMis(true)
  } catch (e) {
    try {
      toast.error(e.messages?.[0] || e.message || 'Save failed')
    } catch (_) {
      /* ignore */
    }
  } finally {
    saving.value = false
  }
}
</script>
