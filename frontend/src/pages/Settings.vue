<template>
  <div>
    <PageHeader
      title="Settings"
      subtitle="Integrations, liquidity, banks, and investment account."
    >
      <Button variant="solid" :loading="saving" @click="saveActive">Save</Button>
    </PageHeader>

    <div class="flex flex-col gap-4 lg:flex-row">
      <nav class="flex shrink-0 gap-1 overflow-x-auto lg:w-48 lg:flex-col">
        <Button
          v-for="tab in tabs"
          :key="tab.id"
          :variant="activeTab === tab.id ? 'solid' : 'ghost'"
          class="justify-start"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </Button>
      </nav>

      <div class="min-w-0 flex-1 space-y-4">
        <!-- Integrations / Recommendations source -->
        <div
          v-if="activeTab === 'integrations'"
          class="space-y-4 rounded-md border border-gray-200 bg-white p-4"
        >
          <h2 class="text-base font-semibold text-gray-900">ERPNext</h2>
          <Checkbox v-model="erpForm.enabled" label="Enable ERPNext" />

          <div v-if="erpForm.enabled" class="space-y-4 border-t border-gray-100 pt-4">
            <Checkbox
              v-if="company.erpnextInstalled"
              v-model="erpForm.is_erpnext_in_the_current_site"
              label="ERPNext is on this site"
            />

            <div
              v-if="erpForm.source === 'This Site'"
              class="space-y-1 rounded-md border border-gray-200 bg-gray-50 p-3"
            >
              <FormControl
                v-if="localCompanies.length"
                v-model="erpForm.remote_company"
                type="select"
                label="Books company"
                :options="[{ label: 'Select company…', value: '' }, ...localCompanyOptions]"
                required
              />
              <FormControl
                v-else
                v-model="erpForm.remote_company"
                label="Books company"
                required
                placeholder="Exact ERPNext Company name on this site"
              />
              <p class="mt-1 text-xs text-gray-500">
                Required — binds this LYQD Company to one ERPNext Company on this site.
              </p>
            </div>

            <div
              v-if="erpForm.source === 'Other Site'"
              class="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-3"
            >
              <FormControl v-model="erpForm.remote_site_url" label="Site URL" />
              <FormControl v-model="erpForm.remote_api_key" label="API Key" />
              <FormControl
                v-model="erpForm.remote_api_secret"
                type="password"
                :label="
                  erpForm.has_remote_api_secret
                    ? 'API Secret (leave blank to keep current)'
                    : 'API Secret'
                "
              />
              <div>
                <FormControl
                  v-if="remoteCompanies.length"
                  v-model="erpForm.remote_company"
                  type="select"
                  label="Remote company"
                  :options="[{ label: 'Select company…', value: '' }, ...remoteCompanyOptions]"
                  required
                />
                <FormControl
                  v-else
                  v-model="erpForm.remote_company"
                  label="Remote company"
                  required
                  placeholder="Exact ERPNext Company name"
                />
                <p class="mt-1 text-xs text-gray-500">
                  Required — binds this LYQD Company to one ERPNext Company on the remote site.
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="solid"
                  :loading="testingRemote"
                  @click="connectRemote"
                >
                  Connect
                </Button>
                <span v-if="remoteConnected" class="text-xs text-green-700">Connected</span>
              </div>
            </div>

            <div
              v-if="erpForm.source === 'Other Site' && !accountsPickerReady"
              class="rounded-md border border-dashed border-gray-300 bg-white px-3 py-6 text-center text-sm text-gray-500"
            >
              Enter site URL, API Key, Secret, and remote company, then Connect.
            </div>

            <!-- Accounts from the active configured source only -->
            <div v-else-if="accountsPickerReady" class="space-y-3 border-t border-gray-100 pt-4">
              <div class="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 class="text-sm font-medium text-gray-900">Recommendation accounts</h3>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  :loading="accountOptions.loading"
                  @click="accountOptions.reload()"
                >
                  Reload accounts
                </Button>
              </div>

              <div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
                <FormControl
                  v-model="accountSearch"
                  class="min-w-0 flex-1"
                  placeholder="Search accounts"
                />
                <FormControl
                  v-model="accountRootFilter"
                  type="select"
                  :options="accountRootOptions"
                />
                <FormControl
                  v-model="accountTypeFilter"
                  type="select"
                  :options="accountTypeFilterOptions"
                />
              </div>

              <p v-if="accountOptions.data?.message" class="text-xs text-amber-800">
                {{ accountOptions.data.message }}
              </p>

              <div class="max-h-80 space-y-1 overflow-y-auto rounded-md border border-gray-200 bg-white p-2">
                <div
                  v-for="acc in orderedAccounts"
                  :key="acc.name"
                  class="flex flex-col gap-1 rounded px-2 py-1.5 hover:bg-gray-50"
                  :class="acc._child ? 'ml-4 border-l border-gray-200 pl-3' : ''"
                >
                  <div class="flex items-center gap-3">
                    <Checkbox
                      :model-value="isAccountSelected(acc.name)"
                      @update:model-value="(on) => setAccountSelected(acc.name, on)"
                    />
                    <div class="min-w-0 flex-1">
                      <div class="truncate text-sm text-gray-900">
                        {{ acc.account_name || acc.name }}
                        <span
                          v-if="acc._selected && !acc._child && refsOffParentOptions(acc.name).length"
                          class="ml-1 text-[10px] font-medium uppercase tracking-wide text-gray-400"
                        >
                          can group
                        </span>
                      </div>
                      <div class="truncate text-xs text-gray-500">
                        {{ acc.root_type || '—' }} · {{ acc.account_type || '—' }} · {{ acc.name }}
                      </div>
                    </div>
                    <Checkbox
                      v-if="isAccountSelected(acc.name)"
                      class="shrink-0"
                      label="Refs"
                      title="Show voucher / reference lines instead of account balance only"
                      :model-value="accountRefs[acc.name] !== false"
                      @update:model-value="(on) => setAccountRefs(acc.name, on)"
                    />
                  </div>
                  <div
                    v-if="isAccountSelected(acc.name) && accountRefs[acc.name] === false"
                    class="ml-7 flex flex-wrap items-center gap-2"
                  >
                    <FormControl
                      class="min-w-[12rem] flex-1"
                      type="select"
                      label="Parent"
                      :model-value="accountParents[acc.name] || ''"
                      :options="parentOptionsFor(acc.name)"
                      @update:model-value="(v) => setAccountParent(acc.name, v)"
                    />
                  </div>
                </div>
                <div
                  v-if="!orderedAccounts.length"
                  class="py-6 text-center text-sm text-gray-500"
                >
                  {{
                    accountOptions.loading
                      ? 'Loading accounts…'
                      : 'No accounts match these filters on the configured site.'
                  }}
                </div>
              </div>
              <p class="text-xs text-gray-500">
                {{ policyForm.selectedAccounts.length }} selected for suggestions
              </p>
            </div>
          </div>
        </div>

        <!-- Liquidity -->
        <div v-else-if="activeTab === 'liquidity'" class="space-y-4 rounded-md border border-gray-200 bg-white p-4">
          <FormControl
            v-model.number="policyForm.min_liquidity_buffer"
            type="number"
            label="Min liquidity buffer"
          />
          <FormControl
            v-model.number="policyForm.restricted_cash"
            type="number"
            label="Restricted cash"
          />
          <FormControl
            v-model.number="policyForm.default_forecast_horizon_days"
            type="number"
            label="Default forecast horizon (days)"
          />
          <FormControl v-model="policyForm.notes" type="textarea" label="Notes" />
        </div>

        <!-- Banks — same card language as ERPNext Banking -->
        <div v-else-if="activeTab === 'banks'" class="space-y-4 rounded-md border border-gray-200 bg-white p-4">
          <div class="flex items-start justify-between gap-3">
            <h2 class="text-base font-semibold text-gray-900">Bank accounts</h2>
            <div class="flex shrink-0 gap-2">
              <Button
                variant="outline"
                :loading="bankOptions.loading"
                @click="bankOptions.reload()"
              >
                Reload
              </Button>
              <Button v-if="!banksFromRemote" variant="outline" @click="showAddBank = true">
                Add bank account
              </Button>
            </div>
          </div>
          <p
            v-if="bankOptions.data?.message"
            class="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
          >
            {{ bankOptions.data.message }}
          </p>
          <BankAccountCards
            :accounts="bankAccountList"
            :selected="policyForm.selectedBanks"
            selectable
            :show-add="!banksFromRemote"
            :empty-title="banksFromRemote ? 'No bank accounts found' : 'No bank accounts found'"
            :empty-hint="bankEmptyHint"
            :desk-url="remoteBankDeskUrl"
            :desk-label="banksFromRemote ? 'Open remote site' : 'Open in Desk'"
            :show-desk="!banksFromRemote || !!remoteBankDeskUrl"
            @toggle="toggleBank"
            @add="showAddBank = true"
          />
        </div>

        <div v-else class="space-y-4 rounded-md border border-gray-200 bg-white p-4">
          <h3 class="text-sm font-semibold text-gray-900">Investment account</h3>

          <div
            v-if="productForm.investment_account_activated"
            class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-950"
          >
            <div class="font-medium text-emerald-950">Activated</div>
          </div>

          <div v-else class="space-y-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-3">
            <p class="text-sm font-medium text-amber-950">Not activated</p>
            <p
              v-if="productForm.investment_account_requested_on"
              class="text-xs text-amber-800"
            >
              Request started · {{ productForm.investment_account_requested_on }}
            </p>
            <Button variant="solid" :loading="requestingAccount" @click="requestInvestmentAccount">
              Request activation
            </Button>
          </div>

          <div class="border-t border-gray-100 pt-4 space-y-3">
            <h4 class="text-sm font-medium text-gray-900">Defaults</h4>
            <FormControl
              v-model.number="productForm.default_forecast_horizon_days"
              type="number"
              label="Forecast horizon (days)"
            />
            <FormControl
              v-model.number="productForm.default_min_liquidity_buffer"
              type="number"
              label="Min liquidity buffer"
            />
            <FormControl
              v-model.number="productForm.default_restricted_cash"
              type="number"
              label="Restricted cash"
            />
          </div>

          <div class="border-t border-gray-100 pt-4 space-y-3">
            <h4 class="text-sm font-medium text-gray-900">Proposal illustration rates</h4>
            <p class="text-xs text-gray-500">
              Stated % p.a. for the Proposal comparison cards only — not forecasts or guarantees.
            </p>
            <FormControl
              v-model.number="productForm.illustrative_idle_yield_pct"
              type="number"
              label="Idle current account % p.a."
            />
            <FormControl
              v-model.number="productForm.illustrative_fd_yield_pct"
              type="number"
              label="Short-term bank FD % p.a."
            />
            <FormControl
              v-model.number="productForm.illustrative_liquid_yield_pct"
              type="number"
              label="Liquid mutual fund % p.a."
            />
          </div>
        </div>
      </div>
    </div>

    <Dialog v-model="showAddBank" :options="{ title: 'Add bank account' }">
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
          <Checkbox v-model="addBank.is_default" label="Set as default bank account" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="addingBank" @click="createBank">Create</Button>
        <Button variant="outline" @click="showAddBank = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call, createResource } from 'frappe-ui'
import { toast } from '@/utils/toast'
import PageHeader from '@/components/PageHeader.vue'
import BankAccountCards from '@/components/BankAccountCards.vue'
import { useCompanyStore } from '@/stores/company'
import { LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL } from '@/utils/investmentAccount'

const company = useCompanyStore()
const route = useRoute()
const saving = ref(false)
const requestingAccount = ref(false)
const showAddBank = ref(false)
const addingBank = ref(false)
const activeTab = ref('liquidity')

const tabs = [
  { id: 'integrations', label: 'Integrations' },
  { id: 'liquidity', label: 'Liquidity' },
  { id: 'banks', label: 'Banks' },
  { id: 'investment', label: 'Investment account' },
]

const accountSearch = ref('')
const accountRootFilter = ref('All')
const accountTypeFilter = ref('All')

const erpForm = reactive({
  enabled: false,
  /** CRM-style: only meaningful when ERPNext is installed on this site. */
  is_erpnext_in_the_current_site: false,
  /** Derived: Manual when !enabled; This Site / Other Site from the check above. */
  source: 'This Site',
  remote_site_url: '',
  remote_company: '',
  remote_api_key: '',
  remote_api_secret: '',
  has_remote_api_secret: false,
})
/** Last successfully saved / connected integration (drives account picker source). */
const savedErp = reactive({
  enabled: false,
  source: 'This Site',
  remote_site_url: '',
  remote_company: '',
  has_remote_api_secret: false,
})

function syncErpSourceFromChecks() {
  if (!erpForm.enabled) {
    erpForm.source = 'This Site' // unused while disabled; save maps enabled=0 → Manual
    return
  }
  if (company.erpnextInstalled && erpForm.is_erpnext_in_the_current_site) {
    erpForm.source = 'This Site'
  } else {
    erpForm.source = 'Other Site'
  }
}

watch(
  () => [erpForm.enabled, erpForm.is_erpnext_in_the_current_site, company.erpnextInstalled],
  () => syncErpSourceFromChecks(),
)

watch(
  () => erpForm.enabled,
  (on) => {
    if (!on) {
      erpForm.is_erpnext_in_the_current_site = false
      return
    }
    // Default to this site when ERPNext is available (CRM behaviour)
    if (company.erpnextInstalled && !erpForm.is_erpnext_in_the_current_site && erpForm.source !== 'Other Site') {
      erpForm.is_erpnext_in_the_current_site = true
    }
  },
)
const testingRemote = ref(false)
const remoteConnected = ref(false)
const remoteCompanies = ref([])
const localCompanies = ref([])

async function loadLocalCompanies() {
  if (!company.erpnextInstalled) {
    localCompanies.value = []
    return
  }
  try {
    const res = await call('lyqd.api.spa.list_local_erpnext_companies')
    localCompanies.value = res.companies || []
  } catch {
    localCompanies.value = []
  }
}

const policyForm = reactive({
  name: null,
  min_liquidity_buffer: 0,
  restricted_cash: 0,
  default_forecast_horizon_days: 7,
  notes: '',
  enable_purchase_invoice_recommendations: true,
  selectedBanks: [],
  selectedAccounts: [],
})
const accountRefs = reactive({})
const accountParents = reactive({})

function isAccountSelected(name) {
  return policyForm.selectedAccounts.includes(name)
}

function accountLabel(name) {
  const meta = accountList.value.find((a) => a.name === name)
  return meta?.account_name || name
}

function refsOffParentOptions(exclude) {
  return policyForm.selectedAccounts.filter((name) => {
    if (name === exclude) return false
    if (accountRefs[name] !== false) return false
    // One level: parent cannot itself be a child
    if (accountParents[name]) return false
    return true
  })
}

function setAccountSelected(name, on) {
  const selected = policyForm.selectedAccounts.includes(name)
  if (!!on === selected) return
  if (on) {
    policyForm.selectedAccounts.push(name)
    accountRefs[name] = true
    return
  }
  const idx = policyForm.selectedAccounts.indexOf(name)
  if (idx >= 0) policyForm.selectedAccounts.splice(idx, 1)
  delete accountRefs[name]
  delete accountParents[name]
  for (const k of Object.keys(accountParents)) {
    if (accountParents[k] === name) delete accountParents[k]
  }
}

function parentOptionsFor(name) {
  return [
    { label: 'None (top-level)', value: '' },
    ...refsOffParentOptions(name).map((p) => ({ label: accountLabel(p), value: p })),
  ]
}

function setAccountRefs(name, on) {
  accountRefs[name] = !!on
  if (on) {
    // Refs on → cannot be parent or child
    delete accountParents[name]
    for (const k of Object.keys(accountParents)) {
      if (accountParents[k] === name) delete accountParents[k]
    }
  }
}

function setAccountParent(name, parent) {
  const p = (parent || '').trim()
  if (!p) {
    delete accountParents[name]
    return
  }
  accountParents[name] = p
}

const productForm = reactive({
  investment_account_activated: false,
  investment_account_crm_lead: '',
  investment_account_requested_on: '',
  default_forecast_horizon_days: 7,
  default_min_liquidity_buffer: 0,
  default_restricted_cash: 0,
  illustrative_idle_yield_pct: 0,
  illustrative_fd_yield_pct: 3,
  illustrative_liquid_yield_pct: 5.5,
})

const addBank = reactive({
  account_name: '',
  bank: '',
  account_type: '',
  bank_account_no: '',
  opening_balance: 0,
  is_default: false,
})

function toggleBank(ba) {
  const name = ba.name
  const idx = policyForm.selectedBanks.indexOf(name)
  // First click when "all" (empty selection): pin to all except this one, or start with only this —
  // Banking-style: empty = all included; first explicit toggle starts a curated list.
  if (!policyForm.selectedBanks.length) {
    const all = bankAccountList.value.map((b) => b.name)
    policyForm.selectedBanks = all.filter((n) => n !== name)
    // If user clicked to "include" while all were implicitly included, treat as deselect.
    // If that emptied everything, select only others; if only one account existed, leave empty (=all).
    return
  }
  if (idx >= 0) {
    policyForm.selectedBanks.splice(idx, 1)
  } else {
    policyForm.selectedBanks.push(name)
  }
}

const bankOptions = createResource({
  url: 'lyqd.api.spa.get_company_bank_account_options',
  makeParams() {
    return { company: company.current }
  },
  auto: false,
})

const bankAccountList = computed(() => bankOptions.data?.accounts || [])

const banksFromRemote = computed(
  () =>
    (bankOptions.data?.source || savedErp.source) === 'Other Site' &&
    (savedErp.enabled || erpForm.enabled),
)

const bankSourceLabel = computed(() => {
  const src = bankOptions.data?.source || (banksFromRemote.value ? 'Other Site' : 'This Site')
  const books = bankOptions.data?.books_company
  if (src === 'Other Site') return `Other site${books ? ` (${books})` : ''}`
  return `This site${books ? ` (${books})` : ''}`
})

const bankEmptyHint = computed(() => bankOptions.data?.message || '')

const remoteBankDeskUrl = computed(() => {
  if (!banksFromRemote.value) return null
  const base = (erpForm.remote_site_url || savedErp.remote_site_url || '').replace(/\/$/, '')
  return base || null
})

const accountOptions = createResource({
  url: 'lyqd.api.spa.get_recommendation_account_options',
  makeParams() {
    return {
      company: company.current,
      root_type: accountRootFilter.value === 'All' ? null : accountRootFilter.value,
      account_type: accountTypeFilter.value === 'All' ? null : accountTypeFilter.value,
      search: accountSearch.value || null,
    }
  },
  auto: false,
})

const accountList = computed(() => accountOptions.data?.accounts || [])

const accountTypeChoices = computed(() => {
  const set = new Set(
    accountList.value.map((a) => a.account_type).filter((t) => t && t !== ''),
  )
  return [...set].sort()
})

const localCompanyOptions = computed(() =>
  localCompanies.value.map((c) => ({ label: c, value: c })),
)
const remoteCompanyOptions = computed(() =>
  remoteCompanies.value.map((c) => ({ label: c, value: c })),
)
const accountRootOptions = [
  { label: 'All roots', value: 'All' },
  { label: 'Liability', value: 'Liability' },
  { label: 'Asset (setoff)', value: 'Asset' },
]
const accountTypeFilterOptions = computed(() => [
  { label: 'All account types', value: 'All' },
  ...accountTypeChoices.value.map((t) => ({ label: t, value: t })),
])

function matchesAccountFilters(a) {
  const q = accountSearch.value.trim().toLowerCase()
  if (q) {
    const hay = `${a.name || ''} ${a.account_name || ''} ${a.account_type || ''}`.toLowerCase()
    if (!hay.includes(q)) return false
  }
  if (accountRootFilter.value !== 'All' && a.root_type !== accountRootFilter.value) return false
  if (accountTypeFilter.value !== 'All' && a.account_type !== accountTypeFilter.value) return false
  return true
}

/** Selected first (parents → children → flats), then unselected — both honor search/filters. */
const orderedAccounts = computed(() => {
  const byName = new Map(accountList.value.map((a) => [a.name, a]))
  // Ensure selected accounts appear even if not in current COA page
  for (const name of policyForm.selectedAccounts) {
    if (!byName.has(name)) {
      byName.set(name, {
        name,
        account_name: name,
        root_type: '',
        account_type: '',
      })
    }
  }

  const rowFor = (name) => byName.get(name) || { name, account_name: name }
  const selectedMatches = (name) => matchesAccountFilters(rowFor(name))

  const selectedSet = new Set(policyForm.selectedAccounts)
  const selectedParents = []
  const selectedChildrenByParent = new Map()
  const selectedFlats = []

  for (const name of policyForm.selectedAccounts) {
    const parent = accountParents[name]
    const refsOff = accountRefs[name] === false
    if (refsOff && parent && selectedSet.has(parent)) {
      if (!selectedChildrenByParent.has(parent)) selectedChildrenByParent.set(parent, [])
      selectedChildrenByParent.get(parent).push(name)
    } else if (refsOff && !parent) {
      selectedParents.push(name)
    } else {
      selectedFlats.push(name)
    }
  }

  // Parents that only appear as parent targets
  for (const parent of selectedChildrenByParent.keys()) {
    if (!selectedParents.includes(parent) && !selectedFlats.includes(parent)) {
      selectedParents.push(parent)
    }
  }

  const out = []
  const pushSelected = (name, child = false) => {
    out.push({ ...rowFor(name), _selected: true, _child: child })
  }

  for (const parent of selectedParents) {
    const matchingChildren = (selectedChildrenByParent.get(parent) || []).filter(selectedMatches)
    const parentOk = selectedMatches(parent)
    // Keep parent visible when a nested child matches the search
    if (!parentOk && !matchingChildren.length) continue
    pushSelected(parent, false)
    for (const child of matchingChildren) {
      pushSelected(child, true)
    }
  }
  for (const name of selectedFlats) {
    if (selectedChildrenByParent.has(name)) continue
    if (!selectedMatches(name)) continue
    pushSelected(name, false)
  }

  const selectedNames = new Set(out.map((r) => r.name))
  const unselected = accountList.value
    .filter((a) => !selectedNames.has(a.name) && matchesAccountFilters(a))
    .map((a) => ({ ...a, _selected: false, _child: false }))

  return [...out, ...unselected]
})

const accountSourceLabel = computed(() => {
  const src = accountOptions.data?.source || savedErp.source
  const books = accountOptions.data?.books_company || savedErp.remote_company
  if (src === 'Other Site') return `Other site${books ? ` (${books})` : ''}`
  return `This site${books ? ` (${books})` : ''}`
})

/** Only show the picker when the form source matches what the server will actually query. */
const accountsPickerReady = computed(() => {
  if (!erpForm.enabled) return false
  if (!(erpForm.remote_company || '').trim()) return false
  if (erpForm.source === 'This Site') return true
  // Other Site: require a successful Connect (or previously saved remote source)
  return (
    remoteConnected.value ||
    (savedErp.enabled &&
      savedErp.source === 'Other Site' &&
      !!savedErp.remote_site_url &&
      !!savedErp.has_remote_api_secret)
  )
})

function applySavedErp(data) {
  Object.assign(savedErp, {
    enabled: !!data.enabled,
    source: data.source || 'This Site',
    remote_site_url: data.remote_site_url || '',
    remote_company: data.remote_company || '',
    has_remote_api_secret: !!data.has_remote_api_secret,
  })
  if (savedErp.source === 'Other Site' && savedErp.has_remote_api_secret && savedErp.remote_site_url) {
    remoteConnected.value = true
  }
}

const policy = createResource({
  url: 'lyqd.api.spa.get_or_create_policy',
  makeParams() {
    return { company: company.current }
  },
  auto: false,
  onSuccess(data) {
    Object.assign(policyForm, {
      name: data.name,
      min_liquidity_buffer: data.min_liquidity_buffer,
      restricted_cash: data.restricted_cash,
      default_forecast_horizon_days: data.default_forecast_horizon_days,
      notes: data.notes || '',
      enable_purchase_invoice_recommendations: !!data.enable_purchase_invoice_recommendations,
      selectedBanks: (data.eligible_bank_accounts || []).map((r) => r.bank_account).filter(Boolean),
      selectedAccounts: (data.recommendation_accounts || []).map((r) => r.account).filter(Boolean),
    })
    Object.keys(accountRefs).forEach((k) => delete accountRefs[k])
    Object.keys(accountParents).forEach((k) => delete accountParents[k])
    for (const r of data.recommendation_accounts || []) {
      if (!r.account) continue
      accountRefs[r.account] = r.show_references !== 0
      if (r.parent_account) accountParents[r.account] = r.parent_account
    }
  },
})

async function loadSiteDefaults() {
  try {
    const data = await call('lyqd.api.spa.get_settings')
    Object.assign(productForm, {
      default_forecast_horizon_days: data.default_forecast_horizon_days,
      default_min_liquidity_buffer: data.default_min_liquidity_buffer,
      default_restricted_cash: data.default_restricted_cash,
      illustrative_idle_yield_pct: data.illustrative_idle_yield_pct ?? 0,
      illustrative_fd_yield_pct: data.illustrative_fd_yield_pct ?? 3,
      illustrative_liquid_yield_pct: data.illustrative_liquid_yield_pct ?? 5.5,
    })
  } catch (e) {
    /* keep defaults */
  }
}

async function loadCompanyErp(name) {
  if (!name) return
  try {
    const erp = await call('lyqd.api.spa.get_erpnext_settings', { company: name })
    const source = erp.source || (erp.enabled ? 'This Site' : 'This Site')
    Object.assign(erpForm, {
      enabled: !!erp.enabled,
      is_erpnext_in_the_current_site: !!erp.enabled && source === 'This Site',
      source,
      remote_site_url: erp.remote_site_url || '',
      remote_company: erp.remote_company || '',
      remote_api_key: erp.remote_api_key || '',
      remote_api_secret: '',
      has_remote_api_secret: !!erp.has_remote_api_secret,
    })
    syncErpSourceFromChecks()
    applySavedErp(erp)
    productForm.investment_account_activated = !!erp.investment_account_activated
    productForm.investment_account_requested_on = erp.investment_account_requested_on || ''
    company.applyCompanyOverlay?.(erp)
    company.erpnextIntegrationEnabled = !!erp.enabled
  } catch (e) {
    erpForm.enabled = false
    productForm.investment_account_activated = false
  }
}

onMounted(async () => {
  const tab = route.query.tab
  // Legacy deep-links
  if (tab === 'recommendations') {
    activeTab.value = 'integrations'
  } else if (tab === 'product') {
    activeTab.value = 'investment'
  } else if (typeof tab === 'string' && tabs.some((t) => t.id === tab)) {
    activeTab.value = tab
  }
  await Promise.all([loadSiteDefaults(), loadLocalCompanies()])
  if (company.current) await loadCompanyErp(company.current)
})

watch(
  () => company.current,
  (c) => {
    if (!c) return
    policy.reload()
    bankOptions.reload()
    loadCompanyErp(c)
    if (accountsPickerReady.value) accountOptions.reload()
  },
  { immediate: true },
)

watch(
  () => erpForm.source,
  (src) => {
    if (src === 'Other Site') {
      // Don't keep showing this-site accounts while drafting remote credentials
      if (!(savedErp.source === 'Other Site' && remoteConnected.value)) {
        remoteConnected.value = false
      }
    } else {
      remoteConnected.value = false
      remoteCompanies.value = []
      if (erpForm.enabled && company.current) accountOptions.reload()
    }
  },
)

watch(
  [accountRootFilter, accountTypeFilter, accountsPickerReady],
  () => {
    if (company.current && accountsPickerReady.value) accountOptions.reload()
  },
)

let searchTimer = null
watch(accountSearch, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (company.current && accountsPickerReady.value) accountOptions.reload()
  }, 300)
})

let skipRemoteCompanyWatch = false
watch(
  () => erpForm.remote_company,
  (c, prev) => {
    if (skipRemoteCompanyWatch || !c || c === prev) return
    if (!accountsPickerReady.value || erpForm.source !== 'Other Site') return
    saveErp()
      .then(() => accountOptions.reload())
      .catch(() => {})
  },
)

async function savePolicy() {
  const data = await call('lyqd.api.spa.save_policy', {
    doc: {
      name: policyForm.name,
      company: company.current,
      min_liquidity_buffer: policyForm.min_liquidity_buffer,
      restricted_cash: policyForm.restricted_cash,
      default_forecast_horizon_days: policyForm.default_forecast_horizon_days,
      notes: policyForm.notes,
      is_active: 1,
      enable_purchase_invoice_recommendations: policyForm.enable_purchase_invoice_recommendations
        ? 1
        : 0,
      eligible_bank_accounts: policyForm.selectedBanks.map((bank_account) => {
        const meta = bankAccountList.value.find((b) => b.name === bank_account)
        return {
          bank_account,
          account_name: meta?.account_name || bank_account,
          gl_account: meta?.account || '',
        }
      }),
      recommendation_accounts: policyForm.selectedAccounts.map((account) => {
        const meta = accountList.value.find((a) => a.name === account)
        const refs = accountRefs[account] === false ? 0 : 1
        return {
          account,
          account_name: meta?.account_name || account,
          show_references: refs,
          parent_account: refs === 0 ? accountParents[account] || '' : '',
        }
      }),
    },
  })
  policyForm.name = data.name
}

async function saveProduct() {
  // Site defaults only — investment activation is per LYQD Company (ops-owned).
  const saved = await call('lyqd.api.spa.save_settings', {
    doc: {
      default_forecast_horizon_days: productForm.default_forecast_horizon_days,
      default_min_liquidity_buffer: productForm.default_min_liquidity_buffer,
      default_restricted_cash: productForm.default_restricted_cash,
      illustrative_idle_yield_pct: productForm.illustrative_idle_yield_pct,
      illustrative_fd_yield_pct: productForm.illustrative_fd_yield_pct,
      illustrative_liquid_yield_pct: productForm.illustrative_liquid_yield_pct,
    },
  })
  // Keep SPA Proposal cards in sync without a full reload
  if (saved && company.settings) {
    Object.assign(company.settings, {
      illustrative_idle_yield_pct: saved.illustrative_idle_yield_pct,
      illustrative_fd_yield_pct: saved.illustrative_fd_yield_pct,
      illustrative_liquid_yield_pct: saved.illustrative_liquid_yield_pct,
    })
  }
  // Refresh company investment stamp (not written by save_settings)
  if (company.current) await loadCompanyErp(company.current)
}

async function requestInvestmentAccount() {
  window.open(LYQD_INVESTMENT_ACCOUNT_WHATSAPP_URL, '_blank', 'noopener,noreferrer')
  requestingAccount.value = true
  try {
    const res = await call('lyqd.api.spa.request_investment_account', {
      company: company.current,
    })
    productForm.investment_account_requested_on = res.requested_on || ''
    company.applyCompanyOverlay?.({
      ...(company.companySettings || {}),
      investment_account_requested_on: productForm.investment_account_requested_on,
      investment_account_activated: productForm.investment_account_activated ? 1 : 0,
    })
  } catch (e) {
    // WhatsApp already opened; stamp is best-effort only
    console.warn(e)
  } finally {
    requestingAccount.value = false
  }
}

async function saveErp() {
  if (
    erpForm.enabled &&
    (erpForm.source === 'This Site' || erpForm.source === 'Other Site') &&
    !(erpForm.remote_company || '').trim()
  ) {
    toast.error('Books company is required when ERPNext is enabled')
    throw new Error('Books company is required')
  }
  const payload = {
    company: company.current,
    enabled: erpForm.enabled ? 1 : 0,
    source: erpForm.source || 'This Site',
    remote_site_url: erpForm.remote_site_url,
    remote_company: erpForm.remote_company,
    remote_api_key: erpForm.remote_api_key,
  }
  if (erpForm.remote_api_secret) {
    payload.remote_api_secret = erpForm.remote_api_secret
  }
  const data = await call('lyqd.api.spa.save_erpnext_settings', { doc: payload })
  const source = data.source || 'This Site'
  Object.assign(erpForm, {
    enabled: !!data.enabled,
    is_erpnext_in_the_current_site: !!data.enabled && source === 'This Site',
    source,
    remote_site_url: data.remote_site_url || '',
    remote_company: data.remote_company || erpForm.remote_company || '',
    remote_api_key: data.remote_api_key || '',
    remote_api_secret: '',
    has_remote_api_secret: !!data.has_remote_api_secret,
  })
  syncErpSourceFromChecks()
  applySavedErp({ ...data, remote_company: erpForm.remote_company })
  company.applyCompanyOverlay?.(data)
  company.erpnextIntegrationEnabled = !!data.enabled
  return data
}

async function connectRemote() {
  testingRemote.value = true
  remoteConnected.value = false
  skipRemoteCompanyWatch = true
  try {
    const res = await call('lyqd.api.spa.probe_remote_erpnext_connection', {
      url: erpForm.remote_site_url,
      api_key: erpForm.remote_api_key,
      api_secret: erpForm.remote_api_secret || null,
      company: erpForm.remote_company || null,
      lyqd_company: company.current,
    })
    remoteCompanies.value = res.companies || []
    if (res.company) erpForm.remote_company = res.company
    if (!(erpForm.remote_company || '').trim()) {
      remoteConnected.value = false
      toast.error('Select the remote company before saving Other Site books')
      return
    }
    await saveErp()
    remoteConnected.value = true
    const mirror = res.bank_mirror
    const mirrorMsg = mirror
      ? ` · Mirrored ${mirror.created || 0} new / ${mirror.updated || 0} bank account(s) locally`
      : ''
    toast.success((res.message || 'Connected') + mirrorMsg)
    if (res.bank_mirror_error) toast.error(res.bank_mirror_error)
    accountOptions.reload()
    bankOptions.reload()
  } catch (e) {
    remoteConnected.value = false
    toast.error(e.messages?.[0] || e.message || 'Connection failed')
  } finally {
    skipRemoteCompanyWatch = false
    testingRemote.value = false
  }
}

async function saveActive() {
  saving.value = true
  try {
    if (activeTab.value === 'investment') {
      await saveProduct()
    } else if (activeTab.value === 'integrations') {
      if (erpForm.source === 'Other Site' && !remoteConnected.value && !savedErp.has_remote_api_secret) {
        await connectRemote()
      } else {
        await saveErp()
        if (accountsPickerReady.value) accountOptions.reload()
      }
      await savePolicy()
    } else {
      await savePolicy()
    }
    toast.success('Settings saved')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}

async function createBank() {
  addingBank.value = true
  try {
    const created = await call('lyqd.api.spa.create_surplus_bank_account', {
      company: company.current,
      account_name: addBank.account_name,
      bank: addBank.bank || null,
      account_type: addBank.account_type || null,
      bank_account_no: addBank.bank_account_no || null,
      opening_balance: addBank.opening_balance || 0,
      is_default: addBank.is_default ? 1 : 0,
      add_to_policy: 1,
    })
    await bankOptions.reload()
    await policy.reload()
    if (created.bank_account && !policyForm.selectedBanks.includes(created.bank_account)) {
      policyForm.selectedBanks.push(created.bank_account)
    }
    showAddBank.value = false
    addBank.account_name = ''
    addBank.bank = ''
    addBank.account_type = ''
    addBank.bank_account_no = ''
    addBank.opening_balance = 0
    addBank.is_default = false
    const parts = []
    if (created.created_gl_account) parts.push('Account')
    if (created.created_bank_account) parts.push('Bank Account')
    toast.success(parts.length ? `Created ${parts.join(' + ')}` : 'Bank account ready')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Create failed')
  } finally {
    addingBank.value = false
  }
}
</script>
