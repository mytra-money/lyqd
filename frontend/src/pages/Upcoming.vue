<template>
  <div>
    <PageHeader title="Commitments" :subtitle="commitmentsSubtitle">
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

    <!-- PWA / narrow: tabs instead of stacking both columns into one long scroll -->
    <div
      v-if="isNarrowLayout"
      class="mb-3 flex w-full rounded-md border border-gray-200 bg-white p-0.5"
      role="tablist"
      aria-label="Commitments columns"
    >
      <button
        type="button"
        role="tab"
        class="min-w-0 flex-1 rounded px-3 py-2 text-sm font-medium transition-colors"
        :class="
          columnTab === 'plan'
            ? 'bg-gray-900 text-white'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        "
        :aria-selected="columnTab === 'plan'"
        @click="columnTab = 'plan'"
      >
        On the plan
        <span class="tabular-nums opacity-70">{{ activePlanCount }}</span>
      </button>
      <button
        type="button"
        role="tab"
        class="min-w-0 flex-1 rounded px-3 py-2 text-sm font-medium transition-colors"
        :class="
          columnTab === 'books'
            ? 'bg-gray-900 text-white'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        "
        :aria-selected="columnTab === 'books'"
        @click="columnTab = 'books'"
      >
        From books
        <span v-if="recsEnabled" class="tabular-nums opacity-70">{{ allRecs.length }}</span>
      </button>
    </div>

    <div class="grid gap-4 lg:grid-cols-2 lg:items-start">
    <!-- ── On the plan ── -->
    <section
      v-show="!isNarrowLayout || columnTab === 'plan'"
      class="min-w-0 rounded-lg border border-gray-200 bg-white"
      role="tabpanel"
    >
      <header class="border-b border-gray-100 px-4 py-3">
        <div class="flex items-baseline justify-between gap-2">
          <h2 class="text-base font-semibold text-gray-900">On the plan</h2>
          <span class="text-xs tabular-nums text-gray-500">{{ activePlanCount }} active</span>
        </div>
        <p v-if="!isNarrowLayout" class="mt-0.5 text-xs text-gray-500">
          These amounts reduce free cash when Planned.
        </p>
        <div class="mt-2.5 space-y-2">
          <FormControl
            v-model="plannedQuery"
            class="w-full [&_input]:w-full"
            size="sm"
            placeholder="Search plan"
          />
          <div class="flex gap-2">
            <FormControl
              v-model="plannedView"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="plannedStatusOptions"
            />
            <FormControl
              v-model="effectFilter"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="plannedEffectOptions"
            />
            <FormControl
              v-model="categoryFilter"
              class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
              type="select"
              size="sm"
              :options="plannedCategoryOptions"
            />
          </div>
        </div>
      </header>

      <EmptyState
        v-if="!filteredList.length && plannedFiltersActive"
        variant="filter"
        title="Nothing matches"
        description="Try another status, direction, category, or clear the search."
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
        <CommitmentRow
          v-for="row in nestedFilteredList"
          :key="row.name"
          hoverable
          :row="row"
          :as-of="todayStr()"
          :expanded="isGroupExpanded(row.name)"
          :marking="marking === row.name"
          :can-mark-paid="groupCanMarkPaid(row)"
          :can-refresh="groupCanRefresh(row)"
          :can-freeze="groupCanFreeze(row)"
          :can-split="canSplitRow(row)"
          :refreshing="refreshing === row.name"
          :freezing="freezing === row.name"
          @toggle-group="toggleGroup(row.name)"
          @edit="(payload) => edit(payload?._schedule ? payload : row)"
          @mark-paid="(payload) => markPaid(payload?._schedule ? payload : row)"
          @refresh="refreshRow(row)"
          @freeze="openFreeze(row)"
          @clear-freeze="clearFreeze(row)"
          @split="openSplit(row)"
        />
      </ul>
    </section>

    <!-- ── From books ── -->
    <section
      v-show="!isNarrowLayout || columnTab === 'books'"
      class="min-w-0 rounded-lg border border-gray-200 bg-white"
      role="tabpanel"
    >
      <header class="border-b border-gray-100 px-4 py-3">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div v-if="!isNarrowLayout">
            <h2 class="text-base font-semibold text-gray-900">From books</h2>
            <p class="mt-0.5 text-xs text-gray-500">
              Optional intake — not reserved until you add to plan.
            </p>
          </div>
          <button
            v-if="recsEnabled"
            type="button"
            class="text-xs text-gray-500 hover:text-gray-800"
            :class="isNarrowLayout ? 'ml-auto' : ''"
            @click="$router.push('/settings?tab=integrations')"
          >
            Configure accounts
          </button>
        </div>

        <template v-if="recsEnabled">
          <div class="mt-2.5 space-y-2">
            <FormControl
              v-model="recQuery"
              class="w-full [&_input]:w-full"
              size="sm"
              placeholder="Search suggestions"
            />
            <div class="flex gap-2">
              <FormControl
                v-model="suggestionView"
                class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
                type="select"
                size="sm"
                :options="suggestionStatusOptions"
              />
              <FormControl
                v-model="recAccount"
                class="min-w-0 flex-1 sm:max-w-[11rem] [&_button]:w-full"
                type="select"
                size="sm"
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
              <div class="mt-1 flex flex-col items-end gap-0.5">
                <button
                  type="button"
                  class="text-xs font-medium text-gray-900 hover:underline disabled:opacity-50"
                  :disabled="
                    accepting === recommendationKey(item) || ignoring === recommendationKey(item)
                  "
                  @click="openAccept(item)"
                >
                  Add to plan
                </button>
                <button
                  type="button"
                  class="text-xs text-gray-500 hover:text-gray-800 hover:underline disabled:opacity-50"
                  :disabled="
                    accepting === recommendationKey(item) || ignoring === recommendationKey(item)
                  "
                  @click="confirmIgnore(item)"
                >
                  Ignore
                </button>
              </div>
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
                <div class="mt-1 flex flex-col items-end gap-0.5">
                  <button
                    type="button"
                    class="text-xs font-medium text-gray-900 hover:underline disabled:opacity-50"
                    :disabled="
                      accepting === recommendationKey(child) ||
                      ignoring === recommendationKey(child)
                    "
                    @click="openAccept(child)"
                  >
                    Add to plan
                  </button>
                  <button
                    type="button"
                    class="text-xs text-gray-500 hover:text-gray-800 hover:underline disabled:opacity-50"
                    :disabled="
                      accepting === recommendationKey(child) ||
                      ignoring === recommendationKey(child)
                    "
                    @click="confirmIgnore(child)"
                  >
                    Ignore
                  </button>
                </div>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </section>
    </div>

    <PlanCalendarDialog
      :model-value="showPlanCalendar"
      @update:model-value="onPlanCalendarOpenChange"
      @edit="edit"
      @changed="loadPlan(true)"
    />

    <Dialog
      v-model="show"
      :options="{
        title: editDialogTitle,
      }"
    >
      <template #body-content>
        <div class="space-y-3">
          <!-- Split schedule line: installment-focused editor -->
          <template v-if="form.edit_mode === 'split_line'">
            <p class="text-sm text-gray-600">
              {{ form.title }}
            </p>
            <div
              class="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-800"
            >
              <div class="flex justify-between gap-3">
                <span class="text-gray-500">Due</span>
                <span class="font-medium tabular-nums">{{ form.due_date || '—' }}</span>
              </div>
              <div class="mt-1 flex justify-between gap-3">
                <span class="text-gray-500">Amount</span>
                <span class="font-medium tabular-nums">{{ formatINR(form.amount) }}</span>
              </div>
              <div class="mt-1 flex justify-between gap-3">
                <span class="text-gray-500">Status</span>
                <span class="font-medium">{{ form.status || 'Planned' }}</span>
              </div>
            </div>
            <FormControl
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              v-model="form.probability"
              type="number"
              label="Probability (%)"
              :min="0"
              :max="100"
            />
            <p
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
            >
              Expected cash for this installment uses this probability. Amount and due date come
              from the split schedule — use Re-split to change them.
            </p>
            <p v-if="form.source_doctype" class="text-xs text-gray-500">
              Source {{ form.source_doctype }} {{ form.source_name }}
            </p>
          </template>

          <!-- Parent with split schedule: read-only ladder + per-line probability -->
          <template v-else-if="form.edit_mode === 'split_schedule'">
            <FormControl
              v-model="form.category"
              type="select"
              label="Category"
              :options="categoryOptions"
              @update:model-value="onCategoryChange"
            />
            <FormControl v-model="form.title" label="Title" />
            <div
              class="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-800"
            >
              <div class="flex justify-between gap-3">
                <span class="text-gray-500">Cash effect</span>
                <span class="font-medium">{{
                  form.cash_effect === 'Inflow' ? 'Inflow (receive)' : form.cash_effect
                }}</span>
              </div>
              <div class="mt-1 flex justify-between gap-3">
                <span class="text-gray-500">Total (planned)</span>
                <span class="font-medium tabular-nums">{{ formatINR(splitScheduleTotal) }}</span>
              </div>
            </div>
            <div class="space-y-2">
              <div class="text-xs font-medium uppercase tracking-wide text-gray-500">
                Split schedule
              </div>
              <ul class="divide-y divide-gray-100 overflow-hidden rounded-md border border-gray-200">
                <li
                  v-for="(line, idx) in form.splits"
                  :key="line.name || idx"
                  class="space-y-2 bg-white px-3 py-2.5"
                >
                  <div class="flex items-start justify-between gap-2 text-sm">
                    <div class="min-w-0">
                      <div class="font-medium text-gray-900">
                        {{ splitPartLabel(idx + 1, form.splits.length) || `Part ${idx + 1}` }}
                        <span
                          v-if="line.status === 'Paid'"
                          class="ml-1 rounded bg-gray-100 px-1 py-px text-[10px] font-medium text-gray-600"
                          >Paid</span
                        >
                      </div>
                      <div class="mt-0.5 text-xs text-gray-500">
                        Due {{ line.due_date || '—' }} ·
                        <span class="tabular-nums">{{ formatINR(line.amount) }}</span>
                      </div>
                    </div>
                  </div>
                  <FormControl
                    v-if="
                      (form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff') &&
                      line.status !== 'Paid'
                    "
                    v-model="line.probability"
                    type="number"
                    label="Probability (%)"
                    :min="0"
                    :max="100"
                  />
                </li>
              </ul>
              <p class="text-xs text-gray-500">
                Amounts and due dates are set by the split schedule. Use Re-split to remap them.
              </p>
            </div>
            <FormControl v-model="form.notes" type="textarea" label="Notes" />
            <p v-if="form.source_doctype" class="text-xs text-gray-500">
              Source {{ form.source_doctype }} {{ form.source_name }}
            </p>
          </template>

          <!-- Normal payment / accept -->
          <template v-else>
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
              Due date follows the parent plan row. Change the parent’s due date to update this
              group.
            </p>
            <CurrencyControl
              v-model="form.amount"
              :label="
                form.is_recurring
                  ? `Amount each ${frequencyUnit(form.frequency)}`
                  : 'Amount'
              "
            />
            <FormControl
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              v-model="form.probability"
              type="number"
              label="Probability (%)"
              :min="0"
              :max="100"
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
              v-if="form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff'"
              class="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
            >
              Incoming — shown on Cash position separately. Does not change free cash today
              (free cash = bank − commitments − policy). Set Probability for the expected amount.
            </p>
            <FormControl
              v-if="form.name && !form.is_recurring"
              v-model="form.status"
              type="select"
              label="Status"
              :options="statusOptions"
            />
            <FormControl v-model="form.notes" type="textarea" label="Notes" />
            <p v-if="form.source_doctype" class="text-xs text-gray-500">
              Source {{ form.source_doctype }} {{ form.source_name }}
            </p>
          </template>
        </div>
      </template>
      <template #actions>
        <Button
          v-if="form.edit_mode === 'split_line' || form.edit_mode === 'split_schedule'"
          variant="outline"
          @click="openResplitFromEdit"
        >
          Re-split…
        </Button>
        <Button
          variant="solid"
          :loading="saving || !!accepting"
          @click="form.source_doctype && !form.name ? confirmAccept() : save()"
        >
          {{ form.source_doctype && !form.name ? 'Add to plan' : 'Save' }}
        </Button>
        <Button variant="outline" @click="closeEdit">Cancel</Button>
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
            <span v-if="freezeForm.childCount">
              · {{ freezeForm.hasSplits ? freezeForm.childCount : freezeForm.childCount + 1 }} rows
            </span>
          </p>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="!!freezing" @click="confirmFreeze">Freeze &amp; sync</Button>
        <Button variant="outline" @click="showFreeze = false">Cancel</Button>
      </template>
    </Dialog>

    <Dialog v-model="showSplit" :options="{ title: 'Split payment' }">
      <template #body-content>
        <div class="space-y-3">
          <div class="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
            <div class="font-medium text-gray-900">{{ splitForm.title || 'Payment' }}</div>
            <div class="mt-0.5 tabular-nums text-xs text-gray-500">
              Total {{ formatINR(splitForm.amount) }}
              <span v-if="splitForm.sourceDoctype === 'Account'"> · GL balance</span>
            </div>
          </div>

          <p v-if="splitForm.resplit" class="text-xs text-amber-800">
            Remapping an existing split ({{ splitForm.familySize }} rows). Saving replaces them
            with the ladder below. Use 1 row to merge back into a single commitment.
          </p>

          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="splitForm.count"
              type="number"
              label="Number of rows"
              :min="1"
              :max="24"
              @update:model-value="onSplitCountChange"
            />
            <FormControl
              v-model="splitForm.mode"
              type="select"
              label="Split type"
              :options="splitModeOptions"
              :disabled="Number(splitForm.count) <= 1"
              @update:model-value="onSplitModeChange"
            />
          </div>

          <p class="text-xs text-gray-500">
            <template v-if="Number(splitForm.count) <= 1">
              Merge into one row for the full {{ formatINR(splitForm.amount) }} total
              <template v-if="splitForm.basisSource === 'books'"> (from books)</template>.
            </template>
            <template v-else-if="splitForm.mode === 'equal'">
              Equal amounts; last row takes any rounding remainder so the total stays exact.
            </template>
            <template v-else-if="splitForm.mode === 'schedule'">
              Prefills from the books Payment Schedule. Last row stays the balance of the total.
            </template>
            <template v-else>
              Enter amounts on the first rows; the last row is always the remaining balance.
            </template>
          </p>

          <div class="max-h-[min(50vh,22rem)] space-y-2 overflow-y-auto pr-0.5">
            <div
              v-for="(line, idx) in splitForm.rows"
              :key="idx"
              class="grid grid-cols-[auto_1fr_1fr] items-end gap-2 rounded-md border border-gray-200 px-2.5 py-2"
            >
              <div class="pb-2 text-xs font-semibold tabular-nums text-gray-400">
                {{ idx + 1 }}
              </div>
              <FormControl v-model="line.due_date" type="date" label="Due" />
              <CurrencyControl
                :model-value="line.amount"
                :label="idx === splitForm.rows.length - 1 ? 'Balance' : 'Amount'"
                :disabled="idx === splitForm.rows.length - 1 || splitForm.mode === 'equal'"
                @update:model-value="onSplitAmountInput(idx, $event)"
              />
            </div>
          </div>

          <p
            v-if="!splitSumOk || splitLastNegative"
            class="text-xs font-medium text-red-600"
          >
            <template v-if="splitLastNegative">
              Earlier amounts exceed the total — reduce them so the last balance is ≥ 0.
            </template>
            <template v-else>
              Amounts must add up to {{ formatINR(splitForm.amount) }}.
            </template>
          </p>
        </div>
      </template>
      <template #actions>
        <Button
          variant="solid"
          :loading="splitting"
          :disabled="!splitSumOk || splitLastNegative"
          @click="confirmSplit"
        >
          Split into {{ splitForm.rows.length }}
        </Button>
        <Button variant="outline" :disabled="splitting" @click="showSplit = false">
          Cancel
        </Button>
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

    <Dialog
      v-model="showSplitAdjust"
      :options="{ title: 'Live GL differs from split schedule' }"
    >
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-gray-600">
            Splitting a GL balance freezes that ladder. Today’s books no longer match the
            schedule total — adjust the split to the new balance, or keep the current dates
            and amounts.
          </p>
          <ul class="divide-y divide-gray-100 rounded-md border border-gray-200">
            <li
              v-for="item in splitAdjustRows"
              :key="item.name"
              class="px-3 py-2.5 text-sm"
            >
              <div class="font-medium text-gray-900">{{ item.title || item.name }}</div>
              <div class="mt-0.5 text-xs text-gray-500">
                Schedule {{ formatINR(item.covered_total ?? item.amount) }}
                <span v-if="item.balance_as_of">
                  · frozen {{ formatDate(item.balance_as_of) }}</span
                >
                · Live {{ formatINR(item.live_today_amount ?? item.books_amount) }}
                · gap {{ formatINR(item.difference) }}
              </div>
            </li>
          </ul>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" @click="confirmAdjustSplit">Adjust split…</Button>
        <Button variant="outline" @click="dismissSplitAdjust">Keep schedule</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { Button, call } from 'frappe-ui'
import { toast } from '@/utils/toast'
import CommitmentRow from '@/components/CommitmentRow.vue'
import CurrencyControl from '@/components/CurrencyControl.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import PlanCalendarDialog from '@/components/PlanCalendarDialog.vue'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { usePlanCalendar } from '@/composables/usePlanCalendar'
import { formatDate, formatINR } from '@/utils/format'
import {
  daysUntil,
  dueLabel,
  frequencyUnit,
  isOverdue,
  shortAccount,
  splitPartLabel,
  stripSplitIndexSuffix,
} from '@/utils/commitment'
import {
  groupMembers,
  nestPlanRows,
  nestRecommendationRows,
  planSignedNet,
  recommendationKey,
  signedCashAmount,
} from '@/utils/planNest'

defineOptions({ name: 'Upcoming' })

const { showPlanCalendar, onPlanCalendarOpenChange } = usePlanCalendar('/upcoming')

const company = useCompanyStore()
const cache = useTreasuryCacheStore()
const show = ref(false)
const showSplit = ref(false)
const saving = ref(false)
const accepting = ref(null)
const ignoring = ref(null)
const marking = ref(null)
const syncing = ref(false)
const refreshing = ref(null)
const freezing = ref(null)
const splitting = ref(false)
const splitForm = reactive({
  name: '',
  title: '',
  amount: 0,
  sourceDoctype: '',
  previewSource: 'current',
  basisSource: 'row',
  resplit: false,
  familySize: 1,
  mode: 'equal', // equal | manual | schedule
  count: 2,
  /** Books schedule snapshot when available (for schedule mode). */
  scheduleRows: [],
  /** Existing family ladder when remapping. */
  familyRows: [],
  rows: [],
})
const splitModeOptions = computed(() => {
  const opts = [
    { label: 'Equal amounts', value: 'equal' },
    { label: 'Manual amounts', value: 'manual' },
  ]
  if ((splitForm.scheduleRows || []).length >= 2) {
    opts.push({ label: 'From payment schedule', value: 'schedule' })
  }
  if ((splitForm.familyRows || []).length >= 2) {
    opts.unshift({ label: 'Current split', value: 'family' })
  }
  return opts
})
const splitSum = computed(() =>
  (splitForm.rows || []).reduce((s, r) => s + (Number(r.amount) || 0), 0),
)
const splitSumOk = computed(
  () => Math.abs(splitSum.value - Number(splitForm.amount || 0)) <= 0.05,
)
const splitLastNegative = computed(() => {
  const rows = splitForm.rows || []
  if (!rows.length) return false
  return Number(rows[rows.length - 1]?.amount) < -0.009
})
/** 'clear' while unfreezing, 'set' while freezing from dialog */
const freezeAction = ref(null)
const showFreeze = ref(false)
const freezeForm = reactive({
  name: '',
  title: '',
  as_of: '',
  childCount: 0,
  hasSplits: false,
})
const showStaleFreeze = ref(false)
const staleFreezeRows = ref([])
const unfreezingStale = ref(false)
const showSplitAdjust = ref(false)
const splitAdjustRows = ref([])
let recsDeferTimer = null

const route = useRoute()
const router = useRouter()
const plannedView = ref('active')
const effectFilter = ref('all')
const categoryFilter = ref('all')
const plannedQuery = ref('')
/** Group parents expanded by name; default collapsed. */
const expandedGroups = ref({})
/** From-books nested groups expanded by recommendation key. */
const expandedRecGroups = ref({})

const suggestionView = ref('all')
const recAccount = ref('all')
const recQuery = ref('')

/** Match Tailwind `lg` — below this the two columns stack; use tabs instead. */
const isNarrowLayout = useMediaQuery('(max-width: 1023px)')
/** Mobile / PWA column: plan vs books */
const columnTab = ref('plan')

const commitmentsSubtitle = computed(() =>
  isNarrowLayout.value
    ? 'Switch tabs for the plan and optional books suggestions.'
    : 'Plan on the left reserves free cash. From books on the right is optional until you add to plan.',
)

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
const statusOptions = ['Planned', 'Paid', 'Cancelled', 'Ignored'].map((s) => ({
  label: s,
  value: s,
}))

const categoryValues = categoryOptions.map((c) => c.value)

const empty = () => ({
  name: null,
  title: 'Other',
  category: 'Other',
  due_date: '',
  amount: 0,
  cash_effect: 'Outflow',
  probability: 100,
  status: 'Planned',
  notes: '',
  parent_payment: '',
  source_doctype: '',
  source_name: '',
  source_row: '',
  account: '',
  is_recurring: false,
  frequency: 'Monthly',
  recurrence_end: '',
  /** payment | split_schedule | split_line */
  edit_mode: 'payment',
  has_splits: false,
  split_name: '',
  splits: [],
})
const form = reactive(empty())

const editDialogTitle = computed(() => {
  if (!form.name) {
    return form.source_doctype ? 'Add to plan' : 'Add payment'
  }
  if (form.edit_mode === 'split_line') return 'Edit split installment'
  if (form.edit_mode === 'split_schedule') return 'Edit split payment'
  return 'Edit payment'
})

const splitScheduleTotal = computed(() =>
  (form.splits || [])
    .filter((s) => (s.status || 'Planned') === 'Planned')
    .reduce((sum, s) => sum + (Number(s.amount) || 0), 0),
)

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

const allRows = computed(() => cache.getPlan(company.current) || [])
const allRecs = computed(() => recsPayload.value?.items || [])

const activePlanCount = computed(
  () => allRows.value.filter((r) => r.status === 'Planned').length,
)

const plannedStatusOptions = computed(() => {
  const rows = allRows.value
  const active = rows.filter((r) => r.status === 'Planned')
  const ignored = rows.filter((r) => r.status === 'Ignored')
  return [
    { label: `Active (${active.length})`, value: 'active' },
    {
      label: `Overdue (${active.filter((r) => isOverdue(r.due_date)).length})`,
      value: 'overdue',
    },
    {
      label: `Paid (${rows.filter((r) => r.status === 'Paid').length})`,
      value: 'paid',
    },
    { label: `Ignored (${ignored.length})`, value: 'ignored' },
  ]
})

const plannedEffectOptions = computed(() => {
  const nested = nestPlanRows(allRows.value)
  const outgoing = nested.filter((r) => planSignedNet(r) > 0.01).length
  const incoming = nested.filter((r) => planSignedNet(r) < -0.01).length
  return [
    { label: 'Direction', value: 'all' },
    { label: `Outgoing (${outgoing})`, value: 'outflow' },
    { label: `Incoming (${incoming})`, value: 'inflow' },
  ]
})

const suggestionStatusOptions = computed(() => {
  const items = allRecs.value
  return [
    { label: `All (${items.length})`, value: 'all' },
    {
      label: `Overdue (${items.filter((i) => isOverdue(i.due_date)).length})`,
      value: 'overdue',
    },
    {
      label: `7 days (${
        items.filter((i) => {
          const d = daysUntil(i.due_date)
          return d !== null && d >= 0 && d <= 7
        }).length
      })`,
      value: 'soon',
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
    effectFilter.value !== 'all' ||
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
    if (plannedView.value === 'ignored' && r.status !== 'Ignored') return false
    if (categoryFilter.value !== 'all' && r.category !== categoryFilter.value) return false
    if (q) {
      const hay = `${r.title || ''} ${r.category || ''} ${r.source_name || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const nestedFilteredList = computed(() => {
  let nested = nestPlanRows(filteredList.value)
  // Nest / split: direction uses signed group net, not parent cash_effect alone
  if (effectFilter.value === 'outflow') {
    nested = nested.filter((r) => planSignedNet(r) > 0.01)
  } else if (effectFilter.value === 'inflow') {
    nested = nested.filter((r) => planSignedNet(r) < -0.01)
  }
  return nested
})

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
  effectFilter.value = 'all'
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

function closeEdit() {
  show.value = false
}

function scheduleLinesFromRow(row) {
  return (row?._children || [])
    .filter((c) => c._schedule)
    .map((c) => ({
      name: c.split_name || c.name,
      split_name: c.split_name,
      title: c.title || row.title,
      due_date: c.due_date,
      amount: Number(c.amount) || 0,
      status: c.status || 'Planned',
      probability: c.probability != null ? Number(c.probability) : 100,
    }))
}

function editSplitLine(child, parentRow) {
  const parent = parentRow || findPlanRow(child.parent_payment)
  const effect =
    (parent?.cash_effect || child.cash_effect) === 'Setoff'
      ? 'Inflow'
      : parent?.cash_effect || child.cash_effect || 'Outflow'
  Object.assign(form, empty(), {
    name: child.parent_payment || parent?.name,
    title: child.title || parent?.title || '',
    category: parent?.category || child.category || 'Other',
    due_date: child.due_date,
    amount: Number(child.amount) || 0,
    cash_effect: effect,
    probability: child.probability != null ? Number(child.probability) : 100,
    status: child.status || 'Planned',
    notes: parent?.notes || '',
    parent_payment: '',
    source_doctype: parent?.source_doctype || child.source_doctype || '',
    source_name: parent?.source_name || child.source_name || '',
    source_row: parent?.source_row || '',
    account: parent?.source_account || '',
    edit_mode: 'split_line',
    has_splits: true,
    split_name: child.split_name,
    splits: [
      {
        name: child.split_name,
        split_name: child.split_name,
        title: child.title,
        due_date: child.due_date,
        amount: Number(child.amount) || 0,
        status: child.status || 'Planned',
        probability: child.probability != null ? Number(child.probability) : 100,
      },
    ],
  })
  show.value = true
}

function findPlanRow(name) {
  if (!name) return null
  const list = cache.getPlan(company.current) || []
  return list.find((p) => p.name === name) || null
}

function edit(row) {
  if (row?._schedule && row.split_name && row.parent_payment) {
    editSplitLine(row)
    return
  }
  const effect = row.cash_effect === 'Setoff' ? 'Inflow' : row.cash_effect || 'Outflow'
  const splits = scheduleLinesFromRow(row)
  const hasSplits = Boolean(row._has_splits && splits.length)
  Object.assign(form, empty(), {
    name: row.name,
    title: row.title,
    category: row.category,
    due_date: row.due_date,
    amount: row.period_amount != null ? row.period_amount : row.amount,
    cash_effect: effect,
    probability: row.probability != null ? Number(row.probability) : 100,
    status: row.status,
    notes: row.notes || '',
    parent_payment: row.parent_payment || '',
    source_doctype: row.source_doctype || '',
    source_name: row.source_name || '',
    source_row: row.source_row || '',
    account: row.source_account || '',
    is_recurring: !!row.is_recurring,
    frequency: row.frequency || 'Monthly',
    recurrence_end: row.recurrence_end || '',
    edit_mode: hasSplits ? 'split_schedule' : 'payment',
    has_splits: hasSplits,
    split_name: '',
    splits,
  })
  show.value = true
}

function openResplitFromEdit() {
  const name = form.name
  closeEdit()
  const row =
    findPlanRow(name) ||
    ({
      name,
      title: form.title,
      amount: form.has_splits ? splitScheduleTotal.value : form.amount,
      due_date: form.due_date,
      source_doctype: form.source_doctype,
      _has_splits: form.has_splits,
      _childCount: form.splits?.length || 0,
      _children: form.splits,
    })
  openSplit(row)
}

function syncToast(summary) {
  const parts = []
  if (summary.marked_paid) parts.push(`${summary.marked_paid} voucher(s) paid`)
  if (summary.amount_updated) parts.push(`${summary.amount_updated} amount(s) updated`)
  if (summary.cancelled) parts.push(`${summary.cancelled} cancelled`)
  if (summary.reopened) parts.push(`${summary.reopened} reopened`)
  if (summary.reconcile) parts.push(`${summary.reconcile} GL split(s) need review`)
  if (summary.awaiting_books)
    parts.push(`${summary.awaiting_books} GL split(s) match books (Paid awaiting posting)`)
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
  // GST-style nest freeze: only when live reserve is lower (exclude GL split ladders)
  const freezeOnly = (rows || []).filter((r) => !r.suggest_adjust_split && !r.schedule)
  const prompts = promptsFromFreezeCompare(freezeOnly)
  if (!prompts.length) return false
  staleFreezeRows.value = prompts
  showStaleFreeze.value = true
  return true
}

function dismissStaleFreeze() {
  showStaleFreeze.value = false
  staleFreezeRows.value = []
}

function promptSplitAdjust(rows) {
  const prompts = (rows || []).filter(
    (r) => r?.suggest_adjust_split && r.live_today_amount != null,
  )
  if (!prompts.length) return false
  splitAdjustRows.value = prompts
  showSplitAdjust.value = true
  return true
}

function dismissSplitAdjust() {
  showSplitAdjust.value = false
  splitAdjustRows.value = []
}

async function confirmAdjustSplit() {
  const first = splitAdjustRows.value[0]
  dismissSplitAdjust()
  if (!first?.name) return
  const plan = cache.getPlan(company.current) || []
  const row = plan.find((p) => p.name === first.name) || {
    name: first.name,
    title: first.title,
    amount: first.live_today_amount ?? first.books_amount,
    due_date: todayStr(),
    source_doctype: 'Account',
    _has_splits: true,
  }
  // Prefill Re-split against live books total
  await openSplit({
    ...row,
    amount: first.live_today_amount ?? first.books_amount ?? row.amount,
  })
}

async function confirmUnfreezeStale() {
  unfreezingStale.value = true
  try {
    const adjustAfter = []
    for (const item of staleFreezeRows.value) {
      const res = await call('lyqd.api.spa.freeze_upcoming_balance', {
        name: item.name,
        clear: 1,
      })
      if (res?.suggest_adjust_split && res?.split_adjust) {
        adjustAfter.push(res.split_adjust)
      }
    }
    const n = staleFreezeRows.value.length
    toast.success(
      n > 1
        ? `Unfrozen ${n} rows · live GL updated`
        : 'Unfrozen · live GL updated',
    )
    dismissStaleFreeze()
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    promptSplitAdjust(adjustAfter)
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
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    // Keep From-books on screen; refresh quietly in case sync cancelled/reopened rows
    cache.ensureRecommendations({ company: company.current, force: true, silent: true })
    const compare = res.freeze_compare || res.results || []
    const splitPrompted = promptSplitAdjust(compare)
    if (!splitPrompted) promptStaleFreeze(compare)
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
  // Split schedule owns the freeze — no Freeze/Unfreeze while ladder exists.
  if (row?._has_splits) return false
  // Account-grain only (GST/TDS GL). Parent owns freeze for the whole group.
  return groupMembers(row).some((m) => m.source_doctype === 'Account' && m.source_name)
}

function groupCanMarkPaid(row) {
  return groupMembers(row).some((m) => m.status === 'Planned')
}

function canSplitRow(row) {
  // Parent plan rows only (not GST nested docs, not schedule line synthetics)
  if (!row?.name || row._schedule) return false
  if (row.status !== 'Planned' && !row._has_splits) return false
  if (row.is_recurring) return false
  if (row.parent_payment && !row._has_splits) return false
  // Books-linked only — manual Add payment rows cannot be split
  const books =
    row.source_doctype &&
    row.source_name &&
    ['Account', 'Sales Invoice', 'Purchase Invoice'].includes(row.source_doctype)
  if (!books) return false
  // Already has a schedule table → Re-split
  if (row._has_splits) return true
  // Nest children of non-Account roots stay under their own books rows
  if (row._childCount && row.source_doctype !== 'Account') return false
  return row.status === 'Planned'
}

function roundMoney(n) {
  return Math.round((Number(n) + Number.EPSILON) * 100) / 100
}

function applySplitLastBalance() {
  const rows = splitForm.rows
  if (!rows?.length) return
  const total = Number(splitForm.amount) || 0
  if (rows.length === 1) {
    rows[0].amount = roundMoney(total)
    return
  }
  let used = 0
  for (let i = 0; i < rows.length - 1; i++) {
    used += Number(rows[i].amount) || 0
  }
  rows[rows.length - 1].amount = roundMoney(total - used)
}

function splitBaseTitle() {
  return stripSplitIndexSuffix(splitForm.title) || splitForm.title || ''
}

function buildEqualSplitRows(count, baseDue) {
  const n = Math.max(1, Math.min(24, Number(count) || 1))
  const total = Number(splitForm.amount) || 0
  const title = splitBaseTitle()
  const due = baseDue || todayStr()
  if (n === 1) {
    splitForm.rows = [{ title, due_date: due, amount: roundMoney(total) }]
    return
  }
  const share = roundMoney(total / n)
  const rows = []
  for (let i = 0; i < n; i++) {
    rows.push({
      title,
      due_date: due,
      amount: i < n - 1 ? share : 0,
    })
  }
  splitForm.rows = rows
  applySplitLastBalance()
}

function buildManualSplitRows(count, keepDates = true) {
  const n = Math.max(1, Math.min(24, Number(count) || 1))
  const prev = splitForm.rows || []
  const title = splitBaseTitle()
  if (n === 1) {
    splitForm.rows = [
      {
        title,
        due_date: (keepDates && prev[0]?.due_date) || todayStr(),
        amount: roundMoney(splitForm.amount),
      },
    ]
    return
  }
  const rows = []
  for (let i = 0; i < n; i++) {
    const prior = prev[i]
    rows.push({
      title: stripSplitIndexSuffix(prior?.title) || title,
      due_date: keepDates && prior?.due_date ? prior.due_date : todayStr(),
      amount: i < n - 1 ? Number(prior?.amount) || 0 : 0,
    })
  }
  splitForm.rows = rows
  applySplitLastBalance()
}

function buildScheduleSplitRows() {
  const sched = splitForm.scheduleRows || []
  if (sched.length < 2) {
    buildEqualSplitRows(splitForm.count)
    return
  }
  const title = splitBaseTitle()
  splitForm.count = sched.length
  splitForm.rows = sched.map((r, i) => ({
    title: stripSplitIndexSuffix(r.title) || title,
    due_date: r.due_date || todayStr(),
    amount: i < sched.length - 1 ? Number(r.amount) || 0 : 0,
  }))
  applySplitLastBalance()
}

function buildFamilySplitRows() {
  const fam = splitForm.familyRows || []
  if (fam.length < 1) {
    buildEqualSplitRows(splitForm.count)
    return
  }
  const title = splitBaseTitle()
  splitForm.count = fam.length
  splitForm.rows = fam.map((r, i) => ({
    title: stripSplitIndexSuffix(r.title) || title,
    due_date: r.due_date || todayStr(),
    amount: i < fam.length - 1 ? Number(r.amount) || 0 : 0,
  }))
  applySplitLastBalance()
}

function rebuildSplitRows() {
  if (Number(splitForm.count) <= 1) {
    buildEqualSplitRows(1, splitForm.rows?.[0]?.due_date || todayStr())
    return
  }
  if (splitForm.mode === 'family') {
    buildFamilySplitRows()
  } else if (splitForm.mode === 'schedule') {
    buildScheduleSplitRows()
  } else if (splitForm.mode === 'equal') {
    const due = splitForm.rows?.[0]?.due_date || todayStr()
    buildEqualSplitRows(splitForm.count, due)
  } else {
    buildManualSplitRows(splitForm.count)
  }
}

function onSplitCountChange(raw) {
  let n = parseInt(raw, 10)
  if (Number.isNaN(n)) n = 2
  n = Math.max(1, Math.min(24, n))
  splitForm.count = n
  if (n === 1) {
    rebuildSplitRows()
    return
  }
  if (splitForm.mode === 'schedule' || splitForm.mode === 'family') {
    splitForm.mode = 'manual'
  }
  rebuildSplitRows()
}

function onSplitModeChange() {
  rebuildSplitRows()
}

function onSplitAmountInput(idx, value) {
  if (idx >= splitForm.rows.length - 1) return
  splitForm.rows[idx].amount = value == null || value === '' ? 0 : Number(value)
  applySplitLastBalance()
}

async function openSplit(row) {
  splitForm.name = row.name
  splitForm.title = stripSplitIndexSuffix(row.title) || row.title || row.name
  // Nest roots: stored/signed group net (outflows − inflows), not root grain alone
  const groupNet = Number(
    row._groupNet != null
      ? row._groupNet
      : row.group_net != null && row.group_net !== ''
        ? row.group_net
        : NaN,
  )
  if (row._childCount && Number.isFinite(groupNet) && groupNet > 0.01) {
    splitForm.amount = roundMoney(groupNet)
  } else {
    splitForm.amount = Number(row.amount) || 0
  }
  splitForm.sourceDoctype = row.source_doctype || ''
  splitForm.previewSource = 'current'
  splitForm.basisSource = row._childCount ? 'plan_group' : 'row'
  splitForm.resplit = false
  splitForm.familySize = 1
  splitForm.scheduleRows = []
  splitForm.familyRows = []
  splitForm.mode = 'equal'
  splitForm.count = 2
  buildEqualSplitRows(2, row.due_date || todayStr())
  showSplit.value = true
  try {
    const res = await call('lyqd.api.spa.preview_split_upcoming_payment', {
      name: row.name,
    })
    if (res?.amount != null) splitForm.amount = Number(res.amount) || splitForm.amount
    splitForm.basisSource = res?.basis_source || splitForm.basisSource
    splitForm.resplit = !!res?.resplit
    splitForm.familySize = res?.family_size || 1
    if (res?.title) {
      splitForm.title = stripSplitIndexSuffix(res.title) || splitForm.title
    }
    if (res?.rows?.length) {
      const base = splitBaseTitle()
      splitForm.familyRows = res.rows.map((r) => ({
        title: stripSplitIndexSuffix(r.title) || base,
        due_date: r.due_date || todayStr(),
        amount: Number(r.amount) || 0,
      }))
    }
    if (res?.preview_source === 'payment_schedule' && res?.rows?.length >= 2) {
      splitForm.scheduleRows = splitForm.familyRows.slice()
      splitForm.previewSource = 'payment_schedule'
      splitForm.mode = 'schedule'
      buildScheduleSplitRows()
    } else if (res?.resplit && (res?.rows || []).length >= 1) {
      splitForm.previewSource = 'existing_split'
      splitForm.mode = (res.rows || []).length >= 2 ? 'family' : 'equal'
      splitForm.count = Math.max(1, (res.rows || []).length)
      rebuildSplitRows()
    } else {
      buildEqualSplitRows(splitForm.count, row.due_date || todayStr())
    }
  } catch {
    buildEqualSplitRows(2, row.due_date || todayStr())
  }
}

async function confirmSplit() {
  applySplitLastBalance()
  if (splitLastNegative.value || !splitSumOk.value) {
    toast.error('Fix split amounts so the last balance matches the total')
    return
  }
  splitting.value = true
  try {
    const n = splitForm.rows.length
    const baseTitle = splitBaseTitle()
    const res = await call('lyqd.api.spa.split_upcoming_payment', {
      name: splitForm.name,
      rows: splitForm.rows.map((r) => ({
        title: stripSplitIndexSuffix(r.title) || baseTitle,
        due_date: r.due_date,
        amount: r.amount,
      })),
    })
    toast.success(
      res?.merged
        ? 'Merged back into one plan row'
        : `${splitForm.resplit ? 'Re-split' : 'Split'} into ${res?.count || n} plan rows`,
    )
    showSplit.value = false
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Split failed')
  } finally {
    splitting.value = false
  }
}

async function openFreeze(row) {
  freezeForm.name = row.name
  freezeForm.title = row.title || row.name
  freezeForm.childCount = row._childCount || 0
  freezeForm.hasSplits = Boolean(row._has_splits)
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
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
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
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    if (res?.suggest_adjust_split && res?.split_adjust) {
      promptSplitAdjust([res.split_adjust])
    }
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not unfreeze')
  } finally {
    freezing.value = null
    freezeAction.value = null
  }
}

function refreshFamilyKey(m) {
  if (!m?.source_doctype || !m?.source_name) return m?.name || ''
  if (
    m.source_doctype === 'Purchase Invoice' ||
    m.source_doctype === 'Sales Invoice' ||
    m.source_doctype === 'Account'
  ) {
    return `${m.source_doctype}:${m.source_name}`
  }
  return m.name
}

async function refreshRow(row) {
  refreshing.value = row.name
  try {
    const targets = groupMembers(row).filter((m) => m.source_doctype && m.source_name)
    // One API call per books family (voucher / Account split syncs siblings together)
    const seen = new Set()
    const unique = []
    for (const m of targets) {
      const key = refreshFamilyKey(m)
      if (seen.has(key)) continue
      seen.add(key)
      unique.push(m)
    }
    const labels = {
      marked_paid: 'Marked paid from books (voucher cleared)',
      amount_updated: 'Amount updated from books',
      cancelled: 'Cancelled — missing/cancelled in books',
      reopened: 'Back on plan from books',
      unchanged: 'Already up to date',
      reconcile: 'Books vs plan differ — review the ladder',
      awaiting_books: 'Matches books (including Paid awaiting GL posting)',
      skipped: 'Skipped',
    }
    let lastAction = 'unchanged'
    let asOfUsed = null
    let anyAmountUpdated = false
    let awaitingMsg = null
    let booksSetChanged = false
    const freezeCompare = []
    for (const m of unique) {
      const res = await call('lyqd.api.spa.refresh_upcoming_from_books', { name: m.name })
      lastAction = res.action || lastAction
      asOfUsed = res.as_of_used || asOfUsed
      if (res.action === 'amount_updated') anyAmountUpdated = true
      // Cancelled / reopened changes what From-books should show — refresh quietly
      if (res.action === 'cancelled' || res.action === 'reopened') booksSetChanged = true
      if (res.action === 'awaiting_books') {
        awaitingMsg = `Books ${formatINR(res.books_amount ?? res.live_amount)} match plan (Planned ${formatINR(res.plan_total)} + Paid ${formatINR(res.paid_on_plan)} awaiting books)`
      }
      if (res.live_today_amount != null && (res.suggest_adjust_split || res.balance_as_of)) {
        freezeCompare.push(res)
      }
    }
    const n = unique.length
    const asOfNote =
      row.balance_as_of || asOfUsed
        ? ` (as of ${formatDate(row.balance_as_of || asOfUsed)})`
        : ''
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    if (booksSetChanged) {
      cache.ensureRecommendations({ company: company.current, force: true, silent: true })
    }
    const splitPrompted = promptSplitAdjust(freezeCompare)
    const prompted = splitPrompted ? false : promptStaleFreeze(freezeCompare)
    if (awaitingMsg && !splitPrompted) {
      toast.success(awaitingMsg)
    } else if (prompted || splitPrompted) {
      toast.success(
        n > 1
          ? `Refreshed ${n} rows from books${asOfNote}`
          : `Refreshed from books${asOfNote}`,
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
    // Single GL schedule line (child table)
    if (row._schedule && row.split_name && row.parent_payment) {
      await call('lyqd.api.spa.mark_upcoming_split_paid', {
        parent: row.parent_payment,
        split_row_name: row.split_name,
      })
      toast.success('Marked schedule line paid')
      cache.invalidatePlanOnly(company.current)
      await loadPlan(true)
      return
    }
    const targets = groupMembers(row).filter((m) => m.status === 'Planned' && !m._schedule)
    // If parent has schedule children, mark each Planned schedule line
    const scheduleKids = (row._children || []).filter(
      (m) => m._schedule && m.status === 'Planned' && m.split_name,
    )
    if (scheduleKids.length) {
      for (const m of scheduleKids) {
        await call('lyqd.api.spa.mark_upcoming_split_paid', {
          parent: row.name,
          split_row_name: m.split_name,
        })
      }
      toast.success(
        scheduleKids.length > 1
          ? `Marked ${scheduleKids.length} schedule lines paid`
          : 'Marked schedule line paid',
      )
      cache.invalidatePlanOnly(company.current)
      await loadPlan(true)
      return
    }
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
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not mark paid')
  } finally {
    marking.value = null
  }
}

function openAccept(item) {
  const effect =
    item.cash_effect === 'Setoff' ? 'Inflow' : item.cash_effect || 'Outflow'
  Object.assign(form, empty(), {
    source_doctype: item.source_doctype || '',
    source_name: item.source_name || '',
    source_row: item.source_row || '',
    account: item.account || '',
    title: item.title || '',
    category: item.category || 'Other',
    due_date: item.due_date || todayStr(),
    amount: item.amount || 0,
    cash_effect: effect,
    probability: item.probability != null ? Number(item.probability) : 100,
    status: 'Planned',
    notes: '',
  })
  show.value = true
}

async function confirmAccept() {
  if (!form.due_date) {
    toast.error('Due date is required')
    return
  }
  accepting.value = recommendationKey(form)
  saving.value = true
  try {
    const effect = form.cash_effect === 'Setoff' ? 'Inflow' : form.cash_effect || 'Outflow'
    await call('lyqd.api.spa.accept_upcoming_recommendation', {
      company: company.current,
      source_doctype: form.source_doctype,
      source_name: form.source_name,
      source_row: form.source_row || null,
      amount: form.amount,
      title: form.title,
      category: form.category,
      due_date: form.due_date,
      account: form.account || null,
      cash_effect: effect,
      probability: effect === 'Inflow' ? Number(form.probability ?? 100) : 100,
    })
    toast.success('Added to plan')
    show.value = false
    cache.removeRecommendationSource(
      company.current,
      form.source_doctype,
      form.source_name,
    )
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    cache.ensureRecommendations({ company: company.current, force: true, silent: true })
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Accept failed')
  } finally {
    accepting.value = null
    saving.value = false
  }
}

async function confirmIgnore(item) {
  if (!item?.source_doctype || !item?.source_name) {
    toast.error('Cannot ignore this suggestion')
    return
  }
  ignoring.value = recommendationKey(item)
  try {
    const effect = item.cash_effect === 'Setoff' ? 'Inflow' : item.cash_effect || 'Outflow'
    await call('lyqd.api.spa.ignore_upcoming_recommendation', {
      company: company.current,
      source_doctype: item.source_doctype,
      source_name: item.source_name,
      source_row: item.source_row || null,
      amount: item.amount,
      title: item.title,
      category: item.category || 'Other',
      due_date: item.due_date || todayStr(),
      account: item.account || null,
      cash_effect: effect,
    })
    toast.success('Ignored — hidden from suggestions')
    cache.removeRecommendationSource(
      company.current,
      item.source_doctype,
      item.source_name,
    )
    cache.invalidatePlanOnly(company.current)
    await loadPlan(true)
    cache.ensureRecommendations({ company: company.current, force: true, silent: true })
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not ignore')
  } finally {
    ignoring.value = null
  }
}

async function save() {
  saving.value = true
  try {
    const isSplitEdit =
      form.edit_mode === 'split_line' || form.edit_mode === 'split_schedule'
    const splitsPayload =
      isSplitEdit && form.edit_mode === 'split_line'
        ? [
            {
              name: form.split_name,
              probability: Number(form.probability ?? 100),
              status: form.status || 'Planned',
            },
          ]
        : isSplitEdit
          ? (form.splits || []).map((s) => ({
              name: s.name || s.split_name,
              probability: Number(s.probability ?? 100),
              status: s.status || 'Planned',
            }))
          : undefined
    await call('lyqd.api.spa.save_upcoming_payment', {
      doc: {
        name: form.name,
        company: company.current,
        title: form.title,
        category: form.category,
        cash_effect: form.is_recurring ? 'Outflow' : form.cash_effect || 'Outflow',
        probability:
          !isSplitEdit &&
          !form.is_recurring &&
          (form.cash_effect === 'Inflow' || form.cash_effect === 'Setoff')
            ? Number(form.probability ?? 100)
            : undefined,
        due_date: form.due_date,
        amount: form.amount,
        period_amount: form.amount,
        is_recurring: form.is_recurring ? 1 : 0,
        frequency: form.is_recurring ? form.frequency || 'Monthly' : null,
        recurrence_end: form.is_recurring ? form.recurrence_end || null : null,
        status: isSplitEdit
          ? undefined
          : form.is_recurring
            ? 'Planned'
            : form.status || 'Planned',
        notes: form.notes,
        splits: splitsPayload,
      },
    })
    // Close first so a toast render error cannot leave the dialog stuck open.
    show.value = false
    try {
      toast.success('Saved')
    } catch (_) {
      /* toast host is best-effort */
    }
    // Cancelled books rows reappear in From-books; Ignored is handled by Ignore / Accept.
    if (!isSplitEdit && form.source_doctype && form.status === 'Cancelled') {
      cache.invalidatePlanRelated(company.current)
      await reloadAll()
    } else {
      cache.invalidatePlanOnly(company.current)
      await loadPlan(true)
    }
  } catch (e) {
    try {
      toast.error(e.messages?.[0] || e.message || 'Save failed')
    } catch (_) {
      /* ignore */
    }
  } finally {
    saving.value = false
  }
}
</script>
