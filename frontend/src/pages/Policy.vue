<template>
  <div>
    <PageHeader
      title="Liquidity policy"
      subtitle="Buffers, horizon, and which bank accounts feed investable surplus."
    >
      <Button variant="solid" :loading="saving" @click="save">Save policy</Button>
    </PageHeader>

    <div v-if="policy.loading && !policy.data" class="text-sm text-gray-500">Loading…</div>
    <div v-else class="max-w-2xl space-y-4">
      <div class="space-y-4 rounded-md border border-gray-200 bg-white p-4">
        <FormControl :model-value="company.current" label="Company" readonly />
        <FormControl
          v-model.number="form.min_liquidity_buffer"
          type="number"
          label="Min liquidity buffer"
        />
        <FormControl v-model.number="form.restricted_cash" type="number" label="Restricted cash" />
        <FormControl
          v-model.number="form.default_forecast_horizon_days"
          type="number"
          label="Default forecast horizon (days)"
        />
        <FormControl v-model="form.notes" type="textarea" label="Notes" />
      </div>

      <div class="rounded-md border border-gray-200 bg-white p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-gray-900">Surplus bank accounts</h2>
            <p class="mt-0.5 text-p-base text-gray-600">
              Checked accounts are included in surplus. Leave none checked to use all company bank
              accounts.
            </p>
          </div>
          <Button variant="outline" @click="showAdd = true">Add bank account</Button>
        </div>

        <div class="mt-4 space-y-2">
          <label
            v-for="ba in bankAccountList"
            :key="ba.name"
            class="flex cursor-pointer items-center gap-3 rounded-md border border-gray-100 px-3 py-2 hover:bg-gray-50"
          >
            <input
              v-model="form.selected"
              type="checkbox"
              class="rounded border-gray-300"
              :value="ba.name"
            />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-gray-900">
                {{ ba.account_name || ba.name }}
              </div>
              <div class="truncate text-xs text-gray-500">
                {{ ba.name }}
                <span v-if="ba.account">· GL {{ ba.account }}</span>
              </div>
            </div>
            <Badge v-if="ba.is_default" theme="blue">Default</Badge>
          </label>
          <div
            v-if="!bankAccountList.length"
            class="py-4 text-center text-sm text-gray-500"
          >
            {{
              bankOptions.data?.message ||
              'No company bank accounts yet. Add one to create CoA + Bank Account.'
            }}
          </div>
        </div>
      </div>
    </div>

    <Dialog v-model="showAdd" :options="{ title: 'Add bank account for surplus' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl v-model="addForm.account_name" label="Account name" />
          <FormControl v-model="addForm.bank" label="Bank (optional)" />
          <FormControl
            v-model.number="addForm.opening_balance"
            type="number"
            label="Opening balance (optional)"
          />
          <p class="text-xs text-gray-500">
            Creates a Bank-type GL under Chart of Accounts and a company Bank Account, then pins it
            on this policy.
          </p>
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
import { computed, reactive, watch, ref } from 'vue'
import { call, createResource, toast } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'

const company = useCompanyStore()
const saving = ref(false)
const showAdd = ref(false)
const adding = ref(false)
const form = reactive({
  name: null,
  min_liquidity_buffer: 0,
  restricted_cash: 0,
  default_forecast_horizon_days: 7,
  notes: '',
  selected: [],
})
const addForm = reactive({
  account_name: '',
  bank: '',
  opening_balance: 0,
})

const bankOptions = createResource({
  url: 'lyqd.api.spa.get_company_bank_account_options',
  makeParams() {
    return { company: company.current }
  },
  auto: false,
})

const bankAccountList = computed(() => bankOptions.data?.accounts || [])

const policy = createResource({
  url: 'lyqd.api.spa.get_or_create_policy',
  makeParams() {
    return { company: company.current }
  },
  auto: false,
  onSuccess(data) {
    Object.assign(form, {
      name: data.name,
      min_liquidity_buffer: data.min_liquidity_buffer,
      restricted_cash: data.restricted_cash,
      default_forecast_horizon_days: data.default_forecast_horizon_days,
      notes: data.notes || '',
      selected: (data.eligible_bank_accounts || []).map((r) => r.bank_account).filter(Boolean),
    })
  },
})

watch(
  () => company.current,
  (c) => {
    if (!c) return
    policy.reload()
    bankOptions.reload()
  },
  { immediate: true },
)

async function save() {
  saving.value = true
  try {
    const data = await call('lyqd.api.spa.save_policy', {
      doc: {
        name: form.name,
        company: company.current,
        min_liquidity_buffer: form.min_liquidity_buffer,
        restricted_cash: form.restricted_cash,
        default_forecast_horizon_days: form.default_forecast_horizon_days,
        notes: form.notes,
        is_active: 1,
        eligible_bank_accounts: form.selected.map((bank_account) => ({ bank_account })),
      },
    })
    form.name = data.name
    toast.success('Policy saved')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}

async function createBank() {
  adding.value = true
  try {
    const created = await call('lyqd.api.spa.create_surplus_bank_account', {
      company: company.current,
      account_name: addForm.account_name,
      bank: addForm.bank || null,
      opening_balance: addForm.opening_balance || 0,
      add_to_policy: 1,
    })
    await bankOptions.reload()
    await policy.reload()
    if (created.bank_account && !form.selected.includes(created.bank_account)) {
      form.selected.push(created.bank_account)
    }
    showAdd.value = false
    addForm.account_name = ''
    addForm.bank = ''
    addForm.opening_balance = 0
    toast.success('Bank account created')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Create failed')
  } finally {
    adding.value = false
  }
}
</script>
