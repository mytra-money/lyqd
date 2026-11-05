<template>
  <div>
    <PageHeader
      title="Cash position"
      :subtitle="`As of ${d?.as_of || '—'} · ${company.current || '—'}`"
    >
      <HorizonPicker v-model="horizon" />
      <Button variant="outline" :loading="loading" @click="refresh">Refresh</Button>
    </PageHeader>

    <div v-if="loading && !d" class="text-sm text-gray-500">Loading morning view…</div>
    <template v-else-if="d">
      <!-- Hero metrics — drill into detail pages -->
      <div class="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Bank cash"
          :value="d.bank_cash"
          hint="Update statement balances"
          to="/cash"
        />
        <MetricCard
          label="Portfolio"
          :value="d.liquid_fund_total"
          hint="Liquid fund holdings"
          to="/holdings"
        />
        <MetricCard
          :label="`Commitments (${d.horizon_days}d)`"
          :value="d.upcoming_total"
          hint="Planned + overdue — open Commitments"
          to="/upcoming"
        />
        <MetricCard
          :label="d.is_shortfall ? 'Liquidity shortfall' : 'Free cash today'"
          :value="Math.abs(d.investable_surplus || 0)"
          :tone="d.is_shortfall ? 'danger' : 'success'"
          :hint="d.is_shortfall ? 'Shortfall — review redeem' : 'Tap to explain · Proposal from Free cash'"
          to="/surplus"
        />
      </div>

      <div
        v-if="staleBanks.length"
        class="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      >
        <span class="font-medium">{{ staleBanks.length }} bank balance(s)</span>
        not updated for {{ d.as_of }}.
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
        v-if="d.cash_gap > 0"
        class="mb-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
      >
        <div class="font-medium">Liquidity shortfall — redeem from portfolio</div>
        <p class="mt-1 text-p-base">
          Required {{ formatINR(d.required_cash) }} (commitments + policy reserves) vs bank cash
          {{ formatINR(d.bank_cash) }}. Gap {{ formatINR(d.cash_gap) }}
          <span v-if="d.liquid_fund_total">
            — suggest redeem {{ formatINR(d.redemption_need) }} from liquid funds (available
            {{ formatINR(d.liquid_fund_total) }}).
          </span>
          <span v-else>. No portfolio holdings on file to redeem.</span>
        </p>
        <div class="mt-2 flex flex-wrap gap-2">
          <!-- Replace / open CTAs live on the proposal-drift card when a proposal exists -->
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

      <!-- Commitments work surface -->
      <section id="commitments" class="rounded-md border border-gray-200 bg-white">
        <header class="border-b border-gray-100 px-3 py-3 sm:px-4">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h2 class="text-base font-semibold text-gray-900">
                Commitments
                <span class="font-normal text-gray-500">({{ d.horizon_days }}d)</span>
              </h2>
              <p class="mt-0.5 text-xs text-gray-500">
                Planned payments that reduce free cash.
              </p>
            </div>
            <div class="flex shrink-0 flex-col items-end gap-1.5 sm:flex-row sm:items-center">
              <Button
                v-if="filteredCommitments.length && !hasBanks"
                size="sm"
                variant="solid"
                @click="$router.push({ path: '/cash', query: { add: '1' } })"
              >
                Add bank account
              </Button>
              <Button
                v-if="filteredCommitments.length"
                size="sm"
                variant="solid"
                @click="openNew"
              >
                Add payment
              </Button>
              <button
                type="button"
                class="text-xs text-gray-500 hover:text-gray-800"
                @click="$router.push('/upcoming')"
              >
                Full list
              </button>
            </div>
          </div>

          <div class="mt-3 flex gap-1 overflow-x-auto pb-0.5">
            <button
              v-for="f in filters"
              :key="f.id"
              type="button"
              class="shrink-0 rounded-md px-2.5 py-1 text-xs font-medium"
              :class="
                commitmentFilter === f.id
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              "
              @click="commitmentFilter = f.id"
            >
              {{ f.label }}
              <span class="tabular-nums opacity-80">{{ f.count }}</span>
            </button>
          </div>
        </header>

        <EmptyState
          v-if="!filteredCommitments.length && commitmentFilter !== 'all'"
          variant="filter"
          title="No commitments in this filter"
          description="Switch filter or add a payment for this window."
        >
          <template #actions>
            <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
          </template>
        </EmptyState>
        <EmptyState
          v-else-if="!filteredCommitments.length && !hasBanks"
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
          v-else-if="!filteredCommitments.length"
          variant="plan"
          title="No payments planned yet"
          description="Add a planned payment to reserve free cash for the next few days."
        >
          <template #actions>
            <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
          </template>
        </EmptyState>

        <ul v-else class="divide-y divide-gray-100">
          <li v-for="u in nestedCommitments" :key="u.name">
            <div class="flex items-start gap-2 px-3 py-3 sm:px-4">
              <div class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center">
                <button
                  v-if="u._childCount"
                  type="button"
                  class="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                  :aria-expanded="isGroupExpanded(u.name)"
                  :aria-label="isGroupExpanded(u.name) ? 'Collapse group' : 'Expand group'"
                  @click="toggleGroup(u.name)"
                >
                  <FeatherIcon
                    :name="isGroupExpanded(u.name) ? 'chevron-down' : 'chevron-right'"
                    class="h-3.5 w-3.5"
                  />
                </button>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-medium text-gray-900">
                      {{ u.title }}
                    </div>
                    <div class="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-gray-500">
                      <Badge v-if="isOverdue(u)" theme="red" variant="subtle">Overdue</Badge>
                      <Badge v-else-if="isDueSoon(u)" theme="orange" variant="subtle"
                        >Due soon</Badge
                      >
                      <Badge v-if="u.is_recurring" theme="blue" variant="subtle">
                        {{ u.frequency || 'Monthly' }}
                      </Badge>
                      <Badge v-if="u.cash_effect === 'Inflow'" theme="green" variant="subtle"
                        >Inflow</Badge
                      >
                      <span v-if="u._childCount" class="font-medium text-gray-600"
                        >Group · {{ u._childCount + 1 }}</span
                      >
                      <span>{{ u.category }}</span>
                      <span>· Due {{ formatDate(u.due_date) }}</span>
                      <span
                        v-if="u.is_recurring && u.occurrence_count > 1"
                        class="tabular-nums text-[11px] text-gray-400"
                      >
                        · {{ formatINR(u.period_amount ?? u.amount / u.occurrence_count) }} ×
                        {{ u.occurrence_count }}
                      </span>
                      <span
                        v-else-if="u._childCount"
                        class="tabular-nums text-[11px] text-gray-400"
                      >
                        · GL {{ formatINR(u.amount) }}
                      </span>
                    </div>
                  </div>
                  <div class="w-[5.75rem] shrink-0 text-right sm:w-auto sm:min-w-[6.5rem]">
                    <template v-if="u._childCount && u._groupNet != null">
                      <div class="tabular-nums text-sm font-semibold text-gray-900">
                        {{ formatINR(u._groupNet) }}
                      </div>
                      <div class="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                        Net
                      </div>
                    </template>
                    <div
                      v-else
                      class="tabular-nums text-sm font-semibold"
                      :class="
                        u.cash_effect === 'Inflow' || u.cash_effect === 'Setoff'
                          ? 'text-emerald-800'
                          : 'text-gray-900'
                      "
                    >
                      {{
                        u.cash_effect === 'Inflow' || u.cash_effect === 'Setoff' ? '−' : ''
                      }}{{ formatINR(u.amount) }}
                    </div>
                    <div class="mt-1.5 flex items-center justify-end gap-0.5">
                      <button
                        v-if="groupCanMarkPaid(u)"
                        type="button"
                        class="inline-flex h-7 items-center gap-1 rounded px-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
                        :disabled="marking === u.name"
                        :title="
                          u.is_recurring
                            ? `Record ${(u.frequency || 'Monthly').toLowerCase()} · advance next due`
                            : 'Mark paid'
                        "
                        :aria-label="
                          u.is_recurring
                            ? `Record ${(u.frequency || 'Monthly').toLowerCase()}`
                            : 'Mark paid'
                        "
                        @click="markPaid(u)"
                      >
                        <FeatherIcon name="check" class="h-3.5 w-3.5" />
                        <span>{{ u.is_recurring ? u.frequency || 'Monthly' : 'Paid' }}</span>
                      </button>
                      <button
                        type="button"
                        class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-800"
                        title="Edit"
                        aria-label="Edit"
                        @click="openEdit(u)"
                      >
                        <FeatherIcon name="edit-2" class="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <ul
              v-if="u._childCount && isGroupExpanded(u.name)"
              class="border-t border-gray-50 bg-gray-50/50"
            >
              <li
                v-for="child in u._children"
                :key="child.name"
                class="border-l-2 border-gray-200 py-2.5 pl-8 pr-3 sm:pl-10 sm:pr-4"
              >
                <div class="truncate text-sm text-gray-800">
                  <span class="mr-1 text-gray-400">↳</span>
                  {{ child.title }}
                </div>
                <div class="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-gray-500">
                  <span>Due {{ formatDate(child.due_date) }}</span>
                  <span class="tabular-nums text-[11px] text-gray-400">
                    · GL {{ formatINR(child.amount) }}
                  </span>
                  <span>· {{ child.category }}</span>
                </div>
              </li>
            </ul>
          </li>
        </ul>
      </section>
    </template>

    <Dialog
      v-model="showNew"
      :options="{ title: form.name ? 'Edit payment' : 'New upcoming payment' }"
    >
      <template #body-content>
        <div class="space-y-3">
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
import { call, toast } from 'frappe-ui'
import CurrencyControl from '@/components/CurrencyControl.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'
import { groupMembers, nestPlanRows } from '@/utils/planNest'

defineOptions({ name: 'Dashboard' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const { horizon } = useHorizon()
const commitmentFilter = ref('all')
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
  due_date: '',
  amount: 0,
  status: 'Planned',
  notes: '',
  parent_payment: '',
  source_doctype: '',
  is_recurring: false,
  frequency: 'Monthly',
  recurrence_end: '',
})
const form = reactive(emptyForm())

const d = computed(() => cache.getMis(company.current, horizon.value))
const loading = computed(() => cache.misLoading && !d.value)
const hasBanks = computed(() => (d.value?.banks || []).length > 0)

function frequencyUnit(frequency) {
  const f = (frequency || 'Monthly').toLowerCase()
  if (f === 'weekly') return 'week'
  if (f === 'quarterly') return 'quarter'
  return 'month'
}

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
  await cache.ensureMis({
    company: company.current,
    horizonDays: horizon.value,
    force,
  })
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
})

const asOfDate = computed(() => d.value?.as_of || new Date().toISOString().slice(0, 10))

const staleBanks = computed(() => {
  const asOf = d.value?.as_of
  return (d.value?.banks || []).filter((ba) => !ba.balance_date || ba.balance_date !== asOf)
})

const upcoming = computed(() => d.value?.upcoming || [])

function daysUntil(due) {
  if (!due) return 999
  const a = new Date(asOfDate.value)
  const b = new Date(due)
  return Math.round((b - a) / 86400000)
}

function isOverdue(u) {
  return daysUntil(u.due_date) < 0
}

function isDueSoon(u) {
  const days = daysUntil(u.due_date)
  return days >= 0 && days <= 3
}

const filters = computed(() => {
  const rows = upcoming.value
  return [
    { id: 'all', label: 'All planned', count: rows.length },
    { id: 'overdue', label: 'Overdue', count: rows.filter(isOverdue).length },
    { id: 'soon', label: 'Due in 3 days', count: rows.filter(isDueSoon).length },
  ]
})

const filteredCommitments = computed(() => {
  const rows = upcoming.value
  if (commitmentFilter.value === 'overdue') return rows.filter(isOverdue)
  if (commitmentFilter.value === 'soon') return rows.filter(isDueSoon)
  return rows
})

const nestedCommitments = computed(() => nestPlanRows(filteredCommitments.value))

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
  Object.assign(form, {
    name: u.name,
    title: u.title,
    category: u.category || 'Other',
    cash_effect: u.cash_effect || 'Outflow',
    parent_payment: u.parent_payment || '',
    source_doctype: u.source_doctype || '',
    due_date: u.due_date,
    amount: u.period_amount != null ? u.period_amount : u.amount,
    status: u.status || 'Planned',
    notes: u.notes || '',
    is_recurring: !!u.is_recurring,
    frequency: u.frequency || 'Monthly',
    recurrence_end: u.recurrence_end || '',
  })
  showNew.value = true
}

async function markPaid(u) {
  marking.value = u.name
  try {
    const targets = groupMembers(u).filter((m) => m.status === 'Planned')
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
    cache.invalidatePlanRelated(company.current)
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
    await call('lyqd.api.spa.save_upcoming_payment', {
      doc: {
        name: form.name,
        company: company.current,
        title: form.title,
        category: form.category,
        cash_effect: form.is_recurring ? 'Outflow' : form.cash_effect || 'Outflow',
        due_date: form.due_date,
        amount: form.amount,
        period_amount: form.amount,
        is_recurring: form.is_recurring ? 1 : 0,
        frequency: form.is_recurring ? form.frequency || 'Monthly' : null,
        recurrence_end: form.is_recurring ? form.recurrence_end || null : null,
        status: form.name && !form.is_recurring ? form.status : 'Planned',
        notes: form.notes,
      },
    })
    toast.success(form.name ? 'Payment updated' : 'Payment added to plan')
    showNew.value = false
    cache.invalidatePlanRelated(company.current)
    await loadMis(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>
