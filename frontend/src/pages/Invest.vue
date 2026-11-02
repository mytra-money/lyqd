<template>
  <div>
    <PageHeader
      title="Invest"
      subtitle="One open investment request per company. Creating a new one cancels the previous open request."
    >
      <HorizonPicker v-model="horizon" />
      <Button variant="outline" @click="$router.push('/surplus')">View free cash</Button>
      <Button variant="solid" :loading="creating" @click="createFromSurplus">
        {{ active ? 'Replace with today’s free cash' : 'Invest today’s free cash' }}
      </Button>
    </PageHeader>

    <div class="mb-5 rounded-md border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700">
      <span class="font-medium text-gray-900">Flow:</span>
      free cash → confirm request → one instruction → approve / ready.
      Parallel confirmed requests are not allowed (same cash pool).
    </div>

    <div
      v-if="!company.investmentAccountActivated"
      class="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      <span class="font-medium">Investment account not activated.</span>
      You can draft and confirm requests, but instructions stay locked until Mytra activates the
      account.
      <button
        type="button"
        class="ml-1 font-medium underline"
        @click="$router.push({ path: '/settings', query: { tab: 'investment' } })"
      >
        Request activation
      </button>
    </div>

    <!-- Active request -->
    <section class="mb-5 rounded-lg border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-4 py-3">
        <h2 class="text-sm font-semibold text-gray-900">Open request</h2>
        <p class="mt-0.5 text-xs text-gray-500">
          At most one Draft or Confirmed request. Cash position tracks this amount.
        </p>
      </header>

      <div v-if="!active" class="px-4 py-10 text-center text-sm text-gray-500">
        No open investment request.
        <button type="button" class="ml-1 text-gray-900 underline" @click="createFromSurplus">
          Create from free cash
        </button>
      </div>

      <div v-else class="flex flex-wrap items-center justify-between gap-4 px-4 py-4">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-mono text-xs text-gray-500">{{ active.name }}</span>
            <Badge :theme="statusTheme(active.status)">{{ statusLabel(active.status) }}</Badge>
          </div>
          <div class="mt-1 text-2xl font-semibold tabular-nums text-gray-900">
            {{ formatINR(active.proposed_amount) }}
          </div>
          <div class="mt-1 text-xs text-gray-500">
            As of {{ formatDate(active.as_of) }}
            <span v-if="active.display_scheme_label"> · {{ active.display_scheme_label }}</span>
            <span v-if="activeInstruction"> · Instruction {{ activeInstruction.name }}</span>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button
            v-if="active.status === 'Draft'"
            variant="outline"
            @click="freeze(active.name)"
          >
            Confirm amount
          </Button>
          <Button
            v-if="active.status === 'Frozen' && !activeInstruction"
            variant="solid"
            :disabled="!company.investmentAccountActivated"
            @click="toInstruction(active.name)"
          >
            Create instruction
          </Button>
          <Button
            v-if="activeInstruction"
            variant="outline"
            @click="$router.push('/instructions')"
          >
            Open instruction
          </Button>
          <Button variant="ghost" :loading="cancelling" @click="cancelActive">Cancel request</Button>
        </div>
      </div>
    </section>

    <!-- History -->
    <section class="rounded-lg border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-4 py-3">
        <h2 class="text-sm font-semibold text-gray-900">History</h2>
        <p class="mt-0.5 text-xs text-gray-500">Superseded and cancelled requests (audit only).</p>
      </header>
      <div v-if="!history.length" class="px-4 py-8 text-center text-sm text-gray-500">
        No prior requests.
      </div>
      <ul v-else class="divide-y divide-gray-100">
        <li
          v-for="row in history"
          :key="row.name"
          class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        >
          <div class="min-w-0">
            <div class="font-mono text-xs text-gray-500">{{ row.name }}</div>
            <div class="mt-0.5 text-xs text-gray-500">
              {{ formatDate(row.as_of) }}
              <span v-if="row.notes"> · {{ row.notes }}</span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Badge theme="gray" variant="subtle">{{ statusLabel(row.status) }}</Badge>
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
import { computed, ref, watch } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import { useCompanyStore } from '@/stores/company'
import { useHorizon } from '@/composables/useHorizon'
import { formatDate, formatINR } from '@/utils/format'

const company = useCompanyStore()
const router = useRouter()
const { horizon } = useHorizon()
const creating = ref(false)
const cancelling = ref(false)

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
    'notes',
  ],
  orderBy: 'modified desc',
  auto: false,
})

const instructions = createListResource({
  doctype: 'LYQD Investment Instruction',
  fields: ['name', 'status', 'proposal', 'amount', 'company'],
  orderBy: 'modified desc',
  pageLength: 50,
  auto: false,
})

watch(
  () => company.current,
  (c) => {
    if (!c) return
    list.update({ filters: { company: c } })
    instructions.update({ filters: { company: c } })
    list.reload()
    instructions.reload()
  },
  { immediate: true },
)

const active = computed(() =>
  (list.data || []).find((r) => r.status === 'Draft' || r.status === 'Frozen'),
)

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

function statusLabel(s) {
  if (s === 'Frozen') return 'Confirmed'
  if (s === 'Draft') return 'Draft'
  if (s === 'Cancelled') return 'Cancelled'
  return s
}

function statusTheme(s) {
  if (s === 'Frozen') return 'green'
  if (s === 'Cancelled') return 'gray'
  return 'blue'
}

async function createFromSurplus() {
  creating.value = true
  try {
    const doc = await call('lyqd.api.spa.create_proposal_from_surplus', {
      company: company.current,
      horizon_days: horizon.value,
      freeze: 1,
    })
    const n = (doc.superseded || []).length
    toast.success(
      n
        ? `New request confirmed · superseded ${n} prior open request(s)`
        : 'Investment request confirmed from today’s free cash',
    )
    list.reload()
    instructions.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create request')
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
  try {
    const doc = await call('lyqd.api.spa.create_instruction_from_proposal', { proposal })
    toast.success(`Instruction ${doc.name}`)
    router.push('/instructions')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not create instruction')
  }
}
</script>
