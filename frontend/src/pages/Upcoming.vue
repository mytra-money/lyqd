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
            <FormControl
              v-model="plannedQuery"
              class="min-w-0 flex-1"
              placeholder="Search plan"
            />
            <FormControl
              v-model="categoryFilter"
              class="max-w-[9rem] shrink-0"
              type="select"
              :options="plannedCategoryOptions"
            />
          </div>
        </div>
      </header>

      <EmptyState
        v-if="!filteredList.length && plannedFiltersActive"
        variant="filter"
        title="Nothing matches"
        description="Try another status, category, or clear the search."
      >
        <template #actions>
          <Button size="sm" variant="outline" @click="resetPlannedFilters">Clear filters</Button>
        </template>
      </EmptyState>
      <EmptyState
        v-else-if="!filteredList.length"
        variant="plan"
        title="No payments on the plan yet"
        description="Add a planned payment to reserve free cash and track what is due."
      >
        <template #actions>
          <Button size="sm" variant="solid" @click="openNew">Add payment</Button>
        </template>
      </EmptyState>

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
                  v-if="row.is_recurring"
                  class="rounded bg-blue-50 px-1 font-medium text-blue-800"
                >
                  {{ row.frequency || 'Monthly' }}
                </span>
                <span
                  v-if="row._childCount"
                  class="tabular-nums text-[11px] text-gray-400"
                  :class="
                    row.cash_effect === 'Setoff' || row.cash_effect === 'Inflow'
                      ? 'text-emerald-700/80'
                      : ''
                  "
                >
                  · GL
                  {{
                    row.cash_effect === 'Setoff' || row.cash_effect === 'Inflow' ? '−' : ''
                  }}{{ formatINR(row.amount) }}
                </span>
                <span
                  v-else-if="row.is_recurring && row.occurrence_count > 1"
                  class="tabular-nums text-[11px] text-gray-400"
                >
                  ·
                  {{ formatINR(row.period_amount ?? row.amount / row.occurrence_count) }} ×
                  {{ row.occurrence_count }}
                </span>
                <span
                  v-else-if="row.is_recurring && !(row.occurrence_count > 0)"
                  class="rounded bg-gray-100 px-1 font-medium text-gray-600"
                  title="Next due is outside the forecast horizon — nothing reserved yet"
                >
                  Outside horizon
                </span>
                <span>· {{ row.category }}</span>
                <span
                  v-if="row.cash_effect === 'Setoff'"
                  class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                >
                  Setoff
                </span>
                <span
                  v-else-if="row.cash_effect === 'Inflow'"
                  class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                >
                  Inflow
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
                :class="
                  row.cash_effect === 'Setoff' || row.cash_effect === 'Inflow'
                    ? 'text-emerald-800'
                    : 'text-gray-900'
                "
              >
                {{
                  row.cash_effect === 'Setoff' || row.cash_effect === 'Inflow' ? '−' : ''
                }}{{ formatINR(displayPlanAmount(row)) }}
                <div
                  v-if="row.is_recurring && !(row.occurrence_count > 0)"
                  class="text-[10px] font-medium uppercase tracking-wide text-gray-400"
                >
                  / {{ frequencyUnit(row.frequency) }}
                </div>
                <div
                  v-else-if="row.is_recurring && row.occurrence_count > 1"
                  class="text-[10px] font-medium uppercase tracking-wide text-gray-400"
                >
                  in horizon
                </div>
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
                  :title="
                    row.is_recurring
                      ? `Record ${(row.frequency || 'Monthly').toLowerCase()} · advance next due`
                      : 'Mark paid'
                  "
                  :aria-label="
                    row.is_recurring
                      ? `Record ${(row.frequency || 'Monthly').toLowerCase()}`
                      : 'Mark paid'
                  "
                  @click="markPaid(row)"
                >
                  <FeatherIcon name="check" class="h-3.5 w-3.5" />
                  <span>{{ row.is_recurring ? row.frequency || 'Monthly' : 'Paid' }}</span>
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
                      child.cash_effect === 'Setoff' || child.cash_effect === 'Inflow'
                        ? 'text-emerald-700/80'
                        : 'text-gray-400'
                    "
                  >
                    · GL
                    {{
                      child.cash_effect === 'Setoff' || child.cash_effect === 'Inflow' ? '−' : ''
                    }}{{ formatINR(child.amount) }}
                  </span>
                  <span>· {{ child.category }}</span>
                  <span
                    v-if="child.cash_effect === 'Setoff'"
                    class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                  >
                    Setoff
                  </span>
                  <span
                    v-else-if="child.cash_effect === 'Inflow'"
                    class="rounded bg-emerald-50 px-1 font-medium text-emerald-800"
                  >
                    Inflow
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
              <FormControl
                v-model="recQuery"
                class="min-w-0 flex-1"
                placeholder="Search suggestions"
              />
              <FormControl
                v-model="recAccount"
                class="max-w-[11rem] shrink-0"
                type="select"
                :title="recAccount === 'all' ? 'All accounts' : recAccount"
                :options="suggestionAccountOptions"
              />
            </div>
          </div>
        </template>
      </header>

      <EmptyState
        v-if="recsLoaded && !recsEnabled"
        variant="books"
        title="Books not connected"
        :description="recsMessage || 'Turn on ERPNext to see liability suggestions from your books.'"
      >
        <template #actions>
          <Button size="sm" variant="outline" @click="$router.push('/settings?tab=integrations')">
            Open integrations
          </Button>
        </template>
      </EmptyState>

      <div
        v-else-if="recsLoading && !recsLoaded"
        class="px-4 py-10 text-center text-sm text-gray-500"
      >
        Loading suggestions…
      </div>

      <EmptyState
        v-else-if="recsError"
        variant="books"
        title="Could not load suggestions"
        :description="recsError"
      >
        <template #actions>
          <Button size="sm" variant="solid" :loading="recsLoading" @click="scheduleRecs(true)">
            Retry
          </Button>
        </template>
      </EmptyState>

      <EmptyState
        v-else-if="recsLoaded && recsMessage && !allRecs.length"
        variant="books"
        title="Nothing from books"
        :description="recsMessage"
      />

      <EmptyState
        v-else-if="recsLoaded && !allRecs.length"
        variant="books"
        title="No open suggestions"
        description="When liabilities appear in your books, they will show up here to add to the plan."
      />

      <EmptyState
        v-else-if="!filteredRecs.length"
        variant="filter"
        title="Nothing matches"
        description="Try another account filter or clear the search."
      >
        <template #actions>
          <Button size="sm" variant="outline" @click="resetRecFilters">Clear filters</Button>
        </template>
      </EmptyState>

      <ul v-else class="max-h-[70vh] divide-y divide-gray-100 overflow-y-auto">
        <li v-for="item in nestedFilteredRecs" :key="recommendationKey(item)" class="px-0">
          <div class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50/80">
            <div class="flex h-6 w-6 shrink-0 items-center justify-center">
              <button
                v-if="item._childCount"
                type="button"
                class="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                :aria-expanded="isRecGroupExpanded(item)"
                :aria-label="isRecGroupExpanded(item) ? 'Collapse group' : 'Expand group'"
                @click="toggleRecGroup(item)"
              >
                <FeatherIcon
                  :name="isRecGroupExpanded(item) ? 'chevron-down' : 'chevron-right'"
                  class="h-3.5 w-3.5"
                />
              </button>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2 truncate text-sm font-medium text-gray-900">
                {{ item.title }}
                <span
                  v-if="item._childCount"
                  class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600"
                >
                  Group · {{ item._childCount + 1 }}
                </span>
              </div>
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
                v-if="item._childCount && item._groupNet != null"
                class="tabular-nums text-sm font-semibold text-gray-900"
              >
                {{ formatINR(item._groupNet) }}
                <div class="text-[10px] font-medium uppercase tracking-wide text-gray-400">Net</div>
              </div>
              <div
                v-else
                class="tabular-nums text-sm font-semibold"
                :class="item.cash_effect === 'Setoff' ? 'text-emerald-800' : 'text-gray-900'"
              >
                {{ item.cash_effect === 'Setoff' ? '−' : '' }}{{ formatINR(item.amount) }}
              </div>
              <button
                type="button"
                class="mt-1 text-xs font-medium text-gray-900 hover:underline disabled:opacity-50"
                :disabled="accepting === recommendationKey(item)"
                @click="openAccept(item)"
              >
                Add to plan
              </button>
            </div>
          </div>

          <ul
            v-if="item._childCount && isRecGroupExpanded(item)"
            class="border-t border-gray-50 bg-gray-50/40"
          >
            <li
              v-for="child in item._children"
              :key="recommendationKey(child)"
              class="flex items-center gap-3 border-l-2 border-gray-200 py-2.5 pl-10 pr-4 hover:bg-gray-50/80"
            >
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-gray-800">
                  <span class="mr-1 text-gray-400">↳</span>
                  {{ child.title }}
                </div>
                <div class="mt-0.5 truncate text-xs text-gray-500">
                  <span v-if="child.account">{{ shortAccount(child.account) }}</span>
                  <span v-if="child.category"> · {{ child.category }}</span>
                  <span
                    v-if="child.cash_effect === 'Setoff'"
                    class="font-medium text-emerald-800"
                  >
                    · Setoff
                  </span>
                </div>
              </div>
              <div class="shrink-0 text-right">
                <div
                  class="tabular-nums text-sm font-semibold"
                  :class="child.cash_effect === 'Setoff' ? 'text-emerald-800' : 'text-gray-900'"
                >
                  {{ child.cash_effect === 'Setoff' ? '−' : '' }}{{ formatINR(child.amount) }}
                </div>
                <button
                  type="button"
                  class="mt-1 text-xs font-medium text-gray-900 hover:underline disabled:opacity-50"
                  :disabled="accepting === recommendationKey(child)"
                  @click="openAccept(child)"
                >
                  Add to plan
                </button>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </section>
    </div>

    <Dialog v-model="show" :options="{ title: form.name ? 'Edit payment' : 'Add payment' }">
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
            :disabled="!!form.parent_payment || !!form.is_recurring || !!form.source_doctype"
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
            Due date follows the parent plan row. Change the parent’s due date to update this group.
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
          <p
            v-if="form.cash_effect === 'Setoff'"
            class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
          >
            Setoff — reduces net commitments. Derived from the books account; not editable.
          </p>
          <p
            v-else-if="form.cash_effect === 'Inflow'"
            class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
          >
            Inflow — expected receipt (FD maturity, loan proceeds) increases free cash.
          </p>
          <FormControl
            v-if="!form.is_recurring"
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

    <Dialog
      v-model="showStaleFreeze"
      :options="{ title: 'Live GL is lower than freeze date' }"
    >
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-gray-600">
            Today’s books balance is lower than the frozen as-of balance (likely paid or
            cleared). Unfreeze to pull live GL onto the plan. If live were higher, the freeze
            date would just be refreshed with no prompt.
          </p>
          <ul class="divide-y divide-gray-100 rounded-md border border-gray-200">
            <li
              v-for="item in staleFreezeRows"
              :key="item.name"
              class="px-3 py-2.5 text-sm"
            >
              <div class="font-medium text-gray-900">{{ item.title || item.name }}</div>
              <div class="mt-0.5 text-xs text-gray-500">
                <template v-if="item.memberCount > 1">
                  Frozen net {{ formatINR(item.freezeNet) }}
                  <span v-if="item.balance_as_of">
                    as of {{ formatDate(item.balance_as_of) }}</span
                  >
                  · Live net {{ formatINR(item.liveNet) }}
                  · {{ item.memberCount }} accounts
                </template>
                <template v-else>
                  Frozen {{ formatINR(item.amount) }}
                  <span v-if="item.balance_as_of">
                    as of {{ formatDate(item.balance_as_of) }}</span
                  >
                  · Live {{ formatINR(item.live_today_amount) }}
                </template>
              </div>
            </li>
          </ul>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="unfreezingStale" @click="confirmUnfreezeStale">
          Unfreeze &amp; update
        </Button>
        <Button variant="outline" :disabled="unfreezingStale" @click="dismissStaleFreeze">
          Keep freeze
        </Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, reactive, ref, watch } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import CurrencyControl from '@/components/CurrencyControl.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatDate, formatINR } from '@/utils/format'
import {
  groupMembers,
  nestPlanRows,
  nestRecommendationRows,
  recommendationKey,
  signedCashAmount,
} from '@/utils/planNest'

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
const showStaleFreeze = ref(false)
const staleFreezeRows = ref([])
const unfreezingStale = ref(false)
let recsDeferTimer = null

const plannedView = ref('active')
const categoryFilter = ref('all')
const plannedQuery = ref('')
/** Group parents expanded by name; default collapsed. */
const expandedGroups = ref({})
/** From-books nested groups expanded by recommendation key. */
const expandedRecGroups = ref({})

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

const empty = () => ({
  name: null,
  title: 'Other',
  category: 'Other',
  due_date: '',
  amount: 0,
  cash_effect: 'Outflow',
  status: 'Planned',
  notes: '',
  parent_payment: '',
  source_doctype: '',
  is_recurring: false,
  frequency: 'Monthly',
  recurrence_end: '',
})
const form = reactive(empty())

function onCategoryChange(value) {
  const next = value || form.category
  // Keep title in sync until the user types a custom name
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

const emptyAccept = () => ({
  source_doctype: '',
  source_name: '',
  source_row: '',
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
const recsError = computed(() => cache.getRecommendationsError(company.current))

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

/** Recurring outside the forecast horizon expands to ₹0 reserved — still show per period. */
function displayPlanAmount(row) {
  if (row?.is_recurring && !(row.occurrence_count > 0) && row.period_amount != null) {
    return row.period_amount
  }
  return row?.amount
}

function frequencyUnit(frequency) {
  const f = (frequency || 'Monthly').toLowerCase()
  if (f === 'weekly') return 'week'
  if (f === 'quarterly') return 'quarter'
  return 'month'
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

const plannedCategoryOptions = computed(() => [
  { label: 'Category', value: 'all' },
  ...plannedCategories.value.map((c) => ({ label: c, value: c })),
])

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

const suggestionAccountOptions = computed(() => [
  { label: 'All accounts', value: 'all' },
  ...suggestionAccounts.value.map((a) => ({ label: shortAccount(a), value: a })),
])

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

const nestedFilteredRecs = computed(() => nestRecommendationRows(filteredRecs.value))

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
    amount: row.period_amount != null ? row.period_amount : row.amount,
    cash_effect: row.cash_effect || 'Outflow',
    status: row.status,
    notes: row.notes || '',
    parent_payment: row.parent_payment || '',
    source_doctype: row.source_doctype || '',
    is_recurring: !!row.is_recurring,
    frequency: row.frequency || 'Monthly',
    recurrence_end: row.recurrence_end || '',
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

/**
 * Freeze-date amounts already refreshed. Prompt only when today's *net* reserve
 * is lower than the freeze-date net (nested groups use signed Outflow / Setoff).
 */
function promptsFromFreezeCompare(rows) {
  const compares = (rows || []).filter(
    (r) => r?.name && r.balance_as_of && r.live_today_amount != null,
  )
  if (!compares.length) return []

  const plan = cache.getPlan(company.current) || []
  const byName = Object.fromEntries(plan.map((p) => [p.name, p]))

  const enriched = compares.map((r) => {
    const planRow = byName[r.name] || {}
    return {
      ...r,
      cash_effect: r.cash_effect || planRow.cash_effect || 'Outflow',
      parent_payment: r.parent_payment || planRow.parent_payment || '',
      title: r.title || planRow.title || r.name,
    }
  })

  const groups = new Map()
  for (const r of enriched) {
    const root = r.parent_payment || r.name
    if (!groups.has(root)) groups.set(root, [])
    groups.get(root).push(r)
  }

  const prompts = []
  for (const [root, members] of groups) {
    let freezeNet = 0
    let liveNet = 0
    for (const m of members) {
      freezeNet += signedCashAmount(m.amount, m.cash_effect)
      liveNet += signedCashAmount(m.live_today_amount, m.cash_effect)
    }
    // Live net reserve lower than freeze-date net → payment / clearance
    if (!(liveNet < freezeNet - 0.01)) continue

    const rootMeta = byName[root] || members.find((m) => m.name === root) || members[0]
    const asOf = members.find((m) => m.balance_as_of)?.balance_as_of
    prompts.push({
      name: root,
      title: rootMeta.title || root,
      balance_as_of: asOf,
      amount: members.length === 1 ? members[0].amount : freezeNet,
      live_today_amount: members.length === 1 ? members[0].live_today_amount : liveNet,
      freezeNet,
      liveNet,
      memberCount: members.length,
    })
  }
  return prompts
}

function promptStaleFreeze(rows) {
  const prompts = promptsFromFreezeCompare(rows)
  if (!prompts.length) return false
  staleFreezeRows.value = prompts
  showStaleFreeze.value = true
  return true
}

function dismissStaleFreeze() {
  showStaleFreeze.value = false
  staleFreezeRows.value = []
}

async function confirmUnfreezeStale() {
  unfreezingStale.value = true
  try {
    for (const item of staleFreezeRows.value) {
      await call('lyqd.api.spa.freeze_upcoming_balance', {
        name: item.name,
        clear: 1,
      })
    }
    const n = staleFreezeRows.value.length
    toast.success(
      n > 1
        ? `Unfrozen ${n} rows · live GL updated`
        : 'Unfrozen · live GL updated',
    )
    dismissStaleFreeze()
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not unfreeze')
  } finally {
    unfreezingStale.value = false
  }
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
    const prompted = promptStaleFreeze(res.freeze_compare || [])
    if (prompted) {
      /* dialog handles next step */
    }
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

function isRecGroupExpanded(item) {
  return !!expandedRecGroups.value[recommendationKey(item)]
}

function toggleRecGroup(item) {
  const key = recommendationKey(item)
  expandedRecGroups.value = {
    ...expandedRecGroups.value,
    [key]: !expandedRecGroups.value[key],
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
    let anyAmountUpdated = false
    const freezeCompare = []
    for (const m of targets) {
      const res = await call('lyqd.api.spa.refresh_upcoming_from_books', { name: m.name })
      lastAction = res.action || lastAction
      asOfUsed = res.as_of_used || asOfUsed
      if (res.action === 'amount_updated') anyAmountUpdated = true
      if (res.balance_as_of && res.live_today_amount != null) freezeCompare.push(res)
    }
    const n = targets.length
    const asOfNote =
      row.balance_as_of || asOfUsed
        ? ` (as of ${formatDate(row.balance_as_of || asOfUsed)})`
        : ''
    cache.invalidatePlanRelated(company.current)
    await reloadAll()
    const prompted = promptStaleFreeze(freezeCompare)
    if (prompted) {
      toast.success(
        n > 1
          ? `Refreshed ${n} rows at freeze date${asOfNote}`
          : `Refreshed freeze date${asOfNote}`,
      )
    } else {
      toast.success(
        n > 1
          ? `Refreshed ${n} linked rows from books${asOfNote}`
          : `${labels[anyAmountUpdated ? 'amount_updated' : lastAction] || `Synced (${lastAction})`}${asOfNote}`,
      )
    }
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
        ? `Recorded ${(row.frequency || 'Monthly').toLowerCase()} · next due advanced`
        : targets.length > 1
          ? `Marked ${targets.length} paid`
          : 'Marked paid',
    )
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
    source_row: item.source_row || '',
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
  accepting.value = recommendationKey(acceptForm)
  try {
    await call('lyqd.api.spa.accept_upcoming_recommendation', {
      company: company.current,
      source_doctype: acceptForm.source_doctype,
      source_name: acceptForm.source_name,
      source_row: acceptForm.source_row || null,
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
        cash_effect: form.is_recurring ? 'Outflow' : form.cash_effect || 'Outflow',
        due_date: form.due_date,
        amount: form.amount,
        period_amount: form.amount,
        is_recurring: form.is_recurring ? 1 : 0,
        frequency: form.is_recurring ? form.frequency || 'Monthly' : null,
        recurrence_end: form.is_recurring ? form.recurrence_end || null : null,
        status: form.is_recurring ? 'Planned' : form.status || 'Planned',
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
