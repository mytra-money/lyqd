<template>
  <div>
    <PageHeader
      title="Bank cash"
      :subtitle="cashSubtitle"
    >
      <Button variant="outline" @click="$router.push('/')">Cash position</Button>
      <Button variant="outline" :loading="loading" @click="refresh">Refresh</Button>
      <Button variant="solid" @click="openNew">Update balance</Button>
    </PageHeader>

    <div v-if="loading && !cash.data" class="mb-4 text-sm text-gray-500">Loading bank cash…</div>

    <div class="mb-6 rounded-md border border-gray-200 bg-white p-4">
      <div class="mb-3">
        <h2 class="text-base font-semibold text-gray-900">Eligible cash</h2>
        <p class="mt-0.5 text-p-base text-gray-600">
          Total {{ formatINRCompact(cash.data?.total) }} as of {{ cash.data?.as_of || '—' }}
          <span v-if="cash.data?.books_source">
            · accounts from {{ cash.data.books_source
            }}{{ cash.data.books_company ? ` (${cash.data.books_company})` : '' }}
          </span>
          <span v-if="cash.data?.balance_source">
            · balances
            {{
              cash.data.balance_source === 'remote'
                ? 'on remote'
                : 'on this site'
            }}
          </span>
        </p>
        <p
          v-if="cash.data?.message"
          class="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          {{ cash.data.message }}
        </p>
      </div>
      <BankAccountCards
        :accounts="cashCards"
        :show-add="false"
        :empty-hint="
          cash.data?.message ||
          'No eligible bank accounts. Configure banks under Settings.'
        "
        @add="$router.push('/settings?tab=banks')"
      />
    </div>

    <Dialog v-model="show" :options="{ title: 'Update statement balance' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl
            v-model="form.bank_account"
            type="select"
            label="Bank account"
            :options="bankSelectOptions"
          />
          <FormControl v-model="form.as_on" type="date" label="Date" />
          <FormControl v-model="form.balance" type="number" label="Balance" />
          <p class="text-xs text-gray-500">
            Saves to Bank Account Balance (same as ERPNext Banking closing as per statement).
          </p>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
        <Button variant="outline" @click="show = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref, watch } from 'vue'
import { call, toast } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import BankAccountCards from '@/components/BankAccountCards.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatINRCompact } from '@/utils/format'

defineOptions({ name: 'Cash' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const show = ref(false)
const saving = ref(false)
const form = reactive({ bank_account: '', as_on: '', balance: 0 })

const cash = computed(() => ({
  data: cache.getCash(company.current),
}))
const loading = computed(() => cache.cashLoading && !cash.value.data)

const cashSubtitle = computed(() => {
  if (cash.value.data?.books_source === 'Other Site') {
    return 'Bank accounts from the configured remote site. Edit balances here when allowed.'
  }
  return 'Statement balances live on LYQD Bank Balance — edit on Cash position or here.'
})

const cashCards = computed(() =>
  (cash.value.data?.accounts || []).map((row) => ({
    name: row.bank_account || row.name,
    account_name: row.account_name,
    account: row.gl_account || row.account,
    bank: row.bank,
    is_default: row.is_default,
    account_type: row.account_type,
    bank_account_no: row.bank_account_no,
    balance: row.balance,
    balance_date: row.balance_date,
    source: row.source,
  })),
)

const bankSelectOptions = computed(() =>
  cashCards.value.map((b) => ({
    label: b.account_name || b.name,
    value: b.name,
  })),
)

async function loadCash(force = false) {
  if (!company.current) return
  await cache.ensureCash({ company: company.current, force })
}

function refresh() {
  return loadCash(true)
}

watch(
  () => company.current,
  () => loadCash(false),
  { immediate: true },
)

onActivated(() => loadCash(false))

function openNew() {
  form.bank_account = bankSelectOptions.value[0]?.value || ''
  form.as_on = cash.value.data?.as_of || new Date().toISOString().slice(0, 10)
  form.balance = cashCards.value[0]?.balance || 0
  show.value = true
}

async function save() {
  saving.value = true
  try {
    await call('lyqd.api.spa.set_daily_bank_balance', {
      bank_account: form.bank_account,
      balance: form.balance,
      as_of: form.as_on,
    })
    toast.success('Statement balance saved')
    show.value = false
    cache.invalidateCashRelated(company.current)
    await loadCash(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>
