<template>
  <div>
    <PageHeader title="Bank cash" :subtitle="cashSubtitle">
      <Button variant="outline" @click="$router.push('/')">Cash position</Button>
      <Button variant="outline" :loading="loading" @click="refresh">Refresh</Button>
      <Button v-if="canAddBanks" variant="solid" @click="openAddBank">Add bank account</Button>
    </PageHeader>

    <div v-if="loading && !cash.data" class="mb-4 text-sm text-gray-500">Loading…</div>

    <div class="mb-6 rounded-md border border-gray-200 bg-white p-4">
      <div class="mb-3">
        <h2 class="text-base font-semibold text-gray-900">Eligible cash</h2>
        <p class="mt-0.5 text-p-base text-gray-600">
          Total {{ formatINRCompact(cash.data?.total) }} as of {{ cash.data?.as_of || '—' }}
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
        :show-add="canAddBanks"
        empty-title="No bank accounts"
        :empty-hint="emptyHint"
        :show-desk="false"
        @add="openAddBank"
        @toggle="openBalanceFor"
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
          <CurrencyControl v-model="form.balance" label="Balance" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
        <Button variant="outline" @click="show = false">Cancel</Button>
      </template>
    </Dialog>

    <Dialog v-model="showAdd" :options="{ title: 'Add bank account' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl v-model="addBank.account_name" label="Account name" />
          <FormControl v-model="addBank.bank" label="Bank" />
          <FormControl
            v-model="addBank.account_type"
            type="select"
            label="Account type (optional)"
            :options="['', 'Current', 'Savings', 'Cash Credit', 'Overdraft']"
          />
          <FormControl v-model="addBank.bank_account_no" label="Bank account no (optional)" />
          <FormControl
            v-model.number="addBank.opening_balance"
            type="number"
            label="Opening balance (optional)"
          />
          <label class="flex items-center gap-2 text-sm">
            <input v-model="addBank.is_default" type="checkbox" class="rounded" />
            Set as default
          </label>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="adding" @click="createBank">Create</Button>
        <Button variant="outline" @click="showAdd = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref, watch } from 'vue'
import { call, toast } from 'frappe-ui'
import CurrencyControl from '@/components/CurrencyControl.vue'
import PageHeader from '@/components/PageHeader.vue'
import BankAccountCards from '@/components/BankAccountCards.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatINRCompact } from '@/utils/format'

defineOptions({ name: 'Cash' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const show = ref(false)
const showAdd = ref(false)
const saving = ref(false)
const adding = ref(false)
const form = reactive({ bank_account: '', as_on: '', balance: 0 })
const addBank = reactive({
  account_name: '',
  bank: '',
  account_type: '',
  bank_account_no: '',
  opening_balance: 0,
  is_default: false,
})

const cash = computed(() => ({
  data: cache.getCash(company.current),
}))
const loading = computed(() => cache.cashLoading && !cash.value.data)

/** Manual / This Site: add locally. Other Site (remote ERPNext): mirrored only. */
const canAddBanks = computed(() => {
  if (cash.value.data?.can_add_banks != null) return !!cash.value.data.can_add_banks
  return (cash.value.data?.books_source || 'Manual') !== 'Other Site'
})

const cashSubtitle = computed(() => 'Statement balances for this company')

const emptyHint = computed(() => cash.value.data?.message || '')

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

function openBalanceFor(ba) {
  const name = ba?.name || ba?.bank_account || ''
  form.bank_account = name || bankSelectOptions.value[0]?.value || ''
  form.as_on = cash.value.data?.as_of || new Date().toISOString().slice(0, 10)
  form.balance = ba?.balance != null ? ba.balance : cashCards.value.find((c) => c.name === name)?.balance || 0
  show.value = true
}

function openAddBank() {
  addBank.account_name = ''
  addBank.bank = ''
  addBank.account_type = ''
  addBank.bank_account_no = ''
  addBank.opening_balance = 0
  addBank.is_default = false
  showAdd.value = true
}

async function createBank() {
  if (!(addBank.account_name || '').trim()) {
    toast.error('Account name is required')
    return
  }
  adding.value = true
  try {
    await call('lyqd.api.spa.create_surplus_bank_account', {
      company: company.current,
      account_name: addBank.account_name,
      bank: addBank.bank || null,
      account_type: addBank.account_type || null,
      bank_account_no: addBank.bank_account_no || null,
      opening_balance: addBank.opening_balance || 0,
      is_default: addBank.is_default ? 1 : 0,
      add_to_policy: 1,
    })
    toast.success('Bank account ready')
    showAdd.value = false
    cache.invalidateCashRelated(company.current)
    await loadCash(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Create failed')
  } finally {
    adding.value = false
  }
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
