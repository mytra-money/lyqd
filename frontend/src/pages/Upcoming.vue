<template>
  <div>
    <PageHeader
      title="Commitments"
      subtitle="Plan on the left reserves free cash. From books on the right is optional until you add to plan."
    >
      <Button
        variant="outline"
        :loading="syncing"
        :disabled="!recsEnabled"
        @click="syncFromBooks"
      >
        Sync plan from books
      </Button>
      <Button variant="outline" :loading="planLoading || recsLoading" @click="reloadAll">
        Refresh
      </Button>
      <Button variant="solid" @click="openNew">Add payment</Button>
    </PageHeader>

    <div class="grid gap-4 lg:grid-cols-2 lg:items-start">
    <!-- ── On the plan ── -->
    <section class="min-w-0 rounded-lg border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-4 py-3">
        <div class="flex items-baseline justify-between gap-2">
          <h2 class="text-base font-semibold text-gray-900">On the plan</h2>
          <span class="text-xs tabular-nums text-gray-500">{{ activePlanCount }} active</span>
        </div>
        <p class="mt-0.5 text-xs text-gray-500">These amounts reduce free cash when Planned.</p>
        <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <div
            class="inline-flex w-fit max-w-full overflow-x-auto rounded-md border border-gray-200 p-0.5"
          >
            <button
              v-for="f in plannedViews"
              :key="f.id"
              type="button"
              class="whitespace-nowrap rounded px-2.5 py-1 text-xs font-medium transition-colors"
              :class="
                plannedView === f.id
                  ? 'bg-gray-900 text-white'
                  : 'text-gray-600 hover:text-gray-900'
              "
              @click="plannedView = f.id"
            >
              {{ f.label }}
              <span v-if="f.count != null" class="tabular-nums opacity-70">{{ f.count }}</span>
            </button>
          </div>
          <div class="flex min-w-0 flex-1 gap-2">
            <div class="relative min-w-0 flex-1">
              <FeatherIcon
                name="search"
                class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400"
              />
              <input
                v-model="plannedQuery"
                type="search"
                placeholder="Search plan"
                class="w-full rounded-md border border-gray-200 py-1.5 pl-8 pr-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-400 focus:outline-none"
              />
            </div>
            <select
              v-model="categoryFilter"
              class="max-w-[9rem] shrink-0 rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700"
            >
              <option value="all">Category</option>
              <option v-for="c in plannedCategories" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
        </div>
      </header>

      <div v-if="!filteredList.length" class="px-4 py-10 text-center text-sm text-gray-500">
        Nothing in this view.
        <button
          v-if="plannedFiltersActive"
          type="button"
          class="ml-1 text-gray-800 underline"
          @click="resetPlannedFilters"
        >
          Clear filters
        </button>
        <button v-else type="button" class="ml-1 text-gray-800 underline" @click="openNew">
          Add a payment
        </button>
      </div>

      <ul v-else class="max-h-[70vh] divide-y divide-gray-100 overflow-y-auto">
        <li v-for="row in nestedFilteredList" :key="row.name" class="px-0">
          <div class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50/80">
            <div class="flex h-6 w-6 shrink-0 items-center justify-center">
              <button
                v-if="row._childCount"
                type="button"
                class="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                :aria-expanded="isGroupExpanded(row.name)"
                :aria-label="isGroupExpanded(row.name) ? 'Collapse group' : 'Expand group'"
                @click="toggleGroup(row.name)"
              >
                <FeatherIcon
                  :name="isGroupExpanded(row.name) ? 'chevron-down' : 'chevron-right'"
                  class="h-3.5 w-3.5"
                />
              </button>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2 truncate text-sm font-medium text-gray-900">
                {{ row.title }}
                <span
                  v-if="row._childCount"
                  class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600"
                >
                  Group · {{ row._childCount + 1 }}
                </span>
              </div>
              <div class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
                <span
                  :class="
                    row.status === 'Planned' && isOverdue(row.due_date)
                      ? 'font-medium text-red-600'
                      : ''
                  "
                >
                  {{ dueLabel(row.due_date) }}
                </span>
                <span
                  v-if="row._childCount"
                  class="tabular-nums text-[11px] text-gray-400"
                  :class="row.cash_effect === 'Setoff' ? 'text-emerald-700/80' : ''"
                >
                  · GL {{ row.cash_effect === 'Setoff' ? '−' : '' }}{{ formatINR(row.amount) }}
                </span>
                <span>· {{ row.category }}</span>
                <span
                  v-if="row.cash_effect === 'Setoff'"
                  class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                >
                  Setoff
                </span>
                <span v-if="row.status !== 'Planned'" class="text-gray-400">· {{ row.status }}</span>
                <span
                  v-if="row.balance_as_of"
                  class="rounded bg-amber-50 px-1 font-medium text-amber-900"
                  :title="'GL frozen as of ' + formatDate(row.balance_as_of)"
                >
                  As of {{ formatDate(row.balance_as_of) }}
                </span>
              </div>
              <div v-if="row.source_doctype" class="mt-0.5 truncate text-xs text-gray-400">
                Ref {{ row.source_doctype }} {{ row.source_name }}
                <span v-if="row.source_account"> · {{ shortAccount(row.source_account) }}</span>
              </div>
            </div>
            <div class="shrink-0 text-right">
              <div
                v-if="row._childCount && row._groupNet != null"
                class="tabular-nums text-base font-semibold text-gray-900"
              >
                {{ formatINR(row._groupNet) }}
                <div class="text-[10px] font-medium uppercase tracking-wide text-gray-400">Net</div>
              </div>
              <div
                v-else
                class="tabular-nums text-sm font-semibold"
                :class="row.cash_effect === 'Setoff' ? 'text-emerald-800' : 'text-gray-900'"
              >
                {{ row.cash_effect === 'Setoff' ? '−' : '' }}{{ formatINR(row.amount) }}
              </div>
              <div class="mt-1 flex flex-wrap items-center justify-end gap-0.5">
                <button
                  v-if="groupCanRefresh(row)"
                  type="button"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
                  :disabled="refreshing === row.name"
                  :title="
                    row.balance_as_of
                      ? 'Refresh GL as of ' + formatDate(row.balance_as_of)
                      : 'Refresh from live books'
                  "
                  :aria-label="
                    row.balance_as_of
                      ? 'Refresh GL as of ' + formatDate(row.balance_as_of)
                      : 'Refresh from live books'
                  "
                  @click="refreshRow(row)"
                >
                  <FeatherIcon
                    name="refresh-cw"
                    class="h-3.5 w-3.5"
                    :class="refreshing === row.name ? 'animate-spin' : ''"
                  />
                </button>
                <Button
                  v-if="groupCanFreeze(row)"
                  size="sm"
                  variant="ghost"
                  class="!h-auto !px-1.5 !py-0.5 !text-xs !font-normal !text-amber-800 hover:!bg-amber-50"
                  :loading="freezing === row.name"
                  :title="row.balance_as_of ? 'Unfreeze · use live GL' : 'Freeze GL as of a date'"
                  @click="row.balance_as_of ? clearFreeze(row) : openFreeze(row)"
                >
                  {{
                    freezing === row.name
                      ? freezeAction === 'clear'
                        ? 'Unfreezing…'
                        : 'Freezing…'
                      : row.balance_as_of
                        ? 'Unfreeze'
                        : 'Freeze as of…'
                  }}
                </Button>
                <button
                  v-if="groupCanMarkPaid(row)"
                  type="button"
                  class="inline-flex h-7 items-center gap-1 rounded px-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
                  :disabled="marking === row.name"
                  title="Mark paid"
                  aria-label="Mark paid"
                  @click="markPaid(row)"
                >
                  <FeatherIcon name="check" class="h-3.5 w-3.5" />
                  <span>Paid</span>
                </button>
                <button
                  type="button"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-800"
                  title="Edit"
                  aria-label="Edit"
                  @click="edit(row)"
                >
                  <FeatherIcon name="edit-2" class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>

          <ul
            v-if="row._childCount && isGroupExpanded(row.name)"
            class="border-t border-gray-50 bg-gray-50/40"
          >
            <li
              v-for="child in row._children"
              :key="child.name"
              class="flex items-center gap-3 border-l-2 border-gray-200 py-2.5 pl-10 pr-4 hover:bg-gray-50/80"
            >
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-gray-800">
                  <span class="mr-1 text-gray-400">↳</span>
                  {{ child.title }}
                </div>
                <div class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
                  <span
                    :class="
                      child.status === 'Planned' && isOverdue(child.due_date)
                        ? 'font-medium text-red-600'
                        : ''
                    "
                  >
                    {{ dueLabel(child.due_date) }}
                  </span>
                  <span
                    class="tabular-nums text-[11px]"
                    :class="
                      child.cash_effect === 'Setoff' ? 'text-emerald-700/80' : 'text-gray-400'
                    "
                  >
                    · GL {{ child.cash_effect === 'Setoff' ? '−' : ''
                    }}{{ formatINR(child.amount) }}
                  </span>
                  <span>· {{ child.category }}</span>
                  <span
                    v-if="child.cash_effect === 'Setoff'"
                    class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                  >
                    Setoff
                  </span>
                  <span v-if="child.status !== 'Planned'" class="text-gray-400"
                    >· {{ child.status }}</span
                  >
                  <span
                    v-if="child.balance_as_of"
                    class="rounded bg-amber-50 px-1 font-medium text-amber-900"
                  >
                    As of {{ formatDate(child.balance_as_of) }}
                  </span>
                </div>
                <div v-if="child.source_doctype" class="mt-0.5 truncate text-xs text-gray-400">
                  Ref {{ child.source_doctype }} {{ child.source_name }}
                  <span v-if="child.source_account">
                    · {{ shortAccount(child.source_account) }}</span
                  >
                </div>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <!-- ── From books ── -->
    <section class="min-w-0 rounded-lg border border-gray-200 bg-white">
      <header class="border-b border-gray-100 px-4 py-3">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 class="text-base font-semibold text-gray-900">From books</h2>
            <p class="mt-0.5 text-xs text-gray-500">
              Optional intake — not reserved until you add to plan.
            </p>
          </div>
          <button
            v-if="recsEnabled"
            type="button"
            class="text-xs text-gray-500 hover:text-gray-800"
            @click="$router.push('/settings?tab=integrations')"
          >
            Configure accounts
          </button>
        </div>

        <template v-if="recsEnabled">
          <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <div
              class="inline-flex w-fit max-w-full overflow-x-auto rounded-md border border-gray-200 p-0.5"
            >
              <button
                v-for="f in suggestionViews"
                :key="f.id"
                type="button"
                class="whitespace-nowrap rounded px-2.5 py-1 text-xs font-medium transition-colors"
                :class="
                  suggestionView === f.id
                    ? 'bg-gray-900 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                "
                @click="suggestionView = f.id"
              >
                {{ f.label }}
                <span v-if="f.count != null" class="tabular-nums opacity-70">{{ f.count }}</span>
              </button>
            </div>
            <div class="flex min-w-0 flex-1 gap-2">
              <div class="relative min-w-0 flex-1">
                <FeatherIcon
                  name="search"
                  class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400"
                />
                <input
                  v-model="recQuery"
                  type="search"
                  placeholder="Search suggestions"
                  class="w-full rounded-md border border-gray-200 py-1.5 pl-8 pr-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-400 focus:outline-none"
                />
              </div>
              <select
                v-model="recAccount"
                class="max-w-[11rem] shrink-0 rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700"
                :title="recAccount === 'all' ? 'All accounts' : recAccount"
              >
                <option value="all">All accounts</option>
                <option v-for="a in suggestionAccounts" :key="a" :value="a">
                  {{ shortAccount(a) }}
                </option>
              </select>
            </div>
          </div>
        </template>
      </header>

      <div v-if="recsLoaded && !recsEnabled" class="px-4 py-10 text-center">
        <p class="text-sm text-gray-600">
          {{ recsMessage || 'Turn on ERPNext to see liability suggestions.' }}
        </p>
        <Button
          class="mt-3"
          size="sm"
          variant="outline"
          @click="$router.push('/settings?tab=integrations')"
        >
          Open integrations
        </Button>
      </div>

      <div
        v-else-if="!recsLoaded || (recsLoading && !allRecs.length)"
        class="px-4 py-10 text-center text-sm text-gray-500"
      >
        Loading suggestions…
      </div>

      <div
        v-else-if="recsLoaded && recsMessage && !allRecs.length"
        class="px-4 py-10 text-center text-sm text-gray-500"
      >
        {{ recsMessage }}
      </div>

      <div
        v-else-if="recsLoaded && !allRecs.length"
        class="px-4 py-10 text-center text-sm text-gray-500"
      >
        No open suggestions right now.
      </div>

      <div v-else-if="!filteredRecs.length" class="px-4 py-10 text-center text-sm text-gray-500">
        Nothing matches.
        <button type="button" class="ml-1 text-gray-800 underline" @click="resetRecFilters">
          Clear filters
        </button>
      </div>

      <ul v-else class="max-h-[70vh] divide-y divide-gray-100 overflow-y-auto">
        <li
          v-for="item in filteredRecs"
          :key="`${item.source_doctype}:${item.source_name}:${item.account}`"
          class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50/80"
        >
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium text-gray-900">{{ item.title }}</div>
            <div class="mt-0.5 truncate text-xs text-gray-500">
              <span :class="isOverdue(item.due_date) ? 'font-medium text-red-600' : ''">
                {{ dueLabel(item.due_date) }}
              </span>
              <span v-if="item.account"> · {{ shortAccount(item.account) }}</span>
              <span v-if="item.category"> · {{ item.category }}</span>
              <span v-if="item.cash_effect === 'Setoff'" class="font-medium text-emerald-800">
                · Setoff
              </span>
            </div>
          </div>
          <div class="shrink-0 text-right">
            <div
              class="tabular-nums text-sm font-semibold"
              :class="item.cash_effect === 'Setoff' ? 'text-emerald-800' : 'text-gray-900'"
            >
              {{ item.cash_effect === 'Setoff' ? '−' : '' }}{{ formatINR(item.amount) }}
            </div>
            <button
              type="button"
              class="mt-1 text-xs font-medium text-gray-900 hover:underline disabled:opacity-50"
              :disabled="accepting === item.source_name"
              @click="openAccept(item)"
            >
              Add to plan
            </button>
          </div>
        </li>
      </ul>
    </section>
    </div>

    <Dialog v-model="show" :options="{ title: form.name ? 'Edit payment' : 'Add payment' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl v-model="form.title" label="Title" />
          <FormControl
            v-model="form.category"
            type="select"
            label="Category"
            :options="categoryOptions"
          />
          <FormControl
            v-model="form.due_date"
            type="date"
            label="Due date"
            :disabled="!!form.parent_payment"
          />
          <p
            v-if="form.parent_payment"
            class="rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-950"
          >
            Due date follows the parent plan row. Change the parent’s due date to update this group.
          </p>
          <CurrencyControl v-model="form.amount" label="Amount" />
          <p
            v-if="form.cash_effect === 'Setoff'"
            class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
          >
            Setoff — reduces net commitments. Derived from the books account; not editable.
          </p>
          <FormControl
            v-model="form.status"
            type="select"
            label="Status"
            :options="statusOptions"
          />
          <FormControl v-model="form.notes" type="textarea" label="Notes" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
        <Button variant="outline" @click="show = false">Cancel</Button>
      </template>
    </Dialog>

    <Dialog v-model="showFreeze" :options="{ title: 'Freeze GL as of date' }">
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-gray-600">
            Use the books balance on this date for the plan (and nested children). Typical for
            GST/TDS: last day of the tax period — later GL movement won’t change the reserved
            amount until you unfreeze or pick another date.
          </p>
          <FormControl v-model="freezeForm.as_of" type="date" label="Balance as of" />
          <p v-if="freezeForm.title" class="text-xs text-gray-500">
            Applying to {{ freezeForm.title }}
            <span v-if="freezeForm.childCount">· {{ freezeForm.childCount + 1 }} rows</span>
          </p>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="!!freezing" @click="confirmFreeze">Freeze &amp; sync</Button>
        <Button variant="outline" @click="showFreeze = false">Cancel</Button>
      </template>
    </Dialog>

    <Dialog v-model="showAccept" :options="{ title: 'Add to plan' }">
      <template #body-content>
        <div class="space-y-3">
          <p
            v-if="acceptForm.cash_effect === 'Setoff'"
            class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
          >
            Setoff — reduces net commitments (customer receipt / Input GST). From the books
            account; not editable.
          </p>
          <FormControl v-model="acceptForm.title" label="Title" />
          <FormControl
            v-model="acceptForm.category"
            type="select"
            label="Category"
            :options="categoryOptions"
          />
          <FormControl v-model="acceptForm.due_date" type="date" label="Due date" />
          <CurrencyControl v-model="acceptForm.amount" label="Amount" />
          <p v-if="acceptForm.source_doctype" class="text-xs text-gray-500">
            Source {{ acceptForm.source_doctype }} {{ acceptForm.source_name }}
          </p>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="!!accepting" @click="confirmAccept">Add to plan</Button>
        <Button variant="outline" @click="showAccept = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, reactive, ref, watch } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import CurrencyControl from '@/components/CurrencyControl.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatDate, formatINR } from '@/utils/format'
import { groupMembers, nestPlanRows } from '@/utils/planNest'

defineOptions({ name: 'Upcoming' })

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const show = ref(false)
const showAccept = ref(false)
const saving = ref(false)
const accepting = ref(null)
const marking = ref(null)
const syncing = ref(false)
const refreshing = ref(null)
const freezing = ref(null)
/** 'clear' while unfreezing, 'set' while freezing from dialog */
const freezeAction = ref(null)
const showFreeze = ref(false)
const freezeForm = reactive({
  name: '',
  title: '',
  as_of: '',
  childCount: 0,
})
let recsDeferTimer = null

const plannedView = ref('active')
const categoryFilter = ref('all')
const plannedQuery = ref('')
/** Group parents expanded by name; default collapsed. */
const expandedGroups = ref({})

const suggestionView = ref('all')
const recAccount = ref('all')
const recQuery = ref('')

const categoryOptions = [
  'Salary',
  'Import-LC',
  'Vendor',
  'Customer',
  'Tax',
  'Loan',
  'Other',
].map((c) => ({ label: c, value: c }))
const statusOptions = ['Planned', 'Paid', 'Cancelled'].map((s) => ({ label: s, value: s }))

const empty = () => ({
  name: null,
  title: '',
  category: 'Other',
  due_date: '',
  amount: 0,
  cash_effect: 'Outflow',
  status: 'Planned',
  notes: '',
  parent_payment: '',
})
const form = reactive(empty())

const emptyAccept = () => ({
  source_doctype: '',
  source_name: '',
  account: '',
  title: '',
  category: 'Other',
  due_date: '',
  amount: 0,
  cash_effect: 'Outflow',
})
const acceptForm = reactive(emptyAccept())

const planLoading = computed(() => cache.planLoading)
const recsLoading = computed(() => cache.recsLoading)
const recsPayload = computed(() => cache.getRecommendations(company.current))
const recsLoaded = computed(() => recsPayload.value != null)
const recsEnabled = computed(() => !!recsPayload.value?.enabled)
const recsMessage = computed(() => recsPayload.value?.message || '')

const todayStr = () => new Date().toISOString().slice(0, 10)

async function loadPlan(force = false) {
  if (!company.current) return
  try {
    await call('lyqd.api.spa.relink_commitment_parents', { company: company.current })
  } catch {
    /* grouping still works once links exist */
  }
  await cache.ensurePlan({ company: company.current, force: true })
}

function scheduleRecs(force = false) {
  clearTimeout(recsDeferTimer)
  // Let the plan column paint first; remote / books suggestions are secondary.
  recsDeferTimer = setTimeout(() => {
    if (!company.current) return
    cache.ensureRecommendations({ company: company.current, force }).catch(() => {})
  }, force ? 0 : 50)
}

async function reloadAll() {
  await loadPlan(true)
  scheduleRecs(true)
}

function daysUntil(due) {
  if (!due) return null
  const a = new Date(todayStr())
  const b = new Date(due)
  return Math.round((b - a) / 86400000)
}

function isOverdue(due) {
  const d = daysUntil(due)
  return d !== null && d < 0
}

function dueLabel(due) {
  if (!due) return 'No due date'
  const d = daysUntil(due)
  if (d === null) return formatDate(due)
  if (d < 0) return `Overdue · ${formatDate(due)}`
  if (d === 0) return 'Due today'
  if (d === 1) return 'Due tomorrow'
  if (d <= 7) return `Due in ${d}d · ${formatDate(due)}`
  return formatDate(due)
}

function shortAccount(account) {
  // ERPNext leaf accounts are "{Account Name} - {Company Abbr}" — show the name, not the abbr.
  if (!account) return ''
  const parts = String(account).split(' - ')
  if (parts.length < 2) return String(account)
  return parts.slice(0, -1).join(' - ')
}

const allRows = computed(() => cache.getPlan(company.current) || [])
const allRecs = computed(() => recsPayload.value?.items || [])

const activePlanCount = computed(
  () => allRows.value.filter((r) => r.status === 'Planned').length,
)

const plannedViews = computed(() => {
  const rows = allRows.value
  const active = rows.filter((r) => r.status === 'Planned')
  return [
    { id: 'active', label: 'Active', count: active.length },
    {
      id: 'overdue',
      label: 'Overdue',
      count: active.filter((r) => isOverdue(r.due_date)).length,
    },
    { id: 'paid', label: 'Paid', count: rows.filter((r) => r.status === 'Paid').length },
  ]
})

const suggestionViews = computed(() => {
  const items = allRecs.value
  return [
    { id: 'all', label: 'All', count: items.length },
    {
      id: 'overdue',
      label: 'Overdue',
      count: items.filter((i) => isOverdue(i.due_date)).length,
    },
    {
      id: 'soon',
      label: '7 days',
      count: items.filter((i) => {
        const d = daysUntil(i.due_date)
        return d !== null && d >= 0 && d <= 7
      }).length,
    },
  ]
})

const plannedCategories = computed(() => {
  const set = new Set(allRows.value.map((r) => r.category).filter(Boolean))
  return [...set].sort()
})

const suggestionAccounts = computed(() => {
  // Prefer accounts that currently have open suggestions; fall back to configured list.
  const fromItems = allRecs.value.map((i) => i.account).filter(Boolean)
  const accounts = fromItems.length
    ? [...new Set(fromItems)]
    : [...new Set((recsPayload.value?.account_filter || []).filter(Boolean))]
  return accounts.sort((a, b) =>
    shortAccount(a).localeCompare(shortAccount(b), undefined, { sensitivity: 'base' }),
  )
})

const plannedFiltersActive = computed(
  () =>
    plannedView.value !== 'active' ||
    categoryFilter.value !== 'all' ||
    !!plannedQuery.value.trim(),
)

const filteredList = computed(() => {
  const q = plannedQuery.value.trim().toLowerCase()
  return allRows.value.filter((r) => {
    if (plannedView.value === 'active' && r.status !== 'Planned') return false
    if (plannedView.value === 'overdue') {
      if (r.status !== 'Planned' || !isOverdue(r.due_date)) return false
    }
    if (plannedView.value === 'paid' && r.status !== 'Paid') return false
    if (categoryFilter.value !== 'all' && r.category !== categoryFilter.value) return false
    if (q) {
      const hay = `${r.title || ''} ${r.category || ''} ${r.source_name || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const nestedFilteredList = computed(() => nestPlanRows(filteredList.value))

const filteredRecs = computed(() => {
  const q = recQuery.value.trim().toLowerCase()
  return allRecs.value.filter((item) => {
    if (suggestionView.value === 'overdue' && !isOverdue(item.due_date)) return false
    if (suggestionView.value === 'soon') {
      const d = daysUntil(item.due_date)
      if (d === null || d < 0 || d > 7) return false
    }
    if (recAccount.value !== 'all' && item.account !== recAccount.value) return false
    if (q) {
      const hay = `${item.title || ''} ${item.account || ''} ${item.source_name || ''} ${item.category || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

watch(
  () => company.current,
  (c) => {
    if (!c) return
    loadPlan(false)
    scheduleRecs(false)
    resetPlannedFilters()
    resetRecFilters()
  },
  { immediate: true },
)

onActivated(() => {
  if (!company.current) return
  loadPlan(false)
  scheduleRecs(false)
})

function resetPlannedFilters() {
  plannedView.value = 'active'
  categoryFilter.value = 'all'
  plannedQuery.value = ''
}

function resetRecFilters() {
  suggestionView.value = 'all'
  recAccount.value = 'all'
  recQuery.value = ''
}

function openNew() {
  Object.assign(form, empty())
  show.value = true
}

function edit(row) {
  Object.assign(form, {
    name: row.name,
    title: row.title,
    category: row.category,
    due_date: row.due_date,
    amount: row.amount,
    cash_effect: row.cash_effect || 'Outflow',
    status: row.status,
    notes: row.notes || '',
    parent_payment: row.parent_payment || '',
  })
  show.value = true
}

function syncToast(summary) {
  const parts = []
  if (summary.marked_paid) parts.push(`${summary.marked_paid} voucher(s) paid`)
  if (summary.amount_updated) parts.push(`${summary.amount_updated} amount(s) updated`)
  if (summary.cancelled) parts.push(`${summary.cancelled} cancelled`)
  if (summary.reopened) parts.push(`${summary.reopened} reopened`)
  return parts.length ? parts.join(' · ') : 'Plan already in sync with books'
}

async function syncFromBooks() {
  syncing.value = true
  try {
    const res = await call('lyqd.api.spa.sync_upcoming_from_books', {
      company: company.current,
    })
    if (!res.enabled) {
      toast.error(res.message || 'ERPNext integration is off')
      return
    }
    toast.success(syncToast(res.summary || {}))
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Sync failed')
  } finally {
    syncing.value = false
  }
}

function isGroupExpanded(name) {
  return !!expandedGroups.value[name]
}

function toggleGroup(name) {
  expandedGroups.value = {
    ...expandedGroups.value,
    [name]: !expandedGroups.value[name],
  }
}

function groupCanRefresh(row) {
  return groupMembers(row).some((m) => m.source_doctype && m.source_name)
}

function groupCanFreeze(row) {
  // Account-grain only (GST/TDS GL). Parent owns freeze for the whole group.
  return groupMembers(row).some((m) => m.source_doctype === 'Account' && m.source_name)
}

function groupCanMarkPaid(row) {
  return groupMembers(row).some((m) => m.status === 'Planned')
}

async function openFreeze(row) {
  freezeForm.name = row.name
  freezeForm.title = row.title || row.name
  freezeForm.childCount = row._childCount || 0
  freezeForm.as_of = row.balance_as_of || ''
  showFreeze.value = true
  try {
    const res = await call('lyqd.api.spa.default_balance_as_of', {
      due_date: row.due_date || null,
    })
    if (!freezeForm.as_of && res?.balance_as_of) {
      freezeForm.as_of = res.balance_as_of
    }
  } catch {
    /* keep empty; user picks */
  }
}

async function confirmFreeze() {
  if (!freezeForm.as_of) {
    toast.error('Pick a balance as-of date')
    return
  }
  freezeAction.value = 'set'
  freezing.value = freezeForm.name
  await nextTick()
  try {
    const res = await call('lyqd.api.spa.freeze_upcoming_balance', {
      name: freezeForm.name,
      as_of: freezeForm.as_of,
    })
    const n = (res.updated || []).length
    toast.success(
      n > 1
        ? `Frozen ${n} rows as of ${formatDate(freezeForm.as_of)}`
        : `Frozen as of ${formatDate(freezeForm.as_of)}`,
    )
    showFreeze.value = false
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not freeze balance')
  } finally {
    freezing.value = null
    freezeAction.value = null
  }
}

async function clearFreeze(row) {
  freezeAction.value = 'clear'
  freezing.value = row.name
  await nextTick()
  try {
    const res = await call('lyqd.api.spa.freeze_upcoming_balance', {
      name: row.name,
      clear: 1,
    })
    const n = (res?.updated || []).length
    toast.success(
      n > 1
        ? `Unfrozen ${n} rows · live GL again`
        : 'Using live GL balance again',
    )
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not unfreeze')
  } finally {
    freezing.value = null
    freezeAction.value = null
  }
}

async function refreshRow(row) {
  refreshing.value = row.name
  try {
    const targets = groupMembers(row).filter((m) => m.source_doctype && m.source_name)
    const labels = {
      marked_paid: 'Marked paid from books (voucher cleared)',
      amount_updated: 'Amount updated from books',
      cancelled: 'Cancelled — missing/cancelled in books',
      reopened: 'Back on plan from books',
      unchanged: 'Already up to date',
      skipped: 'Skipped',
    }
    let lastAction = 'unchanged'
    let asOfUsed = null
    for (const m of targets) {
      const res = await call('lyqd.api.spa.refresh_upcoming_from_books', { name: m.name })
      lastAction = res.action || lastAction
      asOfUsed = res.as_of_used || asOfUsed
    }
    const n = targets.length
    const asOfNote =
      row.balance_as_of || asOfUsed
        ? ` (as of ${formatDate(row.balance_as_of || asOfUsed)})`
        : ''
    toast.success(
      n > 1
        ? `Refreshed ${n} linked rows from books${asOfNote}`
        : `${labels[lastAction] || `Synced (${lastAction})`}${asOfNote}`,
    )
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Refresh failed')
  } finally {
    refreshing.value = null
  }
}

async function markPaid(row) {
  marking.value = row.name
  try {
    const targets = groupMembers(row).filter((m) => m.status === 'Planned')
    for (const m of targets) {
      await call('lyqd.api.spa.save_upcoming_payment', {
        doc: {
          name: m.name,
          company: company.current,
          title: m.title,
          category: m.category,
          due_date: m.due_date,
          amount: m.amount,
          status: 'Paid',
          notes: m.notes,
        },
      })
    }
    toast.success(targets.length > 1 ? `Marked ${targets.length} paid` : 'Marked paid')
    cache.invalidatePlanRelated(company.current)
    await loadPlan(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not mark paid')
  } finally {
    marking.value = null
  }
}

function openAccept(item) {
  Object.assign(acceptForm, {
    source_doctype: item.source_doctype,
    source_name: item.source_name,
    account: item.account || '',
    title: item.title || '',
    category: item.category || 'Other',
    due_date: item.due_date || todayStr(),
    amount: item.amount || 0,
    cash_effect: item.cash_effect || 'Outflow',
  })
  showAccept.value = true
}

async function confirmAccept() {
  if (!acceptForm.due_date) {
    toast.error('Due date is required')
    return
  }
  accepting.value = acceptForm.source_name
  try {
    await call('lyqd.api.spa.accept_upcoming_recommendation', {
      company: company.current,
      source_doctype: acceptForm.source_doctype,
      source_name: acceptForm.source_name,
      amount: acceptForm.amount,
      title: acceptForm.title,
      category: acceptForm.category,
      due_date: acceptForm.due_date,
      account: acceptForm.account || null,
      cash_effect: acceptForm.cash_effect || 'Outflow',
    })
    toast.success('Added to plan')
    showAccept.value = false
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Accept failed')
  } finally {
    accepting.value = null
  }
}

async function save() {
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
        status: form.status || 'Planned',
        notes: form.notes,
      },
    })
    toast.success('Saved')
    show.value = false
    cache.invalidatePlanRelated(company.current)
    await loadPlan(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>
