<template>
  <div>
    <PageHeader
      title="Portfolio"
      subtitle="Balances and history from Mytra. Instructions submitted from LYQD link by Mytra transaction ref."
    >
      <Button variant="outline" :loading="loading" @click="reload">Refresh</Button>
    </PageHeader>

    <div
      v-if="message"
      class="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      {{ message }}
    </div>

    <section class="mb-5">
      <header class="mb-3">
        <h2 class="text-sm font-semibold text-gray-900">Holdings</h2>
        <p class="mt-0.5 text-xs text-gray-500">
          Current positions as received from Mytra
          <span v-if="liquidTotal != null" class="tabular-nums text-gray-700">
            · {{ formatINR(liquidTotal) }}
          </span>
        </p>
      </header>

      <div v-if="loading && !positions.length" class="text-sm text-gray-500">Loading…</div>

      <div v-else-if="!positions.length" class="rounded-lg border border-dashed border-gray-200 px-4 py-10 text-center text-sm text-gray-500">
        No Mytra holdings yet. After an instruction is submitted and allotted on Mytra, positions
        appear here.
      </div>

      <div v-else class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="(row, idx) in positions"
          :key="row.mytra_position_ref || row.scheme_isin || idx"
          class="rounded-lg border border-gray-200 bg-white px-4 py-4"
        >
          <div class="text-sm font-semibold text-gray-900">
            {{ row.scheme_label || row.scheme || 'Scheme' }}
          </div>
          <div v-if="row.scheme_isin" class="mt-0.5 font-mono text-xs text-gray-500">
            {{ row.scheme_isin }}
          </div>
          <div class="mt-3 text-2xl font-semibold tabular-nums text-gray-900">
            {{ formatINR(row.amount) }}
          </div>
          <div class="mt-1 flex flex-wrap gap-x-3 text-xs text-gray-500">
            <span v-if="row.units != null">Units {{ row.units }}</span>
            <span v-if="row.nav != null">NAV {{ row.nav }}</span>
            <span v-if="row.as_on">As of {{ formatDate(row.as_on) }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="rounded-lg border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-4 py-3">
        <h2 class="text-sm font-semibold text-gray-900">Transaction history</h2>
        <p class="mt-0.5 text-xs text-gray-500">
          Mytra transactions plus LYQD instructions (with Mytra ref when submitted).
        </p>
      </header>

      <div v-if="!transactions.length" class="px-4 py-10 text-center text-sm text-gray-500">
        No transactions yet. Create an investment request, then submit the instruction to Mytra.
      </div>

      <ul v-else class="divide-y divide-gray-100">
        <li
          v-for="(txn, idx) in transactions"
          :key="txn.mytra_transaction_ref || txn.name || idx"
          class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-medium text-gray-900">
                {{ txn.kind || 'Transaction' }}
              </span>
              <Badge theme="gray" variant="subtle">{{ txn.source || 'mytra' }}</Badge>
              <Badge v-if="txn.status" theme="blue" variant="subtle">{{ txn.status }}</Badge>
            </div>
            <div class="mt-0.5 text-xs text-gray-500">
              <span v-if="txn.scheme_label || txn.scheme_isin">
                {{ txn.scheme_label || txn.scheme_isin }}
              </span>
              <span v-if="txn.mytra_transaction_ref" class="font-mono">
                · Mytra {{ txn.mytra_transaction_ref }}
              </span>
              <span v-else-if="txn.name" class="font-mono"> · {{ txn.name }}</span>
              <span v-if="txn.external_submit_status">
                · {{ txn.external_submit_status }}
              </span>
            </div>
          </div>
          <div class="tabular-nums text-sm font-medium text-gray-900">
            {{ formatINR(txn.amount) }}
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onActivated, ref, watch } from 'vue'
import { call, toast } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { formatDate, formatINR } from '@/utils/format'

defineOptions({ name: 'Holdings' })

const company = useCompanyStore()
const loading = ref(false)
const portfolio = ref(null)

const positions = computed(() => portfolio.value?.positions || [])
const transactions = computed(() => portfolio.value?.transactions || [])
const liquidTotal = computed(() => portfolio.value?.liquid_total)
const message = computed(() => portfolio.value?.message || '')

async function reload() {
  if (!company.current) return
  loading.value = true
  try {
    portfolio.value = await call('lyqd.api.spa.get_portfolio', { company: company.current })
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not load portfolio')
  } finally {
    loading.value = false
  }
}

watch(
  () => company.current,
  () => reload(),
  { immediate: true },
)

onActivated(() => reload())
</script>
