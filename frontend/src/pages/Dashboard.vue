<template>
  <div>
    <PageHeader
      title="Cash position"
      :subtitle="`As of ${d?.as_of || '—'} · ${company.current || '—'} · morning view (beta)`"
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
          hint="Planned + overdue — manage below"
        />
        <MetricCard
          label="Free cash today"
          :value="d.investable_surplus"
          :tone="d.is_shortfall ? 'danger' : 'success'"
          :hint="d.is_shortfall ? 'Shortfall — review redeem' : 'Tap to explain · Invest from Free cash'"
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

      <!-- Plan drift -->
      <div
        v-if="d.planned_investment > 0"
        class="mb-4 rounded-md border border-gray-200 bg-white px-4 py-3 text-sm"
      >
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <div class="font-medium text-gray-900">Investment request vs free cash today</div>
          <div class="tabular-nums text-gray-700">
            Request {{ formatINR(d.planned_investment) }}
            <span v-if="d.planned_ref" class="text-xs text-gray-500">· {{ d.planned_ref }}</span>
            → free cash {{ formatINR(d.investable_surplus) }}
          </div>
        </div>
        <p v-if="d.over_allocated > 0" class="mt-1 text-p-base text-amber-800">
          Cash moved since the request. Free cash is
          {{ formatINR(d.over_allocated) }} lower — do not deploy the full request
          <span v-if="d.liquid_fund_total">
            ; if already invested, consider redeeming up to
            {{ formatINR(Math.min(d.over_allocated, d.liquid_fund_total)) }}
          </span>
          .
        </p>
        <p v-else class="mt-1 text-p-base text-gray-600">
          Request still fits today’s free cash after the daily balance update.
        </p>
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
        <Button class="mt-2" size="sm" variant="outline" @click="$router.push('/holdings')">
          Open portfolio
        </Button>
      </div>

      <!-- Commitments work surface -->
      <section id="commitments" class="rounded-md border border-gray-200 bg-white p-4">
        <div class="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-gray-900">
              Commitments
              <span class="font-normal text-gray-500">({{ d.horizon_days }}d)</span>
            </h2>
            <p class="mt-0.5 text-p-base text-gray-600">
              Planned payments that reduce free cash. Mark paid when settled; add new as needed.
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
            <Button size="sm" variant="outline" @click="$router.push('/upcoming')">
              Full list & suggestions
            </Button>
          </div>
        </div>

        <div class="mb-3 flex flex-wrap gap-1.5">
          <button
            v-for="f in filters"
            :key="f.id"
            type="button"
            class="rounded-md px-2.5 py-1 text-xs font-medium"
            :class="
              commitmentFilter === f.id
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            "
            @click="commitmentFilter = f.id"
          >
            {{ f.label }}
            <span class="tabular-nums opacity-80">({{ f.count }})</span>
          </button>
        </div>

        <div v-if="!filteredCommitments.length" class="py-6 text-center text-sm text-gray-500">
          No commitments in this filter.
          <button type="button" class="ml-1 text-gray-800 underline" @click="openNew">
            Add a payment
          </button>
        </div>

        <ul v-else class="divide-y divide-gray-100">
          <li
            v-for="u in filteredCommitments"
            :key="u.name"
            class="flex flex-wrap items-center justify-between gap-3 py-3"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-medium text-gray-900">{{ u.title }}</span>
                <Badge v-if="isOverdue(u)" theme="red" variant="subtle">Overdue</Badge>
                <Badge v-else-if="isDueSoon(u)" theme="orange" variant="subtle">Due soon</Badge>
                <span class="text-xs text-gray-500">{{ u.category }}</span>
              </div>
              <div class="mt-0.5 text-xs text-gray-500">
                Due {{ formatDate(u.due_date) }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span class="tabular-nums text-sm font-semibold text-gray-900">
                {{ formatINR(u.amount) }}
              </span>
              <Button size="sm" variant="ghost" @click="openEdit(u)">Edit</Button>
              <Button
                size="sm"
                variant="outline"
                :loading="marking === u.name"
                @click="markPaid(u)"
              >
                Mark paid
              </Button>
            </div>
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
          <FormControl v-model="form.title" label="Title" />
          <FormControl
            v-model="form.category"
            type="select"
            label="Category"
            :options="categoryOptions"
          />
          <FormControl v-model="form.due_date" type="date" label="Due date" />
          <FormControl v-model="form.amount" type="number" label="Amount" />
          <FormControl
            v-if="form.name"
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
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'

defineOptions({ name: 'Dashboard' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const { horizon } = useHorizon()
const commitmentFilter = ref('all')
const showNew = ref(false)
const saving = ref(false)
const marking = ref(null)
const categoryOptions = [
  'Salary',
  'Import-LC',
  'Vendor',
  'Tax',
  'Loan',
  'Other',
].map((c) => ({ label: c, value: c }))
const statusOptions = ['Planned', 'Paid', 'Cancelled'].map((s) => ({ label: s, value: s }))

const emptyForm = () => ({
  name: null,
  title: '',
  category: 'Other',
  due_date: '',
  amount: 0,
  status: 'Planned',
  notes: '',
})
const form = reactive(emptyForm())

const d = computed(() => cache.getMis(company.current, horizon.value))
const loading = computed(() => cache.misLoading && !d.value)

async function loadMis(force = false) {
  if (!company.current) return
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

function openNew() {
  Object.assign(form, emptyForm(), { due_date: asOfDate.value })
  showNew.value = true
}

function openEdit(u) {
  Object.assign(form, {
    name: u.name,
    title: u.title,
    category: u.category || 'Other',
    due_date: u.due_date,
    amount: u.amount,
    status: u.status || 'Planned',
    notes: u.notes || '',
  })
  showNew.value = true
}

async function markPaid(u) {
  marking.value = u.name
  try {
    await call('lyqd.api.spa.save_upcoming_payment', {
      doc: {
        name: u.name,
        company: company.current,
        title: u.title,
        category: u.category,
        due_date: u.due_date,
        amount: u.amount,
        status: 'Paid',
        notes: u.notes,
      },
    })
    toast.success(`Marked ${u.title} as paid`)
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
        due_date: form.due_date,
        amount: form.amount,
        status: form.name ? form.status : 'Planned',
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
